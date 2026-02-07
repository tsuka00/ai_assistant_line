"""Tests for lambda/index.py."""

import io
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# "lambda" is a Python keyword, so we cannot use normal import syntax.
# The module is pre-registered in sys.modules by conftest.py as "lambda.index".
idx = sys.modules["lambda.index"]


# ---------------------------------------------------------------------------
# Lambda Handler tests
# ---------------------------------------------------------------------------


def test_lambda_handler_missing_signature():
    """signature なしで 400 が返ること."""
    with patch.object(idx, "parser") as mock_parser:
        event = {"body": "{}", "headers": {}}
        result = idx.lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "Missing signature" in result["body"]


def test_lambda_handler_invalid_signature():
    """不正な signature で 403 が返ること."""
    from linebot.v3.exceptions import InvalidSignatureError

    with patch.object(idx, "parser") as mock_parser:
        mock_parser.parse.side_effect = InvalidSignatureError("bad sig")
        event = {"body": "{}", "headers": {"x-line-signature": "invalid"}}
        result = idx.lambda_handler(event, None)
        assert result["statusCode"] == 403
        assert "Invalid signature" in result["body"]


def test_lambda_handler_valid_request():
    """正常リクエストで 200 が返ること."""
    from linebot.v3.webhooks import MessageEvent, TextMessageContent

    # Create real instances so isinstance() checks pass in lambda_handler
    mock_event = MessageEvent()
    mock_event.message = TextMessageContent()
    mock_event.source = MagicMock()
    mock_event.reply_token = "tok"

    with (
        patch.object(idx, "parser") as mock_parser,
        patch.object(idx, "handle_text_message") as mock_handle,
    ):
        mock_parser.parse.return_value = [mock_event]
        event = {"body": '{"events":[]}', "headers": {"x-line-signature": "valid"}}
        result = idx.lambda_handler(event, None)
        assert result["statusCode"] == 200
        mock_handle.assert_called_once_with(mock_event)


# ---------------------------------------------------------------------------
# invoke_agent (boto3) test
# ---------------------------------------------------------------------------


def test_invoke_agent_boto3():
    """boto3 invoke_agent_runtime が正しいパラメータで呼ばれること."""
    mock_client = MagicMock()
    response_body = json.dumps({"result": "AI応答"}).encode("utf-8")
    mock_client.invoke_agent_runtime.return_value = {
        "contentType": "application/json",
        "response": io.BytesIO(response_body),
    }

    with patch.object(idx, "boto3") as mock_boto3:
        mock_boto3.client.return_value = mock_client
        result = idx.invoke_agent("テストプロンプト")

    mock_boto3.client.assert_called_once_with(
        "bedrock-agentcore", region_name="us-east-1"
    )
    call_kwargs = mock_client.invoke_agent_runtime.call_args.kwargs
    payload = json.loads(call_kwargs["payload"].decode("utf-8"))
    assert payload["prompt"] == "テストプロンプト"
    assert call_kwargs["contentType"] == "application/json"
    assert result == "AI応答"


# ---------------------------------------------------------------------------
# invoke_agent_local test
# ---------------------------------------------------------------------------


def test_invoke_agent_local():
    """ローカルエンドポイントへの HTTP 呼び出しが正しいこと."""
    original = idx.AGENTCORE_RUNTIME_ENDPOINT
    idx.AGENTCORE_RUNTIME_ENDPOINT = "http://localhost:8080"

    try:
        response_body = json.dumps({"result": "ローカル応答"}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with (
            patch("urllib.request.Request") as mock_request_cls,
            patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            result = idx.invoke_agent_local("テスト")

        mock_request_cls.assert_called_once()
        call_args = mock_request_cls.call_args
        assert call_args[0][0] == "http://localhost:8080/invocations"
        assert result == "ローカル応答"
    finally:
        idx.AGENTCORE_RUNTIME_ENDPOINT = original


# ---------------------------------------------------------------------------
# handle_text_message tests
# ---------------------------------------------------------------------------


def _make_message_event(user_id="U1234", text="こんにちは", reply_token="token123"):
    """テスト用 MessageEvent を作成."""
    event = MagicMock()
    event.source.user_id = user_id
    event.message.text = text
    event.reply_token = reply_token
    return event


def test_handle_text_message_reply():
    """55秒以内なら reply_message が呼ばれること (非カレンダー)."""
    original = idx.AGENTCORE_RUNTIME_ENDPOINT
    idx.AGENTCORE_RUNTIME_ENDPOINT = ""  # boto3 ルート

    try:
        with (
            patch.object(idx, "get_user_state", return_value=None),
            patch.object(idx, "show_loading") as mock_loading,
            patch.object(idx, "invoke_agent", return_value="AI応答テスト") as mock_invoke,
            patch.object(idx, "send_response") as mock_send,
        ):
            event = _make_message_event()
            idx.handle_text_message(event)

            mock_loading.assert_called_once_with("U1234")
            mock_invoke.assert_called_once_with("こんにちは")
            mock_send.assert_called_once()
    finally:
        idx.AGENTCORE_RUNTIME_ENDPOINT = original


def test_handle_text_message_push_fallback():
    """55秒超なら push_message にフォールバックすること."""
    original = idx.AGENTCORE_RUNTIME_ENDPOINT
    idx.AGENTCORE_RUNTIME_ENDPOINT = ""

    try:
        with (
            patch.object(idx, "get_user_state", return_value=None),
            patch.object(idx, "show_loading"),
            patch.object(idx, "invoke_agent", return_value="遅延応答"),
            patch.object(idx, "reply_message", side_effect=Exception("expired")),
            patch.object(idx, "push_message") as mock_push,
            patch.object(idx, "time") as mock_time,
        ):
            # time.time() を制御して 56 秒経過をシミュレート
            mock_time.time.side_effect = [0.0, 56.0]
            mock_time.strftime = MagicMock()
            event = _make_message_event()
            idx.handle_text_message(event)

            # send_response 内で push にフォールバック
            mock_push.assert_called()
    finally:
        idx.AGENTCORE_RUNTIME_ENDPOINT = original


# ---------------------------------------------------------------------------
# show_loading test
# ---------------------------------------------------------------------------


def test_show_loading():
    """show_loading_animation が正しい引数で呼ばれること."""
    mock_api_client = MagicMock()
    mock_api_client.__enter__ = MagicMock(return_value=mock_api_client)
    mock_api_client.__exit__ = MagicMock(return_value=False)

    mock_api = MagicMock()

    with (
        patch.object(idx, "ApiClient", return_value=mock_api_client),
        patch.object(idx, "MessagingApi", return_value=mock_api) as mock_api_cls,
    ):
        idx.show_loading("U9999")

    mock_api_cls.assert_called_once_with(mock_api_client)
    mock_api.show_loading_animation.assert_called_once()
    call_arg = mock_api.show_loading_animation.call_args[0][0]
    assert call_arg.chat_id == "U9999"
    assert call_arg.loading_seconds == 60
