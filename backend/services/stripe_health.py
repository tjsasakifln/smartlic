"""Stripe connectivity health check with grace period and founder notification.

DEC-BIL-GAP-02: Estrategia se Stripe offline.

Provides:
- check_stripe_connection() — probes Stripe API, result cached 60s
- get_stripe_health() — returns status dict with grace period logic
- 4-hour grace period before notifying founder
- 2-hour cooldown between notifications to prevent spam
- Cross-worker state via Redis (fallback InMemoryCache)
- CRITICAL log + Sentry capture_message on offline detection
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
STRIPE_CACHE_TTL = 60           # seconds — how long to cache connection probe
GRACE_PERIOD_HOURS = 4          # hours before notifying founder
NOTIFICATION_COOLDOWN_HOURS = 2 # hours between notifications

# Redis key prefixes
_REDIS_PREFIX = "stripe_health"
_KEY_FAIL_SINCE = f"{_REDIS_PREFIX}:fail_since"          # timestamp of first failure
_KEY_LAST_NOTIFICATION = f"{_REDIS_PREFIX}:last_notification"  # timestamp of last notification
_KEY_CACHED_STATUS = f"{_REDIS_PREFIX}:cached_status"    # "ok" or "unreachable"

# Founder email config
FOUNDER_EMAIL = "tiago.sasaki@gmail.com"
FOUNDER_NOTIFICATION_SUBJECT = "[SmartLic] CRITICAL: Stripe offline detectado"
FOUNDER_EMAIL_FROM = "Tiago do SmartLic <tiago.sasaki@confenge.com.br>"


# ---------------------------------------------------------------------------
# In-memory state (fallback when Redis unavailable)
# ---------------------------------------------------------------------------
_inmemory_fail_since: Optional[float] = None
_inmemory_last_notification: Optional[float] = None
_inmemory_cached_status: Optional[str] = None
_inmemory_cache_ts: float = 0.0


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------
async def _get_redis() -> Optional[object]:
    """Get async Redis pool if available."""
    try:
        from redis_pool import get_redis_pool
        return await get_redis_pool()
    except Exception:
        return None


async def _redis_get(key: str) -> Optional[str]:
    """Get value from Redis."""
    redis = await _get_redis()
    if redis:
        try:
            return await redis.get(key)
        except Exception as exc:
            logger.debug("Redis GET %s failed: %s", key, exc)
    return None


async def _redis_set(key: str, value: str, ttl: int = 7200) -> None:
    """Set value in Redis with TTL."""
    redis = await _get_redis()
    if redis:
        try:
            await redis.setex(key, ttl, value)
        except Exception as exc:
            logger.debug("Redis SETEX %s failed: %s", key, exc)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------
def _stripe_configured() -> bool:
    """Check if Stripe secret key is configured."""
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key:
        logger.warning("STRIPE_SECRET_KEY not configured — stripe_health unavailable")
        return False
    return True


async def check_stripe_connection() -> bool:
    """Check Stripe connectivity with 60s result caching.

    Returns True if Stripe is reachable, False otherwise.
    Result is cached for STRIPE_CACHE_TTL seconds to avoid hammering the API.
    """
    import stripe

    # Check cache first (Redis, then in-memory)
    now = time.monotonic()

    # Try Redis cache
    cached = await _redis_get(_KEY_CACHED_STATUS)
    if cached == "ok":
        return True
    if cached == "unreachable":
        return False

    # Try in-memory cache
    global _inmemory_cache_ts, _inmemory_cached_status
    if _inmemory_cached_status is not None and (now - _inmemory_cache_ts) < STRIPE_CACHE_TTL:
        return _inmemory_cached_status == "ok"

    # Probe Stripe
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
    try:
        stripe.Account.retrieve()
        # Cache result
        await _redis_set(_KEY_CACHED_STATUS, "ok", STRIPE_CACHE_TTL + 10)
        _inmemory_cached_status = "ok"
        _inmemory_cache_ts = now
        return True
    except Exception:
        await _redis_set(_KEY_CACHED_STATUS, "unreachable", STRIPE_CACHE_TTL + 10)
        _inmemory_cached_status = "unreachable"
        _inmemory_cache_ts = now
        return False


def _get_fail_since() -> Optional[float]:
    """Get timestamp when Stripe was first detected as offline (monotonic)."""
    return _inmemory_fail_since


def _set_fail_since(ts: Optional[float]) -> None:
    """Set/clear the fail_since timestamp."""
    global _inmemory_fail_since
    _inmemory_fail_since = ts


def _get_last_notification() -> Optional[float]:
    """Get timestamp of last founder notification (monotonic)."""
    return _inmemory_last_notification


def _set_last_notification(ts: Optional[float]) -> None:
    """Set/clear the last notification timestamp."""
    global _inmemory_last_notification
    _inmemory_last_notification = ts


async def _should_notify(fail_since: float) -> bool:
    """Check if founder should be notified based on grace period and cooldown.

    Args:
        fail_since: Monotonic timestamp when failure was first detected.

    Returns:
        True if notification should be sent.
    """
    now = time.monotonic()
    elapsed = now - fail_since

    # Grace period not yet elapsed
    if elapsed < GRACE_PERIOD_HOURS * 3600:
        logger.info(
            "Stripe offline detected (%.1f min ago) — within %.0fh grace period, no notification",
            elapsed / 60,
            GRACE_PERIOD_HOURS,
        )
        return False

    # Check cooldown
    last_notification = _get_last_notification()
    if last_notification is not None:
        since_last = now - last_notification
        if since_last < NOTIFICATION_COOLDOWN_HOURS * 3600:
            logger.info(
                "Stripe offline — last notification was %.1f min ago (cooldown %.0fh)",
                since_last / 60,
                NOTIFICATION_COOLDOWN_HOURS,
            )
            return False

    return True


def _send_founder_notification(fail_since: float) -> None:
    """Send async email notification to founder about Stripe outage.

    Uses send_email_async to avoid blocking the health check.

    Args:
        fail_since: Monotonic timestamp when failure was first detected.
    """
    elapsed_hours = (time.monotonic() - fail_since) / 3600
    fail_ts_iso = datetime.fromtimestamp(
        time.time() - (time.monotonic() - fail_since), tz=timezone.utc
    ).isoformat()

    html = f"""
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #dc2626;">Alerta: Stripe Offline</h2>
        <p>O Stripe foi detectado como <strong>offline</strong> ha aproximadamente
        <strong>{elapsed_hours:.1f}h</strong>.</p>

        <table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Primeira falha</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{fail_ts_iso}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Duracao estimada</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{elapsed_hours:.1f}h</td>
            </tr>
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Impacto</td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    Checkouts, assinaturas, e faturamento podem estar comprometidos.
                    Usuarios com trial ativo continuam acessando (plan_type mantido).
                </td>
            </tr>
        </table>

        <p><strong>Proximo passo:</strong> Verifique o status do Stripe em
        <a href="https://status.stripe.com">status.stripe.com</a>.</p>
        <p>Consulte o runbook em <code>docs/runbooks/stripe-outage.md</code>
        para procedimentos de restauracao.</p>
        <hr>
        <p style="color: #666; font-size: 12px;">
            Este alerta foi gerado automaticamente pelo health check do SmartLic.
        </p>
    </body>
    </html>
    """

    try:
        from email_service import send_email_async
        send_email_async(
            to=FOUNDER_EMAIL,
            subject=FOUNDER_NOTIFICATION_SUBJECT,
            html=html,
            from_email=FOUNDER_EMAIL_FROM,
            reply_to=FOUNDER_EMAIL,
            tags=[{"name": "category", "value": "stripe_health"}],
        )
        logger.info("Founder notification sent for Stripe offline (%.1fh)", elapsed_hours)
    except Exception as exc:
        logger.error("Failed to send founder notification: %s", exc)


async def _try_sync_fail_since_from_redis() -> None:
    """Try to recover fail_since from Redis for cross-worker consistency."""
    global _inmemory_fail_since
    try:
        redis_ts_str = await _redis_get(_KEY_FAIL_SINCE)
        if redis_ts_str is not None:
            stored_ts = float(redis_ts_str)
            if _inmemory_fail_since is None or stored_ts < _inmemory_fail_since:
                _inmemory_fail_since = stored_ts
    except Exception:
        pass


async def _try_sync_last_notification_from_redis() -> None:
    """Try to recover last_notification from Redis for cross-worker consistency."""
    global _inmemory_last_notification
    try:
        redis_ts_str = await _redis_get(_KEY_LAST_NOTIFICATION)
        if redis_ts_str is not None:
            stored_ts = float(redis_ts_str)
            if _inmemory_last_notification is None or stored_ts > _inmemory_last_notification:
                _inmemory_last_notification = stored_ts
    except Exception:
        pass


async def get_stripe_health() -> dict:
    """Get Stripe connection health status with grace period logic.

    Returns:
        dict with keys:
            "stripe": "ok" or "unreachable"
            "since": ISO timestamp of first failure (only when unreachable)
            "grace_period_hours": int
            "grace_remaining_hours": float (only when unreachable and within grace)
            "notified": bool (only when unreachable and grace exceeded)
    """
    if not _stripe_configured():
        return {"stripe": "ok"}  # No Stripe = no billing issues (dev mode)

    now = time.monotonic()

    # Try to sync cross-worker state
    await _try_sync_fail_since_from_redis()
    await _try_sync_last_notification_from_redis()

    is_online = await check_stripe_connection()

    if is_online:
        # Stripe recovered — clear failure state
        if _get_fail_since() is not None:
            _set_fail_since(None)
            _set_last_notification(None)
            await _redis_set(_KEY_FAIL_SINCE, "cleared", 3600)
            await _redis_set(_KEY_LAST_NOTIFICATION, "cleared", 3600)
            logger.info("Stripe connection restored — clearing offline state")
        return {"stripe": "ok"}

    # Stripe offline
    if _get_fail_since() is None:
        # First failure detected
        _set_fail_since(now)
        await _redis_set(_KEY_FAIL_SINCE, str(now), 86400)

        # Log CRITICAL + Sentry on first detection
        logger.critical("Stripe connection LOST — starting %.0fh grace period", GRACE_PERIOD_HOURS)
        try:
            import sentry_sdk
            sentry_sdk.capture_message(
                f"Stripe connection lost — {GRACE_PERIOD_HOURS}h grace period started",
                level="critical",
            )
        except Exception:
            pass

    fail_since = _get_fail_since()
    assert fail_since is not None  # Guaranteed by set above

    elapsed = now - fail_since
    grace_remaining = max(0.0, (GRACE_PERIOD_HOURS * 3600 - elapsed) / 3600)
    fail_ts_iso = datetime.fromtimestamp(
        time.time() - elapsed, tz=timezone.utc
    ).isoformat()

    result = {
        "stripe": "unreachable",
        "since": fail_ts_iso,
        "grace_period_hours": GRACE_PERIOD_HOURS,
    }

    # Check if grace period has elapsed
    if await _should_notify(fail_since):
        _send_founder_notification(fail_since)
        _set_last_notification(now)
        await _redis_set(_KEY_LAST_NOTIFICATION, str(now), 86400)

    # Always set 'notified' once grace period has elapsed, even during cooldown
    if elapsed >= GRACE_PERIOD_HOURS * 3600:
        result["notified"] = True
    else:
        result["grace_remaining_hours"] = round(grace_remaining, 1)

    return result
