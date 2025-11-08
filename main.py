"""メインスクリプト

42からプロジェクト情報を取得し、Anytypeにインポートします。
ガイドに基づいて、プロジェクトセッション情報を取得します。
"""
import sys
import argparse
from dotenv import load_dotenv
from src.config import Config, get_default_cache_path
from src.logger import setup_logger
from src import ProjectSessionSyncer
from src.cache import SQLiteCache
from auth42 import Auth42, TokenManager, TokenError, Auth42Error
from src import (
    Project42Error,
    ConfigurationError,
    SyncError,
)
from src.planner import RequestPlanner


def main():
    """メイン処理"""
    # .envファイルから環境変数を読み込む
    load_dotenv()

    # コマンドライン引数の解析
    parser = argparse.ArgumentParser(
        description="42からプロジェクト情報を取得し、Anytypeにインポートします",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 全ての操作を実行（デフォルト）
  python main.py

  # キャッシュに溜まっている情報をAnytypeに送信する
  python main.py --sync-cache

  # 42APIから取得してキャッシングする
  python main.py --fetch-only

  # キャッシュの内容を確認
  python main.py --show-cache

  # APIリクエスト候補を列挙（実際には送信しない）
  python main.py --plan

  # 複数のオプションを組み合わせることはできません
        """.strip()
    )

    parser.add_argument(
        "--sync-cache",
        action="store_true",
        help="キャッシュに溜まっている情報をAnytypeに送信するだけ実行します",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="42APIから取得してキャッシングするだけ実行します（Anytypeには送信しません）",
    )
    parser.add_argument(
        "--show-cache",
        action="store_true",
        help="キャッシュの内容を確認します",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="ローカルキャッシュに基づき、APIリクエスト候補を列挙します",
    )

    args = parser.parse_args()

    # --plan オプションが指定された場合は即座に実行
    if args.plan:
        # --planと他のフラグが同時に指定された場合はエラー
        option_count = sum([
            args.sync_cache,
            args.fetch_only,
            args.show_cache,
        ])
        if option_count > 0:
            parser.error("--planと他のオプションを同時に指定することはできません")
        run_plan()
        return

    # 複数のオプションが指定された場合はエラー
    option_count = sum([
        args.sync_cache,
        args.fetch_only,
        args.show_cache,
        args.plan,
    ])
    if option_count > 1:
        parser.error("複数のオプションを同時に指定することはできません")

    # --show-cache の場合は設定の検証をスキップ（キャッシュの確認のみ）
    if args.show_cache:
        show_cache_info()
        return

    logger = None

    try:
        # 設定を読み込む
        config = Config.from_env()

        # --fetch-only の場合はAnytype設定の検証をスキップ
        if not args.fetch_only:
            config.validate()
        else:
            # fetch-onlyの場合は42API設定のみ検証
            if not config.fortytwo_client_id or not config.fortytwo_client_secret:
                raise ConfigurationError("FT_UID と FT_SECRET が設定されていません")

        # ロギング設定（設定ファイルのパスを使用）
        logger = setup_logger(
            name="get_42_projects",
            log_file=config.log_file,
            console=True,
        )

        logger.info("=" * 60)
        logger.info("42プロジェクト取得スクリプト開始")
        logger.info("=" * 60)
        logger.info("設定の読み込みが完了しました")

        # 42認証を初期化
        token_manager = TokenManager(token_file=config.token_file)
        auth = Auth42(
            client_id=config.fortytwo_client_id,
            client_secret=config.fortytwo_client_secret,
            token_manager=token_manager,
        )
        logger.info("42認証の初期化が完了しました")

        # --sync-cache オプションが指定された場合
        if args.sync_cache:
            # 同期処理を初期化
            syncer = ProjectSessionSyncer(
                config=config,
                auth=auth,
                logger=logger,
            )
            logger.info("=" * 60)
            logger.info("キャッシュからAnytypeへの送信処理を開始します...")
            logger.info("=" * 60)
            try:
                cache_result = syncer.restore_from_cache()
                logger.info("=" * 60)
                logger.info("キャッシュ送信処理が完了しました")
                logger.info(f"  {cache_result}")
                logger.info("=" * 60)
                if cache_result.error_count > 0:
                    sys.exit(1)
            except SyncError as e:
                logger.error(f"キャッシュ送信中にエラーが発生しました: {e}", exc_info=True)
                sys.exit(1)
            except Exception as e:
                logger.error(f"キャッシュ送信中に予期せぬエラーが発生しました: {e}", exc_info=True)
                sys.exit(1)
            return

        # --fetch-only オプションが指定された場合
        if args.fetch_only:
            try:
                # Anytype設定が未設定の場合、ダミー値を設定（ProjectSessionSyncerの初期化に必要）
                if not config.anytype_api_key:
                    config.anytype_api_key = "dummy_for_fetch_only"
                if not config.anytype_space_id:
                    config.anytype_space_id = "dummy_for_fetch_only"

                # 同期処理を初期化（fetch_and_cacheメソッドを使用）
                syncer = ProjectSessionSyncer(
                    config=config,
                    auth=auth,
                    logger=logger,
                )

                # fetch_and_cacheメソッドを呼び出し
                fetched_count, saved_count, error_count = syncer.fetch_and_cache(
                    campus_id=config.fortytwo_campus_id,
                    is_subscriptable=True,
                )

                if error_count > 0:
                    logger.warning(f"一部の処理でエラーが発生しました（エラー数: {error_count}）")
                    sys.exit(1)
            except Project42Error as e:
                logger.error(f"プロジェクト取得エラー: {e}", exc_info=True)
                sys.exit(1)
            except Exception as e:
                logger.error(f"取得処理中に予期しないエラーが発生しました: {e}", exc_info=True)
                sys.exit(1)
            return

        # デフォルト動作: 全ての操作を実行
        # 同期処理を初期化
        syncer = ProjectSessionSyncer(
            config=config,
            auth=auth,
            logger=logger,
        )

        # 起動時にキャッシュから未送信のセッションを復元
        logger.info("キャッシュからの復元処理を開始します...")
        try:
            cache_result = syncer.restore_from_cache()
            if cache_result.total_sessions > 0:
                logger.info("=" * 60)
                logger.info("キャッシュ復元処理が完了しました")
                logger.info(f"  {cache_result}")
                logger.info("=" * 60)
            else:
                logger.info("復元するキャッシュはありませんでした")
        except SyncError as e:
            logger.warning(f"キャッシュ復元中にエラーが発生しましたが、処理を続行します: {e}")
        except Exception as e:
            logger.error(f"キャッシュ復元中に予期せぬエラーが発生しましたが、処理を続行します: {e}", exc_info=True)

        # メインの同期処理を実行
        result = syncer.sync(
            campus_id=config.fortytwo_campus_id,
            is_subscriptable=True,  # 利用可能なプロジェクトのみ
        )

        logger.info("=" * 60)
        logger.info("処理が完了しました！")
        logger.info(f"  {result}")
        logger.info("=" * 60)

        # エラーがある場合はexit code 1を返す
        if result.error_count > 0:
            sys.exit(1)

    except ConfigurationError as e:
        if logger:
            logger.error(f"設定エラー: {e}", exc_info=True)
        else:
            print(f"設定エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        if logger:
            logger.error(f"設定エラー: {e}", exc_info=True)
        else:
            print(f"設定エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except (TokenError, Auth42Error) as e:
        if logger:
            logger.error(f"認証エラー: {e}", exc_info=True)
        else:
            print(f"認証エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Project42Error as e:
        if logger:
            logger.error(f"プロジェクト取得エラー: {e}", exc_info=True)
        else:
            print(f"プロジェクト取得エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except SyncError as e:
        if logger:
            logger.error(f"同期エラー: {e}", exc_info=True)
        else:
            print(f"同期エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if logger:
            logger.error(f"予期しないエラーが発生しました: {e}", exc_info=True)
        else:
            print(f"予期しないエラーが発生しました: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        sys.exit(1)


def run_plan():
    """実行計画を立て、リクエスト候補を列挙します。"""
    logger = None
    try:
        # 設定を読み込む（planコマンドは厳格なバリデーションをスキップ）
        config = Config.from_env()
        cache_path = config.cache_db_path or get_default_cache_path()

        # ロギング設定
        logger = setup_logger(
            name="get_42_projects",
            log_file=config.log_file,
            console=True,
        )

        logger.info("=" * 60)
        logger.info("--- Planモード実行 ---")
        logger.info("ローカルキャッシュを読み込み、42 APIへのリクエスト候補を列挙します。")
        logger.info("=" * 60)

        if not cache_path.exists():
            logger.error(f"キャッシュファイルが見つかりません: {cache_path}")
            logger.error("先に `python main.py --fetch-only` コマンドを実行してキャッシュを作成してください。")
            logger.info("キャッシュがない場合のテンプレートリクエストを表示します...")

        # キャッシュを初期化（ファイルが存在しなくても初期化は可能）
        cache = SQLiteCache(db_path=cache_path, logger=logger)
        # キャッシュファイルが存在しなくても、get_all()は空リストを返す
        cached_sessions = cache.get_all()

        if cached_sessions:
            logger.info(f"キャッシュから {len(cached_sessions)} 件のセッションを読み込みました。")
        else:
            logger.warning("キャッシュが空です。テンプレートリクエストのみを表示します。")

        # プランナーを実行
        planner = RequestPlanner(config=config, logger=logger)
        planner.plan_requests_from_cache(cached_sessions)

    except Exception as e:
        if logger:
            logger.error(f"計画の生成中にエラーが発生しました: {e}", exc_info=True)
        else:
            print(f"計画の生成中にエラーが発生しました: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        sys.exit(1)


def show_cache_info():
    """キャッシュの内容を表示"""
    try:
        # 設定を読み込む（キャッシュパスのみ使用）
        config = Config.from_env()
        cache_path = config.cache_db_path or get_default_cache_path()

        # ロガーを初期化（簡易版）
        import logging
        logger = logging.getLogger("cache_info")
        logger.setLevel(logging.WARNING)  # エラーのみ表示

        # キャッシュを初期化
        cache = SQLiteCache(db_path=cache_path, logger=logger)

        # 統計情報を取得
        stats = cache.get_stats()

        print("=" * 60)
        print("キャッシュ情報")
        print("=" * 60)
        print(f"キャッシュファイル: {cache_path}")
        print(f"総件数: {stats['total']}")
        print(f"  未送信 (pending): {stats['pending']}")
        print(f"  送信済み (sent): {stats['sent']}")
        print("=" * 60)

        # 未送信のセッションがある場合は詳細を表示
        if stats['pending'] > 0:
            print("\n未送信セッションの詳細:")
            pending_sessions = cache.get_pending()
            for idx, session in enumerate(pending_sessions[:10], 1):  # 最大10件まで表示
                print(f"  {idx}. ID: {session.id}, プロジェクト: {session.project_name}")
            if len(pending_sessions) > 10:
                print(f"  ... 他 {len(pending_sessions) - 10} 件")

    except Exception as e:
        print(f"❌ キャッシュ情報の取得に失敗しました: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
