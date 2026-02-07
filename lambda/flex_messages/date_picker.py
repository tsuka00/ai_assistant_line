"""日付選択カルーセル Flex Message ビルダー."""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

COLOR_AVAILABLE = "#06C755"  # LINE Green
COLOR_BUSY = "#CCCCCC"  # グレー


def build_date_picker(busy_dates: list[str], weeks: int = 2) -> dict:
    """日付選択カルーセル Flex Message を生成.

    Args:
        busy_dates: 予定で埋まっている日付のリスト (YYYY-MM-DD)
        weeks: 表示する週数 (デフォルト2週間)
    """
    today = datetime.now(JST).date()
    busy_set = set(busy_dates)

    bubbles = []
    current_date = today

    for week_num in range(weeks):
        # 1週間分 (7日) の日付ボタンを作成
        buttons = []
        for _ in range(7):
            date_str = current_date.strftime("%Y-%m-%d")
            wd = WEEKDAYS[current_date.weekday()]
            label = f"{current_date.month}/{current_date.day}({wd})"
            is_busy = date_str in busy_set

            buttons.append(
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": label,
                        "data": f"action=select_date&date={date_str}",
                        "displayText": f"{label} を選択",
                    },
                    "style": "primary",
                    "color": COLOR_BUSY if is_busy else COLOR_AVAILABLE,
                    "height": "sm",
                    "margin": "sm",
                }
            )
            current_date += timedelta(days=1)

        bubble = {
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"日付を選択（{week_num + 1}週目）",
                        "weight": "bold",
                        "size": "md",
                        "color": "#1a73e8",
                    },
                    {
                        "type": "text",
                        "text": "緑が予約可能な日です",
                        "size": "xs",
                        "color": "#999999",
                    },
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": buttons,
                "spacing": "none",
            },
        }
        bubbles.append(bubble)

    return {
        "type": "flex",
        "altText": "日付を選択してください",
        "contents": {
            "type": "carousel",
            "contents": bubbles,
        },
    }
