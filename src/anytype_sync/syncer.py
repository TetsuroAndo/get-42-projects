"""Anytype同期処理モジュール

キャッシュからプロジェクトセッション情報を読み取り、Anytypeに同期する処理を担当します。
"""
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from src.config import Config, get_default_cache_path
from src.payloads import ProjectSession
from src.exceptions import SyncError
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
        logger: logging.Logger,
    ):
        """同期クラスの初期化

        Args:
            config: アプリケーション設定
            logger: ロガー
        """
        self.config = config
        self.logger = logger

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

        # ヘルパークラスを初期化
        self.cache_manager = CacheManager(
            cache=self.cache,
            logger=self.logger
        )
        self.batch_processor = BatchProcessor(
            object_manager=self.object_manager,
            cache_manager=self.cache_manager,
            batch_size=config.batch_size,
            logger=self.logger
        )

    def _sessions_are_equal(self, session1: ProjectSession, session2: ProjectSession) -> bool:
        """2つのセッションが等しいかどうかを比較

        anytype_object_idを除外して、内容が完全に一致するかをチェックします。

        Args:
            session1: 比較するセッション1
            session2: 比較するセッション2

        Returns:
            完全に一致する場合はTrue、そうでなければFalse
        """
        if session1 is None or session2 is None:
            return False

        # セッションの辞書形式に変換して比較
        dict1 = session1.to_dict()
        dict2 = session2.to_dict()

        # IDとanytype_object_idは比較から除外
        # IDは常に一致するため、anytype_object_idはキャッシュにのみ存在するため
        excluded_keys = {"id", "anytype_object_id"}

        # その他のフィールドを比較
        for key in dict1.keys():
            if key in excluded_keys:
                continue
            if dict1.get(key) != dict2.get(key):
                return False

        return True

    def diff_sessions(
        self,
        fetched_sessions: List[ProjectSession]
    ) -> Tuple[List[ProjectSession], List[Tuple[ProjectSession, str]], List[ProjectSession]]:
        """セッションを比較して新規/更新/スキップを分類（Diffフェーズ）

        Args:
            fetched_sessions: Fetchフェーズで取得したセッションのリスト

        Returns:
            (新規セッションリスト, (更新セッション, anytype_object_id)のリスト, スキップセッションリスト)のタプル
        """
        create_list: List[ProjectSession] = []
        update_list: List[Tuple[ProjectSession, str]] = []
        skip_list: List[ProjectSession] = []

        self.logger.info("Diffフェーズ: キャッシュと比較して新規/更新/スキップを分類中...")

        for session in fetched_sessions:
            cached_session = self.cache_manager.get_session(session.id)

            if cached_session is None:
                # キャッシュに存在しない = 新規
                create_list.append(session)
            else:
                # キャッシュに存在する = 更新またはスキップ
                if self._sessions_are_equal(session, cached_session):
                    # 内容が完全に一致 = スキップ
                    skip_list.append(session)
                else:
                    # 内容が異なる = 更新
                    # anytype_object_idを取得
                    anytype_object_id = self.cache_manager.get_anytype_object_id(session.id)
                    if anytype_object_id:
                        update_list.append((session, anytype_object_id))
                    else:
                        # anytype_object_idがない場合は新規として扱う
                        self.logger.warning(
                            f"セッションID {session.id} はキャッシュに存在しますが、"
                            f"anytype_object_idがありません。新規として扱います。"
                        )
                        create_list.append(session)

        self.logger.info(
            f"Diffフェーズ完了: 新規 {len(create_list)}件, "
            f"更新 {len(update_list)}件, スキップ {len(skip_list)}件"
        )

        return create_list, update_list, skip_list

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
        """プロジェクトセッションを同期（3フェーズ: Fetch/Diff/Sync）

        Args:
            campus_id: キャンパスID(Noneの場合は設定値を使用)
            is_subscriptable: 利用可能なプロジェクトのみを取得するか

        Returns:
            同期処理の結果
        """
        result = SyncResult()

        try:
            # ===== フェーズ1: Fetch（取得フェーズ） =====
            self.logger.info("=" * 60)
            self.logger.info("フェーズ1: Fetch（取得フェーズ）")
            self.logger.info("=" * 60)

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

            # ===== フェーズ2: Diff（差分検出フェーズ） =====
            self.logger.info("=" * 60)
            self.logger.info("フェーズ2: Diff（差分検出フェーズ）")
            self.logger.info("=" * 60)

            create_list, update_list, skip_list = self.diff_sessions(sessions_with_details)
            result.skipped_count = len(skip_list)

            # ===== フェーズ3: Sync（同期フェーズ） =====
            self.logger.info("=" * 60)
            self.logger.info("フェーズ3: Sync（同期フェーズ）")
            self.logger.info("=" * 60)

            # 新規セッションをAnytypeに作成
            if create_list:
                create_objects = self.convert_to_objects(create_list)
                create_success, create_errors = self.batch_processor.create_objects(
                    create_objects, create_list
                )
                result.success_count += create_success
                result.error_count += create_errors
            else:
                self.logger.info("新規作成するセッションはありません")

            # 更新セッションをAnytypeに更新
            if update_list:
                update_sessions = [session for session, _ in update_list]
                update_objects = self.convert_to_objects(update_sessions)
                update_success, update_errors = self.batch_processor.update_objects(
                    update_objects, update_list
                )
                result.success_count += update_success
                result.error_count += update_errors
            else:
                self.logger.info("更新するセッションはありません")

            self.logger.info("=" * 60)
            self.logger.info("同期処理完了")
            self.logger.info("=" * 60)

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
        """キャッシュ内の未送信(pending)データをAnytypeに同期（復元）

        main.py の sync() の前に実行されることを想定。

        Returns:
            同期処理の結果
        """
        result = SyncResult()

        self.logger.info("=" * 60)
        self.logger.info("キャッシュ復元処理を開始...")
        self.logger.info("=" * 60)

        try:
            pending_sessions = self.cache.get_pending()
            result.total_sessions = len(pending_sessions)
            if not pending_sessions:
                self.logger.info("復元するキャッシュ（未送信データ）はありませんでした。")
                return result

            self.logger.info(f"キャッシュから {len(pending_sessions)}件の未送信セッションを復元します")

            # 未送信データを「新規」と「更新」に分類
            sessions_to_create: List[ProjectSession] = []
            sessions_to_update: List[Tuple[ProjectSession, str]] = []

            for session in pending_sessions:
                # キャッシュからanytype_object_idを取得
                anytype_id = self.cache.get_anytype_object_id(session.id)
                if anytype_id:
                    # IDがある = 更新
                    sessions_to_update.append((session, anytype_id))
                else:
                    # IDがない = 新規
                    sessions_to_create.append(session)

            # 3. Anytypeへ作成 (復元)
            if sessions_to_create:
                self.logger.info(f"[復元] {len(sessions_to_create)}件の新規オブジェクトを作成します...")
                objects_to_create = self.convert_to_objects(sessions_to_create)
                s, e = self.batch_processor.create_objects(objects_to_create, sessions_to_create)
                result.success_count += s
                result.error_count += e

            # 4. Anytypeへ更新 (復元)
            if sessions_to_update:
                self.logger.info(f"[復元] {len(sessions_to_update)}件の既存オブジェクトを更新します...")
                # (session, id) のタプルから session のリストを抽出
                update_session_list = [session for session, _ in sessions_to_update]
                objects_to_update = self.convert_to_objects(update_session_list)
                s, e = self.batch_processor.update_objects(objects_to_update, sessions_to_update)
                result.success_count += s
                result.error_count += e

            self.logger.info(f"キャッシュ復元完了: 成功 {result.success_count}件, エラー {result.error_count}件")

        except Exception as e:
            self.logger.error(f"キャッシュ復元中にエラーが発生しました: {e}", exc_info=True)
            raise SyncError(
                "キャッシュ復元中にエラーが発生しました",
                original_error=e
            ) from e

        return result
