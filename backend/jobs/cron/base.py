"""jobs.cron.base — BaseCronLoop ABC (Template Method pattern).

All lifespan cron loops inherit from ``BaseCronLoop`` which provides:

  * Uniform ``start()`` lifecycle (initial_delay → run_once → update_health → sleep)
  * Redis-based health reporting (``loop:health:<name>`` hash) — AC5.8
  * Prometheus metrics via ``metrics.py``
  * Configurable ``handle_error()`` override
  * CancelledError / infra-unavailable handling built in
  * Lock helpers (``_acquire_lock`` / ``_release_lock``) available for subclasses

Lock strategy (AC5.1 Template Method):
  Each subclass's ``run_once()`` is responsible for its own Redis lock
  acquisition using the provided helpers.  The ``start()`` lifecycle only
  orchestrates scheduling and error handling — it does NOT acquire locks
  automatically, so that tests calling ``run_once()`` directly get the
  full business logic including lock behavior.

Usage::

    class MyLoop(BaseCronLoop):
        name = "my_loop"
        interval_seconds = 3600
        lock_key = "smartlic:my_loop:lock"
        lock_ttl = 600

        async def run_once(self) -> dict:
            locked = await self._acquire_lock()
            if not locked:
                return {"status": "skipped", "reason": "lock_held"}
            try:
                # business logic
                return {"deleted": 42}
            finally:
                await self._release_lock()
"""

from __future__ import annotations

