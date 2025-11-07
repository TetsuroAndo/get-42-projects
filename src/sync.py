"""同期処理モジュール

42のプロジェクトセッション情報を取得し、Anytypeに同期する処理を担当します。
"""
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from auth42 import Auth42
from src.config import Config, get_default_cache_path
from src.projects import Project42
from src.payloads import ProjectSession
from src.exceptions import SyncError, Project42Error
from src.converters import project_session_to_object
from src.cache import SQLiteCache, CacheBase
from anytype import AnytypeClient, ObjectManager, AnytypeObject


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
        campus_id = campus_id or self.config.fortytwo_campus_id or 9  # 東京キャンパスは9

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

                # 復元済みセッションはキャッシュに保存しない（重複送信を防ぐ）
                if session.id not in self._restored_session_ids:
                    # キャッシュに保存
                    try:
                        self.cache.save(session_with_details)
                    except Exception as e:
                        self.logger.warning(f"キャッシュ保存エラー (session_id={session.id}): {e}")

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
                # 復元済みセッションはキャッシュに保存しない（重複送信を防ぐ）
                if session.id not in self._restored_session_ids:
                    # 基本情報でもキャッシュに保存
                    try:
                        self.cache.save(session)
                    except Exception as e:
                        self.logger.warning(f"キャッシュ保存エラー (session_id={session.id}): {e}")
            except Exception as e:
                self.logger.warning(
                    f"セッションID {session.id} ({session.project_name}) の詳細情報取得に予期しないエラーが発生: {e}"
                )
                # 詳細情報が取得できなくても基本情報は残す
                sessions_with_details.append(session)
                # 復元済みセッションはキャッシュに保存しない（重複送信を防ぐ）
                if session.id not in self._restored_session_ids:
                    # 基本情報でもキャッシュに保存
                    try:
                        self.cache.save(session)
                    except Exception as e:
                        self.logger.warning(f"キャッシュ保存エラー (session_id={session.id}): {e}")

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
    ) -> Tuple[int, int]:
        """Anytypeにオブジェクトを保存

        Args:
            objects: オブジェクトのリスト
            sessions: 対応するプロジェクトセッションのリスト(キャッシュ削除用、オプション)

        Returns:
            (成功数, エラー数) のタプル
        """
        # objectsとsessionsの順序が一致していることを確認
        if sessions is not None:
            if len(objects) != len(sessions):
                raise SyncError(
                    f"objectsとsessionsの長さが一致しません: "
                    f"objects={len(objects)}, sessions={len(sessions)}"
                )

            # 各オブジェクトの名前と対応するセッションのプロジェクト名が一致しているか確認
            mismatches = []
            for idx, (obj, session) in enumerate(zip(objects, sessions)):
                if obj.name != session.project_name:
                    mismatches.append(
                        f"インデックス {idx}: オブジェクト名='{obj.name}', "
                        f"セッション名='{session.project_name}'"
                    )

            if mismatches:
                error_msg = (
                    "objectsとsessionsの順序が一致していません。"
                    f"不一致が{len(mismatches)}件見つかりました:\n"
                    + "\n".join(mismatches[:10])  # 最初の10件のみ表示
                )
                if len(mismatches) > 10:
                    error_msg += f"\n... 他{len(mismatches) - 10}件"
                self.logger.error(error_msg)
                raise SyncError(error_msg)

        self.logger.info("Anytypeにオブジェクトを追加中...")
        batch_size = self.config.batch_size
        success_count = 0
        error_count = 0

        for i in range(0, len(objects), batch_size):
            batch = objects[i:i + batch_size]
            batch_sessions = sessions[i:i + batch_size] if sessions else None
            try:
                results = self.object_manager.create_objects(batch)
                # エラーがないかチェック
                batch_success_indices = []
                batch_error_indices = []
                for idx, r in enumerate(results):
                    if "error" not in r:
                        batch_success_indices.append(idx)
                    else:
                        batch_error_indices.append(idx)

                success_count += len(batch_success_indices)
                error_count += len(batch_error_indices)

                # 成功したセッションのキャッシュを削除
                if batch_sessions:
                    for idx in batch_success_indices:
                        try:
                            session = batch_sessions[idx]
                            self.cache.delete(session.id)
                            self.logger.debug(f"キャッシュ削除: session_id={session.id}")
                        except Exception as e:
                            self.logger.warning(f"キャッシュ削除エラー (session_id={session.id}): {e}")

                self.logger.info(f"  {success_count}/{len(objects)} 件を追加しました")
                if batch_error_indices:
                    self.logger.warning(f"  {len(batch_error_indices)}件のオブジェクトでエラーが発生しました")
                    # エラーが発生したオブジェクトのみを個別に再試行
                    if batch_sessions:
                        error_objects = [batch[idx] for idx in batch_error_indices]
                        error_sessions = [batch_sessions[idx] for idx in batch_error_indices]
                        success, errors = self._save_individually(error_objects, i, error_sessions)
                        success_count += success
                        error_count += errors - len(batch_error_indices)  # 既にカウント済みなので調整
            except Exception as e:
                self.logger.error(
                    f"  バッチ追加エラー ({i+1}-{min(i+batch_size, len(objects))}件): {e}"
                )
                # create_objectsが例外を投げた場合、部分的に成功した可能性がある
                # キャッシュから削除されたセッションは既に作成されていると判断
                already_created_indices = []
                if batch_sessions:
                    for idx, session in enumerate(batch_sessions):
                        cached_session = self.cache.get(session.id)
                        if cached_session is None:
                            # キャッシュから削除されていれば既に作成済み
                            already_created_indices.append(idx)
                            success_count += 1
                            self.logger.debug(f"既に作成済みと判断: session_id={session.id}")

                # 未作成のオブジェクトのみを個別に再試行
                remaining_indices = [idx for idx in range(len(batch)) if idx not in already_created_indices]
                if remaining_indices:
                    remaining_objects = [batch[idx] for idx in remaining_indices]
                    remaining_sessions = [batch_sessions[idx] for idx in remaining_indices] if batch_sessions else None
                    success, errors = self._save_individually(remaining_objects, i, remaining_sessions)
                    success_count += success
                    error_count += errors

        return success_count, error_count

    def _save_individually(
        self,
        batch: List[AnytypeObject],
        start_index: int,
        sessions: Optional[List[ProjectSession]] = None,
    ) -> Tuple[int, int]:
        """バッチ内のオブジェクトを個別に保存

        Args:
            batch: 保存するオブジェクトのリスト
            start_index: 開始インデックス(ログ表示用)
            sessions: 対応するプロジェクトセッションのリスト(キャッシュ削除用、オプション)

        Returns:
            (成功数, エラー数) のタプル
        """
        success_count = 0
        error_count = 0

        for obj_idx, obj in enumerate(batch):
            try:
                self.object_manager.create_object(obj)
                success_count += 1
                self.logger.info(f"  個別追加成功: {start_index + obj_idx + 1} ({obj.name})")

                # 成功したセッションのキャッシュを削除
                if sessions and obj_idx < len(sessions):
                    try:
                        session = sessions[obj_idx]
                        self.cache.delete(session.id)
                        self.logger.debug(f"キャッシュ削除: session_id={session.id}")
                    except Exception as e:
                        self.logger.warning(f"キャッシュ削除エラー (session_id={session.id}): {e}")
            except Exception as e:
                error_count += 1
                self.logger.error(f"  個別追加エラー (オブジェクト {start_index + obj_idx + 1}, {obj.name}): {e}")

        return success_count, error_count

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
