"""LINE Webhook Handler - Lambda + ローカル FastAPI 兼用."""

import json
import logging
import os
import time
import uuid
from urllib.parse import parse_qs, unquote

import boto3
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexContainer,
    FlexMessage,
    LocationAction,
    MessagingApi,
    PushMessageRequest,
    QuickReply,
    QuickReplyItem,
    ReplyMessageRequest,
    ShowLoadingAnimationRequest,
    TextMessage,
)
from linebot.v3.webhooks import (
    LocationMessageContent,
    MessageEvent,
    PostbackEvent,
    TextMessageContent,
)

import google_auth
import google_calendar_api
from flex_messages.calendar_carousel import build_events_carousel
from flex_messages.date_picker import build_date_picker
from flex_messages.event_confirm import (
    build_delete_confirmation,
    build_event_confirmation,
)
from flex_messages.email_carousel import build_email_carousel
from flex_messages.email_confirm import build_email_send_confirm
from flex_messages.email_detail import build_email_detail
from flex_messages.place_carousel import build_place_carousel
from flex_messages.time_picker import build_time_picker

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# LINE SDK
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")

parser = WebhookParser(CHANNEL_SECRET)
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# AgentCore (Router Agent)
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AGENTCORE_RUNTIME_ENDPOINT = os.environ.get("AGENTCORE_RUNTIME_ENDPOINT", "")

TIMEOUT_SECONDS = 55  # Lambda 60s timeout の 5s 手前

# DynamoDB ステート管理テーブル
USER_STATE_TABLE = os.environ.get("USER_STATE_TABLE", "UserSessionState")

# LIFF
LIFF_ID = os.environ.get("LIFF_ID", "")


# ========== LINE メッセージ送信 ==========


def show_loading(user_id: str) -> None:
    """LINE ローディングアニメーション表示."""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.show_loading_animation(
            ShowLoadingAnimationRequest(chatId=user_id, loadingSeconds=60)
        )


def reply_message(reply_token: str, messages: list) -> None:
    """LINE reply message. messages は TextMessage or FlexMessage のリスト."""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(replyToken=reply_token, messages=messages)
        )


def push_message(user_id: str, messages: list) -> None:
    """LINE push message."""
    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.push_message(
            PushMessageRequest(to=user_id, messages=messages)
        )


def send_response(reply_token: str, user_id: str, messages: list, elapsed: float = 0) -> None:
    """Reply or Push でメッセージ送信 (タイムアウト対策付き)."""
    try:
        if elapsed < TIMEOUT_SECONDS:
            reply_message(reply_token, messages)
        else:
            push_message(user_id, messages)
    except Exception:
        logger.warning("Reply failed, falling back to push", exc_info=True)
        try:
            push_message(user_id, messages)
        except Exception:
            logger.error("Push message also failed", exc_info=True)


# ========== Agent 呼び出し ==========


def _build_google_credentials(line_user_id: str) -> dict | None:
    """Google 認証情報を取得して dict に変換. 未連携なら None."""
    creds = google_auth.get_google_credentials(line_user_id)
    if not creds:
        return None
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "client_id": google_auth.GOOGLE_CLIENT_ID,
        "client_secret": google_auth.GOOGLE_CLIENT_SECRET,
        "expired": creds.expired if hasattr(creds, "expired") else False,
    }


def invoke_router_agent(prompt: str, line_user_id: str) -> str:
    """Router Agent を呼び出し (Google 認証情報付き)."""
    payload = {"prompt": prompt}

    # Google 認証情報があれば付与（Router → Calendar Agent に転送される）
    google_creds = _build_google_credentials(line_user_id)
    if google_creds:
        payload["google_credentials"] = google_creds

    if AGENTCORE_RUNTIME_ENDPOINT:
        return _invoke_agent_local(payload, AGENTCORE_RUNTIME_ENDPOINT)

    # AWS 環境: AgentCore Runtime 経由
    client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps(payload).encode("utf-8"),
        contentType="application/json",
    )
    body = response["response"].read().decode("utf-8")
    if "application/json" in response.get("contentType", ""):
        result = json.loads(body)
        return result.get("result", body)
    return body


