"""Stripe Checkout session creation for Intel Reports (#1781)."""
import os
import logging

logger = logging.getLogger(__name__)


def create_intel_report_checkout(
    product_type: str,
    entity_key: str,
    user_id: str,
) -> dict:
    """Create a Stripe Checkout session for an Intel Report one-time purchase."""
    import stripe
    from schemas.intel_report import INTEL_REPORT_PRICES, VALID_PRODUCT_TYPES

    if product_type not in VALID_PRODUCT_TYPES:
        raise ValueError(
            f"product_type must be one of {VALID_PRODUCT_TYPES}, got: {product_type!r}"
        )

    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        raise ValueError("STRIPE_SECRET_KEY not configured")

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    unit_amount = INTEL_REPORT_PRICES[product_type]

    product_names = {
        "cnpj": "SmartLic Intel Report - Analise de Empresa",
        "sector_uf": "SmartLic Intel Report - Relatorio Setor/UF",
        "subcontract": "SmartLic Intel Report - Subcontratacao",
    }

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
                        "description": f"Relatorio inteligente para {entity_key}",
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
