"""SQLiteキャッシュ実装

SQLiteを使用したキャッシュの実装です。
"""
import json
import sqlite3
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone

from src.cache.base import CacheBase
from src.payloads import ProjectSession


class SQLiteCache(CacheBase):
    """SQLiteを使用したキャッシュ実装"""

    def __init__(self, db_path: Path, logger: Optional[logging.Logger] = None):
        """SQLiteキャッシュの初期化

        Args:
            db_path: SQLiteデータベースファイルのパス
            logger: ロガー(オプション)
        """
        self.db_path = db_path
        self.logger = logger or logging.getLogger(__name__)
        self._init_database()

    def _init_database(self) -> None:
        """データベースを初期化"""
        # 親ディレクトリが存在しない場合は作成
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    session_id INTEGER PRIMARY KEY,
                    data TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    anytype_object_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # インデックスを作成(パフォーマンス向上)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON cache(status)
            """)
            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """データベース接続を取得"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, session: ProjectSession, anytype_object_id: Optional[str] = None) -> None:
        """プロジェクトセッションをキャッシュに保存

        Args:
            session: 保存するプロジェクトセッション
            anytype_object_id: AnytypeオブジェクトID（オプション）
        """
        try:
            data_json = json.dumps(session.to_dict(), ensure_ascii=False)
            now = datetime.now(timezone.utc).isoformat()

            with self._get_connection() as conn:
                # 既存のレコードがあるかチェック
                cursor = conn.execute(
                    "SELECT session_id, anytype_object_id FROM cache WHERE session_id = ?",
                    (session.id,)
                )
                existing = cursor.fetchone()

                if existing:
                    # 更新（anytype_object_idが提供されている場合は更新、既存の値がある場合は保持）
                    update_object_id = anytype_object_id if anytype_object_id else existing["anytype_object_id"]
                    # anytype_object_idが提供されている場合はstatusを'sent'に設定
                    status = 'sent' if anytype_object_id else 'pending'
                    conn.execute("""
                        UPDATE cache
                        SET data = ?, updated_at = ?, status = ?, anytype_object_id = ?
                        WHERE session_id = ?
                    """, (data_json, now, status, update_object_id, session.id))
                else:
                    # 新規挿入（anytype_object_idが提供されている場合はstatusを'sent'に設定）
                    status = 'sent' if anytype_object_id else 'pending'
                    conn.execute("""
                        INSERT INTO cache (session_id, data, status, anytype_object_id, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (session.id, data_json, status, anytype_object_id, now, now))
                conn.commit()

            self.logger.debug(f"キャッシュに保存: session_id={session.id}, anytype_object_id={anytype_object_id}")
        except Exception as e:
            self.logger.error(f"キャッシュ保存エラー (session_id={session.id}): {e}", exc_info=True)
            raise

    def get(self, session_id: int) -> Optional[ProjectSession]:
        """キャッシュからプロジェクトセッションを取得

        Args:
            session_id: プロジェクトセッションID

        Returns:
            プロジェクトセッション(存在しない場合はNone)
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT data FROM cache WHERE session_id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()
                if row is None:
                    return None

                data_dict = json.loads(row["data"])
                return ProjectSession(**data_dict)
        except Exception as e:
            self.logger.error(f"キャッシュ取得エラー (session_id={session_id}): {e}", exc_info=True)
            return None

    def get_pending(self) -> List[ProjectSession]:
        """未送信のプロジェクトセッションを取得

        Returns:
            未送信のプロジェクトセッションのリスト
        """
        sessions = []
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT data FROM cache WHERE status = 'pending' ORDER BY created_at ASC"
                )
                for row in cursor:
                    try:
                        data_dict = json.loads(row["data"])
                        sessions.append(ProjectSession(**data_dict))
                    except Exception as e:
                        self.logger.warning(f"キャッシュデータの復元エラー: {e}")
                        continue

            self.logger.info(f"未送信のキャッシュ: {len(sessions)}件")
        except Exception as e:
            self.logger.error(f"未送信キャッシュ取得エラー: {e}", exc_info=True)

        return sessions

    def mark_as_sent(self, session_id: int) -> None:
        """プロジェクトセッションを送信済みとしてマーク

        Args:
            session_id: プロジェクトセッションID
        """
        try:
            now = datetime.now(timezone.utc).isoformat()
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE cache
                    SET status = 'sent', updated_at = ?
                    WHERE session_id = ?
                """, (now, session_id))
                conn.commit()

            self.logger.debug(f"送信済みマーク: session_id={session_id}")
        except Exception as e:
            self.logger.error(f"送信済みマークエラー (session_id={session_id}): {e}", exc_info=True)
            raise

    def delete(self, session_id: int) -> None:
        """キャッシュからプロジェクトセッションを削除

        Args:
            session_id: プロジェクトセッションID
        """
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM cache WHERE session_id = ?", (session_id,))
                conn.commit()

            self.logger.debug(f"キャッシュ削除: session_id={session_id}")
        except Exception as e:
            self.logger.error(f"キャッシュ削除エラー (session_id={session_id}): {e}", exc_info=True)
            raise

    def clear(self) -> None:
        """キャッシュをクリア"""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM cache")
                conn.commit()

            self.logger.info("キャッシュをクリアしました")
        except Exception as e:
            self.logger.error(f"キャッシュクリアエラー: {e}", exc_info=True)
            raise

    def count_pending(self) -> int:
        """未送信のプロジェクトセッション数を取得

        Returns:
            未送信のプロジェクトセッション数
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) as count FROM cache WHERE status = 'pending'")
                row = cursor.fetchone()
                return row["count"] if row else 0
        except Exception as e:
            self.logger.error(f"未送信数取得エラー: {e}", exc_info=True)
            return 0

    def get_anytype_object_id(self, session_id: int) -> Optional[str]:
        """キャッシュからAnytypeオブジェクトIDを取得

        Args:
            session_id: プロジェクトセッションID

        Returns:
            AnytypeオブジェクトID（存在しない場合はNone）
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT anytype_object_id FROM cache WHERE session_id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()
                if row and row["anytype_object_id"]:
                    return row["anytype_object_id"]
                return None
        except Exception as e:
            self.logger.error(f"AnytypeオブジェクトID取得エラー (session_id={session_id}): {e}", exc_info=True)
            return None
