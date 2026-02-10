# AWS / Strands Agent / LINE Bot 開発ナレッジ

このプロジェクトで得た学び・ノウハウをまとめる。

---

## 1. 全体アーキテクチャ

| レイヤー | 技術 | 役割 |
|---------|------|------|
| フロントエンド | LINE Messaging API | ユーザーとのチャット UI |
| Webhook 受信 | API Gateway + Lambda | LINE イベントを受信・ルーティング |
| AI エージェント | Bedrock AgentCore Runtime | Strands Agent をホスト |
| LLM | Claude Sonnet 4.5 (Bedrock) | 自然言語応答を生成 |
| IaC | AWS CDK (TypeScript) | 全リソースをコード管理 |

### ローカル vs AWS の違い

| 項目 | ローカル | AWS |
|------|---------|-----|
| Webhook 受信 | FastAPI (port 8000) + ngrok | API Gateway + Lambda |
| Agent 呼び出し | HTTP `localhost:8080/invocations` | boto3 `invoke_agent_runtime` |
| 切り替え方法 | `AGENTCORE_RUNTIME_ENDPOINT` が空かどうか | CDK が `AGENT_RUNTIME_ARN` を設定 |
| Agent 起動 | `python agent/main.py` | AgentCore Runtime (Docker コンテナ) |

---

## 2. Strands Agent の書き方

| 項目 | 内容 |
|------|------|
| 最小構成 | `BedrockModel` + `Agent` + `BedrockAgentCoreApp` の 3 つ |
| エントリポイント | `@app.entrypoint` デコレータで関数を登録 |
| Agent 呼び出し | `agent(prompt)` で呼ぶだけ。戻り値を `str()` で文字列化 |
| ストリーミング | `BedrockModel(streaming=True)` で有効化 |
| System Prompt | `Agent(system_prompt=...)` で設定 |
| ローカル起動 | `app.run()` で HTTP サーバーが起動 (port 8080) |

### Agent コードのテンプレート

```python
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload: dict) -> dict:
    model = BedrockModel(model_id="...", streaming=True)
    agent = Agent(model=model, system_prompt="...")
    result = agent(payload["prompt"])
    return {"result": str(result), "status": "success"}
```

---

## 3. LINE Bot SDK v3 のポイント

| 項目 | 内容 |
|------|------|
| SDK バージョン | `line-bot-sdk>=3.11.0` (v3 系) |
| Webhook パース | `WebhookParser(channel_secret).parse(body, signature)` |
| 署名検証 | SDK が自動で行い、失敗時は `InvalidSignatureError` を raise |
| メッセージ判定 | `isinstance(ev, MessageEvent) and isinstance(ev.message, TextMessageContent)` |
| Reply vs Push | Reply: 無料・token 必要・30秒制限 / Push: 有料・user_id で送信 |
| ローディング | `ShowLoadingAnimationRequest(chatId=user_id, loadingSeconds=60)` |
| API クライアント | `with ApiClient(configuration) as api_client:` で context manager 使用 |

### Reply Token のタイムアウト対策

```python
TIMEOUT_SECONDS = 55  # Lambda 60s の 5s 手前

elapsed = time.time() - start_time
if elapsed < TIMEOUT_SECONDS:
    reply_message(reply_token, text)  # 無料
else:
    push_message(user_id, text)       # フォールバック
```

---

## 4. CDK (TypeScript) のポイント

| 項目 | 内容 |
|------|------|
| AgentCore 構成 | `@aws-cdk/aws-bedrock-agentcore-alpha` パッケージ (alpha 版) |
| コンテナ指定 | `AgentRuntimeArtifact.fromAsset("./agent")` で Dockerfile を自動ビルド |
| Lambda Layer | `Code.fromAsset` + `bundling` で Docker 内 pip install |
| ARM64 指定 | Lambda・Layer 両方で `Architecture.ARM_64` を指定 (コスト削減) |
| 環境変数の渡し方 | `process.env.XXX` で CDK 実行時の環境変数を Lambda に渡す |
| 権限付与 | `runtime.grantInvokeRuntime(lambda)` で IAM ポリシーを自動設定 |
| デプロイコマンド | `AWS_PROFILE=line-agent npx cdk deploy` |

