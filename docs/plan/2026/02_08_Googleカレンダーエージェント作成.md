# Google Calendar エージェント作成計画

**作成日**: 2026-02-08

## 要件まとめ

| 項目 | 内容 |
|------|------|
| 機能 | フルCRUD + 参加者招待 |
| LINE 表示 | カルーセル（Flex Message） |
| 認証 | OAuth2（各LINEユーザーが自分のGoogleアカウントを連携） |
| 作成フロー | 具体的指示→Agent直接処理 / 曖昧→カルーセルUI（日付→時間→確認） |
| 色分け | 空き=緑、埋まり=グレー |
| 編集・削除 | テキスト指示 + カルーセルボタン両対応 |

## アーキテクチャ

```
User ── LINE ── API Gateway (REST)
                     │
                Lambda (Python 3.13 / ARM64)
                     │
                     ├─ 1. 署名検証
                     ├─ 2. DynamoDB で Google OAuth2 トークン確認
                     │      ├─ トークンなし → OAuth2 認証リンク送信（Flex Message）
                     │      └─ トークンあり → 3 へ
                     ├─ 3. イベント種別判定
                     │      ├─ TextMessage → handle_text_message
                     │      └─ PostbackEvent → handle_postback（カルーセル操作）
                     ├─ 4. show_loading_animation(60s)
                     ├─ 5. AgentCore Runtime invoke → Calendar Agent
                     │      └─ Strands Agent + Google Calendar Tools
                     ├─ 6. レスポンス種別判定 → Flex Message 変換
                     │      ├─ calendar_events   → 予定一覧カルーセル
                     │      ├─ date_selection     → 日付選択カルーセル
                     │      ├─ time_selection     → 時間帯選択カルーセル
                     │      ├─ event_confirmation → 確認画面カルーセル
                     │      └─ text               → プレーンテキスト
                     └─ 7. reply_message / push_message
```

### OAuth2 コールバック（別ルート）

```
Google OAuth2 → API Gateway GET /oauth/callback
                     │
                Lambda (OAuth Callback Handler)
                     ├─ authorization code → token 交換
                     ├─ DynamoDB にトークン保存 (LINE user_id をキー)
                     └─ LINE Push で「連携完了」通知
```

## OAuth2 認証フロー

```
User                   LINE Bot              Google           DynamoDB
 │                        │                    │                 │
 │── "今日の予定は？" ──→│                    │                 │
 │                        │── トークン確認 ──────────────────→│
 │                        │←── なし ─────────────────────────│
 │←─ 🔗 連携リンク ──────│                    │                 │
 │                        │                    │                 │
 │── リンクをタップ ─────────────────────────→│                 │
 │←── Google 認証画面 ──────────────────────│                 │
 │── 許可 ──────────────────────────────────→│                 │
 │                        │←── callback ──────│                 │
 │                        │── token 保存 ────────────────────→│
 │←── "連携完了！" ───────│                    │                 │
 │                        │                    │                 │
 │── "今日の予定は？" ──→│                    │                 │
 │                        │── トークン取得 ──────────────────→│
 │                        │── Calendar API ──→│                 │
 │                        │←── events ────────│                 │
 │←─ 📅 カルーセル ───────│                    │                 │
```

### OAuth2 設計

| 項目 | 値 |
|------|-----|
| スコープ | `https://www.googleapis.com/auth/calendar` |
| リダイレクト URI | `https://{api-gw-id}.execute-api.{region}.amazonaws.com/prod/oauth/callback` |
| state パラメータ | LINE user_id を暗号化して埋め込み |
| トークン保存先 | DynamoDB `GoogleOAuthTokens` テーブル |
| リフレッシュ | Calendar API 呼び出し前に有効期限チェック → 自動リフレッシュ |

### DynamoDB テーブル: `GoogleOAuthTokens`

| キー | 型 | 説明 |
|------|-----|------|
| `line_user_id` (PK) | String | LINE ユーザー ID |
| `access_token` | String | Google アクセストークン |
| `refresh_token` | String | Google リフレッシュトークン |
| `token_expiry` | Number | トークン有効期限 (Unix timestamp) |
| `google_email` | String | 連携した Google アカウントのメール |
| `created_at` | String | 初回連携日時 (ISO 8601) |
| `updated_at` | String | 最終更新日時 (ISO 8601) |

## Calendar Agent ツール

Strands Agent の `@tool` デコレータで Google Calendar API をラップ。

