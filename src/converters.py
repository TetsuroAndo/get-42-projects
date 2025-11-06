"""データ変換モジュール

42のAPIデータをAnytypeテーブル形式に変換する処理を担当します。
"""
from typing import Dict, Any, List, Optional
from anytype import TableRow
from src.projects import ProjectSession


def extract_skill_names(skills: List[Dict[str, Any]]) -> List[str]:
    """スキルリストからスキル名を抽出

    Args:
        skills: スキル情報のリスト

    Returns:
        スキル名のリスト
    """
    return [
        skill.get("name", "")
        for skill in skills
        if isinstance(skill, dict) and skill.get("name")
    ]


def extract_attachment_urls(attachments: List[Dict[str, Any]]) -> List[str]:
    """添付ファイルリストからURLを抽出

    Args:
        attachments: 添付ファイル情報のリスト

    Returns:
        添付ファイルURLのリスト
    """
    urls = []
    for att in attachments:
        if not isinstance(att, dict):
            continue
        url = att.get("url") or att.get("link") or att.get("file_url")
        if url:
            urls.append(url)
    return urls


def format_rules(rules: List[Dict[str, Any]]) -> List[str]:
    """ルール情報を文字列形式に変換

    Args:
        rules: ルール情報のリスト

    Returns:
        フォーマット済みルール文字列のリスト
    """
    rule_descriptions = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue

        rule_str = rule.get("name", "") or rule.get("description", "")
        if not rule_str:
            continue

        # 必須ルールの場合はマークを付ける
        if rule.get("required"):
            rule_str = f"[必須] {rule_str}"

        rule_descriptions.append(rule_str)

    return rule_descriptions


def project_session_to_table_row(session: ProjectSession) -> TableRow:
    """ProjectSessionオブジェクトをTableRowに変換

    Args:
        session: 42のプロジェクトセッションオブジェクト

    Returns:
        Anytypeテーブル用の行データ
    """
    skill_names = extract_skill_names(session.skills)
    attachment_urls = extract_attachment_urls(session.attachments)
    rule_descriptions = format_rules(session.rules)

    fields = {
        "id": session.id,
        "project_id": session.project_id,
        "project_name": session.project_name,
        "project_slug": session.project_slug,
        "description": session.description or "",
        "xp": session.xp,
        "creation_date": session.creation_date or "",
        "cursus_id": session.cursus_id,
        "cursus_name": session.cursus_name or "",
        "cursus_slug": session.cursus_slug or "",
        "max_people": session.max_people,
        "solo": session.solo,
        "correction_number": session.correction_number,
        "keywords": ", ".join(session.keywords),
        "skills": ", ".join(skill_names),
        "attachment_urls": ", ".join(attachment_urls),
        "attachment_count": len(attachment_urls),
        "is_subscriptable": session.is_subscriptable,
        "begin_at": session.begin_at or "",
        "end_at": session.end_at or "",
        "rules": " | ".join(rule_descriptions),
    }
    return TableRow(fields=fields)