### Lambda Layer の bundling 設定

```typescript
bundling: {
  image: lambda.Runtime.PYTHON_3_13.bundlingImage,
  platform: "linux/arm64",
  command: ["bash", "-c",
    "pip install -r requirements.txt -t /asset-output/python " +
    "--platform manylinux2014_aarch64 --only-binary=:all: --python-version 3.13"
  ],
}
```

`--platform manylinux2014_aarch64` と `--only-binary=:all:` が重要。ないと x86 バイナリが混入する。

---

## 5. IAM 設計

| ロール | 付与先 | 権限 |
|--------|--------|------|
| ロール 1 | Lambda | `bedrock-agentcore:InvokeAgentRuntime` |
| ロール 2 | AgentCore Runtime | `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` |

- CDK が自動作成。手動設定不要
- Bedrock モデル権限の Resource ARN は `arn:aws:bedrock:*::foundation-model/anthropic.*` のようにワイルドカード指定

### デプロイ用 IAM ユーザー

| 項目 | 値 |
|------|---|
| ユーザー名 | `line-agent-deployer` |
| AWS CLI プロファイル | `line-agent` |
| ポリシー | `AdministratorAccess` (本番では絞るべき) |

---

## 6. テストのハマりポイント

| 問題 | 原因 | 解決策 |
|------|------|--------|
| `from lambda.index import ...` が SyntaxError | `lambda` は Python 予約語 | `importlib` + `sys.modules` で動的登録。テストでは `sys.modules["lambda.index"]` で参照 |
| `except InvalidSignatureError` が mock をキャッチしない | MagicMock は Exception を継承しない | `conftest.py` で実際の Exception サブクラスをスタブとして定義 |
| `isinstance(mock, MessageEvent)` が False | MagicMock は任意クラスのインスタンスにならない | スタブクラスの実インスタンスを作成して渡す |
| `@app.entrypoint` が関数を MagicMock に置き換える | デコレータが mock の戻り値を返す | `_mock_app_instance.entrypoint = lambda fn: fn` で pass-through に |
| `ShowLoadingAnimationRequest().chat_id` が MagicMock | コンストラクタが mock なので属性も mock | 実クラスのスタブを定義し、`__init__` で `setattr` する |
| `patch("lambda.index.xxx")` が効かない | 文字列パスでのパッチが importlib 登録モジュールに届かない | `patch.object(idx, "xxx")` でモジュールオブジェクトを直接パッチ |

### テストでの import パターン

```python
import sys
# conftest.py が sys.modules に登録済み
idx = sys.modules["lambda.index"]

# パッチは patch.object を使う
with patch.object(idx, "parser") as mock_parser:
    result = idx.lambda_handler(event, None)
```

---

## 7. ローカル開発フロー

| ステップ | コマンド | ポート |
|---------|---------|--------|
| 1. General Agent 起動 | `cd agent && python main.py` | 8080 |
| 2. Calendar Agent 起動 | `cd agent && python calendar_agent.py --port 8081` | 8081 |
| 3. Lambda 起動 | `cd lambda && python index.py` | 8000 |
| 4. ngrok | `ngrok http 8000` | ngrok URL |
| 5. LINE 設定 | Console で Webhook URL + LIFF エンドポイント URL を設定 | - |
| 6. GCP 設定 | OAuth2 リダイレクト URI を ngrok URL に更新 | - |

### `.env.local` で環境切り替え

- ローカル: `AGENTCORE_RUNTIME_ENDPOINT=http://localhost:8080` → HTTP 直接呼び出し
- AWS: 未設定 (空) → boto3 + ARN 経由
- コードの `if AGENTCORE_RUNTIME_ENDPOINT:` で自動分岐

---

## 8. デプロイ関連

### 環境変数の渡し方

CDK スタック (`line-agent-stack.ts`) は `process.env.*` でシェル環境変数を直接参照する。
dotenv は使っていないので、`.env.local` から読み込む場合は `set -a && source .env.local && set +a` が必要。

### デプロイ手順

