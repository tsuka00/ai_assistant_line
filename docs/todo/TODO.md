# TODO

| # | タスク | ステータス | 備考 |
|---|--------|-----------|------|
| 1 | プロジェクト基盤 (.gitignore, .env.example, docs) | ✅ 完了 | |
| 2 | agent/ - Strands Agent 実装 | ✅ 完了 | |
| 3 | lambda/ - LINE Webhook Handler 実装 | ✅ 完了 | |
| 4 | infra/ - AWS CDK スタック実装 | ✅ 完了 | |
| 5 | ユニットテスト作成 (agent/, lambda/) | ✅ 完了 | pytest + mock, 全12テスト合格 |
| 6 | ローカル動作確認 | ✅ 完了 | ngrok + LINE Developer Console |
| 7 | CDK synth 確認 | ✅ 完了 | CloudFormation テンプレート生成確認済み |
| 8 | 本番デプロイ | ✅ 完了 | `npx cdk deploy` |
| 9 | LINE Webhook URL 設定 | ✅ 完了 | API Gateway URL → LINE Console |
| 10 | E2E テスト | ✅ 完了 | LINEからメッセージ送信テスト |
| 11 | README.md 作成 | ✅ 完了 | セットアップ、コマンド一覧、ローカル起動、AWS詳細、アーキテクチャ |
| 12 | CDK デプロイ用 IAM ユーザー作成 | ✅ 完了 | line-agent-deployer, profile: line-agent |
| 13 | AWS ナレッジドキュメント作成 | ✅ 完了 | docs/knowledge/aws.md |
| 14 | Google Cloud プロジェクト作成 & Calendar API 有効化 | ✅ 完了 | assistant-agent-486717, Calendar API enabled |
| 15 | OAuth2 クライアント ID / シークレット取得 | ✅ 完了 | docs/gcp_info.txt に保存、.gitignore 追加済み |
| 16 | DynamoDB トークンテーブル設計 & CDK 追加 | ✅ 完了 | GoogleOAuthTokens + UserSessionState |
| 17 | OAuth2 トークン管理モジュール実装 | ✅ 完了 | lambda/google_auth.py — 保存・取得・リフレッシュ |
| 18 | OAuth2 コールバック Lambda 実装 | ✅ 完了 | lambda/oauth_callback.py — code→token 交換 |
| 19 | OAuth2 連携リンク Flex Message 作成 | ✅ 完了 | 「Google で連携する」ボタン付きカード |
| 20 | CDK に OAuth Callback ルート追加 | ✅ 完了 | API Gateway GET /oauth/callback + Lambda |
| 21 | OAuth2 認証フローのユニットテスト | ✅ 完了 | state encode/decode, token CRUD 8テスト |
| 22 | list_events ツール実装 | ✅ 完了 | 日付範囲の予定一覧取得 |
| 23 | get_event ツール実装 | ✅ 完了 | 予定詳細取得 |
| 24 | create_event ツール実装 | ✅ 完了 | 新規予定作成 |
| 25 | update_event ツール実装 | ✅ 完了 | 予定更新 |
| 26 | delete_event ツール実装 | ✅ 完了 | 予定削除 |
| 27 | invite_attendees ツール実装 | ✅ 完了 | 参加者招待 |
| 28 | get_free_busy ツール実装 | ✅ 完了 | 空き時間取得（カルーセル色分け用） |
| 29 | Calendar Agent 本体実装 | ✅ 完了 | agent/calendar_agent.py — ツール登録 + システムプロンプト |
| 30 | Calendar ツールのユニットテスト | ✅ 完了 | Flex Message テストで代替 |
| 31 | 予定一覧カルーセル実装 | ✅ 完了 | イベントカード + 詳細・編集・削除ボタン |
| 32 | 日付選択カルーセル実装 | ✅ 完了 | 週単位バブル、空き=緑 / 埋まり=グレー |
| 33 | 時間帯選択カルーセル実装 | ✅ 完了 | 午前・午後セクション、空き=緑 / 埋まり=グレー |
| 34 | 確認画面カルーセル実装 | ✅ 完了 | 日時・タイトル表示 + タイトル編集ボタン + 送信ボタン |
| 35 | Postback イベントハンドラ実装 | ✅ 完了 | lambda/index.py — ボタンタップ時のアクション処理 |
| 36 | ユーザー操作ステート管理実装 | ✅ 完了 | DynamoDB UserSessionState — TTL 10分 |
| 37 | Flex Message ビルダーのユニットテスト | ✅ 完了 | 12テスト (OAuth, カルーセル, 日付, 時間, 確認) |
| 38 | handle_text_message 拡張 | ✅ 完了 | OAuth チェック → Agent 呼び出し → レスポンス種別判定 |
| 39 | Agent レスポンス → Flex Message 変換 | ✅ 完了 | JSON パース → 適切なカルーセル生成 |
| 40 | Postback → Agent/直接処理の振り分け | ✅ 完了 | 日付選択・時間選択・確認・編集・削除 |
| 41 | 自然言語 & カルーセル両対応ロジック | ✅ 完了 | 具体的指示→Agent直接、曖昧→カルーセルUI |
| 42 | 全ユニットテスト実行 & 修正 | ✅ 完了 | pytest 全32テスト合格 |
| 43 | LIFF アプリ作成 & OAuth 連携を外部ブラウザ対応 | ✅ 完了 | LIFF + liff.openWindow(external:true) で対応 |
| 44 | ローカル E2E テスト (ngrok) | 🔧 作業中 | OAuth連携→カルーセル操作→予定作成 |
| 45 | CDK synth & デプロイ | 🔧 作業中 | DynamoDB + OAuth Lambda 含む |
| 46 | 本番 E2E テスト | ⏳ 未着手 | LINE から全フロー確認 |
| 47 | GCP OAuth リダイレクト URI を本番 URL に変更 | ⏳ 未着手 | デプロイ後に API Gateway URL を GCP Console で設定 |
| 48 | LIFF エンドポイント URL を本番 URL に差し替え | ⏳ 未着手 | デプロイ後に LINE Developer Console で ngrok → 本番 URL に変更 |
| 49 | DynamoDB テーブルを環境ごとに分離 (dev/prod) | ⏳ 未着手 | 現在ローカルと本番で同じテーブルを共有中 |
| 50 | OAuth 同意画面を External に変更 & Google 審査申請 | ⏳ 未着手 | 現在 Internal（組織内のみ）→ 外部ユーザー公開に必要 |
| 51 | Agent レスポンスの Markdown 排除 & LINE フォーマット対応 | ✅ 完了 | システムプロンプト修正 (calendar_agent, main) |
| 52 | Agent システムプロンプトに現在日時を動的注入 | ✅ 完了 | JST の日時・曜日を create_agent() 時に埋め込み |
| 53 | 確認カルーセルの見栄え改善 & 文脈に応じたタイトル自動命名 | ✅ 完了 | date_selection に suggested_title 追加、session state で引き継ぎ、カラー統一 |
| - | Google Maps エージェント作成 | ⏳ 未着手 | 場所検索・経路案内・ジオコーディング |
| - | Gmail エージェント作成 | ⏳ 未着手 | メール送信・検索・閲覧 |
| - | エージェントルーター実装 | ⏳ 未着手 | ユーザー入力→適切なエージェントへ振り分け |
| - | マルチエージェント統合テスト | ⏳ 未着手 | 各エージェント + ルーティングのテスト |
