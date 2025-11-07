このクエリに基づき、42 API 2.0ドキュメントを利用して、東京キャンパスのカリキュラムプロジェクト情報（特に要求された要素）を取得するための具体的な方法とロジックを以下に詳細にまとめます。

---

## 東京キャンパスのカリキュラム（プロジェクト）情報取得ドキュメント

### 1. 前提条件と認証

すべてのAPIコールには、OAuth 2.0に基づいた適切な認証トークンが必要です。また、多くのエンドポイント（特に管理者や教育関連の詳細情報）には特定のロール（例：`Basic staff`, `Advanced tutor`）が必要となる場合があります。

### 2. 東京キャンパスIDの特定

まず、東京キャンパスの固有ID（`campus_id`）を特定する必要があります。APIレスポンスから、**東京キャンパスのIDは26**であることが確認されています。

*   **APIエンドポイント:** `/v2/campus`
*   **ロジック:** `/v2/campus`を検索するか、`/v2/endpoints/:id`を参照し、東京の`id`を取得します。（以降、このIDを`[CAMPUS_ID]`と表記します。）

#### curlコマンドでの実行例

**注意:** curlコマンドで`filter[...]`のような角括弧を含むURLパラメータを使用する場合、zshなどのシェルでは角括弧がグロブパターンとして解釈されるため、`-g`オプションでグロブ展開を無効化するか、URLエンコードする必要があります。

```bash
# 方法1: -gオプションでグロブ展開を無効化（推奨・動作確認済み）
curl -g -X GET "https://api.intra.42.fr/v2/campus?filter[name]=Tokyo" \
  -H "Authorization: Bearer $TOKEN"

# 方法2: URLエンコードを使用
curl -X GET "https://api.intra.42.fr/v2/campus?filter%5Bname%5D=Tokyo" \
  -H "Authorization: Bearer $TOKEN"
```

**実行結果の例:**
```json
[{
  "id": 26,
  "name": "Tokyo",
  "time_zone": "Asia/Tokyo",
  "language": {"id": 13, "name": "Japanese", "identifier": "ja"},
  "users_count": 6596,
  ...
}]
```

**URLエンコードの対応表:**
- `[` → `%5B`
- `]` → `%5D`

### 2.5. カリキュラム（Cursus）IDの特定

42 APIで利用可能なカリキュラムの一覧とIDを取得する方法です。

*   **APIエンドポイント:** `/v2/cursus`
*   **ロジック:** `/v2/cursus`エンドポイントで全カリキュラムの一覧を取得し、必要なカリキュラムの`id`を確認します。

#### curlコマンドでの実行例

```bash
# 全カリキュラムの一覧を取得
curl -g -X GET "https://api.intra.42.fr/v2/cursus" \
  -H "Authorization: Bearer $TOKEN"

# 特定のカリキュラムを名前で検索（例: "42"）
curl -g -X GET "https://api.intra.42.fr/v2/cursus?filter[name]=42" \
  -H "Authorization: Bearer $TOKEN"

# 特定のカリキュラムをスラッグで検索（例: "42cursus"）
curl -g -X GET "https://api.intra.42.fr/v2/cursus?filter[slug]=42cursus" \
  -H "Authorization: Bearer $TOKEN"
```

**主要なカリキュラムID（実際のAPIレスポンスに基づく）:**
- **21**: 42cursus（メインカリキュラム、`kind: "main"`）
- **1**: 42（非推奨、`kind: "main_deprecated"`）
- **53**: 42.zip（`kind: "main"`）
- **78**: 42Senior（`kind: "main"`）

**実行結果の例:**

```json
// filter[slug]=42cursus の結果
[{
  "id": 21,
  "created_at": "2019-07-29T08:45:17.896Z",
  "name": "42cursus",
  "slug": "42cursus",
  "kind": "main"
}]

// filter[name]=42 の結果
[{
  "id": 1,
  "created_at": "2014-11-02T16:43:38.480Z",
  "name": "42",
  "slug": "42",
  "kind": "main_deprecated"
}]
```

