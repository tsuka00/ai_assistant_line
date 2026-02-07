"""Google Calendar ツール (Strands Agent 用).

各ツールは module-level の _credentials を使って Google Calendar API を呼び出す。
Agent 呼び出し前に set_credentials() でセットすること。
"""

import json
import logging
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from strands import tool

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# リクエストスコープの Google 認証情報
_credentials: Credentials | None = None


def set_credentials(creds: Credentials) -> None:
    """Google Credentials をセット（Agent 呼び出し前に実行）."""
    global _credentials
    _credentials = creds


def _get_service():
    if _credentials is None:
        raise RuntimeError("Google credentials not set. Call set_credentials() first.")
    return build("calendar", "v3", credentials=_credentials, cache_discovery=False)


# ---------- Tools ----------


@tool
def list_events(
    date_from: str = "",
    date_to: str = "",
    max_results: int = 10,
) -> str:
    """Google Calendar の予定一覧を取得します。

    Args:
        date_from: 取得開始日 (YYYY-MM-DD)。空の場合は今日から。
        date_to: 取得終了日 (YYYY-MM-DD)。空の場合は開始日から7日後まで。
        max_results: 最大取得件数。デフォルト10件。

    Returns:
        予定一覧の JSON 文字列。type="calendar_events" でレスポンスを返してください。
    """
    service = _get_service()

    now = datetime.now(JST)
    if not date_from:
        time_min = now.isoformat()
    else:
        time_min = f"{date_from}T00:00:00+09:00"
    if not date_to:
        time_max = (now + timedelta(days=7)).isoformat()
    else:
        time_max = f"{date_to}T23:59:59+09:00"

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = [_parse_event(item) for item in result.get("items", [])]
    return json.dumps(events, ensure_ascii=False)


@tool
def get_event(event_id: str) -> str:
    """指定 ID の予定の詳細を取得します。

    Args:
        event_id: Google Calendar のイベント ID。

    Returns:
        予定詳細の JSON 文字列。
    """
    service = _get_service()
    item = service.events().get(calendarId="primary", eventId=event_id).execute()
    return json.dumps(_parse_event(item), ensure_ascii=False)


@tool
def create_event(
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
) -> str:
    """Google Calendar に新しい予定を作成します。

    Args:
        summary: 予定のタイトル。
        start: 開始日時 (ISO 8601 形式, 例: 2026-02-09T10:00:00+09:00)。
        end: 終了日時 (ISO 8601 形式, 例: 2026-02-09T11:00:00+09:00)。
        description: 予定の説明。省略可。
        location: 場所。省略可。

    Returns:
        作成した予定の JSON 文字列。type="event_created" でレスポンスを返してください。
    """
    service = _get_service()

    body = {
        "summary": summary,
        "start": _build_datetime(start),
        "end": _build_datetime(end),
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location

    item = service.events().insert(calendarId="primary", body=body).execute()
    logger.info("Created event: %s", item.get("id"))
    return json.dumps(_parse_event(item), ensure_ascii=False)


@tool
def update_event(
    event_id: str,
    summary: str = "",
    start: str = "",
    end: str = "",
    description: str = "",
    location: str = "",
) -> str:
    """既存の予定を更新します。変更したいフィールドのみ指定してください。

    Args:
        event_id: 更新対象のイベント ID。
        summary: 新しいタイトル。空の場合は変更しない。
        start: 新しい開始日時 (ISO 8601)。空の場合は変更しない。
        end: 新しい終了日時 (ISO 8601)。空の場合は変更しない。
        description: 新しい説明。空の場合は変更しない。
        location: 新しい場所。空の場合は変更しない。

    Returns:
        更新後の予定の JSON 文字列。type="event_updated" でレスポンスを返してください。
    """
    service = _get_service()
    existing = service.events().get(calendarId="primary", eventId=event_id).execute()

    if summary:
        existing["summary"] = summary
    if start:
        existing["start"] = _build_datetime(start)
    if end:
        existing["end"] = _build_datetime(end)
    if description:
        existing["description"] = description
    if location:
        existing["location"] = location

    item = (
        service.events()
        .update(calendarId="primary", eventId=event_id, body=existing)
        .execute()
    )
    logger.info("Updated event: %s", event_id)
    return json.dumps(_parse_event(item), ensure_ascii=False)


@tool
def delete_event(event_id: str) -> str:
    """予定を削除します。

    Args:
        event_id: 削除対象のイベント ID。

    Returns:
        削除結果のメッセージ。type="event_deleted" でレスポンスを返してください。
    """
    service = _get_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    logger.info("Deleted event: %s", event_id)
    return json.dumps({"deleted": True, "event_id": event_id}, ensure_ascii=False)


@tool
def invite_attendees(event_id: str, attendee_emails: str) -> str:
    """予定に参加者を招待します。

    Args:
        event_id: 招待先のイベント ID。
        attendee_emails: 招待するメールアドレス（カンマ区切り）。

    Returns:
        更新後の予定の JSON 文字列。
    """
    service = _get_service()
    emails = [e.strip() for e in attendee_emails.split(",") if e.strip()]

    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    existing_attendees = event.get("attendees", [])
    existing_emails = {a["email"] for a in existing_attendees}

    for email in emails:
        if email not in existing_emails:
            existing_attendees.append({"email": email})

    event["attendees"] = existing_attendees
    item = (
        service.events()
        .update(calendarId="primary", eventId=event_id, body=event)
        .execute()
    )
    logger.info("Invited %d attendees to event %s", len(emails), event_id)
    return json.dumps(_parse_event(item), ensure_ascii=False)


@tool
def get_free_busy(date_from: str, date_to: str) -> str:
    """指定期間の予定あり（ビジー）スロットを取得します。空き時間の確認に使います。

    Args:
        date_from: 開始日 (YYYY-MM-DD)。
        date_to: 終了日 (YYYY-MM-DD)。

    Returns:
        ビジースロット一覧の JSON 文字列。type="date_selection" でレスポンスを返してください。
    """
    service = _get_service()

    body = {
        "timeMin": f"{date_from}T00:00:00+09:00",
        "timeMax": f"{date_to}T23:59:59+09:00",
        "items": [{"id": "primary"}],
    }
    result = service.freebusy().query(body=body).execute()

    busy_slots = []
    for slot in result.get("calendars", {}).get("primary", {}).get("busy", []):
        busy_slots.append({"start": slot["start"], "end": slot["end"]})

    return json.dumps(busy_slots, ensure_ascii=False)


# ---------- ヘルパー ----------


def _build_datetime(dt_str: str) -> dict:
    if "T" in dt_str:
        return {"dateTime": dt_str, "timeZone": "Asia/Tokyo"}
    return {"date": dt_str}


def _parse_event(item: dict) -> dict:
    start = item.get("start", {})
    end = item.get("end", {})
    return {
        "id": item.get("id", ""),
        "summary": item.get("summary", "(タイトルなし)"),
        "start": start.get("dateTime", start.get("date", "")),
        "end": end.get("dateTime", end.get("date", "")),
        "location": item.get("location", ""),
        "description": item.get("description", ""),
        "attendees": [a.get("email", "") for a in item.get("attendees", [])],
        "html_link": item.get("htmlLink", ""),
    }
