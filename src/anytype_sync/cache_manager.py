"""キャッシュ管理モジュール

Anytype同期処理におけるキャッシュ管理のヘルパークラスです。
"""
import logging
from typing import List, Optional
from src.payloads import ProjectSession
from src.cache import CacheBase


class CacheManager:
    """キャッシュ管理ヘルパークラス

    セッションのキャッシュ保存・削除処理を共通化します。
    """

    def __init__(self, cache: CacheBase, logger: logging.Logger):
        """キャッシュマネージャーの初期化

        Args:
            cache: キャッシュオブジェクト
            logger: ロガー
        """
        self.cache = cache
        self.logger = logger

    def save_session(self, session: ProjectSession, anytype_object_id: Optional[str] = None) -> None:
        """セッションをキャッシュに保存

        Args:
            session: 保存するプロジェクトセッション
            anytype_object_id: AnytypeオブジェクトID（オプション）
        """
        try:
            self.cache.save(session, anytype_object_id)
        except Exception as e:
            self.logger.warning(f"キャッシュ保存エラー (session_id={session.id}): {e}")

    def delete_sessions(self, sessions: List[ProjectSession]) -> None:
        """成功したセッションのキャッシュを削除

        Args:
            sessions: キャッシュを削除するセッションのリスト
        """
        for session in sessions:
            try:
                self.cache.delete(session.id)
                self.logger.debug(f"キャッシュ削除: session_id={session.id}")
            except Exception as e:
                self.logger.warning(f"キャッシュ削除エラー (session_id={session.id}): {e}")

    def get_session(self, session_id: int):
        """キャッシュからセッションを取得

        Args:
            session_id: セッションID

        Returns:
            セッション（存在しない場合はNone）
        """
        return self.cache.get(session_id)

    def get_anytype_object_id(self, session_id: int) -> Optional[str]:
        """キャッシュからAnytypeオブジェクトIDを取得

        Args:
            session_id: セッションID

        Returns:
            AnytypeオブジェクトID（存在しない場合はNone）
        """
        return self.cache.get_anytype_object_id(session_id)
