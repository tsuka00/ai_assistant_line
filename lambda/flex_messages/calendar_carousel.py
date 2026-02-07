"""予定一覧カルーセル Flex Message ビルダー."""

from datetime import datetime


def build_events_carousel(events: list[dict], message: str = "") -> dict:
    """予定一覧のカルーセル Flex Message を生成."""
    if not events:
        return {
            "type": "text",
            "text": message or "予定はありません。",
        }

    bubbles = []
    for event in events[:12]:  # カルーセルは最大12バブル
        bubbles.append(_build_event_bubble(event))

    contents = {
        "type": "carousel",
        "contents": bubbles,
    }

    result = {
        "type": "flex",
        "altText": message or "予定一覧",
        "contents": contents,
    }
    return result


def _build_event_bubble(event: dict) -> dict:
    """1つの予定バブルを生成."""
    start_str = event.get("start", "")
    end_str = event.get("end", "")
    time_display = _format_time_range(start_str, end_str)
    date_display = _format_date(start_str)
    summary = event.get("summary", "(タイトルなし)")
    location = event.get("location", "")
    attendees = event.get("attendees", [])
    event_id = event.get("id", "")

    body_contents = [
        {
            "type": "text",
            "text": summary,
            "weight": "bold",
            "size": "md",
            "wrap": True,
        },
    ]

    if location:
        body_contents.append(
            {
                "type": "box",
                "layout": "baseline",
                "contents": [
                    {"type": "text", "text": "📍", "size": "sm", "flex": 0},
                    {
                        "type": "text",
                        "text": location,
                        "size": "sm",
                        "color": "#666666",
                        "wrap": True,
                        "flex": 1,
                    },
                ],
                "spacing": "sm",
            }
        )

    if attendees:
        body_contents.append(
            {
                "type": "text",
                "text": f"👥 {len(attendees)}人",
                "size": "sm",
                "color": "#666666",
            }
        )

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": date_display,
                    "size": "xs",
                    "color": "#ffffff",
                },
                {
                    "type": "text",
                    "text": time_display,
                    "weight": "bold",
                    "size": "lg",
                    "color": "#ffffff",
                },
            ],
            "backgroundColor": "#06C755",
            "paddingAll": "15px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "spacing": "sm",
            "paddingAll": "15px",
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "詳細",
                        "data": f"action=event_detail&event_id={event_id}",
                        "displayText": "詳細を表示",
                    },
                    "style": "secondary",
                    "height": "sm",
                    "flex": 1,
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "編集",
                        "data": f"action=event_edit&event_id={event_id}",
                        "displayText": "予定を編集",
                    },
                    "style": "secondary",
                    "height": "sm",
                    "flex": 1,
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "削除",
                        "data": f"action=event_delete&event_id={event_id}",
                        "displayText": "予定を削除",
                    },
                    "style": "secondary",
                    "color": "#ff4444",
                    "height": "sm",
                    "flex": 1,
                },
            ],
            "spacing": "sm",
        },
    }
    return bubble


def _format_time_range(start: str, end: str) -> str:
    """開始・終了時刻を "10:00 - 11:00" 形式に変換."""
    try:
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
        return f"{s.strftime('%H:%M')} - {e.strftime('%H:%M')}"
    except (ValueError, TypeError):
        return "終日"


def _format_date(start: str) -> str:
    """日付を "2/8(土)" 形式に変換."""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    try:
        dt = datetime.fromisoformat(start)
        wd = weekdays[dt.weekday()]
        return f"{dt.month}/{dt.day}({wd})"
    except (ValueError, TypeError):
        return ""