**注意:** 
- カリキュラムIDは環境や時期によって異なる可能性があるため、実際のAPIレスポンスで確認することを推奨します。
- `kind: "main"`が現在のメインカリキュラムです。`main_deprecated`は非推奨のカリキュラムです。

### 3. 東京キャンパスに関連するプロジェクトセッションの取得（Available Projects のみ）

カリキュラム（プロジェクト）は、特定のキャンパスやキュルシュ（Cursus）に関連付けられた「プロジェクトセッション（Project session）」として定義されます。

*   **APIエンドポイント:** `/v2/project_sessions`
*   **ロジック:**
    1.  `/v2/project_sessions`エンドポイントに対して、フィルタリングパラメータを使用し、東京キャンパス（`[CAMPUS_ID]`）に関連するセッションを取得します。
        *   例: `GET /v2/project_sessions?filter[campus_id]=[CAMPUS_ID]`
    2.  「Available projects のみ」の条件を満たすには、結果として得られたプロジェクトセッションのデータ内のフィールドを確認します。
        *   `is_subscriptable`が`true`であるセッションを確認します。
        *   必要に応じて、`begin_at`および`end_at`フィールドを参照し、現在利用可能な期間内にあるかを確認できます。

### 4. 必須要素の取得方法とマッピング

ステップ3で取得したプロジェクトセッションのデータ（およびそれにネストされたプロジェクトデータ）から、要求された各要素を取得します。

| 取得したい要素 | データ取得元 (APIリソース) | 詳細な取得パス/ロジック |
| :--- | :--- | :--- |
| **Available projects のみ** | `Project session` | `is_subscriptable: true`のフィルタリングを使用します。 |
| **project name** | `Project session` (ネストされた`project`オブジェクト) | `project.name`フィールドから取得します。 |
| **discription** | `Project session` (ネストされた`project`オブジェクト) | `project.description`フィールドから取得します。 |
| **xp** | `Project`または`Project session` | `project.difficulty`フィールド（経験値/難易度を示す可能性）や、`project_session`のソートパラメータの`difficulty`を参照します。 |
| **creation date** | `Project session` | `created_at`フィールドから取得します。 |
| **Cursus Type** | `Project session` (ネストされた`cursus`オブジェクト) | `cursus_id`またはネストされた`cursus.name`/`cursus.slug`フィールドから取得します。 |
| **チーム人数** | `Project session` | `max_people`フィールドで最大人数を取得します。また、`solo: true/false`で個人プロジェクトかを確認できます。 |
| **評価の回数** | `Project session` (ネストされた`evaluations`オブジェクト) | ネストされた`evaluations`内の情報（特に`kind: scale`の場合）や、関連する`scales`エンドポイント (`/v2/scales/:id`)で**`correction_number`**を参照します。 |
| **Keywords** | `Project` (ネストされた`tags`リスト) | `project`オブジェクト内の`tags`配列からタグ名を取得できます。また、`/v2/projects/:project_id/tags`からも取得可能です。 |
| **Skills** | `Project session skills`または`Project` | `Project session`のIDを用いて`/v2/project_sessions/:project_session_id/project_sessions_skills`から関連スキルを取得します。`project`オブジェクト内にも`skills`リストがあります。 |
| **添付ファイルのリンク（数は1~複数）** | `Attachments` | `project_session_id`または`project_id`を使用して、`/v2/project_sessions/:project_session_id/attachments`または`/v2/projects/:project_id/attachments`エンドポイントから取得します。 |

### 5. 詳細条件（Forbidden か Recommended か、課題の解放条件と禁止条件）の取得

課題の開始条件やルールに関する情報は、プロジェクトセッションのルール（Project Sessions Rules）および関連するルール（Rules）リソースから取得されます。