| ツール名 | 説明 | 主なパラメータ |
|----------|------|---------------|
| `list_events` | 予定一覧を取得 | `date_from`, `date_to`, `max_results` |
| `get_event` | 予定の詳細を取得 | `event_id` |
| `create_event` | 新規予定を作成 | `summary`, `start`, `end`, `description`, `location` |
| `update_event` | 予定を更新 | `event_id`, `summary`, `start`, `end`, ... |
| `delete_event` | 予定を削除 | `event_id` |
| `invite_attendees` | 参加者を招待 | `event_id`, `attendee_emails` |
| `get_free_busy` | 空き時間を取得 | `date_from`, `date_to` — カルーセル色分け用 |

### Agent レスポンス形式

Agent は構造化 JSON を返し、Lambda が Flex Message に変換する。

```json
{
  "type": "calendar_events",
  "message": "今日の予定は3件です。",
  "events": [
    {
      "id": "abc123",
      "summary": "チームミーティング",
      "start": "2026-02-08T10:00:00+09:00",
      "end": "2026-02-08T11:00:00+09:00",
      "location": "会議室A",
      "attendees": ["tanaka@example.com"]
    }
  ]
}
```

## LINE カルーセル UI 設計

### 1. 予定一覧カルーセル

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ 📅 10:00 - 11:00 │  │ 📅 13:00 - 14:00 │  │ 📅 15:00 - 16:00 │
│                  │  │                  │  │                  │
│ チームMTG        │  │ 1on1             │  │ レビュー会       │
│ 📍 会議室A       │  │ 📍 Zoom          │  │ 📍 会議室B       │
│ 👥 3人           │  │ 👥 2人           │  │ 👥 5人           │
│                  │  │                  │  │                  │
│ [詳細][編集][削除]│  │ [詳細][編集][削除]│  │ [詳細][編集][削除]│
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 2. 日付選択カルーセル（予定作成時）

週単位のバブル。空き日=緑ボタン、予定あり=グレーボタン。

```
┌──────────────────┐  ┌──────────────────┐
│ 日付を選択（1週目）│  │ 日付を選択（2週目）│
│ 緑=空き グレー=予定あり│  │                  │
│ ─────────────────│  │ ─────────────────│
│ [■ 2/8 (日) ]     │  │ [■ 2/15(日) ]     │
│ [■ 2/9 (月) ]     │  │ [■ 2/16(月) ]     │
│ [■ 2/10(火) ]     │  │ [□ 2/17(火) ]     │
│ [□ 2/11(水) ]     │  │ [■ 2/18(水) ]     │
│ [■ 2/12(木) ]     │  │ [■ 2/19(木) ]     │
│ [■ 2/13(金) ]     │  │ [□ 2/20(金) ]     │
│ [□ 2/14(土) ]     │  │ [■ 2/21(土) ]     │
└──────────────────┘  └──────────────────┘
  ■=緑(空き)  □=グレー(埋まり)
```

Postback data: `action=select_date&date=2026-02-09`

### 3. 時間帯選択カルーセル

選んだ日付の空き時間を午前/午後で表示。空き=緑、埋まり=グレー。

```
┌─────────────────────┐
│ 時間を選択           │
│ 2月9日（月）         │
│ ────────────────── │
│ 午前                 │
│ [■ 09:00 - 10:00 ]  │
│ [□ 10:00 - 11:00 ]  │
│ [■ 11:00 - 12:00 ]  │
│ ────────────────── │
│ 午後                 │
│ [■ 13:00 - 14:00 ]  │
│ [■ 14:00 - 15:00 ]  │
│ [□ 15:00 - 16:00 ]  │
│ [■ 16:00 - 17:00 ]  │
│ [■ 17:00 - 18:00 ]  │
└─────────────────────┘
  ■=緑(空き)  □=グレー(埋まり)
```

Postback data: `action=select_time&date=2026-02-09&start=09:00&end=10:00`

### 4. 確認画面カルーセル

Agent がタイトルを自動生成。ユーザーは編集可能。

```
┌─────────────────────┐
│ ✅ 予定の確認         │
│ ────────────────── │
│ 📅 2月9日（月）       │
│ 🕐 09:00 - 10:00     │
│ 📝 新しい予定         │
│                      │
│ [タイトル編集] [作成]  │
└─────────────────────┘
```

