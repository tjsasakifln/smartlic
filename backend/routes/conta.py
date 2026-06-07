"""
Conta — account-management public endpoints (STORY-CONV-003c AC2).

Contains the one-click trial-cancellation flow:
  GET  /v1/conta/cancelar-trial?token=<jwt>  -> returns trial metadata for confirmation UI
  POST /v1/conta/cancelar-trial              -> executes cancellation

Both endpoints are public (token-authenticated only). The JWT carries the
``user_id`` + ``action='cancel_trial'`` claim and expires in 48h by default
(see ``services/trial_cancel_token.py``).

Design notes:
- Stripe trial cancellations do NOT generate proration — user keeps access
  until ``trial_end_ts`` regardless.
- Idempotent: cancelling an already-cancelled subscription is a no-op.
- Fail-safe: Stripe errors are logged but we still mark the profile in a
  sentinel state so the user doesn't get billed.
"""

from __future__ import annotations

from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from auth import require_auth
from log_sanitizer import get_sanitized_logger, mask_user_id
from pipeline.budget import _run_with_budget
from services.trial_cancel_token import (
    TrialCancelTokenError,
    verify_cancel_trial_token,
)
from supabase_client import get_supabase, sb_execute

logger = get_sanitized_logger(__name__)
router = APIRouter(prefix="/conta", tags=["conta"])


# ============================================================================
# Response schemas
# ============================================================================


class CancelTrialInfoResponse(BaseModel):
    """Returned by GET /cancelar-trial to populate the confirmation UI."""

    user_id: str
    email: str
    plan_name: str
    trial_end_ts: Optional[int] = Field(
        None, description="Unix epoch seconds when trial ends"
    )
    already_cancelled: bool = False


class CancelTrialRequest(BaseModel):
    token: str = Field(..., min_length=20, description="Signed cancel-trial JWT")


class CancelTrialResponse(BaseModel):
    cancelled: bool
    access_until: Optional[int] = Field(
        None,
        description="Unix epoch seconds — trial access remains until this timestamp",
    )
    already_cancelled: bool = False


# ============================================================================
# Helpers
# ============================================================================


def _error_response_for(reason: str) -> HTTPException:
    """Map token error reason to stable HTTP response. Opaque to avoid leaking why."""
    if reason in ("expired",):
        return HTTPException(
            status_code=410,
            detail={"error": "token_expired", "message": "Link expirado. Gere um novo."},
        )
    if reason in ("invalid_signature", "invalid_payload", "wrong_action", "token_required"):
        return HTTPException(
            status_code=400,
            detail={"error": "token_invalid", "message": "Link inválido."},
        )
    # jwt_secret_missing or unexpected
    return HTTPException(
        status_code=500,
        detail={"error": "server_config", "message": "Erro temporário. Tente novamente."},
    )


async def _load_profile_and_subscription(sb, user_id: str) -> tuple[Optional[dict], Optional[dict]]:
    """Fetch profile + active user_subscriptions row (may be None if user deleted)."""
    profile_result = await sb_execute(
        sb.table("profiles")
        .select("id, email, plan_type, subscription_status, stripe_subscription_id")
        .eq("id", user_id)
        .limit(1)
    )
    if not profile_result.data:
        return None, None
    profile = profile_result.data[0]

    sub_result = await sb_execute(
        sb.table("user_subscriptions")
        .select("id, plan_id, stripe_subscription_id, is_active, subscription_status")
        .eq("user_id", user_id)
        .eq("is_active", True)
        .limit(1)
    )
    subscription = sub_result.data[0] if sub_result.data else None
    return profile, subscription


def _fetch_trial_end_from_stripe(stripe_sub_id: Optional[str]) -> Optional[int]:
    """Best-effort: read trial_end from Stripe. Returns None on any error."""
    if not stripe_sub_id:
        return None
    try:
        sub = stripe.Subscription.retrieve(stripe_sub_id)
        trial_end = sub.get("trial_end") if hasattr(sub, "get") else None
        return int(trial_end) if trial_end else None
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(f"Failed to retrieve Stripe subscription {stripe_sub_id[:8]}***: {exc}")
        return None


# ============================================================================
# Routes
# ============================================================================


