"""OAuth2 コールバック Lambda ハンドラ."""

import json
import logging
import os
from urllib.parse import parse_qs

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    PushMessageRequest,
    TextMessage,
)

import google_auth

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)


def lambda_handler(event, context):
    """API Gateway GET /oauth/callback を処理."""
    params = event.get("queryStringParameters") or {}
    code = params.get("code", "")
    state = params.get("state", "")
    error = params.get("error", "")

    if error:
        logger.error("OAuth error: %s", error)
        return _html_response("認証がキャンセルされました。LINEに戻ってもう一度お試しください。")

    if not code or not state:
        return _html_response("パラメータが不足しています。", status=400)

    # state から LINE user_id を復元・検証
    line_user_id = google_auth.decode_state(state)
    if not line_user_id:
        logger.error("Invalid state parameter")
        return _html_response("無効なリクエストです。", status=400)

    # authorization code → token 交換
    try:
        token_data = google_auth.exchange_code_for_tokens(code)
    except Exception:
        logger.error("Token exchange failed", exc_info=True)
        return _html_response("認証に失敗しました。もう一度お試しください。")

    # DynamoDB に保存
    google_auth.save_tokens(line_user_id, token_data)

    # LINE Push で連携完了を通知
    try:
        _push_completion_message(line_user_id)
    except Exception:
        logger.warning("Failed to push completion message", exc_info=True)

    return _html_response(
        "Google 連携（カレンダー & メール）が完了しました！LINEに戻って「今日の予定は？」や「受信トレイ見せて」と聞いてみてください。"
    )


def _push_completion_message(line_user_id: str) -> None:
    """連携完了メッセージを LINE Push で送信."""
    with ApiClient(configuration) as api_client:
        from linebot.v3.messaging import MessagingApi

        api = MessagingApi(api_client)
        api.push_message(
            PushMessageRequest(
                to=line_user_id,
                messages=[
                    TextMessage(
                        text="Google 連携（カレンダー & メール）が完了しました！\n\n"
                        "「今日の予定は？」「受信トレイ見せて」などと話しかけてみてください。"
                    )
                ],
            )
        )


def _html_response(message: str, status: int = 200) -> dict:
    """HTML レスポンスを返す."""
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Google 連携</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: #f0f2f5;
        }}
        .card {{
            background: white;
            border-radius: 16px;
            padding: 40px;
            max-width: 400px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .card p {{
            color: #333;
            font-size: 16px;
            line-height: 1.6;
        }}
    </style>
</head>
<body>
    <div class="card">
        <p>{message}</p>
    </div>
</body>
</html>"""

    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": html,
    }
