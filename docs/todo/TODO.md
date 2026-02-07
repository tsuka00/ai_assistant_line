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