Postback data:
- 作成: `action=confirm_create&date=2026-02-09&start=09:00&end=10:00&summary=新しい予定`
- 編集: `action=edit_title&date=2026-02-09&start=09:00&end=10:00`

### 5. OAuth2 連携リンク

```
┌──────────────────────────┐
│  🔗 Google Calendar 連携  │
│                          │
│  カレンダー機能を使うには   │
│  Googleアカウントの連携が   │
│  必要です。                │
│                          │
│  [ Google で連携する ]     │
└──────────────────────────┘
```

## ユーザー操作フロー

### A. 自然言語で具体的に指示

```
User: "明日の10時から11時にチームMTGを入れて"
  → Agent が直接 create_event を呼び出し
  → 確認画面カルーセル表示
  → [作成] タップで完了
```

### B. カルーセルで段階的に作成

```
User: "予定を追加したい"
  → Agent が意図を判断 → get_free_busy で空き状況取得
  → 日付選択カルーセル（空き=緑、埋まり=グレー）
  → ユーザーが日付タップ (Postback)
  → 時間帯選択カルーセル（空き=緑、埋まり=グレー）
  → ユーザーが時間タップ (Postback)
  → Agent がタイトルを自動生成
  → 確認画面カルーセル（タイトル編集ボタン付き）
  → [作成] タップで Calendar API に登録
```

### C. 予定の確認

```
User: "今日の予定を教えて"
  → Agent が list_events を呼び出し
  → 予定一覧カルーセル表示（詳細・編集・削除ボタン付き）
```

### D. 編集・削除

```
User: "明日のMTGを14時に変更して"          → Agent が update_event
User: カルーセルの [編集] ボタンをタップ     → Postback → 編集フロー
User: カルーセルの [削除] ボタンをタップ     → Postback → 削除確認 → 削除実行
```

## ディレクトリ構成（追加分）

```
assistant_agent_line/
├── agent/
│   ├── main.py                          # 既存（変更なし）
│   ├── calendar_agent.py                # Calendar Agent 本体
│   └── tools/
│       └── google_calendar.py           # @tool: list/get/create/update/delete/invite/free_busy
│
├── lambda/
│   ├── index.py                         # 既存（Postback 対応・レスポンス変換を追加）
│   ├── oauth_callback.py                # OAuth2 コールバック Lambda
│   ├── google_auth.py                   # OAuth2 トークン管理 (DynamoDB CRUD)
│   └── flex_messages/
│       ├── calendar_carousel.py         # 予定一覧カルーセルビルダー
│       ├── date_picker.py               # 日付選択カルーセルビルダー
│       ├── time_picker.py               # 時間帯選択カルーセルビルダー
│       ├── event_confirm.py             # 確認画面カルーセルビルダー
│       └── oauth_link.py               # OAuth2 連携リンクビルダー
│
├── infra/
│   └── lib/line-agent-stack.ts          # DynamoDB テーブル, OAuth Lambda 追加
│
└── .env.example                         # Google OAuth2 環境変数追加
```

## 環境変数（追加分）

| 変数名 | 用途 | 設定先 |
|--------|------|--------|
| `GOOGLE_CLIENT_ID` | Google OAuth2 クライアント ID | Lambda |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 クライアントシークレット | Lambda (Secrets Manager 推奨) |
| `GOOGLE_REDIRECT_URI` | OAuth2 リダイレクト URI | Lambda |
| `OAUTH_STATE_SECRET` | state パラメータ暗号化キー | Lambda |
| `DYNAMODB_TOKEN_TABLE` | DynamoDB テーブル名 | Lambda / Agent |

## 依存パッケージ（追加分）

**Agent (`agent/requirements.txt`):**
```
google-api-python-client>=2.150.0
google-auth>=2.35.0
google-auth-oauthlib>=1.2.0
```

**Lambda (`lambda/requirements.txt`):**
```
google-auth>=2.35.0
cryptography>=43.0.0
```

## 注意事項

- Google OAuth2 の同意画面は「テスト」モードだとテストユーザーのみ利用可能。本番公開には Google の審査が必要
- Refresh token は初回認証時のみ発行 → `access_type=offline`, `prompt=consent` で確実に取得
- Calendar API クォータ: 1,000,000 queries/day（無料枠で十分）
- DynamoDB のトークンは暗号化保存を推奨（KMS or クライアントサイド暗号化）
- Flex Message のカルーセルは最大 12 バブルまで → 2週間分で十分収まる
- Postback data は最大 300 文字 → アクション情報をコンパクトに設計
