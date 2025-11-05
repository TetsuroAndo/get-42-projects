"""Anytype APIクライアント

AnytypeのAPIと通信するためのクライアントクラスです。
"""
import os
from typing import Dict, Any, Optional
import requests


class AnytypeClient:
    """Anytype APIクライアントクラス"""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        """Anytypeクライアントの初期化

        Args:
            api_url: Anytype APIのURL（環境変数 ANYTYPE_API_URL からも取得可能）
            api_key: APIキー（環境変数 ANYTYPE_API_KEY からも取得可能）
        """
        self.api_url = api_url or os.getenv("ANYTYPE_API_URL", "http://localhost:3030")
        self.api_key = api_key or os.getenv("ANYTYPE_API_KEY")

        if not self.api_key:
            raise ValueError(
                "api_key が必要です。"
                "環境変数 ANYTYPE_API_KEY を設定してください。"
            )

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """APIリクエストを送信

        Args:
            method: HTTPメソッド（GET, POST, PUT, DELETEなど）
            endpoint: APIエンドポイント
            data: リクエストボディ
            params: クエリパラメータ

        Returns:
            APIレスポンスのJSONデータ
        """
        url = f"{self.api_url.rstrip('/')}/{endpoint.lstrip('/')}"

        response = self.session.request(
            method=method,
            url=url,
            json=data,
            params=params,
        )
        response.raise_for_status()

        return response.json()

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GETリクエストを送信"""
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POSTリクエストを送信"""
        return self._request("POST", endpoint, data=data)

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """PUTリクエストを送信"""
        return self._request("PUT", endpoint, data=data)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETEリクエストを送信"""
        return self._request("DELETE", endpoint)