@router.get("/cancelar-trial", response_model=CancelTrialInfoResponse)
async def cancel_trial_info(token: str = Query(..., min_length=20)) -> CancelTrialInfoResponse:
    """
    Return trial metadata for the confirmation UI.

    Does NOT mutate state. Intended to be called by the frontend confirmation
    page (STORY-CONV-003c frontend).
    """
    try:
        user_id = verify_cancel_trial_token(token)
    except TrialCancelTokenError as exc:
        logger.info(f"cancel_trial_info: invalid token reason={exc.reason}")
        raise _error_response_for(exc.reason) from exc

    sb = get_supabase()
    profile, subscription = await _load_profile_and_subscription(sb, user_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": "user_not_found", "message": "Usuário não encontrado."},
        )

    stripe_sub_id = (subscription or {}).get("stripe_subscription_id") or profile.get(
        "stripe_subscription_id"
    )
    trial_end_ts = _fetch_trial_end_from_stripe(stripe_sub_id)

    subscription_status = (subscription or {}).get("subscription_status") or profile.get(
        "subscription_status", ""
    )
    already_cancelled = subscription_status in ("canceled_trial", "cancelled", "canceled")

    plan_name = (subscription or {}).get("plan_id") or profile.get("plan_type") or "free_trial"

    logger.info(
        f"cancel_trial_info: user={mask_user_id(user_id)} already_cancelled={already_cancelled}"
    )

    return CancelTrialInfoResponse(
        user_id=user_id,
        email=profile.get("email", ""),
        plan_name=plan_name,
        trial_end_ts=trial_end_ts,
        already_cancelled=already_cancelled,
    )


@router.post("/cancelar-trial", response_model=CancelTrialResponse)
async def cancel_trial_execute(payload: CancelTrialRequest) -> CancelTrialResponse:
    """
    Cancel the user's active trial subscription.

    Idempotent: if already cancelled, returns ``cancelled=true`` + ``already_cancelled=true``.
    Fail-safe: Stripe errors are swallowed but profile is marked ``canceled_trial``
    so the downgrade still happens if the Stripe-side cancel retries succeed out-of-band
    via billing reconciliation (STORY-314).
    """
    try:
        user_id = verify_cancel_trial_token(payload.token)
    except TrialCancelTokenError as exc:
        logger.info(f"cancel_trial_execute: invalid token reason={exc.reason}")
        raise _error_response_for(exc.reason) from exc

    sb = get_supabase()
    profile, subscription = await _load_profile_and_subscription(sb, user_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": "user_not_found", "message": "Usuário não encontrado."},
        )

    subscription_status = (subscription or {}).get("subscription_status") or profile.get(
        "subscription_status", ""
    )
    if subscription_status in ("canceled_trial", "cancelled", "canceled"):
        stripe_sub_id = (subscription or {}).get("stripe_subscription_id") or profile.get(
            "stripe_subscription_id"
        )
        trial_end_ts = _fetch_trial_end_from_stripe(stripe_sub_id)
        logger.info(f"cancel_trial_execute: already cancelled user={mask_user_id(user_id)}")
        return CancelTrialResponse(
            cancelled=True, access_until=trial_end_ts, already_cancelled=True
        )

    stripe_sub_id = (subscription or {}).get("stripe_subscription_id") or profile.get(
        "stripe_subscription_id"
    )

    trial_end_ts: Optional[int] = None

    # 1) Call Stripe.Subscription.cancel — trials do NOT generate proration.
    if stripe_sub_id:
        try:
            cancelled_sub = stripe.Subscription.cancel(stripe_sub_id)
            trial_end_ts = (
                cancelled_sub.get("trial_end")
                if hasattr(cancelled_sub, "get")
                else None
            )
            if trial_end_ts is not None:
                trial_end_ts = int(trial_end_ts)
            logger.info(
                f"Trial cancelled via one-click: user={mask_user_id(user_id)} sub={stripe_sub_id[:8]}***"
            )
        except stripe.error.InvalidRequestError as exc:
            # Already cancelled on Stripe side, proceed with local cleanup
            logger.warning(
                f"Stripe cancel returned InvalidRequestError (likely already cancelled): {exc}"
            )
        except Exception as exc:  # pragma: no cover — best-effort
            logger.error(f"Stripe cancel failed for sub {stripe_sub_id[:8]}***: {exc}")
            # DO NOT raise — local state gets updated below, billing recon handles Stripe retry

    # 2) Update local state (profiles + user_subscriptions).
    try:
        await sb_execute(
            sb.table("profiles").update(
                {
                    "subscription_status": "canceled_trial",
                    "plan_type": "free_trial",
                }
            ).eq("id", user_id),
            category="write",
        )
    except Exception as exc:
        logger.error(f"Failed to update profiles during trial cancel: {exc}")

    if subscription:
        try:
            await sb_execute(
                sb.table("user_subscriptions").update(
                    {"subscription_status": "canceled", "is_active": False}
                ).eq("id", subscription["id"]),
                category="write",
            )
        except Exception as exc:
            logger.error(f"Failed to update user_subscriptions during trial cancel: {exc}")

    # 3) Mixpanel-shaped structured log for CONV-003c AC4 observability.
    logger.info(
        "analytics.trial_cancelled_before_charge",
        extra={
            "event": "trial_cancelled_before_charge",
            "user_id": user_id,
            "trial_end_ts": trial_end_ts,
            "source": "one_click_email",
        },
    )
    # CONV-003c AC4 Prometheus: real-time rollout monitoring.
    try:
        from metrics import TRIAL_CANCEL_BEFORE_CHARGE

        TRIAL_CANCEL_BEFORE_CHARGE.inc()
    except Exception:  # noqa: BLE001 — metrics must never break cancel
        pass

    return CancelTrialResponse(
        cancelled=True, access_until=trial_end_ts, already_cancelled=False
    )


