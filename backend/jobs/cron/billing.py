"""jobs.cron.billing — Facade: billing cron functions (Issue #1781).

All implementation has been moved to ``jobs.cron.billing_loops``. This module
re-exports constants, loop classes, and ``start_*_task`` wrappers for backward
compatibility.

Legacy ``run_*`` and ``_*_loop`` functions delegate to the corresponding
``BaseCronLoop`` subclasses so that existing tests and imports continue to work.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from jobs.cron.billing_loops import (
    ReconciliationLoop,
    PreDunningLoop,
    RevenueShareLoop,
    PlanReconciliationLoop,
    StripeEventsPurgeLoop,
)

logger = logging.getLogger(__name__)

# ── Lock keys / constants (re-exported) ─────────────────────────────────────
RECONCILIATION_LOCK_KEY = "smartlic:reconciliation:lock"
RECONCILIATION_LOCK_TTL = 30 * 60
PRE_DUNNING_INTERVAL_SECONDS = 24 * 60 * 60
REVENUE_SHARE_LOCK_KEY = "smartlic:revenue_share:lock"
REVENUE_SHARE_LOCK_TTL = 30 * 60
PLAN_RECONCILIATION_LOCK_KEY = "smartlic:plan_reconciliation:lock"
PLAN_RECONCILIATION_LOCK_TTL = 10 * 60
PLAN_RECONCILIATION_INTERVAL = 12 * 60 * 60
STRIPE_EVENTS_RETENTION_DAYS = 90
STRIPE_PURGE_INTERVAL_SECONDS = 24 * 60 * 60
_MONITORED_TABLES = [
    "search_results_cache", "search_results_store", "search_sessions",
    "stripe_webhook_events", "profiles", "user_subscriptions",
    "conversations", "messages", "alert_runs", "classification_feedback",
]


# ── Lock / timing helpers (used by legacy imports — keep for backward compat) ─

async def _acquire_lock(key: str, ttl: int) -> bool:
    """Acquire a Redis NX lock. Returns True if acquired (or Redis unavailable)."""
    try:
        from redis_pool import get_redis_pool
        redis = await get_redis_pool()
        if redis:
            acquired = await redis.set(key, datetime.now(timezone.utc).isoformat(), nx=True, ex=ttl)
            if not acquired:
                return False
    except Exception as e:
        logger.warning(f"Redis lock check failed (proceeding): {e}")
    return True


async def _release_lock(key: str) -> None:
    try:
        from redis_pool import get_redis_pool
        redis = await get_redis_pool()
        if redis:
            await redis.delete(key)
    except Exception:
        pass


def _next_utc_hour(target_hour: int, max_delay: float = 86400.0) -> float:
    """Compute seconds until next occurrence of ``target_hour`` UTC."""
    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if now.hour >= target_hour:
        next_run += timedelta(days=1)
    return max(60.0, min((next_run - now).total_seconds(), max_delay))


# ── Legacy run_* business functions (delegate to loop.run_once()) ────────────

async def run_reconciliation() -> dict:
    return await ReconciliationLoop().run_once()


async def check_pre_dunning_cards() -> dict:
    return await PreDunningLoop().run_once()


async def run_revenue_share_report() -> dict:
    return await RevenueShareLoop().run_once()


async def run_plan_reconciliation() -> dict:
    return await PlanReconciliationLoop().run_once()


async def update_table_size_metrics() -> dict:
    from supabase_client import get_supabase, sb_execute_direct
    from metrics import DB_TABLE_SIZE_BYTES
    sizes = {}
    try:
        sb = get_supabase()
        for table_name in _MONITORED_TABLES:
            try:
                result = await sb_execute_direct(sb.rpc("pg_total_relation_size_safe", {"tbl": table_name}))
                if result and result.data is not None:
                    size_bytes = int(result.data) if not isinstance(result.data, list) else (int(result.data[0]) if result.data else 0)
                    DB_TABLE_SIZE_BYTES.labels(table_name=table_name).set(size_bytes)
                    sizes[table_name] = size_bytes
            except Exception as e:
                logger.debug("DEBT-010: Table size query failed for %s: %s", table_name, e)
                sizes[table_name] = -1
        return {"status": "ok", "sizes": sizes}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def purge_old_stripe_events() -> dict:
    return await StripeEventsPurgeLoop().run_once()


# ── Legacy _*_loop functions (delegate to loop.start()) ─────────────────────

async def _reconciliation_loop() -> None:
    await ReconciliationLoop().start()


async def _pre_dunning_loop() -> None:
    await PreDunningLoop().start()


async def _revenue_share_loop() -> None:
    await RevenueShareLoop().start()


async def _plan_reconciliation_loop() -> None:
    await PlanReconciliationLoop().start()


async def _stripe_events_purge_loop() -> None:
    await StripeEventsPurgeLoop().start()


# ── start_*_task factories (called by task_registry on lifespan startup) ──

async def start_reconciliation_task() -> asyncio.Task:
    from config import RECONCILIATION_ENABLED
    if not RECONCILIATION_ENABLED:
        logger.info("Reconciliation disabled — starting noop task")
        return asyncio.create_task(asyncio.sleep(0), name="reconciliation_noop")
    loop = ReconciliationLoop()
    task = asyncio.create_task(loop.start(), name="stripe_reconciliation")
    logger.info("STORY-314: Stripe reconciliation task started (daily at 03:00 BRT)")
    return task


async def start_pre_dunning_task() -> asyncio.Task:
    loop = PreDunningLoop()
    task = asyncio.create_task(loop.start(), name="pre_dunning")
    logger.info("Pre-dunning card expiry check started (interval: 24h)")
    return task


async def start_revenue_share_task() -> asyncio.Task:
    loop = RevenueShareLoop()
    task = asyncio.create_task(loop.start(), name="revenue_share_report")
    logger.info("STORY-323: Revenue share report task started (monthly, day 1, 09:00 BRT)")
    return task


async def start_plan_reconciliation_task() -> asyncio.Task:
    loop = PlanReconciliationLoop()
    task = asyncio.create_task(loop.start(), name="plan_reconciliation")
    logger.info("DEBT-010: Plan reconciliation task started (interval: 12h)")
    return task


async def start_stripe_events_purge_task() -> asyncio.Task:
    loop = StripeEventsPurgeLoop()
    task = asyncio.create_task(loop.start(), name="stripe_events_purge")
    logger.info("HARDEN-028: Stripe events purge task started (interval: 24h, retention: %dd)", STRIPE_EVENTS_RETENTION_DAYS)
    return task
