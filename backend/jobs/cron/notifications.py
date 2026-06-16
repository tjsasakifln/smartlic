"""jobs.cron.notifications — Facade: notification cron functions (Issue #1781).

All implementation has been moved to ``jobs.cron.notification_loops``. This
module re-exports constants, loop classes, and ``start_*_task`` wrappers for
backward compatibility.

Legacy private functions (``_alerts_loop``, ``_trial_sequence_loop``, etc.) and
their corresponding ``run_*`` methods are kept here as thin wrappers around the
new ``BaseCronLoop`` subclasses so that existing tests and imports continue to
work.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

# Re-export config values so tests that patch ``jobs.cron.notifications.<name>``
# continue to work (backward compat after Issue #1781).
from config import ALERTS_ENABLED, ALERTS_HOUR_UTC  # noqa: F401  re-exported for test patches

from jobs.cron.notification_loops import (
    AlertsLoop,
    TrialSequenceLoop,
    SupportSlaLoop,
    DailyVolumeLoop,
    SectorStatsLoop,
)

logger = logging.getLogger(__name__)

# ── Constants (re-exported) ───────────────────────────────────────────────

TRIAL_SEQUENCE_INTERVAL_SECONDS = 2 * 60 * 60
TRIAL_SEQUENCE_BATCH_SIZE = 50
ALERTS_LOCK_KEY = "smartlic:alerts:lock"
ALERTS_LOCK_TTL = 30 * 60
SECTOR_STATS_HOUR_UTC = 6
DAILY_VOLUME_HOUR_UTC = 7


# ── Timing helper ──────────────────────────────────────────────────────────

def _next_utc_hour(target_hour: int) -> float:
    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if now.hour >= target_hour:
        next_run += timedelta(days=1)
    return max(60.0, min((next_run - now).total_seconds(), 86400.0))


# ── Legacy run_* business functions (thin wrappers around loop.run_once()) ─

async def run_search_alerts() -> dict:
    # Check module-level ALERTS_ENABLED re-export so tests that patch
    # jobs.cron.notifications.ALERTS_ENABLED continue to work (Issue #1781).
    if not ALERTS_ENABLED:
        return {"status": "disabled"}
    return await AlertsLoop().run_once()


async def check_unanswered_messages() -> dict:
    return await SupportSlaLoop().run_once()


async def record_daily_volume() -> dict:
    return await DailyVolumeLoop().run_once()


# ── Legacy _*_loop functions (delegate to loop classes) ────────────────────

async def _alerts_loop() -> None:
    loop = AlertsLoop()
    await loop.start()


async def _trial_sequence_loop() -> None:
    loop = TrialSequenceLoop()
    await loop.start()


async def _support_sla_loop() -> None:
    loop = SupportSlaLoop()
    await loop.start()


async def _daily_volume_loop() -> None:
    loop = DailyVolumeLoop()
    await loop.start()


async def _sector_stats_loop() -> None:
    loop = SectorStatsLoop()
    await loop.start()


# ── start_*_task factories (called by task_registry on lifespan startup) ──

async def start_alerts_task() -> asyncio.Task:
    loop = AlertsLoop()
    task = asyncio.create_task(loop.start(), name="search_alerts")
    logger.info("STORY-315: Search alerts task started (daily at 08:00 BRT)")
    return task


async def start_trial_sequence_task() -> asyncio.Task:
    loop = TrialSequenceLoop()
    task = asyncio.create_task(loop.start(), name="trial_email_sequence")
    logger.info("STORY-310: Trial email sequence task started (daily at 08:00 BRT)")
    return task


async def start_support_sla_task() -> asyncio.Task:
    loop = SupportSlaLoop()
    task = asyncio.create_task(loop.start(), name="support_sla")
    logger.info("STORY-353: Support SLA check started (interval: 4h)")
    return task


async def start_daily_volume_task() -> asyncio.Task:
    loop = DailyVolumeLoop()
    task = asyncio.create_task(loop.start(), name="daily_volume")
    logger.info("STORY-358: Daily volume recording task started (daily at 07:00 UTC)")
    return task


async def start_sector_stats_task() -> asyncio.Task:
    loop = SectorStatsLoop()
    task = asyncio.create_task(loop.start(), name="sector_stats_refresh")
    logger.info("STORY-324: Sector stats refresh task started (daily at 06:00 UTC)")
    return task
