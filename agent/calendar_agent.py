"""Google Calendar Agent on Bedrock AgentCore Runtime."""

import json
import logging
import os

# ローカル開発時は .env.local を読み込む
try:
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
    load_dotenv(dotenv_path=env_path, override=True)
except ImportError:
    pass

from bedrock_agentcore import BedrockAgentCoreApp
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from strands import Agent
from strands.models import BedrockModel

from tools.google_calendar import (
    create_event,
    delete_event,
    get_event,
    get_free_busy,
    invite_attendees,
    list_events,
    set_credentials,
    update_event,
)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたは Google Calendar を操作する日本語AIアシスタントです。
ユーザーのカレンダー操作リクエストに応じて、適切なツールを呼び出してください。

## レスポンスルール

ツールの結果をもとに、必ず以下の JSON 形式でレスポンスしてください。
JSON 以外のテキストは含めないでください。

### 予定一覧を表示する場合:
```json
{"type": "calendar_events", "message": "今日の予定は3件です。", "events": [...]}
```

### 予定を作成した場合:
```json
{"type": "event_created", "message": "予定を作成しました。", "event": {...}}
```

### 予定を更新した場合:
```json
{"type": "event_updated", "message": "予定を更新しました。", "event": {...}}
```

### 予定を削除した場合:
```json
{"type": "event_deleted", "message": "予定を削除しました。"}
```

### 空き時間確認 / 予定作成の開始（ユーザーが日付未指定の場合）:
```json
{"type": "date_selection", "message": "日付を選択してください。", "busy_slots": [...]}
```

### 通常のテキスト応答:
```json
{"type": "text", "message": "応答テキスト"}
```

## 判断基準
- ユーザーが具体的な日時・タイトルを指定した場合 → 直接 create_event を呼ぶ
- ユーザーが「予定を追加したい」「空いてる日は？」など曖昧な場合 → get_free_busy で空き状況を取得し date_selection で返す
- 予定の確認・一覧 → list_events を呼んで calendar_events で返す
"""

MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

app = BedrockAgentCoreApp()


def _setup_credentials(payload: dict) -> bool:
    """payload 内の google_credentials から認証情報をセットアップ."""
    creds_data = payload.get("google_credentials")
    if not creds_data:
        return False

    creds = Credentials(
        token=creds_data.get("access_token"),
        refresh_token=creds_data.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URL,
        client_id=creds_data.get("client_id", ""),
        client_secret=creds_data.get("client_secret", ""),
    )

    # 期限切れの場合はリフレッシュ
    if creds_data.get("expired", False) and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())

    set_credentials(creds)
    return True


def create_agent() -> Agent:
    """Calendar Agent を作成."""
    model = BedrockModel(
        model_id=MODEL_ID,
        streaming=True,
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            list_events,
            get_event,
            create_event,
            update_event,
            delete_event,
            invite_attendees,
            get_free_busy,
        ],
    )


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Calendar Agent を呼び出し."""
    prompt = payload.get("prompt", "")
    if not prompt:
        return {"result": '{"type": "text", "message": "メッセージが空です。"}', "status": "error"}

    # Google 認証情報セットアップ
    if not _setup_credentials(payload):
        return {
            "result": '{"type": "text", "message": "Google 認証情報がありません。"}',
            "status": "error",
        }

    logger.info("Invoking calendar agent with prompt length: %d", len(prompt))

    agent = create_agent()
    result = agent(prompt)

    response_text = str(result)
    logger.info("Calendar agent response length: %d", len(response_text))

    # JSON レスポンスの検証
    try:
        parsed = json.loads(response_text)
        return {"result": response_text, "status": "success"}
    except json.JSONDecodeError:
        # JSON でない場合はテキストとしてラップ
        fallback = json.dumps({"type": "text", "message": response_text}, ensure_ascii=False)
        return {"result": fallback, "status": "success"}


if __name__ == "__main__":
    import argparse

    parser_cli = argparse.ArgumentParser()
    parser_cli.add_argument("--port", type=int, default=8081)
    args = parser_cli.parse_args()
    app.run(port=args.port)
