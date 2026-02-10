"""メール送信確認 Flex Message ビルダー."""

from urllib.parse import quote


def build_email_send_confirm(data: dict) -> dict:
    """メール送信確認のバブル Flex Message を生成."""
    to = data.get("to", "")
    subject = data.get("subject", "")
    body = data.get("body", "")

    # プレビュー用に本文を切り詰め
    body_preview = body[:200] + "..." if len(body) > 200 else body

    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "メール送信確認",
                    "weight": "bold",
                    "size": "md",
                    "color": "#ffffff",
                }
            ],
            "backgroundColor": "#1a73e8",
            "paddingAll": "15px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                _info_row("宛先", to),
                _info_row("件名", subject),
                {"type": "separator", "margin": "md"},
                {
                    "type": "text",
                    "text": body_preview,
                    "size": "sm",
                    "color": "#333333",
                    "wrap": True,
                    "margin": "md",
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
                        "label": "送信",
                        "data": f"action=email_send&to={quote(to)}&subject={quote(subject)}&body={quote(body[:500])}",
                        "displayText": "メールを送信",
                    },
                    "style": "primary",
                    "color": "#1a73e8",
                    "height": "sm",
                    "flex": 1,
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "キャンセル",
                        "data": "action=cancel",
                        "displayText": "キャンセル",
                    },
                    "style": "secondary",
                    "height": "sm",
                    "flex": 1,
                },
            ],
            "spacing": "sm",
        },
    }

    return {
        "type": "flex",
        "altText": f"メール送信確認: {subject}",
        "contents": bubble,
    }


def _info_row(label: str, value: str) -> dict:
    """情報行（ラベル + 値）."""
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {
                "type": "text",
                "text": label,
                "size": "xs",
                "color": "#999999",
                "flex": 2,
            },
            {
                "type": "text",
                "text": value or "-",
                "size": "xs",
                "color": "#333333",
                "wrap": True,
                "flex": 5,
            },
        ],
    }
