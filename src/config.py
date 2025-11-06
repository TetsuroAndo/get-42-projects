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
    anytype_space_id: str = ""
    anytype_objects_id: Optional[str] = None  # オプション（特定のオブジェクトIDを指定する場合）

    # その他設定
    token_file: Optional[Path] = None
    log_file: str = "get_42_projects.log"
    batch_size: int = 50
    detail_fetch_interval: int = 10  # 詳細情報取得の進捗表示間隔

    @classmethod
    def from_env(cls) -> "Config":
        """環境変数から設定を読み込む

        環境変数名:
        - FT_UID: 42 APIのクライアントID
        - FT_SECRET: 42 APIのクライアントシークレット
        """
        client_id = os.getenv("FT_UID", "")
        client_secret = os.getenv("FT_SECRET", "")

        return cls(
            fortytwo_client_id=client_id,
            fortytwo_client_secret=client_secret,
            fortytwo_campus_id=_get_int_env("FORTYTWO_CAMPUS_ID"),
            fortytwo_cursus_id=_get_int_env("FORTYTWO_CURSUS_ID", default=21),
            anytype_api_url=os.getenv("ANYTYPE_API_URL", "http://localhost:3030"),
            anytype_api_key=os.getenv("ANYTYPE_API_KEY", ""),
            anytype_space_id=os.getenv("ANYTYPE_SPACE_ID", ""),
            anytype_objects_id=os.getenv("ANYTYPE_OBJECTS_ID"),
            token_file=_get_path_env("TOKEN_FILE"),
            log_file=os.getenv("LOG_FILE", "get_42_projects.log"),
            batch_size=_get_int_env("BATCH_SIZE", default=50),
            detail_fetch_interval=_get_int_env("DETAIL_FETCH_INTERVAL", default=10),
        )

    def validate(self) -> None:
        """設定の妥当性を検証"""
        errors = []

        if not self.fortytwo_client_id:
            errors.append("FT_UID が設定されていません")
        if not self.fortytwo_client_secret:
            errors.append("FT_SECRET が設定されていません")
        if not self.anytype_api_key:
            errors.append("ANYTYPE_API_KEY が設定されていません")
        if not self.anytype_space_id:
            errors.append("ANYTYPE_SPACE_ID が設定されていません")

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
