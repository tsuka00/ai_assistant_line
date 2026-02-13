# AgentCore Gateway / Identity / Observability 導入プラン

## 現状の構成

```
LINE
  ↓
API Gateway (REST) → Lambda (Webhook Handler)
  ↓
AgentCore Runtime (Router Agent)
  ├── Calendar Agent (AgentCore Runtime, HTTP /invocations)
  ├── Gmail Agent (AgentCore Runtime, HTTP /invocations)
  ├── Maps Tools (Vercel API, HTTP直接)
  └── Tavily Tools (Tavily API, HTTP直接)

DynamoDB
  ├── GoogleOAuthTokens (自前 OAuth2 トークン管理)
  └── UserSessionState (セッションステート)
```

### 現状の課題
- Google OAuth2 トークン管理が自前実装 (lambda/google_auth.py)
- ツール呼び出しが各エージェント/Lambda に散在（直接 HTTP）
- エージェントの監視・メトリクスが CloudWatch ログ頼り
- ツール認証（Google API, Tavily API）が環境変数ベース

---

## 導入後の構成（目標）

```
LINE
  ↓
API Gateway (REST) → Lambda (Webhook Handler)
  ↓
AgentCore Runtime (Router Agent)
  ↓
AgentCore Gateway ← ツール統合管理
  ├── Google Calendar API (Lambda Target or OpenAPI)
  ├── Gmail API (Lambda Target or OpenAPI)
  ├── Maps API (OpenAPI Target → Vercel)
  └── Tavily API (OpenAPI Target)
  ↓
AgentCore Identity ← 認証統合管理
  ├── Google OAuth2 (Calendar + Gmail スコープ)
  └── (将来的に他の IdP も追加可能)
  ↓
AgentCore Observability ← 監視
  ├── CloudWatch ダッシュボード
  ├── トークン使用量 / レイテンシ / エラー率
  └── OpenTelemetry 互換テレメトリ
```

---

## 1. AgentCore Gateway

### 概要
エージェントが使うツール（API）を統合管理する。現在は各エージェントが直接 HTTP で外部 API を叩いているが、Gateway 経由に統一する。

### 対象ツール → Gateway Target

| ツール | 現在の呼び出し方 | Gateway Target 種別 |
|--------|---------------|-------------------|
| Calendar Agent | HTTP → AgentCore Runtime /invocations | Lambda Target or Agent-to-Agent |
| Gmail Agent | HTTP → AgentCore Runtime /invocations | Lambda Target or Agent-to-Agent |
| search_place / recommend_place | HTTP → Vercel API | OpenAPI Target |
| web_search / extract_content | HTTP → Tavily API | OpenAPI Target |

### 作業項目
1. AgentCore Gateway リソースを CDK で作成
2. 各ツールを Gateway Target として登録
   - Google Calendar API / Gmail API: Lambda Target（既存の Calendar/Gmail Agent を Gateway 経由で呼び出し）
   - Maps API: OpenAPI 仕様から Target 作成
   - Tavily API: OpenAPI 仕様から Target 作成
3. Router Agent (agent/main.py) のツール呼び出しを Gateway 経由に変更
4. IAM ポリシー更新（Gateway 操作権限）

### 検討事項
- Calendar Agent / Gmail Agent は AgentCore Runtime 上で動作中 → Gateway Target として直接 Runtime を登録できるか、Lambda でラップが必要か調査
- MCP サーバーとして既存ツールを公開する方式も選択肢
- Gateway のセマンティック検索（ツール自動発見）を活用するか、明示的なツール指定のままにするか

---

## 2. AgentCore Identity

### 概要
現在 `lambda/google_auth.py` + DynamoDB `GoogleOAuthTokens` テーブルで自前管理している Google OAuth2 を、AgentCore Identity に移行する。

### 現在の認証フロー
```
ユーザー → LINE「連携する」ボタン
  → LIFF → Google OAuth2 同意画面
  → /oauth/callback Lambda → DynamoDB にトークン保存
  → 以降のリクエストで Lambda が DynamoDB からトークン取得 → Agent に渡す
```

### 移行後のフロー（想定）
```
ユーザー → LINE「連携する」ボタン
  → AgentCore Identity の OAuth フロー
  → Identity がトークンを Vault に安全に保存
  → Agent が Identity 経由でトークン取得 → Google API 呼び出し
```

### 作業項目
1. AgentCore Identity に Google を OAuth Provider として登録
   - スコープ: `calendar.events`, `gmail.modify`
2. 既存の OAuth コールバックフロー → Identity のフローに移行
   - LINE LIFF → Identity の認証 URL にリダイレクト
3. Lambda / Agent のトークン取得ロジックを Identity SDK に変更
4. DynamoDB `GoogleOAuthTokens` テーブルを段階的に廃止
5. CDK スタック更新（Identity リソース追加）

### 検討事項
- LINE ユーザーと Identity のユーザー紐付け方法（line_user_id をキーにできるか）
- 既存ユーザーのトークン移行手順（一斉移行 or 再認証）
- LIFF 経由の OAuth フローが Identity と互換性があるか
- Identity の Vault ストレージによるトークンリフレッシュの自動化

---

## 3. AgentCore Observability

### 概要
エージェントの実行状況を可視化する。CloudWatch ダッシュボード + OpenTelemetry 互換。

### リージョン制約
**ap-northeast-1 (東京) では Observability 未対応。**

### 対応方針（3案）

| 案 | 方法 | メリット | デメリット |
|----|------|---------|----------|
| A | 東京リージョン対応を待つ | 追加コストなし | いつ対応するか不明 |
| B | CloudWatch + OTEL 自前構築 | 東京で完結 | 構築・運用コスト |
| C | Observability だけ us-east-1 | AgentCore ネイティブ機能を活用 | クロスリージョン通信 |

### 推奨: 案 A（待ち）→ 暫定で案 B
- AgentCore Runtime は OTEL 互換テレメトリを出力する
- CloudWatch Logs + Metrics で最低限の監視を構築
- Observability が東京対応したら移行

### 作業項目（暫定監視）
1. AgentCore Runtime のログを CloudWatch Logs に集約（現状対応済み）
2. CloudWatch メトリクスフィルター追加（エラー率、レイテンシ）
3. CloudWatch ダッシュボード作成（CDK）
4. アラーム設定（エラー率閾値、レイテンシ閾値）

---

## 優先順位

| 順番 | 項目 | 理由 |
|:---:|------|------|
| 1 | **Gateway** | ツール管理の統一が最も実利が大きい |
| 2 | **Identity** | 既存の自前 OAuth から移行、セキュリティ向上 |
| 3 | **Observability** | 東京未対応のため暫定対応から |

---

## リージョン

| サービス | リージョン |
|---------|----------|
| AgentCore Gateway | ap-northeast-1 ✅ |
| AgentCore Identity | ap-northeast-1 ✅ |
| AgentCore Observability | us-east-1 のみ（東京未対応）|
| AgentCore Runtime | ap-northeast-1 ✅ |
| AgentCore Memory | ap-northeast-1 ✅（※現在 us-east-1 で運用中） |

---

## 未決事項
- [ ] AgentCore Gateway の CDK L2 コンストラクト有無の確認
- [ ] AgentCore Identity と LINE LIFF の OAuth 連携方式
- [ ] Calendar/Gmail Agent を Gateway Target にする具体的な方式
- [ ] Observability の東京リージョン対応時期
- [ ] AgentCore Memory を us-east-1 → ap-northeast-1 に移行するか
