"""jobs.cron.registry — CronLoopRegistry: unified lifecycle for all cron loops.

Usage::

    from jobs.cron.registry import CronLoopRegistry
    from jobs.cron.billing_loops.reconciliation import ReconciliationLoop

    registry = CronLoopRegistry()
    registry.register(ReconciliationLoop())
    registry.register(PreDunningLoop())
    # ...
    await registry.start_all()
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)


class CronLoopRegistry:
    """Central registry for all BaseCronLoop instances.

    Supports registering both lifespan loops (BaseCronLoop subclasses) and
    health-check-only entries for ARQ cron jobs that run outside the asyncio
    lifespan but should still be monitored by cron_monitor.
    """

    def __init__(self) -> None:
        self._loops: dict[str, BaseCronLoop] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def register(self, loop: BaseCronLoop) -> None:
        """Register a BaseCronLoop instance.

        The loop will be started as an ``asyncio.Task`` when ``start_all()``
        is called.
        """
        if loop.name in self._loops:
            logger.warning(
                "CronLoopRegistry: duplicate registration for '%s' — overwriting",
                loop.name,
            )
        self._loops[loop.name] = loop

    def register_health_only(self, name: str) -> None:
        """Register a health-check placeholder for an externally-managed loop.

        Use this for ARQ cron jobs that are scheduled by the ARQ scheduler
        (``jobs/queue/config.py``) rather than the asyncio lifespan.  The
        registry will report their health from the ``loop:health:<name>``
        Redis hash without attempting to start them.
        """
        if name not in self._loops:
            # Dummy entry so get_health() and health report work
            class _ExternalLoop(BaseCronLoop):
                name = name
                interval_seconds = 86400

                async def run_once(self) -> dict:
                    return {"status": "external"}

            self._loops[name] = _ExternalLoop()

    async def start_all(self) -> dict[str, bool]:
        """Start all registered loops as asyncio tasks.

        Returns:
            Dict mapping loop name to success (True) or failure (False).
        """
        results: dict[str, bool] = {}
        for loop_name, loop in self._loops.items():
            if loop_name in self._tasks and not self._tasks[loop_name].done():
                logger.debug(
                    "CronLoopRegistry: '%s' already running, skipping", loop_name,
                )
                results[loop_name] = True
                continue
            try:
                self._tasks[loop_name] = asyncio.create_task(
                    loop.start(), name=f"cron_{loop_name}",
                )
                results[loop_name] = True
                logger.info("CronLoopRegistry: started '%s'", loop_name)
            except Exception as e:
                results[loop_name] = False
                logger.error(
                    "CronLoopRegistry: failed to start '%s': %s", loop_name, e,
                )

        started = sum(1 for v in results.values() if v)
        logger.info(
            "CronLoopRegistry: %d/%d loops started", started, len(results),
        )
        return results

    async def stop_all(self, timeout: float = 10.0) -> dict[str, str]:
        """Cancel all running loop tasks and wait for completion."""
        results: dict[str, str] = {}
        tasks_to_wait: list[asyncio.Task] = []

        for name, task in self._tasks.items():
            if task.done():
                results[name] = "already_done"
                continue
            task.cancel()
            tasks_to_wait.append(task)
            results[name] = "cancelling"

        if tasks_to_wait:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_wait, return_exceptions=True),
                    timeout=timeout,
                )
                for name in results:
                    if results[name] == "cancelling":
                        results[name] = "cancelled"
            except asyncio.TimeoutError:
                for name in results:
                    if results[name] == "cancelling":
                        results[name] = "timeout"
                logger.warning(
                    "CronLoopRegistry: stop_all timed out after %.1fs", timeout,
                )

        cancelled = sum(1 for v in results.values() if v in ("cancelled", "already_done"))
        logger.info(
            "CronLoopRegistry: %d/%d loops stopped", cancelled, len(results),
        )
        return results

    def get_health(self) -> dict[str, Any]:
        """Return health status of all registered loops.

        Returns:
            Dict with per-loop status and overall summary.
        """
        now = time.monotonic()
        tasks_info: dict[str, dict[str, Any]] = {}
        healthy = 0
        unhealthy = 0

        for name in self._loops:
            loop = self._loops[name]
            task = self._tasks.get(name)

            if task is None:
                status = "not_started"
                unhealthy += 1
            elif task.done():
                exc = task.exception() if not task.cancelled() else None
                if task.cancelled():
                    status = "cancelled"
                elif exc:
                    status = "crashed"
                    unhealthy += 1
                else:
                    status = "completed"
                    healthy += 1
            else:
                status = "running"
                healthy += 1

            info: dict[str, Any] = {"status": status}
            uptime = now - loop._last_run_at if loop._last_run_at else None
            if uptime is not None:
                info["uptime_seconds"] = round(uptime, 1)
            if loop._last_error:
                info["last_error"] = loop._last_error
            info["last_status"] = loop._last_status

            tasks_info[name] = info

        return {
            "total": len(self._loops),
            "healthy": healthy,
            "unhealthy": unhealthy,
            "loops": tasks_info,
        }

    def get_loop(self, name: str) -> BaseCronLoop | None:
        """Get a registered loop by name (or None)."""
        return self._loops.get(name)

    def get_task(self, name: str) -> asyncio.Task | None:
        """Get the asyncio.Task for a registered loop (or None)."""
        return self._tasks.get(name)

    @property
    def loop_count(self) -> int:
        return len(self._loops)

    @property
    def names(self) -> list[str]:
        return list(self._loops.keys())
