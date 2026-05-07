"""#782: Tests for founding_policy lifetime pivot.

Covers:
- GET /availability exposes price_brl_cents and offer_mode from RPC v2.
- Safe defaults when RPC v2 columns are absent (v1 RPC still live during deploy gap).
- price_brl_cents=99700 and offer_mode='lifetime' on the canonical path.
- Fallback values on RPC exception (same safe defaults).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")

from routes.founding import router as founding_router  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_with_founding():
    app = FastAPI()
    app.include_router(founding_router, prefix="/v1")
    return app


def _make_supabase_mock(rpc_data: list[dict]) -> MagicMock:
    """Build a fake supabase client whose rpc() returns ``rpc_data``."""
    fake_sb = MagicMock()
    rpc_result = MagicMock(data=rpc_data)
    fake_sb.rpc.return_value = MagicMock(execute=MagicMock(return_value=rpc_result))
    fake_sb.table.return_value = fake_sb
    fake_sb.select.return_value = fake_sb
    fake_sb.eq.return_value = fake_sb
    fake_sb.limit.return_value = fake_sb
    fake_sb.execute.return_value = MagicMock(data=[])
    return fake_sb


# ---------------------------------------------------------------------------
# price_brl_cents + offer_mode returned from RPC v2
# ---------------------------------------------------------------------------


@patch("routes.founding.get_supabase")
def test_availability_exposes_price_brl_cents_and_offer_mode(mock_get_sb, app_with_founding):
    """RPC v2 supplies offer_mode and price_brl_cents — route must surface both."""
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": True,
            "seats_remaining": 47,
            "seats_total": 50,
            "deadline_at": "2026-06-30T23:59:59-03:00",
            "paused": False,
            "reason": "available",
            "offer_mode": "lifetime",
            "price_brl_cents": 99700,
        }
    ])

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/availability")
    assert r.status_code == 200
    body = r.json()
    assert body["price_brl_cents"] == 99700
    assert body["offer_mode"] == "lifetime"


@patch("routes.founding.get_supabase")
def test_availability_price_brl_cents_safe_default_when_rpc_v1(mock_get_sb, app_with_founding):
    """v1 RPC still live (no new columns) — safe defaults must kick in."""
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": True,
            "seats_remaining": 40,
            "seats_total": 50,
            "deadline_at": "2026-06-30T23:59:59-03:00",
            "paused": False,
            "reason": "available",
            # offer_mode and price_brl_cents intentionally absent (v1 RPC)
        }
    ])

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/availability")
    assert r.status_code == 200
    body = r.json()
    assert body["price_brl_cents"] == 99700, "safe default when column absent"
    assert body["offer_mode"] == "lifetime", "safe default when column absent"


@patch("routes.founding.get_supabase")
def test_availability_safe_defaults_on_rpc_exception(mock_get_sb, app_with_founding):
    """RPC raises — _check_availability returns safe defaults including new fields."""
    fake_sb = MagicMock()
    fake_sb.rpc.return_value = MagicMock(execute=MagicMock(side_effect=Exception("db flaky")))
    mock_get_sb.return_value = fake_sb

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/availability")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["price_brl_cents"] == 99700
    assert body["offer_mode"] == "lifetime"


@patch("routes.founding.get_supabase")
def test_availability_custom_price_from_rpc(mock_get_sb, app_with_founding):
    """If DB has a different price (e.g. future price change) it flows through."""
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": True,
            "seats_remaining": 10,
            "seats_total": 50,
            "deadline_at": "2026-06-30T23:59:59-03:00",
            "paused": False,
            "reason": "available",
            "offer_mode": "lifetime",
            "price_brl_cents": 149700,  # hypothetical future price
        }
    ])

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/availability")
    assert r.status_code == 200
    body = r.json()
    assert body["price_brl_cents"] == 149700
    assert body["offer_mode"] == "lifetime"


@patch("routes.founding.get_supabase")
def test_availability_offer_mode_subscription_passthrough(mock_get_sb, app_with_founding):
    """If DB is rolled back to subscription mode it flows through too."""
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": True,
            "seats_remaining": 30,
            "seats_total": 50,
            "deadline_at": "2026-06-30T23:59:59-03:00",
            "paused": False,
            "reason": "available",
            "offer_mode": "subscription",
            "price_brl_cents": 49700,
        }
    ])

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/availability")
    assert r.status_code == 200
    body = r.json()
    assert body["offer_mode"] == "subscription"
    assert body["price_brl_cents"] == 49700


@patch("routes.founding.get_supabase")
def test_availability_full_response_shape_with_new_fields(mock_get_sb, app_with_founding):
    """Complete shape contract including the two new fields."""
    mock_get_sb.return_value = _make_supabase_mock([
        {
            "available": True,
            "seats_remaining": 47,
            "seats_total": 50,
            "deadline_at": "2026-06-30T23:59:59-03:00",
            "paused": False,
            "reason": "available",
            "offer_mode": "lifetime",
            "price_brl_cents": 99700,
        }
    ])

    client = TestClient(app_with_founding)
    r = client.get("/v1/founding/availability")
    assert r.status_code == 200
    body = r.json()

    # Existing fields still intact
    assert body["available"] is True
    assert body["seats_total"] == 50
    assert body["seats_remaining"] == 47
    assert body["seats_taken"] == 3
    assert body["paused"] is False
    assert body["reason"] == "available"
    assert "coupon_code" in body
    assert body["discount_pct"] == 50

    # New fields
    assert body["price_brl_cents"] == 99700
    assert body["offer_mode"] == "lifetime"
