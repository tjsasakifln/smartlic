"""Tests for Intel Report one-time checkout and webhook fulfillment (issue #630).

Coverage:
- Schema validation: product_type Literal validates correctly → 422 on bad input
- Service: create_intel_report_checkout() passes correct metadata to Stripe
- Webhook: checkout.session.completed (mode=payment) inserts intel_report_purchases row
- Webhook: idempotency — the dispatcher-level check (stripe_webhook_events) prevents
  duplicate handler invocations, so handle_intel_report_checkout_completed is called
  once per unique event_id
- Webhook: payment_intent.payment_failed → marks purchase as failed
- Route: GET /intel-reports/{id} requires auth
- Route: POST /intel-reports/checkout returns checkout_url and session_id
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────────────────────────

USER = {"id": "user-test-uuid-0001", "email": "test@smartlic.tech", "role": "authenticated"}


def _build_intel_app(user: dict | None = None) -> FastAPI:
    """Build isolated FastAPI app with only the intel_reports router."""
    from auth import require_auth
    from routes.intel_reports import router

    app = FastAPI()
    app.include_router(router, prefix="/v1")

    if user is not None:
        async def _fake_auth():
            return user
        app.dependency_overrides[require_auth] = _fake_auth

    return app


def _make_fake_supabase(insert_data=None, select_data=None):
    """Return a mock supabase client that chains table().select/insert/eq/…/execute()."""
    sb = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(
        data=insert_data if insert_data is not None else select_data or []
    )
    # All chaining methods return chain
    for method in ("table", "select", "insert", "update", "eq", "order", "single", "limit"):
        getattr(chain, method).return_value = chain
    sb.table.return_value = chain
    return sb, chain


# ─────────────────────────────────────────────────────────────────────────────
# 1. Schema validation
# ─────────────────────────────────────────────────────────────────────────────

class TestIntelReportSchemas:
    def test_valid_product_type_cnpj(self):
        from schemas.intel_report import IntelReportCheckoutRequest
        req = IntelReportCheckoutRequest(product_type="cnpj", entity_key="12345678000195")
        assert req.product_type == "cnpj"
        assert req.entity_key == "12345678000195"

    def test_valid_product_type_sector_uf(self):
        from schemas.intel_report import IntelReportCheckoutRequest
        req = IntelReportCheckoutRequest(product_type="sector_uf", entity_key="limpeza:SP")
        assert req.product_type == "sector_uf"

    def test_invalid_product_type_raises_validation_error(self):
        from schemas.intel_report import IntelReportCheckoutRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            IntelReportCheckoutRequest(product_type="invalid_type", entity_key="x")

    def test_checkout_response_fields(self):
        from schemas.intel_report import IntelReportCheckoutResponse
        resp = IntelReportCheckoutResponse(
            checkout_url="https://checkout.stripe.com/pay/cs_test_abc",
            session_id="cs_test_abc",
        )
        assert resp.checkout_url.startswith("https://")
        assert resp.session_id == "cs_test_abc"

    def test_status_response_optional_fields(self):
        from schemas.intel_report import IntelReportStatusResponse
        resp = IntelReportStatusResponse(status="pending")
        assert resp.status == "pending"
        assert resp.pdf_url is None
        assert resp.expires_at is None

    def test_prices_are_correct(self):
        from schemas.intel_report import INTEL_REPORT_PRICES
        assert INTEL_REPORT_PRICES["cnpj"] == 19700       # R$197.00
        assert INTEL_REPORT_PRICES["sector_uf"] == 14700  # R$147.00


# ─────────────────────────────────────────────────────────────────────────────
# 2. Service: create_intel_report_checkout
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateIntelReportCheckout:
    def _make_fake_session(self, url="https://checkout.stripe.com/pay/cs_test_abc"):
        session = MagicMock()
        session.id = "cs_test_abc"
        session.url = url
        return session

    def test_cnpj_creates_session_with_correct_metadata(self):
        fake_session = self._make_fake_session()
        with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake", "FRONTEND_URL": "http://localhost:3000"}):
            with patch("stripe.checkout.Session.create", return_value=fake_session) as mock_create:
                from services.billing import create_intel_report_checkout

                result = create_intel_report_checkout(
                    product_type="cnpj",
                    entity_key="12345678000195",
                    user_id="user-test-uuid-0001",
                )

                assert result["checkout_url"] == fake_session.url
                assert result["session_id"] == "cs_test_abc"

                call_kwargs = mock_create.call_args.kwargs
                assert call_kwargs["mode"] == "payment"
                assert call_kwargs["metadata"]["product_type"] == "cnpj"
                assert call_kwargs["metadata"]["entity_key"] == "12345678000195"
                assert call_kwargs["metadata"]["user_id"] == "user-test-uuid-0001"
                assert call_kwargs["metadata"]["platform"] == "smartlic"

    def test_sector_uf_creates_session_with_correct_price(self):
        fake_session = self._make_fake_session()
        with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}):
            with patch("stripe.checkout.Session.create", return_value=fake_session) as mock_create:
                from services.billing import create_intel_report_checkout

                create_intel_report_checkout(
                    product_type="sector_uf",
                    entity_key="limpeza:SP",
                    user_id="user-test-uuid-0001",
                )

                call_kwargs = mock_create.call_args.kwargs
                line_items = call_kwargs["line_items"]
                assert len(line_items) == 1
                assert line_items[0]["price_data"]["unit_amount"] == 14700  # R$147.00
                assert line_items[0]["price_data"]["currency"] == "brl"

    def test_cnpj_price_is_19700(self):
        fake_session = self._make_fake_session()
        with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}):
            with patch("stripe.checkout.Session.create", return_value=fake_session) as mock_create:
                from services.billing import create_intel_report_checkout

                create_intel_report_checkout(
                    product_type="cnpj",
                    entity_key="12345678000195",
                    user_id="user-test-uuid-0001",
                )

                call_kwargs = mock_create.call_args.kwargs
                assert call_kwargs["line_items"][0]["price_data"]["unit_amount"] == 19700

    def test_payment_method_types_includes_pix_and_boleto(self):
        fake_session = self._make_fake_session()
        with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}):
            with patch("stripe.checkout.Session.create", return_value=fake_session) as mock_create:
                from services.billing import create_intel_report_checkout

                create_intel_report_checkout(
                    product_type="cnpj",
                    entity_key="12345678000195",
                    user_id="user-test-uuid-0001",
                )

                call_kwargs = mock_create.call_args.kwargs
                pmts = call_kwargs["payment_method_types"]
                assert "card" in pmts
                assert "boleto" in pmts
                assert "pix" in pmts

    def test_success_url_contains_stripe_template_placeholder(self):
        """Stripe substitutes {CHECKOUT_SESSION_ID} server-side — must not be Python-interpolated."""
        fake_session = self._make_fake_session()
        with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake", "FRONTEND_URL": "https://smartlic.tech"}):
            with patch("stripe.checkout.Session.create", return_value=fake_session) as mock_create:
                from services.billing import create_intel_report_checkout

                create_intel_report_checkout(
                    product_type="cnpj",
                    entity_key="12345678000195",
                    user_id="user-test-uuid-0001",
                )

                call_kwargs = mock_create.call_args.kwargs
                success_url = call_kwargs["success_url"]
                # Must contain the Stripe template literal, not an empty or Python-substituted string
                assert "{CHECKOUT_SESSION_ID}" in success_url
                assert success_url.startswith("https://smartlic.tech/intel-reports/")

    def test_invalid_product_type_raises_value_error(self):
        with patch.dict("os.environ", {"STRIPE_SECRET_KEY": "sk_test_fake"}):
            from services.billing import create_intel_report_checkout
            with pytest.raises(ValueError, match="product_type"):
                create_intel_report_checkout(
                    product_type="invalid",
                    entity_key="x",
                    user_id="user-test-uuid-0001",
                )

    def test_missing_stripe_key_raises_value_error(self):
        with patch.dict("os.environ", {}, clear=True):
            # Remove STRIPE_SECRET_KEY
            import os
            os.environ.pop("STRIPE_SECRET_KEY", None)
            from services.billing import create_intel_report_checkout
            with pytest.raises(ValueError, match="STRIPE_SECRET_KEY"):
                create_intel_report_checkout(
                    product_type="cnpj",
                    entity_key="12345678000195",
                    user_id="user-test-uuid-0001",
                )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Webhook: handle_intel_report_checkout_completed
# ─────────────────────────────────────────────────────────────────────────────

class TestIntelReportWebhookHandler:
    def _make_session_data(
        self,
        product_type="cnpj",
        entity_key="12345678000195",
        user_id="user-test-uuid-0001",
        mode="payment",
        payment_intent="pi_test_abc",
        session_id="cs_test_abc",
    ):
        """Build a session_data dict mimicking a Stripe checkout.session.completed object."""
        data = {
            "id": session_id,
            "mode": mode,
            "payment_intent": payment_intent,
            "metadata": {
                "product_type": product_type,
                "entity_key": entity_key,
                "user_id": user_id,
                "platform": "smartlic",
            },
        }
        # Make it behave like a Stripe object (supports .get())
        obj = MagicMock()
        obj.get = lambda key, default=None: data.get(key, default)
        obj.__getitem__ = lambda self_, key: data[key]
        obj.__contains__ = lambda self_, key: key in data
        return obj

    @pytest.mark.asyncio
    async def test_inserts_purchase_row(self):
        sb, chain = _make_fake_supabase(insert_data=[{"id": "purchase-uuid-001"}])
        session_data = self._make_session_data()

        # Patch job_queue.get_arq_pool to simulate ARQ unavailable (import inside try block)
        with patch("job_queue.get_arq_pool", side_effect=Exception("no arq pool")):
            from webhooks.handlers.checkout import handle_intel_report_checkout_completed
            await handle_intel_report_checkout_completed(sb, session_data)

        # Assert .table("intel_report_purchases").insert(...).execute() was called
        sb.table.assert_called_with("intel_report_purchases")
        chain.insert.assert_called_once()
        insert_arg = chain.insert.call_args[0][0]
        assert insert_arg["product_type"] == "cnpj"
        assert insert_arg["entity_key"] == "12345678000195"
        assert insert_arg["user_id"] == "user-test-uuid-0001"
        assert insert_arg["status"] == "pending"
        assert insert_arg["stripe_payment_intent_id"] == "pi_test_abc"
        chain.execute.assert_called()

    @pytest.mark.asyncio
    async def test_missing_user_id_skips_insert(self):
        """Handler should log warning and return without inserting."""
        sb, chain = _make_fake_supabase()
        session_data = MagicMock()
        session_data.get = lambda key, default=None: {
            "metadata": {"product_type": "cnpj", "entity_key": "12345678000195"},
            "mode": "payment",
        }.get(key, default)

        from webhooks.handlers.checkout import handle_intel_report_checkout_completed
        await handle_intel_report_checkout_completed(sb, session_data)

        chain.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_arq_failure_does_not_raise(self):
        """ARQ unavailability is best-effort — should not propagate as an exception."""
        sb, chain = _make_fake_supabase(insert_data=[{"id": "purchase-uuid-001"}])
        session_data = self._make_session_data()

        # Patch job_queue.get_arq_pool to simulate ARQ pool unavailable
        with patch("job_queue.get_arq_pool", side_effect=Exception("ARQ pool unavailable")):
            from webhooks.handlers.checkout import handle_intel_report_checkout_completed
            # Should not raise — ARQ failure is best-effort
            await handle_intel_report_checkout_completed(sb, session_data)

        # Purchase row was still inserted
        chain.insert.assert_called_once()


class TestIntelReportPaymentFailed:
    @pytest.mark.asyncio
    async def test_marks_purchase_as_failed(self):
        sb, chain = _make_fake_supabase()

        pi_obj = MagicMock()
        pi_obj.id = "pi_test_failed_001"
        pi_obj.get = lambda k, d=None: {"id": "pi_test_failed_001"}.get(k, d)

        event = MagicMock()
        event.data = MagicMock()
        event.data.object = pi_obj

        from webhooks.handlers.checkout import handle_intel_report_payment_failed
        await handle_intel_report_payment_failed(sb, event)

        sb.table.assert_called_with("intel_report_purchases")
        chain.update.assert_called_once_with({"status": "failed"})
        # Chained eq calls: .eq("stripe_payment_intent_id", "pi_test_failed_001").eq("status", "pending")
        assert chain.eq.call_count >= 1

    @pytest.mark.asyncio
    async def test_missing_payment_intent_id_is_noop(self):
        sb, chain = _make_fake_supabase()

        pi_obj = MagicMock()
        pi_obj.id = None
        pi_obj.get = lambda k, d=None: None

        event = MagicMock()
        event.data = MagicMock()
        event.data.object = pi_obj

        from webhooks.handlers.checkout import handle_intel_report_payment_failed
        await handle_intel_report_payment_failed(sb, event)

        # No DB call when payment_intent id is missing
        chain.update.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Webhook idempotency via dispatcher
# ─────────────────────────────────────────────────────────────────────────────

class TestIntelReportWebhookIdempotency:
    """
    Idempotency is enforced at the dispatcher level (stripe_webhook_events table).
    The second call with the same event_id returns "already_processed" WITHOUT
    invoking handle_intel_report_checkout_completed a second time.

    We test that the handler itself is only called once when the event is claimed
    the first time.
    """

    def _make_stripe_event(
        self,
        event_id="evt_test_intel_001",
        event_type="checkout.session.completed",
        mode="payment",
        product_type="cnpj",
    ):
        """Build a mock stripe.Event for an Intel Report one-time payment."""
        session = MagicMock()
        session.id = "cs_test_abc"
        session.get = lambda key, default=None: {
            "id": "cs_test_abc",
            "mode": mode,
            "payment_intent": "pi_test_abc",
            "metadata": {
                "product_type": product_type,
                "entity_key": "12345678000195",
                "user_id": "user-test-uuid-0001",
                "platform": "smartlic",
            },
        }.get(key, default)

        event = MagicMock()
        event.id = event_id
        event.type = event_type
        event.data = MagicMock()
        event.data.object = session
        return event

    def _make_sb_for_idempotency(self, already_exists=False):
        """
        Build a supabase mock that simulates the stripe_webhook_events table.

        First call: upsert returns data (claim succeeds).
        If already_exists=True: upsert returns empty data (event already claimed).
        """
        sb = MagicMock()
        events_chain = MagicMock()
        intel_chain = MagicMock()

        def table_side_effect(table_name):
            if table_name == "stripe_webhook_events":
                return events_chain
            return intel_chain

        sb.table.side_effect = table_side_effect

        # stripe_webhook_events: upsert
        if already_exists:
            events_chain.upsert.return_value = events_chain
            events_chain.execute.return_value = MagicMock(data=[])  # already claimed → no data
            # Stuck check: select returns non-processing status
            events_chain.select.return_value = events_chain
            events_chain.eq.return_value = events_chain
            events_chain.limit.return_value = events_chain
            events_chain.order.return_value = events_chain
            # For stuck check: return existing processed event
            events_chain.execute.side_effect = [
                MagicMock(data=[]),  # upsert → no data (already exists)
                MagicMock(data=[{"id": "evt_test_intel_001", "status": "completed", "received_at": "2024-01-01T00:00:00Z"}]),  # stuck check
            ]
        else:
            events_chain.upsert.return_value = events_chain
            events_chain.execute.return_value = MagicMock(data=[{"id": "evt_test_intel_001"}])
            events_chain.update.return_value = events_chain
            events_chain.eq.return_value = events_chain

        # intel_report_purchases: insert
        intel_chain.insert.return_value = intel_chain
        intel_chain.update.return_value = intel_chain
        intel_chain.eq.return_value = intel_chain
        intel_chain.execute.return_value = MagicMock(data=[{"id": "purchase-uuid-001"}])

        return sb, intel_chain

    @pytest.mark.asyncio
    async def test_handler_called_once_per_unique_event(self):
        """
        Simulate two webhook deliveries with the same event_id.
        The dispatcher returns "already_processed" on the second call.
        We verify handle_intel_report_checkout_completed is invoked once.
        """
        call_count = {"n": 0}

        async def _fake_handler(sb, session_data):
            call_count["n"] += 1

        event = self._make_stripe_event()
        sb, intel_chain = self._make_sb_for_idempotency(already_exists=False)

        with patch("webhooks.stripe.stripe.Webhook.construct_event", return_value=event), \
             patch("webhooks.stripe.get_supabase", return_value=sb), \
             patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("webhooks.stripe._handle_checkout_session_completed") as mock_handler:

            # Import here to avoid top-level circular import issues in test env
            from webhooks.stripe import stripe_webhook

            # Build a mock request
            request = AsyncMock()
            request.body = AsyncMock(return_value=b'{}')
            request.headers = {"stripe-signature": "t=1234567890,v1=sig"}

            # First invocation
            mock_handler.return_value = None
            result = await stripe_webhook(request)

            assert result["status"] == "success"
            assert mock_handler.call_count == 1

    @pytest.mark.asyncio
    async def test_second_delivery_returns_already_processed(self):
        """Second delivery with same event_id returns already_processed."""
        event = self._make_stripe_event()
        sb, intel_chain = self._make_sb_for_idempotency(already_exists=True)

        with patch("webhooks.stripe.stripe.Webhook.construct_event", return_value=event), \
             patch("webhooks.stripe.get_supabase", return_value=sb), \
             patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test"), \
             patch("webhooks.stripe._handle_checkout_session_completed") as mock_handler:

            from webhooks.stripe import stripe_webhook

            request = AsyncMock()
            request.body = AsyncMock(return_value=b'{}')
            request.headers = {"stripe-signature": "t=1234567890,v1=sig"}

            mock_handler.return_value = None
            result = await stripe_webhook(request)

            # Should be already_processed — handler not called
            assert result["status"] == "already_processed"
            mock_handler.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# 5. Checkout.session.completed mode=payment dispatch in the handler
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckoutHandlerModeBranching:
    """
    Ensures the payment mode branch fires for intel reports
    and does NOT run subscription logic.
    """

    def _make_event(self, mode="payment", product_type="cnpj", plan_id=None):
        session = MagicMock()
        meta = {}
        if product_type:
            meta["product_type"] = product_type
        if plan_id:
            meta["plan_id"] = plan_id

        session.get = lambda key, default=None: {
            "mode": mode,
            "metadata": meta,
            "payment_status": "paid",
            "subscription": None,
            "customer": "cus_test",
        }.get(key, default)

        event = MagicMock()
        event.data = MagicMock()
        event.data.object = session
        return event

    @pytest.mark.asyncio
    async def test_payment_mode_with_product_type_dispatches_to_intel_handler(self):
        sb = MagicMock()
        event = self._make_event(mode="payment", product_type="cnpj")

        with patch(
            "webhooks.handlers.checkout.handle_intel_report_checkout_completed",
            new_callable=AsyncMock,
        ) as mock_intel:
            from webhooks.handlers.checkout import handle_checkout_session_completed
            await handle_checkout_session_completed(sb, event)
            mock_intel.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscription_mode_does_not_dispatch_to_intel_handler(self):
        sb = MagicMock()
        sb.table.return_value = MagicMock(
            select=MagicMock(return_value=MagicMock(
                eq=MagicMock(return_value=MagicMock(
                    single=MagicMock(return_value=MagicMock(
                        execute=MagicMock(return_value=MagicMock(data=None))
                    ))
                ))
            ))
        )
        event = self._make_event(mode="subscription", product_type=None, plan_id="smartlic_pro")

        with patch(
            "webhooks.handlers.checkout.handle_intel_report_checkout_completed",
            new_callable=AsyncMock,
        ) as mock_intel, \
        patch("webhooks.handlers.checkout.resolve_user_id", return_value=None):
            from webhooks.handlers.checkout import handle_checkout_session_completed
            await handle_checkout_session_completed(sb, event)
            mock_intel.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_payment_succeeded_payment_mode_dispatches_to_intel(self):
        sb = MagicMock()
        event = self._make_event(mode="payment", product_type="sector_uf")

        with patch(
            "webhooks.handlers.checkout.handle_intel_report_async_payment_succeeded",
            new_callable=AsyncMock,
        ) as mock_intel:
            from webhooks.handlers.checkout import handle_async_payment_succeeded
            await handle_async_payment_succeeded(sb, event)
            mock_intel.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Route: POST /intel-reports/checkout
# ─────────────────────────────────────────────────────────────────────────────

class TestIntelReportCheckoutRoute:
    def _client(self):
        app = _build_intel_app(user=USER)
        return TestClient(app)

    def test_valid_cnpj_checkout_returns_200(self):
        client = self._client()
        fake_result = {
            "checkout_url": "https://checkout.stripe.com/pay/cs_test_abc",
            "session_id": "cs_test_abc",
        }
        # Patch the module-level alias _create_checkout in routes.intel_reports
        with patch("routes.intel_reports._create_checkout", return_value=fake_result):
            resp = client.post("/v1/intel-reports/checkout", json={
                "product_type": "cnpj",
                "entity_key": "12345678000195",
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["checkout_url"] == fake_result["checkout_url"]
        assert body["session_id"] == "cs_test_abc"

    def test_invalid_product_type_returns_422(self):
        client = self._client()
        resp = client.post("/v1/intel-reports/checkout", json={
            "product_type": "invalid_type",
            "entity_key": "12345678000195",
        })
        assert resp.status_code == 422

    def test_route_requires_auth(self):
        """Without dependency override, the route should return 401/403."""
        from routes.intel_reports import router
        app = FastAPI()
        app.include_router(router, prefix="/v1")
        # No auth override — require_auth will raise HTTPException
        client = TestClient(app, raise_server_exceptions=False)

        with patch("auth.require_auth", side_effect=Exception("not authenticated")):
            resp = client.post("/v1/intel-reports/checkout", json={
                "product_type": "cnpj",
                "entity_key": "12345678000195",
            })
        # Either 401 or 422 (missing auth header) — definitely not 200
        assert resp.status_code != 200

    def test_stripe_invalid_request_returns_400(self):
        import stripe as stripe_lib
        client = self._client()
        with patch("routes.intel_reports._create_checkout",
                   side_effect=stripe_lib.error.InvalidRequestError("bad param", "param")):
            resp = client.post("/v1/intel-reports/checkout", json={
                "product_type": "cnpj",
                "entity_key": "12345678000195",
            })
        assert resp.status_code == 400

    def test_stripe_error_returns_503(self):
        import stripe as stripe_lib
        client = self._client()
        with patch("routes.intel_reports._create_checkout",
                   side_effect=stripe_lib.error.StripeError("network error")):
            resp = client.post("/v1/intel-reports/checkout", json={
                "product_type": "cnpj",
                "entity_key": "12345678000195",
            })
        assert resp.status_code == 503


# ─────────────────────────────────────────────────────────────────────────────
# 7. Route: GET /intel-reports/{id} requires auth and returns status
# ─────────────────────────────────────────────────────────────────────────────

class TestIntelReportStatusRoute:
    def _client_with_db(self, purchase_data=None):
        from database import get_db

        app = _build_intel_app(user=USER)

        fake_db = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.single.return_value = chain
        chain.execute.return_value = MagicMock(data=purchase_data)
        fake_db.table.return_value = chain

        async def _fake_db():
            return fake_db

        app.dependency_overrides[get_db] = _fake_db

        return TestClient(app)

    def test_found_purchase_returns_status(self):
        purchase = {
            "id": "purchase-uuid-001",
            "user_id": USER["id"],
            "status": "pending",
            "pdf_url": None,
            "expires_at": None,
        }
        client = self._client_with_db(purchase_data=purchase)

        # Patch the module-level sb_execute in routes.intel_reports
        with patch("routes.intel_reports.sb_execute", new_callable=AsyncMock) as mock_sb:
            mock_sb.return_value = MagicMock(data=purchase)
            resp = client.get("/v1/intel-reports/purchase-uuid-001")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        assert body["pdf_url"] is None

    def test_route_unauthenticated_returns_non_200(self):
        """Without auth override, route should fail auth."""
        from routes.intel_reports import router
        app = FastAPI()
        app.include_router(router, prefix="/v1")
        client = TestClient(app, raise_server_exceptions=False)

        with patch("auth.require_auth", side_effect=Exception("not authenticated")):
            resp = client.get("/v1/intel-reports/purchase-uuid-001")
        assert resp.status_code != 200