```bash
cd infra

# 1. .env.local の環境変数をシェルに読み込み
set -a && source ../.env.local && set +a

# 2. Bootstrap (初回のみ)
npx cdk bootstrap

# 3. 差分確認 (推奨)
npx cdk diff

# 4. デプロイ
npx cdk deploy --require-approval never
```

AWS CLI プロファイルを使う場合:
```bash
export AWS_PROFILE=line-agent
```

### コマンド一覧

| 項目 | コマンド |
|------|---------|
| 環境変数読み込み | `set -a && source ../.env.local && set +a` |
| Bootstrap (初回のみ) | `npx cdk bootstrap` |
| デプロイ | `npx cdk deploy --require-approval never` |
| 差分確認 | `npx cdk diff` |
| スタック削除 | `npx cdk destroy` |

### デプロイ時の注意

| 注意点 | 詳細 |
|--------|------|
| 環境変数必須 | `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_STATE_SECRET`, `TAVILY_API_KEY` が必要 |
| Docker 必須 | AgentCore Runtime のコンテナビルドと Lambda Layer のビルドに Docker が必要 |
| ARM64 | Lambda と Layer は ARM64。ローカルの Docker が ARM エミュレーションに対応している必要あり (Apple Silicon は OK) |
| logRetention 非推奨 | CDK の `logRetention` は deprecated。`logGroup` に移行推奨 (動作には影響なし) |

### デプロイ後の設定

| 項目 | 設定場所 | 値 |
|------|---------|---|
| Webhook URL | LINE Developer Console | `https://<api-gw>.execute-api.<region>.amazonaws.com/prod/callback` |
| OAuth Redirect URI | GCP Console + `.env.local` | `https://<api-gw>.execute-api.<region>.amazonaws.com/prod/oauth/callback` |
| LIFF Endpoint URL | LINE Developer Console | LIFF 用ページの URL (本番 or ngrok) |

### DynamoDB テーブルの CDK インポート

**問題**: DynamoDB テーブルを CDK の外で先に作成した場合、`cdk deploy` で
`Resource of type 'AWS::DynamoDB::Table' with identifier 'xxx' already exists` エラーになる。

CDK は自分が管理していないリソースを新規作成しようとして、同名テーブルが既にあるため失敗する。

**解決策**: `cdk import` で既存リソースを CDK 管理下に取り込む。

```bash
# 1. マッピングファイルを作成
cat > import-map.json << 'EOF'
{
  "GoogleOAuthTokensD18E1AC9": {
    "TableName": "GoogleOAuthTokens"
  },
  "UserSessionState3B06873E": {
    "TableName": "UserSessionState"
  }
}
EOF

# 2. インポート実行
npx cdk import --resource-mapping import-map.json --force

# 3. その後 cdk deploy で残りの変更を適用
npx cdk deploy --require-approval never
```

**注意点**:
- マッピングファイルのキー (`GoogleOAuthTokensD18E1AC9` 等) は CDK が生成する論理 ID。`cdk synth` の出力や `cdk diff` のエラーメッセージから確認できる
- `--force` は import 時に他の変更差分を無視するオプション。import 後に `cdk deploy` で残りを適用する
- データは消えない。CDK の管理下に入るだけ

### 本番環境情報 (2026-02-11 時点)

| リソース | 値 |
|---|---|
| API Gateway | `https://2uco1x3zrk.execute-api.ap-northeast-1.amazonaws.com/prod/` |
| Webhook URL | `.../prod/callback` |
| OAuth Callback | `.../prod/oauth/callback` |
| Router Agent | `lineAssistantAgent-RyWqz746z6` |
| Calendar Agent | `calendarAgent-q4mELzB9a6` |
| Gmail Agent | `gmailAgent-Owua548TiA` |
| リージョン | `ap-northeast-1` |

---

## 9. コスト意識

| リソース | 課金 | 備考 |
|---------|------|------|
| API Gateway | リクエスト数課金 | 100万リクエストあたり $3.50 |
| Lambda | 実行時間 + メモリ | 512MB / 60s。ARM64 で x86 比 20% 安い |
| AgentCore Runtime | コンテナ稼働時間 | 使わない時は `cdk destroy` で削除推奨 |
| Bedrock (Claude) | トークン数課金 | input/output で異なる。最もコストが高い部分 |
| LINE Push Message | 1000通/月まで無料 | それ以上は有料プラン |
| CloudWatch Logs | 保存量 + 取り込み量 | 1週間保持に設定済み |

