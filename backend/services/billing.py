"""Billing service for subscription management.

Handles billing period updates and Stripe integration.
GTM-002: Removed pro-rata calculations — Stripe handles proration automatically.

Also provides create_intel_report_checkout() for one-time payment mode (issue #630).
"""

import os
import logging
from datetime import datetime
from typing import Optional, Literal

logger = logging.getLogger(__name__)


def update_stripe_subscription_billing_period(
    stripe_subscription_id: str,
    new_billing_period: Literal["monthly", "semiannual", "annual"],
    stripe_price_id_monthly: str,
    stripe_price_id_semiannual: str = "",
    stripe_price_id_annual: str = "",
) -> dict:
    """Update Stripe subscription billing period.

    GTM-002: Stripe handles proration automatically via proration_behavior.
    No manual credit calculation needed.

    Args:
        stripe_subscription_id: Stripe subscription ID (sub_...)
        new_billing_period: Target billing period
        stripe_price_id_monthly: Stripe price ID for monthly billing
        stripe_price_id_semiannual: Stripe price ID for semiannual billing
        stripe_price_id_annual: Stripe price ID for annual billing

    Returns:
        Updated Stripe subscription object
    """
    import stripe

    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        raise ValueError("STRIPE_SECRET_KEY not configured")

    # Determine target price ID based on billing period
    price_map = {
        "monthly": stripe_price_id_monthly,
        "semiannual": stripe_price_id_semiannual,
        "annual": stripe_price_id_annual,
    }
    target_price_id = price_map.get(new_billing_period, stripe_price_id_monthly)

    if not target_price_id:
        raise ValueError(f"No Stripe price ID configured for billing_period={new_billing_period}")

    logger.info(
        f"Updating Stripe subscription {stripe_subscription_id} to {new_billing_period} "
        f"billing (price_id={target_price_id})"
    )

    # Retrieve current subscription to get item ID
    subscription = stripe.Subscription.retrieve(stripe_subscription_id, api_key=stripe_key)

    # Update subscription — Stripe handles proration automatically
    updated_subscription = stripe.Subscription.modify(
        stripe_subscription_id,
        items=[{
            "id": subscription["items"]["data"][0]["id"],
            "price": target_price_id,
        }],
        proration_behavior="create_prorations",
        api_key=stripe_key,
    )

    logger.info(f"Successfully updated Stripe subscription {stripe_subscription_id}")
    return updated_subscription


def create_intel_report_checkout(
    product_type: str,
    entity_key: str,
    user_id: str,
) -> dict:
    """Create a Stripe Checkout session for an Intel Report one-time purchase.

    Products:
        - cnpj    → R$197.00 (INTEL-REPORT-001)
        - sector_uf → R$147.00 (INTEL-REPORT-002)

    NOTE: Stripe Products and Prices are created MANUALLY in the Stripe Dashboard.
    This function uses price_data with unit_amount so it works without pre-created
    Price objects. For production, pre-create Products in the Dashboard and use
    their price IDs in line_items instead of price_data.

    Args:
        product_type: "cnpj" or "sector_uf"
        entity_key: CNPJ value or "sector:uf" string
        user_id: Supabase user UUID

    Returns:
        {"checkout_url": str, "session_id": str}

    Raises:
        ValueError: invalid product_type
        stripe.error.StripeError: Stripe API error
    """
    import stripe

    from schemas.intel_report import VALID_PRODUCT_TYPES, INTEL_REPORT_PRICES

    if product_type not in VALID_PRODUCT_TYPES:
        raise ValueError(
            f"product_type deve ser um de {VALID_PRODUCT_TYPES}, recebido: {product_type!r}"
        )

    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        raise ValueError("STRIPE_SECRET_KEY not configured")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    unit_amount = INTEL_REPORT_PRICES[product_type]

    product_names = {
        "cnpj": "SmartLic Intel Report — Análise de Empresa",
        "sector_uf": "SmartLic Intel Report — Relatório Setor/UF",
    }

    # IMPORTANT: {CHECKOUT_SESSION_ID} is a Stripe template literal (server-side substitution).
    # The double braces {{ }} produce a single { } in the f-string, which Stripe then substitutes.
    success_url = (
        f"{frontend_url}/intel-reports/{{CHECKOUT_SESSION_ID}}?status=processing"
    )
    cancel_url = f"{frontend_url}/intel-reports/cancelado"

    logger.info(
        f"Creating Intel Report checkout: product_type={product_type}, "
        f"entity_key={entity_key!r}, user_id={user_id[:8]}"
    )

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card", "boleto", "pix"],
        line_items=[
            {
                "price_data": {
                    "currency": "brl",
                    "unit_amount": unit_amount,
                    "product_data": {
                        "name": product_names[product_type],
                        "description": f"Relatório inteligente para {entity_key}",
                    },
                },
                "quantity": 1,
            }
        ],
        metadata={
            "product_type": product_type,
            "entity_key": entity_key,
            "user_id": user_id,
            "platform": "smartlic",
        },
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=user_id,
        api_key=stripe_key,
    )

    logger.info(
        f"Intel Report checkout session created: session_id={session.id}, "
        f"user_id={user_id[:8]}"
    )
    return {"checkout_url": session.url, "session_id": session.id}


def get_next_billing_date(user_id: str) -> Optional[datetime]:
    """Get user's next billing date from Supabase.

    Args:
        user_id: User UUID

    Returns:
        Next billing date (timezone-aware) or None if no active subscription
    """
    from supabase_client import get_supabase

    sb = get_supabase()

    result = (
        sb.table("user_subscriptions")
        .select("expires_at, created_at, billing_period")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not result.data or len(result.data) == 0:
        return None

    sub = result.data[0]
    expires_at_str = sub.get("expires_at")

    if not expires_at_str:
        return None

    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    return expires_at
