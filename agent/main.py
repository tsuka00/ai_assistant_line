"""Router Agent on Bedrock AgentCore Runtime.

Agents as Tools パターン:
- 一般的な質問 → 自分で回答
- カレンダー操作 → calendar_agent ツール経由で Calendar Agent に委譲
"""

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
from strands import Agent, tool
from strands.models import BedrockModel

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたは LINE で動く日本語AIアシスタントです。
ユーザーの質問に丁寧かつ簡潔に回答してください。

【重要】Markdown は絶対に使わないでください（LINE ではレンダリングされません）。
・NG: **太字**、# 見出し、[リンク](URL)、```コードブロック```
・OK: 「・」で箇条書き、【】で強調、改行で区切り

【ルーティングルール — 最優先】
以下のキーワードや意図が含まれる場合は、必ず calendar_agent ツールを呼んでください。
自分で回答せず、必ずツールに委譲してください。質問や確認も不要です。

calendar_agent を呼ぶべきケース:
・予定/スケジュール/カレンダーに関する操作すべて
・「予定を見せて」「予定ある？」「スケジュール確認」→ 予定一覧
・「予定を入れたい」「予定を追加」「○○したい」(予定作成の意図) → 予定作成
・「予定を変更」「時間を変えて」→ 予定変更
・「予定を消して」「キャンセル」→ 予定削除
・「空いてる日は？」「いつが空いてる？」→ 空き時間確認
・「来週」「明日」「今日」などの日時表現 + 行動 → 予定作成
・ユーザーの発言にカレンダー操作の意図が少しでもあれば → calendar_agent

自分で直接回答するケース:
・一般的な質問・雑談・知識系の質問（予定やスケジュールに全く関係ないもの）

calendar_agent ツールを呼んだ場合は、その戻り値をそのまま返してください。加工しないでください。
"""

MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
)

CALENDAR_AGENT_ENDPOINT = os.environ.get("CALENDAR_AGENT_ENDPOINT", "http://localhost:8081")

app = BedrockAgentCoreApp()

# Google 認証情報をリクエストスコープで保持
_google_credentials: dict | None = None
# calendar_agent ツールの生レスポンスを保持（LLM の加工をバイパスするため）
_calendar_agent_result: str | None = None


@tool
def calendar_agent(query: str) -> str:
    """Google Calendar の予定確認・作成・変更・削除・空き時間確認を行うエージェント。
    カレンダーに関する操作はすべてこのツールに委譲してください。"""
    global _calendar_agent_result
    import urllib.request

    payload = {"prompt": query}
    if _google_credentials:
        payload["google_credentials"] = _google_credentials

    url = f"{CALENDAR_AGENT_ENDPOINT.rstrip('/')}/invocations"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=55) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            raw_result = result.get("result", str(result))
    except Exception as e:
        logger.error("Calendar agent call failed: %s", e)
        raw_result = json.dumps(
            {"type": "text", "message": "カレンダーエージェントへの接続に失敗しました。"},
            ensure_ascii=False,
        )

    # LLM が JSON を加工するのを防ぐため、生レスポンスを保持
    _calendar_agent_result = raw_result
    return raw_result


def _build_system_prompt() -> str:
    """現在日時を埋め込んだシステムプロンプトを生成."""
    from datetime import datetime, timedelta, timezone

    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    weekday = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
    date_line = f"現在の日時: {now.strftime('%Y年%m月%d日')}({weekday}) {now.strftime('%H:%M')}"
    return f"{date_line}\n\n{SYSTEM_PROMPT}"


def create_agent() -> Agent:
    """Router Agent を作成."""
    model = BedrockModel(
        model_id=MODEL_ID,
        streaming=True,
    )
    return Agent(
        model=model,
        system_prompt=_build_system_prompt(),
        tools=[calendar_agent],
    )


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Router Agent を呼び出し."""
    global _google_credentials, _calendar_agent_result

    prompt = payload.get("prompt", "")
    if not prompt:
        return {"result": "メッセージが空です。", "status": "error"}

    # リクエストスコープの初期化
    _google_credentials = payload.get("google_credentials")
    _calendar_agent_result = None

    logger.info("Invoking router agent with prompt length: %d", len(prompt))

    agent = create_agent()
    result = agent(prompt)

    # calendar_agent ツールが呼ばれた場合、LLM の加工を無視して生の JSON を返す
    if _calendar_agent_result is not None:
        response_text = _calendar_agent_result
        logger.info("Using raw calendar_agent result (bypassing LLM post-processing)")
    else:
        response_text = str(result)

    logger.info("Router agent response length: %d", len(response_text))

    # クリア
    _google_credentials = None
    _calendar_agent_result = None

    return {"result": response_text, "status": "success"}


if __name__ == "__main__":
    app.run()
