"""Anytypeテーブル操作モジュール

Anytypeのテーブル（データベース）を操作するためのモジュールです。
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .client import AnytypeClient


@dataclass
class TableRow:
    """テーブル行のデータクラス"""
    fields: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """APIリクエスト用の辞書形式に変換"""
        return self.fields


class TableManager:
    """Anytypeテーブル管理クラス"""

    def __init__(self, client: AnytypeClient, table_id: str):
        """テーブルマネージャーの初期化

        Args:
            client: Anytypeクライアント
            table_id: テーブルID
        """
        self.client = client
        self.table_id = table_id

    def create_row(self, row: TableRow) -> Dict[str, Any]:
        """テーブルに行を追加

        Args:
            row: 追加する行データ

        Returns:
            APIレスポンス
        """
        endpoint = f"tables/{self.table_id}/rows"
        return self.client.post(endpoint, data=row.to_dict())

    def create_rows(self, rows: List[TableRow]) -> Dict[str, Any]:
        """テーブルに複数行を追加

        Args:
            rows: 追加する行データのリスト

        Returns:
            APIレスポンス
        """
        endpoint = f"tables/{self.table_id}/rows/batch"
        data = {
            "rows": [row.to_dict() for row in rows]
        }
        return self.client.post(endpoint, data=data)

    def get_rows(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """テーブルの行を取得

        Args:
            limit: 取得件数の上限
            offset: オフセット
            filters: フィルター条件

        Returns:
            APIレスポンス（行データを含む）
        """
        params = {}
        if limit:
            params["limit"] = limit
        if offset:
            params["offset"] = offset
        if filters:
            params["filters"] = filters

        endpoint = f"tables/{self.table_id}/rows"
        return self.client.get(endpoint, params=params)

    def update_row(self, row_id: str, row: TableRow) -> Dict[str, Any]:
        """テーブルの行を更新

        Args:
            row_id: 行ID
            row: 更新する行データ

        Returns:
            APIレスポンス
        """
        endpoint = f"tables/{self.table_id}/rows/{row_id}"
        return self.client.put(endpoint, data=row.to_dict())

    def delete_row(self, row_id: str) -> Dict[str, Any]:
        """テーブルの行を削除

        Args:
            row_id: 行ID

        Returns:
            APIレスポンス
        """
        endpoint = f"tables/{self.table_id}/rows/{row_id}"
        return self.client.delete(endpoint)

    def upsert_row(
        self,
        row: TableRow,
        unique_fields: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """行を追加または更新（存在する場合は更新、存在しない場合は追加）

        Args:
            row: 行データ
            unique_fields: 一意性を判定するフィールド名のリスト

        Returns:
            APIレスポンス
        """
        if unique_fields:
            # 既存の行を検索
            filters = {field: row.fields.get(field) for field in unique_fields}
            existing_rows = self.get_rows(filters=filters)

            if existing_rows.get("rows"):
                # 既存の行があれば更新
                row_id = existing_rows["rows"][0]["id"]
                return self.update_row(row_id, row)

        # 既存の行がなければ追加
        return self.create_row(row)