*   **APIエンドポイント:** `/v2/project_sessions/:project_session_id/project_sessions_rules`
*   **ロジック:**
    1.  ステップ3で取得した各プロジェクトセッションID (`:project_session_id`) を使用して、上記エンドポイントを呼び出します。
    2.  返された`project_sessions_rules`には、`rule_id`や、そのルールが`required`かどうか（必須条件か）といった情報が含まれています。
    3.  さらに詳細なルールの内容（「Forbidden」や「Recommended」といった具体的な条件）を取得するには、`rule_id`を使用して`/v2/rules/:id`エンドポイントを呼び出します。
        *   ルールの`kind`には、`inscription`（登録条件）、`retry_inscription`（再挑戦登録）、`correction`（評価）などが含まれます。これらのルール名や説明（`description`）が、課題の解放条件や禁止条件に該当します。

### 6. その他のチームの成績（Success した割合など）の取得（追加で取得したい要素）

特定のプロジェクトにおける全チームの成績や成功率（`Success`した割合）は、`Teams`エンドポイントを利用し、結果をフィルタリングして集計することで取得が可能です。

*   **APIエンドポイント:** `/v2/projects/:project_id/teams` または `/v2/project_sessions/:project_session_id/teams`
*   **ロジック:**
    1.  プロジェクトID（またはプロジェクトセッションID）を使用して、関連するチームのリストを取得します。
    2.  チーム（`teams`）のデータには、`final_mark`（最終点）や、`status`（進行状況）、および`validated?`（検証済みか）の情報が含まれています。
    3.  フィルタリングパラメータ`filter[with_mark]=true`を使用して、最終マークが付いたチーム（完了したチーム）のみを抽出できます。
    4.  抽出したチームのデータ内の`final_mark`や`validated?`の情報を基に、プロジェクト成功と見なされるチームの数を集計し、総完了チーム数に対する割合（成功した割合）を算出します。

### まとめ：データ取得のフロー

東京キャンパスのプロジェクト詳細情報を取得するための推奨フローは、まずプロジェクトセッションを核として情報を集め、次に詳細情報を結合することです。

1.  **東京キャンパスIDの取得:** `/v2/campus` (または既知のID `26`)。
2.  **プロジェクトセッションのリスト取得:** `/v2/project_sessions?filter[campus_id]=[CAMPUS_ID]`で、利用可能なプロジェクトセッションIDと、内包されるプロジェクト情報（名前、説明、開始/終了日、チーム人数、評価回数）を取得します。
3.  **付加情報の取得（ループ処理）:**
    *   各プロジェクトセッションIDを使用して、**スキル**情報(`/v2/project_sessions/:id/project_sessions_skills`)を取得します。
    *   各プロジェクトセッションIDを使用して、**添付ファイル**情報(`/v2/project_sessions/:id/attachments`)を取得します。
    *   各プロジェクトセッションIDを使用して、**ルール/条件**情報(`/v2/project_sessions/:id/project_sessions_rules`)を取得し、さらにルールIDを用いて具体的なルール名と説明（解放/禁止条件）を取得します。
    *   （オプションで）各プロジェクトIDを使用して、**チームの成績統計**(`/v2/projects/:project_id/teams`)を取得し、成功率を計算します。

ご提示いただいたソースに基づき、ユーザーに関連する**学業、管理、および認定記録**を管理するために利用可能なエンドポイントを以下にまとめます。これらのエンドポイントの多くは、特定のユーザーデータへのアクセスや操作を行うため、`Basic staff`や`Advanced tutor`などの特定のロールを必要とします。

## ユーザー関連の記録を管理するためのエンドポイント（API 2.0）

### I. ユーザーアカウントおよび管理記録 (`users`, `user_candidatures`, `alumnized_users`, `closes`)

ユーザーアカウント自体の作成、更新、および管理ステータス（休学/卒業など）を扱うエンドポイントです。

