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
| 1. Agent 起動 | `cd agent && python main.py` | 8080 |
| 2. Lambda 起動 | `cd lambda && python index.py` | 8000 |
| 3. ngrok | `ngrok http 8000` | ngrok URL |
| 4. LINE 設定 | Console で Webhook URL を設定 | - |

### `.env.local` で環境切り替え

- ローカル: `AGENTCORE_RUNTIME_ENDPOINT=http://localhost:8080` → HTTP 直接呼び出し
- AWS: 未設定 (空) → boto3 + ARN 経由
- コードの `if AGENTCORE_RUNTIME_ENDPOINT:` で自動分岐

---

## 8. デプロイ関連

| 項目 | コマンド |
|------|---------|
| Bootstrap (初回のみ) | `AWS_PROFILE=line-agent npx cdk bootstrap` |
| デプロイ | `AWS_PROFILE=line-agent LINE_CHANNEL_SECRET=xxx LINE_CHANNEL_ACCESS_TOKEN=xxx npx cdk deploy` |
| 差分確認 | `AWS_PROFILE=line-agent npx cdk diff` |
| スタック削除 | `AWS_PROFILE=line-agent npx cdk destroy` |
| リージョン指定 | `CDK_DEFAULT_REGION=ap-northeast-1` |

### デプロイ時の注意

| 注意点 | 詳細 |
|--------|------|
| LINE 環境変数 | デプロイ時に `LINE_CHANNEL_SECRET` と `LINE_CHANNEL_ACCESS_TOKEN` が必要。空だと Lambda が動かない |
| Docker 必須 | AgentCore Runtime のコンテナビルドと Lambda Layer のビルドに Docker が必要 |
| ARM64 | Lambda と Layer は ARM64。ローカルの Docker が ARM エミュレーションに対応している必要あり (Apple Silicon は OK) |
| logRetention 非推奨 | CDK の `logRetention` は deprecated。`logGroup` に移行推奨 (動作には影響なし) |

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
