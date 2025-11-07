"""42プロジェクト取得モジュールの例外クラス

再利用可能で階層的なエラークラスを定義します。
"""
from typing import Optional


class Project42Error(Exception):
    """42プロジェクト取得関連の基底エラー

    すべてのプロジェクト取得関連のエラーの基底クラスです。
    """

    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        """エラーの初期化

        Args:
            message: エラーメッセージ
            status_code: HTTPステータスコード（オプション）
            response_text: レスポンステキスト（オプション）
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_text = response_text

    def __str__(self) -> str:
        """エラーメッセージの文字列表現"""
        msg = self.message
        if self.status_code:
            msg = f"[HTTP {self.status_code}] {msg}"
        return msg


class APIError(Project42Error):
    """API関連の一般的なエラー"""
    pass


class NotFoundError(Project42Error):
    """リソースが見つからないエラー（404 Not Found）"""

    def __init__(self, message: str = "リソースが見つかりませんでした", resource_id: Optional[str] = None, response_text: Optional[str] = None):
        if resource_id:
            message = f"{message}: {resource_id}"
        super().__init__(message, status_code=404, response_text=response_text)
        self.resource_id = resource_id


class RateLimitError(Project42Error):
    """レート制限エラー（429 Too Many Requests）

    APIのレート制限に達した場合に発生します。
    """

    def __init__(self, message: str = "レート制限に達しました", retry_after: Optional[int] = None, response_text: Optional[str] = None):
        if retry_after:
            message = f"{message} (Retry-After: {retry_after}秒)"
        super().__init__(message, status_code=429, response_text=response_text)
        self.retry_after = retry_after


class NetworkError(Project42Error):
    """ネットワーク関連のエラー

    接続エラー、タイムアウト、DNS解決失敗などが含まれます。
    """

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error

    def __str__(self) -> str:
        msg = self.message
        if self.original_error:
            msg = f"{msg}: {self.original_error}"
        return msg


class ConnectionError(NetworkError):
    """接続エラー

    APIサーバーへの接続に失敗した場合に発生します。
    """

    def __init__(self, message: str = "APIへの接続に失敗しました", original_error: Optional[Exception] = None):
        super().__init__(message, original_error)


class TimeoutError(NetworkError):
    """タイムアウトエラー

    リクエストがタイムアウトした場合に発生します。
    """

    def __init__(self, message: str = "リクエストがタイムアウトしました", timeout: Optional[float] = None, original_error: Optional[Exception] = None):
        if timeout:
            message = f"{message} (タイムアウト: {timeout}秒)"
        super().__init__(message, original_error)
        self.timeout = timeout


class ValidationError(Project42Error):
    """バリデーションエラー

    リクエストパラメータが不正な場合に発生します（400 Bad Request）。
    """

    def __init__(self, message: str = "リクエストの形式が不正です", field: Optional[str] = None, response_text: Optional[str] = None):
        if field:
            message = f"{message}: {field}"
        super().__init__(message, status_code=400, response_text=response_text)
        self.field = field


class ParseError(Project42Error):
    """レスポンス解析エラー

    APIレスポンスのJSON解析やデータ構造の解析に失敗した場合に発生します。
    """

    def __init__(self, message: str = "レスポンスの解析に失敗しました", original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error

    def __str__(self) -> str:
        msg = self.message
        if self.original_error:
            msg = f"{msg}: {self.original_error}"
        return msg


class ConfigurationError(Project42Error):
    """設定エラー

    設定が不正または不足している場合に発生します。
    """

    def __init__(self, message: str, missing_fields: Optional[list] = None):
        if missing_fields:
            fields_str = ", ".join(missing_fields)
            message = f"{message} (不足しているフィールド: {fields_str})"
        super().__init__(message)
        self.missing_fields = missing_fields


class SyncError(Project42Error):
    """同期処理エラー

    プロジェクトセッションの同期処理中に発生するエラーです。
    """

    def __init__(self, message: str, session_id: Optional[int] = None, original_error: Optional[Exception] = None):
        if session_id:
            message = f"{message} (セッションID: {session_id})"
        super().__init__(message)
        self.session_id = session_id
        self.original_error = original_error

    def __str__(self) -> str:
        msg = self.message
        if self.original_error:
            msg = f"{msg}: {self.original_error}"
        return msg


class RetryExhaustedError(Project42Error):
    """リトライ回数超過エラー

    最大リトライ回数に達してもリクエストが成功しなかった場合に発生します。
    """

    def __init__(self, message: str = "最大リトライ回数に達しました", retry_count: Optional[int] = None, last_error: Optional[Exception] = None):
        if retry_count:
            message = f"{message} (試行回数: {retry_count})"
        super().__init__(message)
        self.retry_count = retry_count
        self.last_error = last_error

    def __str__(self) -> str:
        msg = self.message
        if self.last_error:
            msg = f"{msg} (最後のエラー: {self.last_error})"
        return msg
