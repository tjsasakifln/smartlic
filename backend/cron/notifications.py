"""Notification and operations cron jobs: alerts, trial emails, support SLA,
daily volume, sector stats, session cleanup, and results cleanup."""

import asyncio
import logging
import os
import time as _time
from datetime import datetime, timedelta, timezone

from config import ALERTS_ENABLED, ALERTS_HOUR_UTC
from cron._loop import (
    acquire_redis_lock, release_redis_lock,
    cron_loop, daily_loop, is_cb_or_connection_error,
)

logger = logging.getLogger(__name__)

# Constants
SESSION_STALE_HOURS = 1
SESSION_OLD_DAYS = 7
CLEANUP_INTERVAL_SECONDS = 6 * 60 * 60
TRIAL_SEQUENCE_INTERVAL_SECONDS = 24 * 60 * 60
TRIAL_SEQUENCE_BATCH_SIZE = 50
RESULTS_CLEANUP_INTERVAL_SECONDS = 6 * 60 * 60
ALERTS_LOCK_KEY = "smartlic:alerts:lock"
ALERTS_LOCK_TTL = 30 * 60
SECTOR_STATS_INTERVAL_SECONDS = 24 * 60 * 60
SECTOR_STATS_HOUR_UTC = 6
DAILY_VOLUME_INTERVAL_SECONDS = 24 * 60 * 60
DAILY_VOLUME_HOUR_UTC = 7


# ---------------------------------------------------------------------------
# Session cleanup (CRIT-011)
# ---------------------------------------------------------------------------

async def cleanup_stale_sessions() -> dict:
    """CRIT-011 AC7: Clean up stale search sessions."""
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        now = datetime.now(timezone.utc)
        stale_cutoff = (now - timedelta(hours=SESSION_STALE_HOURS)).isoformat()
        old_cutoff = (now - timedelta(days=SESSION_OLD_DAYS)).isoformat()

        try:
            marked_stale = 0
            for status in ("in_progress", "created", "processing"):
                r = await sb_execute(
                    sb.table("search_sessions")
                    .update({"status": "timed_out", "error_message": "Session timed out (cleanup)",
                             "error_code": "session_timeout", "completed_at": now.isoformat()})
                    .eq("status", status).lt("created_at", stale_cutoff)
                )
                marked_stale += len(r.data) if r.data else 0

            deleted_old = 0
            for terminal_status in ("failed", "timeout", "timed_out"):
                r = await sb_execute(
                    sb.table("search_sessions").delete().eq("status", terminal_status).lt("created_at", old_cutoff)
                )
                deleted_old += len(r.data) if r.data else 0

            return {"marked_stale": marked_stale, "deleted_old": deleted_old}
        except Exception as col_err:
            if "42703" in str(col_err):
                logger.warning("Session cleanup: status column not found, fallback to created_at-only")
                r = await sb_execute(sb.table("search_sessions").delete().lt("created_at", old_cutoff))
                return {"marked_stale": 0, "deleted_old": len(r.data) if r.data else 0}
            raise
    except Exception as e:
        logger.error("Session cleanup error: %s", e, exc_info=True)
        return {"marked_stale": 0, "deleted_old": 0, "error": str(e)}


async def start_session_cleanup_task() -> asyncio.Task:
    async def _loop():
        try:
            result = await cleanup_stale_sessions()
            logger.info("Session cleanup (startup): marked %d stale, deleted %d old", result["marked_stale"], result["deleted_old"])
        except Exception as e:
            if is_cb_or_connection_error(e):
                logger.warning("Session cleanup skipped on startup (Supabase unavailable): %s", e)
            else:
                logger.error("Session cleanup error on startup: %s", e, exc_info=True)
        await cron_loop("Session cleanup", cleanup_stale_sessions, CLEANUP_INTERVAL_SECONDS, error_retry_seconds=60)

    task = asyncio.create_task(_loop(), name="session_cleanup")
    logger.info("Session cleanup background task started (interval: 6h)")
    return task


# ---------------------------------------------------------------------------
# Search alerts (STORY-315)
# ---------------------------------------------------------------------------

