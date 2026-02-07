"""OAuth2 連携リンク Flex Message ビルダー."""


def build_oauth_link_message(auth_url: str) -> dict:
    """Google Calendar 連携リンクの Flex Message を生成."""
    return {
        "type": "flex",
        "altText": "Google Calendar 連携",
        "contents": {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "Google Calendar 連携",
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
                        "text": "カレンダー機能を使うには\nGoogleアカウントの連携が\n必要です。",
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
                            "uri": auth_url,
                        },
                        "style": "primary",
                        "color": "#1a73e8",
                    }
                ],
            },
        },
    }
