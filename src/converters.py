"""データ変換モジュール

42のAPIデータをAnytypeオブジェクト形式に変換する処理を担当します。
"""
from typing import Dict, Any, List
from anytype import AnytypeObject
from src.payloads import ProjectSession


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


def project_session_to_object(session: ProjectSession) -> AnytypeObject:
    """ProjectSessionオブジェクトをAnytypeObjectに変換

    Args:
        session: 42のプロジェクトセッションオブジェクト

    Returns:
        Anytypeオブジェクト
    """
    skill_names = extract_skill_names(session.skills)
    attachment_urls = extract_attachment_urls(session.attachments)
    rule_descriptions = format_rules(session.rules)

    # 成功率をパーセンテージ形式に変換
    success_rate_percent = (
        f"{session.team_success_rate * 100:.1f}%"
        if session.team_success_rate is not None
        else ""
    )

    # ボディコンテンツをMarkdown形式で作成
    body = _build_markdown_body(
        session,
        skill_names,
        attachment_urls,
        rule_descriptions,
        success_rate_percent
    )

    # プロパティを設定
    properties = _build_properties(session, skill_names)

    # アイコンを設定(プロジェクト名の最初の文字を使用)
    icon = {
        "emoji": "📄",
        "format": "emoji",
    }

    return AnytypeObject(
        name=session.project_name,
        body=body,
        type_key="page",
        icon=icon,
        properties=properties,
    )


def _build_markdown_body(
    session: ProjectSession,
    skill_names: List[str],
    attachment_urls: List[str],
    rule_descriptions: List[str],
    success_rate_percent: str
) -> str:
    """Markdown形式のボディコンテンツを構築

    Args:
        session: プロジェクトセッションオブジェクト
        skill_names: スキル名のリスト
        attachment_urls: 添付ファイルURLのリスト
        rule_descriptions: ルール説明のリスト
        success_rate_percent: 成功率のパーセンテージ文字列

    Returns:
        Markdown形式のボディ文字列
    """
    body_parts = []

    if session.description:
        body_parts.append(f"## 説明\n\n{session.description}\n")

    body_parts.append("## 基本情報\n\n")
    body_parts.append(f"- **プロジェクトID**: {session.project_id}\n")
    body_parts.append(f"- **プロジェクト名**: {session.project_name}\n")
    body_parts.append(f"- **スラッグ**: {session.project_slug}\n")
    body_parts.append(f"- **XP**: {session.xp}\n")
    body_parts.append(f"- **作成日**: {session.creation_date or 'N/A'}\n")
    body_parts.append(f"- **ステータス**: {session.status or 'N/A'}\n")
    body_parts.append(f"- **最大人数**: {session.max_people}\n")
    body_parts.append(f"- **ソロ**: {'はい' if session.solo else 'いいえ'}\n")
    body_parts.append(f"- **修正回数**: {session.correction_number}\n")
    body_parts.append(f"- **利用可能**: {'はい' if session.is_subscriptable else 'いいえ'}\n")

    if session.begin_at:
        body_parts.append(f"- **開始日**: {session.begin_at}\n")
    if session.end_at:
        body_parts.append(f"- **終了日**: {session.end_at}\n")

    body_parts.append("\n## コース情報\n\n")
    body_parts.append(f"- **コースID**: {session.cursus_id}\n")
    body_parts.append(f"- **コース名**: {session.cursus_name or 'N/A'}\n")
    body_parts.append(f"- **コーススラッグ**: {session.cursus_slug or 'N/A'}\n")

    if session.keywords:
        body_parts.append(f"\n## キーワード\n\n{', '.join(session.keywords)}\n")

    if skill_names:
        body_parts.append(f"\n## スキル\n\n{', '.join(skill_names)}\n")

    if attachment_urls:
        body_parts.append(f"\n## 添付ファイル ({len(attachment_urls)}件)\n\n")
        for url in attachment_urls:
            body_parts.append(f"- [{url}]({url})\n")

    if rule_descriptions:
        body_parts.append("\n## ルール\n\n")
        for rule in rule_descriptions:
            body_parts.append(f"- {rule}\n")

    if session.forbidden_rules:
        body_parts.append("\n## 禁止ルール\n\n")
        for rule in session.forbidden_rules:
            body_parts.append(f"- {rule}\n")

    if session.recommended_rules:
        body_parts.append("\n## 推奨ルール\n\n")
        for rule in session.recommended_rules:
            body_parts.append(f"- {rule}\n")

    if session.team_total_count is not None:
        body_parts.append("\n## チーム統計\n\n")
        body_parts.append(f"- **総チーム数**: {session.team_total_count}\n")
        body_parts.append(f"- **成功チーム数**: {session.team_success_count or 0}\n")
        body_parts.append(f"- **成功率**: {success_rate_percent}\n")

    return "\n".join(body_parts)


def _build_properties(session: ProjectSession, skill_names: List[str]) -> List[Dict[str, Any]]:
    """Anytypeオブジェクトのプロパティリストを構築

    Args:
        session: プロジェクトセッションオブジェクト
        skill_names: スキル名のリスト

    Returns:
        プロパティのリスト
    """
    properties = [
        {
            "key": "project_id",
            "text": str(session.project_id),
        },
        {
            "key": "project_slug",
            "text": session.project_slug,
        },
        {
            "key": "xp",
            "number": session.xp,
        },
        {
            "key": "cursus_id",
            "number": session.cursus_id,
        },
        {
            "key": "max_people",
            "number": session.max_people,
        },
        {
            "key": "solo",
            "checkbox": session.solo,
        },
        {
            "key": "correction_number",
            "number": session.correction_number,
        },
        {
            "key": "is_subscriptable",
            "checkbox": session.is_subscriptable,
        },
    ]

    if session.description:
        properties.append({
            "key": "description",
            "text": session.description,
        })

    if session.cursus_name:
        properties.append({
            "key": "cursus_name",
            "text": session.cursus_name,
        })

    if session.status:
        properties.append({
            "key": "status",
            "text": session.status,
        })

    if session.creation_date:
        properties.append({
            "key": "creation_date",
            "text": session.creation_date,
        })

    if session.begin_at:
        properties.append({
            "key": "begin_at",
            "text": session.begin_at,
        })

    if session.end_at:
        properties.append({
            "key": "end_at",
            "text": session.end_at,
        })

    if skill_names:
        properties.append({
            "key": "skills",
            "text": ", ".join(skill_names),
        })

    if session.keywords:
        properties.append({
            "key": "keywords",
            "text": ", ".join(session.keywords),
        })

    return properties