---

## 10. Google Calendar Agent

### アーキテクチャ

| 項目 | 内容 |
|------|------|
| 実行形態 | General Agent とは別プロセスで起動 (port 8081) |
| エントリポイント | `agent/calendar_agent.py` |
| Docker | `agent/Dockerfile.calendar` |
| ツール定義 | `agent/tools/google_calendar.py` (@tool デコレータで 7 ツール登録) |
| Agent → Lambda 連携 | Agent が JSON レスポンスを返し、Lambda が type フィールドで Flex Message を構築 |

### 7 つの Calendar ツール

| ツール名 | 説明 |
|---------|------|
| `list_events` | 日付範囲の予定一覧を取得 |
| `get_event` | 予定の詳細を取得 |
| `create_event` | 新規予定を作成 |
| `update_event` | 予定を更新 |
| `delete_event` | 予定を削除 |
| `invite_attendees` | 参加者を招待 |
| `get_free_busy` | 空き時間を取得 (カルーセルの色分け用) |

### モジュールレベル credentials パターン

Calendar ツールは Google API のクレデンシャルを必要とするが、Agent のツール関数はシグネチャが固定されている。
解決策: モジュールレベル変数 + `set_credentials()` 関数で、ツール呼び出し前にクレデンシャルを注入する。

```python
# agent/tools/google_calendar.py
_credentials = None

def set_credentials(creds):
    global _credentials
    _credentials = creds

@tool
def list_events(start_date: str, end_date: str) -> str:
    # _credentials を使って Google Calendar API を呼び出し
    ...
```

### JSON レスポンス契約

Agent と Lambda 間のレスポンスは `type` フィールドで種別を判定する。

| type | 用途 | 主要フィールド |
|------|------|---------------|
| `calendar_events` | 予定一覧 | `events[]` (summary, start, end, id) |
| `date_selection` | 日付選択 | `dates[]` (date, is_available) |
| `event_created` | 予定作成完了 | `event` (summary, start, end) |
| `event_updated` | 予定更新完了 | `event` (summary, start, end) |
| `event_deleted` | 予定削除完了 | `event_id` |
| `free_busy` | 空き時間 | `busy[]` (start, end) |

---

## 11. OAuth2 フロー (Google)

### フロー全体像

```
LINE User → LIFF リンクタップ → LIFF App → liff.openWindow(external:true)
→ Google OAuth 同意画面 (外部ブラウザ) → 認証・同意
→ GET /oauth/callback → OAuth Callback Lambda → DynamoDB にトークン保存
→ ユーザーに「連携完了」メッセージ表示
```

### セキュリティ: HMAC 署名付き state パラメータ

| 項目 | 内容 |
|------|------|
| state 構成 | `user_id:timestamp:hmac_signature` |
| 署名アルゴリズム | HMAC-SHA256 (`OAUTH_STATE_SECRET` を鍵として使用) |
| 検証 | コールバック時に state を分解し、HMAC を再計算して一致を確認 |
| タイムスタンプ | リプレイ攻撃対策 (有効期限を設定可能) |

### トークン管理 (lambda/google_auth.py)

| 関数 | 説明 |
|------|------|
| `save_tokens(user_id, tokens)` | DynamoDB にアクセストークン + リフレッシュトークンを保存 |
| `get_tokens(user_id)` | DynamoDB からトークンを取得 |
| `get_google_credentials(user_id)` | トークンを取得し、期限切れの場合は自動リフレッシュ |
| `delete_tokens(user_id)` | トークンを削除 |
| `encode_state(user_id)` | HMAC 署名付き state を生成 |
| `decode_state(state)` | state を検証・デコードし user_id を返す |

### Google の WebView ブロック問題

Google は `disallowed_useragent` ポリシーにより、LINE アプリ内 WebView での OAuth 認証をブロックする。

**解決策**: LIFF App で `liff.openWindow({ url: oauthUrl, external: true })` を使い、外部ブラウザ (Safari/Chrome) で OAuth 画面を開く。

