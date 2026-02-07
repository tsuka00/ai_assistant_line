"""LINE Webhook Handler - Lambda + ローカル FastAPI 兼用."""

import json
import logging
import os
import time
import uuid

import boto3
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    ShowLoadingAnimationRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# LINE SDK
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

parser = WebhookParser(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# AgentCore
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# ローカル開発用
AGENTCORE_RUNTIME_ENDPOINT = os.environ.get("AGENTCORE_RUNTIME_ENDPOINT", "")

TIMEOUT_SECONDS = 55  # Lambda 60s timeout の 5s 手前


def invoke_agent(prompt: str) -> str:
    """AgentCore Runtime を呼び出してAI応答を取得."""
    client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

    payload = json.dumps({"prompt": prompt}).encode("utf-8")

    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=str(uuid.uuid4()),
        payload=payload,
        contentType="application/json",
    )

    # レスポンスを読み取り
    content_type = response.get("contentType", "")
    body = response["response"].read().decode("utf-8")

    if "application/json" in content_type:
        result = json.loads(body)
        return result.get("result", body)

    return body


def invoke_agent_local(prompt: str) -> str:
    """ローカル開発用: 直接 AgentCore エンドポイントを呼び出し."""
    import urllib.request

    endpoint = AGENTCORE_RUNTIME_ENDPOINT.rstrip("/")
    url = f"{endpoint}/invocations"

    data = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("result", str(result))


def show_loading(user_id: str) -> None:
    """LINE ローディングアニメーション表示."""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.show_loading_animation(
            ShowLoadingAnimationRequest(chatId=user_id, loadingSeconds=60)
        )


def reply_message(reply_token: str, text: str) -> None:
    """LINE reply message."""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                replyToken=reply_token,
                messages=[TextMessage(text=text)],
            )
        )


def push_message(user_id: str, text: str) -> None:
    """LINE push message (reply token 期限切れ時のフォールバック)."""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.push_message(
            PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=text)],
            )
        )


def handle_text_message(event: MessageEvent) -> None:
    """テキストメッセージを処理."""
    user_id = event.source.user_id
    user_text = event.message.text
    reply_token = event.reply_token

    logger.info("Received message from %s: %s", user_id, user_text[:50])

    # 1. ローディングアニメーション表示
    try:
        show_loading(user_id)
    except Exception:
        logger.warning("Failed to show loading animation", exc_info=True)

    # 2. AI 応答を取得
    start_time = time.time()
    try:
        if AGENTCORE_RUNTIME_ENDPOINT:
            ai_response = invoke_agent_local(user_text)
        else:
            ai_response = invoke_agent(user_text)
    except Exception:
        logger.error("Agent invocation failed", exc_info=True)
        ai_response = "申し訳ありません。エラーが発生しました。もう一度お試しください。"

    elapsed = time.time() - start_time
    logger.info("Agent response in %.1fs", elapsed)

    # 3. 返信 (タイムアウト対策: 55秒超えたら Push API)
    try:
        if elapsed < TIMEOUT_SECONDS:
            reply_message(reply_token, ai_response)
        else:
            push_message(user_id, ai_response)
    except Exception:
        logger.warning("Reply failed, falling back to push", exc_info=True)
        try:
            push_message(user_id, ai_response)
        except Exception:
            logger.error("Push message also failed", exc_info=True)


# ---------- Lambda Handler ----------


def lambda_handler(event, context):
    """API Gateway proxy event を処理."""
    body = event.get("body", "")
    signature = (event.get("headers") or {}).get("x-line-signature", "")

    if not signature:
        return {"statusCode": 400, "body": "Missing signature"}

    try:
        events = parser.parse(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        return {"statusCode": 403, "body": "Invalid signature"}

    for ev in events:
        if isinstance(ev, MessageEvent) and isinstance(
            ev.message, TextMessageContent
        ):
            handle_text_message(ev)

    return {"statusCode": 200, "body": "OK"}


# ---------- ローカル開発 (FastAPI) ----------

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    # 環境変数を再読み込み
    CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
    CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    AGENTCORE_RUNTIME_ENDPOINT = os.environ.get(
        "AGENTCORE_RUNTIME_ENDPOINT", "http://localhost:8080"
    )

    # グローバル変数を更新
    parser.__init__(CHANNEL_SECRET)
    configuration.access_token = CHANNEL_ACCESS_TOKEN

    from fastapi import FastAPI, Header, Request

    app = FastAPI(title="LINE Webhook (Local)")

    @app.post("/callback")
    async def callback(
        request: Request, x_line_signature: str = Header(default="")
    ):
        body = (await request.body()).decode("utf-8")

        try:
            events = parser.parse(body, x_line_signature)
        except InvalidSignatureError:
            return {"status": "error", "message": "Invalid signature"}

        for ev in events:
            if isinstance(ev, MessageEvent) and isinstance(
                ev.message, TextMessageContent
            ):
                handle_text_message(ev)

        return {"status": "ok"}

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
