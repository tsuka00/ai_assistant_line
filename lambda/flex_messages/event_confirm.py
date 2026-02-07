"""確認画面カルーセル Flex Message ビルダー."""

from datetime import datetime
from urllib.parse import quote

WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


def build_event_confirmation(
    date: str,
    start: str,
    end: str,
    summary: str = "新しい予定",
) -> dict:
    """予定作成の確認画面 Flex Message を生成."""
    dt = datetime.strptime(date, "%Y-%m-%d")
    wd = WEEKDAYS[dt.weekday()]
    date_display = f"{dt.month}月{dt.day}日（{wd}）"
    time_display = f"{start} - {end}"

    encoded_summary = quote(summary)

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "予定の確認",
                    "weight": "bold",
                    "size": "md",
                    "color": "#1a73e8",
                }
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "baseline",
                    "contents": [
                        {"type": "text", "text": "📅", "size": "sm", "flex": 0},
                        {
                            "type": "text",
                            "text": date_display,
                            "size": "sm",
                            "color": "#333333",
                            "flex": 1,
                        },
                    ],
                    "spacing": "sm",
                },
                {
                    "type": "box",
                    "layout": "baseline",
                    "contents": [
                        {"type": "text", "text": "🕐", "size": "sm", "flex": 0},
                        {
                            "type": "text",
                            "text": time_display,
                            "size": "sm",
                            "color": "#333333",
                            "flex": 1,
                        },
                    ],
                    "spacing": "sm",
                },
                {
                    "type": "box",
                    "layout": "baseline",
                    "contents": [
                        {"type": "text", "text": "📝", "size": "sm", "flex": 0},
                        {
                            "type": "text",
                            "text": summary,
                            "size": "sm",
                            "color": "#333333",
                            "weight": "bold",
                            "flex": 1,
                            "wrap": True,
                        },
                    ],
                    "spacing": "sm",
                },
            ],
            "spacing": "lg",
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
                        "label": "タイトル編集",
                        "data": (
                            f"action=edit_title"
                            f"&date={date}&start={start}&end={end}"
                        ),
                        "displayText": "タイトルを変更します。新しいタイトルを入力してください。",
                    },
                    "style": "secondary",
                    "height": "sm",
                    "flex": 1,
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "作成",
                        "data": (
                            f"action=confirm_create"
                            f"&date={date}&start={start}&end={end}"
                            f"&summary={encoded_summary}"
                        ),
                        "displayText": "予定を作成します",
                    },
                    "style": "primary",
                    "color": "#06C755",
                    "height": "sm",
                    "flex": 1,
                },
            ],
            "spacing": "sm",
        },
    }

    return {
        "type": "flex",
        "altText": f"予定の確認: {summary} ({date_display} {time_display})",
        "contents": bubble,
    }


def build_delete_confirmation(event: dict) -> dict:
    """予定削除の確認画面 Flex Message を生成."""
    summary = event.get("summary", "(タイトルなし)")
    event_id = event.get("id", "")
    start_str = event.get("start", "")

    try:
        dt = datetime.fromisoformat(start_str)
        wd = WEEKDAYS[dt.weekday()]
        date_display = f"{dt.month}/{dt.day}({wd}) {dt.strftime('%H:%M')}"
    except (ValueError, TypeError):
        date_display = start_str

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "この予定を削除しますか？",
                    "weight": "bold",
                    "size": "sm",
                    "color": "#ff4444",
                },
                {
                    "type": "text",
                    "text": f"📅 {date_display}",
                    "size": "sm",
                    "margin": "md",
                },
                {
                    "type": "text",
                    "text": f"📝 {summary}",
                    "size": "sm",
                    "weight": "bold",
                },
            ],
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
                        "label": "キャンセル",
                        "data": "action=cancel",
                        "displayText": "キャンセルしました",
                    },
                    "style": "secondary",
                    "height": "sm",
                    "flex": 1,
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "削除する",
                        "data": f"action=confirm_delete&event_id={event_id}",
                        "displayText": "予定を削除します",
                    },
                    "style": "primary",
                    "color": "#ff4444",
                    "height": "sm",
                    "flex": 1,
                },
            ],
            "spacing": "sm",
        },
    }

    return {
        "type": "flex",
        "altText": f"削除確認: {summary}",
        "contents": bubble,
    }
