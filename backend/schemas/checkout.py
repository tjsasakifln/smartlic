"""CONV-005b-2: Pydantic schemas for checkout endpoint."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CheckoutRequest(BaseModel):
    """Request body for POST /api/checkout/one-time."""

    sku: str
    context: dict[str, Any] = {}


class CheckoutResponse(BaseModel):
    """Response for a successful checkout session creation."""

    checkout_url: str


class ApiSubscriptionCheckoutRequest(BaseModel):
    """Request body for POST /api/checkout/api-subscription."""

    tier: str  # "api_starter", "api_pro", "api_scale"


class ApiSubscriptionCheckoutResponse(BaseModel):
    """Response for API subscription checkout session creation."""

    checkout_url: str
    session_id: str
