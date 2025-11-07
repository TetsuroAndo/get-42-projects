"""レート制限管理モジュール

APIのレート制限を管理するユーティティクラスです。
"""
import time
import logging
from typing import Optional
import requests
from threading import Lock


class RateLimiter:
    """レート制限管理クラス

    APIレスポンスのレート制限ヘッダーをチェックし、
    必要に応じて待機処理を行います。
    また、1秒間に2リクエストという事前制御も行います。
    """

    def __init__(
        self,
        threshold: int = 10,
        base_delay: float = 0.5,
        requests_per_second: float = 2.0,
        logger: Optional[logging.Logger] = None
    ):
        """レート制限管理クラスの初期化

        Args:
            threshold: レート制限残りがこの値以下になったら待機
            base_delay: 基本待機時間（秒）
            requests_per_second: 1秒あたりの最大リクエスト数（デフォルト: 2.0）
            logger: ロガー（オプション）
        """
        self.threshold = threshold
        self.base_delay = base_delay
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second  # 1秒間に2回 = 0.5秒間隔
        self.logger = logger or logging.getLogger(__name__)

        # 最後のリクエスト時刻を記録（スレッドセーフのためLockを使用）
        self._last_request_time: Optional[float] = None
        self._lock = Lock()

    def wait_if_needed(self) -> None:
        """リクエスト送信前に、必要に応じて待機

        1秒間に2リクエストという制限を守るため、
        最後のリクエストから最低0.5秒経過するまで待機します。
        """
        with self._lock:
            current_time = time.time()

            if self._last_request_time is not None:
                elapsed = current_time - self._last_request_time

                if elapsed < self.min_interval:
                    wait_time = self.min_interval - elapsed
                    self.logger.debug(
                        f"レート制限事前制御: 前回リクエストから{elapsed:.3f}秒経過。"
                        f"{wait_time:.3f}秒待機します（1秒間に{self.requests_per_second}回の制限）"
                    )
                    time.sleep(wait_time)
                    current_time = time.time()

            # リクエスト時刻を記録
            self._last_request_time = current_time

    def check_and_wait(self, response: requests.Response) -> None:
        """レート制限ヘッダーをチェックし、必要に応じて待機

        Args:
            response: HTTPレスポンス
        """
        # レート制限ヘッダーを確認
        rate_limit_remaining = response.headers.get("X-RateLimit-Remaining")
        rate_limit_reset = response.headers.get("X-RateLimit-Reset")

        if rate_limit_remaining:
            try:
                remaining = int(rate_limit_remaining)
                self.logger.debug(f"レート制限残り: {remaining}リクエスト")

                # 残りが閾値以下の場合、リセット時刻まで待機
                if remaining <= self.threshold:
                    if rate_limit_reset:
                        try:
                            reset_time = int(rate_limit_reset)
                            current_time = int(time.time())
                            wait_time = max(0, reset_time - current_time)

                            if wait_time > 0:
                                self.logger.warning(
                                    f"レート制限が近づいています（残り: {remaining}）。"
                                    f"{wait_time}秒待機します..."
                                )
                                time.sleep(wait_time)
                                # 待機後、最後のリクエスト時刻を更新
                                with self._lock:
                                    self._last_request_time = time.time()
                        except (ValueError, TypeError):
                            # リセット時刻が取得できない場合は基本待機時間を使用
                            self.logger.warning(
                                f"レート制限が近づいています（残り: {remaining}）。"
                                f"{self.base_delay}秒待機します..."
                            )
                            time.sleep(self.base_delay)
                            with self._lock:
                                self._last_request_time = time.time()
                    else:
                        # リセット時刻が不明な場合は基本待機時間を使用
                        self.logger.warning(
                            f"レート制限が近づいています（残り: {remaining}）。"
                            f"{self.base_delay}秒待機します..."
                        )
                        time.sleep(self.base_delay)
                        with self._lock:
                            self._last_request_time = time.time()
            except (ValueError, TypeError):
                # ヘッダーの値が無効な場合は無視
                pass

    def get_retry_after(self, response: requests.Response) -> Optional[int]:
        """429エラーのRetry-Afterヘッダーを取得

        Args:
            response: HTTPレスポンス

        Returns:
            Retry-Afterの値（秒）、取得できない場合はNone
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return int(retry_after)
            except (ValueError, TypeError):
                return None
        return None
