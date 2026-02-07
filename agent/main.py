"""Strands Agent on Bedrock AgentCore Runtime."""

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
from strands import Agent
from strands.models import BedrockModel

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "あなたは親切で知識豊富な日本語AIアシスタントです。"
    "ユーザーの質問に丁寧かつ簡潔に回答してください。"
    "回答はLINEメッセージとして読みやすい長さに収めてください。"
    "\n\n"
    "【重要】Markdown は絶対に使わないでください（LINE ではレンダリングされません）。"
    "NG: **太字**、# 見出し、[リンク](URL)、```コードブロック```。"
    "OK: 「・」で箇条書き、【】で強調、改行で区切り。"
)

MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "global.anthropic.claude-opus-4-6-v1",
)

app = BedrockAgentCoreApp()


def create_agent() -> Agent:
    """Create a Strands Agent with Bedrock model."""
    model = BedrockModel(
        model_id=MODEL_ID,
        streaming=True,
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
    )


@app.entrypoint
def invoke(payload: dict) -> dict:
    """Process user input and return a response."""
    prompt = payload.get("prompt", "")
    if not prompt:
        return {"result": "メッセージが空です。", "status": "error"}

    logger.info("Invoking agent with prompt length: %d", len(prompt))

    agent = create_agent()
    result = agent(prompt)

    response_text = str(result)
    logger.info("Agent response length: %d", len(response_text))

    return {"result": response_text, "status": "success"}


if __name__ == "__main__":
    app.run()
