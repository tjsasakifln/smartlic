"""jobs.cron.data_retention — Unified data retention/purge orchestrator (GAP-005).

Automates purge policies for temporal tables per the documented policy in
docs/operations/data-retention-policy.md.

Policies implemented here:
  - trial_email_log:          purge > 180 days (AC3)
  - messages:                 purge > 365 days (AC4)
  - ingestion_checkpoints:    purge > 30 days  (AC5)

Already handled elsewhere (documented, not duplicated):
  - stripe_webhook_events:    billing.py::purge_old_stripe_events (90d, AC2)
  - search_sessions:          session_cleanup.py (stale 1h, old 7d)
  - pncp_raw_bids:            pg_cron purge_old_bids (400d)
  - search_results_store:     session_cleanup.py (expired TTL)
  - search_results_cache:     pg_cron cleanup-search-results-store (per-user cap)
  - analytics_events:         External (Mixpanel) — no local database table

Metrics:
  - data_purge_rows_total{table}:     Counter per table
  - data_purge_bytes_freed:           Gauge of estimated total bytes freed
  - data_purge_duration_seconds:      Histogram of purge cycle duration
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from jobs.cron.canary import _is_cb_or_connection_error

logger = logging.getLogger(__name__)

# Retention policy constants (days)
RETENTION_TRIAL_EMAIL_LOG = 180   # AC3: purge > 180 days
RETENTION_MESSAGES = 365           # AC4: purge > 365 days
RETENTION_INGESTION_CHECKPOINTS = 30  # AC5: purge > 30 days

# Purge interval: run daily
PURGE_INTERVAL_SECONDS = 24 * 60 * 60


async def purge_trial_email_log() -> dict:
    """Purge trial_email_log rows older than RETENTION_TRIAL_EMAIL_LOG days.

    Returns dict with count of deleted rows and any error message.
    """
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_TRIAL_EMAIL_LOG)).isoformat()
        result = await sb_execute(
            sb.table("trial_email_log").delete().lt("sent_at", cutoff)
        )
        deleted = len(result.data) if result and result.data else 0
        logger.info(
            "GAP-005: Purged %d trial_email_log rows older than %d days (cutoff=%s)",
            deleted, RETENTION_TRIAL_EMAIL_LOG, cutoff,
        )
        return {"deleted": deleted, "table": "trial_email_log", "cutoff": cutoff}
    except Exception as e:
        if _is_cb_or_connection_error(e):
            logger.warning("GAP-005: trial_email_log purge skipped (Supabase unavailable): %s", e)
        else:
            logger.error("GAP-005: trial_email_log purge error: %s", e, exc_info=True)
        return {"deleted": 0, "table": "trial_email_log", "error": str(e)}


async def purge_messages() -> dict:
    """Purge messages rows older than RETENTION_MESSAGES days.

    Also purges conversations whose last_message_at is older than the cutoff.
    Conversations that still have recent messages are preserved.

    Uses a two-step approach:
      1. Delete old messages (created_at < cutoff)
      2. Delete conversations with last_message_at < cutoff
         (safe because messages trigger keeps last_message_at in sync)

    Returns dict with count of deleted rows and any error message.
    """
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_MESSAGES)).isoformat()

        # Step 1: Delete old messages
        result = await sb_execute(
            sb.table("messages").delete().lt("created_at", cutoff)
        )
        deleted_messages = len(result.data) if result and result.data else 0

        # Step 2: Delete conversations whose last message is older than cutoff.
        # The `last_message_at` is kept in sync by a trigger on messages insert,
        # so this safely removes conversations that have aged out entirely.
        conv_result = await sb_execute(
            sb.table("conversations").delete().lt("last_message_at", cutoff)
        )
        deleted_conversations = len(conv_result.data) if conv_result and conv_result.data else 0

        total = deleted_messages + deleted_conversations
        logger.info(
            "GAP-005: Purged %d messages + %d conversations older than %d days (cutoff=%s)",
            deleted_messages, deleted_conversations, RETENTION_MESSAGES, cutoff,
        )
        return {
            "table": "messages",
            "messages_deleted": deleted_messages,
            "conversations_deleted": deleted_conversations,
            "deleted": total,
            "cutoff": cutoff,
        }
    except Exception as e:
        if _is_cb_or_connection_error(e):
            logger.warning("GAP-005: messages purge skipped (Supabase unavailable): %s", e)
        else:
            logger.error("GAP-005: messages purge error: %s", e, exc_info=True)
        return {"deleted": 0, "table": "messages", "error": str(e)}


async def purge_ingestion_checkpoints() -> dict:
    """Purge completed/failed ingestion_checkpoints older than 30 days.

    Only deletes checkpoints with terminal status (completed, failed).
    Active/pending checkpoints are never purged.

    Returns dict with count of deleted rows and any error message.
    """
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_INGESTION_CHECKPOINTS)).isoformat()

        # Purge completed/failed checkpoints older than cutoff
        # completed_at is set when a checkpoint finishes; use it as the age metric.
        # For rows where completed_at is NULL, fall back to started_at.
        result = await sb_execute(
            sb.table("ingestion_checkpoints")
            .delete()
            .in_("status", ("completed", "failed"))
            .lt("completed_at", cutoff)
        )
        deleted = len(result.data) if result and result.data else 0

        # Also purge failed checkpoints that have no completed_at but old started_at
        result2 = await sb_execute(
            sb.table("ingestion_checkpoints")
            .delete()
            .in_("status", ("completed", "failed"))
            .is_("completed_at", "null")
            .lt("started_at", cutoff)
        )
        deleted2 = len(result2.data) if result2 and result2.data else 0
        total = deleted + deleted2

        logger.info(
            "GAP-005: Purged %d ingestion_checkpoints rows (completed_at) + %d (started_at fallback) "
            "older than %d days (cutoff=%s)",
            deleted, deleted2, RETENTION_INGESTION_CHECKPOINTS, cutoff,
        )
        return {
            "table": "ingestion_checkpoints",
            "deleted_completed_at": deleted,
            "deleted_started_at_fallback": deleted2,
            "deleted": total,
            "cutoff": cutoff,
        }
    except Exception as e:
        if _is_cb_or_connection_error(e):
            logger.warning("GAP-005: ingestion_checkpoints purge skipped (Supabase unavailable): %s", e)
        else:
            logger.error("GAP-005: ingestion_checkpoints purge error: %s", e, exc_info=True)
        return {"deleted": 0, "table": "ingestion_checkpoints", "error": str(e)}


async def run_data_retention_purge() -> dict:
    """Run all data retention purge steps and aggregate results.

    Each table is purged in its own try/except block so a failure in one
    table does not prevent the others from being cleaned.

    Returns a dict with per-table results and aggregated totals.
    """
    start_time = datetime.now(timezone.utc)
    logger.info("GAP-005: Starting data retention purge cycle")

    # Run purges
    trial_result = await purge_trial_email_log()
    messages_result = await purge_messages()
    checkpoints_result = await purge_ingestion_checkpoints()

    grand_total = (
        trial_result.get("deleted", 0)
        + messages_result.get("deleted", 0)
        + checkpoints_result.get("deleted", 0)
    )

    duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Report metrics
    try:
        from metrics import (
            DATA_PURGE_ROWS_TOTAL, DATA_PURGE_BYTES_FREED, DATA_PURGE_DURATION,
        )
        for tbl_result in (trial_result, messages_result, checkpoints_result):
            tbl = tbl_result.get("table", "unknown")
            deleted = tbl_result.get("deleted", 0)
            DATA_PURGE_ROWS_TOTAL.labels(table=tbl).inc(deleted)

        # Estimate bytes freed: assume ~2KB per row average
        estimated_bytes = grand_total * 2048
        DATA_PURGE_BYTES_FREED.set(estimated_bytes)
        DATA_PURGE_DURATION.observe(duration)
    except Exception:
        pass

    summary = {
        "trial_email_log": trial_result,
        "messages": messages_result,
        "ingestion_checkpoints": checkpoints_result,
        "total_rows_purged": grand_total,
        "duration_seconds": round(duration, 2),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "GAP-005: Purge cycle complete — %d total rows purged in %.2fs",
        grand_total, duration,
    )
    return summary


async def _data_retention_loop() -> None:
    """Background loop that runs data retention purge on a schedule.

    Runs immediately on startup, then every PURGE_INTERVAL_SECONDS.
    """
    try:
        result = await run_data_retention_purge()
        logger.info(
            "GAP-005: Initial data retention purge: %d rows purged",
            result["total_rows_purged"],
        )
    except Exception as e:
        if _is_cb_or_connection_error(e):
            logger.warning("GAP-005: Initial purge skipped (Supabase unavailable): %s", e)
        else:
            logger.error("GAP-005: Initial purge error: %s", e, exc_info=True)

    while True:
        try:
            await asyncio.sleep(PURGE_INTERVAL_SECONDS)
            result = await run_data_retention_purge()
            logger.info(
                "GAP-005: Scheduled purge cycle: %d rows purged",
                result["total_rows_purged"],
            )
        except asyncio.CancelledError:
            logger.info("GAP-005: Data retention task cancelled")
            break
        except Exception as e:
            if _is_cb_or_connection_error(e):
                logger.warning("GAP-005: Purge loop skipped (Supabase unavailable): %s", e)
            else:
                logger.error("GAP-005: Purge loop error: %s", e, exc_info=True)
            await asyncio.sleep(300)


async def start_data_retention_task() -> asyncio.Task:
    """Start the data retention background loop.

    Returns the asyncio.Task handle for lifecycle management.
    """
    task = asyncio.create_task(_data_retention_loop(), name="data_retention")
    logger.info(
        "GAP-005: Data retention task started (interval: %ds, trial_email: %dd, "
        "messages: %dd, checkpoints: %dd)",
        PURGE_INTERVAL_SECONDS,
        RETENTION_TRIAL_EMAIL_LOG,
        RETENTION_MESSAGES,
        RETENTION_INGESTION_CHECKPOINTS,
    )
    return task
