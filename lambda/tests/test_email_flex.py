"""Tests for email Flex Message builders."""

import json
import sys

import pytest

# Flex modules are registered by conftest.py
email_carousel = sys.modules["flex_messages.email_carousel"]
email_detail = sys.modules["flex_messages.email_detail"]
email_confirm = sys.modules["flex_messages.email_confirm"]


# ---------- email_carousel tests ----------


def test_build_email_carousel_empty():
    """メールが空の場合テキストが返ること."""
    result = email_carousel.build_email_carousel([], "メールはありません。")
    assert result["type"] == "text"
    assert "メールはありません" in result["text"]


def test_build_email_carousel_with_emails():
    """メール一覧でカルーセルが生成されること."""
    emails = [
        {
            "id": "msg1",
            "subject": "テスト件名1",
            "from": "田中太郎 <tanaka@example.com>",
            "date": "Mon, 10 Feb 2026 10:00:00 +0900",
            "snippet": "テストスニペット1",
            "label_ids": ["INBOX", "UNREAD"],
        },
        {
            "id": "msg2",
            "subject": "テスト件名2",
            "from": "suzuki@example.com",
            "date": "Mon, 10 Feb 2026 11:00:00 +0900",
            "snippet": "テストスニペット2",
            "label_ids": ["INBOX"],
        },
    ]
    result = email_carousel.build_email_carousel(emails, "受信トレイです。")
    assert result["type"] == "flex"
    assert result["contents"]["type"] == "carousel"
    assert len(result["contents"]["contents"]) == 2


def test_build_email_carousel_unread_indicator():
    """未読メールのヘッダー色が青であること."""
    emails = [
        {
            "id": "msg1",
            "subject": "未読メール",
            "from": "sender@example.com",
            "date": "",
            "snippet": "",
            "label_ids": ["INBOX", "UNREAD"],
        },
    ]
    result = email_carousel.build_email_carousel(emails)
    bubble = result["contents"]["contents"][0]
    assert bubble["header"]["backgroundColor"] == "#1a73e8"


def test_build_email_carousel_read_indicator():
    """既読メールのヘッダー色がグレーであること."""
    emails = [
        {
            "id": "msg1",
            "subject": "既読メール",
            "from": "sender@example.com",
            "date": "",
            "snippet": "",
            "label_ids": ["INBOX"],
        },
    ]
    result = email_carousel.build_email_carousel(emails)
    bubble = result["contents"]["contents"][0]
    assert bubble["header"]["backgroundColor"] == "#888888"


def test_extract_display_name():
    """メールアドレスから表示名が抽出されること."""
    assert email_carousel._extract_display_name("田中太郎 <tanaka@example.com>") == "田中太郎"
    assert email_carousel._extract_display_name("plain@example.com") == "plain@example.com"


def test_email_bubble_has_postback_buttons():
    """メールバブルに詳細・削除ボタンがあること."""
    emails = [
        {
            "id": "msg1",
            "subject": "テスト",
            "from": "sender@example.com",
            "date": "",
            "snippet": "",
            "label_ids": [],
        },
    ]
    result = email_carousel.build_email_carousel(emails)
    bubble = result["contents"]["contents"][0]
    footer_buttons = bubble["footer"]["contents"]
    assert len(footer_buttons) == 2
    assert "email_detail" in footer_buttons[0]["action"]["data"]
    assert "email_delete" in footer_buttons[1]["action"]["data"]


# ---------- email_detail tests ----------


def test_build_email_detail():
    """メール詳細バブルが正しく生成されること."""
    email = {
        "id": "msg1",
        "subject": "テスト件名",
        "from": "sender@example.com",
        "to": "recipient@example.com",
        "cc": "cc@example.com",
        "date": "Mon, 10 Feb 2026 10:00:00 +0900",
        "summary": "会議の日程調整について。来週水曜日14時の提案。",
        "has_attachments": True,
        "attachment_count": 2,
    }
    result = email_detail.build_email_detail(email)
    assert result["type"] == "flex"
    assert "テスト件名" in result["altText"]

    bubble = result["contents"]
    assert bubble["type"] == "bubble"
    assert bubble["header"]["backgroundColor"] == "#1a73e8"


def test_build_email_detail_no_attachments():
    """添付なしの場合に添付表示がないこと."""
    email = {
        "id": "msg2",
        "subject": "添付なし",
        "from": "sender@example.com",
        "to": "recipient@example.com",
        "summary": "テスト要約",
        "has_attachments": False,
        "attachment_count": 0,
    }
    result = email_detail.build_email_detail(email)
    bubble = result["contents"]
    body_texts = [c.get("text", "") for c in bubble["body"]["contents"] if c.get("type") == "text"]
    # 添付ファイルのテキストがないこと
    assert not any("添付ファイル" in t for t in body_texts)


# ---------- email_confirm tests ----------


def test_build_email_send_confirm():
    """メール送信確認バブルが正しく生成されること."""
    data = {
        "to": "test@example.com",
        "subject": "テスト件名",
        "body": "テスト本文です。",
    }
    result = email_confirm.build_email_send_confirm(data)
    assert result["type"] == "flex"
    assert "テスト件名" in result["altText"]

    bubble = result["contents"]
    assert bubble["type"] == "bubble"

    # 送信・キャンセルボタンがあること
    footer_buttons = bubble["footer"]["contents"]
    assert len(footer_buttons) == 2
    assert footer_buttons[0]["action"]["label"] == "送信"
    assert footer_buttons[1]["action"]["label"] == "キャンセル"


def test_build_email_send_confirm_long_body():
    """長い本文が切り詰められること."""
    data = {
        "to": "test@example.com",
        "subject": "長文テスト",
        "body": "x" * 300,
    }
    result = email_confirm.build_email_send_confirm(data)
    bubble = result["contents"]
    # body 内のテキストが 203 文字以下であること (200 + "...")
    body_contents = bubble["body"]["contents"]
    text_items = [c for c in body_contents if c.get("type") == "text"]
    # 最後のテキスト要素が本文プレビュー
    preview = text_items[-1]["text"]
    assert preview.endswith("...")
    assert len(preview) == 203
