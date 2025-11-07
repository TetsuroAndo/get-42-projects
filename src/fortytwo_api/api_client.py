"""42 API共通処理モジュール

42のAPIリクエストにおける共通のエラーハンドリング処理を提供します。
"""
import json
import requests
from typing import Optional
from src.exceptions import (
    ValidationError,
    NotFoundError,
    APIError,
    ConnectionError,
    NetworkError,
    ParseError,
)
from auth42.exceptions import AuthenticationError as Auth42AuthenticationError, AuthorizationError as Auth42AuthorizationError


class APIResponseHandler:
    """APIレスポンスのエラーハンドリング共通処理クラス"""

    @staticmethod
    def handle_response(
        response: requests.Response,
        error_message_prefix: str = "APIリクエスト",
        resource_id: Optional[str] = None
    ) -> None:
        """APIレスポンスのエラーハンドリング共通処理

        Args:
            response: HTTPレスポンス
            error_message_prefix: エラーメッセージのプレフィックス
            resource_id: リソースID（404エラー時に使用）

        Raises:
            ValidationError: 400エラーの場合
            AuthenticationError: 401エラーの場合
            AuthorizationError: 403エラーの場合
            NotFoundError: 404エラーの場合
            APIError: その他のエラーの場合
        """
        if response.status_code == 400:
            raise ValidationError(
                f"{error_message_prefix}の形式が不正です。パラメータを確認してください",
                response_text=response.text
            )
        elif response.status_code == 401:
            raise Auth42AuthenticationError(
                f"認証に失敗しました。トークンが無効です。再認証を試みてください。レスポンス: {response.text}",
                status_code=401
            )
        elif response.status_code == 403:
            raise Auth42AuthorizationError(
                f"アクセスが拒否されました。必要なロールやスコープが不足している可能性があります。レスポンス: {response.text}",
                status_code=403
            )
        elif response.status_code == 404:
            raise NotFoundError(
                "リソースが見つかりませんでした",
                resource_id=resource_id,
                response_text=response.text
            )
        elif not response.ok:
            raise APIError(
                f"{error_message_prefix}に失敗しました (HTTP {response.status_code})",
                status_code=response.status_code,
                response_text=response.text
            )

    @staticmethod
    def handle_request_exceptions(e: Exception) -> None:
        """リクエスト例外のハンドリング共通処理

        Args:
            e: 例外オブジェクト

        Raises:
            ConnectionError: 接続エラーの場合
            NetworkError: ネットワークエラーの場合
            ParseError: パースエラーの場合
        """
        if isinstance(e, requests.exceptions.ConnectionError):
            raise ConnectionError(
                "APIへの接続に失敗しました。HTTPSを使用しているか確認してください",
                original_error=e
            ) from e
        elif isinstance(e, requests.exceptions.RequestException):
            raise NetworkError(
                "リクエスト中にエラーが発生しました",
                original_error=e
            ) from e
        elif isinstance(e, (json.JSONDecodeError, KeyError, TypeError)):
            raise ParseError(
                "レスポンスの解析に失敗しました",
                original_error=e
            ) from e
        else:
            raise
