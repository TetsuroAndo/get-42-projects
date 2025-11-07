"""セッション詳細取得モジュール

42のプロジェクトセッションの詳細情報（スキル、添付ファイル、ルール、チーム統計など）を取得する処理を提供します。
"""
import logging
from typing import List, Dict, Any, Tuple
import requests

from auth42 import Auth42
from src.http_client import HTTPClient
from src.exceptions import Project42Error
from src.payloads import ProjectSession


class SessionDetailsFetcher:
    """セッション詳細情報取得クラス"""

    BASE_URL = "https://api.intra.42.fr"

    def __init__(self, auth: Auth42, http_client: HTTPClient, logger: logging.Logger):
        """セッション詳細取得クラスの初期化

        Args:
            auth: 42認証オブジェクト
            http_client: HTTPクライアント
            logger: ロガー
        """
        self.auth = auth
        self.http_client = http_client
        self.logger = logger

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
            response = self.http_client.request("GET", url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Project42Error:
            # Project42Errorはそのまま再スロー
            raise
        except requests.exceptions.RequestException as e:
            # エラー時は空リストを返す(ログに記録はしない)
            self.logger.debug(f"スキル情報取得エラー (session_id={project_session_id}): {e}")
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
            response = self.http_client.request("GET", url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Project42Error:
            # Project42Errorはそのまま再スロー
            raise
        except requests.exceptions.RequestException as e:
            # エラー時は空リストを返す(ログに記録はしない)
            self.logger.debug(f"添付ファイル情報取得エラー (session_id={project_session_id}): {e}")
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
            response = self.http_client.request("GET", url, headers=headers)
            response.raise_for_status()
            rules_data = response.json()

            # ルールの詳細情報を取得
            detailed_rules = []
            for rule_item in rules_data:
                rule_id = rule_item.get("rule_id")
                if rule_id:
                    try:
                        rule_url = f"{self.BASE_URL}/v2/rules/{rule_id}"
                        rule_response = self.http_client.request("GET", rule_url, headers=headers)
                        rule_response.raise_for_status()
                        rule_detail = rule_response.json()
                        detailed_rules.append({
                            "rule_id": rule_id,
                            "required": rule_item.get("required"),
                            "kind": rule_detail.get("kind"),
                            "name": rule_detail.get("name"),
                            "description": rule_detail.get("description"),
                        })
                    except (Project42Error, requests.exceptions.RequestException) as e:
                        # 詳細取得失敗時は基本情報のみ
                        self.logger.debug(f"ルール詳細取得エラー (rule_id={rule_id}): {e}")
                        detailed_rules.append({
                            "rule_id": rule_id,
                            "required": rule_item.get("required"),
                        })

            return detailed_rules
        except Project42Error:
            # Project42Errorはそのまま再スロー
            raise
        except requests.exceptions.RequestException as e:
            # エラー時は空リストを返す(ログに記録はしない)
            self.logger.debug(f"ルール情報取得エラー (session_id={project_session_id}): {e}")
            return []

    def get_project_session_teams(self, project_session_id: int) -> Dict[str, Any]:
        """プロジェクトセッションのチーム統計情報を取得

        ガイドに基づいて、チームの成績(Success した割合など)を取得します。

        Args:
            project_session_id: プロジェクトセッションID

        Returns:
            チーム統計情報の辞書(total_count, success_count, success_rate)
        """
        url = f"{self.BASE_URL}/v2/project_sessions/{project_session_id}/teams"
        headers = self.auth.get_headers()

        try:
            # 完了したチームのみを取得(with_mark=true)
            params = {"filter[with_mark]": "true"}
            response = self.http_client.request("GET", url, headers=headers, params=params)
            response.raise_for_status()
            teams_data = response.json()

            total_count = len(teams_data)
            success_count = 0

            # 成功したチームをカウント
            # validated?がtrue、またはfinal_markが一定以上(例:125以上)の場合を成功とする
            for team in teams_data:
                if team.get("validated") is True:
                    success_count += 1
                elif team.get("final_mark") is not None:
                    # final_markが125以上の場合も成功とみなす(42の一般的な合格基準)
                    if team.get("final_mark", 0) >= 125:
                        success_count += 1

            success_rate = success_count / total_count if total_count > 0 else 0.0

            return {
                "total_count": total_count,
                "success_count": success_count,
                "success_rate": success_rate,
            }
        except Project42Error:
            # Project42Errorはそのまま再スロー
            raise
        except requests.exceptions.RequestException as e:
            # エラー時はデフォルト値を返す
            self.logger.debug(f"チーム統計情報取得エラー (session_id={project_session_id}): {e}")
            return {
                "total_count": 0,
                "success_count": 0,
                "success_rate": 0.0,
            }

    @staticmethod
    def categorize_rules(rules: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
        """ルールをForbidden(禁止)とRecommended(推奨)に分類

        Args:
            rules: ルール情報のリスト

        Returns:
            (forbidden_rules, recommended_rules) のタプル
        """
        forbidden_rules = []
        recommended_rules = []

        for rule in rules:
            if not isinstance(rule, dict):
                continue

            rule_name = rule.get("name", "")
            rule_description = rule.get("description", "")
            rule_kind = rule.get("kind", "")
            rule_text = rule_name or rule_description

            if not rule_text:
                continue

            # ルール名や説明に「forbidden」「禁止」「not allowed」などのキーワードが含まれる場合
            rule_text_lower = rule_text.lower()
            if any(keyword in rule_text_lower for keyword in ["forbidden", "禁止", "not allowed", "not permitted"]):
                forbidden_rules.append(rule_text)
            # ルール名や説明に「recommended」「推奨」「suggested」などのキーワードが含まれる場合
            elif any(keyword in rule_text_lower for keyword in ["recommended", "推奨", "suggested", "should"]):
                recommended_rules.append(rule_text)
            # kindがinscription(登録条件)でrequiredがFalseの場合は推奨とみなす
            elif rule_kind == "inscription" and rule.get("required") is False:
                recommended_rules.append(rule_text)
            # kindがinscriptionでrequiredがTrueの場合は必須条件(禁止ではないが、必須として扱う)
            # その他のルールは説明に基づいて判定

        return forbidden_rules, recommended_rules

    def get_project_session_with_details(self, session: ProjectSession) -> ProjectSession:
        """プロジェクトセッションの詳細情報(スキル、添付ファイル、ルール、チーム統計)を取得して更新

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

        # ルールをForbidden/Recommendedに分類
        forbidden_rules, recommended_rules = self.categorize_rules(session.rules)
        session.forbidden_rules = forbidden_rules
        session.recommended_rules = recommended_rules

        # 評価の回数(correction_number)を取得
        # 評価(evaluations)エンドポイントから取得を試みる
        try:
            evaluations_url = f"{self.BASE_URL}/v2/project_sessions/{session.id}/evaluations"
            headers = self.auth.get_headers()
            response = self.http_client.request("GET", evaluations_url, headers=headers)
            if response.ok:
                evaluations = response.json()
                # kindがscaleの場合、correction_numberを取得
                for eval_item in evaluations:
                    if eval_item.get("kind") == "scale":
                        scale_id = eval_item.get("scale_id")
                        if scale_id:
                            try:
                                scale_url = f"{self.BASE_URL}/v2/scales/{scale_id}"
                                scale_response = self.http_client.request("GET", scale_url, headers=headers)
                                if scale_response.ok:
                                    scale_data = scale_response.json()
                                    session.correction_number = scale_data.get("correction_number")
                                    break
                            except requests.exceptions.RequestException:
                                pass
        except requests.exceptions.RequestException:
            pass

        # チーム統計情報を取得
        team_stats = self.get_project_session_teams(session.id)
        session.team_total_count = team_stats.get("total_count")
        session.team_success_count = team_stats.get("success_count")
        session.team_success_rate = team_stats.get("success_rate")

        return session
