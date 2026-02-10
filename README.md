# LINE AI Assistant

LINE 上で動く AI チャットボット。
AWS Bedrock AgentCore Runtime (Strands Agents + Claude) で AI エージェントをホストし、LINE Webhook は API Gateway + Lambda で受ける。
Router Agent (Agents as Tools パターン) が LLM ベースで意図を判断し、一般質問には自分で回答、カレンダー操作は Calendar Agent に、メール操作は Gmail Agent に、場所検索は Maps ツールに、Web 検索は Tavily API に委譲する。
Google 連携 (OAuth2 + LIFF) により、LINE 上からカレンダー・Gmail の操作が可能。
場所検索・おすすめ場所は Flex Message カルーセル（静的地図画像付き）でリッチ表示。
Bedrock AgentCore Memory によるユーザーごとの会話記憶（短期・長期）に対応。

---

## Architecture

```
┌──────┐     ┌──────────────────┐     ┌─────────────────────┐     ┌─────────────────────────┐     ┌──────────────────┐
│ LINE │────▶│ API Gateway      │────▶│  Lambda (Python)    │────▶│ Router Agent            │────▶│ Claude           │
│ User │◀────│ POST /callback   │◀────│  Webhook Handler    │     │ (AgentCore Runtime)     │◀────│ (Foundation Model)│
└──────┘     │ GET /oauth/callback│    │                     │     │                         │     └──────────────────┘
             └──────────────────┘     │                     │     │  ┌─ 一般質問: 自分で回答 │
                                      │                     │     │  ├─ カレンダー: @tool ──┐│
                                      │                     │     │  ├─ メール: @tool ────┐ ││     ┌──────────────────┐
                                      │                     │     │  ├─ 場所検索: @tool   │ ││  ┌─▶│ Google Calendar  │
                                      │                     │     │  ├─ おすすめ: @tool   │ ││  │  │ API              │
                                      │                     │     │  ├─ 位置情報: @tool   │ ││  │  └──────────────────┘
                                      │                     │     │  └─ Web検索: @tool    │ ││  │  ┌──────────────────┐
                                      │                     │     └─────────────────────────┘ ││  ├─▶│ Gmail API        │
                                      │                     │                                 ││  │  └──────────────────┘
                                      │                     │     ┌─────────────────────────┐ ││  │  ┌──────────────────┐
                                      │                     │     │ Calendar Agent          ◀─┘│──┤  │ Vercel Maps API  │
                                      │                     │     │ (AgentCore Runtime)     │  │  ├─▶│ (search/recommend)│
                                      │                     │     └─────────────────────────┘  │  │  └──────────────────┘
                                      │                     │     ┌─────────────────────────┐  │  │  ┌──────────────────┐
                                      │                     │     │ Gmail Agent             ◀──┘  └─▶│ Tavily API       │
                                      │                     │     │ (AgentCore Runtime)     │        │ (Web検索/抽出)    │
                                      │                     │     └─────────────────────────┘        └──────────────────┘
                                      │                     │
                                      │  ┌─── DynamoDB ────┐│     ┌─────────────────────────┐
                                      │  │ GoogleOAuthTokens││     │ AgentCore Memory        │
                                      │  │ UserSessionState ││     │ (会話記憶: 短期+長期)    │
                                      │  └─────────────────┘│     │ actor_id = LINE user_id  │
                                      └─────────────────────┘     │ session_id = user-日付   │
                                                                  └─────────────────────────┘
                                      ┌─────────────────────┐
                                      │ LIFF App            │
                                      │ → Google OAuth2      │
                                      │ (外部ブラウザで認証) │
                                      └─────────────────────┘
```

**リクエストフロー (テキストメッセージ):**

1. LINE ユーザーがメッセージを送信
2. API Gateway が `POST /callback` を Lambda へルーティング
3. Lambda が LINE Webhook 署名を検証し、メッセージを処理
4. Lambda が Router Agent を呼び出し (Google 認証情報付き)
5. Router Agent が LLM ベースで意図を判断
   - 一般質問・雑談 → 自分で直接回答
   - カレンダー操作 → `calendar_agent` @tool 経由で Calendar Agent に委譲
   - メール操作 → `gmail_agent` @tool 経由で Gmail Agent に委譲
   - 場所検索 → `search_place` @tool 経由で Vercel Maps API に委譲
   - おすすめ場所 → `recommend_place` @tool 経由で Vercel Maps API に委譲
   - 現在地依存 → `request_location` @tool で位置情報をリクエスト
   - Web 検索 → `web_search` / `extract_content` @tool 経由で Tavily API に委譲
   - 会話記憶: Bedrock AgentCore Memory で過去の会話・ユーザー情報を自動参照
