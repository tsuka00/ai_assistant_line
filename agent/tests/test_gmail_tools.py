"""Tests for agent/tools/google_gmail.py."""

import base64
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

gmail_tools = sys.modules["tools.google_gmail"]


# ---------- ヘルパー関数テスト ----------


def test_build_mime_message():
    """MIME メッセージが正しく構築されること."""
    result = gmail_tools._build_mime_message(
        to="test@example.com",
        subject="テスト件名",
        body="テスト本文",
        cc="cc@example.com",
    )
    assert "raw" in result
    # base64url デコードして内容を確認
    decoded = base64.urlsafe_b64decode(result["raw"]).decode("utf-8")
    assert "test@example.com" in decoded
    assert "cc@example.com" in decoded


def test_parse_email_headers():
    """ヘッダー抽出が正しいこと."""
    headers = [
        {"name": "Subject", "value": "テスト件名"},
        {"name": "From", "value": "sender@example.com"},
        {"name": "To", "value": "recipient@example.com"},
        {"name": "Date", "value": "Mon, 10 Feb 2026 10:00:00 +0900"},
        {"name": "Cc", "value": "cc@example.com"},
    ]
    result = gmail_tools._parse_email_headers(headers)
    assert result["subject"] == "テスト件名"
    assert result["from"] == "sender@example.com"
    assert result["to"] == "recipient@example.com"
    assert result["cc"] == "cc@example.com"


def test_strip_html():
    """HTML タグが除去されること."""
    html = "<p>Hello <b>World</b></p><br/>Line2&amp;done"
    result = gmail_tools._strip_html(html)
    assert "Hello World" in result
    assert "Line2&done" in result
    assert "<" not in result or "&" in result  # タグが除去されていること


def test_extract_plain_body_text_plain():
    """text/plain パートが優先されること."""
    data = base64.urlsafe_b64encode("プレーンテキスト".encode("utf-8")).decode("ascii")
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": data}},
            {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(b"<p>HTML</p>").decode("ascii")}},
        ],
    }
    result = gmail_tools._extract_plain_body(payload)
    assert result == "プレーンテキスト"


def test_extract_plain_body_html_fallback():
    """text/plain がない場合は text/html からタグ除去."""
    html_data = base64.urlsafe_b64encode("<p>HTMLの本文</p>".encode("utf-8")).decode("ascii")
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {"mimeType": "text/html", "body": {"data": html_data}},
        ],
    }
    result = gmail_tools._extract_plain_body(payload)
    assert "HTMLの本文" in result
    assert "<p>" not in result


# ---------- ツールテスト ----------


def _mock_service():
    """Gmail API サービスモック."""
    return MagicMock()


@patch.object(gmail_tools, "_get_service")
def test_list_emails(mock_get_service):
    """list_emails がメール一覧を返すこと."""
    mock_svc = _mock_service()
    mock_get_service.return_value = mock_svc

    # messages.list の戻り値
    mock_svc.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}, {"id": "msg2"}],
    }

    # messages.get の戻り値
    mock_svc.users().messages().get().execute.return_value = {
        "id": "msg1",
        "threadId": "thread1",
        "snippet": "テストスニペット",
        "labelIds": ["INBOX", "UNREAD"],
        "payload": {
            "headers": [
                {"name": "Subject", "value": "テスト件名"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "Date", "value": "Mon, 10 Feb 2026 10:00:00 +0900"},
            ]
        },
    }

    result = json.loads(gmail_tools.list_emails())
    assert isinstance(result, list)
    assert len(result) == 2


@patch.object(gmail_tools, "_get_service")
def test_get_email(mock_get_service):
    """get_email がメール詳細を返すこと."""
    mock_svc = _mock_service()
    mock_get_service.return_value = mock_svc

    body_data = base64.urlsafe_b64encode("メール本文".encode("utf-8")).decode("ascii")
    mock_svc.users().messages().get().execute.return_value = {
        "id": "msg1",
        "threadId": "thread1",
        "labelIds": ["INBOX"],
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "Subject", "value": "テスト件名"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "To", "value": "recipient@example.com"},
                {"name": "Date", "value": "Mon, 10 Feb 2026 10:00:00 +0900"},
            ],
            "body": {"data": body_data},
            "parts": [],
        },
    }

    result = json.loads(gmail_tools.get_email(email_id="msg1"))
    assert result["id"] == "msg1"
    assert result["subject"] == "テスト件名"
    assert "メール本文" in result["body"]


@patch.object(gmail_tools, "_get_service")
def test_send_email(mock_get_service):
    """send_email が送信結果を返すこと."""
    mock_svc = _mock_service()
    mock_get_service.return_value = mock_svc

    mock_svc.users().messages().send().execute.return_value = {
        "id": "sent1",
        "threadId": "thread1",
    }

    result = json.loads(gmail_tools.send_email(
        to="test@example.com",
        subject="テスト",
        body="テスト本文",
    ))
    assert result["sent"] is True
    assert result["id"] == "sent1"


@patch.object(gmail_tools, "_get_service")
def test_search_emails(mock_get_service):
    """search_emails が検索結果を返すこと."""
    mock_svc = _mock_service()
    mock_get_service.return_value = mock_svc

    mock_svc.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}],
    }
    mock_svc.users().messages().get().execute.return_value = {
        "id": "msg1",
        "threadId": "thread1",
        "snippet": "検索結果",
        "labelIds": ["INBOX"],
        "payload": {
            "headers": [
                {"name": "Subject", "value": "検索テスト"},
                {"name": "From", "value": "sender@example.com"},
                {"name": "Date", "value": "Mon, 10 Feb 2026 10:00:00 +0900"},
            ]
        },
    }

    result = json.loads(gmail_tools.search_emails(query="from:sender@example.com"))
    assert len(result) == 1
    assert result[0]["subject"] == "検索テスト"


@patch.object(gmail_tools, "_get_service")
def test_delete_email_trash(mock_get_service):
    """delete_email がゴミ箱移動すること."""
    mock_svc = _mock_service()
    mock_get_service.return_value = mock_svc

    mock_svc.users().messages().trash().execute.return_value = {}

    result = json.loads(gmail_tools.delete_email(email_id="msg1"))
    assert result["deleted"] is True
    assert result["permanent"] is False


@patch.object(gmail_tools, "_get_service")
def test_manage_labels(mock_get_service):
    """manage_labels がラベル更新結果を返すこと."""
    mock_svc = _mock_service()
    mock_get_service.return_value = mock_svc

    mock_svc.users().messages().modify().execute.return_value = {
        "id": "msg1",
        "labelIds": ["INBOX", "STARRED"],
    }

    result = json.loads(gmail_tools.manage_labels(
        email_id="msg1",
        add_labels="STARRED",
        remove_labels="UNREAD",
    ))
    assert result["updated"] is True


@patch.object(gmail_tools, "_get_service")
def test_save_draft(mock_get_service):
    """save_draft が下書き保存結果を返すこと."""
    mock_svc = _mock_service()
    mock_get_service.return_value = mock_svc

    mock_svc.users().drafts().create().execute.return_value = {
        "id": "draft1",
        "message": {"id": "msg1"},
    }

    result = json.loads(gmail_tools.save_draft(
        to="test@example.com",
        subject="下書き",
        body="下書き本文",
    ))
    assert result["saved"] is True
    assert result["draft_id"] == "draft1"
