"""メインスクリプト

42からプロジェクト情報を取得し、Anytypeにインポートします。
ガイドに基づいて、プロジェクトセッション情報を取得します。
"""
import sys

from src.config import Config
from src.logger import setup_logger
from src.sync import ProjectSessionSyncer
from auth42 import Auth42, TokenManager, TokenError, Auth42Error
from src import Project42Error


def main():
    """メイン処理"""
    logger = None

    try:
        # 設定を読み込む
        config = Config.from_env()
        config.validate()

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

        # 同期処理を実行
        syncer = ProjectSessionSyncer(
            config=config,
            auth=auth,
            logger=logger,
        )

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
    except Exception as e:
        if logger:
            logger.error(f"予期しないエラーが発生しました: {e}", exc_info=True)
        else:
            print(f"予期しないエラーが発生しました: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
