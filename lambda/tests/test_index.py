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
# invoke_router_agent tests
# ---------------------------------------------------------------------------


def test_invoke_router_agent_local():
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
            patch.object(idx, "_build_google_credentials", return_value=None),
        ):
            result = idx.invoke_router_agent("テスト", "U1234")

        mock_request_cls.assert_called_once()
        call_args = mock_request_cls.call_args
        assert call_args[0][0] == "http://localhost:8080/invocations"
        assert result == "ローカル応答"
    finally:
        idx.AGENTCORE_RUNTIME_ENDPOINT = original


def test_invoke_router_agent_with_credentials():
    """Google 認証情報が payload に含まれること."""
    original = idx.AGENTCORE_RUNTIME_ENDPOINT
    idx.AGENTCORE_RUNTIME_ENDPOINT = "http://localhost:8080"

    fake_creds = {
        "access_token": "tok",
        "refresh_token": "ref",
        "client_id": "cid",
        "client_secret": "csec",
        "expired": False,
    }

    try:
        response_body = json.dumps({"result": "応答"}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with (
            patch("urllib.request.Request") as mock_request_cls,
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch.object(idx, "_build_google_credentials", return_value=fake_creds),
        ):
            result = idx.invoke_router_agent("予定を見せて", "U1234")

        # payload に google_credentials が含まれているか確認
        call_args = mock_request_cls.call_args
        # Request(url, data=..., headers=...) の data を取得
        sent_bytes = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("data")
        sent_data = json.loads(sent_bytes.decode("utf-8"))
        assert sent_data["prompt"] == "予定を見せて"
        assert sent_data["google_credentials"]["access_token"] == "tok"
    finally:
        idx.AGENTCORE_RUNTIME_ENDPOINT = original


def test_invoke_router_agent_boto3():
    """boto3 invoke_agent_runtime が正しいパラメータで呼ばれること."""
    original = idx.AGENTCORE_RUNTIME_ENDPOINT
    idx.AGENTCORE_RUNTIME_ENDPOINT = ""  # AWS ルート

    try:
        mock_client = MagicMock()
        response_body = json.dumps({"result": "AI応答"}).encode("utf-8")
        mock_client.invoke_agent_runtime.return_value = {
            "contentType": "application/json",
            "response": io.BytesIO(response_body),
        }

        with (
            patch.object(idx, "boto3") as mock_boto3,
            patch.object(idx, "_build_google_credentials", return_value=None),
        ):
            mock_boto3.client.return_value = mock_client
            result = idx.invoke_router_agent("テストプロンプト", "U1234")

        call_kwargs = mock_client.invoke_agent_runtime.call_args.kwargs
        payload = json.loads(call_kwargs["payload"].decode("utf-8"))
        assert payload["prompt"] == "テストプロンプト"
        assert "google_credentials" not in payload
        assert result == "AI応答"
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
    """55秒以内なら reply_message が呼ばれること."""
    with (
        patch.object(idx, "get_user_state", return_value=None),
        patch.object(idx, "show_loading") as mock_loading,
        patch.object(idx, "invoke_router_agent", return_value="AI応答テスト") as mock_invoke,
        patch.object(idx, "send_response") as mock_send,
    ):
        event = _make_message_event()
        idx.handle_text_message(event)

        mock_loading.assert_called_once_with("U1234")
        mock_invoke.assert_called_once_with("こんにちは", "U1234")
        mock_send.assert_called_once()


def test_handle_text_message_push_fallback():
    """55秒超なら push_message にフォールバックすること."""
    with (
        patch.object(idx, "get_user_state", return_value=None),
        patch.object(idx, "show_loading"),
        patch.object(idx, "invoke_router_agent", return_value="遅延応答"),
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


# ---------------------------------------------------------------------------
# convert_agent_response tests
# ---------------------------------------------------------------------------


def test_convert_agent_response_place_search():
    """place_search タイプで Flex カルーセルが返ること."""
    response = json.dumps({
        "type": "place_search",
        "message": "「渋谷カフェ」の検索結果です。",
        "places": [
            {"name": "Cafe A", "lat": "35.658", "lon": "139.701"},
        ],
    })
    messages = idx.convert_agent_response(response, "U1234")
    # TextMessage (message) + FlexMessage
    assert len(messages) == 2


def test_convert_agent_response_place_recommend():
    """place_recommend タイプで Flex カルーセルが返ること."""
    response = json.dumps({
        "type": "place_recommend",
        "message": "おすすめの場所です。",
        "places": [
            {
                "name": "おしゃれカフェ",
                "description": "静かな雰囲気",
                "latitude": 35.661,
                "longitude": 139.703,
                "rating": 4.5,
                "minPrice": 800,
            },
        ],
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 2


def test_convert_agent_response_place_empty():
    """place_search で場所が空の場合テキストが返ること."""
    response = json.dumps({
        "type": "place_search",
        "message": "",
        "places": [],
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 1


# ---------------------------------------------------------------------------
# location_request tests
# ---------------------------------------------------------------------------


def test_convert_agent_response_location_request():
    """location_request タイプで QuickReply 付き TextMessage が返ること."""
    # TextMessage の呼び出し記録をリセット
    idx.TextMessage.reset_mock()

    response = json.dumps({
        "type": "location_request",
        "message": "近くのカフェを探したいので、位置情報を送ってもらえますか？",
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 1
    # TextMessage の呼び出し引数を確認
    call_kwargs = idx.TextMessage.call_args[1]
    assert "位置情報を送ってもらえますか" in call_kwargs["text"]
    # quick_reply が渡されていること
    assert "quick_reply" in call_kwargs
    qr = call_kwargs["quick_reply"]
    assert hasattr(qr, "items")
    assert len(qr.items) == 1
    # LocationAction であること
    item = qr.items[0]
    assert hasattr(item, "action")
    assert hasattr(item.action, "label")


def test_handle_location_message_with_state():
    """waiting_location ステートがある場合、元クエリ + 位置情報で Agent を再呼び出しすること."""
    event = MagicMock()
    event.source.user_id = "U1234"
    event.reply_token = "token_loc"
    event.message.latitude = 35.6812
    event.message.longitude = 139.7671

    waiting_state = {"action": "waiting_location", "original_query": "近くのカフェ教えて"}

    with (
        patch.object(idx, "get_user_state", return_value=waiting_state),
        patch.object(idx, "clear_user_state") as mock_clear,
        patch.object(idx, "show_loading"),
        patch.object(idx, "invoke_router_agent", return_value="AI応答") as mock_invoke,
        patch.object(idx, "send_response") as mock_send,
    ):
        idx.handle_location_message(event)

        mock_clear.assert_called_once_with("U1234")
        # プロンプトに位置情報と元クエリが含まれること
        call_args = mock_invoke.call_args[0]
        prompt = call_args[0]
        assert "緯度35.6812" in prompt
        assert "経度139.7671" in prompt
        assert "近くのカフェ教えて" in prompt
        mock_send.assert_called_once()


def test_handle_location_message_without_state():
    """ステートなしの自発的位置情報送信でデフォルトプロンプトが使われること."""
    event = MagicMock()
    event.source.user_id = "U5678"
    event.reply_token = "token_loc2"
    event.message.latitude = 34.6937
    event.message.longitude = 135.5023

    with (
        patch.object(idx, "get_user_state", return_value=None),
        patch.object(idx, "show_loading"),
        patch.object(idx, "invoke_router_agent", return_value="AI応答") as mock_invoke,
        patch.object(idx, "send_response"),
    ):
        idx.handle_location_message(event)

        call_args = mock_invoke.call_args[0]
        prompt = call_args[0]
        assert "緯度34.6937" in prompt
        assert "経度135.5023" in prompt
        assert "周辺でおすすめ" in prompt


def test_handle_text_message_clears_waiting_location():
    """waiting_location 状態でテキストが来たらステートクリアして通常処理すること."""
    waiting_state = {"action": "waiting_location", "original_query": "近くのカフェ"}

    with (
        patch.object(idx, "get_user_state", return_value=waiting_state),
        patch.object(idx, "clear_user_state") as mock_clear,
        patch.object(idx, "show_loading"),
        patch.object(idx, "invoke_router_agent", return_value="テスト応答") as mock_invoke,
        patch.object(idx, "send_response"),
    ):
        event = _make_message_event(text="渋谷のカフェ教えて")
        idx.handle_text_message(event)

        # ステートがクリアされ、通常テキスト処理が行われること
        mock_clear.assert_called_once_with("U1234")
        mock_invoke.assert_called_once_with("渋谷のカフェ教えて", "U1234")


# ---------------------------------------------------------------------------
# Gmail convert_agent_response tests
# ---------------------------------------------------------------------------


def test_convert_agent_response_email_list():
    """email_list タイプで Flex カルーセルが返ること."""
    response = json.dumps({
        "type": "email_list",
        "message": "受信トレイの一覧です。",
        "emails": [
            {
                "id": "msg1",
                "subject": "テスト件名",
                "from": "sender@example.com",
                "date": "",
                "snippet": "スニペット",
                "label_ids": ["INBOX"],
            },
        ],
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 2  # TextMessage + FlexMessage


def test_convert_agent_response_email_list_empty():
    """email_list で空の場合テキストが返ること."""
    response = json.dumps({
        "type": "email_list",
        "message": "",
        "emails": [],
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 1


def test_convert_agent_response_email_detail():
    """email_detail タイプで Flex が返ること."""
    response = json.dumps({
        "type": "email_detail",
        "message": "メールの内容です。",
        "email": {
            "id": "msg1",
            "subject": "テスト件名",
            "from": "sender@example.com",
            "to": "recipient@example.com",
            "date": "",
            "summary": "要約テスト",
            "has_attachments": False,
            "attachment_count": 0,
        },
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 2  # TextMessage + FlexMessage


def test_convert_agent_response_email_confirm_send():
    """email_confirm_send タイプで Flex が返ること."""
    response = json.dumps({
        "type": "email_confirm_send",
        "message": "以下の内容でメールを送信しますか？",
        "to": "test@example.com",
        "subject": "テスト",
        "body": "テスト本文",
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 2  # TextMessage + FlexMessage


def test_convert_agent_response_email_sent():
    """email_sent タイプでテキストが返ること."""
    response = json.dumps({
        "type": "email_sent",
        "message": "メールを送信しました。",
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 1


def test_convert_agent_response_email_deleted():
    """email_deleted タイプでテキストが返ること."""
    response = json.dumps({
        "type": "email_deleted",
        "message": "メールを削除しました。",
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 1


def test_convert_agent_response_draft_saved():
    """draft_saved タイプでテキストが返ること."""
    response = json.dumps({
        "type": "draft_saved",
        "message": "下書きを保存しました。",
    })
    messages = idx.convert_agent_response(response, "U1234")
    assert len(messages) == 1


def test_invoke_router_agent_passes_line_user_id():
    """payload に line_user_id が含まれること."""
    original = idx.AGENTCORE_RUNTIME_ENDPOINT
    idx.AGENTCORE_RUNTIME_ENDPOINT = "http://localhost:8080"

    try:
        response_body = json.dumps({"result": "応答"}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.read.return_value = response_body
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with (
            patch("urllib.request.Request") as mock_request_cls,
            patch("urllib.request.urlopen", return_value=mock_resp),
            patch.object(idx, "_build_google_credentials", return_value=None),
        ):
            result = idx.invoke_router_agent("テスト", "U5678")

        call_args = mock_request_cls.call_args
        sent_bytes = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("data")
        sent_data = json.loads(sent_bytes.decode("utf-8"))
        assert sent_data["prompt"] == "テスト"
        assert sent_data["line_user_id"] == "U5678"
        assert result == "応答"
    finally:
        idx.AGENTCORE_RUNTIME_ENDPOINT = original


def test_lambda_handler_location_message():
    """LocationMessageContent のディスパッチが正しいこと."""
    from linebot.v3.webhooks import LocationMessageContent, MessageEvent

    mock_event = MessageEvent()
    mock_event.message = LocationMessageContent()
    mock_event.source = MagicMock()
    mock_event.reply_token = "tok"

    with (
        patch.object(idx, "parser") as mock_parser,
        patch.object(idx, "handle_location_message") as mock_handle,
    ):
        mock_parser.parse.return_value = [mock_event]
        event = {"body": '{"events":[]}', "headers": {"x-line-signature": "valid"}}
        result = idx.lambda_handler(event, None)
        assert result["statusCode"] == 200
        mock_handle.assert_called_once_with(mock_event)
