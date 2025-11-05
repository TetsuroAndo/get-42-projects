"""42プロジェクト取得モジュール

42のAPIからプロジェクト情報を取得します。
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import requests

from auth42 import Auth42


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


@dataclass
class ProjectSession:
    """42のプロジェクトセッション情報を保持するデータクラス

    ガイドに基づいて、東京キャンパスのカリキュラムプロジェクト情報を
    取得するために必要な全てのフィールドを含みます。
    """
    id: int
    project_id: int
    project_name: str
    project_slug: str
    description: Optional[str] = None
    xp: Optional[int] = None  # difficultyから取得
    creation_date: Optional[str] = None  # created_at
    cursus_id: Optional[int] = None
    cursus_name: Optional[str] = None
    cursus_slug: Optional[str] = None
    max_people: Optional[int] = None
    solo: Optional[bool] = None
    correction_number: Optional[int] = None  # 評価の回数
    keywords: List[str] = field(default_factory=list)  # tags
    skills: List[Dict[str, Any]] = field(default_factory=list)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    is_subscriptable: Optional[bool] = None
    begin_at: Optional[str] = None
    end_at: Optional[str] = None
    rules: List[Dict[str, Any]] = field(default_factory=list)  # ルール情報

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "ProjectSession":
        """APIレスポンスからProjectSessionオブジェクトを作成"""
        project = data.get("project", {})
        cursus = data.get("cursus", {})

        return cls(
            id=data.get("id"),
            project_id=project.get("id") if project else None,
            project_name=project.get("name", ""),
            project_slug=project.get("slug", ""),
            description=project.get("description"),
            xp=project.get("difficulty"),  # difficultyがXP/難易度を示す
            creation_date=data.get("created_at"),
            cursus_id=cursus.get("id") if cursus else None,
            cursus_name=cursus.get("name") if cursus else None,
            cursus_slug=cursus.get("slug") if cursus else None,
            max_people=data.get("max_people"),
            solo=data.get("solo"),
            correction_number=None,  # 後で取得
            keywords=[tag.get("name", "") for tag in project.get("tags", [])],
            skills=[],  # 後で取得
            attachments=[],  # 後で取得
            is_subscriptable=data.get("is_subscriptable"),
            begin_at=data.get("begin_at"),
            end_at=data.get("end_at"),
            rules=[],  # 後で取得
        )

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "project_slug": self.project_slug,
            "description": self.description,
            "xp": self.xp,
            "creation_date": self.creation_date,
            "cursus_id": self.cursus_id,
            "cursus_name": self.cursus_name,
            "cursus_slug": self.cursus_slug,
            "max_people": self.max_people,
            "solo": self.solo,
            "correction_number": self.correction_number,
            "keywords": self.keywords,
            "skills": self.skills,
            "attachments": self.attachments,
            "is_subscriptable": self.is_subscriptable,
            "begin_at": self.begin_at,
            "end_at": self.end_at,
            "rules": self.rules,
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

    def get_project_sessions(
        self,
        campus_id: Optional[int] = None,
        is_subscriptable: Optional[bool] = True,
        page: int = 1,
        per_page: int = 100,
        **kwargs
    ) -> List[ProjectSession]:
        """プロジェクトセッション一覧を取得

        ガイドに基づいて、東京キャンパスのカリキュラムプロジェクト情報を取得します。

        Args:
            campus_id: キャンパスID（オプション、東京キャンパスは9）
            is_subscriptable: 利用可能なプロジェクトのみを取得するか（デフォルト: True）
            page: ページ番号
            per_page: 1ページあたりの項目数
            **kwargs: その他のフィルター条件

        Returns:
            プロジェクトセッションのリスト
        """
        url = f"{self.BASE_URL}/v2/project_sessions"
        params = {
            "page": page,
            "per_page": per_page,
        }

        if campus_id:
            params["filter[campus_id]"] = campus_id
        if is_subscriptable is not None:
            params["filter[is_subscriptable]"] = str(is_subscriptable).lower()

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
                    f"プロジェクトセッション取得に失敗しました (HTTP {response.status_code}): {response.text}"
                )

            sessions_data = response.json()
            return [ProjectSession.from_api_response(session) for session in sessions_data]

        except requests.exceptions.ConnectionError as e:
            raise Project42Error(
                f"APIへの接続に失敗しました: {e}\n"
                "HTTPSを使用しているか確認してください。"
            ) from e
        except requests.exceptions.RequestException as e:
            raise Project42Error(f"リクエスト中にエラーが発生しました: {e}") from e
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise Project42Error(f"レスポンスの解析に失敗しました: {e}") from e

    def get_all_project_sessions(
        self,
        campus_id: Optional[int] = None,
        is_subscriptable: Optional[bool] = True,
        **kwargs
    ) -> List[ProjectSession]:
        """全プロジェクトセッションを取得（ページネーション対応）

        Args:
            campus_id: キャンパスID（オプション、東京キャンパスは9）
            is_subscriptable: 利用可能なプロジェクトのみを取得するか（デフォルト: True）
            **kwargs: その他のフィルター条件

        Returns:
            全プロジェクトセッションのリスト
        """
        all_sessions = []
        page = 1
        per_page = 100

        while True:
            sessions = self.get_project_sessions(
                campus_id=campus_id,
                is_subscriptable=is_subscriptable,
                page=page,
                per_page=per_page,
                **kwargs
            )

            if not sessions:
                break

            all_sessions.extend(sessions)

            # レスポンスがper_page未満なら最後のページ
            if len(sessions) < per_page:
                break

            page += 1

        return all_sessions

    def get_project_session_skills(self, project_session_id: int) -> List[Dict[str, Any]]:
        """プロジェクトセッションのスキル情報を取得

        Args:
            project_session_id: プロジェクトセッションID

        Returns:
            スキル情報のリスト
        """
        url = f"{self.BASE_URL}/v2/project_sessions/{project_session_id}/project_sessions_skills"
        headers = self.auth.get_headers()

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # エラー時は空リストを返す（ログに記録はしない）
            return []

    def get_project_session_attachments(self, project_session_id: int) -> List[Dict[str, Any]]:
        """プロジェクトセッションの添付ファイル情報を取得

        Args:
            project_session_id: プロジェクトセッションID

        Returns:
            添付ファイル情報のリスト
        """
        url = f"{self.BASE_URL}/v2/project_sessions/{project_session_id}/attachments"
        headers = self.auth.get_headers()

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # エラー時は空リストを返す（ログに記録はしない）
            return []

    def get_project_session_rules(self, project_session_id: int) -> List[Dict[str, Any]]:
        """プロジェクトセッションのルール情報を取得

        Args:
            project_session_id: プロジェクトセッションID

        Returns:
            ルール情報のリスト
        """
        url = f"{self.BASE_URL}/v2/project_sessions/{project_session_id}/project_sessions_rules"
        headers = self.auth.get_headers()

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            rules_data = response.json()

            # ルールの詳細情報を取得
            detailed_rules = []
            for rule_item in rules_data:
                rule_id = rule_item.get("rule_id")
                if rule_id:
                    try:
                        rule_url = f"{self.BASE_URL}/v2/rules/{rule_id}"
                        rule_response = requests.get(rule_url, headers=headers)
                        rule_response.raise_for_status()
                        rule_detail = rule_response.json()
                        detailed_rules.append({
                            "rule_id": rule_id,
                            "required": rule_item.get("required"),
                            "kind": rule_detail.get("kind"),
                            "name": rule_detail.get("name"),
                            "description": rule_detail.get("description"),
                        })
                    except requests.exceptions.RequestException:
                        # 詳細取得失敗時は基本情報のみ
                        detailed_rules.append({
                            "rule_id": rule_id,
                            "required": rule_item.get("required"),
                        })

            return detailed_rules
        except requests.exceptions.RequestException as e:
            # エラー時は空リストを返す（ログに記録はしない）
            return []

    def get_project_session_with_details(self, session: ProjectSession) -> ProjectSession:
        """プロジェクトセッションの詳細情報（スキル、添付ファイル、ルール）を取得して更新

        Args:
            session: プロジェクトセッションオブジェクト

        Returns:
            詳細情報が追加されたプロジェクトセッションオブジェクト
        """
        # スキル情報を取得
        session.skills = self.get_project_session_skills(session.id)

        # 添付ファイル情報を取得
        session.attachments = self.get_project_session_attachments(session.id)

        # ルール情報を取得
        session.rules = self.get_project_session_rules(session.id)

        # 評価の回数（correction_number）を取得
        # 評価（evaluations）エンドポイントから取得を試みる
        try:
            evaluations_url = f"{self.BASE_URL}/v2/project_sessions/{session.id}/evaluations"
            headers = self.auth.get_headers()
            response = requests.get(evaluations_url, headers=headers)
            if response.ok:
                evaluations = response.json()
                # kindがscaleの場合、correction_numberを取得
                for eval_item in evaluations:
                    if eval_item.get("kind") == "scale":
                        scale_id = eval_item.get("scale_id")
                        if scale_id:
                            try:
                                scale_url = f"{self.BASE_URL}/v2/scales/{scale_id}"
                                scale_response = requests.get(scale_url, headers=headers)
                                if scale_response.ok:
                                    scale_data = scale_response.json()
                                    session.correction_number = scale_data.get("correction_number")
                                    break
                            except requests.exceptions.RequestException:
                                pass
        except requests.exceptions.RequestException:
            pass

        return session