def _invoke_agent_local(payload: dict, endpoint: str) -> str:
    """ローカル開発用: AgentCore エンドポイントに直接アクセス."""
    import urllib.request

    url = f"{endpoint.rstrip('/')}/invocations"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result.get("result", str(result))


# ========== レスポンス → LINE メッセージ変換 ==========


def _build_flex_message(flex_dict: dict):
    """Flex Message dict から LINE SDK の FlexMessage を生成."""
    return FlexMessage(
        alt_text=flex_dict.get("altText", "Flex Message"),
        contents=FlexContainer.from_dict(flex_dict["contents"]),
    )


def _build_oauth_messages(user_id: str) -> list:
    """OAuth 連携用メッセージを生成 (LIFF 経由で外部ブラウザを開く)."""
    liff_url = f"https://liff.line.me/{LIFF_ID}"
    flex_dict = {
        "altText": "Google 連携",
        "contents": {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "Google 連携",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#1a73e8",
                    }
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "カレンダー・メール機能を\n使うにはGoogleアカウントの\n連携が必要です。",
                        "wrap": True,
                        "size": "sm",
                        "color": "#666666",
                    }
                ],
                "spacing": "md",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "Google で連携する",
                            "uri": liff_url,
                        },
                        "style": "primary",
                        "color": "#1a73e8",
                    }
                ],
            },
        },
    }
    return [_build_flex_message(flex_dict)]


def _sanitize_response(text: str) -> str:
    """LLM レスポンスから JSON 部分を抽出.

    Agent のレスポンスにマークダウンコードブロックや余分なテキストが
    含まれることがある。複数の手法で JSON を抽出する。
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


def convert_agent_response(response_text: str, user_id: str) -> list:
    """Agent レスポンスを LINE メッセージに変換."""
    cleaned = _sanitize_response(response_text)
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return [TextMessage(text=cleaned)]

    resp_type = data.get("type", "text")
    message_text = data.get("message", "")

    if resp_type == "oauth_required":
        return _build_oauth_messages(user_id)

    if resp_type == "calendar_events":
        events = data.get("events", [])
        flex = build_events_carousel(events, message_text)
        if flex.get("type") == "text":
            return [TextMessage(text=flex["text"])]
        messages = []
        if message_text:
            messages.append(TextMessage(text=message_text))
        messages.append(_build_flex_message(flex))
        return messages

    if resp_type == "date_selection":
        busy_slots = data.get("busy_slots", [])
        suggested_title = data.get("suggested_title", "新しい予定")
        # suggested_title を session state に保存（カルーセルフローで引き継ぐ）
        save_user_state(user_id, {"action": "date_selection", "suggested_title": suggested_title})

        # busy_slots から日付ごとの busy を抽出
        from datetime import datetime

        busy_dates = set()
        for slot in busy_slots:
            try:
                start = datetime.fromisoformat(slot["start"])
                end = datetime.fromisoformat(slot["end"])
                # 終日ブロックの日付を busy に
                if (end - start).total_seconds() >= 8 * 3600:
                    busy_dates.add(start.strftime("%Y-%m-%d"))
            except (ValueError, KeyError):
                continue
        flex = build_date_picker(list(busy_dates))
        messages = []
        if message_text:
            messages.append(TextMessage(text=message_text))
        messages.append(_build_flex_message(flex))
        return messages

    if resp_type == "location_request":
        quick_reply = QuickReply(items=[
            QuickReplyItem(action=LocationAction(label="📍 位置情報を送る")),
        ])
        return [TextMessage(
            text=message_text or "お近くのお店を探すので、位置情報を送ってもらえますか？",
            quick_reply=quick_reply,
        )]

    if resp_type in ("place_search", "place_recommend"):
        places = data.get("places", [])
        flex = build_place_carousel(
            places,
            message_text,
            place_type="recommend" if resp_type == "place_recommend" else "search",
        )
        if flex.get("type") == "text":
            return [TextMessage(text=flex["text"])]
        messages = []
        if message_text:
            messages.append(TextMessage(text=message_text))
        messages.append(_build_flex_message(flex))
        return messages

    if resp_type in ("event_created", "event_updated"):
        return [TextMessage(text=message_text or "予定を処理しました。")]

    if resp_type == "event_deleted":
        return [TextMessage(text=message_text or "予定を削除しました。")]

    # --- Gmail レスポンス ---

    if resp_type == "email_list":
        emails = data.get("emails", [])
        flex = build_email_carousel(emails, message_text)
        if flex.get("type") == "text":
            return [TextMessage(text=flex["text"])]
        messages = []
        if message_text:
            messages.append(TextMessage(text=message_text))
        messages.append(_build_flex_message(flex))
        return messages

    if resp_type == "email_detail":
        email = data.get("email", {})
        flex = build_email_detail(email)
        messages = []
        if message_text:
            messages.append(TextMessage(text=message_text))
        messages.append(_build_flex_message(flex))
        return messages

    if resp_type == "email_confirm_send":
        flex = build_email_send_confirm(data)
        messages = []
        if message_text:
            messages.append(TextMessage(text=message_text))
        messages.append(_build_flex_message(flex))
        return messages

    if resp_type == "email_sent":
        return [TextMessage(text=message_text or "メールを送信しました。")]

    if resp_type == "email_deleted":
        return [TextMessage(text=message_text or "メールを削除しました。")]

    if resp_type == "email_labels_updated":
        return [TextMessage(text=message_text or "ラベルを更新しました。")]

    if resp_type == "draft_saved":
        return [TextMessage(text=message_text or "下書きを保存しました。")]

    # デフォルト: テキスト
    return [TextMessage(text=message_text or response_text)]


# ========== ユーザーステート管理 ==========


def save_user_state(user_id: str, state: dict) -> None:
    """ユーザーの操作ステートを DynamoDB に保存."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(USER_STATE_TABLE)
    table.put_item(
        Item={
            "line_user_id": user_id,
            "state": json.dumps(state, ensure_ascii=False),
            "ttl": int(time.time()) + 600,  # 10分で期限切れ
        }
    )