6. 各 Agent / Maps API が JSON レスポンスを返却
7. Router Agent がツールの生 JSON をそのまま Lambda に返す (LLM の後処理をバイパス)
8. Lambda が `_sanitize_response` で JSON を抽出後、type フィールドに応じて Flex Message を構築
   - `calendar_events` → 予定一覧カルーセル
   - `date_selection` → 日付選択カルーセル (空き=緑 / 埋まり=グレー)
   - `email_list` → メール一覧カルーセル (未読/既読インジケーター付き)
   - `email_detail` → メール詳細 (要約・添付ファイル情報)
   - `email_confirm_send` → メール送信確認画面
   - `place_search` → 場所カルーセル (静的地図画像 + 地図を開くボタン)
   - `place_recommend` → おすすめカルーセル (地図画像 + 説明 + 評価・価格)
   - `location_request` → 位置情報リクエスト (QuickReply 付き)
   - `event_created` / `event_deleted` / `email_sent` / `email_deleted` → 確認メッセージ
   - テキスト → そのまま返信
9. Lambda が LINE Messaging API 経由でユーザーに応答を返信
   - 55 秒以内: Reply API
   - 55 秒超過: Push API にフォールバック

**Postback フロー (ボタンタップ):**

1. ユーザーがカルーセルのボタンをタップ
2. Lambda が Postback データを解析し、アクション種別に応じて処理
   - 日付選択 → 時間帯選択カルーセルを返信
   - 時間選択 → 確認画面を返信
   - 確認 → Calendar Agent で予定作成/削除
3. ユーザーセッション状態は DynamoDB (UserSessionState, TTL 10分) で管理

**OAuth2 フロー:**

1. Lambda が未認証ユーザーに LIFF URL を含む Flex Message を返信
2. ユーザーが LIFF リンクをタップ → LIFF App が開く
3. LIFF が `liff.openWindow({ url: oauthUrl, external: true })` で外部ブラウザを起動
   - Google が WebView (disallowed_useragent) をブロックするため、外部ブラウザが必須
4. ユーザーが Google アカウントで認証・同意 (Calendar + Gmail スコープ)
5. Google が `GET /oauth/callback` にリダイレクト → OAuth Callback Lambda がトークンを DynamoDB に保存
6. 以降のリクエストでは DynamoDB からトークンを取得 (自動リフレッシュ対応)

---

## Project Structure

