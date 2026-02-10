"""メール一覧カルーセル Flex Message ビルダー."""

from datetime import datetime


def build_email_carousel(emails: list[dict], message: str = "") -> dict:
    """メール一覧のカルーセル Flex Message を生成."""
    if not emails:
        return {
            "type": "text",
            "text": message or "メールはありません。",
        }

    bubbles = []
    for email in emails[:12]:  # カルーセルは最大12バブル
        bubbles.append(_build_email_bubble(email))

    contents = {
        "type": "carousel",
        "contents": bubbles,
    }

    return {
        "type": "flex",
        "altText": message or "メール一覧",
        "contents": contents,
    }


def _build_email_bubble(email: dict) -> dict:
    """1つのメールバブルを生成."""
    email_id = email.get("id", "")
    subject = email.get("subject", "(件名なし)")
    from_addr = email.get("from", "")
    date_str = email.get("date", "")
    snippet = email.get("snippet", "")

    # 差出人の表示名を抽出
    from_display = _extract_display_name(from_addr)
    date_display = _format_date(date_str)

    # 未読判定
    label_ids = email.get("label_ids", [])
    is_unread = "UNREAD" in label_ids

    body_contents = [
        {
            "type": "text",
            "text": subject,
            "weight": "bold",
            "size": "md",
            "wrap": True,
            "maxLines": 2,
        },
        {
            "type": "box",
            "layout": "baseline",
            "contents": [
                {"type": "text", "text": "👤", "size": "sm", "flex": 0},
                {
                    "type": "text",
                    "text": from_display,
                    "size": "sm",
                    "color": "#666666",
                    "wrap": True,
                    "flex": 1,
                    "maxLines": 1,
                },
            ],
            "spacing": "sm",
        },
    ]

    if snippet:
        body_contents.append(
            {
                "type": "text",
                "text": snippet[:80],
                "size": "xs",
                "color": "#999999",
                "wrap": True,
                "maxLines": 2,
            }
        )

    # 未読インジケーター
    header_color = "#1a73e8" if is_unread else "#888888"

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
                    "text": "未読" if is_unread else "既読",
                    "weight": "bold",
                    "size": "sm",
                    "color": "#ffffff",
                },
            ],
            "backgroundColor": header_color,
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
                        "data": f"action=email_detail&email_id={email_id}",
                        "displayText": "メールの詳細を表示",
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
                        "data": f"action=email_delete&email_id={email_id}",
                        "displayText": "メールを削除",
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


def _extract_display_name(from_addr: str) -> str:
    """メールアドレスから表示名を抽出."""
    if "<" in from_addr:
        return from_addr.split("<")[0].strip().strip('"')
    return from_addr


def _format_date(date_str: str) -> str:
    """日付文字列を "2/8(土) 10:30" 形式に変換."""
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    # RFC 2822 形式の日付をパース
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            wd = weekdays[dt.weekday()]
            return f"{dt.month}/{dt.day}({wd}) {dt.strftime('%H:%M')}"
        except (ValueError, TypeError):
            continue
    return date_str[:20] if date_str else ""