| エンドポイントリソース | 目的 | 操作 (CRUD/カスタム) | 詳細なエンドポイント/機能 | 必要なロール (主なもの) |
| :--- | :--- | :--- | :--- | :--- |
| **users** | ユーザーの基本情報管理 | GET, POST, PUT/PATCH | **ユーザー情報の取得:** `/v2/users`、`/v2/users/:id`。**ユーザーの作成/更新:** `/v2/users`、`/v2/users/:id` (ユーザーの基本情報、**cursus_users**、**languages_users**、**user_candidature**の属性をネストして更新可能)。 | Advanced tutor |
| **users** | 修正点 (Correction Points) の管理 | POST, DELETE | **修正点の追加:** `/v2/users/:id/correction_points/add`。**修正点の削除:** `/v2/users/:id/correction_points/remove`。 | Advanced tutor |
| **user_candidatures** | ユーザーの出願詳細情報 | GET, POST, PUT/PATCH | **出願情報の取得:** `/v2/user_candidatures`、`/v2/users/:user_id/user_candidature`。**出願情報の作成/更新:** `/v2/user_candidatures`、`/v2/users/:user_id/user_candidature`。 | Basic staff / Advanced staff, Advanced tutor |
| **alumnized_users** | 卒業生（Alumni）情報 | GET | **卒業生の一覧取得:** `/v2/alumnized_users` (特定のキャンパスIDが必要)。 | Advanced tutor |
| **users (Alumnization)** | 卒業ステータスの変更 | POST | **Alumnize（卒業生化）:** `/v2/users/:id/alumnize`。**Dealumnize（卒業生ステータス解除）:** `/v2/users/:id/dealumnize`。 | 42network |
| **closes** | ユーザーの休学/クローズ記録 | GET, POST, DELETE | **クローズ記録の取得:** `/v2/closes`、`/v2/users/:user_id/closes`。**クローズ記録の削除:** `/v2/closes/:id`。 | Basic staff / Advanced staff |
| **correction\_point\_historics** | 修正点の履歴 | GET | **ユーザーの修正点履歴の取得:** `/v2/users/:user_id/correction_point_historics`。 | (権限指定なし/ユーザー紐づき) |
| **mailings** | ユーザーに送信されたメール記録 | GET | **ユーザーのメール記録の取得:** `/v2/users/:user_id/mailings`。 | Advanced staff, Advanced tutor |
| **notes** | ユーザーに関するメモ | GET | **ユーザーのメモの取得:** `/v2/users/:user_id/notes`。 | Notes manager, Advanced notes manager |

---

### II. 学業および進捗関連記録 (`cursus`, `projects`, `exams`, `experiences`)

ユーザーの学習進捗、コース登録、評価に関するエンドポイントです。

| エンドポイントリソース | 目的 | 操作 (CRUD/カスタム) | 詳細なエンドポイント/機能 | 必要なロール (主なもの) |
| :--- | :--- | :--- | :--- | :--- |
| **cursus_users** | ユーザーのコース登録情報（レベル、成績など） | GET, POST, PUT/PATCH, DELETE | **登録情報の取得:** `/v2/cursus_users`、`/v2/users/:user_id/cursus_users`。**登録の作成/更新/削除:** `/v2/cursus_users`、`/v2/cursus_users/:id`。 | Advanced tutor |
| **projects_users** | ユーザーのプロジェクト進捗状況 | GET, POST, PUT/PATCH, DELETE | **進捗状況の取得:** `/v2/projects_users/:id`。**進捗状況の作成:** `/v2/projects_users`、`/v2/projects/:project_id/register`。**進捗状況の更新:** `/v2/projects_users/:id`。**再挑戦:** `/v2/projects_users/:id/retry`。 | Advanced tutor, Advanced staff |
| **exams** | 試験のスケジュールとユーザーへの関連付け | GET, POST, PUT/PATCH, DELETE | **ユーザー関連の試験の取得:** `/v2/users/:user_id/exams`。**試験の作成/更新/削除:** `/v2/exams`、`/v2/exams/:id`。 | Advanced tutor |
| **exams_users** | 試験へのユーザー登録 | GET, POST, DELETE, PUT/PATCH | **試験登録の取得:** `/v2/exams/:exam_id/exams_users`。**試験登録の作成:** `/v2/exams/:exam_id/exams_users`。**試験登録の削除:** `/v2/exams/:exam_id/exams_users/:id`。**更新:** `/v2/exams_users/:id`。 | Advanced tutor / Basic staff |
| **experiences** | ユーザーが獲得したスキル経験値 | GET, PUT/PATCH | **ユーザーの経験値の取得:** `/v2/users/:user_id/experiences`。**経験値の更新:** `/v2/experiences/:id`。 | Basic staff / Advanced tutor |
| **achievements_users** | ユーザーが達成したアチーブメント | GET | **達成者の一覧取得:** `/v2/achievements_users`、`/v2/achievements/:achievement_id/users`。 | (権限指定なし/フィルタリング可能) |
| **quests_users** | ユーザーのクエスト進捗状況 | GET, POST, PUT/PATCH, DELETE | **クエスト進捗の取得:** `/v2/quests_users/:id`、`/v2/users/:user_id/quests`。**作成/更新/削除:** `/v2/quests_users` (詳細はソースにないがCRUD操作あり)。 | Advanced tutor |

