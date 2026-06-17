"""Tests for B2GOPS-015 — integrations webhooks CRUD + dispatch (#1522)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from schemas.integrations import (
    WebhookChannel,
    WebhookCreate,
    WebhookEvent,
    WebhookResponse,
    WebhookUpdate,
)

# ---------------------------------------------------------------------------
# UUID constants for testing
# ---------------------------------------------------------------------------

UUID_SLACK = "a1b2c3d4-0001-4000-8000-000000000001"
UUID_TEAMS = "b2c3d4e5-0002-4000-8000-000000000002"
UUID_EMAIL = "c3d4e5f6-0003-4000-8000-000000000003"
UUID_UPDATE = "d4e5f6a7-0004-4000-8000-000000000004"
UUID_DELETE = "e5f6a7b8-0005-4000-8000-000000000005"
UUID_OTHER = "f6a7b8c9-0006-4000-8000-000000000006"
UUID_TEST = "a7b8c9d0-0007-4000-8000-000000000007"

USER_ID = "user-test-123"
OTHER_USER_ID = "user-other-456"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _mock_user() -> dict:
    return {
        "id": USER_ID,
        "sub": USER_ID,
        "email": "test@smartlic.tech",
        "role": "authenticated",
    }


def _sample_slack_webhook_row(**overrides) -> dict:
    row = {
        "id": UUID_SLACK,
        "user_id": USER_ID,
        "channel": "slack",
        "label": "Meu Slack",
        "webhook_url": "https://hooks.slack.com/services/T00/B00/xxx",
        "email_target": None,
        "events": ["new_edital", "deadline_24h"],
        "is_active": True,
        "last_triggered_at": None,
        "created_at": "2026-06-17T00:00:00Z",
        "updated_at": "2026-06-17T00:00:00Z",
    }
    row.update(overrides)
    return row


def _sample_teams_webhook_row(**overrides) -> dict:
    row = {
        "id": UUID_TEAMS,
        "user_id": USER_ID,
        "channel": "teams",
        "label": "Meu Teams",
        "webhook_url": "https://outlook.office.com/webhook/xxx",
        "email_target": None,
        "events": ["new_edital"],
        "is_active": True,
        "last_triggered_at": None,
        "created_at": "2026-06-17T00:00:00Z",
        "updated_at": "2026-06-17T00:00:00Z",
    }
    row.update(overrides)
    return row


def _sample_email_webhook_row(**overrides) -> dict:
    row = {
        "id": UUID_EMAIL,
        "user_id": USER_ID,
        "channel": "email",
        "label": "Meu Email",
        "webhook_url": None,
        "email_target": "notify@example.com",
        "events": ["result_published"],
        "is_active": True,
        "last_triggered_at": None,
        "created_at": "2026-06-17T00:00:00Z",
        "updated_at": "2026-06-17T00:00:00Z",
    }
    row.update(overrides)
    return row


def _make_supabase_mock(initial_data: list[dict] | None = None):
    """Create a mock Supabase client with configurable results.

    If initial_data is provided, the first .execute() returns those rows.
    For multi-call scenarios, use side_effect_list.
    """
    sb = MagicMock()
    chain = MagicMock()
    result = MagicMock()
    result.data = initial_data or []

    # Chain methods return self
    chain.select.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.delete.return_value = chain
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.is_.return_value = chain
    chain.execute.return_value = result

    sb.table.return_value = chain
    return sb


@pytest.fixture
def client():
    """TestClient with mocked auth."""
    from main import app
    from auth import require_auth

    app.dependency_overrides[require_auth] = _mock_user
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestWebhookChannel:
    def test_slack(self):
        assert WebhookChannel.slack.value == "slack"

    def test_teams(self):
        assert WebhookChannel.teams.value == "teams"

    def test_email(self):
        assert WebhookChannel.email.value == "email"


class TestWebhookEvent:
    def test_new_edital(self):
        assert WebhookEvent.new_edital.value == "new_edital"

    def test_all_events_defined(self):
        expected = {
            "new_edital", "deadline_24h", "deadline_6h",
            "deadline_1h", "pregao_started", "result_published",
        }
        actual = {e.value for e in WebhookEvent}
        assert actual == expected


class TestWebhookCreate:
    def test_valid_slack(self):
        body = WebhookCreate(
            channel=WebhookChannel.slack,
            webhook_url="https://hooks.slack.com/xxx",
            events=[WebhookEvent.new_edital],
        )
        assert body.channel == WebhookChannel.slack
        assert body.webhook_url == "https://hooks.slack.com/xxx"
        assert body.events == [WebhookEvent.new_edital]

    def test_valid_email(self):
        body = WebhookCreate(
            channel=WebhookChannel.email,
            email_target="user@example.com",
        )
        assert body.email_target == "user@example.com"
        assert body.events == []

    def test_default_events_empty(self):
        body = WebhookCreate(
            channel=WebhookChannel.slack,
            webhook_url="https://hooks.slack.com/xxx",
        )
        assert body.events == []



class TestValidateWebhookUrl:
    """Tests for SSRF validation on webhook_url."""

    def test_valid_https_passes(self):
        """Valid HTTPS URLs pass validation."""
        from schemas.integrations import validate_webhook_url

        urls = [
            "https://hooks.slack.com/services/T00/B00/xxx",
            "https://outlook.office.com/webhook/xxx",
            "https://example.com/webhook",
            "https://sub.domain.com/path?query=1",
        ]
        for url in urls:
            assert validate_webhook_url(url) == url

    def test_none_passes(self):
        """None is allowed (field is optional)."""
        from schemas.integrations import validate_webhook_url

        assert validate_webhook_url(None) is None

    def test_http_rejected(self):
        """HTTP URLs are rejected."""
        from schemas.integrations import validate_webhook_url

        with pytest.raises(ValueError, match="scheme must be 'https'"):
            validate_webhook_url("http://hooks.slack.com/xxx")

    def test_localhost_rejected(self):
        """localhost is blocked."""
        from schemas.integrations import validate_webhook_url

        with pytest.raises(ValueError, match="host not allowed"):
            validate_webhook_url("https://localhost:5432/webhook")

    def test_loopback_rejected(self):
        """127.0.0.1 is blocked."""
        from schemas.integrations import validate_webhook_url

        with pytest.raises(ValueError, match="host not allowed"):
            validate_webhook_url("https://127.0.0.1:8000/webhook")

    def test_metadata_ip_rejected(self):
        """Cloud metadata IP 169.254.169.254 is blocked."""
        from schemas.integrations import validate_webhook_url

        with pytest.raises(ValueError, match="host not allowed"):
            validate_webhook_url("https://169.254.169.254/latest/meta-data/")

    def test_private_10_rejected(self):
        """10.x.x.x private range is blocked."""
        from schemas.integrations import validate_webhook_url

        with pytest.raises(ValueError, match="private IP range"):
            validate_webhook_url("https://10.0.0.1/webhook")

    def test_private_192_168_rejected(self):
        """192.168.x.x private range is blocked."""
        from schemas.integrations import validate_webhook_url

        with pytest.raises(ValueError, match="private IP range"):
            validate_webhook_url("https://192.168.1.1/webhook")

    def test_private_172_16_rejected(self):
        """172.16-31.x.x private range is blocked."""
        from schemas.integrations import validate_webhook_url

        with pytest.raises(ValueError, match="private IP range"):
            validate_webhook_url("https://172.16.0.1/webhook")

    def test_private_172_31_rejected(self):
        """172.31.x.x private range is blocked (upper bound)."""
        from schemas.integrations import validate_webhook_url

        with pytest.raises(ValueError, match="private IP range"):
            validate_webhook_url("https://172.31.255.255/webhook")

    def test_public_172_allowed(self):
        """172.32.x.x (public) is allowed."""
        from schemas.integrations import validate_webhook_url

        assert validate_webhook_url("https://172.32.0.1/webhook") == "https://172.32.0.1/webhook"

    def test_link_local_rejected(self):
        """169.254.x.x (link-local) is blocked."""
        from schemas.integrations import validate_webhook_url

        with pytest.raises(ValueError, match="link-local"):
            validate_webhook_url("https://169.254.1.1/webhook")

    def test_webhook_create_rejects_localhost(self):
        """WebhookCreate schema rejects localhost webhook_url via field_validator."""
        with pytest.raises(ValueError, match="host not allowed"):
            WebhookCreate(
                channel=WebhookChannel.slack,
                webhook_url="https://localhost:5432/webhook",
                events=[WebhookEvent.new_edital],
            )

    def test_webhook_update_rejects_private_ip(self):
        """WebhookUpdate schema rejects private IP webhook_url via field_validator."""
        with pytest.raises(ValueError, match="private IP range"):
            WebhookUpdate(
                webhook_url="https://10.0.0.1/webhook",
            )

    def test_api_create_rejects_http(self, client):
        """API endpoint returns 422 for HTTP webhook URLs."""
        sb = MagicMock()
        chain = MagicMock()

        check_result = MagicMock()
        check_result.data = []

        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.eq.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.is_.return_value = chain
        chain.execute.return_value = check_result

        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/integrations/webhooks",
                json={
                    "channel": "slack",
                    "label": "SSRF Test",
                    "webhook_url": "http://hooks.slack.com/xxx",
                    "events": ["new_edital"],
                },
                headers={"Authorization": "Bearer fake"},
            )

        # Should fail validation at Pydantic level -> 422
        assert resp.status_code == 422

    def test_dispatcher_blocks_ssrf(self):
        """_send_webhook_post returns False for blocked URLs (defense-in-depth)."""
        from services.webhook_dispatcher import _send_webhook_post

        import asyncio
        result = asyncio.run(
            _send_webhook_post("https://169.254.169.254/latest/meta-data/", {"test": True})
        )
        assert result is False

class TestWebhookResponse:
    def test_fields(self):
        resp = WebhookResponse(
            id="uuid-1",
            channel=WebhookChannel.slack,
            label="My Webhook",
            events=[WebhookEvent.new_edital],
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        data = resp.model_dump()
        assert data["id"] == "uuid-1"
        assert data["channel"] == "slack"
        assert data["is_active"] is True

    def test_optional_fields(self):
        resp = WebhookResponse(
            id="uuid-1",
            channel=WebhookChannel.email,
            events=[],
            is_active=False,
            created_at=datetime.now(timezone.utc),
        )
        assert resp.label is None
        assert resp.webhook_url is None
        assert resp.email_target is None
        assert resp.last_triggered_at is None

    def test_model_dump_serializable(self):
        """Ensure the response can be serialized to JSON."""
        resp = WebhookResponse(
            id="uuid-1",
            channel=WebhookChannel.slack,
            label="Test",
            events=[WebhookEvent.new_edital, WebhookEvent.deadline_24h],
            is_active=True,
            created_at=datetime.now(timezone.utc),
        )
        resp.model_dump_json()


class TestWebhookUpdate:
    def test_partial_update(self):
        body = WebhookUpdate(label="New Label")
        assert body.label == "New Label"
        assert body.is_active is None

    def test_all_fields_optional(self):
        body = WebhookUpdate()
        assert body.label is None
        assert body.webhook_url is None
        assert body.email_target is None
        assert body.events is None
        assert body.is_active is None

    def test_toggle_active(self):
        body = WebhookUpdate(is_active=False)
        assert body.is_active is False


# ---------------------------------------------------------------------------
# POST /v1/integrations/webhooks
# ---------------------------------------------------------------------------


class TestCreateWebhook:
    def test_create_slack(self, client):
        """POST creates a Slack webhook and returns WebhookResponse."""
        sb = _make_supabase_mock([_sample_slack_webhook_row()])

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/integrations/webhooks",
                json={
                    "channel": "slack",
                    "label": "Meu Slack",
                    "webhook_url": "https://hooks.slack.com/services/T00/B00/xxx",
                    "events": ["new_edital", "deadline_24h"],
                },
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["channel"] == "slack"
        assert data["label"] == "Meu Slack"
        assert data["events"] == ["new_edital", "deadline_24h"]

    def test_create_teams(self, client):
        """POST creates a Teams webhook."""
        sb = _make_supabase_mock([_sample_teams_webhook_row()])

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/integrations/webhooks",
                json={
                    "channel": "teams",
                    "label": "Meu Teams",
                    "webhook_url": "https://outlook.office.com/webhook/xxx",
                    "events": ["new_edital"],
                },
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["channel"] == "teams"
        assert data["label"] == "Meu Teams"

    def test_create_email(self, client):
        """POST creates an Email webhook."""
        sb = _make_supabase_mock([_sample_email_webhook_row()])

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.post(
                "/v1/integrations/webhooks",
                json={
                    "channel": "email",
                    "label": "Meu Email",
                    "email_target": "notify@example.com",
                    "events": ["result_published"],
                },
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["channel"] == "email"
        assert data["email_target"] == "notify@example.com"

    def test_slack_requires_webhook_url(self, client):
        """Slack webhook must include webhook_url."""
        resp = client.post(
            "/v1/integrations/webhooks",
            json={"channel": "slack", "label": "No URL"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 422

    def test_email_requires_target(self, client):
        """Email webhook must include email_target."""
        resp = client.post(
            "/v1/integrations/webhooks",
            json={"channel": "email", "label": "No Target"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 422

    def test_invalid_channel(self, client):
        """Invalid channel value returns 422."""
        resp = client.post(
            "/v1/integrations/webhooks",
            json={"channel": "pagerduty", "label": "Invalid"},
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 422

    def test_requires_auth(self):
        """Request without auth returns 401."""
        from main import app

        original = dict(app.dependency_overrides)
        app.dependency_overrides.clear()
        unauth_client = TestClient(app)
        resp = unauth_client.post(
            "/v1/integrations/webhooks",
            json={"channel": "slack", "webhook_url": "https://hooks.slack.com/xxx"},
        )
        app.dependency_overrides.update(original)
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /v1/integrations/webhooks
# ---------------------------------------------------------------------------


class TestListWebhooks:
    def test_lists_user_webhooks(self, client):
        """GET returns all webhooks for the authenticated user."""
        sb = _make_supabase_mock([
            _sample_slack_webhook_row(),
            _sample_email_webhook_row(),
        ])

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.get(
                "/v1/integrations/webhooks",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_empty_list(self, client):
        """Returns empty list when user has no webhooks."""
        sb = _make_supabase_mock([])

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.get(
                "/v1/integrations/webhooks",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# PATCH /v1/integrations/webhooks/{id}
# ---------------------------------------------------------------------------


class TestUpdateWebhook:
    def test_update_label(self, client):
        """PATCH updates webhook label."""
        sb = MagicMock()
        chain = MagicMock()

        # Ownership check result
        check_result = MagicMock()
        check_result.data = [{"id": UUID_UPDATE, "user_id": USER_ID}]
        # Update result
        update_result = MagicMock()
        update_result.data = [_sample_slack_webhook_row(
            id=UUID_UPDATE,
            label="Updated Label",
        )]

        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.is_.return_value = chain

        # First execute = ownership check, second = update
        chain.execute.side_effect = [check_result, update_result]

        # .eq() after .update().eq() needs to return chain for chaining
        # Simpler: make eq return chain always
        chain.eq.return_value = chain

        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.patch(
                f"/v1/integrations/webhooks/{UUID_UPDATE}",
                json={"label": "Updated Label"},
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] == "Updated Label"

    def test_update_events(self, client):
        """PATCH updates event subscriptions."""
        sb = MagicMock()
        chain = MagicMock()

        check_result = MagicMock()
        check_result.data = [{"id": UUID_UPDATE, "user_id": USER_ID}]
        update_result = MagicMock()
        update_result.data = [_sample_slack_webhook_row(
            id=UUID_UPDATE,
            events=["new_edital", "pregao_started", "result_published"],
        )]

        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.is_.return_value = chain
        chain.eq.return_value = chain
        chain.execute.side_effect = [check_result, update_result]

        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.patch(
                f"/v1/integrations/webhooks/{UUID_UPDATE}",
                json={
                    "events": [
                        "new_edital",
                        "pregao_started",
                        "result_published",
                    ],
                },
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "new_edital" in data["events"]
        assert "pregao_started" in data["events"]

    def test_update_not_found(self, client):
        """PATCH returns 404 for non-existent webhook."""
        sb = _make_supabase_mock([])

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.patch(
                f"/v1/integrations/webhooks/{UUID_UPDATE}",
                json={"label": "Noop"},
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 404

    def test_cannot_update_other_users_webhook(self, client):
        """User cannot update another user's webhook."""
        sb = MagicMock()
        chain = MagicMock()
        check_result = MagicMock()
        check_result.data = [{"id": UUID_OTHER, "user_id": OTHER_USER_ID}]

        chain.select.return_value = chain
        chain.insert.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.is_.return_value = chain
        chain.eq.return_value = chain
        chain.execute.return_value = check_result

        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.patch(
                f"/v1/integrations/webhooks/{UUID_OTHER}",
                json={"label": "Hacked"},
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /v1/integrations/webhooks/{id}
# ---------------------------------------------------------------------------


class TestDeleteWebhook:
    def test_deletes_own_webhook(self, client):
        """User can delete their own webhook."""
        sb = MagicMock()
        chain = MagicMock()

        check_result = MagicMock()
        check_result.data = [{"id": UUID_DELETE, "user_id": USER_ID}]

        chain.select.return_value = chain
        chain.delete.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = check_result

        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.delete(
                f"/v1/integrations/webhooks/{UUID_DELETE}",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 204

    def test_delete_not_found(self, client):
        """DELETE returns 404 for non-existent webhook."""
        sb = _make_supabase_mock([])

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.delete(
                f"/v1/integrations/webhooks/{UUID_DELETE}",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 404

    def test_cannot_delete_others_webhook(self, client):
        """User cannot delete another user's webhook."""
        sb = MagicMock()
        chain = MagicMock()

        check_result = MagicMock()
        check_result.data = [{"id": UUID_OTHER, "user_id": OTHER_USER_ID}]

        chain.select.return_value = chain
        chain.delete.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = check_result

        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.delete(
                f"/v1/integrations/webhooks/{UUID_OTHER}",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /v1/integrations/webhooks/{id}/test — Test notification
# ---------------------------------------------------------------------------


class TestTestWebhook:
    def test_test_slack(self, client):
        """POST test sends test notification to Slack webhook."""
        sb = MagicMock()
        chain = MagicMock()

        fetch_result = MagicMock()
        fetch_result.data = [_sample_slack_webhook_row(id=UUID_TEST)]

        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = fetch_result

        sb.table.return_value = chain

        with (
            patch("supabase_client.get_supabase", return_value=sb),
            patch(
                "services.webhook_dispatcher._send_slack",
                return_value=True,
            ),
        ):
            resp = client.post(
                f"/v1/integrations/webhooks/{UUID_TEST}/test",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "sucesso" in data["message"]
        assert data["channel"] == "slack"

    def test_test_email(self, client):
        """POST test sends test notification via email."""
        sb = MagicMock()
        chain = MagicMock()

        fetch_result = MagicMock()
        fetch_result.data = [_sample_email_webhook_row(id=UUID_TEST)]

        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = fetch_result

        sb.table.return_value = chain

        with (
            patch("supabase_client.get_supabase", return_value=sb),
            patch(
                "services.webhook_dispatcher._send_email",
                return_value=True,
            ),
        ):
            resp = client.post(
                f"/v1/integrations/webhooks/{UUID_TEST}/test",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["channel"] == "email"
        assert data["target"] == "notify@example.com"

    def test_test_not_found(self, client):
        """Test endpoint returns 404 for missing webhook."""
        sb = _make_supabase_mock([])

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.post(
                f"/v1/integrations/webhooks/{UUID_TEST}/test",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 404

    def test_test_other_user_forbidden(self, client):
        """User cannot test another user's webhook."""
        sb = MagicMock()
        chain = MagicMock()

        fetch_result = MagicMock()
        fetch_result.data = [_sample_slack_webhook_row(
            id=UUID_OTHER,
            user_id=OTHER_USER_ID,
        )]

        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = fetch_result

        sb.table.return_value = chain

        with patch("supabase_client.get_supabase", return_value=sb):
            resp = client.post(
                f"/v1/integrations/webhooks/{UUID_OTHER}/test",
                headers={"Authorization": "Bearer fake"},
            )

        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimit:
    def test_rate_limited_skip(self):
        """_is_rate_limited returns True when last trigger < 1h ago."""
        from services.webhook_dispatcher import _is_rate_limited

        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        webhook = {"last_triggered_at": recent.isoformat()}
        assert _is_rate_limited(webhook) is True

    def test_rate_limit_expired(self):
        """_is_rate_limited returns False when last trigger > 1h ago."""
        from services.webhook_dispatcher import _is_rate_limited

        old = datetime.now(timezone.utc) - timedelta(hours=2)
        webhook = {"last_triggered_at": old.isoformat()}
        assert _is_rate_limited(webhook) is False

    def test_rate_limit_no_history(self):
        """_is_rate_limited returns False when never triggered."""
        from services.webhook_dispatcher import _is_rate_limited

        webhook: dict = {}
        assert _is_rate_limited(webhook) is False

    def test_dispatch_respects_rate_limit(self):
        """dispatch_notification skips when rate limited."""
        from services.webhook_dispatcher import dispatch_notification

        recent = datetime.now(timezone.utc) - timedelta(minutes=30)
        webhook = {
            "id": "rate-test-id",
            "channel": "slack",
            "webhook_url": "https://hooks.slack.com/xxx",
            "is_active": True,
            "last_triggered_at": recent.isoformat(),
        }

        import asyncio
        result = asyncio.run(
            dispatch_notification(webhook, "new_edital", {"title": "Test"})
        )
        assert result is False


# ---------------------------------------------------------------------------
# Webhook dispatcher — message formatters
# ---------------------------------------------------------------------------


class TestSlackFormatter:
    def test_basic_format(self):
        from services.webhook_dispatcher import _format_slack_message

        msg = _format_slack_message(
            "new_edital",
            {"title": "Novo Edital", "description": "Descricao", "url": "https://smartlic.tech"},
        )
        assert "Novo Edital" in msg["text"]
        assert len(msg["attachments"]) == 1
        blocks = msg["attachments"][0]["blocks"]
        assert any("Novo Edital" in json.dumps(b) for b in blocks)

    def test_without_url(self):
        from services.webhook_dispatcher import _format_slack_message

        msg = _format_slack_message(
            "new_edital",
            {"title": "Novo Edital", "description": "Descricao"},
        )
        assert "Novo Edital" in msg["text"]


class TestTeamsFormatter:
    def test_basic_format(self):
        from services.webhook_dispatcher import _format_teams_message

        msg = _format_teams_message(
            "new_edital",
            {"title": "Novo Edital", "description": "Descricao", "url": "https://smartlic.tech"},
        )
        assert msg["@type"] == "MessageCard"
        assert "Novo Edital" in msg["title"]

    def test_without_url(self):
        from services.webhook_dispatcher import _format_teams_message

        msg = _format_teams_message(
            "new_edital",
            {"title": "Novo Edital"},
        )
        assert msg["potentialAction"] == []


class TestEmailFormatter:
    def test_html_format(self):
        from services.webhook_dispatcher import _format_email_html

        html = _format_email_html(
            "new_edital",
            {"title": "Novo Edital", "description": "Descricao", "url": "https://smartlic.tech"},
        )
        assert "Novo Edital" in html
        assert "smartlic.tech" in html
        assert "<!DOCTYPE html>" in html

    def test_subject_format(self):
        from services.webhook_dispatcher import _format_email_subject

        subject = _format_email_subject(
            "new_edital",
            {"title": "Novo Edital"},
        )
        assert "Novo Edital" in subject


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


class TestCrossUserIsolation:
    def test_other_user_sees_no_overlap(self):
        """Webhooks from different users don't overlap."""
        user_a_uuid = "00000000-0000-0000-0000-0000000000a1"
        user_b_uuid = "00000000-0000-0000-0000-0000000000b2"

        user_a_keys = [
            _sample_slack_webhook_row(id=user_a_uuid),
        ]
        user_b_uuid = "00000000-0000-0000-0000-0000000000b2"

        from main import app
        from auth import require_auth

        # User A
        sb_a = _make_supabase_mock(user_a_keys)
        with patch("supabase_client.get_supabase", return_value=sb_a):
            app.dependency_overrides[require_auth] = lambda: {
                "id": "user-a", "sub": "user-a",
                "email": "a@test.com", "role": "authenticated",
            }
            c = TestClient(app)
            resp_a = c.get("/v1/integrations/webhooks", headers={"Authorization": "Bearer fake"})
            app.dependency_overrides.clear()

        assert resp_a.status_code == 200
        ids_a = [w["id"] for w in resp_a.json()]
        assert user_a_uuid in ids_a
        assert user_b_uuid not in ids_a

    def test_send_email_dispatches(self):
        """send_email in webhook_dispatcher calls email_service.send_email."""
        from services.webhook_dispatcher import _send_email

        with patch("email_service.send_email") as mock_send:
            mock_send.return_value = "email-id-123"
            import asyncio
            result = asyncio.run(
                _send_email(
                    "user@example.com",
                    "test",
                    {"title": "Test", "description": "Test body"},
                )
            )
            assert result is True
            mock_send.assert_called_once()
