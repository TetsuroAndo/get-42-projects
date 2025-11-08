"""リクエスト計画モジュール

ローカルキャッシュに基づき、42 APIへのリクエスト候補を計画（Plan）するモジュールです。
実際のリクエストは送信しません。
"""
import logging
from typing import List, Set

from src.payloads import ProjectSession
from src.config import Config


class RequestPlanner:
    """ローカルキャッシュに基づき、42 APIへのリクエスト候補を計画（Plan）するクラス。

    実際のリクエストは送信しません。
    """

    BASE_URL = "https://api.intra.42.fr"

    def __init__(self, config: Config, logger: logging.Logger):
        """RequestPlannerの初期化

        Args:
            config: アプリケーション設定
            logger: ロガー
        """
        self.config = config
        self.logger = logger
        # 重複を避けるためSetを使用
        self.request_list: Set[str] = set()
        # エンドポイントの重複チェック用
        self.seen_endpoints: Set[str] = set()

    def _add_request(self, method: str, endpoint: str, description: str):
        """リクエスト候補をリストに追加します。

        Args:
            method (str): "GET", "POST" など
            endpoint (str): "/v2/..." から始まるパス
            description (str): リクエストの説明
        """
        # プレースホルダー（[ID]）が含まれているか、
        # 既にリストになければ追加
        if "[ID]" in endpoint or "[SCALE_ID]" in endpoint or "[CAMPUS_ID]" in endpoint or endpoint not in self.seen_endpoints:
            url = f"{self.BASE_URL}{endpoint}"
            entry = f"[{method}] {url}  ({description})"
            self.request_list.add(entry)
            self.seen_endpoints.add(endpoint)

    def plan_requests_from_cache(self, cached_sessions: List[ProjectSession]):
        """キャッシュされたセッションリストに基づき、
        fetcher.py が実行するであろうAPIリクエストをすべて列挙します。

        Args:
            cached_sessions: キャッシュされたプロジェクトセッションのリスト
        """
        self.logger.info(f"キャッシュ内の {len(cached_sessions)} 件のセッションに基づき、リクエスト候補を生成します...")
        self.request_list.clear()
        self.seen_endpoints.clear()

        if not cached_sessions:
            self.logger.warning("キャッシュが空です。リクエスト候補を生成できません。")
            self._plan_initial_fetch_template()  # キャッシュが無くてもテンプレートは表示
            self._print_plan()
            return

        # --- 1. 全セッション取得リクエスト（1段階目）のシミュレート ---
        # fetcher.pyのロジックに基づき、テンプレートURLを生成
        self._plan_initial_fetch_template()

        # --- 2. 詳細取得リクエスト（2段階目）のシミュレート ---
        self.logger.info(f"{len(cached_sessions)} 件のセッション詳細リクエスト（N+1クエリ）をシミュレート中...")

        for session in cached_sessions:
            session_id = session.id
            project_name = session.project_name

            # 'fortytwo_api/session_details.py' の 'get_project_session_with_details' を模倣

            # 2a. スキル
            self._add_request(
                "GET",
                f"/v2/project_sessions/{session_id}/project_sessions_skills",
                f"スキル (Session: {project_name})"
            )
            # 2b. 添付ファイル
            self._add_request(
                "GET",
                f"/v2/project_sessions/{session_id}/attachments",
                f"添付ファイル (Session: {project_name})"
            )
            # 2c. ルール
            self._add_request(
                "GET",
                f"/v2/project_sessions/{session_id}/project_sessions_rules",
                f"ルール一覧 (Session: {project_name})"
            )

            # 2c-i. ルールの詳細（ネストしたリクエスト）
            # キャッシュにルール詳細が保存されている場合、そのIDからリクエストを復元
            if session.rules:
                for rule in session.rules:
                    if isinstance(rule, dict) and rule.get("rule_id"):
                        rule_id = rule.get("rule_id")
                        self._add_request(
                            "GET",
                            f"/v2/rules/{rule_id}",
                            f"ルール詳細 {rule_id} (from Session: {project_name})"
                        )

            # 2d. 評価
            self._add_request(
                "GET",
                f"/v2/project_sessions/{session_id}/evaluations",
                f"評価 (Session: {project_name})"
            )

            # 2d-i. スケール詳細（ネストしたリクエスト）
            # 'get_project_session_with_details'はscale_idを取得しようとします。
            # キャッシュからは元のscale_idを特定できないため、テンプレートを登録します。
            self._add_request(
                "GET",
                "/v2/scales/[SCALE_ID]",
                f"スケール詳細 (from Session: {project_name})"
            )

            # 2e. チーム (ページネーションあり)
            self._add_request(
                "GET",
                f"/v2/project_sessions/{session_id}/teams?filter[with_mark]=true&page=1&per_page=100",
                f"チーム 1ページ目 (Session: {project_name})"
            )
            # 2ページ目以降のテンプレート
            self._add_request(
                "GET",
                f"/v2/project_sessions/{session_id}/teams?filter[with_mark]=true&page=...&per_page=100",
                f"チーム 2ページ目以降 (Session: {project_name})"
            )

        # --- 3. 結果の出力 ---
        self._print_plan()

    def _plan_initial_fetch_template(self):
        """全セッションを取得する1段階目のリクエストテンプレートを追加します"""
        campus_id = self.config.fortytwo_campus_id or "[CAMPUS_ID]"
        # fetcher.py のデフォルト (is_subscriptable=True) に合わせる
        is_subscriptable = True

        self._add_request(
            "GET",
            f"/v2/project_sessions?filter[campus_id]={campus_id}&filter[is_subscriptable]={str(is_subscriptable).lower()}&page=1&per_page=100",
            "プロジェクトセッション 1ページ目"
        )
        self._add_request(
            "GET",
            f"/v2/project_sessions?filter[campus_id]={campus_id}&filter[is_subscriptable]={str(is_subscriptable).lower()}&page=...&per_page=100",
            "プロジェクトセッション 2ページ目以降 (ページネーション)"
        )

    def _print_plan(self):
        """計画したリクエストリストをコンソールに出力します"""
        self.logger.info("=" * 60)
        self.logger.info(f"--- 42 API リクエスト実行計画 (合計 {len(self.request_list)} 種類の候補) ---")

        # 読みやすさのためにソートして出力
        sorted_list = sorted(list(self.request_list))
        for req in sorted_list:
            print(req)  # logger.infoではなく標準出力

        self.logger.info("--- 計画ここまで ---")
        self.logger.info("（注意: 実際の詳細リクエスト数はキャッシュ内のデータに基づきます）")
        self.logger.info("（注意: ページネーション(...)は、複数ページにまたがる可能性を示します）")
