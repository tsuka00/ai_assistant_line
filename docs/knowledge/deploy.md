# デプロイナレッジ

## 1. デプロイ手順

### 前提条件

| 項目 | 詳細 |
|------|------|
| AWS CLI | `aws configure --profile line-agent` 済み |
| Docker | 起動中であること（AgentCore Runtime のコンテナビルドに必要） |
| Node.js | CDK CLI (`npx cdk`) が使える状態 |
| `.env.local` | ルートディレクトリに全環境変数が設定済み |

### デプロイコマンド

```bash
cd infra

# 1. 環境変数を読み込み（CDK は process.env.* で参照する）
set -a && source ../.env.local && set +a

# 2. AWS プロファイル指定
export AWS_PROFILE=line-agent

# 3. デプロイ
npx cdk deploy --require-approval never
```

### CDK の環境変数の仕組み

CDK (TypeScript) は `process.env.*` でシェル環境変数を直接読み込む。
`dotenv` ライブラリは使っていないため、`source .env.local` でシェルに展開する必要がある。

```typescript
// infra/lib/line-agent-stack.ts
environmentVariables: {
  LINE_CHANNEL_SECRET: process.env.LINE_CHANNEL_SECRET ?? "",  // ← シェルから読む
}
```

`set -a` は変数を自動的に `export` するオプション。`set +a` で解除。

---

## 2. デプロイ後の設定

| 項目 | 設定場所 | 値 |
|------|---------|---|
| Webhook URL | LINE Developer Console | `https://<api-gw>.execute-api.<region>.amazonaws.com/prod/callback` |
| OAuth Redirect URI | GCP Console + `.env.local` | `https://<api-gw>.execute-api.<region>.amazonaws.com/prod/oauth/callback` |
| LIFF Endpoint URL | LINE Developer Console | LIFF 用ページの URL |

### 本番環境情報 (2026-02-11 時点)

| リソース | 値 |
|---|---|
| API Gateway | `https://2uco1x3zrk.execute-api.ap-northeast-1.amazonaws.com/prod/` |
| Webhook URL | `.../prod/callback` |
| OAuth Callback | `.../prod/oauth/callback` |
| Router Agent | `lineAssistantAgent-RyWqz746z6` |
| Calendar Agent | `calendarAgent-q4mELzB9a6` |
| Gmail Agent | `gmailAgent-Owua548TiA` |
| Memory | `LineAssistantMemory-8u4fziHv4d` (us-east-1) |
| リージョン | `ap-northeast-1`（Memory のみ `us-east-1`） |

---

## 3. DynamoDB テーブルの CDK インポート

### 問題

DynamoDB テーブルを CDK の外で先に作成した場合、`cdk deploy` で以下のエラーになる:

```
Resource of type 'AWS::DynamoDB::Table' with identifier 'xxx' already exists
```

CDK は自分が管理していないリソースを新規作成しようとして、同名テーブルが既にあるため失敗する。

### 解決策

`cdk import` で既存リソースを CDK 管理下に取り込む。

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

# 3. 残りの変更を適用
npx cdk deploy --require-approval never
```

### 注意点

- マッピングファイルのキー（`GoogleOAuthTokensD18E1AC9` 等）は CDK が生成する論理 ID。`cdk synth` の出力や `cdk diff` のエラーメッセージから確認できる
- `--force` は import 時に他の変更差分を無視するオプション。import 後に `cdk deploy` で残りを適用する
- データは消えない。CDK の管理下に入るだけ
- `cdk import` は対話的に論理 ID を聞いてくるが、`--resource-mapping` を使えば非対話で実行できる

---

## 4. Bedrock AgentCore Memory リソースの作成

Memory リソースは CDK では管理しない。AWS CLI で手動作成する。

### 作成コマンド

```bash
aws bedrock-agentcore-control create-memory \
  --name LineAssistantMemory \
  --description "LINE AI Assistant - user conversation memory" \
  --event-expiry-duration 90 \
  --region us-east-1 \
  --profile line-agent \
  --memory-strategies '[
    {
      "summaryMemoryStrategy": {
        "name": "SessionSummarizer",
        "namespaces": ["/summaries/{actorId}/{sessionId}/"]
      }
    },
    {
      "userPreferenceMemoryStrategy": {
        "name": "PreferenceLearner",
        "namespaces": ["/preferences/{actorId}/"]
      }
    },
    {
      "semanticMemoryStrategy": {
        "name": "FactExtractor",
        "namespaces": ["/facts/{actorId}/"]
      }
    }
  ]' \
  --output json
```

### ステータス確認

```bash
aws bedrock-agentcore-control get-memory \
  --memory-id "LineAssistantMemory-8u4fziHv4d" \
  --region us-east-1 \
  --profile line-agent \
  --query 'memory.status' \
  --output text
