"""42 APIからの取得とキャッシュ処理モジュール

42のプロジェクトセッション情報を取得し、キャッシュに保存する処理を担当します。
"""
import logging
import re
from typing import Tuple

from auth42 import Auth42
from src.config import Config, get_default_cache_path
from src.fortytwo_api import Project42
from src.exceptions import Project42Error
from src.cache import SQLiteCache, CacheBase
from src.anytype_sync.cache_manager import CacheManager


class ProjectSessionFetcher:
    """プロジェクトセッション取得・キャッシュクラス

    42のプロジェクトセッション情報を取得し、キャッシュに保存します。
    """

    def __init__(
        self,
        config: Config,
        auth: Auth42,
        logger: logging.Logger,
    ):
        """取得クラスの初期化

        Args:
            config: アプリケーション設定
            auth: 42認証オブジェクト
            logger: ロガー
        """
        self.config = config
        self.auth = auth
        self.logger = logger

        # プロジェクト取得クライアントを初期化
        self.project42 = Project42(auth=auth, logger=logger, config=config)

        # キャッシュを初期化
        cache_path = config.cache_db_path or get_default_cache_path()
        self.cache: CacheBase = SQLiteCache(db_path=cache_path, logger=logger)
        self.logger.info(f"キャッシュを初期化しました: {cache_path}")

        # キャッシュマネージャーを初期化
        self.cache_manager = CacheManager(
            cache=self.cache,
            logger=self.logger
        )

    def fetch_and_cache(
        self,
        campus_id: int = None,
        is_subscriptable: bool = True,
    ) -> Tuple[int, int, int]:
        """プロジェクトセッションを取得し、取得したらすぐにキャッシュに保存

        Args:
            campus_id: キャンパスID(Noneの場合は設定値を使用)
            is_subscriptable: 利用可能なプロジェクトのみを取得するか

        Returns:
            (取得成功数, キャッシュ保存成功数, エラー数) のタプル
        """
        campus_id = campus_id or self.config.fortytwo_campus_id or 26

        self.logger.info("=" * 60)
        self.logger.info("42APIから取得してキャッシングする処理を開始します...")
        self.logger.info("=" * 60)

        # プロジェクトセッションを取得
        self.logger.info(f"プロジェクトセッションを取得中... (campus_id={campus_id})")
        sessions = self.project42.get_all_project_sessions(
            campus_id=campus_id,
            is_subscriptable=is_subscriptable,
        )
        self.logger.info(f"{len(sessions)}件のプロジェクトセッションを取得しました")

        if not sessions:
            self.logger.warning("取得したプロジェクトセッションがありません")
            return (0, 0, 0)

        # リクエストカウンターをリセット（追加リクエストの統計を開始）
        self.project42.session_details_fetcher.reset_request_counter()

        # 詳細情報を取得し、取得したらすぐにキャッシュに保存
        self.logger.info("Fetchフェーズ: 詳細情報を取得中（取得と同時にキャッシュに保存します）...")
        fetched_count = 0
        saved_count = 0
        error_count = 0
        cache_error_count = 0

        for idx, session in enumerate(sessions, 1):
            try:
                # 詳細情報を取得
                session_with_details = self.project42.get_project_session_with_details(session)
                fetched_count += 1

                # 取得したらすぐにキャッシュに保存
                try:
                    self.cache_manager.save_session(session_with_details, anytype_object_id=None)
                    saved_count += 1
                except Exception as e:
                    cache_error_count += 1
                    self.logger.warning(
                        f"セッションID {session.id} ({session.project_name}) のキャッシュ保存に失敗: {e}"
                    )

                # 進捗表示
                if idx % self.config.detail_fetch_interval == 0:
                    self.logger.info(
                        f"  進捗: {idx}/{len(sessions)} "
                        f"(取得: {fetched_count}, キャッシュ保存: {saved_count}, エラー: {error_count + cache_error_count}) "
                        f"プロジェクト: {session.project_name}"
                    )
            except Project42Error as e:
                error_count += 1
                self.logger.warning(
                    f"セッションID {session.id} ({session.project_name}) の詳細情報取得に失敗: {e}"
                )
                # 取得に失敗した場合でも基本情報をキャッシュに保存
                try:
                    self.cache_manager.save_session(session, anytype_object_id=None)
                    saved_count += 1
                except Exception as cache_e:
                    cache_error_count += 1
                    self.logger.warning(f"セッションID {session.id} のキャッシュ保存に失敗: {cache_e}")
            except Exception as e:
                error_count += 1
                self.logger.warning(
                    f"セッションID {session.id} ({session.project_name}) の詳細情報取得に予期しないエラーが発生: {e}"
                )
                # 取得に失敗した場合でも基本情報をキャッシュに保存
                try:
                    self.cache_manager.save_session(session, anytype_object_id=None)
                    saved_count += 1
                except Exception as cache_e:
                    cache_error_count += 1
                    self.logger.warning(f"セッションID {session.id} のキャッシュ保存に失敗: {cache_e}")

        self.logger.info("=" * 60)
        self.logger.info("Fetchフェーズ完了")
        self.logger.info(f"  詳細情報取得: {fetched_count}/{len(sessions)}")
        self.logger.info(f"  キャッシュ保存: {saved_count}/{len(sessions)}")
        if error_count > 0:
            self.logger.warning(f"  取得エラー: {error_count}")
        if cache_error_count > 0:
            self.logger.warning(f"  キャッシュ保存エラー: {cache_error_count}")

        # 追加リクエストの統計情報を表示
        request_summary = self.project42.session_details_fetcher.get_request_summary()
        if request_summary["total_requests"] > 0:
            self.logger.info("=" * 60)
            self.logger.info("追加リクエスト統計")
            self.logger.info(f"  総リクエスト数: {request_summary['total_requests']}")
            self.logger.info("  エンドポイント別リクエスト数:")
            # エンドポイントをパターン別に集計
            endpoint_patterns = {}
            for endpoint, count in request_summary["endpoint_counts"].items():
                # パターンを抽出（例: /v2/project_sessions/{id}/skills -> /v2/project_sessions/*/skills）
                pattern = re.sub(r'/\d+', '/*', endpoint)
                pattern = re.sub(r'\?page=\d+', '?page=*', pattern)
                if pattern not in endpoint_patterns:
                    endpoint_patterns[pattern] = 0
                endpoint_patterns[pattern] += count

            for pattern, count in sorted(endpoint_patterns.items(), key=lambda x: x[1], reverse=True):
                self.logger.info(f"    {pattern}: {count}回")
            self.logger.info("=" * 60)

        self.logger.info("=" * 60)

        return (fetched_count, saved_count, error_count + cache_error_count)
