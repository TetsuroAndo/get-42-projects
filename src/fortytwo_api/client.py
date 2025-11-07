"""42プロジェクト取得モジュール

42のAPIからプロジェクト情報を取得します。
"""
from typing import List, Optional
import logging

from auth42 import Auth42
from auth42.exceptions import AuthenticationError, AuthorizationError
from src.config import Config
from src.exceptions import (
    ValidationError,
    APIError,
    NotFoundError,
)
from src.payloads import Project, ProjectSession
from src.rate_limiter import RateLimiter
from src.http_client import HTTPClient
from .api_client import APIResponseHandler
from .session_details import SessionDetailsFetcher


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

        # セッション詳細取得クラスを初期化
        self.session_details_fetcher = SessionDetailsFetcher(
            auth=self.auth,
            http_client=self.http_client,
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
            APIResponseHandler.handle_response(response, error_message_prefix="プロジェクト取得")
            projects_data = response.json()
            return [Project.from_api_response(project) for project in projects_data]
        except (ValidationError, AuthenticationError, AuthorizationError, NotFoundError, APIError):
            raise
        except Exception as e:
            APIResponseHandler.handle_request_exceptions(e)

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
            APIResponseHandler.handle_response(
                response,
                error_message_prefix="プロジェクト取得",
                resource_id=str(project_id)
            )
            project_data = response.json()
            return Project.from_api_response(project_data)
        except (ValidationError, AuthenticationError, AuthorizationError, NotFoundError, APIError):
            raise
        except Exception as e:
            APIResponseHandler.handle_request_exceptions(e)

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
            APIResponseHandler.handle_response(
                response,
                error_message_prefix="プロジェクト取得",
                resource_id=slug
            )
            project_data = response.json()
            return Project.from_api_response(project_data)
        except (ValidationError, AuthenticationError, AuthorizationError, NotFoundError, APIError):
            raise
        except Exception as e:
            APIResponseHandler.handle_request_exceptions(e)

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
            APIResponseHandler.handle_response(response, error_message_prefix="プロジェクトセッション取得")
            sessions_data = response.json()
            return [ProjectSession.from_api_response(session) for session in sessions_data]
        except (ValidationError, AuthenticationError, AuthorizationError, NotFoundError, APIError):
            raise
        except Exception as e:
            APIResponseHandler.handle_request_exceptions(e)

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

    def get_project_session_with_details(self, session: ProjectSession) -> ProjectSession:
        """プロジェクトセッションの詳細情報(スキル、添付ファイル、ルール、チーム統計)を取得して更新

        Args:
            session: プロジェクトセッションオブジェクト

        Returns:
            詳細情報が追加されたプロジェクトセッションオブジェクト
        """
        return self.session_details_fetcher.get_project_session_with_details(session)
