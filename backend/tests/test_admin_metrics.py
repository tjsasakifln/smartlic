"""Tests for FOUNDER-003/005: admin metrics dashboard + Mixpanel tracking.

Validates:
- 403 for non-admin users (require_admin gate)
- Correct response shape for admin users
- Mixpanel event fired with correct aggregated properties (no PII)
- Mixpanel failure does NOT break the response (fire-and-forget)
- No PII in the response snapshot
- Audit log event fires on access
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import require_auth
from rate_limiter import require_rate_limit

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

FAKE_ADMIN = {
    "id": "admin-123-uuid",
    "sub": "admin-123-uuid",
    "email": "admin@smartlic.tech",
    "role": "authenticated",
}

FAKE_NON_ADMIN = {
    "id": "user-456-uuid",
    "sub": "user-456-uuid",
    "email": "user@example.com",
    "role": "authenticated",
}

# Mock RPC data
MOCK_MRR_DATA = [
    {"month": "2026-05-01", "mrr": 15000.00, "subscriber_count": 12},
    {"month": "2026-06-01", "mrr": 18250.00, "subscriber_count": 15},
]

MOCK_CHURN_DATA = [{"get_churn_rate_30d": 3.5}]
MOCK_TRIAL_30D_DATA = [{"get_trial_to_paid_30d": 12.0}]
MOCK_TRIAL_90D_DATA = [{"get_trial_to_paid_90d": 18.5}]
MOCK_RETENTION_DATA = [{"get_d7_retention": 45.0}]
MOCK_ARPA_DATA = [{"get_arpa": 1216.67}]
MOCK_SUBSCRIBERS_COUNT = 15


def _rpc_side_effect(name, params=None):
    """Side effect for _call_rpc mock — dispatches by RPC name."""
    if name == "get_mrr":
        return MOCK_MRR_DATA
    elif name == "get_churn_rate_30d":
        return MOCK_CHURN_DATA
    elif name == "get_trial_to_paid_30d":
        return MOCK_TRIAL_30D_DATA
    elif name == "get_trial_to_paid_90d":
        return MOCK_TRIAL_90D_DATA
    elif name == "get_d7_retention":
        return MOCK_RETENTION_DATA
    elif name == "get_arpa":
        return MOCK_ARPA_DATA
    return []


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _setup_admin_router():
    """Register the admin_metrics router with dependency overrides.

    Each test gets a fresh app so overrides don't leak between tests.
    """
    from routes.admin_metrics import router

    app = FastAPI()
    app.include_router(router)

    # Bypass rate limiter in tests
    app.dependency_overrides[require_rate_limit(60, 60)] = lambda: None
    app.dependency_overrides[require_rate_limit(20, 60)] = lambda: None

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
def _admin_auth(_setup_admin_router):
    """Set up admin authentication overrides on the app."""
    import admin
    app = _setup_admin_router
    app.dependency_overrides[require_auth] = lambda: FAKE_ADMIN
    app.dependency_overrides[admin.require_admin] = lambda: FAKE_ADMIN
    return app


@pytest.fixture
def _mock_all_rpcs():
    """Mock all _call_rpc calls to return standard test data."""
    with patch("routes.admin_metrics._call_rpc") as mock_rpc:
        mock_rpc.side_effect = _rpc_side_effect
        yield mock_rpc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPermissionGate:
    """FOUNDER-005 AC2: Permission check — 401/403 for non-admin."""

    def test_non_admin_gets_403(self, _setup_admin_router):
        """Non-admin user must receive 403 Forbidden."""
        import admin
        app = _setup_admin_router
        app.dependency_overrides[require_auth] = lambda: FAKE_NON_ADMIN

        async def _fail_non_admin(_user=None):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Acesso restrito a administradores")

        app.dependency_overrides[admin.require_admin] = _fail_non_admin

        client = TestClient(app)
        response = client.get("/admin/metrics/founder")

        assert response.status_code == 403
        assert "restrito" in response.json().get("detail", "").lower()

    def test_admin_gets_200(self, _setup_admin_router):
        """Admin user must receive 200 OK with valid metrics."""
        import admin
        app = _setup_admin_router
        app.dependency_overrides[require_auth] = lambda: FAKE_ADMIN
        app.dependency_overrides[admin.require_admin] = lambda: FAKE_ADMIN

        with patch("routes.admin_metrics._call_rpc") as mock_rpc:
            mock_rpc.side_effect = _rpc_side_effect
            with patch("routes.admin_metrics._get_total_subscribers") as mock_subs:
                mock_subs.return_value = 15

                client = TestClient(app)
                response = client.get("/admin/metrics/founder")

        assert response.status_code == 200


class TestMetricsStructure:
    """FOUNDER-003/005: Response shape validation."""

    def test_response_contains_all_fields(self, _admin_auth, _mock_all_rpcs):
        """Response must include all expected metric fields."""
        with patch("routes.admin_metrics._get_total_subscribers") as mock_subs:
            mock_subs.return_value = 15

            client = TestClient(_admin_auth)
            response = client.get("/admin/metrics/founder")

        assert response.status_code == 200
        data = response.json()

        assert "mrr" in data
        assert "churn_rate_30d" in data
        assert "trial_to_paid_30d" in data
        assert "trial_to_paid_90d" in data
        assert "d7_retention" in data
        assert "arpa" in data
        assert "total_subscribers" in data
        assert "lookup_duration_ms" in data

        assert len(data["mrr"]) == 2
        assert data["mrr"][0]["month"] == "2026-05-01"
        assert data["mrr"][0]["mrr"] == 15000.0
        assert data["mrr"][0]["subscriber_count"] == 12

        assert data["churn_rate_30d"] == 3.5
        assert data["trial_to_paid_30d"] == 12.0
        assert data["trial_to_paid_90d"] == 18.5
        assert data["d7_retention"] == 45.0
        assert data["arpa"] == 1216.67
        assert data["total_subscribers"] == 15
        assert data["lookup_duration_ms"] > 0

    def test_no_pii_in_response(self, _admin_auth, _mock_all_rpcs):
        """Response must NOT contain PII (email, name, etc.)."""
        with patch("routes.admin_metrics._get_total_subscribers") as mock_subs:
            mock_subs.return_value = 15

            client = TestClient(_admin_auth)
            response = client.get("/admin/metrics/founder")

        assert response.status_code == 200
        data = response.json()
        body_str = str(data).lower()

        assert "@" not in body_str
        assert "admin-123-uuid" not in body_str
        assert "admin@smartlic.tech" not in body_str


class TestMixpanelTracking:
    """FOUNDER-005 AC1: Mixpanel founder_metrics_viewed event."""

    def test_mixpanel_event_fired(self, _admin_auth, _mock_all_rpcs):
        """Mixpanel track_event must be called with founder_metrics_viewed."""
        with patch("routes.admin_metrics._get_total_subscribers") as mock_subs:
            mock_subs.return_value = 15

            with patch("routes.admin_metrics.track_event") as mock_track:
                client = TestClient(_admin_auth)
                response = client.get("/admin/metrics/founder")

        assert response.status_code == 200
        mock_track.assert_called_once()

        call_args = mock_track.call_args
        assert call_args[0][0] == "founder_metrics_viewed"

        props = call_args[0][1]
        assert "user_id" in props
        assert props["user_id"] == FAKE_ADMIN["sub"]
        assert props["mrr"] == 18250.0  # Latest month MRR
        assert props["churn_rate_30d"] == 3.5
        assert props["trial_to_paid_30d"] == 12.0
        assert props["trial_to_paid_90d"] == 18.5
        assert props["d7_retention"] == 45.0
        assert props["arpa"] == 1216.67
        assert props["total_subscribers"] == 15

        # No PII in properties
        assert "email" not in props
        assert "name" not in props

    def test_mixpanel_failure_does_not_break(self, _admin_auth, _mock_all_rpcs):
        """Mixpanel failure must NOT prevent 200 response (fire-and-forget).

        The route wraps ``track_event`` in try/except so that even if the
        analytics call raises unexpectedly, the response is still 200.
        """
        with patch("routes.admin_metrics._get_total_subscribers") as mock_subs:
            mock_subs.return_value = 15

            with patch("routes.admin_metrics.track_event") as mock_track:
                mock_track.side_effect = Exception("Mixpanel connection error")

                client = TestClient(_admin_auth)
                response = client.get("/admin/metrics/founder")

        assert response.status_code == 200
        data = response.json()
        assert data["total_subscribers"] == 15


class TestAuditLog:
    """FOUNDER-005 AC3: Audit log on founder metrics access."""

    def test_audit_log_fired(self, _admin_auth, _mock_all_rpcs):
        """Audit log must be called with correct event type."""
        with patch("routes.admin_metrics._get_total_subscribers") as mock_subs:
            mock_subs.return_value = 15

            with patch("routes.admin_metrics.audit_logger") as mock_audit:
                mock_audit.log = AsyncMock()

                client = TestClient(_admin_auth)
                response = client.get("/admin/metrics/founder")

        assert response.status_code == 200
        mock_audit.log.assert_called_once()
        call_kwargs = mock_audit.log.call_args.kwargs
        assert call_kwargs["event_type"] == "admin.founder_metrics_viewed"
        assert call_kwargs["actor_id"] == FAKE_ADMIN["sub"]

        details = call_kwargs.get("details", {})
        assert details["total_subscribers"] == 15
        assert "email" not in str(details).lower()

    def test_audit_log_failure_does_not_break(self, _admin_auth, _mock_all_rpcs):
        """Audit log failure must NOT prevent 200 response."""
        with patch("routes.admin_metrics._get_total_subscribers") as mock_subs:
            mock_subs.return_value = 15

            with patch("routes.admin_metrics.audit_logger") as mock_audit:
                mock_audit.log = AsyncMock(side_effect=Exception("DB error"))

                client = TestClient(_admin_auth)
                response = client.get("/admin/metrics/founder")

        assert response.status_code == 200


class TestEdgeCases:
    """Edge case handling for founder metrics."""

    def test_empty_mrr_returns_empty_list(self, _admin_auth):
        """Empty MRR data should return [] for mrr field."""
        with patch("routes.admin_metrics._call_rpc") as mock_rpc:
            def side_effect(name, params=None):
                if name == "get_mrr":
                    return []
                return _rpc_side_effect(name, params)
            mock_rpc.side_effect = side_effect

            with patch("routes.admin_metrics._get_total_subscribers") as mock_subs:
                mock_subs.return_value = 0

                client = TestClient(_admin_auth)
                response = client.get("/admin/metrics/founder")

        assert response.status_code == 200
        data = response.json()
        assert data["mrr"] == []
        assert data["total_subscribers"] == 0

    def test_rpc_failure_returns_502(self, _admin_auth):
        """RPC failure should return 502 Bad Gateway."""
        from fastapi import HTTPException

        async def _failing_rpc(name, params=None):
            raise HTTPException(
                status_code=502,
                detail=f"Erro ao consultar indicador: {name}",
            )

        with patch("routes.admin_metrics._call_rpc", side_effect=_failing_rpc):
            client = TestClient(_admin_auth)
            response = client.get("/admin/metrics/founder")

        assert response.status_code == 502