def get_user_state(user_id: str) -> dict | None:
    """ユーザーの操作ステートを取得."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(USER_STATE_TABLE)
    response = table.get_item(Key={"line_user_id": user_id})
    item = response.get("Item")
    if item:
        return json.loads(item.get("state", "{}"))
    return None


def clear_user_state(user_id: str) -> None:
    """ユーザーの操作ステートを削除."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(USER_STATE_TABLE)
    table.delete_item(Key={"line_user_id": user_id})


# ========== メッセージハンドラ ==========


def handle_text_message(event: MessageEvent) -> None:
    """テキストメッセージを処理."""
    user_id = event.source.user_id
    user_text = event.message.text
    reply_token = event.reply_token

    logger.info("Received message from %s: %s", user_id, user_text[:50])

    # ユーザーステート確認 (タイトル編集中など)
    user_state = get_user_state(user_id)
    if user_state and user_state.get("action") == "waiting_location":
        # 位置情報待ちの状態でテキストが来た場合はステートをクリアして通常処理へ
        clear_user_state(user_id)

    if user_state and user_state.get("action") == "edit_title":
        # タイトル編集モード: 入力テキストを新しいタイトルとして確認画面を表示
        clear_user_state(user_id)
        flex = build_event_confirmation(
            date=user_state["date"],
            start=user_state["start"],
            end=user_state["end"],
            summary=user_text,
        )
        send_response(reply_token, user_id, [_build_flex_message(flex)])
        return

    # 1. ローディングアニメーション表示
    try:
        show_loading(user_id)
    except Exception:
        logger.warning("Failed to show loading animation", exc_info=True)

    # 2. Router Agent 呼び出し（Google 認証情報付き）
    start_time = time.time()
    try:
        ai_response = invoke_router_agent(user_text, user_id)
    except Exception:
        logger.error("Agent invocation failed", exc_info=True)
        ai_response = json.dumps(
            {"type": "text", "message": "申し訳ありません。エラーが発生しました。もう一度お試しください。"}
        )

    elapsed = time.time() - start_time
    logger.info("Agent response in %.1fs", elapsed)

    # 3. location_request の場合は元クエリをステートに保存
    try:
        resp_data = json.loads(ai_response)
        if resp_data.get("type") == "location_request":
            save_user_state(user_id, {
                "action": "waiting_location",
                "original_query": user_text,
            })
    except (json.JSONDecodeError, TypeError):
        pass

    # 4. レスポンス変換 & 送信
    messages = convert_agent_response(ai_response, user_id)
    send_response(reply_token, user_id, messages, elapsed)


