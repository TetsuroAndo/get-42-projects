"""プロジェクト取得モジュール

42のAPIからプロジェクト情報を取得するモジュールです。
"""
from .projects import Project42, Project, Project42Error

__all__ = ["Project42", "Project", "Project42Error"]