# ============================================================================
# DIGEST-004: Digest preference frequency toggle
# ============================================================================

_VALID_FREQUENCIES = frozenset({"daily", "weekly", "twice_weekly", "off", "none"})


class PreferenciasRequest(BaseModel):
    """Request body for PATCH /conta/preferencias — frequency toggle."""

    frequency: str = Field(
        ...,
        description="Digest frequency: daily, weekly, twice_weekly, off, none",
    )

    @field_validator("frequency")
    @classmethod
    def _validate_frequency(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in _VALID_FREQUENCIES:
            raise ValueError(
                f"Frequência inválida: '{v}'. Opções: {', '.join(sorted(_VALID_FREQUENCIES))}"
            )
        return normalized


class PreferenciasResponse(BaseModel):
    """Response for PATCH /conta/preferencias — current digest preferences."""

    frequency: str = Field(
        ...,
        description="Digest frequency (API namespace: off, not none)",
    )
    enabled: bool = Field(
        default=True,
        description="Whether the digest email is enabled",
    )
    last_digest_sent_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp of last sent digest",
    )


@router.patch("/preferencias", response_model=PreferenciasResponse)
async def update_preferencias(
    payload: PreferenciasRequest,
    user: dict = Depends(require_auth),
) -> PreferenciasResponse:
    """DIGEST-004: Toggle the user's digest email frequency.

    Accepts ``frequency`` field with one of:
      - ``daily`` — every day at 07:00 BRT
      - ``twice_weekly`` — Monday + Thursday at 07:00 BRT
      - ``weekly`` — Monday at 07:00 BRT
      - ``off`` / ``none`` — disable digest emails

    Internally normalizes ``off`` → ``none`` for DB storage (DIGEST-001 naming).
    Returns the API-facing value (``off``, never ``none``) on the response.
    Uses upsert on ``user_id`` — creates a row if none exists.
    Uses ``_run_with_budget`` for the DB write (RES-BE-001/015 compliance).
    """
    user_id = user["id"]
    raw_frequency = payload.frequency

    # DIGEST-001: normalize API value "off" → DB value "none"
    db_frequency = "none" if raw_frequency in ("off", "none") else raw_frequency

    sb = get_supabase()

    try:
        result = await _run_with_budget(
            sb_execute(
                sb.table("alert_preferences").upsert(
                    {
                        "user_id": user_id,
                        "frequency": db_frequency,
                    },
                    on_conflict="user_id",
                ),
                category="write",
            ),
            budget=5.0,
            phase="route",
            source="conta.update_preferencias",
        )
    except Exception as exc:
        logger.error(f"Failed to update digest preferences for {mask_user_id(user_id)}: {exc}")
        raise HTTPException(
            status_code=500,
            detail="Erro ao salvar preferências de frequência.",
        ) from exc

    row = result.data[0] if result.data else {}

    # DIGEST-001: normalize DB value "none" → API value "off"
    api_frequency = row.get("frequency", db_frequency)
    if api_frequency == "none":
        api_frequency = "off"

    logger.info(
        "DIGEST-004: frequency updated user=%s frequency=%s",
        mask_user_id(user_id),
        api_frequency,
    )

    return PreferenciasResponse(
        frequency=api_frequency,
        enabled=row.get("enabled", True),
        last_digest_sent_at=row.get("last_digest_sent_at"),
    )


# ============================================================================
# API-SELF-006: API usage dashboard endpoint
# ============================================================================


class ApiKeyInfo(BaseModel):
    """Public representation of a user's API key (no hash, no plaintext)."""

    id: str
    name: str
    created_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None


class DailyUsage(BaseModel):
    """Usage count for a single day."""

    date: str  # YYYY-MM-DD
    count: int


class ApiUsageResponse(BaseModel):
    """GET /v1/conta/api-usage — API usage dashboard data."""

    api_keys: list[ApiKeyInfo]
    current_month_usage: int
    monthly_limit: int
    tier: str  # "starter" | "pro" | "scale" | "unlimited" | "none"
    daily_usage: list[DailyUsage]
    month: str  # YYYY-MM