def handle_location_message(event: MessageEvent) -> None:
    """位置情報メッセージを処理."""
    user_id = event.source.user_id
    reply_token = event.reply_token
    latitude = event.message.latitude
    longitude = event.message.longitude

    logger.info("Location from %s: lat=%s, lon=%s", user_id, latitude, longitude)

    # ステート確認: waiting_location なら元クエリを復元
    user_state = get_user_state(user_id)
    if user_state and user_state.get("action") == "waiting_location":
        original_query = user_state.get("original_query", "この場所の周辺でおすすめを教えて")
        clear_user_state(user_id)
        prompt = f"[ユーザーの現在地: 緯度{latitude}, 経度{longitude}] {original_query}"
    else:
        # 自発的な位置情報送信
        prompt = f"[ユーザーの現在地: 緯度{latitude}, 経度{longitude}] この場所の周辺でおすすめを教えて"

    # ローディングアニメーション
    try:
        show_loading(user_id)
    except Exception:
        logger.warning("Failed to show loading animation", exc_info=True)

    # Agent 呼び出し
    start_time = time.time()
    try:
        ai_response = invoke_router_agent(prompt, user_id)
    except Exception:
        logger.error("Agent invocation failed", exc_info=True)
        ai_response = json.dumps(
            {"type": "text", "message": "申し訳ありません。エラーが発生しました。もう一度お試しください。"}
        )

    elapsed = time.time() - start_time
    logger.info("Agent response in %.1fs", elapsed)

    messages = convert_agent_response(ai_response, user_id)
    send_response(reply_token, user_id, messages, elapsed)


def handle_postback(event: PostbackEvent) -> None:
    """Postback イベント (カルーセルボタンタップ) を処理."""
    user_id = event.source.user_id
    reply_token = event.reply_token
    data_str = event.postback.data

    logger.info("Postback from %s: %s", user_id, data_str)

    params = parse_qs(data_str)
    action = params.get("action", [""])[0]

    try:
        show_loading(user_id)
    except Exception:
        logger.warning("Failed to show loading animation", exc_info=True)

    try:
        if action == "select_date":
            _handle_select_date(reply_token, user_id, params)
        elif action == "select_time":
            _handle_select_time(reply_token, user_id, params)
        elif action == "confirm_create":
            _handle_confirm_create(reply_token, user_id, params)
        elif action == "edit_title":
            _handle_edit_title(reply_token, user_id, params)
        elif action == "event_detail":
            _handle_event_detail(reply_token, user_id, params)
        elif action == "event_edit":
            _handle_event_edit(reply_token, user_id, params)
        elif action == "event_delete":
            _handle_event_delete(reply_token, user_id, params)
        elif action == "confirm_delete":
            _handle_confirm_delete(reply_token, user_id, params)
        elif action == "email_detail":
            _handle_email_detail(reply_token, user_id, params)
        elif action == "email_delete":
            _handle_email_delete(reply_token, user_id, params)
        elif action == "email_send":
            _handle_email_send(reply_token, user_id, params)
        elif action == "cancel":
            clear_user_state(user_id)
        else:
            logger.warning("Unknown postback action: %s", action)
    except Exception:
        logger.error("Postback handling failed", exc_info=True)
        send_response(
            reply_token,
            user_id,
            [TextMessage(text="エラーが発生しました。もう一度お試しください。")],
        )


