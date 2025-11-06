# get-42-projects

42からプロジェクト情報を取得し、Anytypeにインポートするツールです。

## セットアップ

### 1. 依存関係のインストール

```sh
uv sync
```

### 2. 環境変数の設定

プロジェクトルートの`.env.template`ファイルをコピーして`.env`ファイルを作成し、実際の値を設定してください：

```sh
cp .env.template .env
```

`.env`ファイルを編集して、実際の値を設定してください。

#### 環境変数の読み込み方法

**方法1: python-dotenvを使用（推奨）**

`python-dotenv`を使用すると、`.env`ファイルを自動的に読み込みます：

```sh
# 依存関係に追加
uv add python-dotenv
```

その後、`main.py`の先頭に以下を追加してください：

```python
from dotenv import load_dotenv
load_dotenv()
```

**方法2: 手動で環境変数を設定**

シェルで直接環境変数を設定するか、`.env`ファイルを手動で読み込みます：

```sh
# .envファイルを読み込む（bash/zsh）
export $(cat .env | xargs)

# または手動で設定
export FT_UID=your_client_id
export FT_SECRET=your_client_secret
# ... など
```

**設定する環境変数:**

**42 API認証情報:**
- `FT_UID` : 42 APIのクライアントID
- `FT_SECRET`: 42 APIのクライアントシークレット

**Anytype API設定:**
- `ANYTYPE_API_URL`: Anytype APIのURL（デフォルト: http://localhost:3030）
- `ANYTYPE_API_KEY`: Anytype APIキー
- `ANYTYPE_TABLE_ID`: AnytypeテーブルID

**42 APIフィルター（オプション）:**
- `FORTYTWO_CAMPUS_ID`: キャンパスID
- `FORTYTWO_CURSUS_ID`: カリキュラムID（デフォルト: 21）

**トークンファイル（オプション）:**
- `TOKEN_FILE`: トークンファイルのパス（デフォルト: ~/.42_token.json）

> **注意**: `.env`ファイルは`.gitignore`に含まれているため、機密情報を安全に保存できます。

### 3. 実行

```sh
python main.py
```

## サブモジュールの使用方法

このプロジェクトは`auth42`と`anytype`の2つのサブモジュールを含んでいます。それぞれは独立して使用することも、コマンドラインから直接実行することもできます。

### auth42モジュールの使用

42 API認証をテストするには：

```bash
# 環境変数から認証情報を読み込む
export FT_UID=your_client_id
export FT_SECRET=your_client_secret
python -m auth42.main

# コマンドライン引数で認証情報を指定
python -m auth42.main --client-id your_client_id --client-secret your_client_secret

# トークン情報を取得
python -m auth42.main --client-id your_client_id --client-secret your_client_secret --token-info
```

詳細は`auth42/README.md`を参照してください。

### anytypeモジュールの使用

Anytype API接続をテストするには：

```bash
# 環境変数からAPIキーを読み込む
export ANYTYPE_API_KEY=your_api_key
export ANYTYPE_API_URL=http://localhost:3030
python -m anytype.main

# コマンドライン引数でAPIキーを指定
python -m anytype.main --api-key your_api_key --api-url http://localhost:3030

# テーブルIDを指定して接続テスト
python -m anytype.main --api-key your_api_key --table-id your_table_id
```

詳細は`anytype/README.md`を参照してください。

## プロジェクト構造

- `auth42/`: 42認証モジュール（サブモジュール）
  - `client.py`: 認証クライアント
  - `token.py`: トークン管理
  - `exceptions.py`: 例外クラス
  - `main.py`: コマンドラインエントリーポイント
- `anytype/`: Anytype API操作モジュール（サブモジュール）
  - `client.py`: APIクライアント
  - `table.py`: テーブル操作
  - `main.py`: コマンドラインエントリーポイント
- `src/`: メインアプリケーション
  - `config.py`: 設定管理
  - `projects.py`: プロジェクト取得
  - `sync.py`: 同期処理

## エラーハンドリング

モジュールは以下のエラーを適切に処理します：

- `TokenError`: トークン取得・認証関連のエラー
- `Project42Error`: プロジェクト取得関連のエラー
- `Auth42Error`: 認証全般のエラー

エラーメッセージには、HTTPステータスコード、エラー内容、解決方法のヒントが含まれます。

## 実装詳細

### 42 API認証

- **OAuth2クライアントクレデンシャルフロー**を使用
- トークンは自動的にキャッシュされ、期限切れ前に自動更新
- `/oauth/token/info`エンドポイントを使用してトークン情報を確認可能
- HTTPS必須（すべての通信はSSL/TLSで保護）

### エラーコードの対応

- **400**: リクエストの形式が不正
- **401**: 認証失敗（無効なトークン）
- **403**: アクセス拒否（権限不足）
- **404**: リソースが見つからない
- **422**: 処理できないエンティティ
- **500**: サーバーエラー

```python
from src.auth import Auth42
from src.api import Project42
from src.anytype import AnytypeClient, TableManager, TableRow

# 認証
auth = Auth42(client_id="...", client_secret="...")

# プロジェクト取得
project42 = Project42(auth=auth)
projects = project42.get_all_projects()

# Anytypeに追加
client = AnytypeClient(api_key="...")
table = TableManager(client=client, table_id="...")
for project in projects:
    row = TableRow(fields={...})
    table.create_row(row)
```
