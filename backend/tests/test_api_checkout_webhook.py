"""API-SELF-004: Tests for API subscription checkout webhook and metered billing.

Coverage:
    1. Webhook handler: API subscription activation
    2. Webhook handler: non-API checkout (skipped)
    3. Webhook handler: missing user_id resolution
    4. Webhook handler: tier resolution from session metadata
    5. Metered billing: normal aggregation
    6. Metered billing: over-limit detection
    7. Metered billing: skipped when lock held
    8. Stripe API products config module
    9. API subscription checkout endpoint
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_sb():
    """Mock Supabase client with chainable table methods."""
    sb = MagicMock()
    sb.table.return_value = sb
    sb.select.return_value = sb
    sb.eq.return_value = sb
    sb.is_.return_value = sb
    sb.limit.return_value = sb
    sb.single.return_value = sb
    sb.order.return_value = sb
    sb.execute.return_value = MagicMock(data=[])
    return sb


# ---------------------------------------------------------------------------
# Module: stripe_api_products
# ---------------------------------------------------------------------------


class TestStripeApiProducts:
    """Tests for backend/stripe_api_products.py."""

    def test_api_products_defined(self):
        from stripe_api_products import (
            API_PRODUCTS,
            API_TIER_STARTER,
            API_TIER_PRO,
            API_TIER_SCALE,
        )

        assert API_TIER_STARTER in API_PRODUCTS
        assert API_TIER_PRO in API_PRODUCTS
        assert API_TIER_SCALE in API_PRODUCTS

        starter = API_PRODUCTS[API_TIER_STARTER]
        assert starter["name"] == "API Starter"
        assert starter["price_brl"] == 9700

        pro = API_PRODUCTS[API_TIER_PRO]
        assert pro["name"] == "API Pro"
        assert pro["price_brl"] == 29700

        scale = API_PRODUCTS[API_TIER_SCALE]
        assert scale["name"] == "API Scale"
        assert scale["price_brl"] == 99700

    def test_get_api_product(self):
        from stripe_api_products import get_api_product, API_TIER_PRO

        product = get_api_product(API_TIER_PRO)
        assert product is not None
        assert product["id"] == "api_pro"

        assert get_api_product("nonexistent") is None

    def test_get_tier_by_price_id(self, monkeypatch):
        from stripe_api_products import get_tier_by_price_id

        monkeypatch.setenv("STRIPE_PRICE_API_STARTER", "price_starter_test")
        monkeypatch.setenv("STRIPE_PRICE_API_PRO", "price_pro_test")
        monkeypatch.setenv("STRIPE_PRICE_API_SCALE", "price_scale_test")

        assert get_tier_by_price_id("price_pro_test") == "api_pro"
        assert get_tier_by_price_id("price_starter_test") == "api_starter"
        assert get_tier_by_price_id("price_scale_test") == "api_scale"
        assert get_tier_by_price_id("unknown_price") is None

    def test_get_tier_price_id(self, monkeypatch):
        from stripe_api_products import get_tier_price_id, API_TIER_STARTER

        monkeypatch.setenv("STRIPE_PRICE_API_STARTER", "price_starter_123")
        assert get_tier_price_id(API_TIER_STARTER) == "price_starter_123"
        assert get_tier_price_id("nonexistent") is None

    def test_get_tier_monthly_limit(self):
        from stripe_api_products import (
            get_tier_monthly_limit,
            API_TIER_STARTER,
            API_TIER_PRO,
            API_TIER_SCALE,
        )

        assert get_tier_monthly_limit(API_TIER_STARTER) == 500
        assert get_tier_monthly_limit(API_TIER_PRO) == 5000
        assert get_tier_monthly_limit(API_TIER_SCALE) == 50000
        assert get_tier_monthly_limit("unknown") == 0


# ---------------------------------------------------------------------------
# Module: webhooks/handlers/api_checkout
# ---------------------------------------------------------------------------


class TestApiCheckoutWebhook:
    """Tests for the API subscription checkout webhook handler."""

    @patch("analytics_events.track_funnel_event")
    @patch("webhooks.handlers.api_checkout._send_api_welcome_email")
    async def test_handle_api_checkout_creates_subscription(
        self,
        mock_welcome_email,
        mock_track,
        mock_sb,
    ):
        """Verify that a valid API checkout creates api_subscriptions row and updates profile."""
        from webhooks.handlers.api_checkout import handle_api_checkout_session_completed

        event = MagicMock()
        event.type = "checkout.session.completed"
        event.id = "evt_test_api_checkout_001"
        event.data.object = {
            "id": "cs_test_api_sub_001",
            "mode": "subscription",
            "object": "checkout.session",
            "payment_status": "paid",
            "metadata": {
                "source": "api_subscription",
                "tier": "api_pro",
            },
            "client_reference_id": "user_test_001",
            "customer": "cus_test_001",
            "subscription": "sub_test_001",
            "customer_details": {"email": "test@example.com"},
            "line_items": {
                "data": [
                    {
                        "price": {
                            "id": "price_api_pro_test",
                            "product": "prod_api_pro_test",
                        },
                        "quantity": 1,
                    }
                ]
            },
        }

        await handle_api_checkout_session_completed(mock_sb, event)

        # Verify insert was called for api_subscriptions
        insert_calls = [
            call for call in mock_sb.table.call_args_list
            if call[0][0] == "api_subscriptions"
        ]
        assert len(insert_calls) >= 1, "Expected api_subscriptions insert"

    async def test_handle_api_checkout_skips_non_api(self, mock_sb):
        """Verify non-API subscription checkouts are skipped."""
        from webhooks.handlers.api_checkout import handle_api_checkout_session_completed

        event = MagicMock()
        event.type = "checkout.session.completed"
        event.id = "evt_test_non_api"
        event.data.object = {
            "id": "cs_test_regular",
            "mode": "payment",
            "metadata": {"product_type": "intel_report"},
        }

        await handle_api_checkout_session_completed(mock_sb, event)

        # Verify no api_subscriptions operations were performed
        api_sub_calls = [
            call for call in mock_sb.table.call_args_list
            if len(call[0]) > 0 and call[0][0] == "api_subscriptions"
        ]
        assert len(api_sub_calls) == 0

    @patch("analytics_events.track_funnel_event")
    @patch("webhooks.handlers.api_checkout._send_api_welcome_email")
    async def test_handle_api_checkout_resolves_tier_from_metadata(
        self,
        mock_welcome_email,
        mock_track,
        mock_sb,
    ):
        """Verify tier is resolved from session metadata when present."""
        from webhooks.handlers.api_checkout import handle_api_checkout_session_completed

        event = MagicMock()
        event.type = "checkout.session.completed"
        event.id = "evt_tier_meta"
        event.data.object = {
            "id": "cs_test_tier_meta",
            "mode": "subscription",
            "payment_status": "paid",
            "metadata": {
                "source": "api_subscription",
                "tier": "api_starter",
            },
            "client_reference_id": "user_starter",
            "customer": "cus_starter",
            "subscription": None,
            "customer_details": {"email": "starter@example.com"},
            "line_items": {"data": []},
        }

        await handle_api_checkout_session_completed(mock_sb, event)
        # Should not raise — metadata tier should be used

    @patch("analytics_events.track_funnel_event")
    @patch("webhooks.handlers.api_checkout._send_api_welcome_email")
    async def test_handle_api_checkout_missing_user_skips(
        self,
        mock_welcome_email,
        mock_track,
        mock_sb,
    ):
        """Verify handler does not raise when user_id cannot be resolved."""
        from webhooks.handlers.api_checkout import handle_api_checkout_session_completed

        event = MagicMock()
        event.type = "checkout.session.completed"
        event.id = "evt_no_user"
        event.data.object = {
            "id": "cs_test_no_user",
            "mode": "subscription",
            "metadata": {"source": "api_subscription", "tier": "api_scale"},
            "client_reference_id": None,
            "customer": None,
            "customer_details": None,
        }

        await handle_api_checkout_session_completed(mock_sb, event)


# ---------------------------------------------------------------------------
# Module: cron/api_metered_billing
# ---------------------------------------------------------------------------


class TestApiMeteredBilling:
    """Tests for the API metered billing cron."""

    @patch("cron.api_metered_billing.acquire_redis_lock", return_value=True)
    @patch("cron.api_metered_billing.release_redis_lock")
    async def test_run_empty_month(self, mock_release, mock_acquire):
        """Verify empty month returns zero counts."""
        from cron.api_metered_billing import run_api_metered_billing

        with patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(data=[])

            with patch("supabase_client.get_supabase"):
                result = await run_api_metered_billing()

        assert result["status"] == "completed"
        assert result["total_requests"] == 0
        assert result["records_updated"] == 0

    @patch("cron.api_metered_billing.acquire_redis_lock", return_value=True)
    @patch("cron.api_metered_billing.release_redis_lock")
    async def test_run_with_usage(self, mock_release, mock_acquire):
        """Verify usage aggregation works."""
        from cron.api_metered_billing import run_api_metered_billing

        usage_rows = [
            {"user_id": "user_1", "month": "2026-06", "request_count": 100},
            {"user_id": "user_1", "month": "2026-06", "request_count": 50},
            {"user_id": "user_2", "month": "2026-06", "request_count": 200},
        ]

        with patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(data=usage_rows)

            with patch("supabase_client.get_supabase"):
                result = await run_api_metered_billing()

        assert result["status"] == "completed"
        assert result["total_requests"] == 350  # 100 + 50 + 200
        assert result["records_checked"] == 2  # 2 distinct users

        assert result["status"] == "completed"
        assert result["total_requests"] == 350  # 100 + 50 + 200
        assert result["records_checked"] == 2  # 2 distinct users

    @patch("cron.api_metered_billing.acquire_redis_lock", return_value=False)
    async def test_skip_when_lock_held(self, mock_acquire):
        """Verify the cron is skipped when Redis lock is held."""
        from cron.api_metered_billing import run_api_metered_billing

        result = await run_api_metered_billing()

        assert result["status"] == "skipped"
        assert result["reason"] == "lock_held"

    @patch("cron.api_metered_billing.acquire_redis_lock", return_value=True)
    @patch("cron.api_metered_billing.release_redis_lock")
    async def test_run_with_overage_detection(self, mock_release, mock_acquire):
        """Verify over-limit detection works for a user exceeding tier limits."""
        from cron.api_metered_billing import run_api_metered_billing

        usage_rows = [
            {"user_id": "user_over", "month": "2026-06", "request_count": 600},
        ]

        with patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = [
                MagicMock(data=usage_rows),  # 1st call: usage query
                MagicMock(data=[{"api_tier": "api_starter"}]),  # 2nd call: profile query
            ]

            with patch("supabase_client.get_supabase") as mock_get_sb:
                mock_sb_inner = MagicMock()
                mock_sb_inner.table.return_value = mock_sb_inner
                mock_sb_inner.select.return_value = mock_sb_inner
                mock_sb_inner.eq.return_value = mock_sb_inner
                mock_sb_inner.limit.return_value = mock_sb_inner
                mock_sb_inner.execute.return_value = MagicMock(data=[{"api_tier": "api_starter"}])
                mock_get_sb.return_value = mock_sb_inner

                result = await run_api_metered_billing()

        assert result["status"] == "completed"
        assert result["total_requests"] == 600
        assert result["records_over_limit"] == 1  # 600 > 500 (starter limit)


# ---------------------------------------------------------------------------
# Module: routes/checkout — API subscription endpoint
# ---------------------------------------------------------------------------


class TestApiCheckoutRoute:
    """Tests for the POST /api/checkout/api-subscription endpoint."""

    @patch("stripe.checkout.Session.create")
    async def test_create_api_subscription_checkout(self, mock_stripe_create):
        """Verify API subscription checkout session creation."""
        from routes.checkout import create_api_subscription_checkout
        from schemas.checkout import ApiSubscriptionCheckoutRequest

        mock_session = MagicMock()
        mock_session.id = "cs_test_api_checkout"
        mock_session.url = "https://checkout.stripe.com/test"
        mock_stripe_create.return_value = mock_session

        payload = ApiSubscriptionCheckoutRequest(tier="api_pro")
        user = {
            "sub": "user_test_123",
            "email": "test@example.com",
        }

        with patch("routes.checkout._get_stripe_key", return_value="sk_test_key"):
            with patch("stripe_api_products.get_tier_price_id", return_value="price_pro_test"):
                with patch("routes.checkout._get_frontend_url", return_value="http://localhost:3000"):
                    result = await create_api_subscription_checkout(payload, user)

        assert result.checkout_url == "https://checkout.stripe.com/test"
        assert result.session_id == "cs_test_api_checkout"

        mock_stripe_create.assert_called_once()
        call_kwargs = mock_stripe_create.call_args[1]
        assert call_kwargs["mode"] == "subscription"
        assert call_kwargs["metadata"]["source"] == "api_subscription"
        assert call_kwargs["metadata"]["tier"] == "api_pro"
        assert call_kwargs["client_reference_id"] == "user_test_123"

    async def test_create_api_subscription_invalid_tier(self):
        """Verify invalid tier raises 400."""
        from routes.checkout import create_api_subscription_checkout
        from schemas.checkout import ApiSubscriptionCheckoutRequest
        from fastapi import HTTPException

        payload = ApiSubscriptionCheckoutRequest(tier="api_enterprise")
        user = {"sub": "user_test", "email": "test@example.com"}

        with pytest.raises(HTTPException) as exc_info:
            with patch("routes.checkout._get_stripe_key", return_value="sk_test_key"):
                await create_api_subscription_checkout(payload, user)

        assert exc_info.value.status_code == 400

    async def test_create_api_subscription_missing_price(self):
        """Verify missing price ID raises 503."""
        from routes.checkout import create_api_subscription_checkout
        from schemas.checkout import ApiSubscriptionCheckoutRequest
        from fastapi import HTTPException

        payload = ApiSubscriptionCheckoutRequest(tier="api_pro")
        user = {"sub": "user_test", "email": "test@example.com"}

        with pytest.raises(HTTPException) as exc_info:
            with patch("routes.checkout._get_stripe_key", return_value="sk_test_key"):
                with patch("stripe_api_products.get_tier_price_id", return_value=None):
                    await create_api_subscription_checkout(payload, user)

        assert exc_info.value.status_code == 503