---

### III. 認定、資格、専門知識 (`accreditations`, `certificates`, `expertises`, `titles`)

ユーザーの公式な資格、認定、および専門知識に関するエンドポイントです。

| エンドポイントリソース | 目的 | 操作 (CRUD) | 詳細なエンドポイント/機能 | 必要なロール (主なもの) |
| :--- | :--- | :--- | :--- | :--- |
| **accreditations** | ユーザーの認定記録 | GET, POST, PUT/PATCH, DELETE | **認定記録の取得:** `/v2/accreditations`、`/v2/accreditations/:id`。**作成/更新/削除:** `/v2/accreditations`、`/v2/accreditations/:id`。 | Basic tutor, Basic staff |
| **certificates** | 認定証の定義 | GET | **認定証の取得:** `/v2/certificates`、`/v2/certificates/:id`。 | Advanced tutor |
| **certificates_users** | ユーザーへの認定証付与記録 | GET, DELETE | **ユーザー認定の取得:** `/v2/certificates/:certificate_id/certificates_users`、`/v2/users/:user_id/certificates_users`。**削除:** `/v2/certificates_users/:id`。 | Advanced tutor |
| **expertises_users** | ユーザーの専門知識への関連付け | GET, POST, PUT/PATCH, DELETE | **専門知識関連の取得:** `/v2/users/:user_id/expertises_users`。**作成/更新/削除:** `/v2/expertises_users`。 | Advanced tutor (またはプロファイルスコープを持つリソースオーナー) |
| **titles_users** | ユーザーが保有する称号 | GET, POST, PUT/PATCH | **称号付与記録の取得:** `/v2/users/:user_id/titles_users`。**作成/更新:** `/v2/titles_users`。 | Advanced tutor |

### IV. インターンシップとロケーション

ユーザーの職業的記録と物理的な所在地の管理です。

| エンドポイントリソース | 目的 | 操作 (CRUD) | 詳細なエンドポイント/機能 | 必要なロール (主なもの) |
| :--- | :--- | :--- | :--- | :--- |
| **internships** | インターンシップ情報 | GET, POST, PUT/PATCH, DELETE | **ユーザーのインターンシップ取得:** `/v2/users/:user_id/internships`。**作成/更新/削除:** `/v2/internships`、`/v2/internships/:id`。 | Companies manager |
| **amendments** | インターンシップの修正記録 | GET | **ユーザーの修正記録の取得:** `/v2/users/:user_id/amendments`。 | (権限指定なし) |
| **locations** | ユーザーのキャンパス内での位置情報 | GET, POST, PUT/PATCH | **ユーザーの位置情報取得:** `/v2/users/:user_id/locations`。**位置情報の作成/更新:** `/v2/locations`、`/v2/locations/:id`。 | Basic staff / Advanced staff |

