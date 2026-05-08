"""
Tests for CONV-INST-003: Email confirmation lifecycle Mixpanel events.

Verifies that:
- email_confirmation_sent fires after signup (routes/auth_signup.py)
- email_confirmation_resent fires after resend (routes/auth_email.py)
- email_confirmation_clicked fires on first confirmation (routes/auth_email.py)
- All events are fire-and-forget (never raise even if analytics fails)
"""

from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# email_confirmation_sent — fires on signup
# ---------------------------------------------------------------------------

class TestEmailConfirmationSentOnSignup:
    """track_event('email_confirmation_sent') is called after user creation."""

    def _make_mock_user(self, user_id="uid-abc-123"):
        user = MagicMock()
        user.id = user_id
        return user

    def _make_mock_auth_result(self, user_id="uid-abc-123"):
        result = MagicMock()
        result.user = self._make_mock_user(user_id)
        return result

    def test_email_confirmation_sent_fires_after_signup(self):
        """track_event('email_confirmation_sent') is called with user_id after create_user."""
        mock_sb = MagicMock()
        auth_result = self._make_mock_auth_result("uid-abc-123")
        mock_sb.auth.admin.create_user.return_value = auth_result
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("routes.auth_signup._get_supabase", return_value=mock_sb), \
             patch("analytics_events.track_event") as mock_track, \
             patch("routes.auth_signup.is_disposable_email", return_value=False), \
             patch("routes.auth_signup.validate_password", return_value=(True, None)), \
             patch("routes.auth_signup.require_rate_limit", return_value=lambda: None), \
             patch.dict("sys.modules", {"audit": MagicMock(log_audit_event=MagicMock())}):

            from routes.auth_signup import signup
            from schemas.user import SignupRequest
            import asyncio

            request = MagicMock()
            body = SignupRequest(email="test@example.com", password="StrongPass123!")

            asyncio.run(signup(request, body, _rl=None))

            # Verify email_confirmation_sent was tracked
            sent_calls = [c for c in mock_track.call_args_list
                          if c.args and c.args[0] == "email_confirmation_sent"]
            assert len(sent_calls) >= 1, "email_confirmation_sent was not tracked"
            props = sent_calls[0].args[1] if len(sent_calls[0].args) > 1 else sent_calls[0].kwargs.get("properties", {})
            assert props.get("user_id") == "uid-abc-123"

    def test_email_confirmation_sent_never_raises_if_analytics_fails(self):
        """If track_event raises, signup still completes without error."""
        mock_sb = MagicMock()
        auth_result = self._make_mock_auth_result("uid-xyz-999")
        mock_sb.auth.admin.create_user.return_value = auth_result
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        with patch("routes.auth_signup._get_supabase", return_value=mock_sb), \
             patch("analytics_events.track_event", side_effect=RuntimeError("Mixpanel down")), \
             patch("routes.auth_signup.is_disposable_email", return_value=False), \
             patch("routes.auth_signup.validate_password", return_value=(True, None)), \
             patch("routes.auth_signup.require_rate_limit", return_value=lambda: None), \
             patch.dict("sys.modules", {"audit": MagicMock(log_audit_event=MagicMock())}):

            from routes.auth_signup import signup
            from schemas.user import SignupRequest
            import asyncio

            request = MagicMock()
            body = SignupRequest(email="test@example.com", password="StrongPass123!")

            # Should not raise even though analytics fails
            response = asyncio.run(signup(request, body, _rl=None))
            assert response is not None


# ---------------------------------------------------------------------------
# email_confirmation_resent — fires on resend endpoint
# ---------------------------------------------------------------------------

class TestEmailConfirmationResentEndpoint:
    """track_event('email_confirmation_resent') is called after resend succeeds."""

    @pytest.fixture
    def client(self):
        """Create test client with auth_email router."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routes.auth_email import router, _resend_timestamps

        app = FastAPI()
        app.include_router(router, prefix="/v1")
        _resend_timestamps.clear()
        yield TestClient(app)
        _resend_timestamps.clear()

    def test_resent_event_fires_on_success(self, client):
        """email_confirmation_resent is tracked when resend succeeds."""
        mock_sb = MagicMock()
        # No cooldown active
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        # Resend succeeds silently
        mock_sb.auth.resend.return_value = MagicMock()
        # Record resend succeeds
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("analytics_events.track_event") as mock_track:

            resp = client.post("/v1/auth/resend-confirmation", json={"email": "user@test.com"})

            assert resp.status_code == 200
            resent_calls = [c for c in mock_track.call_args_list
                            if c.args and c.args[0] == "email_confirmation_resent"]
            assert len(resent_calls) >= 1, "email_confirmation_resent was not tracked"

    def test_resent_event_never_raises_if_analytics_fails(self, client):
        """Resend endpoint still returns 200 even if analytics raises."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
        mock_sb.auth.resend.return_value = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("analytics_events.track_event", side_effect=RuntimeError("boom")):

            resp = client.post("/v1/auth/resend-confirmation", json={"email": "user@test.com"})
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# email_confirmation_clicked — fires on first confirmation in /auth/status
# ---------------------------------------------------------------------------

class TestEmailConfirmationClickedOnStatus:
    """email_confirmation_clicked is tracked on first confirmed status check."""

    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routes.auth_email import router

        app = FastAPI()
        app.include_router(router, prefix="/v1")
        yield TestClient(app)

    def _build_confirmed_user(self, email: str):
        user = MagicMock()
        user.email = email
        user.id = "user-confirmed-id"
        user.email_confirmed_at = "2026-05-08T10:00:00+00:00"
        return user

    def test_clicked_event_fires_on_first_confirm(self, client):
        """email_confirmation_clicked fires when status endpoint detects first confirm."""
        confirmed_user = self._build_confirmed_user("confirmed@test.com")

        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = [confirmed_user]
        # _record_confirm_db returns True (first time)
        # Select: empty rows (not yet confirmed in DB)
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        # Insert succeeds
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        with patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("analytics_events.track_event") as mock_track:

            resp = client.get("/v1/auth/status?email=confirmed@test.com")

            assert resp.status_code == 200
            assert resp.json()["confirmed"] is True

            clicked_calls = [c for c in mock_track.call_args_list
                             if c.args and c.args[0] == "email_confirmation_clicked"]
            assert len(clicked_calls) >= 1, "email_confirmation_clicked was not tracked"

    def test_clicked_event_not_fired_on_repeated_confirm(self, client):
        """email_confirmation_clicked is NOT fired again if already recorded."""
        confirmed_user = self._build_confirmed_user("confirmed@test.com")

        mock_sb = MagicMock()
        mock_sb.auth.admin.list_users.return_value = [confirmed_user]
        # _record_confirm_db returns False (already confirmed in DB)
        mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "existing-confirm-row"}
        ]

        with patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("analytics_events.track_event") as mock_track:

            resp = client.get("/v1/auth/status?email=confirmed@test.com")

            assert resp.status_code == 200
            clicked_calls = [c for c in mock_track.call_args_list
                             if c.args and c.args[0] == "email_confirmation_clicked"]
            assert len(clicked_calls) == 0, "email_confirmation_clicked fired on repeat (should be idempotent)"
