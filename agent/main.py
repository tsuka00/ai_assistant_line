"""Router Agent on Bedrock AgentCore Runtime.

Agents as Tools パターン:
- 一般的な質問 → 自分で回答
- カレンダー操作 → calendar_agent ツール経由で Calendar Agent に委譲
- メール操作 → gmail_agent ツール経由で Gmail Agent に委譲
- 場所検索 → search_place ツール経由で Vercel API に委譲
- おすすめ場所 → recommend_place ツール経由で Vercel API に委譲
- Web 検索 → web_search / extract_content ツール経由で Tavily API
"""

import json
import logging
import os
import urllib.request
from datetime import datetime, timedelta, timezone

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
from tools.google_maps import (
    clear_maps_result,
    get_maps_result,
    recommend_place,
    request_location,
    search_place,
)
from tools.tavily_search import extract_content, web_search

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

jst = timezone(timedelta(hours=9))

# --- Bedrock AgentCore Memory (条件付き) ---
BEDROCK_MEMORY_ID = os.environ.get("BEDROCK_MEMORY_ID", "")
_memory_available = False
try:
    from bedrock_agentcore.memory.integrations.strands import AgentCoreMemorySessionManager
    from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
    _memory_available = bool(BEDROCK_MEMORY_ID)
except ImportError:
    AgentCoreMemorySessionManager = None  # type: ignore[assignment,misc]
    AgentCoreMemoryConfig = None  # type: ignore[assignment,misc]
    if BEDROCK_MEMORY_ID:
        logger.warning("bedrock_agentcore.memory not available, running without memory")


def _build_session_manager(line_user_id: str):
    """Memory が利用可能なら AgentCoreMemorySessionManager を構築."""
    if not _memory_available or not BEDROCK_MEMORY_ID:
        return None
    today = datetime.now(jst).strftime("%Y-%m-%d")
    config = AgentCoreMemoryConfig(
        memory_id=BEDROCK_MEMORY_ID,
        session_id=f"{line_user_id}-{today}",
        actor_id=line_user_id,
    )
    return AgentCoreMemorySessionManager(
        agentcore_memory_config=config,
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
    )

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

gmail_agent を呼ぶべきケース:
・メール/Gmail/受信トレイに関する操作すべて
・「メール見せて」「受信トレイ」「メール一覧」→ メール一覧
・「メール送って」「○○にメール」→ メール送信
・「メール検索」「○○からのメール」→ メール検索
・「メール削除」「メール消して」→ メール削除
・「既読にして」「スターつけて」「ラベルを変更」→ ラベル管理
・「下書き保存」→ 下書き
・ユーザーの発言にメール操作の意図が少しでもあれば → gmail_agent

search_place を呼ぶべきケース:
・特定の場所・店舗・住所を検索したいとき
・「東京タワーの場所は？」「新宿駅近くのラーメン屋」「渋谷カフェ」
・場所名やエリア + ジャンルで探している場合 → search_place

recommend_place を呼ぶべきケース:
・目的や雰囲気に合ったおすすめ場所を探したいとき
・「デートにおすすめの渋谷のカフェ」「大阪で安くて美味しいお好み焼き屋」
・「子連れで行けるレストラン」「静かに作業できるカフェ」
・具体的な店名ではなく、条件や好みでの提案を求めている場合 → recommend_place

request_location を呼ぶべきケース:
・「近くの」「ここら辺の」「この辺の」「周辺の」など、ユーザーの現在地に依存する質問
・エリア名が明示されていない場所検索・おすすめリクエスト → request_location
・注意: 「渋谷のカフェ」のようにエリアが明示されている場合は直接 search_place / recommend_place を使う

web_search を呼ぶべきケース:
・最新ニュースや時事問題について聞かれたとき
・「調べて」「検索して」「最新の○○」などの表現
・LLM の知識だけでは回答できない最新情報が必要なとき
・特定のトピックについて詳しい情報が欲しいとき

extract_content を呼ぶべきケース:
・ユーザーが URL を共有して「この記事を要約して」と聞いたとき
・web_search の結果をさらに詳しく確認したいとき

【位置情報の扱い】
・プロンプトに「[ユーザーの現在地: 緯度XX, 経度XX]」が含まれている場合はその座標を使って search_place / recommend_place を呼ぶ
・位置情報が含まれている場合は request_location を呼ばない

自分で直接回答するケース:
・一般的な質問・雑談・知識系の質問（予定・場所検索・Web検索に全く関係ないもの）

【記憶機能について】
あなたはユーザーとの過去の会話を記憶しています。
・ユーザーの名前、好み、習慣などを覚えている場合は自然に活用してください
・「前に話した○○」のような参照があれば記憶から思い出してください
・ただし記憶を無理に言及する必要はありません。自然な会話を優先してください

