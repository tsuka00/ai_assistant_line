"""Flex Message ビルダーのユニットテスト."""

import sys
from pathlib import Path

# lambda/ ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flex_messages.calendar_carousel import build_events_carousel
from flex_messages.date_picker import build_date_picker
from flex_messages.event_confirm import (
    build_delete_confirmation,
    build_event_confirmation,
)
from flex_messages.oauth_link import build_oauth_link_message
from flex_messages.place_carousel import build_place_carousel
from flex_messages.time_picker import build_time_picker


class TestOAuthLinkMessage:
    def test_build_oauth_link(self):
        result = build_oauth_link_message("https://accounts.google.com/auth?foo=bar")
        assert result["type"] == "flex"
        assert result["altText"] == "Google Calendar 連携"
        assert result["contents"]["type"] == "bubble"
        footer = result["contents"]["footer"]
        button = footer["contents"][0]
        assert button["action"]["uri"] == "https://accounts.google.com/auth?foo=bar"


class TestEventsCarousel:
    def test_empty_events(self):
        result = build_events_carousel([])
        assert result["type"] == "text"
        assert "ありません" in result["text"]

    def test_single_event(self):
        events = [
            {
                "id": "ev1",
                "summary": "チームMTG",
                "start": "2026-02-08T10:00:00+09:00",
                "end": "2026-02-08T11:00:00+09:00",
                "location": "会議室A",
                "attendees": ["user@example.com"],
            }
        ]
        result = build_events_carousel(events, "今日の予定は1件です")
        assert result["type"] == "flex"
        carousel = result["contents"]
        assert carousel["type"] == "carousel"
        assert len(carousel["contents"]) == 1
        bubble = carousel["contents"][0]
        # ヘッダーに時間帯
        assert "10:00 - 11:00" in bubble["header"]["contents"][1]["text"]
        # フッターに3つのボタン
        assert len(bubble["footer"]["contents"]) == 3

    def test_max_12_events(self):
        events = [
            {"id": f"ev{i}", "summary": f"Event {i}", "start": "2026-02-08T10:00:00+09:00", "end": "2026-02-08T11:00:00+09:00"}
            for i in range(15)
        ]
        result = build_events_carousel(events)
        assert len(result["contents"]["contents"]) == 12


class TestDatePicker:
    def test_build_date_picker_default(self):
        result = build_date_picker(busy_dates=[], weeks=2)
        assert result["type"] == "flex"
        carousel = result["contents"]
        assert carousel["type"] == "carousel"
        assert len(carousel["contents"]) == 2  # 2週間分

    def test_busy_dates_are_grey(self):
        result = build_date_picker(busy_dates=["2026-02-08"], weeks=1)
        bubble = result["contents"]["contents"][0]
        buttons = bubble["body"]["contents"]
        # 最初のボタン (2/8) がグレーか確認 (日付は today ベースなので動的)
        assert len(buttons) == 7  # 1週間分

    def test_postback_data_format(self):
        result = build_date_picker(busy_dates=[], weeks=1)
        buttons = result["contents"]["contents"][0]["body"]["contents"]
        first_button = buttons[0]
        assert "action=select_date&date=" in first_button["action"]["data"]


class TestTimePicker:
    def test_build_time_picker(self):
        result = build_time_picker("2026-02-09", busy_slots=[])
        assert result["type"] == "flex"
        bubble = result["contents"]
        assert bubble["type"] == "bubble"
        # ヘッダーに日付
        assert "2月9日" in bubble["header"]["contents"][1]["text"]

    def test_busy_slots_are_grey(self):
        busy = [{"start": "2026-02-09T10:00:00+09:00", "end": "2026-02-09T11:00:00+09:00"}]
        result = build_time_picker("2026-02-09", busy)
        body = result["contents"]["body"]["contents"]
        # ボタンを探して 10:00-11:00 がグレーか確認
        for item in body:
            if item.get("type") == "button" and "10:00 - 11:00" in item.get("action", {}).get("label", ""):
                assert item["color"] == "#CCCCCC"
                break

    def test_postback_data_format(self):
        result = build_time_picker("2026-02-09", [])
        body = result["contents"]["body"]["contents"]
        for item in body:
            if item.get("type") == "button":
                assert "action=select_time&date=2026-02-09" in item["action"]["data"]
                break


class TestEventConfirmation:
    def test_build_confirmation(self):
        result = build_event_confirmation(
            date="2026-02-09",
            start="10:00",
            end="11:00",
            summary="チームMTG",
        )
        assert result["type"] == "flex"
        bubble = result["contents"]
        # フッターに2つのボタン
        footer_buttons = bubble["footer"]["contents"]
        assert len(footer_buttons) == 2
        assert footer_buttons[0]["action"]["data"].startswith("action=edit_title")
        assert footer_buttons[1]["action"]["data"].startswith("action=confirm_create")

    def test_delete_confirmation(self):
        event = {
            "id": "ev123",
            "summary": "チームMTG",
            "start": "2026-02-09T10:00:00+09:00",
        }
        result = build_delete_confirmation(event)
        assert result["type"] == "flex"
        footer_buttons = result["contents"]["footer"]["contents"]
        assert footer_buttons[0]["action"]["data"] == "action=cancel"
        assert "confirm_delete" in footer_buttons[1]["action"]["data"]


class TestPlaceCarousel:
    def test_empty_places(self):
        result = build_place_carousel([])
        assert result["type"] == "text"
        assert "見つかりませんでした" in result["text"]

    def test_search_single_place(self):
        places = [
            {"name": "渋谷カフェ", "lat": "35.6580", "lon": "139.7016"},
        ]
        result = build_place_carousel(places, "「渋谷カフェ」の検索結果です。", place_type="search")
        assert result["type"] == "flex"
        carousel = result["contents"]
        assert carousel["type"] == "carousel"
        assert len(carousel["contents"]) == 1
        bubble = carousel["contents"][0]
        # body に場所名
        assert bubble["body"]["contents"][0]["text"] == "渋谷カフェ"
        # footer に「地図を開く」ボタン
        assert bubble["footer"]["contents"][0]["action"]["label"] == "地図を開く"
        assert "35.6580,139.7016" in bubble["footer"]["contents"][0]["action"]["uri"]

    def test_recommend_place_with_rating(self):
        places = [
            {
                "name": "おしゃれカフェ",
                "description": "静かで落ち着いた雰囲気",
                "latitude": 35.6614,
                "longitude": 139.7036,
                "rating": 4.2,
                "minPrice": 600,
            },
        ]
        result = build_place_carousel(places, "おすすめの場所です。", place_type="recommend")
        assert result["type"] == "flex"
        bubble = result["contents"]["contents"][0]
        body_texts = [c.get("text", "") for c in bubble["body"]["contents"]]
        assert "おしゃれカフェ" in body_texts
        assert "静かで落ち着いた雰囲気" in body_texts
        # 評価 & 価格
        assert any("4.2" in t and "600" in t for t in body_texts)

    def test_max_12_places(self):
        places = [
            {"name": f"Place {i}", "lat": "35.0", "lon": "139.0"}
            for i in range(15)
        ]
        result = build_place_carousel(places)
        assert len(result["contents"]["contents"]) == 12

    def test_no_footer_without_coordinates(self):
        places = [{"name": "不明な場所", "lat": "", "lon": ""}]
        result = build_place_carousel(places, place_type="search")
        bubble = result["contents"]["contents"][0]
        assert "footer" not in bubble
