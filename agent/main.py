"""Strands Agent on Bedrock AgentCore Runtime."""

import logging
import os

from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = os.environ.get(
    "SYSTEM_PROMPT",
    (
        "あなたは親切で知識豊富な日本語AIアシスタントです。"
        "ユーザーの質問に丁寧かつ簡潔に回答してください。"
        "回答はLINEメッセージとして読みやすい長さに収めてください。"
    ),
)

MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
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
