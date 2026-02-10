"""メール詳細 Flex Message ビルダー."""


def build_email_detail(email: dict) -> dict:
    """メール詳細のバブル Flex Message を生成."""
    email_id = email.get("id", "")
    subject = email.get("subject", "(件名なし)")
    from_addr = email.get("from", "")
    to_addr = email.get("to", "")
    cc_addr = email.get("cc", "")
    date_str = email.get("date", "")
    summary = email.get("summary", "")
    has_attachments = email.get("has_attachments", False)
    attachment_count = email.get("attachment_count", 0)

    body_contents = [
        {
            "type": "text",
            "text": subject,
            "weight": "bold",
            "size": "lg",
            "wrap": True,
        },
        {"type": "separator", "margin": "md"},
        {
            "type": "box",
            "layout": "vertical",
            "contents": [
                _info_row("差出人", from_addr),
                _info_row("宛先", to_addr),
            ],
            "spacing": "sm",
            "margin": "md",
        },
    ]

    if cc_addr:
        body_contents[-1]["contents"].append(_info_row("CC", cc_addr))

    if date_str:
        body_contents[-1]["contents"].append(_info_row("日時", date_str[:25]))

    if summary:
        body_contents.append({"type": "separator", "margin": "md"})
        body_contents.append(
            {
                "type": "text",
                "text": summary,
                "size": "sm",
                "color": "#333333",
                "wrap": True,
                "margin": "md",
            }
        )

    if has_attachments:
        body_contents.append(
            {
                "type": "text",
                "text": f"📎 添付ファイル {attachment_count}件",
                "size": "xs",
                "color": "#1a73e8",
                "margin": "md",
            }
        )

    bubble = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "メール詳細",
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
                        "label": "削除",
                        "data": f"action=email_delete&email_id={email_id}",
                        "displayText": "メールを削除",
                    },
                    "style": "secondary",
                    "color": "#ff4444",
                    "height": "sm",
                },
            ],
        },
    }

    return {
        "type": "flex",
        "altText": f"メール: {subject}",
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
