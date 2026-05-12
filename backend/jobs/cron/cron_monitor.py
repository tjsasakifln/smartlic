"""STORY-1.1 (EPIC-TD-2026Q2 P0): pg_cron health monitor.

Hourly ARQ cron that queries ``public.get_cron_health()`` and raises a
Sentry alert for any scheduled job that either:

  * has status = 'failed' on its most recent run, or
  * has not produced a successful run for more than ``STALE_AFTER_HOURS``
    hours (default 25h — one-day window + 1h grace).

Dedup: ``sentry_sdk.push_scope`` + ``fingerprint=['cron_job', jobname]``
prevents spam when a job fails repeatedly for the same reason.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterable

from supabase_client import get_supabase, sb_execute_direct

logger = logging.getLogger(__name__)

# Stale threshold: a daily cron that has not succeeded in >25h is suspect.
STALE_AFTER_HOURS = 25

# Schedule-aware thresholds for non-daily cron jobs.
# The cron_job_health view retains a 7-day window of run_details, so weekly
# and monthly jobs need proportionally longer windows to avoid false positives.
_WEEKLY_STALE_HOURS = 8 * 24       # ~weekly + 1 day grace
_MONTHLY_STALE_HOURS = 35 * 24     # ~monthly + grace

# Run monitor every hour (3600s). Override via CRON_MONITOR_INTERVAL_S env var.
CRON_MONITOR_INTERVAL_SECONDS = 3600


def _parse_ts(value: Any) -> datetime | None:
    """Accept str / datetime / None and return a tz-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _is_stale(last_run_at: datetime | None, now: datetime) -> bool:
    if last_run_at is None:
        return True
    delta_hours = (now - last_run_at).total_seconds() / 3600.0
    return delta_hours > STALE_AFTER_HOURS


def _fire_sentry_alert(jobname: str, reason: str, row: dict[str, Any]) -> None:
    """Alias for _emit_sentry_alert — public name used in tests and run_cron_monitor."""
    _emit_sentry_alert(jobname, reason, row)


def _emit_sentry_alert(jobname: str, reason: str, row: dict[str, Any]) -> None:
    """Fire a deduplicated Sentry message for a failing / stale cron job."""
    try:
        import sentry_sdk
    except Exception:
        return

    try:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("cron_job", jobname)
            scope.set_tag("cron_job.reason", reason)
            scope.set_extra("row", row)
            # Dedup across runs so one bad job doesn't flood the issue list.
            scope.fingerprint = ["cron_job", jobname, reason]
            sentry_sdk.capture_message(
                f"[pg_cron] {jobname} — {reason}",
                level="error",
            )
    except Exception as exc:
        logger.warning("Failed to emit Sentry alert for %s: %s", jobname, exc)


def _compute_stale_threshold_hours(schedule: str | None) -> float:
    """Return a stale threshold proportional to the cron schedule interval.

    Defaults to ``STALE_AFTER_HOURS`` (25h) for daily or more-frequent
    schedules.  Returns larger thresholds for weekly and monthly cron jobs so
    that the monitor does not fire false-positive ``stale`` alerts between
    intended runs.

    Recognised patterns (all others fall back to the default):
    * ``dom != '*'`` (specific day-of-month) → monthly
    * ``dom startswith '*/'`` (every N days) → N days
    * ``dow != '*'`` (specific day-of-week) → weekly
    * ``dow startswith '*/'`` (every N weeks) → N weeks
    """
    if not schedule:
        return STALE_AFTER_HOURS

    parts = schedule.strip().split()
    if len(parts) != 5:
        return STALE_AFTER_HOURS

    _minute, _hour, dom, _month, dow = parts

    # Specific day-of-month (e.g. ``0 2 1 * *`` → 1st of month).
    if dom != "*" and not dom.startswith("*/") and "," not in dom:
        return _MONTHLY_STALE_HOURS

    # Every-N-days (e.g. ``0 2 */3 * *``).
    if dom.startswith("*/"):
        try:
            n = int(dom[2:])
            return float((n + 1) * 24)
        except ValueError:
            pass

    # Specific day-of-week (e.g. ``30 6 * * 0`` → Sundays only).
    if dow != "*" and not dow.startswith("*/") and "," not in dow:
        return _WEEKLY_STALE_HOURS

    # Every-N-weeks (e.g. ``30 6 * * */2``).
    if dow.startswith("*/"):
        try:
            n = int(dow[2:])
            return float((n * 7 + 1) * 24)
        except ValueError:
            pass

    return STALE_AFTER_HOURS