import abc
import asyncio
import logging
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BaseCronLoop(abc.ABC):
    """Template-method base class for all lifespan cron loops.

    Subclasses MUST define:
      * ``name``             — human-readable unique identifier (used for Redis
                               health key and Prometheus labels).
      * ``interval_seconds`` — sleep interval between successful runs.
      * ``run_once()``       — the actual business logic; returns a dict result.

    Subclasses MAY override:
      * ``lock_key``         — Redis NX lock key (None = no locking).
      * ``lock_ttl``         — lock TTL in seconds.
      * ``initial_delay``    — seconds to sleep before first run.
      * ``error_retry_seconds`` — sleep after an unhandled exception.
      * ``handle_error()``   — custom error handling (default: log + sleep).
    """

    # --- Required overrides ---
    name: str = ""
    interval_seconds: int | float = 0

    # --- Optional overrides ---
    lock_key: str | None = None
    lock_ttl: int | None = None
    initial_delay: float = 0.0
    error_retry_seconds: float = 300.0

    # --- Internal state (updated by start()) ---
    _last_run_at: float = 0.0     # monotonic clock
    _last_status: str = "unknown"
    _last_error: str | None = None

    # ── Abstract ────────────────────────────────────────────────────────────

    @abc.abstractmethod
    async def run_once(self) -> dict:
        """Execute one cycle of the loop (includes lock acquisition if used).

        Returns:
            A dict summarising the result (e.g. ``{"deleted": 42}``).
            The dict is logged and stored in the Redis health hash.
        """
        ...

    # ── Hooks ───────────────────────────────────────────────────────────────

    async def on_startup(self) -> None:
        """Called once before the main loop (optional hook).

        Use for scheduling the first run (e.g. ``await asyncio.sleep(delay)``).
        """
        pass

    async def handle_error(self, exc: Exception) -> None:
        """Handle an exception from ``run_once()``.

        Default: log the exception with circuit-breaker awareness and let
        the loop retry after ``error_retry_seconds``.
        """
        _log_cb_aware(logger, self.name, exc)

    # ── Lock helpers ────────────────────────────────────────────────────────

    async def _acquire_lock(self) -> bool:
        """Acquire a Redis NX lock. Returns True if acquired or Redis down."""
        if not self.lock_key or not self.lock_ttl:
            return True
        try:
            from redis_pool import get_redis_pool
            redis = await get_redis_pool()
            if redis:
                acquired = await redis.set(
                    self.lock_key,
                    datetime.now(timezone.utc).isoformat(),
                    nx=True,
                    ex=self.lock_ttl,
                )
                if not acquired:
                    return False
        except Exception as e:
            logger.warning("%s: lock check failed (proceeding): %s", self.name, e)
        return True

    async def _release_lock(self) -> None:
        """Release a Redis lock (best-effort)."""
        if not self.lock_key:
            return
        try:
            from redis_pool import get_redis_pool
            redis = await get_redis_pool()
            if redis:
                await redis.delete(self.lock_key)
        except Exception:
            pass

    # ── Health reporting (AC5.8) ────────────────────────────────────────────

    async def _report_health(
        self,
        status: str,
        error: str | None = None,
        extra: dict | None = None,
    ) -> None:
        """Write health state to Redis hash ``loop:health:<name>``.

        Fields: ``last_run_at`` (ISO-8601), ``last_status``, ``last_error``,
        and any extra keys provided.
        """
        self._last_status = status
        self._last_error = error
        if error:
            self._last_run_at = 0.0
        else:
            self._last_run_at = time.monotonic()

        try:
            from redis_pool import get_redis_pool
            redis = await get_redis_pool()
            if redis:
                mapping: dict[str, str] = {
                    "last_run_at": datetime.now(timezone.utc).isoformat(),
                    "last_status": status,
                    "last_error": error or "",
                }
                if extra:
                    mapping.update(extra)
                await redis.hset(f"loop:health:{self.name}", mapping=mapping)  # type: ignore[arg-type]
        except Exception:
            pass

    # ── Prometheus metrics ──────────────────────────────────────────────────

    def _observe_duration(self, duration_s: float) -> None:
        """Record loop duration to Prometheus (best-effort)."""
        try:
            from metrics import CRON_LOOP_DURATION
            CRON_LOOP_DURATION.labels(loop=self.name).observe(duration_s)
        except Exception:
            pass

    def _inc_status(self, status: str) -> None:
        """Increment loop status counter (best-effort)."""
        try:
            from metrics import CRON_LOOP_STATUS
            CRON_LOOP_STATUS.labels(loop=self.name, status=status).inc()
        except Exception:
            pass

    # ── Main lifecycle ──────────────────────────────────────────────────────

    async def start(self) -> None:
        """Main loop lifecycle.

        Sequence:
          1. ``initial_delay`` sleep (if configured)
          2. ``on_startup()`` hook
          3. Infinite loop::
               await run_once()
               _report_health("completed")
               await asyncio.sleep(interval_seconds)
             On exception: handle_error() → _report_health("error") → sleep
        """
        await asyncio.sleep(self.initial_delay)

        try:
            await self.on_startup()
        except Exception:
            logger.exception("%s: on_startup hook failed, continuing", self.name)

        while True:
            start_ts = time.monotonic()
            status = "completed"
            error: str | None = None

            try:
                result = await self.run_once()
                duration = time.monotonic() - start_ts
                logger.info("%s: completed in %.2fs — %s", self.name, duration, result)
                self._observe_duration(duration)
                self._inc_status("completed")
            except asyncio.CancelledError:
                logger.info("%s: cancelled", self.name)
                self._inc_status("cancelled")
                break
            except Exception as exc:
                duration = time.monotonic() - start_ts
                status = "error"
                error = f"{type(exc).__name__}: {exc}"
                self._observe_duration(duration)
                self._inc_status("error")
                await self.handle_error(exc)

            # Report health (always — even on error, so cron_monitor sees the
            # failure timestamp rather than a stale "completed" entry).
            await self._report_health(status, error=error, extra={
                "duration_s": f"{time.monotonic() - start_ts:.2f}",
            })

            if status == "error":
                await asyncio.sleep(self.error_retry_seconds)
            else:
                await asyncio.sleep(self.interval_seconds)


def _log_cb_aware(log: logging.Logger, name: str, exc: Exception) -> None:
    """Log exception with awareness of circuit-breaker / connection errors."""
    err_name = type(exc).__name__
    err_str = str(exc)
    if (
        "CircuitBreaker" in err_name
        or "ConnectionError" in err_name
        or "ConnectError" in err_str
        or "PGRST205" in err_str
    ):
        log.warning("%s: skipped (infra unavailable): %s", name, exc)
    else:
        log.error("%s: loop error: %s", name, exc, exc_info=True)
