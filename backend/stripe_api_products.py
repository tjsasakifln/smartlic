"""API-SELF-004: Stripe product configuration for API tiers.

Defines the three API access tiers (Starter, Pro, Scale) with their
Stripe Price IDs sourced from environment variables. Price IDs are
set in the environment so they can differ between dev/staging/prod
without code changes.

Usage:
    from stripe_api_products import (
        API_PRODUCTS, get_api_product, get_tier_by_price_id,
        API_TIER_STARTER, API_TIER_PRO, API_TIER_SCALE,
    )
"""

from __future__ import annotations

import os
from typing import Optional

# ---------------------------------------------------------------------------
# Tier identifiers
# ---------------------------------------------------------------------------

API_TIER_STARTER: str = "api_starter"
API_TIER_PRO: str = "api_pro"
API_TIER_SCALE: str = "api_scale"

# ---------------------------------------------------------------------------
# Product definitions
# ---------------------------------------------------------------------------

API_PRODUCTS: dict[str, dict] = {
    API_TIER_STARTER: {
        "id": API_TIER_STARTER,
        "name": "API Starter",
        "display_name": "API Starter",
        "description": "Para testar e prototipar integracoes com licitacoes publicas.",
        "price_brl": 9700,  # R$ 97,00
        "price_id_env": "STRIPE_PRICE_API_STARTER",
        "max_requests_per_month": 500,
        "max_requests_per_min": 10,
        "features": ["Ate 500 requisicoes/mes", "10 req/min", "Suporte email"],
    },
    API_TIER_PRO: {
        "id": API_TIER_PRO,
        "name": "API Pro",
        "display_name": "API Pro",
        "description": "Para equipes que precisam de acesso regular a dados de licitacoes.",
        "price_brl": 29700,  # R$ 297,00
        "price_id_env": "STRIPE_PRICE_API_PRO",
        "max_requests_per_month": 5000,
        "max_requests_per_min": 60,
        "features": ["Ate 5.000 requisicoes/mes", "60 req/min", "Suporte prioritario"],
    },
    API_TIER_SCALE: {
        "id": API_TIER_SCALE,
        "name": "API Scale",
        "display_name": "API Scale",
        "description": "Para empresas com alto volume de consultas e analise de dados.",
        "price_brl": 99700,  # R$ 997,00
        "price_id_env": "STRIPE_PRICE_API_SCALE",
        "max_requests_per_month": 50000,
        "max_requests_per_min": 300,
        "features": ["Ate 50.000 requisicoes/mes", "300 req/min", "Suporte dedicado 24/7"],
    },
}

# ---------------------------------------------------------------------------
# Tier lookup helpers
# ---------------------------------------------------------------------------


def get_api_product(tier_id: str) -> Optional[dict]:
    """Return the product definition dict for *tier_id*, or None."""
    return API_PRODUCTS.get(tier_id)


def get_tier_by_price_id(price_id: str) -> Optional[str]:
    """Return the tier id whose ``price_id_env`` resolves to *price_id*.

    Each tier's Stripe Price ID is read from the environment variable
    named in ``price_id_env``. This helper compares *price_id* to the
    current env value for each tier and returns the matching tier id.

    Returns:
        The tier id string (e.g. ``"api_starter"``) or None if no match.
    """
    for tier_id, product in API_PRODUCTS.items():
        env_var = product["price_id_env"]
        expected = os.getenv(env_var)
        if expected and price_id == expected:
            return tier_id
    return None


def get_tier_price_id(tier_id: str) -> Optional[str]:
    """Return the resolved Stripe Price ID for *tier_id*, or None."""
    product = API_PRODUCTS.get(tier_id)
    if product is None:
        return None
    return os.getenv(product["price_id_env"])


# ---------------------------------------------------------------------------
# Tier limits (used by metered billing)
# ---------------------------------------------------------------------------

TIER_LIMITS: dict[str, dict] = {
    API_TIER_STARTER: {"max_requests_per_month": 500, "max_requests_per_min": 10},
    API_TIER_PRO: {"max_requests_per_month": 5000, "max_requests_per_min": 60},
    API_TIER_SCALE: {"max_requests_per_month": 50000, "max_requests_per_min": 300},
}


def get_tier_monthly_limit(tier_id: str) -> int:
    """Return the monthly request limit for *tier_id*.

    Returns 0 if tier is unknown (effectively blocked).
    """
    limits = TIER_LIMITS.get(tier_id)
    if limits is None:
        return 0
    return limits["max_requests_per_month"]
