"""時間帯選択カルーセル Flex Message ビルダー."""

from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]

COLOR_AVAILABLE = "#06C755"  # LINE Green
COLOR_BUSY = "#CCCCCC"  # グレー

# 選択可能な時間帯 (1時間刻み)
TIME_SLOTS = [
    ("09:00", "10:00"),
    ("10:00", "11:00"),
    ("11:00", "12:00"),
    ("13:00", "14:00"),
    ("14:00", "15:00"),
    ("15:00", "16:00"),
    ("16:00", "17:00"),
    ("17:00", "18:00"),
]


def build_time_picker(date: str, busy_slots: list[dict]) -> dict:
    """時間帯選択 Flex Message を生成.

    Args:
        date: 選択された日付 (YYYY-MM-DD)
        busy_slots: 予定ありスロット [{"start": "...", "end": "..."}]
    """
    dt = datetime.strptime(date, "%Y-%m-%d")
    wd = WEEKDAYS[dt.weekday()]
    date_display = f"{dt.month}月{dt.day}日（{wd}）"

    # 予定ありの時間帯を判定
    busy_ranges = _parse_busy_ranges(busy_slots, date)

    # 午前・午後に分ける
    am_buttons = []
    pm_buttons = []

    for start, end in TIME_SLOTS:
        is_busy = _is_slot_busy(date, start, end, busy_ranges)

        if is_busy:
            # busy: タップ不可のテキストボックス
            element = {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{start} - {end}",
                        "align": "center",
                        "color": "#FFFFFF",
                        "size": "sm",
                    }
                ],
                "backgroundColor": COLOR_BUSY,
                "cornerRadius": "md",
                "height": "40px",
                "justifyContent": "center",
                "margin": "sm",
            }
        else:
            element = {
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": f"{start} - {end}",
                    "data": f"action=select_time&date={date}&start={start}&end={end}",
                    "displayText": f"{start} - {end} を選択",
                },
                "style": "primary",
                "color": COLOR_AVAILABLE,
                "height": "sm",
                "margin": "sm",
            }

        hour = int(start.split(":")[0])
        if hour < 12:
            am_buttons.append(element)
        else:
            pm_buttons.append(element)

    contents = []

    # 午前セクション
    if am_buttons:
        contents.append(
            {
                "type": "text",
                "text": "午前",
                "weight": "bold",
                "size": "sm",
                "color": "#333333",
                "margin": "md",
            }
        )
        contents.append(
            {"type": "separator", "margin": "sm", "color": "#EEEEEE"}
        )
        contents.extend(am_buttons)

    # 午後セクション
    if pm_buttons:
        contents.append(
            {
                "type": "text",
                "text": "午後",
                "weight": "bold",
                "size": "sm",
                "color": "#333333",
                "margin": "lg",
            }
        )
        contents.append(
            {"type": "separator", "margin": "sm", "color": "#EEEEEE"}
        )
        contents.extend(pm_buttons)

    bubble = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "時間を選択",
                    "weight": "bold",
                    "size": "md",
                    "color": "#06C755",
                },
                {
                    "type": "text",
                    "text": date_display,
                    "size": "sm",
                    "color": "#333333",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": contents,
            "spacing": "none",
        },
    }

    return {
        "type": "flex",
        "altText": f"{date_display} の時間を選択してください",
        "contents": bubble,
    }


def _parse_busy_ranges(busy_slots: list[dict], date: str) -> list[tuple[int, int]]:
    """busy_slots を当日の分だけ (start_minutes, end_minutes) のリストに変換."""
    ranges = []
    for slot in busy_slots:
        start = slot.get("start", "")
        end = slot.get("end", "")
        try:
            s = datetime.fromisoformat(start)
            e = datetime.fromisoformat(end)
            if s.strftime("%Y-%m-%d") == date or e.strftime("%Y-%m-%d") == date:
                ranges.append((s.hour * 60 + s.minute, e.hour * 60 + e.minute))
        except (ValueError, TypeError):
            continue
    return ranges


def _is_slot_busy(
    date: str, start: str, end: str, busy_ranges: list[tuple[int, int]]
) -> bool:
    """指定スロットが busy_ranges と重なるか判定."""
    s_parts = start.split(":")
    e_parts = end.split(":")
    s_min = int(s_parts[0]) * 60 + int(s_parts[1])
    e_min = int(e_parts[0]) * 60 + int(e_parts[1])

    for busy_start, busy_end in busy_ranges:
        # スロットと busy 範囲が重なるか
        if s_min < busy_end and e_min > busy_start:
            return True
    return False
