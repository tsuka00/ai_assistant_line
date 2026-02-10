"""Google Gmail Agent on Bedrock AgentCore Runtime."""

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

from tools.google_gmail import (
    delete_email,
    get_email,
    list_emails,
    manage_labels,
    save_draft,
    search_emails,
    send_email,
    set_credentials,
)

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたは Gmail を操作する日本語AIアシスタントです。
ユーザーのメール操作リクエストに応じて、適切なツールを呼び出してください。

【重要】レスポンスは LINE メッセージとして表示されます。
Markdown は絶対に使わないでください（LINE ではレンダリングされません）。
・NG: **太字**、# 見出し、[リンク](URL)、```コードブロック```
・OK: 「・」で箇条書き、【】で強調、改行で区切り

【レスポンスルール】

ツールの結果をもとに、必ず以下の JSON 形式でレスポンスしてください。
JSON 以外のテキストは含めないでください。
"message" フィールドの中身も Markdown 禁止です。プレーンテキストで書いてください。

メール一覧を表示する場合:
{"type": "email_list", "message": "受信トレイのメール10件です。", "emails": [...]}
・emails はツールの戻り値（配列）をそのまま入れてください。

メール詳細を表示する場合:
{"type": "email_detail", "message": "メールの内容です。", "email": {"id": "...", "subject": "...", "from": "...", "to": "...", "date": "...", "summary": "要約テキスト", "has_attachments": true, "attachment_count": 2}}
・summary: メール本文を事実ベースで簡潔に要約すること（元の本文は返さない）
・has_attachments: 添付ファイルがあれば true
・attachment_count: 添付ファイルの数

メール送信前の確認（宛先・件名・本文を確認させる）:
{"type": "email_confirm_send", "message": "以下の内容でメールを送信しますか？", "to": "...", "subject": "...", "body": "..."}
・ユーザーがメール送信を依頼した場合、まずこの確認レスポンスを返す
・ユーザーが「送信して」「OK」「はい」と承認したら send_email を実行

メール送信完了:
{"type": "email_sent", "message": "メールを送信しました。"}

メール削除完了:
{"type": "email_deleted", "message": "メールを削除しました。"}

ラベル更新完了:
{"type": "email_labels_updated", "message": "ラベルを更新しました。"}

下書き保存完了:
{"type": "draft_saved", "message": "下書きを保存しました。"}

通常のテキスト応答:
{"type": "text", "message": "応答テキスト"}

【判断基準】
・「受信トレイ見せて」「メール一覧」→ list_emails
・「○○からのメール」「○○に関するメール」→ search_emails
・「メールの詳細」「メールを読んで」→ get_email
・「メール送って」「○○にメール」→ まず email_confirm_send で確認 → 承認後 send_email
・「メール消して」「削除して」→ delete_email
・「既読にして」「スターつけて」→ manage_labels
・「下書き保存」→ save_draft
"""

MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _sanitize_response(text: str) -> str:
    """LLM レスポンスから JSON 部分を抽出.

    Strands Agent の str(result) にはマークダウンコードブロックや
    前後の説明テキストが含まれることがある。複数の手法で JSON を抽出する。
    """
    stripped = text.strip()

    # 1. そのまま JSON として解析できるならそのまま返す
    try:
        json.loads(stripped)
        return stripped
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Markdown コードブロック除去
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            candidate = stripped[first_newline + 1:]
        else:
            candidate = stripped[3:]
        if candidate.endswith("```"):
            candidate = candidate[:-3].strip()
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. テキスト中の最外 JSON オブジェクトを抽出 ({ ... })
    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = stripped[first_brace:last_brace + 1]
        try:
            json.loads(candidate)
            return candidate
        except (json.JSONDecodeError, TypeError):
            pass

    return stripped

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


def _build_system_prompt() -> str:
    """現在日時を埋め込んだシステムプロンプトを生成."""
    from datetime import datetime, timedelta, timezone

    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    weekday = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
    date_line = f"現在の日時: {now.strftime('%Y年%m月%d日')}({weekday}) {now.strftime('%H:%M')}"
    return f"{date_line}\n\n{SYSTEM_PROMPT}"


def create_agent() -> Agent:
    """Gmail Agent を作成."""
    model = BedrockModel(
        model_id=MODEL_ID,
        streaming=True,
    )
    return Agent(
        model=model,
        system_prompt=_build_system_prompt(),
        tools=[
            list_emails,
            get_email,
            send_email,
            search_emails,
            delete_email,
            manage_labels,
            save_draft,
        ],
    )


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Gmail Agent を呼び出し."""
    prompt = payload.get("prompt", "")
    if not prompt:
        return {"result": '{"type": "text", "message": "メッセージが空です。"}', "status": "error"}

    # Google 認証情報セットアップ
    if not _setup_credentials(payload):
        return {
            "result": '{"type": "oauth_required", "message": "Google 認証が必要です。"}',
            "status": "error",
        }

    logger.info("Invoking gmail agent with prompt length: %d", len(prompt))

    agent = create_agent()
    result = agent(prompt)

    response_text = _sanitize_response(str(result))
    logger.info("Gmail agent response length: %d", len(response_text))

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
    parser_cli.add_argument("--port", type=int, default=8082)
    args = parser_cli.parse_args()
    app.run(port=args.port)
