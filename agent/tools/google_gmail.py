"""Google Gmail ツール (Strands Agent 用).

各ツールは module-level の _credentials を使って Gmail API を呼び出す。
Agent 呼び出し前に set_credentials() でセットすること。
"""

import base64
import json
import logging
import re
from email.mime.text import MIMEText

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from strands import tool

logger = logging.getLogger(__name__)

# リクエストスコープの Google 認証情報
_credentials: Credentials | None = None


def set_credentials(creds: Credentials) -> None:
    """Google Credentials をセット（Agent 呼び出し前に実行）."""
    global _credentials
    _credentials = creds


def _get_service():
    if _credentials is None:
        raise RuntimeError("Google credentials not set. Call set_credentials() first.")
    return build("gmail", "v1", credentials=_credentials, cache_discovery=False)


# ---------- ヘルパー ----------


def _build_mime_message(to: str, subject: str, body: str, cc: str = "", bcc: str = "") -> dict:
    """MIME メッセージを構築して base64url エンコード."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return {"raw": raw}


def _parse_email_headers(headers: list[dict]) -> dict:
    """Subject/From/To/Date/Cc を抽出."""
    result = {}
    for h in headers:
        name = h.get("name", "").lower()
        if name in ("subject", "from", "to", "date", "cc"):
            result[name] = h.get("value", "")
    return result


def _strip_html(html: str) -> str:
    """HTML タグを除去してプレーンテキストに変換."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", "", text)
    return text.strip()


def _extract_plain_body(payload: dict) -> str:
    """MIME パートを再帰走査して text/plain 優先、text/html はタグ除去."""
    mime_type = payload.get("mimeType", "")
    parts = payload.get("parts", [])

    if mime_type == "text/plain" and "body" in payload:
        data = payload["body"].get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    if mime_type == "text/html" and "body" in payload:
        data = payload["body"].get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            return _strip_html(html)

    # multipart: text/plain を優先
    plain_text = ""
    html_text = ""
    for part in parts:
        part_mime = part.get("mimeType", "")
        if part_mime == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                plain_text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif part_mime == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                html_text = _strip_html(html)
        elif part_mime.startswith("multipart/"):
            result = _extract_plain_body(part)
            if result:
                return result

    return plain_text or html_text


# ---------- Tools ----------


@tool
def list_emails(
    label: str = "INBOX",
    max_results: int = 10,
) -> str:
    """Gmail のメール一覧を取得します。

    Args:
        label: 取得するラベル。デフォルトは INBOX。
        max_results: 最大取得件数。デフォルト10件。

    Returns:
        メール一覧の JSON 文字列。type="email_list" でレスポンスを返してください。
    """
    service = _get_service()

    results = (
        service.users()
        .messages()
        .list(userId="me", labelIds=[label], maxResults=max_results)
        .execute()
    )

    messages = results.get("messages", [])
    emails = []
    for msg_ref in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="metadata", metadataHeaders=["Subject", "From", "Date"])
            .execute()
        )
        headers = _parse_email_headers(msg.get("payload", {}).get("headers", []))
        emails.append({
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "subject": headers.get("subject", "(件名なし)"),
            "from": headers.get("from", ""),
            "date": headers.get("date", ""),
            "snippet": msg.get("snippet", ""),
            "label_ids": msg.get("labelIds", []),
        })

    return json.dumps(emails, ensure_ascii=False)


@tool
def get_email(email_id: str) -> str:
    """指定 ID のメールの詳細を取得します。

    Args:
        email_id: Gmail のメッセージ ID。

    Returns:
        メール詳細の JSON 文字列。type="email_detail" でレスポンスを返してください。
        本文は事実ベースで簡潔に要約して summary フィールドに入れてください。
    """
    service = _get_service()

    msg = (
        service.users()
        .messages()
        .get(userId="me", id=email_id, format="full")
        .execute()
    )

    headers = _parse_email_headers(msg.get("payload", {}).get("headers", []))
    body = _extract_plain_body(msg.get("payload", {}))

    # 添付ファイル情報
    parts = msg.get("payload", {}).get("parts", [])
    attachments = [
        p.get("filename", "")
        for p in parts
        if p.get("filename")
    ]

    return json.dumps({
        "id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "subject": headers.get("subject", "(件名なし)"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "date": headers.get("date", ""),
        "body": body,
        "label_ids": msg.get("labelIds", []),
        "attachments": attachments,
    }, ensure_ascii=False)


