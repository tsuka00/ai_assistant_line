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
├── agent/          # Strands Agent (BedrockAgentCoreApp)
├── lambda/         # LINE Webhook Handler (Lambda)
├── infra/          # AWS CDK スタック
├── docs/
│   ├── todo/       # タスク管理
│   └── knowledge/  # 開発ルール・ナレッジ
├── conftest.py     # テスト用モジュール登録
├── requirements-dev.txt  # テスト用依存パッケージ
└── pyproject.toml  # pytest 設定
```
