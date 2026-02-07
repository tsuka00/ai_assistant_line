# LINE AI Assistant

LINE上で動くAIチャットボット。Strands Agents + Bedrock AgentCore Runtime でAIエージェントをホストし、LINE Webhookは API Gateway + Lambda で受ける。

## アーキテクチャ

```
User → LINE → API Gateway → Lambda → AgentCore Runtime (Strands Agent + Claude Sonnet 4.5)
```

## プロジェクト構成

```
assistant_agent_line/
├── infra/          # AWS CDK (TypeScript)
├── agent/          # Strands Agent (AgentCore Container)
├── lambda/         # LINE Webhook Handler
└── docs/           # ドキュメント
```

## セットアップ

### 前提条件

- Python 3.13+
- Node.js 20+
- AWS CLI (設定済み)
- Docker
- LINE Developer Console アカウント

### ローカル開発

```bash
# Agent 起動
cd agent
pip install -r requirements.txt
python main.py  # localhost:8080

# Lambda 起動 (別ターミナル)
cd lambda
pip install -r requirements.txt
python index.py  # localhost:8000 (FastAPI)

# ngrok でトンネル作成 (別ターミナル)
ngrok http 8000

# LINE Developer Console で Webhook URL を ngrok URL/callback に設定
```

### デプロイ

```bash
cd infra
npm install
npx cdk synth   # テンプレート確認
npx cdk deploy  # デプロイ
```

## 環境変数

`.env.example` を `.env` にコピーして設定:

```bash
cp .env.example .env
```
