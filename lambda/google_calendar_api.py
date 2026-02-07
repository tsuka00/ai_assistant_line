"""Google Calendar API ラッパー (Lambda 用)."""

import logging
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))


def _get_service(credentials: Credentials):
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def list_events(
    credentials: Credentials,
    date_from: str | None = None,
    date_to: str | None = None,
    max_results: int = 10,
) -> list[dict]:
    """予定一覧を取得."""
    service = _get_service(credentials)

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

    events = []
    for item in result.get("items", []):
        events.append(_parse_event(item))
    return events


def get_event(credentials: Credentials, event_id: str) -> dict:
    """予定の詳細を取得."""
    service = _get_service(credentials)
    item = service.events().get(calendarId="primary", eventId=event_id).execute()
    return _parse_event(item)


def create_event(
    credentials: Credentials,
    summary: str,
    start: str,
    end: str,
    description: str = "",
    location: str = "",
    attendees: list[str] | None = None,
) -> dict:
    """新規予定を作成."""
    service = _get_service(credentials)

    body = {
        "summary": summary,
        "start": _build_datetime(start),
        "end": _build_datetime(end),
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": e} for e in attendees]

    item = service.events().insert(calendarId="primary", body=body).execute()
    logger.info("Created event: %s", item.get("id"))
    return _parse_event(item)


def update_event(
    credentials: Credentials,
    event_id: str,
    **kwargs,
) -> dict:
    """予定を更新."""
    service = _get_service(credentials)

    # 既存イベント取得
    existing = service.events().get(calendarId="primary", eventId=event_id).execute()

    if "summary" in kwargs:
        existing["summary"] = kwargs["summary"]
    if "start" in kwargs:
        existing["start"] = _build_datetime(kwargs["start"])
    if "end" in kwargs:
        existing["end"] = _build_datetime(kwargs["end"])
    if "description" in kwargs:
        existing["description"] = kwargs["description"]
    if "location" in kwargs:
        existing["location"] = kwargs["location"]

    item = (
        service.events()
        .update(calendarId="primary", eventId=event_id, body=existing)
        .execute()
    )
    logger.info("Updated event: %s", event_id)
    return _parse_event(item)


def delete_event(credentials: Credentials, event_id: str) -> None:
    """予定を削除."""
    service = _get_service(credentials)
    service.events().delete(calendarId="primary", eventId=event_id).execute()
    logger.info("Deleted event: %s", event_id)


def invite_attendees(
    credentials: Credentials, event_id: str, attendee_emails: list[str]
) -> dict:
    """参加者を招待."""
    service = _get_service(credentials)

    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    existing_attendees = event.get("attendees", [])
    existing_emails = {a["email"] for a in existing_attendees}

    for email in attendee_emails:
        if email not in existing_emails:
            existing_attendees.append({"email": email})

    event["attendees"] = existing_attendees
    item = (
        service.events()
        .update(calendarId="primary", eventId=event_id, body=event)
        .execute()
    )
    logger.info("Invited %d attendees to event %s", len(attendee_emails), event_id)
    return _parse_event(item)


def get_free_busy(
    credentials: Credentials,
    date_from: str,
    date_to: str,
) -> list[dict]:
    """指定期間の予定ありスロットを取得."""
    service = _get_service(credentials)

    body = {
        "timeMin": f"{date_from}T00:00:00+09:00",
        "timeMax": f"{date_to}T23:59:59+09:00",
        "items": [{"id": "primary"}],
    }
    result = service.freebusy().query(body=body).execute()

    busy_slots = []
    for slot in result.get("calendars", {}).get("primary", {}).get("busy", []):
        busy_slots.append(
            {
                "start": slot["start"],
                "end": slot["end"],
            }
        )
    return busy_slots


# ---------- ヘルパー ----------


def _build_datetime(dt_str: str) -> dict:
    """ISO 8601 文字列から Calendar API 用の datetime dict を構築."""
    if "T" in dt_str:
        return {"dateTime": dt_str, "timeZone": "Asia/Tokyo"}
    return {"date": dt_str}


def _parse_event(item: dict) -> dict:
    """Calendar API のイベントをシンプルな dict に変換."""
    start = item.get("start", {})
    end = item.get("end", {})
    return {
        "id": item.get("id", ""),
        "summary": item.get("summary", "(タイトルなし)"),
        "start": start.get("dateTime", start.get("date", "")),
        "end": end.get("dateTime", end.get("date", "")),
        "location": item.get("location", ""),
        "description": item.get("description", ""),
        "attendees": [
            a.get("email", "") for a in item.get("attendees", [])
        ],
        "html_link": item.get("htmlLink", ""),
    }
