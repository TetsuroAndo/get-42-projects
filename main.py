"""メインスクリプト

42からプロジェクト情報を取得し、Anytypeにインポートします。
"""
import sys
from typing import List

from src.config import Config
from auth42 import Auth42, TokenManager, TokenError, Auth42Error
from src import Project42, Project, Project42Error
from anytype import AnytypeClient, TableManager, TableRow

def project_to_table_row(project: Project) -> TableRow:
    """ProjectオブジェクトをTableRowに変換

    Args:
        project: 42のプロジェクトオブジェクト

    Returns:
        Anytypeテーブル用の行データ
    """
    fields = {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "description": project.description or "",
        "tier": project.tier,
        "difficulty": project.difficulty,
        "duration": project.duration or "",
        "objectives": ", ".join(project.objectives),
        "tags": ", ".join(project.tags),
        "exam": project.exam,
        "repository": project.repository or "",
        "created_at": project.created_at or "",
        "updated_at": project.updated_at or "",
    }
    return TableRow(fields=fields)


def main():
    """メイン処理"""
    try:
        # 設定を読み込む
        config = Config.from_env()
        config.validate()

        print("設定の読み込みが完了しました")

        # 42認証を初期化
        token_manager = TokenManager(token_file=config.token_file)
        auth = Auth42(
            client_id=config.fortytwo_client_id,
            client_secret=config.fortytwo_client_secret,
            token_manager=token_manager,
        )

        print("42認証の初期化が完了しました")

        # プロジェクト取得を初期化
        project42 = Project42(auth=auth)

        print("42プロジェクト取得の初期化が完了しました")

        # プロジェクトを取得
        print("プロジェクトを取得中...")
        projects = project42.get_all_projects(
            campus_id=config.fortytwo_campus_id,
            cursus_id=config.fortytwo_cursus_id,
        )

        print(f"{len(projects)}件のプロジェクトを取得しました")

        # Anytypeクライアントを初期化
        anytype_client = AnytypeClient(
            api_url=config.anytype_api_url,
            api_key=config.anytype_api_key,
        )

        print("Anytypeクライアントの初期化が完了しました")

        # テーブルマネージャーを初期化
        table_manager = TableManager(
            client=anytype_client,
            table_id=config.anytype_table_id,
        )

        print("テーブルマネージャーの初期化が完了しました")

        # プロジェクトをテーブル行に変換
        print("プロジェクトをテーブル形式に変換中...")
        rows = [project_to_table_row(project) for project in projects]

        # テーブルに追加（バッチ処理）
        print("Anytypeテーブルに追加中...")
        batch_size = 100
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            table_manager.create_rows(batch)
            print(f"  {i + len(batch)}/{len(rows)} 件を追加しました")

        print("処理が完了しました！")

    except ValueError as e:
        print(f"設定エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except (TokenError, Auth42Error) as e:
        print(f"認証エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Project42Error as e:
        print(f"プロジェクト取得エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"予期しないエラーが発生しました: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