def _get_tier_for_plan(plan_type: str | None) -> str:
    """Map plan_type to API tier."""
    if not plan_type:
        return "none"
    from api_key_rate_limit import _API_KEY_TIER_MAP  # reuse existing mapping
    return _API_KEY_TIER_MAP.get(plan_type, "starter")


def _get_monthly_limit(tier: str) -> int:
    """Get monthly request limit for a tier."""
    from api_key_rate_limit import API_KEY_TIER_LIMITS  # reuse existing limits
    return API_KEY_TIER_LIMITS.get(tier, 1000)


@router.get("/api-usage", response_model=ApiUsageResponse)
async def get_api_usage(
    user: dict = Depends(require_auth),
) -> ApiUsageResponse:
    """API-SELF-006: Return API usage data for the authenticated user's dashboard.

    Includes API keys, current month usage, daily breakdown, tier, and limits.
    """
    user_id = user["id"]
    sb = get_supabase()

    # 1. Fetch user's API keys (non-revoked)
    keys_result = await _run_with_budget(
        sb_execute(
            sb.table("api_keys")
            .select("id, name, created_at, last_used_at, revoked_at")
            .eq("user_id", user_id)
            .is_("revoked_at", None)
            .order("created_at", desc=True),
            category="read",
        ),
        budget=3.0,
        phase="route",
        source="conta.get_api_usage.keys",
    )

    api_keys: list[ApiKeyInfo] = []
    if keys_result.data:
        for row in keys_result.data:
            api_keys.append(ApiKeyInfo(
                id=row["id"],
                name=row.get("name", ""),
                created_at=row.get("created_at", ""),
                last_used_at=row.get("last_used_at"),
                revoked_at=row.get("revoked_at"),
            ))

    # 2. Get current month (BRT)
    from datetime import datetime, timedelta, timezone
    now_brt = datetime.now(timezone.utc) - timedelta(hours=3)
    current_month = now_brt.strftime("%Y-%m")

    # 3. Fetch current month usage for user's API keys
    key_ids = [k.id for k in api_keys]
    current_month_usage = 0
    daily_usage_map: dict[str, int] = {}

    if key_ids:
        usage_result = await _run_with_budget(
            sb_execute(
                sb.table("api_usage_records")
                .select("api_key_id, request_count, month")
                .eq("user_id", user_id)
                .eq("month", current_month)
                .in_("api_key_id", key_ids),
                category="read",
            ),
            budget=3.0,
            phase="route",
            source="conta.get_api_usage.records",
        )

        if usage_result.data:
            for row in usage_result.data:
                current_month_usage += row.get("request_count", 0)

    # 4. Get daily usage from Redis (faster than DB for daily granularity)
    try:
        from redis_pool import get_redis_pool
        redis = get_redis_pool()
        if redis:
            # Scan Redis keys for daily usage: api_key_daily:{key_id}:{YYYY-MM-DD}
            for key_id in key_ids:
                cursor = 0
                pattern = f"api_key_daily:{key_id}:{current_month}-*"
                while True:
                    cursor, keys = redis.scan(cursor, match=pattern, count=100)
                    for k in keys:
                        day_str = k.decode().rsplit(":", 1)[-1]  # YYYY-MM-DD
                        count = int(redis.get(k) or 0)
                        daily_usage_map[day_str] = daily_usage_map.get(day_str, 0) + count
                    if cursor == 0:
                        break
    except Exception:
        # Redis unavailable — fall back to aggregated monthly total only
        logger.warning("Redis unavailable for daily usage breakdown, returning monthly total only")

    # 5. Get user's plan tier for API limits
    profile_result = await _run_with_budget(
        sb_execute(
            sb.table("profiles")
            .select("plan_type, api_tier")
            .eq("id", user_id)
            .single(),
            category="read",
        ),
        budget=2.0,
        phase="route",
        source="conta.get_api_usage.profile",
    )

    tier = "none"
    if profile_result.data:
        plan_type = profile_result.data.get("plan_type")
        api_tier = profile_result.data.get("api_tier")
        if api_tier:
            # Map api_tier (api_starter/api_pro/api_scale) to short form
            tier = api_tier.replace("api_", "")
        elif plan_type:
            tier = _get_tier_for_plan(plan_type)

    monthly_limit = _get_monthly_limit(tier)

    # 6. Build daily usage sorted by date
    daily_usage = [
        DailyUsage(date=date, count=count)
        for date, count in sorted(daily_usage_map.items())
    ]

    return ApiUsageResponse(
        api_keys=api_keys,
        current_month_usage=current_month_usage,
        monthly_limit=monthly_limit,
        tier=tier,
        daily_usage=daily_usage,
        month=current_month,
    )
