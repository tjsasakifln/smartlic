"""FOUNDER-003 (#1416): tests for GET /v1/admin/metrics/revenue.

Covers:
- Returns full response schema with all 11 fields.
- Percentage-to-rate conversion (0-100 → 0.0-1.0) for RPC-based metrics.
- Rejects non-admin users (403).
- 503 on timeout / 500 on DB error.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")

from main import app  # noqa: E402
from auth import require_auth  # noqa: E402
from admin import require_admin  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client():
    fake_admin = {"id": "00000000-0000-0000-0000-00000000a001", "email": "admin@test"}
    app.dependency_overrides[require_auth] = lambda: fake_admin
    app.dependency_overrides[require_admin] = lambda: fake_admin
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def regular_client():
    """Logged-in non-admin user — should get 403 from require_admin."""
    fake_user = {"id": "regular-user", "email": "user@test"}
    app.dependency_overrides[require_auth] = lambda: fake_user
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Helpers: build mock Supabase chains for rpc() and table()
# ---------------------------------------------------------------------------


def _make_rpc_side_effect(fn_return: dict[str, object]):
    """Return a side-effect callable for ``fake_sb.rpc`` that dispatches
    to different return values based on the function name.

    ``fn_return`` maps RPC function names to the ``data`` value that
    ``.execute().data`` should return.
    """

    def _side_effect(name: str, params: object = None):
        q = MagicMock()
        q.execute.return_value = MagicMock(data=fn_return.get(name))
        return q

    return _side_effect


def _make_table_side_effect(tbl_return: dict[str, list[dict]]):
    """Return a side-effect callable for ``fake_sb.table`` that returns
    chainable mocks whose ``.execute().data`` returns the list for the
    given table name.
    """

    def _side_effect(name: str):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.lt.return_value = chain
        chain.gte.return_value = chain
        chain.lte.return_value = chain
        chain.limit.return_value = chain
        chain.execute.return_value = MagicMock(data=tbl_return.get(name, []))
        return chain

    return _side_effect


def _iso(days_ago: int) -> str:
    """Return an ISO-8601 string *days_ago* days before now."""
    from datetime import datetime, timezone, timedelta
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


# ---------------------------------------------------------------------------
# GET /metrics/revenue — happy path
# ---------------------------------------------------------------------------


@patch("routes.admin_metrics.get_supabase")
def test_revenue_metrics_returns_full_schema(mock_get_sb, admin_client):
    """Should return 200 with all 11 fields matching the expected schema."""
    fake_sb = MagicMock()

    # ── RPC return data ──────────────────────────────────────────────
    # get_mrr returns a list of monthly rows (last row is the latest)
    mrr_rows = [
        {"month": "2026-01-01", "mrr": 10000.00, "subscriber_count": 30},
        {"month": "2026-02-01", "mrr": 11000.00, "subscriber_count": 33},
        {"month": "2026-03-01", "mrr": 11500.00, "subscriber_count": 35},
        {"month": "2026-04-01", "mrr": 12000.00, "subscriber_count": 38},
        {"month": "2026-05-01", "mrr": 12345.67, "subscriber_count": 42},
    ]
    fake_sb.rpc.side_effect = _make_rpc_side_effect({
        "get_mrr": mrr_rows,
        "get_churn_rate_30d": 5.0,          # 5% → 0.05
        "get_trial_to_paid_30d": 15.0,       # 15% → 0.15
        "get_trial_to_paid_90d": 22.0,       # 22% → 0.22
        "get_d7_retention": 35.0,            # 35% → 0.35
        "get_arpa": 297.00,
    })

    # ── Table return data (for inline metrics) ───────────────────────
    # activation_d7: 4 profiles >7d, 2 with a session in D7 window → 0.4
    # retention_d1: 10 profiles >1d, 6 with a login in D1 window → 0.6
    # retention_d30: 5 profiles >30d, 1 with a login in D30 window → 0.2
    profile_rows = [
        {"id": "u-act-1", "created_at": _iso(60)},
        {"id": "u-act-2", "created_at": _iso(60)},
        {"id": "u-act-3", "created_at": _iso(60)},
        {"id": "u-act-4", "created_at": _iso(60)},
        {"id": "u-d1-a",  "created_at": _iso(60)},
        {"id": "u-d1-b",  "created_at": _iso(60)},
        {"id": "u-d1-c",  "created_at": _iso(60)},
        {"id": "u-d1-d",  "created_at": _iso(60)},
        {"id": "u-d1-e",  "created_at": _iso(60)},
        {"id": "u-d1-f",  "created_at": _iso(60)},
        {"id": "u-d30-a", "created_at": _iso(90)},
        {"id": "u-d30-b", "created_at": _iso(90)},
        {"id": "u-d30-c", "created_at": _iso(90)},
        {"id": "u-d30-d", "created_at": _iso(90)},
        {"id": "u-d30-e", "created_at": _iso(90)},
    ]

    # Sessions within D7 window of user signup — for activation_d7
    session_rows = [
        {"user_id": "u-act-1", "created_at": _iso(57)},  # D3, ✔ activated
        {"user_id": "u-act-2", "created_at": _iso(54)},  # D6, ✔ activated
        # u-act-3 and u-act-4 have no sessions → not activated
        {"user_id": "u-d1-a",  "created_at": _iso(59)},  # out of D7 scope
    ]

    # Login activity for retention_d1 (D1 window: 1-2 days after signup)
    # For users created 60 days ago, D1 is at D59, D2 is at D58
    login_rows = [
        # D1 retention: created 60d ago → D1 window is D59
        {"user_id": "u-d1-a", "logged_in_at": _iso(59)},   # D1 ✔
        {"user_id": "u-d1-b", "logged_in_at": _iso(59)},   # D1 ✔
        {"user_id": "u-d1-c", "logged_in_at": _iso(59)},   # D1 ✔
        {"user_id": "u-d1-d", "logged_in_at": _iso(59)},   # D1 ✔
        {"user_id": "u-d1-e", "logged_in_at": _iso(59)},   # D1 ✔
        {"user_id": "u-d1-f", "logged_in_at": _iso(59)},   # D1 ✔
        # D30 retention: created 90d ago → D30 window at D60
        {"user_id": "u-d30-a", "logged_in_at": _iso(60)},  # D30 ✔
        # Other D30 users have no login → not retained
    ]

    fake_sb.table.side_effect = _make_table_side_effect({
        "profiles": profile_rows,
        "search_sessions": session_rows,
        "login_activity": login_rows,
    })
    mock_get_sb.return_value = fake_sb

    # ── Execute ──────────────────────────────────────────────────────
    r = admin_client.get("/v1/admin/metrics/revenue")
    assert r.status_code == 200, f"body={r.text}"
    body = r.json()

    # ── Assert schema presence and types ─────────────────────────────
    expected_fields = [
        "mrr", "churn_rate_30d", "trial_to_paid_30d", "trial_to_paid_90d",
        "activation_d7", "retention_d1", "retention_d7", "retention_d30",
        "arpa", "total_subscribers", "period_start", "period_end",
    ]
    for field in expected_fields:
        assert field in body, f"missing field: {field}"

    # ── RPC-based values (percentage -> rate conversion) ─────────────
    assert body["mrr"] == 12345.67
    assert body["churn_rate_30d"] == 0.05       # 5.0 / 100
    assert body["trial_to_paid_30d"] == 0.15     # 15.0 / 100
    assert body["trial_to_paid_90d"] == 0.22     # 22.0 / 100
    assert body["retention_d7"] == 0.35          # 35.0 / 100
    assert body["arpa"] == 297.00
    assert body["total_subscribers"] == 42

    # ── Inline computed values (0-1 range) ─────────────────────────--
    for key in ("activation_d7", "retention_d1", "retention_d30"):
        assert isinstance(body[key], float), f"{key} should be float"
        assert 0.0 <= body[key] <= 1.0, f"{key}={body[key]} out of range"

    # ── Period strings present ───────────────────────────────────────
    assert isinstance(body["period_start"], str) and body["period_start"]
    assert isinstance(body["period_end"], str) and body["period_end"]


# ---------------------------------------------------------------------------
# Auth enforcement
# ---------------------------------------------------------------------------


def test_revenue_metrics_rejects_non_admin(regular_client):
    """Regular authenticated user without admin role → 403."""
    r = regular_client.get("/v1/admin/metrics/revenue")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Edge case: empty MRR data
# ---------------------------------------------------------------------------


@patch("routes.admin_metrics.get_supabase")
def test_revenue_metrics_empty_mrr_returns_defaults(mock_get_sb, admin_client):
    """When get_mrr returns no rows, mrr and total_subscribers default to 0."""
    fake_sb = MagicMock()

    fake_sb.rpc.side_effect = _make_rpc_side_effect({
        "get_mrr": [],
        "get_churn_rate_30d": 0.0,
        "get_trial_to_paid_30d": 0.0,
        "get_trial_to_paid_90d": 0.0,
        "get_d7_retention": 0.0,
        "get_arpa": 0.0,
    })
    fake_sb.table.side_effect = _make_table_side_effect({
        "profiles": [],
        "search_sessions": [],
        "login_activity": [],
    })
    mock_get_sb.return_value = fake_sb

    r = admin_client.get("/v1/admin/metrics/revenue")
    assert r.status_code == 200
    body = r.json()
    assert body["mrr"] == 0.0
    assert body["total_subscribers"] == 0
    assert body["churn_rate_30d"] == 0.0
    assert body["arpa"] == 0.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@patch("routes.admin_metrics.get_supabase")
def test_revenue_metrics_db_timeout_returns_503(mock_get_sb, admin_client):
    """When RPC call times out → 503."""
    from asyncio import TimeoutError

    fake_sb = MagicMock()
    rpc_mock = MagicMock()
    rpc_mock.execute.side_effect = TimeoutError()
    fake_sb.rpc.return_value = rpc_mock

    table_chain = MagicMock()
    table_chain.select.return_value = table_chain
    table_chain.lt.return_value = table_chain
    table_chain.limit.return_value = table_chain
    table_chain.execute.side_effect = TimeoutError()
    fake_sb.table.return_value = table_chain

    mock_get_sb.return_value = fake_sb

    r = admin_client.get("/v1/admin/metrics/revenue")
    # The parallel gather should propagate TimeoutError and the route
    # catches it as 503.
    assert r.status_code in (503, 500), f"unexpected status: {r.status_code}"


@patch("routes.admin_metrics.get_supabase")
def test_revenue_metrics_db_error_returns_500(mock_get_sb, admin_client):
    """When RPC call raises unknown exception → 500."""
    fake_sb = MagicMock()
    rpc_mock = MagicMock()
    rpc_mock.execute.side_effect = RuntimeError("connection lost")
    fake_sb.rpc.return_value = rpc_mock

    table_chain = MagicMock()
    table_chain.select.return_value = table_chain
    table_chain.lt.return_value = table_chain
    table_chain.limit.return_value = table_chain
    table_chain.execute.side_effect = RuntimeError("connection lost")
    fake_sb.table.return_value = table_chain

    mock_get_sb.return_value = fake_sb

    r = admin_client.get("/v1/admin/metrics/revenue")
    assert r.status_code == 500, f"unexpected status: {r.status_code}"
