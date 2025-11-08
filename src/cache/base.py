"""キャッシュ基底クラス

キャッシュ実装の抽象基底クラスです。
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.payloads import ProjectSession


class CacheBase(ABC):
    """キャッシュの抽象基底クラス"""

    @abstractmethod
    def save(self, session: ProjectSession, anytype_object_id: Optional[str] = None) -> None:
        """プロジェクトセッションをキャッシュに保存

        Args:
            session: 保存するプロジェクトセッション
            anytype_object_id: AnytypeオブジェクトID（オプション）
        """
        pass

    @abstractmethod
    def get_anytype_object_id(self, session_id: int) -> Optional[str]:
        """キャッシュからAnytypeオブジェクトIDを取得

        Args:
            session_id: プロジェクトセッションID

        Returns:
            AnytypeオブジェクトID（存在しない場合はNone）
        """
        pass

    @abstractmethod
    def get(self, session_id: int) -> Optional[ProjectSession]:
        """キャッシュからプロジェクトセッションを取得

        Args:
            session_id: プロジェクトセッションID

        Returns:
            プロジェクトセッション(存在しない場合はNone)
        """
        pass

    @abstractmethod
    def get_pending(self) -> List[ProjectSession]:
        """未送信のプロジェクトセッションを取得

        Returns:
            未送信のプロジェクトセッションのリスト
        """
        pass

    @abstractmethod
    def mark_as_sent(self, session_id: int) -> None:
        """プロジェクトセッションを送信済みとしてマーク

        Args:
            session_id: プロジェクトセッションID
        """
        pass

    @abstractmethod
    def delete(self, session_id: int) -> None:
        """キャッシュからプロジェクトセッションを削除

        Args:
            session_id: プロジェクトセッションID
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """キャッシュをクリア"""
        pass

    @abstractmethod
    def count_pending(self) -> int:
        """未送信のプロジェクトセッション数を取得

        Returns:
            未送信のプロジェクトセッション数
        """
        pass