def _handle_select_date(reply_token: str, user_id: str, params: dict) -> None:
    """日付選択 → 時間帯選択カルーセルを表示."""
    date = params.get("date", [""])[0]

    creds = google_auth.get_google_credentials(user_id)
    if not creds:
        send_response(reply_token, user_id, _build_oauth_messages(user_id))
        return

    # suggested_title を引き継ぎ
    user_state = get_user_state(user_id)
    suggested_title = (user_state or {}).get("suggested_title", "新しい予定")
    save_user_state(user_id, {"action": "select_date", "suggested_title": suggested_title})

    busy_slots = google_calendar_api.get_free_busy(creds, date, date)
    flex = build_time_picker(date, busy_slots)
    send_response(reply_token, user_id, [_build_flex_message(flex)])


def _handle_select_time(reply_token: str, user_id: str, params: dict) -> None:
    """時間帯選択 → 確認画面カルーセルを表示."""
    date = params.get("date", [""])[0]
    start = params.get("start", [""])[0]
    end = params.get("end", [""])[0]

    # session state から suggested_title を取得
    user_state = get_user_state(user_id)
    summary = (user_state or {}).get("suggested_title", "新しい予定")

    flex = build_event_confirmation(
        date=date,
        start=start,
        end=end,
        summary=summary,
    )
    send_response(reply_token, user_id, [_build_flex_message(flex)])


def _handle_confirm_create(reply_token: str, user_id: str, params: dict) -> None:
    """確認画面の「作成」ボタン → 予定を作成."""
    date = params.get("date", [""])[0]
    start = params.get("start", [""])[0]
    end = params.get("end", [""])[0]
    summary = unquote(params.get("summary", ["新しい予定"])[0])

    creds = google_auth.get_google_credentials(user_id)
    if not creds:
        send_response(reply_token, user_id, _build_oauth_messages(user_id))
        return

    start_dt = f"{date}T{start}:00+09:00"
    end_dt = f"{date}T{end}:00+09:00"

    event = google_calendar_api.create_event(
        credentials=creds,
        summary=summary,
        start=start_dt,
        end=end_dt,
    )
    clear_user_state(user_id)
    send_response(
        reply_token,
        user_id,
        [TextMessage(text=f"予定を作成しました！\n\n📝 {summary}\n📅 {date} {start}-{end}")],
    )


def _handle_edit_title(reply_token: str, user_id: str, params: dict) -> None:
    """タイトル編集ボタン → ステートを保存し、テキスト入力を待つ."""
    date = params.get("date", [""])[0]
    start = params.get("start", [""])[0]
    end = params.get("end", [""])[0]

    save_user_state(user_id, {
        "action": "edit_title",
        "date": date,
        "start": start,
        "end": end,
    })
    send_response(
        reply_token,
        user_id,
        [TextMessage(text="新しいタイトルを入力してください。")],
    )


def _handle_event_detail(reply_token: str, user_id: str, params: dict) -> None:
    """予定詳細表示."""
    event_id = params.get("event_id", [""])[0]

    creds = google_auth.get_google_credentials(user_id)
    if not creds:
        return

    event = google_calendar_api.get_event(creds, event_id)
    detail = (
        f"📝 {event['summary']}\n"
        f"📅 {event['start']} 〜 {event['end']}\n"
    )
    if event.get("location"):
        detail += f"📍 {event['location']}\n"
    if event.get("description"):
        detail += f"\n{event['description']}\n"
    if event.get("attendees"):
        detail += f"\n👥 参加者: {', '.join(event['attendees'])}"

    send_response(reply_token, user_id, [TextMessage(text=detail)])


def _handle_event_edit(reply_token: str, user_id: str, params: dict) -> None:
    """予定編集 → テキストで指示を入力させる."""
    event_id = params.get("event_id", [""])[0]

    save_user_state(user_id, {
        "action": "event_edit",
        "event_id": event_id,
    })
    send_response(
        reply_token,
        user_id,
        [TextMessage(text="変更内容を教えてください。\n例: 「タイトルを○○に変更」「14時に変更」")],
    )


def _handle_event_delete(reply_token: str, user_id: str, params: dict) -> None:
    """予定削除確認画面を表示."""
    event_id = params.get("event_id", [""])[0]

    creds = google_auth.get_google_credentials(user_id)
    if not creds:
        return

    event = google_calendar_api.get_event(creds, event_id)
    flex = build_delete_confirmation(event)
    send_response(reply_token, user_id, [_build_flex_message(flex)])