```
assistant_agent_line/
├── agent/                         # Strands Agent (AgentCore Container)
│   ├── main.py                    # Router Agent エントリポイント (Agents as Tools)
│   ├── calendar_agent.py          # Calendar Agent (port 8081)
│   ├── gmail_agent.py             # Gmail Agent (port 8082)
│   ├── Dockerfile                 # Router Agent Docker
│   ├── Dockerfile.calendar        # Calendar Agent Docker
│   ├── Dockerfile.gmail           # Gmail Agent Docker
│   ├── tools/
│   │   ├── google_calendar.py     # 7 Calendar tools (@tool)
│   │   ├── google_gmail.py        # 7 Gmail tools (@tool)
│   │   ├── google_maps.py         # 3 Maps tools (@tool)
│   │   └── tavily_search.py       # 2 Web search tools (@tool)
│   ├── tests/
│   │   ├── test_main.py           # Router Agent テスト (Memory 統合含む)
│   │   ├── test_gmail_tools.py    # Gmail ツールテスト
│   │   └── test_tavily_tools.py   # Tavily Web 検索テスト
│   └── requirements.txt           # strands-agents, bedrock-agentcore
├── lambda/                        # LINE Webhook Handler
│   ├── index.py                   # Lambda ハンドラ (Postback, Router Agent 呼び出し)
│   ├── google_auth.py             # OAuth2 トークン管理 (DynamoDB CRUD)
│   ├── google_calendar_api.py     # Calendar API ラッパー (Postback 用)
│   ├── oauth_callback.py          # OAuth2 コールバックハンドラ
│   ├── flex_messages/             # Flex Message ビルダー
│   │   ├── oauth_link.py          # OAuth 連携リンクカード
│   │   ├── calendar_carousel.py   # 予定一覧カルーセル
│   │   ├── place_carousel.py      # 場所カルーセル (静的地図画像付き)
│   │   ├── date_picker.py         # 日付選択 (緑=空き, グレー=埋まり)
│   │   ├── time_picker.py         # 時間帯選択
│   │   ├── event_confirm.py       # 作成/削除 確認画面
│   │   ├── email_carousel.py      # メール一覧カルーセル
│   │   ├── email_detail.py        # メール詳細表示
│   │   └── email_confirm.py       # メール送信確認画面
│   ├── tests/
│   │   ├── test_index.py          # Lambda ハンドラテスト
│   │   ├── test_flex_messages.py  # Calendar/Maps Flex テスト
│   │   ├── test_email_flex.py     # Gmail Flex テスト
│   │   └── test_google_auth.py    # OAuth テスト
│   └── requirements.txt           # line-bot-sdk, boto3, fastapi, uvicorn
├── infra/                         # AWS CDK (TypeScript)
│   ├── bin/app.ts                 # CDK アプリエントリポイント
│   └── lib/line-agent-stack.ts    # スタック定義
├── docs/
│   ├── todo/TODO.md               # タスク管理
│   └── knowledge/                 # 開発ナレッジ
├── conftest.py                    # テスト用モジュール登録
├── requirements-dev.txt           # テスト依存 (pytest, moto)
├── pyproject.toml                 # pytest 設定
├── .env.example                   # 環境変数テンプレート
└── .env.local                     # ローカル開発用環境変数
```

---

## Setup

### Prerequisites

| Tool | Version | 用途 |
|------|---------|------|
| Python | 3.13+ | Agent / Lambda |
| Node.js | 20+ | CDK |
| AWS CLI | v2 | AWS 認証 |
| Docker | latest | Lambda Layer ビルド / AgentCore ローカル |
| ngrok | latest | ローカル開発時の LINE Webhook トンネル |

### GCP セットアップ (Google カレンダー・Gmail 連携 + Static Maps)

1. **Google Cloud プロジェクト作成** & Calendar API / Gmail API を有効化
2. **OAuth2 クライアント作成** (認証情報 → OAuth 2.0 クライアント ID → ウェブアプリケーション)
   - 承認済みリダイレクト URI: `https://<ngrok-or-api-gateway>/oauth/callback`
3. **LIFF アプリ作成** (LINE Developer Console → LIFF タブ)
   - エンドポイント URL: `https://<ngrok-domain>/liff/oauth` (ローカル) or 本番 URL
   - LIFF ID を `.env.local` の `LIFF_ID` に設定
4. **Maps Static API を有効化** & API キー作成 (場所カルーセルの地図画像用)
   ```bash
   gcloud services enable static-maps-backend.googleapis.com
   gcloud alpha services api-keys create \
     --display-name="Static Maps API Key" \
     --api-target=service=static-maps-backend.googleapis.com
   ```
   - API キーを `.env.local` の `GOOGLE_STATIC_MAPS_KEY` に設定

### 1. Clone & 環境変数設定

```bash
git clone <repository-url>
cd assistant_agent_line

cp .env.example .env.local
```

`.env.local` を編集 (`.env.example` を参照):

```bash
# LINE Messaging API (LINE Developer Console から取得)
LINE_CHANNEL_SECRET=your-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-channel-access-token

# AWS
AWS_REGION=us-east-1

# Agent
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
CALENDAR_AGENT_ENDPOINT=http://localhost:8081
GMAIL_AGENT_ENDPOINT=http://localhost:8082
MAPS_API_BASE_URL=https://myplace-blush.vercel.app
GOOGLE_STATIC_MAPS_KEY=your-google-static-maps-api-key
LOG_LEVEL=INFO

# ローカル開発用 AgentCore エンドポイント
AGENTCORE_RUNTIME_ENDPOINT=http://localhost:8080

# Google OAuth2
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=https://your-ngrok-domain.ngrok.io/oauth/callback
OAUTH_STATE_SECRET=your-random-secret-key

# LIFF (Google OAuth を外部ブラウザで開くため)
LIFF_ID=your-liff-id

# DynamoDB
DYNAMODB_TOKEN_TABLE=GoogleOAuthTokens
USER_STATE_TABLE=UserSessionState
```

