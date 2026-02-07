# 開発ルール

## タスク管理

- **作業開始前に必ず `docs/todo/TODO.md` を更新すること**
  - 新規タスクの場合は行を追加し、ステータスを「🔧 作業中」にする
  - 既存タスクの場合はステータスを「🔧 作業中」に変更する
- **作業完了後にも `docs/todo/TODO.md` を更新すること**
  - ステータスを「✅ 完了」に変更し、備考欄に結果を記載する

## テスト

- テスト実行: `pytest agent/tests/ lambda/tests/ -v`
- `lambda` は Python 予約語のため、通常の import ができない
  - `conftest.py`（ルート）で `importlib` + `sys.modules` を使って動的にモジュール登録している
- LINE SDK の型（`InvalidSignatureError`, `MessageEvent`, `TextMessageContent`）は `isinstance()` / `except` で使われるため、MagicMock ではなく実クラスのスタブが必要
- `BedrockAgentCoreApp.entrypoint` デコレータは pass-through にしないと `invoke` 関数がモックに置き換わる

## プロジェクト構成

```
assistant_agent_line/
├── agent/                         # Strands Agent (BedrockAgentCoreApp)
│   ├── main.py                    # General Agent (port 8080)
│   ├── calendar_agent.py          # Calendar Agent (port 8081)
│   ├── Dockerfile.calendar        # Calendar Agent Docker
│   └── tools/
│       └── google_calendar.py     # 7 Calendar tools (@tool)
├── lambda/                        # LINE Webhook Handler (Lambda)
│   ├── index.py                   # Lambda ハンドラ (Postback, OAuth チェック, Calendar ルーティング)
│   ├── google_auth.py             # OAuth2 トークン管理 (DynamoDB CRUD)
│   ├── google_calendar_api.py     # Calendar API ラッパー
│   ├── oauth_callback.py          # OAuth2 コールバックハンドラ
│   ├── flex_messages/             # Flex Message ビルダー
│   │   ├── oauth_link.py          # OAuth 連携リンクカード
│   │   ├── calendar_carousel.py   # 予定一覧カルーセル
│   │   ├── date_picker.py         # 日付選択
│   │   ├── time_picker.py         # 時間帯選択
│   │   └── event_confirm.py       # 作成/削除 確認画面
│   └── tests/
│       ├── test_index.py
│       ├── test_flex_messages.py
│       └── test_google_auth.py
├── infra/                         # AWS CDK スタック
├── docs/
│   ├── todo/                      # タスク管理
│   ├── knowledge/                 # 開発ルール・ナレッジ
│   └── plan/                      # 開発計画
├── conftest.py                    # テスト用モジュール登録
├── requirements-dev.txt           # テスト用依存パッケージ
└── pyproject.toml                 # pytest 設定
```

## Google OAuth テスト

- OAuth トークンは DynamoDB (`GoogleOAuthTokens`) に保存される
- ローカル開発と本番で同じ DynamoDB テーブルを共有しているため、ローカルで認証したトークンは本番でもそのまま使える
- テスト時は `moto` を使って DynamoDB をモック化する (`test_google_auth.py`)
- `OAUTH_STATE_SECRET` はローカルと本番で同じ値を使用すること (state パラメータの HMAC 検証が失敗するため)

## LIFF

- `LIFF_ID` は `.env.local` に設定する
- LIFF エンドポイント URL は LINE Developer Console で設定し、ngrok ドメイン (ローカル) or 本番 URL と一致させる
- ngrok ドメインが変わるたびに LIFF エンドポイント URL の更新が必要
- ngrok 無料枠では `fetch` 時に `ngrok-skip-browser-warning` ヘッダーを付与する必要がある

## Calendar Agent

- General Agent (port 8080) とは別プロセスで起動する (port 8081)
- ローカル起動: `python agent/calendar_agent.py --port 8081`
- Lambda からは `CALENDAR_AGENT_ENDPOINT` 環境変数で接続先を指定
- Agent のレスポンスは JSON 形式で、`type` フィールドにより Lambda 側で適切な Flex Message に変換される
