"""プロジェクト取得モジュール

42のAPIからプロジェクト情報を取得するモジュールです。
"""
from .projects import Project42
from .payloads import Project, ProjectSession
from .rate_limiter import RateLimiter
from .http_client import HTTPClient
from .exceptions import (
    Project42Error,
    APIError,
    NotFoundError,
    RateLimitError,
    NetworkError,
    ConnectionError,
    TimeoutError,
    ValidationError,
    ParseError,
    ConfigurationError,
    SyncError,
    RetryExhaustedError,
)
# auth42モジュールの認証関連例外もエクスポート
from auth42.exceptions import AuthenticationError, AuthorizationError
from .config import Config
from .logger import setup_logger
from .converters import project_session_to_object
from .sync import ProjectSessionSyncer, SyncResult

__all__ = [
    "Project42",
    "Project",
    "ProjectSession",
    "RateLimiter",
    "HTTPClient",
    "Project42Error",
    "APIError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "RateLimitError",
    "NetworkError",
    "ConnectionError",
    "TimeoutError",
    "ValidationError",
    "ParseError",
    "ConfigurationError",
    "SyncError",
    "RetryExhaustedError",
    "Config",
    "setup_logger",
    "project_session_to_object",
    "ProjectSessionSyncer",
    "SyncResult",
]