**補足:**
多くの機密性の高い管理エンドポイント（作成、更新、削除など）は、セキュリティのため、`vpn_key`アイコンで示されており、通常、`Advanced tutor`や`Basic staff`/`Advanced Staff`などのスタッフロールが必要です。

ご提示いただいたAPIドキュメントの抜粋に基づき、ユーザーの学業、管理、および認定記録に関連する主要なエンドポイントのうち、データの作成（POST）や更新（PATCH/PUT）、削除（DELETE）に必要な**具体的なペイロード（パラメータ）**を以下にまとめます。

これらの操作のほとんどは、管理者権限（`Advanced tutor`, `Basic staff`など）または特定のスコープが必要となる点にご注意ください。

---

## 42 API 2.0 ユーザー関連エンティティのペイロード詳細

### 1. 認定・資格関連のペイロード

#### A. Accreditations (認定記録) `/v2/accreditations`

| エンドポイント | メソッド | ペイロード (`accreditation`) | 必須ロール |
| :--- | :--- | :--- | :--- |
| `/v2/accreditations` | POST (作成) | 詳細なパラメータは提示されていませんが、作成アクションは存在します。 | |

#### B. Certificates Users (ユーザーへの認定証付与) `/v2/certificates_users`

| エンドポイント | メソッド | パラメータ | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/certificates_users/:id` | DELETE (削除) | **id** (必須, String) | 削除対象のID。| Advanced tutor |
| | | `certificates_user[certificate_id]` (オプション, Fixnum) | 認定証ID。特定のユーザーのスコープ内で一意である必要。 | |
| | | `certificates_user[user_id]` (オプション, Fixnum) | ユーザーID。 | |
| | | `certificates_user[certified_at]` (オプション, String) | 認定された日時。 | |

### 2. 管理・ステータス関連のペイロード

#### A. Closes (休学・退学記録) `/v2/closes`

| エンドポイント | メソッド | ペイロード (`close`) | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/closes` `/v2/users/:user_id/closes` | POST (作成) | `close[user_id]` (必須) | 休止されるユーザーID (Fixnum)。 | Basic staff |
| | | `close[closer_id]` (オプション, Fixnum) | 処理を行ったスタッフID。 | Basic staff |
| | | `close[kind]` (オプション, String) | 休止の種類 (`agu`, `other`, `deserter`, `black_hole`, `serious_misconduct`など)。 | Basic staff |
| | | `close[reason]` (オプション, String) | 理由。 | Basic staff |
| | | `close[end_at]` (オプション, DateTime) | 終了日時。 | Basic staff |
| `/v2/closes/:id` | PATCH/PUT (更新) | `close[community_services_attributes]` (オプション, Array) | 関連するコミュニティサービス属性の配列。サービス期間は7200, 14400, 28800秒のいずれかである必要がある。| Basic staff |
| `/v2/closes/:id/close` `/v2/closes/:id/unclose` | PATCH/PUT (状態変更) | `id` (必須, String) | クローズID。 | Basic staff |

#### B. Notes (ユーザーへのメモ) `/v2/notes`

| エンドポイント | メソッド | ペイロード (`note`) | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/notes` | POST (作成) | `note[user_id]` (必須, Fixnum) | メモを受け取るユーザーID。 | Notes manager, Advanced notes manager |
| | | `note[subject]` (オプション, String) | 件名。 | Notes manager, Advanced notes manager |
| | | `note[content]` (オプション, String) | 内容。 | Notes manager, Advanced notes manager |
| | | `note[kind]` (オプション, String) | 種別 (`manual`, `black_hole`, `school_record`のいずれか)。 | Notes manager, Advanced notes manager |
| `/v2/notes/:id` | PATCH/PUT (更新) | `note[approved_at]` (オプション, DateTime) | 承認日時（Advanced Note managerのみが作成/編集可能）。 | Notes manager, Advanced notes manager |
| `/v2/notes/:id` | DELETE (削除) | **id** (必須, String) | 削除対象のID。| Notes manager, Advanced notes manager |

#### C. User Candidatures (出願情報) `/v2/user_candidatures`

| エンドポイント | メソッド | パラメータ | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/user_candidatures/:id` `/v2/users/:user_id/user_candidature` | PATCH/PUT (更新) | ペイロードの詳細は提示されていません。 | | Basic staff |

