"""同期処理モジュール

42のプロジェクトセッション情報を取得し、Anytypeに同期する処理を担当します。
"""
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from auth42 import Auth42
from src.config import Config
from src.projects import Project42, ProjectSession, Project42Error
from src.converters import project_session_to_table_row
from anytype import AnytypeClient, TableManager, TableRow


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
        self.project42 = Project42(auth=auth)

        # Anytypeクライアントを初期化
        self.anytype_client = AnytypeClient(
            api_url=config.anytype_api_url,
            api_key=config.anytype_api_key,
        )

        # テーブルマネージャーを初期化
        self.table_manager = TableManager(
            client=self.anytype_client,
            table_id=config.anytype_table_id,
        )

    def fetch_sessions(
        self,
        campus_id: Optional[int] = None,
        is_subscriptable: bool = True,
    ) -> List[ProjectSession]:
        """プロジェクトセッションを取得

        Args:
            campus_id: キャンパスID（Noneの場合は設定値を使用）
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

                # 進捗表示
                if idx % self.config.detail_fetch_interval == 0:
                    self.logger.info(f"  詳細情報取得進捗: {idx}/{len(sessions)}")
            except Exception as e:
                self.logger.warning(
                    f"セッションID {session.id} ({session.project_name}) の詳細情報取得に失敗: {e}"
                )
                # 詳細情報が取得できなくても基本情報は残す
                sessions_with_details.append(session)

        self.logger.info(
            f"{len(sessions_with_details)}件のプロジェクトセッションの詳細情報を取得しました"
        )
        return sessions_with_details

    def convert_to_rows(self, sessions: List[ProjectSession]) -> List[TableRow]:
        """プロジェクトセッションをテーブル行に変換

        Args:
            sessions: プロジェクトセッションのリスト

        Returns:
            テーブル行のリスト
        """
        self.logger.info("プロジェクトセッションをテーブル形式に変換中...")
        rows = [project_session_to_table_row(session) for session in sessions]
        self.logger.info(f"{len(rows)}件のテーブル行を生成しました")
        return rows

    def save_to_anytype(self, rows: List[TableRow]) -> Tuple[int, int]:
        """Anytypeテーブルに保存

        Args:
            rows: テーブル行のリスト

        Returns:
            (成功数, エラー数) のタプル
        """
        self.logger.info("Anytypeテーブルに追加中...")
        batch_size = self.config.batch_size
        success_count = 0
        error_count = 0

        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            try:
                self.table_manager.create_rows(batch)
                success_count += len(batch)
                self.logger.info(f"  {success_count}/{len(rows)} 件を追加しました")
            except Exception as e:
                error_count += len(batch)
                self.logger.error(
                    f"  バッチ追加エラー ({i+1}-{min(i+batch_size, len(rows))}件): {e}"
                )
                # 個別に追加を試みる
                success, errors = self._save_individually(batch, i)
                success_count += success
                error_count += errors

        return success_count, error_count

    def _save_individually(
        self,
        batch: List[TableRow],
        start_index: int,
    ) -> Tuple[int, int]:
        """バッチ内の行を個別に保存

        Args:
            batch: 保存する行のリスト
            start_index: 開始インデックス（ログ表示用）

        Returns:
            (成功数, エラー数) のタプル
        """
        success_count = 0
        error_count = 0

        for row_idx, row in enumerate(batch):
            try:
                self.table_manager.create_row(row)
                success_count += 1
                self.logger.info(f"  個別追加成功: {start_index + row_idx + 1}")
            except Exception as e:
                error_count += 1
                self.logger.error(f"  個別追加エラー (行 {start_index + row_idx + 1}): {e}")

        return success_count, error_count

    def sync(
        self,
        campus_id: Optional[int] = None,
        is_subscriptable: bool = True,
    ) -> SyncResult:
        """プロジェクトセッションを同期

        Args:
            campus_id: キャンパスID（Noneの場合は設定値を使用）
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

            # テーブル行に変換
            rows = self.convert_to_rows(sessions_with_details)

            # Anytypeに保存
            success_count, error_count = self.save_to_anytype(rows)
            result.success_count = success_count
            result.error_count = error_count

        except Project42Error as e:
            self.logger.error(f"プロジェクト取得エラー: {e}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"同期処理中にエラーが発生しました: {e}", exc_info=True)
            raise

        return result