def evaluate_jobs(rows: Iterable[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Return a list of ``{jobname, reason, row}`` entries for offending jobs.

    Pure function; extracted so that tests can exercise the decision logic
    without touching Supabase, Sentry or the ARQ runtime.
    """
    current = now or datetime.now(timezone.utc)
    problems: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        jobname = row.get("jobname") or "<unknown>"

        # Skip intentionally disabled jobs (active = False).
        active = row.get("active")
        if active is False:
            continue

        last_status = (row.get("last_status") or "").lower()
        last_run_at = _parse_ts(row.get("last_run_at"))

        if last_status == "failed":
            problems.append({"jobname": jobname, "reason": "last_status=failed", "row": row})
            continue

        # Schedule-aware stale threshold prevents false positives for
        # weekly / monthly jobs (e.g. bloat-check-pncp-raw-bids runs
        # Sundays only; cleanup-trial-email-log runs on the 1st of month).
        stale_hours = _compute_stale_threshold_hours(row.get("schedule"))
        if last_run_at is None:
            # No runs in the 7-day health view window.
            # For daily+ jobs = definitely stale.  For longer-interval
            # jobs the 7-day window may simply not contain a run that
            # happened within the expected interval → skip to avoid
            # false-positive alerts.
            if stale_hours <= STALE_AFTER_HOURS:
                problems.append({"jobname": jobname, "reason": "stale", "row": row})
            continue

        delta_hours = (current - last_run_at).total_seconds() / 3600.0
        if delta_hours > stale_hours:
            problems.append({"jobname": jobname, "reason": "stale", "row": row})

    return problems


async def run_cron_monitor() -> dict:
    """Core monitoring logic: query get_cron_health() and fire alerts for problems.

    Public interface for tests and direct invocation. Returns::

        {"status": "ok", "jobs_checked": N, "alerts_fired": M}
        {"status": "error", "jobs_checked": 0, "alerts_fired": 0, "error": "..."}
    """
    try:
        sb = get_supabase()
        result = await sb_execute_direct(sb.rpc("get_cron_health"))
        rows = getattr(result, "data", None) or []
    except Exception as exc:
        logger.error("[CronMonitor] RPC failed: %s", exc, exc_info=True)
        return {"status": "error", "jobs_checked": 0, "alerts_fired": 0, "error": str(exc)}

    problems = evaluate_jobs(rows)
    for p in problems:
        _fire_sentry_alert(p["jobname"], p["reason"], p["row"])

    logger.info(
        "[CronMonitor] Evaluated %d jobs, %d problems",
        len(rows),
        len(problems),
    )
    if problems:
        logger.warning(
            "[CronMonitor] Problem jobs: %s",
            [{"jobname": p["jobname"], "reason": p["reason"]} for p in problems],
        )
    return {
        "status": "ok",
        "jobs_checked": len(rows),
        "alerts_fired": len(problems),
    }


async def _cron_monitor_loop() -> None:
    """Asyncio task loop — runs run_cron_monitor() hourly."""
    import os
    interval = int(os.getenv("CRON_MONITOR_INTERVAL_S", str(CRON_MONITOR_INTERVAL_SECONDS)))
    await asyncio.sleep(60)  # Short initial delay to let startup settle
    while True:
        try:
            await run_cron_monitor()
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("[CronMonitor] Task cancelled")
            break
        except Exception as exc:
            logger.error("[CronMonitor] Loop error: %s", exc, exc_info=True)
            await asyncio.sleep(300)  # Back-off on error


async def start_cron_monitor_task() -> asyncio.Task:
    """Create and return the cron monitor asyncio Task."""
    task = asyncio.create_task(_cron_monitor_loop(), name="cron_monitor")
    logger.info("[CronMonitor] Hourly monitor task started (interval: %ds)", CRON_MONITOR_INTERVAL_SECONDS)
    return task


async def cron_monitoring_job(ctx: dict) -> dict:
    """ARQ cron handler: scheduled hourly (minute=0).

    Returns a summary dict so the ARQ result store surfaces health without
    requiring the Sentry/dashboard side-channel.
    """
    start = time.monotonic()
    try:
        sb = get_supabase()
        result = await sb_execute_direct(sb.rpc("get_cron_health"))
        rows = getattr(result, "data", None) or []
    except Exception as exc:
        duration_s = round(time.monotonic() - start, 2)
        logger.error("[CronMonitor] RPC failed: %s", exc, exc_info=True)
        # Surface the monitoring failure itself so Sentry doesn't stay quiet
        # while the underlying signal is blind.
        _fire_sentry_alert("_monitor_self", f"rpc_error:{type(exc).__name__}", {"error": str(exc)})
        return {"status": "failed", "error": str(exc), "duration_s": duration_s}

    problems = evaluate_jobs(rows)
    for p in problems:
        _fire_sentry_alert(p["jobname"], p["reason"], p["row"])

    duration_s = round(time.monotonic() - start, 2)
    problem_names = [p["jobname"] for p in problems]
    if problems:
        logger.warning(
            "[CronMonitor] Evaluated %d jobs, %d problems in %ss: %s",
            len(rows),
            len(problems),
            duration_s,
            problem_names,
        )
    else:
        logger.info(
            "[CronMonitor] Evaluated %d jobs, 0 problems in %ss",
            len(rows),
            duration_s,
        )
    return {
        "status": "completed",
        "evaluated": len(rows),
        "problems": len(problems),
        "problem_jobs": problem_names,
        "duration_s": duration_s,
    }