### 3. 学業・プロジェクト進捗関連のペイロード

#### A. Projects Users (プロジェクト進捗) `/v2/projects_users`

| エンドポイント | メソッド | ペイロード | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/projects/:project_id/projects_users` | POST (作成) | 詳細なパラメータは提示されていません。 | プロジェクトにユーザーを登録。| Advanced tutor |
| `/v2/projects_users/reset` | DELETE (リセット) | `user_id` (必須, Fixnum), `project_id` (必須, Fixnum) | 指定したユーザーのプロジェクトをリセット。 | 42network |
| `/v2/projects_users/:id/compile` | PATCH/PUT (コンパイル) | `project_users_id` (必須, Fixnum) | プロジェクトユーザーをコンパイル。 | Advanced tutor |
| `/v2/projects_users/:id/retry` | POST (再挑戦) | `id` (必須, Fixnum) | プロジェクトの再挑戦。`force` (`true`/`false`) オプションで強制再挑戦が可能。| 権限を持つリソースオーナー / Advanced tutor |

#### B. Experiences (経験値) `/v2/experiences`

| エンドポイント | メソッド | ペイロード | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/experiences/:id` | DELETE (削除) | **id** (必須, String) | 経験を削除。 | Advanced tutor |

### 4. 専門知識・称号関連のペイロード

#### A. Expertises Users (ユーザーの専門知識) `/v2/expertises_users`

| エンドポイント | メソッド | ペイロード (`expertises_user`) | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/expertises_users` | POST (作成) | `expertise_id` (必須) や `user_id` (必須) などがネストされる可能性がある。| 専門知識をユーザーに関連付ける。| 権限を持つリソースオーナー / Advanced tutor |
| `/v2/expertises_users/:id` | DELETE (削除) | **id** (必須, String) | 専門知識の関連付けを削除。| 権限を持つリソースオーナー / Advanced tutor |
| `/v2/expertises_users/:id` | PATCH/PUT (更新) | 更新可能なパラメータの詳細は提示されていません。| | 権限を持つリソースオーナー / Advanced tutor |

#### B. Titles Users (ユーザーの称号) `/v2/titles_users`

| エンドポイント | メソッド | ペイロード | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/titles_users` | POST (作成) | 詳細なパラメータは提示されていません。| ユーザーに称号を付与。| Advanced tutor |
| `/v2/titles_users/:id` | DELETE (削除) | **id** (必須, String) | 称号の付与記録を削除。| Advanced tutor |

### 5. その他の操作（管理、トランザクション、イベント）

#### A. Endpoints (キャンパス認証同期設定) `/v2/endpoints`

| エンドポイント | メソッド | ペイロード (`endpoint`) | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/endpoints` | POST (作成) | `endpoint[url]` (必須, String), `endpoint[secret]` (オプション, String)。 | 新しいエンドポイントを作成。| Basic staff |
| `/v2/endpoints/:id` | PATCH/PUT (更新) | `endpoint[url]` (オプション, String), `endpoint[secret]` (オプション, String)。 | エンドポイントを更新。 | Advanced staff |
| `/v2/endpoints/:id/callback` | POST (コールバック) | `url` (必須, String), `user_id` (必須, Integer), `initial_data` (必須, Hash), `response_data` (必須, Hash)。 | エンドポイントのコールバック操作。| 42network |

#### B. Mailings (メール送信) `/v2/mailings`

| エンドポイント | メソッド | ペイロード (`mailing`) | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/mailings` | POST (作成) | `mailing[subject]`, `mailing[content]`, `mailing[from]` (すべて必須, String)。`mailing[to]`, `mailing[cc]`, `mailing[bcc]` (オプション, Array)。 | 認証済みのメールを作成/送信。 | Advanced tutor, Advanced staff |
| `/v2/mailings/:id` | DELETE (削除) | **id** (必須, String) | メーリングを削除。 | Advanced staff, Advanced tutor |

