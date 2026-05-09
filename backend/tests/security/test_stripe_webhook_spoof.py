"""SEC-TEST-2026-001 — AC1: Stripe webhook signature spoofing tests.

OWASP A02:2021 Cryptographic Failures + A08:2021 Software & Data Integrity.

Drives webhooks.stripe.stripe_webhook directly (no TestClient required) and
asserts:

- Missing stripe-signature header → 400.
- Invalid/forged signature → 400 (stripe.error.SignatureVerificationError).
- Valid construct_event but malformed envelope (missing id/type) → 400.
- Replay protection: idempotency dedup at the DB layer (we cover the
  validation envelope; full replay is gated by stripe.Webhook.construct_event's
  built-in 5-minute timestamp tolerance).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
import stripe
from fastapi import HTTPException


def _request(body: bytes = b'{"id":"evt_test_1","type":"customer.subscription.updated"}',
             sig: str | None = "t=1234567890,v1=fake_signature") -> Mock:
    request = AsyncMock()
    request.body = AsyncMock(return_value=body)
    request.headers = {"stripe-signature": sig} if sig is not None else {}
    return request


# ──────────────────────────────────────────────────────────────────────
# Signature absent / malformed
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature_header():
    """Webhook with NO stripe-signature header MUST return 400."""
    from webhooks.stripe import stripe_webhook

    req = _request(sig=None)
    with pytest.raises(HTTPException) as exc:
        await stripe_webhook(req)
    assert exc.value.status_code == 400
    assert "Assinatura" in exc.value.detail


@pytest.mark.asyncio
async def test_webhook_rejects_empty_signature_header():
    """Empty signature value MUST be rejected — we test BOTH the header-missing
    path (handled above) AND the construct_event-rejection path here.
    """
    from webhooks.stripe import stripe_webhook

    req = _request(sig="")  # empty header value
    # Empty string is falsy → triggers missing-header branch (400)
    with pytest.raises(HTTPException) as exc:
        await stripe_webhook(req)
    assert exc.value.status_code == 400


# ──────────────────────────────────────────────────────────────────────
# Forged signature — construct_event raises SignatureVerificationError
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_rejects_forged_signature():
    """Attacker-crafted signature MUST be rejected with 400."""
    from webhooks.stripe import stripe_webhook

    req = _request(sig="t=1234567890,v1=AAAAAAAAAAAAAAAAAAAAAAA_attacker_forged")

    with patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test_secret"), \
         patch("webhooks.stripe.stripe.Webhook.construct_event") as mock_ctor:
        mock_ctor.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )
        with pytest.raises(HTTPException) as exc:
            await stripe_webhook(req)
    assert exc.value.status_code == 400
    assert "Assinatura" in exc.value.detail


@pytest.mark.asyncio
async def test_webhook_rejects_tampered_payload():
    """Even with a sig-shaped header, payload-tamper triggers ValueError → 400."""
    from webhooks.stripe import stripe_webhook

    req = _request(body=b"not_json{}{")

    with patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test_secret"), \
         patch("webhooks.stripe.stripe.Webhook.construct_event") as mock_ctor:
        mock_ctor.side_effect = ValueError("Invalid payload")
        with pytest.raises(HTTPException) as exc:
            await stripe_webhook(req)
    assert exc.value.status_code == 400


# ──────────────────────────────────────────────────────────────────────
# Replay attack — old timestamp would fail Stripe's 5-min tolerance
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_replay_old_timestamp_rejected():
    """Stripe's construct_event rejects events with timestamp >5min stale.
    We assert that path: when construct_event raises SignatureVerificationError
    citing timestamp, we return 400.
    """
    from webhooks.stripe import stripe_webhook

    # Old timestamp (1970) — Stripe SDK treats as "Timestamp outside the tolerance zone"
    req = _request(sig="t=1,v1=stale_replay")

    with patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test_secret"), \
         patch("webhooks.stripe.stripe.Webhook.construct_event") as mock_ctor:
        mock_ctor.side_effect = stripe.error.SignatureVerificationError(
            "Timestamp outside the tolerance zone", "t=1,v1=stale_replay"
        )
        with pytest.raises(HTTPException) as exc:
            await stripe_webhook(req)
    assert exc.value.status_code == 400


# ──────────────────────────────────────────────────────────────────────
# Envelope validation — sig OK but missing id/type
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_rejects_event_missing_id():
    """Even with valid sig, event without `id` MUST return 400."""
    from webhooks.stripe import stripe_webhook

    req = _request()

    bad_event = Mock()
    bad_event.id = None  # missing
    bad_event.type = "customer.subscription.updated"
    bad_event.data = Mock()
    bad_event.data.object = Mock()

    with patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test_secret"), \
         patch("webhooks.stripe.stripe.Webhook.construct_event", return_value=bad_event):
        with pytest.raises(HTTPException) as exc:
            await stripe_webhook(req)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_webhook_rejects_event_missing_type():
    """Event without `type` MUST return 400."""
    from webhooks.stripe import stripe_webhook

    req = _request()

    bad_event = Mock()
    bad_event.id = "evt_test_1"
    bad_event.type = None
    bad_event.data = Mock()
    bad_event.data.object = Mock()

    with patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", "whsec_test_secret"), \
         patch("webhooks.stripe.stripe.Webhook.construct_event", return_value=bad_event):
        with pytest.raises(HTTPException) as exc:
            await stripe_webhook(req)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_webhook_secret_required_for_construct_event():
    """If STRIPE_WEBHOOK_SECRET is None, construct_event will fail — verify
    we don't accidentally short-circuit and accept unsigned events.
    """
    from webhooks.stripe import stripe_webhook

    req = _request()

    with patch("webhooks.stripe.STRIPE_WEBHOOK_SECRET", None), \
         patch("webhooks.stripe.stripe.Webhook.construct_event") as mock_ctor:
        mock_ctor.side_effect = stripe.error.SignatureVerificationError(
            "No secret configured", ""
        )
        with pytest.raises(HTTPException) as exc:
            await stripe_webhook(req)
    assert exc.value.status_code == 400
