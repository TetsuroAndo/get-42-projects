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
                # create_objectsが例外を投げた場合、実際の作成結果が不明なため
                # キャッシュの状態に依存せず、すべてのオブジェクトを個別に再試行する
                # キャッシュの欠落は、キャッシュの失敗、破損、またはセッションが
                # 最初からキャッシュされていないことを示している可能性があるため、
                # 成功の証拠として使用できない
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
                    self.cache_manager.delete_sessions([sessions[obj_idx]])
            except Exception as e:
                error_count += 1
                self.logger.error(f"  個別追加エラー (オブジェクト {start_index + obj_idx + 1}, {obj.name}): {e}")

        return success_count, error_count
