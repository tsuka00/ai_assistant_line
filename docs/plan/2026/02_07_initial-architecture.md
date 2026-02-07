# LINE AI Assistant - 初期アーキテクチャ計画

**作成日**: 2026-02-07

## アーキテクチャ

```
User → LINE → API Gateway (REST)
                   ↓
              Lambda (Python 3.13 / ARM64)
                   │
                   ├─ 1. 署名検証
                   ├─ 2. show_loading_animation(60s)
                   ├─ 3. AgentCore Runtime invoke ──→ Strands Agent (Claude Sonnet 4.5)
                   └─ 4. reply_message (ローディング自動消滅)
```

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| IaC | AWS CDK (TypeScript) + `@aws-cdk/aws-bedrock-agentcore-alpha` |
| Webhook | API Gateway (REST) + Lambda (Python 3.13 / ARM64) |
| Agent | Strands Agents SDK (`strands-agents`) on Bedrock AgentCore Runtime |
| LLM | Claude Sonnet 4.5 on Amazon Bedrock |

## 処理フロー

```
User                LINE Platform         Lambda                    AgentCore Runtime
 |                       |                   |                           |
 |-- メッセージ送信 ----->|                   |                           |
 |                       |-- POST /callback ->|                           |
 |                       |                   |-- 署名検証                 |
 |                       |<-- loading(60s) --|                           |
 |<- ローディング表示 ---|                   |                           |
 |                       |                   |-- invoke_runtime() ------>|
 |                       |                   |   (Strands Agent)         |
 |                       |                   |   Agent(Claude 4.5)       |
 |                       |                   |<-- AI応答 ---------------|
 |                       |<-- reply_message -|                           |
 |<- AI応答メッセージ ---|                   |                           |
 |   (ローディング消滅)   |                   |                           |
```

## 環境変数

| 変数名 | 用途 | 設定先 |
|--------|------|--------|
| `LINE_CHANNEL_SECRET` | LINE署名検証 | Lambda |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE API認証 | Lambda |
| `AGENTCORE_RUNTIME_NAME` | AgentCore Runtime識別子 | Lambda |
| `AWS_REGION` | AWSリージョン | Lambda / Agent |
| `BEDROCK_MODEL_ID` | Claudeモデル指定 | Agent |
| `SYSTEM_PROMPT` | AIペルソナ | Agent |
