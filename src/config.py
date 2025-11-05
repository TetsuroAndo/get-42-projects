"""設定管理モジュール

環境変数や設定ファイルから設定を読み込むモジュールです。
"""
import os
from typing import Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Config:
    """アプリケーション設定クラス"""
    # 42 API設定
    fortytwo_client_id: str
    fortytwo_client_secret: str
    fortytwo_campus_id: Optional[int] = None
    fortytwo_cursus_id: Optional[int] = 21  # デフォルト: Piscine C

    # Anytype API設定
    anytype_api_url: str = "http://localhost:3030"
    anytype_api_key: str = ""
    anytype_table_id: str = ""

    # その他設定
    token_file: Optional[Path] = None

    @classmethod
    def from_env(cls) -> "Config":
        """環境変数から設定を読み込む

        複数の環境変数名をサポート:
        - FORTYTWO_CLIENT_ID / UID / CLIENT_ID
        - FORTYTWO_CLIENT_SECRET / SECRET / CLIENT_SECRET
        """
        # 複数の環境変数名をサポート
        client_id = (
            os.getenv("FORTYTWO_CLIENT_ID")
            or os.getenv("UID")
            or os.getenv("CLIENT_ID")
            or ""
        )
        client_secret = (
            os.getenv("FORTYTWO_CLIENT_SECRET")
            or os.getenv("SECRET")
            or os.getenv("CLIENT_SECRET")
            or ""
        )

        return cls(
            fortytwo_client_id=client_id,
            fortytwo_client_secret=client_secret,
            fortytwo_campus_id=_get_int_env("FORTYTWO_CAMPUS_ID"),
            fortytwo_cursus_id=_get_int_env("FORTYTWO_CURSUS_ID", default=21),
            anytype_api_url=os.getenv("ANYTYPE_API_URL", "http://localhost:3030"),
            anytype_api_key=os.getenv("ANYTYPE_API_KEY", ""),
            anytype_table_id=os.getenv("ANYTYPE_TABLE_ID", ""),
            token_file=_get_path_env("TOKEN_FILE"),
        )

    def validate(self) -> None:
        """設定の妥当性を検証"""
        errors = []

        if not self.fortytwo_client_id:
            errors.append("FORTYTWO_CLIENT_ID が設定されていません")
        if not self.fortytwo_client_secret:
            errors.append("FORTYTWO_CLIENT_SECRET が設定されていません")
        if not self.anytype_api_key:
            errors.append("ANYTYPE_API_KEY が設定されていません")
        if not self.anytype_table_id:
            errors.append("ANYTYPE_TABLE_ID が設定されていません")

        if errors:
            raise ValueError("\n".join(errors))


def _get_int_env(key: str, default: Optional[int] = None) -> Optional[int]:
    """環境変数を整数として取得"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_path_env(key: str) -> Optional[Path]:
    """環境変数をPathとして取得"""
    value = os.getenv(key)
    if value is None:
        return None
    return Path(value)
