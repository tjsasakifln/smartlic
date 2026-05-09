"""TEST-ERR-RECOVERY-2026-001 AC3.1 — Stripe webhook retry idempotency.

Validates the contract Stripe expects: when delivery fails (non-2xx
response), Stripe retries with the same ``event.id``. The handler MUST
detect the duplicate via ``stripe_webhook_events`` and return
``{"status": "already_processed"}`` without re-running the handler
side-effects (subscription update, plan sync, etc.).

Origin: STORY-307 (idempotent INSERT ON CONFLICT) + memory
``feedback_supabase_management_api`` — 2026-04 incident where a Stripe
retry hit a wedge handler and triggered a duplicate plan downgrade.
"""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock, Mock

import pytest
from fastapi import HTTPException


pytestmark = pytest.mark.asyncio


def _make_event(event_id: str = "evt_retry_001",
                event_type: str = "customer.subscription.updated") -> Mock:
    event = Mock()
    event.id = event_id
    event.type = event_type
    data = Mock()
    data.id = "sub_retry_001"
    data.get = lambda key, default=None: {
        "customer": "cus_retry_001",
        "items": {"data": [{"plan": {"interval": "year"}}]},
        "metadata": {"plan_id": "plan_pro"},
    }.get(key, default)
    event.data = Mock()
    event.data.object = data
    return event


def _make_request(body: bytes = b'{"id":"evt_retry_001"}') -> AsyncMock:
    request = AsyncMock()
    request.body = AsyncMock(return_value=body)
    request.headers = {"stripe-signature": "t=0,v1=ok"}
    return request


def _make_supabase_chain(claim_data):
    """Build a chainable Supabase mock returning ``claim_data`` on execute."""
    sb = MagicMock()
    chain = MagicMock()
    chain.upsert.return_value = chain
    chain.select.return_value = chain
    chain.update.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.single.return_value = chain
    chain.order.return_value = chain
    chain.insert.return_value = chain
    chain.delete.return_value = chain
    chain.execute.return_value = Mock(data=claim_data)
    sb.table.return_value = chain
    sb._chain = chain
    return sb


@patch('webhooks.stripe.STRIPE_WEBHOOK_SECRET', 'whsec_retry')
@patch('webhooks.stripe.redis_cache')
@patch('webhooks.stripe.get_supabase')
@patch('webhooks.stripe.stripe.Webhook.construct_event')
async def test_stripe_retry_with_same_event_id_short_circuits(
    mock_construct, mock_get_sb, mock_redis,
):
    """AC3.1.a — Same event.id on retry → ``already_processed`` (no handler).

    First delivery wins the upsert (data returned). The second delivery
    sees the row already (data empty) and the handler returns
    ``already_processed`` BEFORE invoking ``_handle_subscription_updated``.
    """
    from webhooks.stripe import stripe_webhook

    event = _make_event()
    mock_construct.return_value = event

    # 2nd delivery — upsert returns empty (row already exists).
    sb = _make_supabase_chain(claim_data=[])
    # The stuck-check that follows reads back the existing row.
    sb._chain.execute.side_effect = [
        Mock(data=[]),  # upsert returned empty
        Mock(data=[{
            "id": "evt_retry_001",
            "status": "completed",
            "received_at": "2026-05-08T10:00:00+00:00",
        }]),  # stuck-check shows completed
    ]
    mock_get_sb.return_value = sb

    with patch('webhooks.stripe._handle_subscription_updated') as handler:
        result = await stripe_webhook(_make_request())

    assert result == {"status": "already_processed", "event_id": "evt_retry_001"}
    handler.assert_not_awaited()


@patch('webhooks.stripe.STRIPE_WEBHOOK_SECRET', 'whsec_retry')
@patch('webhooks.stripe.redis_cache')
@patch('webhooks.stripe.get_supabase')
@patch('webhooks.stripe.stripe.Webhook.construct_event')
async def test_first_delivery_invokes_handler_then_marks_completed(
    mock_construct, mock_get_sb, mock_redis,
):
    """AC3.1.b — Happy path: first delivery runs the handler exactly once.

    Pairs with the retry test — guards the boundary between "first" and
    "duplicate" so the regression is caught from both sides.
    """
    from webhooks.stripe import stripe_webhook

    event = _make_event()
    mock_construct.return_value = event

    sb = _make_supabase_chain(claim_data=[{"id": "evt_retry_001"}])
    mock_get_sb.return_value = sb

    with patch('webhooks.stripe._handle_subscription_updated', new_callable=AsyncMock) as handler:
        result = await stripe_webhook(_make_request())

    assert result.get("status") == "success"
    assert result.get("event_id") == "evt_retry_001"
    handler.assert_awaited_once()


@patch('webhooks.stripe.STRIPE_WEBHOOK_SECRET', 'whsec_retry')
@patch('webhooks.stripe.redis_cache')
@patch('webhooks.stripe.get_supabase')
@patch('webhooks.stripe.stripe.Webhook.construct_event')
async def test_signature_failure_returns_400(
    mock_construct, mock_get_sb, mock_redis,
):
    """AC3.1.c — Edge: invalid signature → 400 (Stripe will retry).

    The handler must NOT crash with 500 on signature errors — Stripe
    treats 400 as fatal-but-logged. 500 would trigger an exponential
    retry storm against an already-broken delivery.
    """
    import webhooks.stripe as wh

    # Get the actual SignatureVerificationError class used in the
    # production handler — works regardless of whether the stripe
    # module was mocked by an earlier test.
    try:
        SigErr = wh.stripe.error.SignatureVerificationError
    except AttributeError:  # pragma: no cover
        class SigErr(Exception):
            def __init__(self, msg, sig_header=""):
                super().__init__(msg)
                self.sig_header = sig_header
        wh.stripe.error.SignatureVerificationError = SigErr

    mock_construct.side_effect = SigErr("bad", sig_header="hdr")
    from webhooks.stripe import stripe_webhook

    with pytest.raises(HTTPException) as exc:
        await stripe_webhook(_make_request())

    assert exc.value.status_code == 400
