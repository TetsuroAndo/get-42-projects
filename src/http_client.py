"""HTTPクライアントモジュール

APIリクエストを送信するためのHTTPクライアントクラスです。
リトライ機能とレート制限管理を含みます。
"""
import time
import logging
from typing import Optional, Dict, Any
import requests

from src.rate_limiter import RateLimiter
from src.exceptions import (
    APIError,
    RateLimitError,
    NetworkError,
    ConnectionError,
    TimeoutError,
    ValidationError,
    RetryExhaustedError,
)


class HTTPClient:
    """HTTPクライアントクラス

    リトライ機能とレート制限管理を備えたHTTPリクエスト送信クラスです。
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 60.0,
        logger: Optional[logging.Logger] = None
    ):
        """HTTPクライアントの初期化

        Args:
            rate_limiter: レート制限管理オブジェクト(オプション)
            max_retries: 最大リトライ回数
            base_delay: 基本待機時間(秒)
            max_delay: 最大待機時間(秒)
            logger: ロガー(オプション)
        """
        self.rate_limiter = rate_limiter
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.logger = logger or logging.getLogger(__name__)

    def request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> requests.Response:
        """リトライ機能付きリクエスト送信

        Args:
            method: HTTPメソッド('GET', 'POST'など)
            url: リクエストURL
            params: クエリパラメータ
            headers: リクエストヘッダー
            **kwargs: requests.get/postなどの追加引数

        Returns:
            HTTPレスポンス

        Raises:
            Project42Error: リトライ回数を超えた場合、または回復不可能なエラーの場合
        """
        retry_count = 0
        last_exception = None

        while retry_count <= self.max_retries:
            try:
                # リクエスト情報をログに出力(初回のみ)
                if retry_count == 0:
                    self.logger.info(f"リクエスト送信: {method} {url}")
                    if params:
                        self.logger.info(f"  パラメータ: {params}")

                # リトライ時はログに出力
                if retry_count > 0:
                    self.logger.info(f"リトライ {retry_count}/{self.max_retries}: {method} {url}")

                # リクエスト送信前にレート制限の事前制御(1秒間に2回の制限)
                if self.rate_limiter:
                    self.rate_limiter.wait_if_needed()

                # リクエスト送信
                response = self._send_request(method, url, params=params, headers=headers, **kwargs)

                # レート制限ヘッダーをチェック
                if self.rate_limiter:
                    self.rate_limiter.check_and_wait(response)

                # 429エラー(Too Many Requests)の処理
                if response.status_code == 429:
                    retry_after = self.rate_limiter.get_retry_after(response) if self.rate_limiter else None
                    if retry_after:
                        self.logger.warning(
                            f"レート制限エラー(429): Retry-After={retry_after}秒。"
                            f"待機してからリトライします... (試行 {retry_count + 1}/{self.max_retries + 1})"
                        )
                        time.sleep(retry_after)
                        retry_count += 1
                        continue

                    # Retry-Afterがない場合は指数バックオフを使用
                    if retry_count < self.max_retries:
                        delay = min(self.base_delay * (2 ** retry_count), self.max_delay)
                        self.logger.warning(
                            f"レート制限エラー(429): {delay:.2f}秒待機してからリトライします... "
                            f"(試行 {retry_count + 1}/{self.max_retries + 1})"
                        )
                        time.sleep(delay)
                        retry_count += 1
                        continue
                    else:
                        raise RateLimitError(
                            f"レート制限エラー: 最大リトライ回数({self.max_retries}回)に達しました",
                            retry_after=retry_after,
                            response_text=response.text
                        )

                # 400, 401, 403, 404エラーはリトライしない
                if response.status_code in [400, 401, 403, 404]:
                    return response

                # その他のエラー(500番台など)はリトライ可能
                if not response.ok:
                    if retry_count < self.max_retries:
                        delay = min(self.base_delay * (2 ** retry_count), self.max_delay)
                        self.logger.warning(
                            f"HTTPエラー {response.status_code}: {delay:.2f}秒待機してからリトライします... "
                            f"(試行 {retry_count + 1}/{self.max_retries + 1})"
                        )
                        time.sleep(delay)
                        retry_count += 1
                        continue
                    else:
                        raise APIError(
                            f"HTTPエラー {response.status_code}: 最大リトライ回数({self.max_retries}回)に達しました",
                            status_code=response.status_code,
                            response_text=response.text
                        )

                # 成功
                return response

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if retry_count < self.max_retries:
                    delay = min(self.base_delay * (2 ** retry_count), self.max_delay)
                    self.logger.warning(
                        f"接続エラー: {delay:.2f}秒待機してからリトライします... "
                        f"(試行 {retry_count + 1}/{self.max_retries + 1})"
                    )
                    time.sleep(delay)
                    retry_count += 1
                    continue
                else:
                    raise ConnectionError(
                        f"APIへの接続に失敗しました。最大リトライ回数({self.max_retries}回)に達しました",
                        original_error=e
                    ) from e

            except requests.exceptions.Timeout as e:
                last_exception = e
                if retry_count < self.max_retries:
                    delay = min(self.base_delay * (2 ** retry_count), self.max_delay)
                    self.logger.warning(
                        f"タイムアウトエラー: {delay:.2f}秒待機してからリトライします... "
                        f"(試行 {retry_count + 1}/{self.max_retries + 1})"
                    )
                    time.sleep(delay)
                    retry_count += 1
                    continue
                else:
                    raise TimeoutError(
                        f"リクエストがタイムアウトしました。最大リトライ回数({self.max_retries}回)に達しました",
                        timeout=None,
                        original_error=e
                    ) from e

            except requests.exceptions.RequestException as e:
                last_exception = e
                if retry_count < self.max_retries:
                    delay = min(self.base_delay * (2 ** retry_count), self.max_delay)
                    self.logger.warning(
                        f"リクエストエラー: {delay:.2f}秒待機してからリトライします... "
                        f"(試行 {retry_count + 1}/{self.max_retries + 1})"
                    )
                    time.sleep(delay)
                    retry_count += 1
                    continue
                else:
                    raise NetworkError(
                        f"リクエスト中にエラーが発生しました。最大リトライ回数({self.max_retries}回)に達しました",
                        original_error=e
                    ) from e

        # 最大リトライ回数に達した場合
        raise RetryExhaustedError(
            f"リクエストが{self.max_retries + 1}回連続で失敗しました",
            retry_count=self.max_retries + 1,
            last_error=last_exception
        )

    def _send_request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> requests.Response:
        """実際のHTTPリクエストを送信

        Args:
            method: HTTPメソッド
            url: リクエストURL
            params: クエリパラメータ
            headers: リクエストヘッダー
            **kwargs: requests.get/postなどの追加引数

        Returns:
            HTTPレスポンス

        Raises:
            ValidationError: サポートされていないHTTPメソッドの場合
        """
        method_upper = method.upper()
        if method_upper == "GET":
            return requests.get(url, headers=headers, params=params, **kwargs)
        elif method_upper == "POST":
            return requests.post(url, headers=headers, params=params, **kwargs)
        elif method_upper == "PUT":
            return requests.put(url, headers=headers, params=params, **kwargs)
        elif method_upper == "DELETE":
            return requests.delete(url, headers=headers, params=params, **kwargs)
        else:
            raise ValidationError(f"サポートされていないHTTPメソッド: {method}")
