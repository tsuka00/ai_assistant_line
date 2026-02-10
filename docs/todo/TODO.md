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
| 54 | main.py を Router Agent (Agents as Tools) に改修 | ✅ 完了 | キーワードマッチ廃止、LLM ベースのルーティング + 汎用回答 |
| 55 | Calendar Agent を @tool として Router に登録 | ✅ 完了 | calendar_agent ツール — HTTP 経由で Calendar Agent を呼び出し |
| 56 | Lambda のキーワード振り分けを廃止、Router Agent 一本化 | ✅ 完了 | invoke_router_agent に統一、常に Router Agent を呼ぶ |
| 57 | Google 認証情報の受け渡し設計 | ✅ 完了 | Lambda → Router (_google_credentials) → Calendar の credentials フロー |
| 58 | Router Agent のユニットテスト | ✅ 完了 | 全33テスト合格 (Router + Lambda + Flex + OAuth) |
| 59 | ローカル E2E テスト (Router 経由) | ✅ 完了 | LINE → Lambda → Router → Calendar の全フロー確認済み |
| 60 | agent/tools/google_maps.py 作成 — search_place @tool | ✅ 完了 | GET Vercel /api/search?q={query} を呼び出し、場所一覧を返す |
| 61 | agent/tools/google_maps.py 作成 — recommend_place @tool | ✅ 完了 | POST Vercel /api/ai/recommend を呼び出し、AI おすすめ場所を返す |
| 62 | agent/main.py — search_place / recommend_place をツール登録 | ✅ 完了 | create_agent() の tools[] に追加 |
| 63 | agent/main.py — システムプロンプトにマップ系ルーティングルール追加 | ✅ 完了 | 場所検索→search_place、おすすめ→recommend_place の振り分けルール |
| 64 | .env.example / .env / .env.local に MAPS_API_BASE_URL 追加 | ✅ 完了 | https://myplace-blush.vercel.app |
| 65 | Google Maps @tool のユニットテスト作成 | ⏳ 未着手 | HTTP モック + レスポンス検証 |
| 66 | ローカル E2E テスト (Maps @tool 経由) | ✅ 完了 | LINE → Router → search_place / recommend_place → Flex カルーセル表示確認済み |
| 67 | LINE 内の Maps 表示 UI/UX 検討・実装 | ✅ 完了 | Flex Message カルーセル（静的地図画像付き）、全41テスト合格 |
| 75 | Gmail Agent: OAuth スコープに gmail.modify 追加 | ✅ 完了 | lambda/google_auth.py |
| 76 | Gmail Agent: Gmail ツールモジュール作成 | ✅ 完了 | agent/tools/google_gmail.py — 7ツール |
| 77 | Gmail Agent: Gmail Agent 本体実装 | ✅ 完了 | agent/gmail_agent.py — ポート8082 |
| 78 | Gmail Agent: Dockerfile 作成 | ✅ 完了 | agent/Dockerfile.gmail |
| 79 | Gmail Agent: Router Agent 統合 | ✅ 完了 | agent/main.py — gmail_agent ツール追加 |
| 80 | Gmail Agent: Flex Message ビルダー | ✅ 完了 | email_carousel / email_detail / email_confirm |
| 81 | Gmail Agent: Lambda レスポンス変換 | ✅ 完了 | lambda/index.py — Gmail レスポンス型ハンドリング |
| 82 | Gmail Agent: CDK スタック更新 | ✅ 完了 | infra/lib/line-agent-stack.ts |
| 83 | Gmail Agent: 環境変数・OAuth メッセージ更新 | ✅ 完了 | .env.example, oauth_callback.py |
| 84 | Gmail Agent: ユニットテスト | ✅ 完了 | 全76テスト合格 (Gmail 22テスト追加) |
| 68 | request_location ツール実装 | ✅ 完了 | agent/tools/google_maps.py に切り出し + システムプロンプト更新 |
| 69 | LocationMessage ハンドラ実装 | ✅ 完了 | QuickReply 生成 + DynamoDB ステート管理 + 再呼び出し |
| 70 | conftest.py / テスト追加 | ✅ 完了 | LocationMessageContent スタブ + QuickReply スタブ + 全47テスト合格 |
| 71 | Pseudo-GPS ローカル E2E テスト | ✅ 完了 | ngrok → LINE「近くのカフェ」→ QuickReply → 位置情報 → カルーセル表示確認済み |
| 72 | Maps ツールを agent/tools/google_maps.py に分離 | ✅ 完了 | search_place / recommend_place / request_location を main.py から切り出し |
| 73 | 位置情報リクエストのメッセージトーン改善 | ✅ 完了 | 固定テンプレート廃止、LLM が自然な依頼文を生成する方式に変更 |
| 74 | Maps ナレッジドキュメント作成 | ✅ 完了 | docs/knowledge/maps.md — API仕様・ツール設計・Pseudo-GPSフロー |
| 85 | Markdown コードブロック除去 (sanitize_response) | ✅ 完了 | gmail_agent / calendar_agent / main.py |
| 86 | OAuth トークン再認証 (gmail.modify スコープ) | ✅ 完了 | DynamoDB トークン削除済み → 次回操作時に再連携 |
| 87 | Gmail Agent レスポンス変換問題の調査・修正 | ⏳ 未着手 | LINE→Lambda→Router→Gmail Agent の E2E フローでレスポンスが返らない / JSON が二重ラップされる問題。_sanitize_response 修正済みだが E2E 未検証 |
| 88 | Tavily Web Research: tavily_search.py ツール実装 | ✅ 完了 | web_search + extract_content |
| 89 | Tavily Web Research: Router Agent 統合 | ✅ 完了 | main.py — import、ツール登録、システムプロンプト |
| 90 | Tavily Web Research: CDK 環境変数追加 | ✅ 完了 | TAVILY_API_KEY |
| 91 | Tavily Web Research: ユニットテスト | ✅ 完了 | 全86テスト合格 (Tavily 10テスト追加) |
| 92 | Bedrock AgentCore Memory: conftest.py モック追加 | ✅ 完了 | bedrock_agentcore.memory.* サブモジュールのモック登録 |
| 93 | Bedrock AgentCore Memory: agent/main.py 統合 | ✅ 完了 | import, _build_session_manager, create_agent, invoke 修正, システムプロンプト |
| 94 | Bedrock AgentCore Memory: agent/tests/test_main.py テスト追加 | ✅ 完了 | 7テスト追加 |
| 95 | Bedrock AgentCore Memory: lambda/index.py payload 修正 | ✅ 完了 | line_user_id を payload に追加 |
| 96 | Bedrock AgentCore Memory: lambda/tests/test_index.py テスト追加 | ✅ 完了 | line_user_id テスト |
| 97 | Bedrock AgentCore Memory: requirements.txt 更新 | ✅ 完了 | bedrock-agentcore>=1.2.1 |
| 98 | Bedrock AgentCore Memory: .env / CDK 更新 | ✅ 完了 | BEDROCK_MEMORY_ID 追加, IAM ポリシー |
| 99 | Bedrock AgentCore Memory: テスト実行・修正 | ✅ 完了 | 全94テスト合格 |
| - | マルチエージェント統合テスト | ⏳ 未着手 | 各エージェント + ルーティングのテスト |