calendar_agent ツールを呼んだ場合は、その戻り値をそのまま返してください。加工しないでください。
gmail_agent ツールを呼んだ場合は、その戻り値をそのまま返してください。加工しないでください。
search_place / recommend_place ツールを呼んだ場合も、その戻り値をそのまま返してください。加工しないでください。
web_search / extract_content ツールの結果は、内容を読み取り、ユーザーにわかりやすく自然な日本語で要約して回答してください。（他のツールと異なり、そのまま返さないでください）
"""

MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
)

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


CALENDAR_AGENT_ENDPOINT = os.environ.get("CALENDAR_AGENT_ENDPOINT", "http://localhost:8081")
GMAIL_AGENT_ENDPOINT = os.environ.get("GMAIL_AGENT_ENDPOINT", "http://localhost:8082")

app = BedrockAgentCoreApp()

# Google 認証情報をリクエストスコープで保持
_google_credentials: dict | None = None
# calendar_agent / gmail_agent ツールの生レスポンスを保持（LLM の加工をバイパスするため）
_calendar_agent_result: str | None = None
_gmail_agent_result: str | None = None


@tool
def calendar_agent(query: str) -> str:
    """Google Calendar の予定確認・作成・変更・削除・空き時間確認を行うエージェント。
    カレンダーに関する操作はすべてこのツールに委譲してください。"""
    global _calendar_agent_result

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


@tool
def gmail_agent(query: str) -> str:
    """Gmail のメール確認・検索・送信・削除・ラベル管理・下書き保存を行うエージェント。
    メールに関する操作はすべてこのツールに委譲してください。"""
    global _gmail_agent_result

    payload = {"prompt": query}
    if _google_credentials:
        payload["google_credentials"] = _google_credentials

    url = f"{GMAIL_AGENT_ENDPOINT.rstrip('/')}/invocations"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=55) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            raw_result = result.get("result", str(result))
    except Exception as e:
        logger.error("Gmail agent call failed: %s", e)
        raw_result = json.dumps(
            {"type": "text", "message": "メールエージェントへの接続に失敗しました。"},
            ensure_ascii=False,
        )

    # LLM が JSON を加工するのを防ぐため、生レスポンスを保持
    _gmail_agent_result = raw_result
    return raw_result


def _build_system_prompt() -> str:
    """現在日時を埋め込んだシステムプロンプトを生成."""
    now = datetime.now(jst)
    weekday = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
    date_line = f"現在の日時: {now.strftime('%Y年%m月%d日')}({weekday}) {now.strftime('%H:%M')}"
    return f"{date_line}\n\n{SYSTEM_PROMPT}"


def create_agent(session_manager=None) -> Agent:
    """Router Agent を作成."""
    model = BedrockModel(
        model_id=MODEL_ID,
        streaming=True,
    )
    kwargs = {
        "model": model,
        "system_prompt": _build_system_prompt(),
        "tools": [calendar_agent, gmail_agent, search_place, recommend_place, request_location, web_search, extract_content],
    }
    if session_manager is not None:
        kwargs["session_manager"] = session_manager
    return Agent(**kwargs)


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Router Agent を呼び出し."""
    global _google_credentials, _calendar_agent_result, _gmail_agent_result

    prompt = payload.get("prompt", "")
    if not prompt:
        return {"result": "メッセージが空です。", "status": "error"}

    # リクエストスコープの初期化
    _google_credentials = payload.get("google_credentials")
    _calendar_agent_result = None
    _gmail_agent_result = None
    clear_maps_result()

    logger.info("Invoking router agent with prompt length: %d", len(prompt))

    # Memory session manager の構築
    session_manager = None
    line_user_id = payload.get("line_user_id")
    if line_user_id:
        try:
            session_manager = _build_session_manager(line_user_id)
        except Exception:
            logger.warning("Failed to build session manager, continuing without memory", exc_info=True)

    agent = create_agent(session_manager=session_manager)
    result = agent(prompt)

    # ツールが呼ばれた場合、LLM の加工を無視して生の JSON を返す
    maps_result = get_maps_result()
    if _calendar_agent_result is not None:
        response_text = _calendar_agent_result
        logger.info("Using raw calendar_agent result (bypassing LLM post-processing)")
    elif _gmail_agent_result is not None:
        response_text = _gmail_agent_result
        logger.info("Using raw gmail_agent result (bypassing LLM post-processing)")
    elif maps_result is not None:
        response_text = maps_result
        logger.info("Using raw maps_agent result (bypassing LLM post-processing)")
    else:
        response_text = _sanitize_response(str(result))

    logger.info("Router agent response length: %d", len(response_text))

    # クリア
    _google_credentials = None
    _calendar_agent_result = None
    _gmail_agent_result = None
    clear_maps_result()

    return {"result": response_text, "status": "success"}


if __name__ == "__main__":
    app.run()