---

## 12. Flex Messages & カルーセル UI

### 5 つの Flex Message ビルダー

| モジュール | 説明 | 主な要素 |
|-----------|------|---------|
| `oauth_link.py` | OAuth 連携リンクカード | 「Google で連携する」ボタン (LIFF URL) |
| `calendar_carousel.py` | 予定一覧カルーセル | イベントカード + 詳細・編集・削除ボタン |
| `date_picker.py` | 日付選択カルーセル | 週単位バブル、空き=緑 / 埋まり=グレー |
| `time_picker.py` | 時間帯選択カルーセル | 午前・午後セクション、空き=緑 / 埋まり=グレー |
| `event_confirm.py` | 作成/削除 確認画面 | 日時・タイトル表示 + タイトル編集ボタン + 送信ボタン |

### Flex Message でタップ不可のボタン風要素を作る

LINE Flex Message の `button` は `action` が必須で、外すことができない。
そのため、グレー表示してもタップすると postback が発火してしまう。

**解決策**: busy なスロットは `button` ではなく `box` + `text` で同じ見た目を再現する。
`box` には `action` がないのでタップしても何も起きない。

```json
{
  "type": "box",
  "layout": "vertical",
  "contents": [
    {
      "type": "text",
      "text": "13:00 - 14:00",
      "align": "center",
      "color": "#FFFFFF",
      "size": "sm"
    }
  ],
  "backgroundColor": "#CCCCCC",
  "cornerRadius": "md",
  "height": "40px",
  "justifyContent": "center",
  "margin": "sm"
}
```

この手法は日付ピッカー・時間帯ピッカーの両方で使用している。

### デュアル入力パターン

| ユーザー入力 | 処理 | 例 |
|------------|------|---|
| 具体的な自然言語 | Agent が直接処理 | 「明日の14時に会議を作成して」 |
| 曖昧な指示 | カルーセルで段階的に選択 | 「予定を作りたい」→ 日付選択 → 時間選択 → 確認 |

### Postback イベント処理

ボタンタップ時のアクションは Postback イベントとして Lambda に送信される。

| action | 処理内容 |
|--------|---------|
| `select_date` | 選択された日付を保存し、時間帯選択カルーセルを返信 |
| `select_time` | 選択された時間を保存し、確認画面を返信 |
| `confirm_create` | Calendar Agent で予定を作成 |
| `confirm_delete` | Calendar Agent で予定を削除 |
| `edit_title` | タイトル入力を促すテキストを返信 |
| `view_detail` | 予定の詳細を表示 |

### ユーザーセッション状態

カルーセルの段階的な入力を管理するため、DynamoDB (`UserSessionState`) にセッション状態を保存する。

| 項目 | 内容 |
|------|------|
| テーブル | `UserSessionState` |
| パーティションキー | `user_id` (LINE ユーザー ID) |
| TTL | 10 分 (操作途中で放置された場合に自動削除) |
| 保存データ | 選択済みの日付、時間、タイトルなどの操作途中データ |

---

## 13. LIFF 連携

### LIFF (LINE Front-end Framework) の役割

Google が LINE アプリ内 WebView での OAuth 認証をブロックするため、LIFF を中継として使用し、外部ブラウザで OAuth 画面を開く。

### LIFF SDK の処理フロー

```
1. LIFF 初期化: liff.init({ liffId })
2. プロフィール取得: liff.getProfile() → userId
3. OAuth URL 取得: fetch("/api/oauth-url?user_id=xxx")
4. 外部ブラウザ起動: liff.openWindow({ url: oauthUrl, external: true })
5. LIFF 終了: liff.closeWindow()
```

### 注意点

| 項目 | 内容 |
|------|------|
| LIFF_ID | `.env.local` と CDK 環境変数の両方に設定が必要 |
| エンドポイント URL | LINE Developer Console で設定する URL は ngrok ドメイン (ローカル) or 本番 URL と一致させる |
| ngrok 無料枠の制限 | `fetch` 時に `ngrok-skip-browser-warning` ヘッダーが必要 (無料枠のブラウザ警告ページを回避) |
| openWindow external | `liff.openWindow({ url, external: true })` で外部ブラウザを開く。`external: false` だと LINE 内 WebView で開かれ Google にブロックされる |