def _handle_confirm_delete(reply_token: str, user_id: str, params: dict) -> None:
    """予定を実際に削除."""
    event_id = params.get("event_id", [""])[0]

    creds = google_auth.get_google_credentials(user_id)
    if not creds:
        return

    google_calendar_api.delete_event(creds, event_id)
    send_response(
        reply_token,
        user_id,
        [TextMessage(text="予定を削除しました。")],
    )


def _handle_email_detail(reply_token: str, user_id: str, params: dict) -> None:
    """メール詳細表示 → Agent に委譲."""
    email_id = params.get("email_id", [""])[0]

    start_time = time.time()
    try:
        prompt = f"メール ID {email_id} の詳細を表示してください。"
        ai_response = invoke_router_agent(prompt, user_id)
    except Exception:
        logger.error("Email detail agent call failed", exc_info=True)
        ai_response = json.dumps({"type": "text", "message": "メール詳細の取得に失敗しました。"})

    elapsed = time.time() - start_time
    messages = convert_agent_response(ai_response, user_id)
    send_response(reply_token, user_id, messages, elapsed)


def _handle_email_delete(reply_token: str, user_id: str, params: dict) -> None:
    """メール削除 → Agent に委譲."""
    email_id = params.get("email_id", [""])[0]

    start_time = time.time()
    try:
        prompt = f"メール ID {email_id} を削除してください。"
        ai_response = invoke_router_agent(prompt, user_id)
    except Exception:
        logger.error("Email delete agent call failed", exc_info=True)
        ai_response = json.dumps({"type": "text", "message": "メール削除に失敗しました。"})

    elapsed = time.time() - start_time
    messages = convert_agent_response(ai_response, user_id)
    send_response(reply_token, user_id, messages, elapsed)


def _handle_email_send(reply_token: str, user_id: str, params: dict) -> None:
    """メール送信確認後の実際の送信 → Agent に委譲."""
    to = unquote(params.get("to", [""])[0])
    subject = unquote(params.get("subject", [""])[0])
    body = unquote(params.get("body", [""])[0])

    start_time = time.time()
    try:
        prompt = f"以下の内容でメールを送信してください。送信確認は不要です。\n宛先: {to}\n件名: {subject}\n本文: {body}"
        ai_response = invoke_router_agent(prompt, user_id)
    except Exception:
        logger.error("Email send agent call failed", exc_info=True)
        ai_response = json.dumps({"type": "text", "message": "メール送信に失敗しました。"})

    elapsed = time.time() - start_time
    messages = convert_agent_response(ai_response, user_id)
    send_response(reply_token, user_id, messages, elapsed)


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
        elif isinstance(ev, MessageEvent) and isinstance(
            ev.message, LocationMessageContent
        ):
            handle_location_message(ev)
        elif isinstance(ev, PostbackEvent):
            handle_postback(ev)

    return {"statusCode": 200, "body": "OK"}


# ---------- ローカル開発 (FastAPI) ----------

if __name__ == "__main__":
    from dotenv import load_dotenv

    env_path = os.path.join(os.path.dirname(__file__), "..", ".env.local")
    load_dotenv(dotenv_path=env_path, override=True)

    # ロガーレベルを .env.local の値で再設定
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    logging.getLogger().setLevel(os.environ.get("LOG_LEVEL", "INFO"))

    # .env.local の値でグローバル変数を再設定
    CHANNEL_SECRET = os.environ["LINE_CHANNEL_SECRET"]
    CHANNEL_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    AGENTCORE_RUNTIME_ENDPOINT = os.environ.get(
        "AGENTCORE_RUNTIME_ENDPOINT", "http://localhost:8080"
    )
    AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

    parser = WebhookParser(CHANNEL_SECRET)
    configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

    # google_auth モジュールのグローバル変数も再設定
    google_auth.GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
    google_auth.GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    google_auth.GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "")
    google_auth.OAUTH_STATE_SECRET = os.environ.get("OAUTH_STATE_SECRET", "")
    google_auth.DYNAMODB_TOKEN_TABLE = os.environ.get("DYNAMODB_TOKEN_TABLE", "GoogleOAuthTokens")
    google_auth.AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
    LIFF_ID = os.environ.get("LIFF_ID", "")

    from fastapi import FastAPI, Header, Request
    from fastapi.responses import HTMLResponse, JSONResponse

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
            elif isinstance(ev, MessageEvent) and isinstance(
                ev.message, LocationMessageContent
            ):
                handle_location_message(ev)
            elif isinstance(ev, PostbackEvent):
                handle_postback(ev)

        return {"status": "ok"}

    @app.get("/liff/oauth")
    async def liff_oauth():
        """LIFF ページ: 外部ブラウザで Google OAuth を開く."""
        html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Google Calendar 連携</title>
