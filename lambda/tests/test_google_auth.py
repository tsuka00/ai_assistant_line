"""Google OAuth2 トークン管理のユニットテスト."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# lambda/ ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# google モジュールを mock
sys.modules.setdefault("google.oauth2.credentials", MagicMock())
sys.modules.setdefault("google.auth.transport.requests", MagicMock())

import google_auth


class TestStateEncoding:
    def test_encode_decode_roundtrip(self):
        google_auth.OAUTH_STATE_SECRET = "test-secret-key"
        user_id = "U1234567890abcdef"
        state = google_auth.encode_state(user_id)
        decoded = google_auth.decode_state(state)
        assert decoded == user_id

    def test_decode_invalid_state(self):
        google_auth.OAUTH_STATE_SECRET = "test-secret-key"
        assert google_auth.decode_state("invalid") is None
        assert google_auth.decode_state("user:wrongmac") is None

    def test_decode_tampered_state(self):
        google_auth.OAUTH_STATE_SECRET = "test-secret-key"
        state = google_auth.encode_state("U1234")
        # user_id を改ざん
        tampered = "U9999" + state[5:]
        assert google_auth.decode_state(tampered) is None


class TestBuildAuthUrl:
    def test_auth_url_contains_params(self):
        google_auth.GOOGLE_CLIENT_ID = "test-client-id"
        google_auth.GOOGLE_REDIRECT_URI = "https://example.com/callback"
        google_auth.OAUTH_STATE_SECRET = "secret"

        url = google_auth.build_auth_url("U1234")

        assert "client_id=test-client-id" in url
        assert "redirect_uri=" in url
        assert "response_type=code" in url
        assert "scope=" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "state=" in url


class TestTokenCRUD:
    @patch.object(google_auth, "_get_table")
    def test_save_tokens(self, mock_get_table):
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table

        # get_tokens returns None (first time)
        mock_table.get_item.return_value = {}

        google_auth.save_tokens("U1234", {
            "access_token": "access-123",
            "refresh_token": "refresh-456",
            "expires_in": 3600,
        })

        mock_table.put_item.assert_called_once()
        item = mock_table.put_item.call_args[1]["Item"]
        assert item["line_user_id"] == "U1234"
        assert item["access_token"] == "access-123"
        assert item["refresh_token"] == "refresh-456"

    @patch.object(google_auth, "_get_table")
    def test_get_tokens(self, mock_get_table):
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.get_item.return_value = {
            "Item": {"line_user_id": "U1234", "access_token": "test"}
        }

        result = google_auth.get_tokens("U1234")
        assert result["access_token"] == "test"

    @patch.object(google_auth, "_get_table")
    def test_get_tokens_not_found(self, mock_get_table):
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table
        mock_table.get_item.return_value = {}

        result = google_auth.get_tokens("U9999")
        assert result is None

    @patch.object(google_auth, "_get_table")
    def test_delete_tokens(self, mock_get_table):
        mock_table = MagicMock()
        mock_get_table.return_value = mock_table

        google_auth.delete_tokens("U1234")
        mock_table.delete_item.assert_called_once_with(Key={"line_user_id": "U1234"})