async def run_search_alerts() -> dict:
    """Execute a single search alerts run with lock protection."""
    if not ALERTS_ENABLED:
        return {"status": "disabled"}

    lock_acquired = await acquire_redis_lock(ALERTS_LOCK_KEY, ALERTS_LOCK_TTL)
    if not lock_acquired:
        logger.info("STORY-315: Alerts skipped — lock already held")
        return {"status": "skipped", "reason": "lock_held"}

    try:
        from services.alert_matcher import match_alerts, finalize_matched_alert
        from templates.emails.alert_digest import render_alert_digest_email, get_alert_digest_subject
        from routes.alerts import get_alert_unsubscribe_url
        from email_service import send_email_async
        from metrics import ALERTS_PROCESSED, ALERTS_ITEMS_MATCHED, ALERTS_EMAILS_SENT, ALERTS_PROCESSING_DURATION

        start = _time.time()
        result = await match_alerts(max_alerts=100, batch_size=10)

        emails_sent = 0
        for payload in result.get("payloads", []):
            try:
                items = payload.get("new_items", [])
                if not items:
                    continue
                alert_id = payload["alert_id"]
                unsubscribe_url = get_alert_unsubscribe_url(alert_id)
                alert_name = payload.get("alert_name", "suas licitacoes")

                html = render_alert_digest_email(
                    user_name=payload["full_name"], alert_name=alert_name,
                    opportunities=items[:20], total_count=len(items), unsubscribe_url=unsubscribe_url,
                )
                send_email_async(
                    to=payload["email"], subject=get_alert_digest_subject(len(items), alert_name),
                    html=html,
                    headers={"List-Unsubscribe": f"<{unsubscribe_url}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
                    tags=[{"name": "category", "value": "alert_digest"}, {"name": "alert_id", "value": alert_id[:8]}],
                )
                await finalize_matched_alert(alert_id, [item["id"] for item in items if item.get("id")])
                emails_sent += 1
                ALERTS_EMAILS_SENT.labels(mode="individual").inc()
                ALERTS_ITEMS_MATCHED.inc(len(items))
            except Exception as e:
                logger.error("STORY-315: Failed to send alert email for %s: %s", payload.get("alert_id", "?")[:8], e)

        ALERTS_PROCESSED.labels(outcome="matched").inc(result.get("matched", 0))
        ALERTS_PROCESSED.labels(outcome="skipped").inc(result.get("skipped", 0))
        ALERTS_PROCESSED.labels(outcome="error").inc(result.get("errors", 0))

        duration = _time.time() - start
        ALERTS_PROCESSING_DURATION.observe(duration)
        result["emails_sent"] = emails_sent
        result["duration_s"] = round(duration, 2)

        logger.info("STORY-315: Alert cycle complete — matched=%d, emails=%d, skipped=%d, errors=%d, duration=%.1fs",
                     result.get("matched", 0), emails_sent, result.get("skipped", 0), result.get("errors", 0), duration)
        return result
    finally:
        await release_redis_lock(ALERTS_LOCK_KEY)


async def _alerts_loop() -> None:
    """STORY-315 AC8: Run search alerts daily at configured hour. Exposed for tests."""
    await daily_loop("STORY-315 alerts", run_search_alerts, ALERTS_HOUR_UTC)


async def start_alerts_task() -> asyncio.Task:
    task = asyncio.create_task(_alerts_loop(), name="search_alerts")
    logger.info("STORY-315: Search alerts task started (daily at 08:00 BRT)")
    return task


# ---------------------------------------------------------------------------
# Trial email sequence — DEPRECATED (CRIT-044)
# Canonical implementation moved to jobs/cron/notifications.py to eliminate
# dual-cron conflict. This legacy stub is kept for backward compat only.
# ---------------------------------------------------------------------------

# start_trial_sequence_task removed — use jobs.cron.notifications instead


# ---------------------------------------------------------------------------
# Sector stats refresh (STORY-324)
# ---------------------------------------------------------------------------

async def start_sector_stats_task() -> asyncio.Task:
    async def _refresh():
        from routes.sectors_public import refresh_all_sector_stats
        refreshed = await refresh_all_sector_stats()
        return {"refreshed": refreshed}

    task = asyncio.create_task(
        daily_loop("STORY-324 sector stats", _refresh, SECTOR_STATS_HOUR_UTC, error_retry_seconds=600),
        name="sector_stats_refresh",
    )
    logger.info("STORY-324: Sector stats refresh task started (daily at 06:00 UTC)")
    return task


# ---------------------------------------------------------------------------
# Support SLA (STORY-353)
# ---------------------------------------------------------------------------

async def check_unanswered_messages() -> dict:
    """STORY-353 AC3+AC4: Check for unanswered support messages."""
    from config import MESSAGES_ENABLED
    if not MESSAGES_ENABLED:
        return {"checked": 0, "breached": 0, "alerted": 0, "disabled": True}

    try:
        from supabase_client import get_supabase, sb_execute
        from business_hours import calculate_business_hours
        from config import SUPPORT_SLA_ALERT_THRESHOLD_HOURS
        from metrics import SUPPORT_PENDING_MESSAGES

        sb = get_supabase()
        now = datetime.now(timezone.utc)

        result = await sb_execute(
            sb.table("conversations").select("id, user_id, subject, category, created_at")
            .is_("first_response_at", "null").neq("status", "resolvido").order("created_at", desc=False)
        )
        conversations = result.data or []
        SUPPORT_PENDING_MESSAGES.set(len(conversations))

        if not conversations:
            return {"checked": 0, "breached": 0, "alerted": 0}

        breached = []
        for conv in conversations:
            from dateutil.parser import isoparse
            created_at = isoparse(conv["created_at"])
            elapsed = calculate_business_hours(created_at, now)
            if elapsed >= SUPPORT_SLA_ALERT_THRESHOLD_HOURS:
                breached.append({"id": conv["id"], "subject": conv["subject"],
                                "category": conv["category"], "elapsed_hours": elapsed, "created_at": conv["created_at"]})

        alerted = 0
        if breached:
            admin_email = os.getenv("ADMIN_EMAIL", "tiago.sasaki@gmail.com")
            try:
                from email_service import send_email_async
                items_html = "".join(
                    f"<tr><td>{b['subject']}</td><td>{b['category']}</td>"
                    f"<td>{b['elapsed_hours']:.1f}h</td><td>{b['created_at'][:16]}</td></tr>"
                    for b in breached
                )
                html = f"""
                <h2>Alerta de SLA de Suporte</h2>
                <p>{len(breached)} mensagem(ns) sem resposta excederam {SUPPORT_SLA_ALERT_THRESHOLD_HOURS}h uteis.</p>
                <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
                    <tr style="background:#f0f0f0;"><th>Assunto</th><th>Categoria</th><th>Horas uteis</th><th>Criada em</th></tr>
                    {items_html}
                </table>
                <p>Acesse <a href="https://smartlic.tech/mensagens">SmartLic Mensagens</a> para responder.</p>
                """
                send_email_async(to=admin_email, subject=f"[SLA] {len(breached)} mensagem(ns) sem resposta > {SUPPORT_SLA_ALERT_THRESHOLD_HOURS}h",
                                html=html, tags=[{"name": "category", "value": "sla_alert"}])
                alerted = len(breached)
                logger.warning("STORY-353 SLA alert: %d breached, email sent to %s", len(breached), admin_email)
            except Exception as e:
                logger.error("STORY-353: Failed to send SLA alert email: %s", e)

        logger.info("STORY-353 SLA check: checked=%d, breached=%d, alerted=%d", len(conversations), len(breached), alerted)
        return {"checked": len(conversations), "breached": len(breached), "alerted": alerted}
    except Exception as e:
        if is_cb_or_connection_error(e):
            logger.warning("STORY-353: Support SLA check skipped: %s", e)
        else:
            logger.error("STORY-353: Support SLA check error: %s", e, exc_info=True)
        return {"checked": 0, "breached": 0, "alerted": 0, "error": str(e)}


async def start_support_sla_task() -> asyncio.Task:
    from config import SUPPORT_SLA_CHECK_INTERVAL_SECONDS
    task = asyncio.create_task(
        cron_loop("STORY-353 SLA", check_unanswered_messages, SUPPORT_SLA_CHECK_INTERVAL_SECONDS, initial_delay=60),
        name="support_sla",
    )
    logger.info("STORY-353: Support SLA check started (interval: 4h)")
    return task


# ---------------------------------------------------------------------------
# Daily volume recording (STORY-358)
# ---------------------------------------------------------------------------

async def record_daily_volume() -> dict:
    """STORY-358 AC2: Record count of bids processed in the last 24 hours."""
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        now = datetime.now(timezone.utc)
        yesterday = (now - timedelta(hours=24)).isoformat()

        result = await sb_execute(
            sb.table("search_sessions").select("total_raw")
            .gte("created_at", yesterday).in_("status", ["completed", "completed_partial"])
        )
        sessions = result.data or []
        total_bids = sum(s.get("total_raw") or 0 for s in sessions)
        logger.info("STORY-358 daily volume: %d bids across %d sessions in last 24h", total_bids, len(sessions))
        return {"total_bids_24h": total_bids, "session_count": len(sessions), "recorded_at": now.isoformat()}
    except Exception as e:
        if is_cb_or_connection_error(e):
            logger.warning("STORY-358: Daily volume skipped: %s", e)
        else:
            logger.error("STORY-358: Daily volume error: %s", e, exc_info=True)
        return {"total_bids_24h": 0, "session_count": 0, "error": str(e)}


async def start_daily_volume_task() -> asyncio.Task:
    task = asyncio.create_task(
        daily_loop("STORY-358 daily volume", record_daily_volume, DAILY_VOLUME_HOUR_UTC, error_retry_seconds=600),
        name="daily_volume",
    )
    logger.info("STORY-358: Daily volume recording task started (daily at 07:00 UTC)")
    return task


# ---------------------------------------------------------------------------
# Expired results cleanup (STORY-362)
# ---------------------------------------------------------------------------

async def cleanup_expired_results() -> dict:
    """STORY-362 AC7: Delete expired search results from Supabase L3."""
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        now = datetime.now(timezone.utc).isoformat()
        result = await sb_execute(sb.table("search_results_store").delete().lt("expires_at", now))
        deleted = len(result.data) if result and result.data else 0
        logger.info("STORY-362: Cleaned up %d expired search results", deleted)
        return {"deleted": deleted, "cleaned_at": now}
    except Exception as e:
        if is_cb_or_connection_error(e):
            logger.warning("STORY-362: Results cleanup skipped: %s", e)
        else:
            logger.error("STORY-362: Results cleanup error: %s", e, exc_info=True)
        return {"deleted": 0, "error": str(e)}


async def start_results_cleanup_task() -> asyncio.Task:
    task = asyncio.create_task(
        cron_loop("STORY-362 results cleanup", cleanup_expired_results, RESULTS_CLEANUP_INTERVAL_SECONDS),
        name="results_cleanup",
    )
    logger.info("STORY-362: Expired results cleanup task started (interval: 6h)")
    return task
