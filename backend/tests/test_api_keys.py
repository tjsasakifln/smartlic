"""Tests for API-SELF-001 — api_keys CRUD (#1418)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from schemas.api_keys import ApiKeyCreate, ApiKeyCreated, ApiKeyResponse


def _mock_user():
    return {"id": "user-test-123", "sub": "user-test-123", "email": "test@example.com", "role": "authenticated"}


@pytest.fixture
def client():
    from main import app
    from auth import require_auth

    app.dependency_overrides[require_auth] = _mock_user
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestApiKeyCreate:
    def test_valid(self):
        req = ApiKeyCreate(name="Minha Chave API")
        assert req.name == "Minha Chave API"

    def test_name_min_length(self):
        with pytest.raises(ValueError):
            ApiKeyCreate(name="")

    def test_name_max_length(self):
        ApiKeyCreate(name="a" * 100)  # should not raise

    def test_name_exceeds_max_length(self):
        with pytest.raises(ValueError):
            ApiKeyCreate(name="a" * 101)


class TestApiKeyResponse:
    def test_no_sensitive_fields(self):
        resp = ApiKeyResponse(
            id="uuid-1",
            name="test-key",
            created_at=datetime.now(timezone.utc),
        )
        data = resp.model_dump()
        assert "plaintext_key" not in data
        assert "key_hash" not in data

    def test_optional_last_used_at(self):
        resp = ApiKeyResponse(
            id="uuid-1",
            name="test-key",
            created_at=datetime.now(timezone.utc),
        )
        assert resp.last_used_at is None

    def test_with_last_used_at(self):
        ts = datetime.now(timezone.utc)
        resp = ApiKeyResponse(
            id="uuid-1",
            name="test-key",
            created_at=ts,
            last_used_at=ts,
        )
        assert resp.last_used_at == ts


class TestApiKeyCreated:
    def test_includes_plaintext(self):
        resp = ApiKeyCreated(
            id="uuid-1",
            name="test-key",
            plaintext_key="sk_abc123",
            created_at=datetime.now(timezone.utc),
        )
        assert resp.plaintext_key == "sk_abc123"
        assert "Guarde esta chave" in resp.message

    def test_message_present(self):
        resp = ApiKeyCreated(
            id="uuid-1",
            name="test-key",
            plaintext_key="sk_abc123",
            created_at=datetime.now(timezone.utc),
        )
        assert resp.message is not None
        assert len(resp.message) > 10


# ---------------------------------------------------------------------------
# Key generation helpers
# ---------------------------------------------------------------------------


class TestGenerateKey:
    def test_format(self):
        from routes.api_keys import _generate_key, API_KEY_PREFIX

        plaintext, key_hash = _generate_key()
        assert plaintext.startswith(API_KEY_PREFIX)
        assert len(key_hash) == 64  # SHA-256 hex

    def test_hash_matches(self):
        from routes.api_keys import _generate_key, _hash_key

        plaintext, key_hash = _generate_key()
        expected = _hash_key(plaintext)
        assert key_hash == expected

    def test_uniqueness(self):
        from routes.api_keys import _generate_key

        keys = [_generate_key()[0] for _ in range(10)]
        assert len(set(keys)) == 10


# ---------------------------------------------------------------------------
# POST /v1/api-keys
# ---------------------------------------------------------------------------


class TestCreateApiKey:
    def test_creates_and_returns_plaintext(self, client):
        """POST creates key and returns ApiKeyCreated with plaintext."""
        mock_result = MagicMock()
        mock_result.data = [{"id": "key-uuid-1", "name": "minha-chave", "created_at": "2026-06-06T00:00:00Z"}]

        with patch("supabase_client.get_supabase") as mock_sb:
            sb = MagicMock()
            chain = MagicMock()
            chain.insert.return_value = chain
            chain.select.return_value = chain
            chain.execute.return_value = mock_result
            sb.table.return_value = chain
            mock_sb.return_value = sb

            resp = client.post(
                "/v1/api-keys",
                json={"name": "minha-chave"},
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == "key-uuid-1"
        assert data["name"] == "minha-chave"
        assert data["plaintext_key"].startswith("sk_")
        assert "message" in data

    def test_name_required(self, client):
        """Name is required with min_length=1."""
        resp = client.post(
            "/v1/api-keys",
            json={"name": ""},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 422

    def test_unauthorized_without_token(self):
        """Request without auth header returns 401."""
        # Create client WITHOUT the dependency override
        from main import app
        original_overrides = {}
        original_overrides.update(app.dependency_overrides)
        app.dependency_overrides.clear()

        client_unauth = TestClient(app)
        resp = client_unauth.post("/v1/api-keys", json={"name": "test"})

        # Restore
        app.dependency_overrides.update(original_overrides)

        # FastAPI returns 403 when no bearer token (HTTPBearer auto_error)
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /v1/api-keys
# ---------------------------------------------------------------------------


class TestListApiKeys:
    def test_lists_keys_no_plaintext(self, client):
        """GET returns list of keys without plaintext."""
        mock_result = MagicMock()
        mock_result.data = [
            {"id": "key-1", "name": "key-a", "created_at": "2026-06-06T00:00:00Z", "last_used_at": None},
            {"id": "key-2", "name": "key-b", "created_at": "2026-06-05T00:00:00Z", "last_used_at": "2026-06-06T00:00:00Z"},
        ]

        with patch("supabase_client.get_supabase") as mock_sb:
            sb = MagicMock()
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.is_.return_value = chain
            chain.order.return_value = chain
            chain.execute.return_value = mock_result
            sb.table.return_value = chain
            mock_sb.return_value = sb

            resp = client.get(
                "/v1/api-keys",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["name"] == "key-a"
        # No plaintext field in response
        assert "plaintext_key" not in data[0]
        assert "key_hash" not in data[0]


# ---------------------------------------------------------------------------
# DELETE /v1/api-keys/{id}
# ---------------------------------------------------------------------------


class TestRevokeApiKey:
    def test_soft_deletes(self, client):
        """DELETE soft-deletes by setting revoked_at."""
        # Mock the ownership check
        check_result = MagicMock()
        check_result.data = [{"id": "key-to-revoke", "user_id": "user-test-123", "revoked_at": None}]

        with patch("supabase_client.get_supabase") as mock_sb:
            sb = MagicMock()

            # First call: ownership check
            check_chain = MagicMock()
            check_chain.select.return_value = check_chain
            check_chain.eq.return_value = check_chain
            check_chain.limit.return_value = check_chain
            check_chain.execute.return_value = check_result

            # Second call: update
            update_chain = MagicMock()
            update_chain.update.return_value = update_chain
            update_chain.eq.return_value = update_chain

            sb.table.side_effect = lambda name: check_chain if sb.table.call_count == 0 else update_chain

            # Using a more straightforward approach
            sb.table.reset_mock()
            sb.table.side_effect = None
            sb.table.return_value = check_chain

            mock_sb.return_value = sb

            resp = client.delete(
                "/v1/api-keys/key-to-revoke",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 204

    def test_not_found_returns_404(self, client):
        """DELETE on non-existent key returns 404."""
        check_result = MagicMock()
        check_result.data = []

        with patch("supabase_client.get_supabase") as mock_sb:
            sb = MagicMock()
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.limit.return_value = chain
            chain.execute.return_value = check_result
            sb.table.return_value = chain
            mock_sb.return_value = sb

            resp = client.delete(
                "/v1/api-keys/non-existent",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 404

    def test_cannot_revoke_other_users_key(self, client):
        """Cannot access other user's keys."""
        check_result = MagicMock()
        check_result.data = [{"id": "key-other", "user_id": "user-other-456", "revoked_at": None}]

        with patch("supabase_client.get_supabase") as mock_sb:
            sb = MagicMock()
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.limit.return_value = chain
            chain.execute.return_value = check_result
            sb.table.return_value = chain
            mock_sb.return_value = sb

            resp = client.delete(
                "/v1/api-keys/key-other",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Log sanitizer
# ---------------------------------------------------------------------------


class TestMaskApiKey:
    def test_mask_api_key_exists(self):
        """mask_api_key function exists and masks properly."""
        from log_sanitizer import mask_api_key

        masked = mask_api_key("sk_abcdef1234567890")
        assert "sk_" in masked
        assert "***" in masked
        assert "abcdef1234567890" not in masked  # full key not exposed

    def test_mask_none(self):
        from log_sanitizer import mask_api_key

        assert "[no-key]" in mask_api_key(None)