---

## 14. Agents as Tools パターン (Router Agent)

### アーキテクチャ

```
LINE User → Lambda → Router Agent (port 8080) → 一般質問: 自分で回答
                                                → カレンダー: calendar_agent @tool → Calendar Agent (port 8081)
```

Router Agent が LLM ベースで判断し、一般質問には自分で回答、専門的な操作は `@tool` 経由で専門 Agent に委譲する。
キーワードマッチではなく LLM の意図理解に基づくルーティングなので、自然な表現にも対応できる。

### LLM がツール結果の JSON を加工してしまう問題

**問題**: Router Agent の LLM が `calendar_agent` ツールの戻り値（JSON）を受け取ると、
それを自然言語に変換して返してしまう。例えば `{"type": "calendar_events", "events": [...]}` が
「2月9日の予定は2件です」に変換され、Lambda の `convert_agent_response` が JSON パースに失敗する。

システムプロンプトで「加工しないでください」と指示しても、LLM の性質上 100% の保証はできない。

**解決策**: モジュールレベル変数 `_calendar_agent_result` でツールの生レスポンスを保持し、
`invoke()` で LLM の出力を無視して生 JSON を直接返す。

```python
_calendar_agent_result: str | None = None

@tool
def calendar_agent(query: str) -> str:
    global _calendar_agent_result
    # ... Calendar Agent を呼び出し ...
    raw_result = result.get("result", str(result))
    _calendar_agent_result = raw_result  # 生レスポンスを保持
    return raw_result

@app.entrypoint
def invoke(payload: dict) -> dict:
    global _calendar_agent_result
    _calendar_agent_result = None  # リセット

    agent = create_agent()
    result = agent(prompt)

    # ツールが呼ばれた場合、LLM の後処理をバイパス
    if _calendar_agent_result is not None:
        response_text = _calendar_agent_result
    else:
        response_text = str(result)  # 一般回答はそのまま
    ...
```

**教訓**: LLM にツール結果を「そのまま返せ」と指示するより、アプリケーションレベルでバイパスする方が確実。

### Router Agent のシステムプロンプト設計

**問題**: ルーティングルールが曖昧だと、カレンダー関連のリクエストでもツールを呼ばず
自分でテキスト回答してしまう（例: 「来週に買い物の予定を入れたい」に対して質問返しをする）。

**解決策**: ルーティングルールを具体的なパターン列挙 + 「少しでも意図があれば必ずツール委譲」と明示する。

```
calendar_agent を呼ぶべきケース:
・予定/スケジュール/カレンダーに関する操作すべて
・「予定を見せて」「予定ある？」→ 予定一覧
・「予定を入れたい」「○○したい」(予定作成の意図) → 予定作成
・「来週」「明日」などの日時表現 + 行動 → 予定作成
・ユーザーの発言にカレンダー操作の意図が少しでもあれば → calendar_agent
```

**教訓**: LLM は「判断してください」と言うと自分で回答しがち。「必ず」「質問や確認も不要」と強制する方がルーティング精度が上がる。

---

## 15. Maps Flex Message カルーセル

### アーキテクチャ

```
Router Agent の search_place / recommend_place
  ↓ JSON レスポンス（_maps_agent_result でバイパス）
Lambda convert_agent_response()
  ↓ type: "place_search" / "place_recommend" を検出
place_carousel.py で Flex Message カルーセル生成
  ↓ 静的地図画像 + 場所情報カード
LINE に送信
```

### ツール定義の配置場所

**問題**: 当初 `agent/tools/google_maps.py` に分離して定義していたが、`_maps_agent_result` バイパス変数を `main.py` と共有する必要があった。

**解決策**: `search_place` / `recommend_place` を `main.py` にインライン定義（`calendar_agent` と同じパターン）。
ツールが少ないうちはファイル分離よりバイパス変数の共有のしやすさを優先する方がシンプル。

### LINE Flex Message image URL のバリデーション