```

ステータスは `CREATING` → `ACTIVE` に遷移する（約 3 分）。

### `.env.local` への設定

```
BEDROCK_MEMORY_ID=LineAssistantMemory-8u4fziHv4d
```

設定後にデプロイすると、Router Agent Runtime の環境変数として反映される。

### Memory のリージョン

AgentCore Memory は `us-east-1` で作成する。Agent Runtime (`ap-northeast-1`) からクロスリージョンでアクセスする。
`agent/main.py` の `_build_session_manager()` で `region_name` を明示的に指定している。

---

## 5. 環境変数一覧

### CDK が `process.env.*` で読む変数（デプロイ時に必要）

| 変数名 | 用途 | 設定先 |
|--------|------|--------|
| `LINE_CHANNEL_SECRET` | LINE 署名検証 | Webhook Lambda |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE API 呼び出し | Webhook Lambda |
| `GOOGLE_CLIENT_ID` | Google OAuth2 | Webhook Lambda, OAuth Callback Lambda |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 | Webhook Lambda, OAuth Callback Lambda |
| `OAUTH_STATE_SECRET` | OAuth state HMAC 署名 | Webhook Lambda, OAuth Callback Lambda |
| `TAVILY_API_KEY` | Tavily Web Search | Router Agent Runtime |
| `BEDROCK_MEMORY_ID` | AgentCore Memory | Router Agent Runtime |

### CDK が自動設定する変数（手動設定不要）

| 変数名 | 用途 | 設定先 |
|--------|------|--------|
| `AGENT_RUNTIME_ARN` | Router Agent 呼び出し | Webhook Lambda |
| `CALENDAR_AGENT_RUNTIME_ARN` | Calendar Agent 呼び出し | Webhook Lambda |
| `GMAIL_AGENT_RUNTIME_ARN` | Gmail Agent 呼び出し | Webhook Lambda |
| `DYNAMODB_TOKEN_TABLE` | OAuth トークンテーブル名 | Webhook Lambda |
| `USER_STATE_TABLE` | セッションステートテーブル名 | Webhook Lambda |
| `BEDROCK_MODEL_ID` | LLM モデル ID | 各 Agent Runtime |

---

## 6. CDK コマンド一覧

| コマンド | 用途 |
|---------|------|
| `npx cdk synth` | CloudFormation テンプレート生成（ドライラン） |
| `npx cdk diff` | 現在のスタックとの差分確認 |
| `npx cdk deploy` | デプロイ |
| `npx cdk deploy --require-approval never` | 承認なしデプロイ |
| `npx cdk destroy` | スタック削除（コスト節約時） |
| `npx cdk import --resource-mapping import-map.json --force` | 既存リソースの取り込み |

---

## 7. トラブルシューティング

### `cdk deploy` で DynamoDB already exists

→ セクション 3 参照。`cdk import` で解決。

### Lambda タイムアウト

Agent Runtime の応答が遅いと Lambda が 60 秒でタイムアウトする。
CloudWatch Logs (`/aws/lambda/LineAgentStack-WebhookFunction*`) で確認。

### Agent Runtime のログ確認

```bash
# Router Agent
aws bedrock-agentcore get-runtime \
  --runtime-name lineAssistantAgent \
  --region ap-northeast-1 \
  --profile line-agent
```

CloudWatch Logs グループは `/aws/bedrock-agentcore/runtime/<runtime-name>` 形式。

### 環境変数が空で渡される

`source .env.local` を忘れると全ての `process.env.*` が空文字列になる。
`cdk diff` で環境変数が変わっていないことを確認してからデプロイすること。

### Docker が起動していない

AgentCore Runtime のビルドで `Cannot connect to the Docker daemon` エラー。
Docker Desktop を起動してから再実行。

---

## 8. 今後のデプロイ改善

### CI/CD パイプライン構築

GitHub Actions で `main` ブランチへのマージ時に自動デプロイ。
環境変数は GitHub Secrets で管理し、`set -a && source` を不要にする。

### 環境分離 (dev / prod)

CDK の `Stage` を使って dev / prod を分離する。
DynamoDB テーブル名に環境プレフィックス (`dev-GoogleOAuthTokens` 等) を付与。

### `cdk deploy` のキャッシュ高速化

Lambda Layer と AgentCore Runtime のコンテナビルドがボトルネック。
Docker レイヤーキャッシュの活用、ECR キャッシュの導入を検討。

### CloudFormation ドリフト検知

`cdk diff` だけでなく、定期的に `aws cloudformation detect-stack-drift` でドリフトを検知する。
CDK 外で手動変更されたリソースを早期に発見する。

### コスト最適化

- 使わない時は `cdk destroy` でスタック削除（AgentCore Runtime の稼働時間課金を停止）
- Lambda の Provisioned Concurrency は不要（コールドスタートは許容範囲）
- CloudWatch Logs の保持期間は 1 週間に設定済み

### ロールバック手順の整備

デプロイ失敗時に前回のバージョンに戻す手順を整備。
CloudFormation のロールバックは自動だが、Agent Runtime のコンテナイメージのバージョニングが必要。
