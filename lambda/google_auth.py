"""Google OAuth2 トークン管理 (DynamoDB CRUD)."""

import hashlib
import hmac
import json
import logging
import os
import time
from urllib.parse import urlencode

import boto3
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "")
OAUTH_STATE_SECRET = os.environ.get("OAUTH_STATE_SECRET", "")
DYNAMODB_TOKEN_TABLE = os.environ.get("DYNAMODB_TOKEN_TABLE", "GoogleOAuthTokens")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _get_table():
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    return dynamodb.Table(DYNAMODB_TOKEN_TABLE)


# ---------- state パラメータ (HMAC署名) ----------


def encode_state(line_user_id: str) -> str:
    """LINE user_id を HMAC 署名付きの state パラメータにエンコード."""
    mac = hmac.new(
        OAUTH_STATE_SECRET.encode(), line_user_id.encode(), hashlib.sha256
    ).hexdigest()[:16]
    return f"{line_user_id}:{mac}"


def decode_state(state: str) -> str | None:
    """state パラメータをデコードし、署名検証. 成功すれば LINE user_id を返す."""
    parts = state.split(":", 1)
    if len(parts) != 2:
        return None
    line_user_id, mac = parts
    expected_mac = hmac.new(
        OAUTH_STATE_SECRET.encode(), line_user_id.encode(), hashlib.sha256
    ).hexdigest()[:16]
    if not hmac.compare_digest(mac, expected_mac):
        return None
    return line_user_id


# ---------- OAuth2 URL ----------


def build_auth_url(line_user_id: str) -> str:
    """Google OAuth2 認証 URL を生成."""
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": encode_state(line_user_id),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


# ---------- Token 交換 ----------


def exchange_code_for_tokens(code: str) -> dict:
    """Authorization code を access_token / refresh_token に交換."""
    import urllib.request

    data = urlencode(
        {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode()

    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


# ---------- DynamoDB CRUD ----------


def save_tokens(line_user_id: str, token_data: dict) -> None:
    """OAuth2 トークンを DynamoDB に保存."""
    table = _get_table()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    item = {
        "line_user_id": line_user_id,
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "token_expiry": int(time.time()) + token_data.get("expires_in", 3600),
        "updated_at": now,
    }
    # google_email はユーザー情報から取得できる場合に追加
    if "email" in token_data:
        item["google_email"] = token_data["email"]

    # 初回のみ created_at を設定
    existing = get_tokens(line_user_id)
    if existing and "created_at" in existing:
        item["created_at"] = existing["created_at"]
    else:
        item["created_at"] = now

    # refresh_token が空の場合は既存を保持
    if not item["refresh_token"] and existing:
        item["refresh_token"] = existing.get("refresh_token", "")

    table.put_item(Item=item)
    logger.info("Saved tokens for user %s", line_user_id)


def get_tokens(line_user_id: str) -> dict | None:
    """DynamoDB からトークンを取得."""
    table = _get_table()
    response = table.get_item(Key={"line_user_id": line_user_id})
    return response.get("Item")


def delete_tokens(line_user_id: str) -> None:
    """DynamoDB からトークンを削除."""
    table = _get_table()
    table.delete_item(Key={"line_user_id": line_user_id})
    logger.info("Deleted tokens for user %s", line_user_id)


# ---------- Credentials 取得 (自動リフレッシュ) ----------


def get_google_credentials(line_user_id: str) -> Credentials | None:
    """LINE user_id から Google Credentials を取得. 期限切れなら自動リフレッシュ."""
    token_data = get_tokens(line_user_id)
    if not token_data:
        return None

    creds = Credentials(
        token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URL,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )

    # トークンの有効期限チェック & リフレッシュ
    if token_data.get("token_expiry", 0) < time.time() + 60:
        if creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
            save_tokens(
                line_user_id,
                {
                    "access_token": creds.token,
                    "refresh_token": creds.refresh_token or token_data.get("refresh_token", ""),
                    "expires_in": 3600,
                },
            )
            logger.info("Refreshed token for user %s", line_user_id)
        else:
            logger.warning("No refresh token for user %s", line_user_id)
            return None

    return creds