#### C. Transactions (Altarian Dollarsのトランザクション) `/v2/transactions`

| エンドポイント | メソッド | ペイロード (`transaction`) | 説明 | 必須ロール |
| :--- | :--- | :--- | :--- | :--- |
| `/v2/transactions` | POST (作成) | 詳細なパラメータは提示されていません。| トランザクションを作成。| Transactions manager |
| `/v2/transactions/:id` | PATCH/PUT (更新) | `transaction[value]` (オプション, Fixnum), `transaction[user_id]` (オプション, Fixnum), `transaction[reason]` (オプション, String)。| トランザクションを更新。 | Transactions manager |

### まとめ: ペイロードの構造に関する洞察

API 2.0ドキュメント全体を通して、リソースの作成（POST）および更新（PATCH/PUT）操作では、**リソース名（単数形）をキーとするネストされたハッシュ**がペイロードとして使用される傾向があります。

*   **例（作成）:** `/v2/closes` への POST リクエストでは、`{ "close": { "user_id": 123, "reason": "..." } }` のような形式が期待されます。
*   **例外:** 修正点（Correction Points）の追加/削除など、特定のカスタムアクションや単純なリレーションの作成/削除では、URLパスまたはクエリパラメータにIDを渡すのみでペイロードが不要な場合があります。

ペイロード内の必須フィールドは、リソースによって異なり、特に**リレーションシップの確立（例: `internship_id`、`user_id`）やコアデータの定義（例: `name`, `content`, `kind`）**に重点が置かれています。


## APIアプリケーションのレート制限 (Rate Limit) に関する詳細ドキュメント

### 1. レート制限の定義と場所

レート制限とは、APIリソースの安定性を保つために、アプリケーションが一定期間内に行えるリクエスト数を制限するメカニズムです。

#### 1.1 `rate_limit` フィールド

個々のアプリケーションに設定された具体的なレート制限値は、そのアプリケーションの情報を取得するAPIコールによって確認できます。

*   **エンドポイント:** `/v2/apps/:id`
*   **レスポンス内容:** アプリケーションのJSONレスポンスには、`"rate_limit"`というフィールドが含まれます。
    *   **観測された値の例:** 複数のアプリケーションの例において、`"rate_limit"`の値が **1800** であることが確認されています。

### 2. レート制限の標準的な制限（会話履歴に基づく）

以前の会話で提供された情報に基づくと、標準的なアプリケーションには以下の制限が適用されます。

*   **デフォルトの制限:** 1秒あたり2リクエスト、および1時間あたり1200リクエスト。
    *   *注: 上記のデフォルト制限は会話履歴に基づきますが、APIレスポンスの例では「1800」という値が確認されています。*

### 3. レート制限の免除：特権ロール

特定の「ロール（役割）」が付与されたアプリケーションは、標準的なレート制限の対象外となります。
※ ただしアプリケーション開発においてはロール付与されていない前提で組み上げる必要があります。

#### 3.1 Official App (公式アプリ)

*   **ロールID:** 16
*   **ロール名:** Official App
*   **説明:** このロールを持つアプリケーションは、「**Approved application without rate limits**」（レート制限なしの承認済みアプリケーション）として明確に記述されています。

この「Official App」ロールが付与されているアプリケーションは、他のロール（例：Basic Staff、Advanced Staff、Intrateamなど）と共に、`/v2/apps/:id`エンドポイントのレスポンス内で確認できます。

### 4. まとめ：レート制限の目的

レート制限は、APIの健全性を維持するために不可欠です。しかし、「Official App」のように、高い信頼性や統合が必要な基幹アプリケーションに対しては、その必要性に応じて制限が免除される仕組みが導入されています。これにより、サービス提供の継続性を確保しながら、不正な利用や過剰な負荷を防いでいます。