@tool
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
    bcc: str = "",
) -> str:
    """メールを送信します。

    Args:
        to: 宛先メールアドレス。
        subject: 件名。
        body: 本文。
        cc: CC（カンマ区切り）。省略可。
        bcc: BCC（カンマ区切り）。省略可。

    Returns:
        送信結果の JSON 文字列。type="email_sent" でレスポンスを返してください。
    """
    service = _get_service()
    message = _build_mime_message(to, subject, body, cc, bcc)

    result = (
        service.users()
        .messages()
        .send(userId="me", body=message)
        .execute()
    )

    logger.info("Sent email: %s", result.get("id"))
    return json.dumps({
        "sent": True,
        "id": result.get("id", ""),
        "thread_id": result.get("threadId", ""),
    }, ensure_ascii=False)


@tool
def search_emails(
    query: str,
    max_results: int = 10,
) -> str:
    """Gmail クエリでメールを検索します。

    Args:
        query: Gmail 検索クエリ（例: "from:example@gmail.com", "subject:会議", "is:unread"）。
        max_results: 最大取得件数。デフォルト10件。

    Returns:
        検索結果のメール一覧 JSON 文字列。type="email_list" でレスポンスを返してください。
    """
    service = _get_service()

    results = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    messages = results.get("messages", [])
    emails = []
    for msg_ref in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="metadata", metadataHeaders=["Subject", "From", "Date"])
            .execute()
        )
        headers = _parse_email_headers(msg.get("payload", {}).get("headers", []))
        emails.append({
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "subject": headers.get("subject", "(件名なし)"),
            "from": headers.get("from", ""),
            "date": headers.get("date", ""),
            "snippet": msg.get("snippet", ""),
            "label_ids": msg.get("labelIds", []),
        })

    return json.dumps(emails, ensure_ascii=False)


@tool
def delete_email(
    email_id: str,
    permanent: bool = False,
) -> str:
    """メールを削除します。

    Args:
        email_id: 削除対象のメッセージ ID。
        permanent: True の場合は完全削除。False の場合はゴミ箱に移動（デフォルト）。

    Returns:
        削除結果の JSON 文字列。type="email_deleted" でレスポンスを返してください。
    """
    service = _get_service()

    if permanent:
        service.users().messages().delete(userId="me", id=email_id).execute()
        logger.info("Permanently deleted email: %s", email_id)
    else:
        service.users().messages().trash(userId="me", id=email_id).execute()
        logger.info("Trashed email: %s", email_id)

    return json.dumps({
        "deleted": True,
        "email_id": email_id,
        "permanent": permanent,
    }, ensure_ascii=False)


@tool
def manage_labels(
    email_id: str,
    add_labels: str = "",
    remove_labels: str = "",
) -> str:
    """メールのラベルを管理します。

    Args:
        email_id: 対象のメッセージ ID。
        add_labels: 追加するラベル ID（カンマ区切り）。例: "STARRED,IMPORTANT"
        remove_labels: 削除するラベル ID（カンマ区切り）。例: "UNREAD"

    Returns:
        ラベル更新結果の JSON 文字列。type="email_labels_updated" でレスポンスを返してください。
    """
    service = _get_service()

    body = {}
    if add_labels:
        body["addLabelIds"] = [l.strip() for l in add_labels.split(",") if l.strip()]
    if remove_labels:
        body["removeLabelIds"] = [l.strip() for l in remove_labels.split(",") if l.strip()]

    result = (
        service.users()
        .messages()
        .modify(userId="me", id=email_id, body=body)
        .execute()
    )

    logger.info("Updated labels for email: %s", email_id)
    return json.dumps({
        "updated": True,
        "email_id": email_id,
        "label_ids": result.get("labelIds", []),
    }, ensure_ascii=False)


@tool
def save_draft(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
) -> str:
    """メールの下書きを保存します。

    Args:
        to: 宛先メールアドレス。
        subject: 件名。
        body: 本文。
        cc: CC（カンマ区切り）。省略可。

    Returns:
        下書き保存結果の JSON 文字列。type="draft_saved" でレスポンスを返してください。
    """
    service = _get_service()
    message = _build_mime_message(to, subject, body, cc)

    result = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": message})
        .execute()
    )

    logger.info("Saved draft: %s", result.get("id"))
    return json.dumps({
        "saved": True,
        "draft_id": result.get("id", ""),
        "message_id": result.get("message", {}).get("id", ""),
    }, ensure_ascii=False)