<script charset="utf-8" src="https://static.line-scdn.net/liff/edge/2/sdk.js"></script>
<style>
body {{ font-family: sans-serif; text-align: center; padding: 40px 20px; background: #f5f5f5; }}
.card {{ background: #fff; border-radius: 12px; padding: 30px; max-width: 360px; margin: 0 auto; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
h2 {{ color: #1a73e8; margin-bottom: 16px; }}
p {{ color: #666; font-size: 14px; line-height: 1.6; }}
.loading {{ color: #999; }}
.error {{ color: #d32f2f; }}
</style>
</head><body>
<div class="card">
<h2>Google Calendar 連携</h2>
<p id="status" class="loading">認証ページを開いています...</p>
</div>
<script>
async function main() {{
  var s = document.getElementById('status');
  try {{
    s.textContent = '1. LIFF 初期化中...';
    await liff.init({{ liffId: '{LIFF_ID}' }});
    s.textContent = '2. ログイン確認中...';
    if (!liff.isLoggedIn()) {{
      liff.login();
      return;
    }}
    s.textContent = '3. プロフィール取得中...';
    var profile = await liff.getProfile();
    s.textContent = '4. OAuth URL 取得中...';
    var res = await fetch('/api/oauth-url?user_id=' + encodeURIComponent(profile.userId), {{
      headers: {{ 'ngrok-skip-browser-warning': 'true' }}
    }});
    var data = await res.json();
    s.textContent = '5. 外部ブラウザを開いています...';
    liff.openWindow({{ url: data.url, external: true }});
    s.textContent = 'ブラウザで Google 認証を完了してください。';
    setTimeout(function() {{ liff.closeWindow(); }}, 2000);
  }} catch(e) {{
    s.textContent = s.textContent + ' エラー: ' + e.message;
    s.className = 'error';
  }}
}}
main();
</script>
</body></html>"""
        return HTMLResponse(html)

    @app.get("/api/oauth-url")
    async def get_oauth_url(user_id: str = ""):
        """LIFF から呼ばれる: LINE user_id → Google OAuth URL を返す."""
        if not user_id:
            return JSONResponse({"error": "user_id required"}, status_code=400)
        url = google_auth.build_auth_url(user_id)
        return {"url": url}

    @app.get("/oauth/callback")
    async def oauth_callback(code: str = "", state: str = "", error: str = ""):
        """ローカル開発用 OAuth2 コールバック."""
        if error:
            return HTMLResponse(f"<p>認証エラー: {error}</p>")

        line_user_id = google_auth.decode_state(state)
        if not line_user_id:
            return HTMLResponse("<p>無効なリクエストです。</p>", status_code=400)

        token_data = google_auth.exchange_code_for_tokens(code)
        google_auth.save_tokens(line_user_id, token_data)

        # LINE Push で連携完了を通知
        try:
            push_message(
                line_user_id,
                [TextMessage(
                    text="Google Calendar の連携が完了しました！\n\n"
                    "「今日の予定は？」「予定を追加したい」などと話しかけてみてください。"
                )],
            )
        except Exception:
            logger.warning("Failed to push completion message", exc_info=True)

        return HTMLResponse(
            "<p>Google Calendar の連携が完了しました！LINEに戻ってください。</p>"
        )

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
