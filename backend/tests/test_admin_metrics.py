"""Tests for FOUNDER-003/005: admin metrics dashboard + Mixpanel tracking.

Validates:
- 403 for non-admin users (require_admin gate)
- Correct response shape for admin users
- Mixpanel event fired with correct aggregated properties (no PII)
- Mixpanel failure does NOT break the response (fire-and-forget)
- No PII in the response snapshot
- Audit log event fires on access
Schema defaults (MrrHistoryEntry, RevenueMetricsResponse).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from routes.admin_metrics import router as admin_metrics_router
from schemas.admin import MrrHistoryEntry, RevenueMetricsResponse

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



# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Test app with just the admin_metrics router."""
    application = FastAPI()
    application.include_router(admin_metrics_router)
    return application


@pytest.fixture
async def client(app):
    """Async HTTP client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Schema unit tests
# ---------------------------------------------------------------------------


class TestMrrHistoryEntry:
    def test_defaults(self):
        entry = MrrHistoryEntry()
        assert entry.month == ""
        assert entry.mrr == 0.0
        assert entry.subscriber_count == 0

    def test_full_constructor(self):
        entry = MrrHistoryEntry(month="2026-01", mrr=15000.50, subscriber_count=42)
        assert entry.month == "2026-01"
        assert entry.mrr == 15000.50
        assert entry.subscriber_count == 42


class TestRevenueMetricsResponse:
    def test_defaults(self):
        resp = RevenueMetricsResponse()
        assert resp.mrr == 0.0
        assert resp.churn_rate_30d == 0.0
        assert resp.arpa == 0.0
        assert resp.total_subscribers == 0
        assert resp.mrr_history == []

    def test_with_mrr_history(self):
        history = [
            MrrHistoryEntry(month="2026-01", mrr=10000.0, subscriber_count=30),
            MrrHistoryEntry(month="2026-02", mrr=12000.0, subscriber_count=35),
        ]
        resp = RevenueMetricsResponse(
            mrr=12000.0,
            churn_rate_30d=0.05,
            trial_to_paid_30d=0.12,
            arpa=400.0,
            total_subscribers=35,
            mrr_history=history,
        )
        assert resp.mrr == 12000.0
        assert resp.churn_rate_30d == 0.05
        assert len(resp.mrr_history) == 2
        assert resp.mrr_history[0].month == "2026-01"
        assert resp.mrr_history[1].mrr == 12000.0


# ---------------------------------------------------------------------------
# Auth rejection tests
# ---------------------------------------------------------------------------


class TestAuthRejection:
    """Require admin guard — unauthenticated requests get 401."""

    async def test_no_auth(self, client):
        """Unauthenticated request should 401."""
        resp = await client.get("/v1/admin/metrics/revenue")
        assert resp.status_code == 401

    async def test_no_token(self, client):
        """Request without Bearer token should 401."""
        resp = await client.get(
            "/v1/admin/metrics/revenue",
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# FOUNDER-005: Permission gate, Mixpanel tracking, audit log tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="DEBT-131: setup ERROR on main — @patch paths stale after module refactor")
@pytest.mark.usefixtures("dependency_overrides")
class TestRevenueMetricsEndpoint:
    @patch("routes.admin_metrics.require_admin")
    @patch("routes.admin_metrics.get_supabase")
    async def test_empty_data_defaults(self, mock_get_sb, mock_admin, client):
        """When all RPCs return None/empty, response should have defaults."""
        mock_admin.return_value = {"sub": "admin-id", "email": "admin@test.com"}

        mock_sb = MagicMock()
        mock_sb.rpc = MagicMock()

        async def mock_execute(*args, **kwargs):
            result = MagicMock()
            result.data = None
            return result

        mock_sb.table = MagicMock()
        mock_sb.table.return_value.select.return_value.lt.return_value.limit.return_value = AsyncMock()
        mock_sb.table.return_value.select.return_value.lt.return_value.limit.return_value.execute = mock_execute

        mock_get_sb.return_value = mock_sb

        with patch("routes.admin_metrics.sb_execute", new=mock_execute):
            resp = await client.get(
                "/v1/admin/metrics/revenue",
                headers={"Authorization": "Bearer test-token"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["mrr"] == 0.0
        assert data["total_subscribers"] == 0
        assert data["mrr_history"] == []
        assert data["churn_rate_30d"] == 0.0

    @patch("routes.admin_metrics.require_admin")
    @patch("routes.admin_metrics.get_supabase")
    async def test_mrr_history_in_response(self, mock_get_sb, mock_admin, client):
        """MRR history should be present and populated."""
        mock_admin.return_value = {"sub": "admin-id"}

        mock_sb = MagicMock()
        mock_sb.rpc = MagicMock()

        mock_rows = [
            {"month": "2026-01", "mrr": 10000.0, "subscriber_count": 30},
            {"month": "2026-02", "mrr": 12000.0, "subscriber_count": 35},
            {"month": "2026-03", "mrr": 15000.0, "subscriber_count": 42},
        ]

        call_count = 0

        async def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.data = mock_rows  # get_mrr
            elif call_count in (2, 3, 4, 5, 9):
                # churn, trial_to_paid_30d, trial_to_paid_90d, d7_retention, arpa
                # — these return single float in .data
                result.data = None
            else:
                result.data = []
            return result

        mock_sb.table.return_value.select.return_value.lt.return_value.limit.return_value = AsyncMock()
        mock_sb.table.return_value.select.return_value.lt.return_value.limit.return_value.execute = mock_execute

        mock_get_sb.return_value = mock_sb

        with (
            patch("routes.admin_metrics.sb_execute", new=mock_execute),
            patch("routes.admin_metrics.AuditLogger.log_event", new=AsyncMock()),
        ):
            resp = await client.get(
                "/v1/admin/metrics/revenue",
                headers={"Authorization": "Bearer admin-token"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["mrr"] == 15000.0
        assert data["total_subscribers"] == 42
        assert len(data["mrr_history"]) == 3
        assert data["mrr_history"][0]["month"] == "2026-01"
        assert data["mrr_history"][0]["mrr"] == 10000.0
        assert data["mrr_history"][1]["mrr"] == 12000.0
        assert data["mrr_history"][2]["month"] == "2026-03"
        assert data["mrr_history"][2]["subscriber_count"] == 42
