"""バッチ処理モジュール

Anytype同期処理におけるバッチ処理のヘルパークラスです。
"""
import logging
from typing import List, Optional, Tuple
from anytype import AnytypeObject, ObjectManager
from src.payloads import ProjectSession
from src.exceptions import SyncError
from .cache_manager import CacheManager


class BatchProcessor:
    """バッチ処理ヘルパークラス

    Anytypeへのオブジェクト保存をバッチ処理で行います。
    """

    def __init__(
        self,
        object_manager: ObjectManager,
        cache_manager: CacheManager,
        batch_size: int,
        logger: logging.Logger
    ):
        """バッチプロセッサーの初期化

        Args:
            object_manager: Anytypeオブジェクトマネージャー
            cache_manager: キャッシュマネージャー
            batch_size: バッチサイズ
            logger: ロガー
        """
        self.object_manager = object_manager
        self.cache_manager = cache_manager
        self.batch_size = batch_size
        self.logger = logger

    def create_objects(
        self,
        objects: List[AnytypeObject],
        sessions: List[ProjectSession],
    ) -> Tuple[int, int]:
        """Anytypeにオブジェクトを新規作成（Syncフェーズ: 新規）

        Args:
            objects: 作成するオブジェクトのリスト
            sessions: 対応するプロジェクトセッションのリスト

        Returns:
            (成功数, エラー数) のタプル
        """
        self._validate_object_session_alignment(objects, sessions)

        self.logger.info(f"新規作成: {len(objects)}件のオブジェクトをAnytypeに作成します")
        success_count = 0
        error_count = 0

        for i in range(0, len(objects), self.batch_size):
            batch = objects[i:i + self.batch_size]
            batch_sessions = sessions[i:i + self.batch_size]

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

                # 成功したオブジェクトのanytype_object_idをキャッシュに保存
                for idx in batch_success_indices:
                    session = batch_sessions[idx]
                    result = results[idx]
                    # APIレスポンスからobject_idを取得
                    anytype_object_id = result.get("id") or result.get("object_id")
                    if anytype_object_id:
                        # キャッシュにanytype_object_idを保存
                        self.cache_manager.save_session(session, anytype_object_id)
                        self.logger.debug(
                            f"anytype_object_idをキャッシュに保存: "
                            f"session_id={session.id}, object_id={anytype_object_id}"
                        )
                    else:
                        self.logger.warning(
                            f"APIレスポンスにobject_idが含まれていません: session_id={session.id}"
                        )

                success_count += len(batch_success_indices)
                error_count += len(batch_error_indices)

                # 成功したセッションはanytype_object_idを保存した時点でstatus='sent'になっているため、
                # キャッシュを削除する必要はない（次回のDiffフェーズで比較に使用するため保持）

                self.logger.info(f"  新規作成進捗: {success_count}/{len(objects)} 件")
                if batch_error_indices:
                    self.logger.warning(f"  {len(batch_error_indices)}件のオブジェクトでエラーが発生しました")
                    # エラーが発生したオブジェクトのみを個別に再試行
                    error_objects = [batch[idx] for idx in batch_error_indices]
                    error_sessions = [batch_sessions[idx] for idx in batch_error_indices]
                    success, errors = self._create_individually(error_objects, i, error_sessions)
                    success_count += success
                    error_count += errors - len(batch_error_indices)  # 既にカウント済みなので調整
            except Exception as e:
                self.logger.error(
                    f"  バッチ作成エラー ({i+1}-{min(i+self.batch_size, len(objects))}件): {e}"
                )
                # 個別に再試行
                success, errors = self._create_individually(batch, i, batch_sessions)
                success_count += success
                error_count += errors

        return success_count, error_count

    def update_objects(
        self,
        objects: List[AnytypeObject],
        update_list: List[Tuple[ProjectSession, str]],
    ) -> Tuple[int, int]:
        """Anytypeのオブジェクトを更新（Syncフェーズ: 更新）

        Args:
            objects: 更新するオブジェクトのリスト
            update_list: (セッション, anytype_object_id)のタプルのリスト

        Returns:
            (成功数, エラー数) のタプル
        """
        if len(objects) != len(update_list):
            raise SyncError(
                f"objectsとupdate_listの長さが一致しません: "
                f"objects={len(objects)}, update_list={len(update_list)}"
            )

        self.logger.info(f"更新: {len(objects)}件のオブジェクトをAnytypeに更新します")
        success_count = 0
        error_count = 0

        for obj_idx, (obj, (session, anytype_object_id)) in enumerate(zip(objects, update_list)):
            try:
                result = self.object_manager.update_object(anytype_object_id, obj)
                # エラーチェック
                if "error" in result:
                    error_count += 1
                    self.logger.error(
                        f"  更新エラー (オブジェクト {obj_idx + 1}, {obj.name}): {result.get('error')}"
                    )
                else:
                    success_count += 1
                    # 成功したセッションのデータをキャッシュに保存（anytype_object_idを保持し、status='sent'に設定）
                    self.cache_manager.save_session(session, anytype_object_id)
                    self.logger.debug(f"  更新成功: {obj_idx + 1} ({obj.name})")

                # 進捗表示
                if (obj_idx + 1) % self.batch_size == 0 or obj_idx == len(objects) - 1:
                    self.logger.info(f"  更新進捗: {obj_idx + 1}/{len(objects)} 件")
            except Exception as e:
                error_count += 1
                self.logger.error(f"  更新エラー (オブジェクト {obj_idx + 1}, {obj.name}): {e}")

        return success_count, error_count

    def save_objects(
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
            self._validate_object_session_alignment(objects, sessions)

        self.logger.info("Anytypeにオブジェクトを追加中...")
        success_count = 0
        error_count = 0

        for i in range(0, len(objects), self.batch_size):
            batch = objects[i:i + self.batch_size]
            batch_sessions = sessions[i:i + self.batch_size] if sessions else None

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
                    success_sessions = [batch_sessions[idx] for idx in batch_success_indices]
                    self.cache_manager.delete_sessions(success_sessions)

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
                    f"  バッチ追加エラー ({i+1}-{min(i+self.batch_size, len(objects))}件): {e}"
                )
                # create_objectsが例外を投げた場合、部分的に成功している可能性がある
                # キャッシュをチェックして、既に作成済みの可能性があるオブジェクトを特定する
                # ただし、キャッシュの欠落は成功の証拠ではないため、成功としてカウントしない
                # キャッシュに存在しないオブジェクトは再試行をスキップするが、
                # 重複エラーが発生する可能性があるため、すべてを再試行する方が安全
                if batch_sessions:
                    # キャッシュの状態を確認して、既に作成済みの可能性があるオブジェクトを記録
                    potentially_created = []
                    for obj_idx, (obj, session) in enumerate(zip(batch, batch_sessions)):
                        cached_session = self.cache_manager.get_session(session.id)
                        if cached_session is None:
                            potentially_created.append((obj_idx, obj.name))

                    if potentially_created:
                        self.logger.warning(
                            f"  バッチ内の {len(potentially_created)}件のオブジェクトは"
                            f" キャッシュに存在しません（既に作成済みの可能性があります）"
                        )
                        # キャッシュに存在しないオブジェクトをスキップして再試行を避ける
                        # これにより重複作成を防ぐ
                        retry_objects = []
                        retry_sessions = []
                        skipped_count = 0

                        for obj_idx, (obj, session) in enumerate(zip(batch, batch_sessions)):
                            cached_session = self.cache_manager.get_session(session.id)
                            if cached_session is None:
                                # キャッシュに存在しない場合はスキップ
                                # 成功としてカウントしない（キャッシュの欠落は成功の証拠ではない）
                                skipped_count += 1
                                self.logger.debug(
                                    f"  オブジェクト {i + obj_idx + 1} ({obj.name}) をスキップ"
                                    f" (キャッシュに存在しない)"
                                )
                            else:
                                retry_objects.append(obj)
                                retry_sessions.append(session)

                        if skipped_count > 0:
                            self.logger.info(
                                f"  {skipped_count}件のオブジェクトをスキップしました"
                                f"（キャッシュに存在しないため、既に作成済みの可能性があります）"
                            )

                        # キャッシュに残っているオブジェクトのみを再試行
                        if retry_objects:
                            success, errors = self._save_individually(
                                retry_objects, i, retry_sessions
                            )
                            success_count += success
                            error_count += errors
                        else:
                            self.logger.info("  再試行が必要なオブジェクトはありません")
                    else:
                        # すべてのオブジェクトがキャッシュに存在する場合は、すべてを再試行
                        success, errors = self._save_individually(batch, i, batch_sessions)
                        success_count += success
                        error_count += errors
                else:
                    # sessionsが提供されていない場合は、全てを再試行
                    success, errors = self._save_individually(batch, i, batch_sessions)
                    success_count += success
                    error_count += errors

        return success_count, error_count

    def _validate_object_session_alignment(
        self,
        objects: List[AnytypeObject],
        sessions: List[ProjectSession]
    ) -> None:
        """objectsとsessionsの順序が一致していることを確認

        Args:
            objects: オブジェクトのリスト
            sessions: セッションのリスト

        Raises:
            SyncError: 順序が一致していない場合
        """
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

    def _create_individually(
        self,
        batch: List[AnytypeObject],
        start_index: int,
        sessions: List[ProjectSession],
    ) -> Tuple[int, int]:
        """バッチ内のオブジェクトを個別に作成

        Args:
            batch: 作成するオブジェクトのリスト
            start_index: 開始インデックス(ログ表示用)
            sessions: 対応するプロジェクトセッションのリスト

        Returns:
            (成功数, エラー数) のタプル
        """
        success_count = 0
        error_count = 0

        for obj_idx, obj in enumerate(batch):
            try:
                result = self.object_manager.create_object(obj)
                # APIレスポンスからobject_idを取得
                anytype_object_id = result.get("id") or result.get("object_id")
                if anytype_object_id:
                    # キャッシュにanytype_object_idを保存
                    session = sessions[obj_idx]
                    self.cache_manager.save_session(session, anytype_object_id)
                    self.logger.debug(
                        f"anytype_object_idをキャッシュに保存: "
                        f"session_id={session.id}, object_id={anytype_object_id}"
                    )
                success_count += 1
                self.logger.info(f"  個別作成成功: {start_index + obj_idx + 1} ({obj.name})")

                # 成功したセッションはanytype_object_idを保存した時点でstatus='sent'になっているため、
                # キャッシュを削除する必要はない（次回のDiffフェーズで比較に使用するため保持）
            except Exception as e:
                error_count += 1
                # エラーの詳細をログに出力
                error_msg = f"  個別作成エラー (オブジェクト {start_index + obj_idx + 1}, {obj.name}): {e}"
                # HTTPエラーの場合はレスポンスの詳細も含める
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_body = e.response.json()
                        error_msg += f"\n    エラー詳細: {error_body}"
                    except Exception:
                        error_msg += f"\n    エラーレスポンス: {e.response.text[:500]}"
                self.logger.error(error_msg, exc_info=True)

        return success_count, error_count

    def _save_individually(
        self,
        batch: List[AnytypeObject],
        start_index: int,
        sessions: Optional[List[ProjectSession]] = None,
    ) -> Tuple[int, int]:
        """バッチ内のオブジェクトを個別に保存（後方互換性のため残す）

        Args:
            batch: 保存するオブジェクトのリスト
            start_index: 開始インデックス(ログ表示用)
            sessions: 対応するプロジェクトセッションのリスト(キャッシュ削除用、オプション)

        Returns:
            (成功数, エラー数) のタプル
        """
        if sessions:
            return self._create_individually(batch, start_index, sessions)
        else:
            # sessionsがない場合は従来の動作
            success_count = 0
            error_count = 0
            for obj_idx, obj in enumerate(batch):
                try:
                    self.object_manager.create_object(obj)
                    success_count += 1
                    self.logger.info(f"  個別追加成功: {start_index + obj_idx + 1} ({obj.name})")
                except Exception as e:
                    error_count += 1
                    self.logger.error(f"  個別追加エラー (オブジェクト {start_index + obj_idx + 1}, {obj.name}): {e}")
            return success_count, error_count
