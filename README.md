# LINE AI Assistant

LINE 上で動く AI チャットボット。
AWS Bedrock AgentCore Runtime (Strands Agents + Claude Sonnet 4.5) で AI エージェントをホストし、LINE Webhook は API Gateway + Lambda で受ける。

---

## Architecture

```
┌──────┐     ┌──────────────┐     ┌────────────────────┐     ┌──────────────────────────────┐     ┌──────────────────┐
│ LINE │────▶│ API Gateway  │────▶│  Lambda (Python)   │────▶│ Bedrock AgentCore Runtime    │────▶│ Claude Sonnet 4.5│
│ User │◀────│ POST /callback│◀────│ Webhook Handler    │◀────│ Strands Agent                │◀────│ (Foundation Model)│
└──────┘     └──────────────┘     └────────────────────┘     └──────────────────────────────┘     └──────────────────┘
                  prod                  512MB / 60s                lineAssistantAgent
                  ARM64                 ARM64
```

**リクエストフロー:**

1. LINE ユーザーがメッセージを送信
2. API Gateway が `POST /callback` を Lambda へルーティング
3. Lambda が LINE Webhook 署名を検証し、メッセージを処理
4. Lambda が Bedrock AgentCore Runtime を呼び出し
5. AgentCore Runtime が Claude Sonnet 4.5 で AI 応答を生成
6. Lambda が LINE Messaging API 経由でユーザーに応答を返信
   - 55 秒以内: Reply API
   - 55 秒超過: Push API にフォールバック

---

## Project Structure

```
assistant_agent_line/
├── agent/                  # Strands Agent (AgentCore Container)
│   ├── main.py             # Agent エントリポイント
│   └── requirements.txt    # strands-agents, bedrock-agentcore
├── lambda/                 # LINE Webhook Handler
│   ├── index.py            # Lambda ハンドラ + ローカル FastAPI
│   └── requirements.txt    # line-bot-sdk, boto3, fastapi, uvicorn
├── infra/                  # AWS CDK (TypeScript)
│   ├── bin/app.ts          # CDK アプリエントリポイント
│   └── lib/stack.ts        # スタック定義
├── docs/
│   ├── todo/TODO.md        # タスク管理
│   └── knowledge/RULES.md  # 開発ルール
├── conftest.py             # テスト用モジュール登録
├── requirements-dev.txt    # テスト依存 (pytest, moto)
├── pyproject.toml          # pytest 設定
├── .env.example            # 環境変数テンプレート
└── .env.local              # ローカル開発用環境変数
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

### 1. Clone & 環境変数設定

```bash
git clone <repository-url>
cd assistant_agent_line

cp .env.example .env.local
```

`.env.local` を編集:

```bash
# LINE Messaging API (LINE Developer Console から取得)
LINE_CHANNEL_SECRET=your-channel-secret
LINE_CHANNEL_ACCESS_TOKEN=your-channel-access-token

# AWS
AWS_REGION=us-east-1

# Agent
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
LOG_LEVEL=INFO

# ローカル開発用 AgentCore エンドポイント
AGENTCORE_RUNTIME_ENDPOINT=http://localhost:8080
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

3 つのターミナルを使用する。

### Terminal 1: Agent 起動

```bash
source .venv/bin/activate
cd agent
python main.py
# → http://localhost:8080 で起動
```

### Terminal 2: Lambda (FastAPI) 起動

```bash
source .venv/bin/activate
cd lambda
python index.py
# → http://localhost:8000 で起動 (FastAPI + uvicorn)
```

### Terminal 3: ngrok トンネル

```bash
ngrok http 8000
# → https://xxxx.ngrok.io が発行される
```

### LINE Developer Console で Webhook URL 設定

1. [LINE Developer Console](https://developers.line.biz/) を開く
2. Messaging API チャネルを選択
3. Webhook URL に `https://xxxx.ngrok.io/callback` を設定
4. Webhook を有効化
5. LINE でメッセージを送って動作確認

---

## Commands

### 開発コマンド

| コマンド | 説明 |
|---------|------|
| `python agent/main.py` | Agent をローカル起動 (port 8080) |
| `python lambda/index.py` | Lambda を FastAPI でローカル起動 (port 8000) |
| `ngrok http 8000` | ngrok トンネル作成 |

### テストコマンド

| コマンド | 説明 |
|---------|------|
| `pytest agent/tests/ lambda/tests/ -v` | 全テスト実行 |
| `pytest agent/tests/ -v` | Agent テストのみ |
| `pytest lambda/tests/ -v` | Lambda テストのみ |

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
| `LineWebhookApi` | API Gateway REST API | `POST /callback`, rate=100/s, burst=50 |
| `WebhookFunction` | Lambda | Python 3.13, ARM64, 512MB, 60s timeout |
| `LambdaDepsLayer` | Lambda Layer | line-bot-sdk, boto3 等の依存パッケージ |
| `lineAssistantAgent` | Bedrock AgentCore Runtime | Strands Agent + Claude Sonnet 4.5 |
| CloudWatch Logs | CloudWatch | Lambda ログ (保持期間: 1 週間) |

### IAM Permissions

- **Lambda → AgentCore Runtime**: `bedrock-agentcore:InvokeAgentRuntime`
- **AgentCore Runtime → Bedrock**: `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`

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

#### Lambda

| 変数 | 説明 |
|------|------|
| `LINE_CHANNEL_SECRET` | LINE チャネルシークレット |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE チャネルアクセストークン |
| `AGENT_RUNTIME_ARN` | AgentCore Runtime ARN (CDK が自動設定) |
| `AWS_REGION_NAME` | AWS リージョン (CDK が自動設定) |
| `LOG_LEVEL` | ログレベル (default: `INFO`) |

#### Agent (AgentCore Runtime)

| 変数 | 説明 |
|------|------|
| `BEDROCK_MODEL_ID` | Bedrock モデル ID (default: Claude Sonnet 4.5) |
| `LOG_LEVEL` | ログレベル (default: `INFO`) |
