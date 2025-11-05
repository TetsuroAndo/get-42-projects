"""ロギング設定モジュール

アプリケーション全体のロギング設定を管理します。
"""
import sys
import logging
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "get_42_projects",
    log_file: Optional[str] = None,
    log_level: int = logging.INFO,
    console: bool = True,
) -> logging.Logger:
    """ロガーを設定

    Args:
        name: ロガー名
        log_file: ログファイルのパス（Noneの場合はファイル出力なし）
        log_level: ログレベル
        console: コンソール出力を行うか

    Returns:
        設定済みのロガー
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # 既存のハンドラーをクリア（重複を防ぐ）
    logger.handlers.clear()

    # ファイルハンドラー（ログファイルに記録）
    if log_file:
        log_path = Path(log_file)
        # ログディレクトリを作成
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # コンソールハンドラー（標準出力にも記録）
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger
