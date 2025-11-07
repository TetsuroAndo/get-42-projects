"""Anytype同期処理モジュール

42のプロジェクトセッション情報を取得し、Anytypeに同期する処理を担当します。
"""
import logging
from typing import List, Optional
from dataclasses import dataclass

from auth42 import Auth42
from src.config import Config, get_default_cache_path
from src.fortytwo_api import Project42
from src.payloads import ProjectSession
from src.exceptions import SyncError, Project42Error
from src.converters import project_session_to_object
from src.cache import SQLiteCache, CacheBase
from anytype import AnytypeClient, ObjectManager, AnytypeObject
from .cache_manager import CacheManager
from .batch_processor import BatchProcessor


@dataclass
class SyncResult:
    """同期処理の結果"""
    total_sessions: int = 0
    success_count: int = 0
    error_count: int = 0
    skipped_count: int = 0

    def __str__(self) -> str:
        return (
            f"総セッション数: {self.total_sessions}, "
            f"成功: {self.success_count}, "
            f"エラー: {self.error_count}, "
            f"スキップ: {self.skipped_count}"
        )


class ProjectSessionSyncer:
    """プロジェクトセッション同期クラス

    42のプロジェクトセッション情報を取得し、Anytypeに同期します。
    """

    def __init__(
        self,
        config: Config,
        auth: Auth42,
        logger: logging.Logger,
    ):
        """同期クラスの初期化

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

        # Anytypeクライアントを初期化
        self.anytype_client = AnytypeClient(
            api_url=config.anytype_api_url,
            api_key=config.anytype_api_key,
        )

        # オブジェクトマネージャーを初期化
        self.object_manager = ObjectManager(
            client=self.anytype_client,
            space_id=config.anytype_space_id,
        )

        # キャッシュを初期化
        cache_path = config.cache_db_path or get_default_cache_path()
        self.cache: CacheBase = SQLiteCache(db_path=cache_path, logger=logger)
        self.logger.info(f"キャッシュを初期化しました: {cache_path}")

        # 復元済みセッションIDのセット（重複送信を防ぐため）
        self._restored_session_ids: set[int] = set()

        # ヘルパークラスを初期化
        self.cache_manager = CacheManager(
            cache=self.cache,
            logger=self.logger,
            restored_session_ids=self._restored_session_ids
        )
        self.batch_processor = BatchProcessor(
            object_manager=self.object_manager,
            cache_manager=self.cache_manager,
            batch_size=config.batch_size,
            logger=self.logger
        )

    def fetch_sessions(
        self,
        campus_id: Optional[int] = None,
        is_subscriptable: bool = True,
    ) -> List[ProjectSession]:
        """プロジェクトセッションを取得

        Args:
            campus_id: キャンパスID(Noneの場合は設定値を使用)
            is_subscriptable: 利用可能なプロジェクトのみを取得するか

        Returns:
            プロジェクトセッションのリスト
        """
        campus_id = campus_id or self.config.fortytwo_campus_id or 26  # 東京キャンパスは26

        self.logger.info(f"プロジェクトセッションを取得中... (campus_id={campus_id})")

        sessions = self.project42.get_all_project_sessions(
            campus_id=campus_id,
            is_subscriptable=is_subscriptable,
        )

        self.logger.info(f"{len(sessions)}件のプロジェクトセッションを取得しました")
        return sessions

    def fetch_details(
        self,
        sessions: List[ProjectSession],
    ) -> List[ProjectSession]:
        """プロジェクトセッションの詳細情報を取得

        Args:
            sessions: プロジェクトセッションのリスト

        Returns:
            詳細情報が追加されたプロジェクトセッションのリスト
        """
        self.logger.info("詳細情報を取得中...")
        sessions_with_details = []

        for idx, session in enumerate(sessions, 1):
            try:
                session_with_details = self.project42.get_project_session_with_details(session)
                sessions_with_details.append(session_with_details)
                # キャッシュに保存
                self.cache_manager.save_session(session_with_details)

                # 進捗表示
                if idx % self.config.detail_fetch_interval == 0:
                    self.logger.info(
                        f"  詳細情報取得進捗: {idx}/{len(sessions)} "
                        f"(プロジェクト: {session.project_name})"
                    )
            except Project42Error as e:
                self.logger.warning(
                    f"セッションID {session.id} ({session.project_name}) の詳細情報取得に失敗: {e}"
                )
                # 詳細情報が取得できなくても基本情報は残す
                sessions_with_details.append(session)
                # 基本情報でもキャッシュに保存
                self.cache_manager.save_session(session)
            except Exception as e:
                self.logger.warning(
                    f"セッションID {session.id} ({session.project_name}) の詳細情報取得に予期しないエラーが発生: {e}"
                )
                # 詳細情報が取得できなくても基本情報は残す
                sessions_with_details.append(session)
                # 基本情報でもキャッシュに保存
                self.cache_manager.save_session(session)

        self.logger.info(
            f"{len(sessions_with_details)}件のプロジェクトセッションの詳細情報を取得しました"
        )
        return sessions_with_details

    def convert_to_objects(self, sessions: List[ProjectSession]) -> List[AnytypeObject]:
        """プロジェクトセッションをオブジェクトに変換

        Args:
            sessions: プロジェクトセッションのリスト

        Returns:
            オブジェクトのリスト
        """
        self.logger.info("プロジェクトセッションをオブジェクト形式に変換中...")
        objects = [project_session_to_object(session) for session in sessions]
        self.logger.info(f"{len(objects)}件のオブジェクトを生成しました")
        return objects

    def save_to_anytype(
        self,
        objects: List[AnytypeObject],
        sessions: Optional[List[ProjectSession]] = None,
    ) -> tuple[int, int]:
        """Anytypeにオブジェクトを保存

        Args:
            objects: オブジェクトのリスト
            sessions: 対応するプロジェクトセッションのリスト(キャッシュ削除用、オプション)

        Returns:
            (成功数, エラー数) のタプル
        """
        return self.batch_processor.save_objects(objects, sessions)

    def sync(
        self,
        campus_id: Optional[int] = None,
        is_subscriptable: bool = True,
    ) -> SyncResult:
        """プロジェクトセッションを同期

        Args:
            campus_id: キャンパスID(Noneの場合は設定値を使用)
            is_subscriptable: 利用可能なプロジェクトのみを取得するか

        Returns:
            同期処理の結果
        """
        result = SyncResult()

        try:
            # プロジェクトセッションを取得
            sessions = self.fetch_sessions(
                campus_id=campus_id,
                is_subscriptable=is_subscriptable,
            )
            result.total_sessions = len(sessions)

            if not sessions:
                self.logger.warning("取得したプロジェクトセッションがありません")
                return result

            # 詳細情報を取得
            sessions_with_details = self.fetch_details(sessions)

            # オブジェクトに変換
            objects = self.convert_to_objects(sessions_with_details)

            # Anytypeに保存(セッション情報も渡してキャッシュ削除を可能にする)
            success_count, error_count = self.save_to_anytype(objects, sessions_with_details)
            result.success_count = success_count
            result.error_count = error_count

        except Project42Error as e:
            self.logger.error(f"プロジェクト取得エラー: {e}", exc_info=True)
            raise SyncError(
                "プロジェクト取得中にエラーが発生しました",
                original_error=e
            ) from e
        except Exception as e:
            self.logger.error(f"同期処理中に予期しないエラーが発生しました: {e}", exc_info=True)
            raise SyncError(
                "同期処理中に予期しないエラーが発生しました",
                original_error=e
            ) from e

        return result

    def restore_from_cache(self) -> SyncResult:
        """キャッシュから未送信のセッションを復元してAnytypeに送信

        Returns:
            同期処理の結果
        """
        result = SyncResult()

        try:
            # 未送信のセッションを取得
            pending_sessions = self.cache.get_pending()
            result.total_sessions = len(pending_sessions)

            if not pending_sessions:
                self.logger.info("復元するキャッシュがありません")
                return result

            self.logger.info(f"キャッシュから {len(pending_sessions)}件のセッションを復元します")

            # オブジェクトに変換
            objects = self.convert_to_objects(pending_sessions)

            # Anytypeに保存
            success_count, error_count = self.save_to_anytype(objects, pending_sessions)
            result.success_count = success_count
            result.error_count = error_count

            # 送信成功したセッションIDを記録（重複送信を防ぐため）
            for session in pending_sessions:
                # キャッシュから削除されたか確認（削除されていれば送信成功）
                cached_session = self.cache.get(session.id)
                if cached_session is None:
                    self._restored_session_ids.add(session.id)
                    self.logger.debug(f"復元済みセッションIDを記録: session_id={session.id}")

            self.logger.info(f"キャッシュ復元完了: 成功 {success_count}件, エラー {error_count}件")

        except Exception as e:
            self.logger.error(f"キャッシュ復元中にエラーが発生しました: {e}", exc_info=True)
            raise SyncError(
                "キャッシュ復元中にエラーが発生しました",
                original_error=e
            ) from e

        return result
