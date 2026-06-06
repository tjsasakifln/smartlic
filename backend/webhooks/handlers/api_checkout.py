"""API-SELF-004: Webhook handler for API subscription checkout.

Events:
    - checkout.session.completed (mode=subscription + metadata.source=api_subscription)

Handles Stripe Checkout Session completion for API tier subscriptions.
When a user checks out for API Starter, Pro, or Scale:
    1. Resolves the API tier from the Stripe Price ID
    2. Creates/updates api_subscriptions row
    3. Updates profiles.api_tier
    4. Sends welcome email with API key creation instructions
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import stripe as stripe_lib

from log_sanitizer import get_sanitized_logger
from pipeline.budget import _run_with_budget
from webhooks.handlers._shared import resolve_user_id, invalidate_user_caches

# RES-BE: per-query budget (fits within the 30s overall webhook timeout)
_WEBHOOK_QUERY_BUDGET_S = 5.0

logger = get_sanitized_logger(__name__)


async def handle_api_checkout_session_completed(
    sb,
    event: stripe_lib.Event,
) -> None:
    """Handle checkout.session.completed for API subscription purchases.

    Triggered when a user completes a Stripe Checkout Session for an API
    tier subscription (mode=subscription + metadata.source=api_subscription).

    Idempotency is guaranteed at the dispatcher level (stripe_webhook_events),
    so this handler does NOT implement its own dedup.

    Workflow:
        1. Verify this is an API subscription checkout via metadata.source
        2. Resolve user_id from client_reference_id or email
        3. Determine the API tier from the line item's Stripe Price ID
        4. Create or update the api_subscriptions row
        5. Update profiles.api_tier
        6. Invalidate user caches
        7. Send welcome email (fire-and-forget)

    Idempotent: safe to replay for the same event_id.
    """
    session_data = event.data.object
    metadata = session_data.get("metadata") or {}
    source = metadata.get("source")

    # Only handle API subscription checkouts
    if source != "api_subscription":
        return

    mode = session_data.get("mode")
    if mode != "subscription":
        logger.warning(
            "API checkout with unexpected mode=%s — expected 'subscription'",
            mode,
        )
        return

    logger.info(
        "API subscription checkout completed: session_id=%s",
        session_data.get("id"),
    )

    # -----------------------------------------------------------------------
    # Step 1: Resolve user
    # -----------------------------------------------------------------------
    user_id = resolve_user_id(sb, session_data)
    if not user_id:
        logger.warning(
            "API checkout: could not resolve user_id from session "
            "client_reference_id=%s, customer_details=%s",
            session_data.get("client_reference_id"),
            session_data.get("customer_details"),
        )
        return

    # -----------------------------------------------------------------------
    # Step 2: Determine API tier from line items
    # -----------------------------------------------------------------------
    stripe_subscription_id = session_data.get("subscription")
    stripe_customer_id = session_data.get("customer")

    # Resolve tier from the first line item's price metadata
    tier = await _resolve_tier_from_session(session_data)
    if not tier:
        logger.warning(
            "API checkout: could not determine tier from session line items "
            "for user_id=%s",
            user_id[:8],
        )
        return

    logger.info(
        "API checkout resolved: user_id=%s, tier=%s, "
        "stripe_subscription_id=%s",
        user_id[:8],
        tier,
        stripe_subscription_id,
    )

    # -----------------------------------------------------------------------
    # Step 3: Create / update api_subscriptions row
    # -----------------------------------------------------------------------
    now_iso = datetime.now(timezone.utc).isoformat()

    # Parse current_period from subscription if available
    current_period_start = None
    current_period_end = None
    if stripe_subscription_id:
        try:
            sub_data = await _fetch_subscription_period(stripe_subscription_id)
            if sub_data:
                current_period_start, current_period_end = sub_data
        except Exception as exc:
            logger.warning(
                "API checkout: failed to fetch subscription period "
                "(non-fatal): %s",
                exc,
            )

    # Deactivate any existing active API subscription for this user
    await _run_with_budget(
        asyncio.to_thread(
            lambda: sb.table("api_subscriptions")
            .update({"status": "canceled", "updated_at": now_iso})
            .eq("user_id", user_id)
            .eq("status", "active")
            .execute()
        ),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.api_checkout.deactivate_existing",
    )

    # Insert new subscription
    sub_row = {
        "user_id": user_id,
        "tier": tier,
        "status": "active",
        "stripe_subscription_id": stripe_subscription_id,
        "stripe_customer_id": stripe_customer_id,
        "current_period_start": current_period_start,
        "current_period_end": current_period_end,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await _run_with_budget(
        asyncio.to_thread(
            lambda: sb.table("api_subscriptions").insert(sub_row).execute()
        ),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.api_checkout.insert_subscription",
    )

    # -----------------------------------------------------------------------
    # Step 4: Update profiles.api_tier
    # -----------------------------------------------------------------------
    await _run_with_budget(
        asyncio.to_thread(
            lambda: sb.table("profiles")
            .update({"api_tier": tier})
            .eq("id", user_id)
            .execute()
        ),
        budget=_WEBHOOK_QUERY_BUDGET_S,
        phase="route",
        source="webhook.api_checkout.sync_profile",
    )

    await invalidate_user_caches(user_id, "API subscription activation complete")

    # -----------------------------------------------------------------------
    # Step 5: Send welcome email (fire-and-forget)
    # -----------------------------------------------------------------------
    _send_api_welcome_email(sb, user_id, tier)

    # Track activation event
    try:
        from analytics_events import track_funnel_event

        track_funnel_event("api_subscription_activated", user_id, {
            "tier": tier,
            "payment_method": "card",
        })
    except Exception:
        pass

    logger.info(
        "API subscription activated: user_id=%s, tier=%s",
        user_id[:8],
        tier,
    )


async def _resolve_tier_from_session(session_data: dict) -> str | None:
    """Determine the API tier from the Checkout Session's line items.

    Stripe Checkout Sessions for subscriptions have line_items with a
    ``price`` object that contains the ``id`` (price_xxx). We compare
    this price ID against the configured env vars for each API tier.

    Falls back to session metadata.tier if line items are unavailable
    (e.g. in test scenarios).
    """
    # First try session metadata (set during checkout creation)
    metadata = session_data.get("metadata") or {}
    metadata_tier = metadata.get("tier")
    if metadata_tier in ("api_starter", "api_pro", "api_scale"):
        return metadata_tier

    # Expand line items to find the price
    try:
        line_items_data = session_data.get("line_items", {}).get("data", [])
        if not line_items_data:
            # Fall back to Stripe API expand if not included in the webhook payload
            session_id = session_data.get("id")
            if session_id:
                expanded = stripe_lib.checkout.Session.retrieve(
                    session_id,
                    expand=["line_items"],
                )
                line_items_data = (
                    getattr(expanded, "line_items", None)
                    and getattr(expanded.line_items, "data", [])
                ) or []

        for item in line_items_data:
            price = item.get("price") or {}
            price_id = price.get("id") or (getattr(price, "id", None) if not isinstance(price, dict) else None)
            if price_id:
                from stripe_api_products import get_tier_by_price_id

                tier = get_tier_by_price_id(str(price_id))
                if tier:
                    return tier
    except Exception as exc:
        logger.warning(
            "API checkout: failed to resolve tier from line items: %s",
            exc,
        )

    return None


async def _fetch_subscription_period(
    stripe_subscription_id: str,
) -> tuple[str, str] | None:
    """Fetch the current_period_start and current_period_end from Stripe."""
    try:
        import stripe as stripe_lib

        subscription = stripe_lib.Subscription.retrieve(stripe_subscription_id)
        if hasattr(subscription, "current_period_start") and hasattr(subscription, "current_period_end"):
            from datetime import datetime, timezone

            start = datetime.fromtimestamp(
                subscription.current_period_start, tz=timezone.utc
            ).isoformat()
            end = datetime.fromtimestamp(
                subscription.current_period_end, tz=timezone.utc
            ).isoformat()
            return start, end
    except Exception:
        raise

    return None


# ============================================================================
# Helpers (fire-and-forget)
# ============================================================================


def _send_api_welcome_email(sb, user_id: str, tier: str) -> None:
    """Send welcome email after API subscription activation. Never raises."""
    try:
        from email_service import send_email_async

        tier_names = {
            "api_starter": "API Starter",
            "api_pro": "API Pro",
            "api_scale": "API Scale",
        }
        tier_name = tier_names.get(tier, tier)

        profile = (
            sb.table("profiles")
            .select("email, full_name")
            .eq("id", user_id)
            .single()
            .execute()
        )
        if not profile.data or not profile.data.get("email"):
            return

        email = profile.data["email"]
        name = profile.data.get("full_name") or email.split("@")[0]

        html = _render_api_welcome_email(name=name, tier_name=tier_name)
        send_email_async(
            to=email,
            subject=f"Sua assinatura {tier_name} esta ativa!",
            html=html,
            tags=[{"name": "category", "value": "api_welcome"}],
        )
        logger.info("API welcome email queued for user_id=%s", user_id[:8])
    except Exception as e:
        logger.warning("Failed to send API welcome email: %s", e)


def _render_api_welcome_email(name: str, tier_name: str) -> str:
    """Render the API welcome email HTML. Pure function (no template engine)."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
<h2>Bem-vindo ao {tier_name}!</h2>
<p>Ola <strong>{name}</strong>,</p>
<p>Sua assinatura <strong>{tier_name}</strong> do SmartLic API esta ativa.</p>
<p>Para comecar a usar sua chave de API:</p>
<ol>
  <li>Acesse <a href="https://smartlic.tech/conta">smartlic.tech/conta</a></li>
  <li>Va em "Chaves de API" e crie uma nova chave</li>
  <li>Use a chave no header <code>X-API-Key</code> para autenticar</li>
</ol>
<p>Documentacao: <a href="https://docs.smartlic.tech/api">docs.smartlic.tech/api</a></p>
<p>Precisa de ajuda? Responda a este email ou entre em contato pelo suporte.</p>
<p>Atenciosamente,<br>Time SmartLic</p>
</body>
</html>"""