### 2. Python 仮想環境

```bash
python -m venv .venv
source .venv/bin/activate

pip install -r agent/requirements.txt
pip install -r lambda/requirements.txt
pip install -r requirements-dev.txt
```

### 3. CDK セットアップ

```bash
cd infra
npm install
cd ..
```

---

## Local Development

5 つのターミナルを使用する。

### Terminal 1: Calendar Agent 起動

```bash
.venv/bin/python agent/calendar_agent.py --port 8081
# → http://localhost:8081 で起動
```

### Terminal 2: Gmail Agent 起動

```bash
.venv/bin/python agent/gmail_agent.py --port 8082
# → http://localhost:8082 で起動
```

### Terminal 3: Router Agent 起動

```bash
.venv/bin/python agent/main.py
# → http://localhost:8080 で起動
```

### Terminal 4: Lambda (FastAPI) 起動

```bash
.venv/bin/python lambda/index.py
# → http://localhost:8000 で起動 (FastAPI + uvicorn)
```

### Terminal 5: ngrok トンネル

```bash
ngrok http 8000
# → https://xxxx.ngrok.io が発行される
```

### LINE Developer Console で Webhook URL 設定

1. [LINE Developer Console](https://developers.line.biz/) を開く
2. Messaging API チャネルを選択
3. Webhook URL に `https://xxxx.ngrok.io/callback` を設定
4. Webhook を有効化
5. LIFF エンドポイント URL を `https://xxxx.ngrok.io/liff/oauth` に更新
6. `.env.local` の `GOOGLE_REDIRECT_URI` を `https://xxxx.ngrok.io/oauth/callback` に更新
7. GCP Console で OAuth2 リダイレクト URI も同じ ngrok URL に更新
8. LINE でメッセージを送って動作確認

---

## Commands

### 開発コマンド

| コマンド | 説明 |
|---------|------|
| `.venv/bin/python agent/main.py` | Router Agent をローカル起動 (port 8080) |
| `.venv/bin/python agent/calendar_agent.py --port 8081` | Calendar Agent をローカル起動 (port 8081) |
| `.venv/bin/python agent/gmail_agent.py --port 8082` | Gmail Agent をローカル起動 (port 8082) |
| `.venv/bin/python lambda/index.py` | Lambda を FastAPI でローカル起動 (port 8000) |
| `ngrok http 8000` | ngrok トンネル作成 |

### テストコマンド

| コマンド | 説明 |
|---------|------|
| `.venv/bin/pytest agent/tests/ lambda/tests/ -v` | 全テスト実行 (94テスト) |
| `.venv/bin/pytest agent/tests/ -v` | Agent テストのみ |
| `.venv/bin/pytest lambda/tests/ -v` | Lambda テストのみ |

### CDK コマンド

```bash
cd infra
```

| コマンド | 説明 |
|---------|------|
| `npm run synth` | CloudFormation テンプレート生成 |
| `npm run deploy` | AWS にデプロイ |
| `npm run diff` | デプロイ済みスタックとの差分表示 |
| `npm run build` | TypeScript コンパイル |
| `npx cdk destroy` | スタック削除 |

---

## AWS Details

### デプロイされるリソース

| リソース | サービス | 詳細 |
|---------|---------|------|
| `LineWebhookApi` | API Gateway REST API | `POST /callback`, `GET /oauth/callback`, rate=100/s, burst=50 |
| `WebhookFunction` | Lambda | Python 3.13, ARM64, 512MB, 60s timeout |
| `OAuthCallbackFunction` | Lambda | OAuth2 コールバック処理 |
| `LambdaDepsLayer` | Lambda Layer | line-bot-sdk, boto3 等の依存パッケージ |
| `lineAssistantAgent` | Bedrock AgentCore Runtime | Router Agent (Strands Agent + Claude, Agents as Tools) |
| `CalendarAgentRuntime` | Bedrock AgentCore Runtime | Calendar Agent (Strands Agent + Calendar tools) |
| `GmailAgentRuntime` | Bedrock AgentCore Runtime | Gmail Agent (Strands Agent + Gmail tools) |
| `GoogleOAuthTokens` | DynamoDB | OAuth2 トークン保存 (RemovalPolicy: RETAIN) |
| `UserSessionState` | DynamoDB | ユーザーセッション状態 (RemovalPolicy: DESTROY, TTL 有効) |
| CloudWatch Logs | CloudWatch | Lambda ログ (保持期間: 1 週間) |

### IAM Permissions

- **Lambda → AgentCore Runtime**: `bedrock-agentcore:InvokeAgentRuntime`
- **Lambda → DynamoDB**: `GoogleOAuthTokens` / `UserSessionState` テーブルへの CRUD
- **AgentCore Runtime → Bedrock**: `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`
- **AgentCore Runtime → Bedrock Memory**: `bedrock:GetMemory`, `bedrock:CreateSession`, `bedrock:PutSessionEvent` 等
- **OAuthCallbackFunction → DynamoDB**: `GoogleOAuthTokens` テーブルへの書き込み

### デプロイ手順

```bash
# 1. 環境変数を設定
export LINE_CHANNEL_SECRET=your-channel-secret
export LINE_CHANNEL_ACCESS_TOKEN=your-channel-access-token

# 2. CDK Bootstrap (初回のみ)
cd infra
npx cdk bootstrap

# 3. デプロイ
npm run deploy
```

### デプロイ後のスタック出力

| 出力 | 説明 |
|------|------|
| `WebhookUrl` | LINE Developer Console に設定する Webhook URL |
| `RuntimeArn` | AgentCore Runtime の ARN |
| `RuntimeName` | AgentCore Runtime の名前 (`lineAssistantAgent`) |

デプロイ後、出力された `WebhookUrl` を LINE Developer Console の Webhook URL に設定する。

### 環境変数一覧

#### Lambda (WebhookFunction)

| 変数 | 説明 |
|------|------|
| `LINE_CHANNEL_SECRET` | LINE チャネルシークレット |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE チャネルアクセストークン |
| `AGENT_RUNTIME_ARN` | Router Agent Runtime ARN (CDK が自動設定) |
| `AWS_REGION_NAME` | AWS リージョン (CDK が自動設定) |
| `GOOGLE_CLIENT_ID` | Google OAuth2 クライアント ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 クライアントシークレット |
| `GOOGLE_REDIRECT_URI` | OAuth2 リダイレクト URI |
| `OAUTH_STATE_SECRET` | HMAC 署名用シークレットキー |
| `LIFF_ID` | LIFF アプリ ID (LINE Developer Console から取得) |
| `DYNAMODB_TOKEN_TABLE` | OAuth トークンテーブル名 (default: `GoogleOAuthTokens`) |
| `USER_STATE_TABLE` | ユーザーセッション状態テーブル名 (default: `UserSessionState`) |
| `GOOGLE_STATIC_MAPS_KEY` | Google Static Maps API キー (場所カルーセルの地図画像用) |
| `LOG_LEVEL` | ログレベル (default: `INFO`) |

#### Lambda (OAuthCallbackFunction)

| 変数 | 説明 |
|------|------|
| `GOOGLE_CLIENT_ID` | Google OAuth2 クライアント ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 クライアントシークレット |
| `GOOGLE_REDIRECT_URI` | OAuth2 リダイレクト URI |
| `OAUTH_STATE_SECRET` | HMAC 署名用シークレットキー |
| `DYNAMODB_TOKEN_TABLE` | OAuth トークンテーブル名 |

#### Agent (AgentCore Runtime)

| 変数 | 説明 |
|------|------|
| `BEDROCK_MODEL_ID` | Bedrock モデル ID (default: Claude Sonnet 4.5) |
| `BEDROCK_MEMORY_ID` | Bedrock AgentCore Memory ID (空の場合はメモリ無効) |
| `CALENDAR_AGENT_ENDPOINT` | Calendar Agent エンドポイント (default: `http://localhost:8081`) |
| `GMAIL_AGENT_ENDPOINT` | Gmail Agent エンドポイント (default: `http://localhost:8082`) |
| `MAPS_API_BASE_URL` | Maps API ベース URL (default: `https://myplace-blush.vercel.app`) |
| `TAVILY_API_KEY` | Tavily API キー (Web 検索用) |
| `LOG_LEVEL` | ログレベル (default: `INFO`) |
