"""42プロジェクト取得モジュール

42のAPIからプロジェクト情報を取得します。
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import requests

from ..auth import Auth42


class Project42Error(Exception):
    """42プロジェクト取得関連のエラー"""
    pass


@dataclass
class Project:
    """42のプロジェクト情報を保持するデータクラス"""
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    tier: Optional[int] = None
    difficulty: Optional[int] = None
    duration: Optional[str] = None
    objectives: List[str] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    exam: bool = False
    repository: Optional[str] = None
    parent_id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "Project":
        """APIレスポンスからProjectオブジェクトを作成"""
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            slug=data.get("slug", ""),
            description=data.get("description"),
            tier=data.get("tier"),
            difficulty=data.get("difficulty"),
            duration=data.get("duration"),
            objectives=[obj.get("name", "") for obj in data.get("objectives", [])],
            attachments=data.get("attachments", []),
            tags=[tag.get("name", "") for tag in data.get("tags", [])],
            exam=data.get("exam", False),
            repository=data.get("repository"),
            parent_id=data.get("parent_id"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "tier": self.tier,
            "difficulty": self.difficulty,
            "duration": self.duration,
            "objectives": self.objectives,
            "tags": self.tags,
            "exam": self.exam,
            "repository": self.repository,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class Project42:
    """42プロジェクト取得クラス"""

    BASE_URL = "https://api.intra.42.fr"

    def __init__(self, auth: Auth42):
        """プロジェクト取得クラスの初期化

        Args:
            auth: 42認証オブジェクト
        """
        self.auth = auth

    def get_projects(
        self,
        campus_id: Optional[int] = None,
        cursus_id: Optional[int] = None,
        page: int = 1,
        per_page: int = 100,
        **kwargs
    ) -> List[Project]:
        """プロジェクト一覧を取得

        Args:
            campus_id: キャンパスID（オプション）
            cursus_id: カリキュラムID（オプション、デフォルト: 21 (Piscine C)）
            page: ページ番号
            per_page: 1ページあたりの項目数
            **kwargs: その他のフィルター条件

        Returns:
            プロジェクトのリスト
        """
        url = f"{self.BASE_URL}/v2/projects"
        params = {
            "page": page,
            "per_page": per_page,
        }

        if campus_id:
            params["filter[campus_id]"] = campus_id
        if cursus_id:
            params["filter[cursus_id]"] = cursus_id

        # その他のフィルター条件を追加
        for key, value in kwargs.items():
            if key.startswith("filter["):
                params[key] = value
            else:
                params[f"filter[{key}]"] = value

        headers = self.auth.get_headers()

        try:
            response = requests.get(url, headers=headers, params=params)

            # エラーハンドリング
            if response.status_code == 400:
                raise Project42Error(
                    f"リクエストの形式が不正です: {response.text}\n"
                    "パラメータを確認してください。"
                )
            elif response.status_code == 401:
                raise Project42Error(
                    f"認証に失敗しました: {response.text}\n"
                    "トークンが無効です。再認証を試みてください。"
                )
            elif response.status_code == 403:
                raise Project42Error(
                    f"アクセスが拒否されました: {response.text}\n"
                    "必要なロールやスコープが不足している可能性があります。"
                )
            elif response.status_code == 404:
                raise Project42Error(
                    f"リソースが見つかりませんでした: {response.text}"
                )
            elif not response.ok:
                raise Project42Error(
                    f"プロジェクト取得に失敗しました (HTTP {response.status_code}): {response.text}"
                )

            projects_data = response.json()
            return [Project.from_api_response(project) for project in projects_data]

        except requests.exceptions.ConnectionError as e:
            raise Project42Error(
                f"APIへの接続に失敗しました: {e}\n"
                "HTTPSを使用しているか確認してください。"
            ) from e
        except requests.exceptions.RequestException as e:
            raise Project42Error(f"リクエスト中にエラーが発生しました: {e}") from e
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise Project42Error(f"レスポンスの解析に失敗しました: {e}") from e

    def get_project_by_id(self, project_id: int) -> Project:
        """プロジェクトIDでプロジェクトを取得

        Args:
            project_id: プロジェクトID

        Returns:
            プロジェクトオブジェクト
        """
        url = f"{self.BASE_URL}/v2/projects/{project_id}"
        headers = self.auth.get_headers()

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == 401:
                raise Project42Error(
                    f"認証に失敗しました: {response.text}\n"
                    "トークンが無効です。再認証を試みてください。"
                )
            elif response.status_code == 403:
                raise Project42Error(
                    f"アクセスが拒否されました: {response.text}\n"
                    "必要なロールやスコープが不足している可能性があります。"
                )
            elif response.status_code == 404:
                raise Project42Error(
                    f"プロジェクトID {project_id} が見つかりませんでした: {response.text}"
                )
            elif not response.ok:
                raise Project42Error(
                    f"プロジェクト取得に失敗しました (HTTP {response.status_code}): {response.text}"
                )

            project_data = response.json()
            return Project.from_api_response(project_data)

        except requests.exceptions.ConnectionError as e:
            raise Project42Error(
                f"APIへの接続に失敗しました: {e}\n"
                "HTTPSを使用しているか確認してください。"
            ) from e
        except requests.exceptions.RequestException as e:
            raise Project42Error(f"リクエスト中にエラーが発生しました: {e}") from e
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise Project42Error(f"レスポンスの解析に失敗しました: {e}") from e

    def get_project_by_slug(self, slug: str) -> Project:
        """プロジェクトスラッグでプロジェクトを取得

        Args:
            slug: プロジェクトスラッグ

        Returns:
            プロジェクトオブジェクト
        """
        url = f"{self.BASE_URL}/v2/projects/{slug}"
        headers = self.auth.get_headers()

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == 401:
                raise Project42Error(
                    f"認証に失敗しました: {response.text}\n"
                    "トークンが無効です。再認証を試みてください。"
                )
            elif response.status_code == 403:
                raise Project42Error(
                    f"アクセスが拒否されました: {response.text}\n"
                    "必要なロールやスコープが不足している可能性があります。"
                )
            elif response.status_code == 404:
                raise Project42Error(
                    f"プロジェクトスラッグ '{slug}' が見つかりませんでした: {response.text}"
                )
            elif not response.ok:
                raise Project42Error(
                    f"プロジェクト取得に失敗しました (HTTP {response.status_code}): {response.text}"
                )

            project_data = response.json()
            return Project.from_api_response(project_data)

        except requests.exceptions.ConnectionError as e:
            raise Project42Error(
                f"APIへの接続に失敗しました: {e}\n"
                "HTTPSを使用しているか確認してください。"
            ) from e
        except requests.exceptions.RequestException as e:
            raise Project42Error(f"リクエスト中にエラーが発生しました: {e}") from e
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise Project42Error(f"レスポンスの解析に失敗しました: {e}") from e

    def get_all_projects(
        self,
        campus_id: Optional[int] = None,
        cursus_id: Optional[int] = None,
        **kwargs
    ) -> List[Project]:
        """全プロジェクトを取得（ページネーション対応）

        Args:
            campus_id: キャンパスID（オプション）
            cursus_id: カリキュラムID（オプション）
            **kwargs: その他のフィルター条件

        Returns:
            全プロジェクトのリスト
        """
        all_projects = []
        page = 1
        per_page = 100

        while True:
            projects = self.get_projects(
                campus_id=campus_id,
                cursus_id=cursus_id,
                page=page,
                per_page=per_page,
                **kwargs
            )

            if not projects:
                break

            all_projects.extend(projects)

            # レスポンスがper_page未満なら最後のページ
            if len(projects) < per_page:
                break

            page += 1

        return all_projects
