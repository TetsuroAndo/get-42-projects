"""42プロジェクト取得モジュール

42のAPIからプロジェクト情報を取得します。
"""
from typing import List, Optional, Dict, Any, Tuple
import json
import logging
import requests

from auth42 import Auth42
from auth42.exceptions import AuthenticationError, AuthorizationError
from src.config import Config
from src.exceptions import (
    Project42Error,
    APIError,
    NotFoundError,
    NetworkError,
    ConnectionError,
    ValidationError,
    ParseError,
)
from src.payloads import Project, ProjectSession
from src.rate_limiter import RateLimiter
from src.http_client import HTTPClient


class Project42:
    """42プロジェクト取得クラス"""

    BASE_URL = "https://api.intra.42.fr"

    def __init__(self, auth: Auth42, logger: Optional[logging.Logger] = None, config: Optional[Config] = None):
        """プロジェクト取得クラスの初期化

        Args:
            auth: 42認証オブジェクト
            logger: ロガー(オプション)
            config: 設定オブジェクト(オプション)
        """
        self.auth = auth
        self.logger = logger or logging.getLogger(__name__)
        self.config = config

        # デフォルト設定値
        max_retries = config.max_retries if config else 3
        rate_limit_threshold = config.rate_limit_threshold if config else 10
        base_delay = config.base_delay if config else 0.5
        max_delay = config.max_delay if config else 60.0

        # レート制限管理とHTTPクライアントを初期化
        self.rate_limiter = RateLimiter(
            threshold=rate_limit_threshold,
            base_delay=base_delay,
            logger=self.logger
        )
        self.http_client = HTTPClient(
            rate_limiter=self.rate_limiter,
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            logger=self.logger
        )


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
            campus_id: キャンパスID(オプション)
            cursus_id: カリキュラムID(オプション、デフォルト: 21 (Piscine C))
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
            response = self.http_client.request("GET", url, headers=headers, params=params)

            # エラーハンドリング
            if response.status_code == 400:
                raise ValidationError(
                    "リクエストの形式が不正です。パラメータを確認してください",
                    response_text=response.text
                )
            elif response.status_code == 401:
                raise AuthenticationError(
                    f"認証に失敗しました。トークンが無効です。再認証を試みてください。レスポンス: {response.text}",
                    status_code=401
                )
            elif response.status_code == 403:
                raise AuthorizationError(
                    f"アクセスが拒否されました。必要なロールやスコープが不足している可能性があります。レスポンス: {response.text}",
                    status_code=403
                )
            elif response.status_code == 404:
                raise NotFoundError(
                    "リソースが見つかりませんでした",
                    response_text=response.text
                )
            elif not response.ok:
                raise APIError(
                    f"プロジェクト取得に失敗しました (HTTP {response.status_code})",
                    status_code=response.status_code,
                    response_text=response.text
                )

            projects_data = response.json()
            return [Project.from_api_response(project) for project in projects_data]

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                "APIへの接続に失敗しました。HTTPSを使用しているか確認してください",
                original_error=e
            ) from e
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                "リクエスト中にエラーが発生しました",
                original_error=e
            ) from e
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ParseError(
                "レスポンスの解析に失敗しました",
                original_error=e
            ) from e

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
            response = self.http_client.request("GET", url, headers=headers)

            if response.status_code == 401:
                raise AuthenticationError(
                    "認証に失敗しました。トークンが無効です。再認証を試みてください",
                    response_text=response.text
                )
            elif response.status_code == 403:
                raise AuthorizationError(
                    "アクセスが拒否されました。必要なロールやスコープが不足している可能性があります",
                    response_text=response.text
                )
            elif response.status_code == 404:
                raise NotFoundError(
                    "プロジェクトが見つかりませんでした",
                    resource_id=str(project_id),
                    response_text=response.text
                )
            elif not response.ok:
                raise APIError(
                    f"プロジェクト取得に失敗しました (HTTP {response.status_code})",
                    status_code=response.status_code,
                    response_text=response.text
                )

            project_data = response.json()
            return Project.from_api_response(project_data)

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                "APIへの接続に失敗しました。HTTPSを使用しているか確認してください",
                original_error=e
            ) from e
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                "リクエスト中にエラーが発生しました",
                original_error=e
            ) from e
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ParseError(
                "レスポンスの解析に失敗しました",
                original_error=e
            ) from e

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
            response = self.http_client.request("GET", url, headers=headers)

            if response.status_code == 401:
                raise AuthenticationError(
                    "認証に失敗しました。トークンが無効です。再認証を試みてください",
                    response_text=response.text
                )
            elif response.status_code == 403:
                raise AuthorizationError(
                    "アクセスが拒否されました。必要なロールやスコープが不足している可能性があります",
                    response_text=response.text
                )
            elif response.status_code == 404:
                raise NotFoundError(
                    "プロジェクトが見つかりませんでした",
                    resource_id=slug,
                    response_text=response.text
                )
            elif not response.ok:
                raise APIError(
                    f"プロジェクト取得に失敗しました (HTTP {response.status_code})",
                    status_code=response.status_code,
                    response_text=response.text
                )

            project_data = response.json()
            return Project.from_api_response(project_data)

        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                "APIへの接続に失敗しました。HTTPSを使用しているか確認してください",
                original_error=e
            ) from e
        except requests.exceptions.RequestException as e:
            raise NetworkError(
                "リクエスト中にエラーが発生しました",
                original_error=e
            ) from e
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ParseError(
                "レスポンスの解析に失敗しました",
                original_error=e
            ) from e

    def get_all_projects(
        self,
        campus_id: Optional[int] = None,
        cursus_id: Optional[int] = None,
        **kwargs
    ) -> List[Project]:
        """全プロジェクトを取得(ページネーション対応)

        Args:
            campus_id: キャンパスID(オプション)
            cursus_id: カリキュラムID(オプション)
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
            campus_id: キャンパスID(オプション、東京キャンパスは9)
            is_subscriptable: 利用可能なプロジェクトのみを取得するか(デフォルト: True)
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
            response = self.http_client.request("GET", url, params=params, headers=headers)

            # エラーハンドリング
            if response.status_code == 400:
                raise ValidationError(
                    "リクエストの形式が不正です。パラメータを確認してください",
                    response_text=response.text
                )
            elif response.status_code == 401:
                raise AuthenticationError(
                    f"認証に失敗しました。トークンが無効です。再認証を試みてください。レスポンス: {response.text}",
                    status_code=401
                )
            elif response.status_code == 403:
                raise AuthorizationError(
                    f"アクセスが拒否されました。必要なロールやスコープが不足している可能性があります。レスポンス: {response.text}",
                    status_code=403
                )
            elif response.status_code == 404:
                raise NotFoundError(
                    "リソースが見つかりませんでした",
                    response_text=response.text
                )
            elif not response.ok:
                raise APIError(
                    f"プロジェクトセッション取得に失敗しました (HTTP {response.status_code})",
                    status_code=response.status_code,
                    response_text=response.text
                )

            sessions_data = response.json()
            return [ProjectSession.from_api_response(session) for session in sessions_data]

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ParseError(
                "レスポンスの解析に失敗しました",
                original_error=e
            ) from e

    def get_all_project_sessions(
        self,
        campus_id: Optional[int] = None,
        is_subscriptable: Optional[bool] = True,
        **kwargs
    ) -> List[ProjectSession]:
        """全プロジェクトセッションを取得(ページネーション対応)

        Args:
            campus_id: キャンパスID(オプション、東京キャンパスは9)
            is_subscriptable: 利用可能なプロジェクトのみを取得するか(デフォルト: True)
            **kwargs: その他のフィルター条件

        Returns:
            全プロジェクトセッションのリスト
        """
        all_sessions = []
        page = 1
        per_page = 100

        self.logger.info(f"全プロジェクトセッション取得開始 (campus_id={campus_id}, is_subscriptable={is_subscriptable})")

        while True:
            self.logger.info(f"  ページ {page} を取得中...")
            sessions = self.get_project_sessions(
                campus_id=campus_id,
                is_subscriptable=is_subscriptable,
                page=page,
                per_page=per_page,
                **kwargs
            )

            if not sessions:
                self.logger.info(f"  ページ {page}: データなし")
                break

            all_sessions.extend(sessions)
            self.logger.info(f"  ページ {page}: {len(sessions)}件取得")

            # レスポンスがper_page未満なら最後のページ
            if len(sessions) < per_page:
                break

            page += 1

        self.logger.info(f"全プロジェクトセッション取得完了: 合計 {len(all_sessions)}件")
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

    def categorize_rules(self, rules: List[Dict[str, Any]]) -> Tuple[List[str], List[str]]:
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
