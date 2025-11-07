"""ペイロード処理モジュール

APIレスポンスからデータオブジェクトへの変換処理を行います。
"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field


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
    status: Optional[str] = None  # 進行ステータス
    forbidden_rules: List[str] = field(default_factory=list)  # 禁止条件
    recommended_rules: List[str] = field(default_factory=list)  # 推奨条件
    team_total_count: Optional[int] = None  # チーム総数
    team_success_count: Optional[int] = None  # 成功チーム数
    team_success_rate: Optional[float] = None  # 成功率（0.0-1.0）

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
            status=data.get("status"),  # 進行ステータス
            forbidden_rules=[],  # 後で取得
            recommended_rules=[],  # 後で取得
            team_total_count=None,  # 後で取得
            team_success_count=None,  # 後で取得
            team_success_rate=None,  # 後で取得
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
            "status": self.status,
            "forbidden_rules": self.forbidden_rules,
            "recommended_rules": self.recommended_rules,
            "team_total_count": self.team_total_count,
            "team_success_count": self.team_success_count,
            "team_success_rate": self.team_success_rate,
        }
