"""STORY-1.1 (EPIC-TD-2026Q2 P0): pg_cron + ARQ cron health monitor.

Monitors two cron layers:

  1. **pg_cron** — queries ``public.get_cron_health()`` (PostgreSQL native cron)
     and fires Sentry alerts for failed / stale scheduled jobs.

  2. **ARQ cron jobs** — checks ``loop:health:*`` Redis keys written by
     ``BaseCronLoop`` subclasses (Issue #1781 AC5.6) and ``arq:job-result:*``
     keys for pure ARQ schedules.

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


# ── ARQ cron job health checking (Issue #1781 AC5.6) ────────────────────────

# Known ARQ cron job function names that should be monitored.
# These are the function names registered in ``_worker_cron_jobs`` in
# ``jobs/queue/config.py``.
_ARQ_KNOWN_CRONS: list[str] = [
    "daily_digest_job",
    "email_alerts_job",
    "predictive_alert_job",
    "cron_monitoring_job",
    "founders_auto_disable_check",
    "gsc_sync_job",
    "aggregate_and_cleanup_network_events",
    "ingestion_full_crawl_job",
    "ingestion_incremental_job",
    "ingestion_purge_job",
    "contracts_full_crawl_job",
    "contracts_incremental_job",
    "enrich_entities_job",
    "enrich_municipios_job",
    "enrich_pncp_ibge_codes_job",
    "run_competitive_alert_detection",
    "run_competitive_alert_weekly_digest",
]

# How long an ARQ cron job can go without reporting health before being
# considered stale.  Daily jobs → 25h, weekly jobs → 8d, monthly → 35d.
_ARQ_STALE_HOURS: dict[str, float] = {
    "ingestion_full_crawl_job": 8 * 24,        # weekly-ish
    "contracts_full_crawl_job": 8 * 24,         # 3x/week
    "gsc_sync_job": 8 * 24,                     # weekly (sun)
    "aggregate_and_cleanup_network_events": 8 * 24,  # weekly (sun)
    "run_competitive_alert_weekly_digest": 8 * 24,   # weekly (mon)
    "enrich_entities_job": 3 * 24,              # daily-ish
    "enrich_municipios_job": 3 * 24,            # daily-ish
    "enrich_pncp_ibge_codes_job": 3 * 24,       # daily-ish
}
_LOOP_HEALTH_PREFIX = "loop:health:"


async def _check_arq_cron_health() -> list[dict[str, Any]]:
    """Check health of ARQ cron jobs via ``loop:health:*`` Redis keys.

    Iterates known ARQ cron job names and checks their last health report
    in Redis.  Falls back to scanning ``arq:job-result:*`` when a health
    key is missing.

    Returns:
        List of ``{jobname, reason, row}`` dicts for unhealthy jobs.
    """
    now = datetime.now(timezone.utc)
    redis = await _get_redis_for_health()
    if redis is None:
        return []

    problems: list[dict[str, Any]] = []
    for name in _ARQ_KNOWN_CRONS:
        try:
            health_data = await redis.hgetall(f"{_LOOP_HEALTH_PREFIX}{name}")
        except Exception:
            continue
        stale_hours = _ARQ_STALE_HOURS.get(name, 25.0)

        if health_data:
            problem = _evaluate_arq_health_key(name, health_data, now, stale_hours)
        else:
            problem = await _evaluate_arq_fallback(name, redis, now, stale_hours)

        if problem:
            problems.append(problem)

    return problems


async def _get_redis_for_health() -> Any | None:
    """Get Redis pool connection for ARQ health checking.

    Returns the Redis client, or None if unavailable.
    """
    try:
        from redis_pool import get_redis_pool
        redis = await get_redis_pool()
        if not redis:
            logger.warning("[ArqCronMonitor] Redis unavailable — skipping ARQ health check")
            return None
        return redis
    except Exception:
        return None


def _evaluate_arq_health_key(
    name: str, health_data: dict, now: datetime, stale_hours: float,
) -> dict[str, Any] | None:
    """Evaluate a single ARQ cron job from its ``loop:health:*`` Redis hash.

    Returns a problem dict if the job is unhealthy, or None if healthy.
    """
    last_status = _decode_redis(health_data.get(b"last_status") or health_data.get("last_status"), "unknown")
    last_error = _decode_redis(health_data.get(b"last_error") or health_data.get("last_error"), "")
    last_str = _decode_redis(health_data.get(b"last_run_at") or health_data.get("last_run_at"), "")

    if last_status == "error":
        return {
            "jobname": name,
            "reason": f"arq_last_status=error: {last_error[:200]}",
            "row": {"jobname": name, "last_status": last_status, "last_error": last_error},
        }

    if last_str:
        try:
            last_dt = datetime.fromisoformat(last_str.replace("Z", "+00:00"))
            delta_h = (now - last_dt).total_seconds() / 3600.0
            if delta_h > stale_hours:
                return {
                    "jobname": name,
                    "reason": f"arq_stale ({delta_h:.1f}h > {stale_hours}h)",
                    "row": {"jobname": name, "last_status": last_status, "last_run_at": last_str},
                }
        except (ValueError, TypeError):
            pass
    return None


async def _evaluate_arq_fallback(
    name: str, redis: Any, now: datetime, stale_hours: float,
) -> dict[str, Any] | None:
    """Fallback check when a health key is missing: scan ``arq:job-result:*``.

    Returns a problem dict if the job is unhealthy or has no recent result,
    or None if the job is healthy.
    """
    try:
        cursor, keys = await redis.scan(
            cursor=0, match="arq:job-result:*", count=500,
        )
        found = False
        for key in keys:
            result_data = await redis.hgetall(key)
            if result_data and result_data.get(b"function") == name.encode():
                found = True
                finish_ts = result_data.get(b"finish_time") or result_data.get(b"job_try")
                if finish_ts:
                    try:
                        finish_dt = datetime.fromtimestamp(float(finish_ts), tz=timezone.utc)
                        delta_h = (now - finish_dt).total_seconds() / 3600.0
                        if delta_h <= stale_hours:
                            return None  # healthy
                        # Found but stale
                        return {
                            "jobname": name,
                            "reason": f"arq_stale ({delta_h:.1f}h > {stale_hours}h)",
                            "row": {"jobname": name, "last_status": "stale"},
                        }
                    except (ValueError, TypeError):
                        continue
                break
        if not found:
            return {
                "jobname": name,
                "reason": "arq_no_recent_result",
                "row": {"jobname": name, "last_status": "no_data"},
            }
        return None
    except Exception:
        return {
            "jobname": name,
            "reason": "arq_health_scan_error",
            "row": {"jobname": name, "last_status": "error"},
        }


def _decode_redis(value: Any, default: str = "") -> str:
    """Decode bytes to str; return default for None/empty."""
    if value is None:
        return default
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


async def run_cron_monitor() -> dict:
    """Core monitoring logic: query get_cron_health() + ARQ health and fire alerts.

    Public interface for tests and direct invocation. Returns::

        {"status": "ok", "jobs_checked": N, "alerts_fired": M}
        {"status": "error", "jobs_checked": 0, "alerts_fired": 0, "error": "..."}
    """
    problems: list[dict[str, Any]] = []
    pg_rows: list[dict[str, Any]] = []
    pg_cron_error: str | None = None

    try:
        sb = get_supabase()
        result = await sb_execute_direct(sb.rpc("get_cron_health"))
        pg_rows = getattr(result, "data", None) or []
    except Exception as exc:
        pg_cron_error = str(exc)
        logger.error("[CronMonitor] pg_cron RPC failed: %s", exc, exc_info=True)
        problems.append({"jobname": "_pg_cron_rpc", "reason": f"rpc_error:{type(exc).__name__}", "row": {"error": str(exc)}})

    # Evaluate pg_cron jobs
    problems.extend(evaluate_jobs(pg_rows))

    # Evaluate ARQ cron jobs (Issue #1781 AC5.6)
    try:
        arq_problems = await _check_arq_cron_health()
        problems.extend(arq_problems)
    except Exception as exc:
        logger.error("[CronMonitor] ARQ health check failed: %s", exc, exc_info=True)
        problems.append({"jobname": "_arq_health", "reason": f"check_error:{type(exc).__name__}", "row": {"error": str(exc)}})

    for p in problems:
        _fire_sentry_alert(p["jobname"], p["reason"], p["row"])

    logger.info(
        "[CronMonitor] Evaluated %d pg_cron + %d ARQ jobs, %d problems",
        len(pg_rows),
        len(_ARQ_KNOWN_CRONS),
        len(problems),
    )
    if problems:
        logger.warning(
            "[CronMonitor] Problem jobs: %s",
            [{"jobname": p["jobname"], "reason": p["reason"]} for p in problems],
        )

    # backward compat: when pg_cron RPC fails, return error status with error message
    status = "error" if pg_cron_error else "ok"
    result: dict[str, Any] = {
        "status": status,
        "jobs_checked": len(pg_rows),
        "arq_jobs_checked": len(_ARQ_KNOWN_CRONS),
        "alerts_fired": len(problems),
    }
    if pg_cron_error:
        result["error"] = pg_cron_error
    return result


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

    Checks both pg_cron health (``get_cron_health()`` RPC) and ARQ cron
    job health (``loop:health:*`` Redis keys per Issue #1781 AC5.6).

    Returns a summary dict so the ARQ result store surfaces health without
    requiring the Sentry/dashboard side-channel.
    """
    start = time.monotonic()
    problems: list[dict[str, Any]] = []
    pg_rows: list[dict[str, Any]] = []
    pg_cron_error: str | None = None

    try:
        sb = get_supabase()
        result = await sb_execute_direct(sb.rpc("get_cron_health"))
        pg_rows = getattr(result, "data", None) or []
    except Exception as exc:
        pg_cron_error = str(exc)
        logger.error("[CronMonitor] pg_cron RPC failed: %s", exc, exc_info=True)
        _fire_sentry_alert("_monitor_self", f"rpc_error:{type(exc).__name__}", {"error": str(exc)})
        # Don't add _pg_cron_rpc to problems — _monitor_self covers it (avoids double-fire).

    try:
        arq_problems = await _check_arq_cron_health()
        problems.extend(arq_problems)
    except Exception as exc:
        logger.error("[CronMonitor] ARQ health check failed: %s", exc, exc_info=True)
        problems.append({"jobname": "_arq_health", "reason": f"check_error:{type(exc).__name__}", "row": {"error": str(exc)}})

    if not pg_cron_error:
        problems.extend(evaluate_jobs(pg_rows))

    for p in problems:
        _fire_sentry_alert(p["jobname"], p["reason"], p["row"])

    duration_s = round(time.monotonic() - start, 2)
    problem_names = [p["jobname"] for p in problems]
    if problems:
        logger.warning(
            "[CronMonitor] Evaluated %d jobs (pg_cron=%d, arq=%d), %d problems in %ss: %s",
            len(pg_rows), len(pg_rows), len(_ARQ_KNOWN_CRONS),
            len(problems), duration_s, problem_names,
        )
    else:
        logger.info(
            "[CronMonitor] Evaluated %d jobs (pg_cron=%d, arq=%d), 0 problems in %ss",
            len(pg_rows), len(pg_rows), len(_ARQ_KNOWN_CRONS), duration_s,
        )
    status = "failed" if pg_cron_error else "completed"
    result: dict[str, Any] = {
        "status": status,
        "evaluated": len(pg_rows),
        "arq_jobs_evaluated": len(_ARQ_KNOWN_CRONS),
        "problems": len(problems),
        "problem_jobs": problem_names,
        "duration_s": duration_s,
    }
    if pg_cron_error:
        result["error"] = pg_cron_error
    return result