**問題**: Google Static Maps API の URL に含まれる `|` (パイプ文字) が LINE のバリデーションに引っかかり、
`invalid uri scheme` エラー (HTTP 400) で Flex Message の送信が失敗した。

```
エラーログ:
HTTP response body: {"message":"A message (messages[1]) in the request body is invalid",
"details":[{"message":"invalid uri scheme","property":"/contents/0/hero/url"}]}
```

**原因**: `markers=color:red|35.658,139.701` の `|` が RFC 準拠の URI として不正。

**解決策**: `urllib.parse.quote()` でパイプをエンコード (`%7C`) する。

```python
from urllib.parse import quote
markers = quote(f"color:red|{lat},{lon}")
url = f"https://maps.googleapis.com/maps/api/staticmap?...&markers={markers}&key={api_key}"
```

**教訓**: 外部 API の URL をそのまま LINE Flex Message に埋め込む場合、特殊文字 (`|`, `#`, `{`, `}` 等) は必ず URL エンコードすること。

### モジュールレベル変数 vs 関数内読み込み

**問題**: `place_carousel.py` で API キーをモジュールレベルで読み込んでいたが、
Lambda の `__main__` ブロックで `load_dotenv()` が実行される前にモジュールがインポートされるため、
環境変数が空になっていた。

```python
# NG: インポート時に読み込まれるが、まだ .env.local が load されていない
GOOGLE_STATIC_MAPS_KEY = os.environ.get("GOOGLE_STATIC_MAPS_KEY", "")
```

**解決策**: 環境変数は関数内で読む。

```python
# OK: 関数呼び出し時に読むので、load_dotenv() 後に確実に取得できる
def _build_hero_image(lat, lon):
    if not os.environ.get("GOOGLE_STATIC_MAPS_KEY", ""):
        return None
    ...
```

**教訓**: `__main__` で `load_dotenv()` するローカル開発パターンでは、
他モジュールの環境変数読み込みはモジュールレベルではなく関数内で行うこと。
Lambda 本番環境では環境変数が最初から設定されるため問題にならないが、ローカルではハマる。

### Bedrock モデル ID のリージョン依存

**問題**: `us.anthropic.claude-sonnet-4-5-20250929-v1:0` を `ap-northeast-1` リージョンで使おうとして `ValidationException: The provided model identifier is invalid` エラーが発生。

**原因**: モデル ID のプレフィックスはリージョンに紐づく。`us.` は US リージョン専用。

**解決策**: `aws bedrock list-inference-profiles` で利用可能なモデルを確認する。

```bash
aws bedrock list-inference-profiles --region ap-northeast-1 \
  --query "inferenceProfileSummaries[?contains(inferenceProfileName, 'Sonnet')].{name:inferenceProfileName, id:inferenceProfileId}" \
  --output table
```

| リージョン | プレフィックス | 例 |
|-----------|-------------|---|
| US | `us.` | `us.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| 東京 (JP) | `jp.` | `jp.anthropic.claude-sonnet-4-5-20250929-v1:0` |
| APAC 全体 | `apac.` | `apac.anthropic.claude-sonnet-4-20250514-v1:0` (Sonnet 4.5 は `apac.` なし) |
| グローバル | `global.` | `global.anthropic.claude-sonnet-4-5-20250929-v1:0` |

**教訓**: リージョン変更時はモデル ID のプレフィックスも変更する。`global.` は全リージョンで使えるが、JP 固有のプレフィックスの方が低レイテンシになる場合がある。

### GCP Static Maps API のセットアップ

CLI で API 有効化とキー作成ができる。

```bash
# 1. プロジェクト設定
gcloud config set project <project-id>

# 2. Static Maps API を有効化
gcloud services enable static-maps-backend.googleapis.com

# 3. API キー作成 (Static Maps API のみに制限)
gcloud alpha services api-keys create \
  --display-name="Static Maps API Key" \
  --api-target=service=static-maps-backend.googleapis.com
```

### JSON レスポンス契約 (Maps)

| type | 用途 | 主要フィールド |
|------|------|---------------|
| `place_search` | 場所検索結果 | `places[]` (name, lat, lon, place_id) |
| `place_recommend` | おすすめ場所 | `places[]` (name, description, latitude, longitude, rating, minPrice) |
