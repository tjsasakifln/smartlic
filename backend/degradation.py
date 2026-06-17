"""Graceful Degradation Utilities — Issue #1921.

Provides reusable patterns for graceful degradation across all external
dependencies:

1. ``track_degradation(source, mode)`` — Increments the unified
   ``smartlic_degradation_total{source, mode}`` Prometheus counter.

2. ``graceful_fallback(fallback_value, source)`` — Decorator that wraps an
   async function, catches timeout/connection errors, logs the degradation,
   increments the metric, and returns ``fallback_value``.

Usage::

    from degradation import graceful_fallback

    @graceful_fallback(fallback_value=[], source="pncp")
    async def fetch_from_pncp(uf: str) -> list:
        ...

    # On TimeoutError -> returns [], logs warning, increments metric

3. ``handle_sync_call(source, fallback, func, *args, **kwargs)`` — Sync
   equivalent for use in ``asyncio.to_thread`` contexts.
"""

import asyncio
import functools
import logging
from typing import Any, Callable, TypeVar, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")


def track_degradation(source: str, mode: str) -> None:
    """Increment the unified degradation counter (best-effort, never raises).

    Args:
        source: Dependency name (e.g. ``"supabase"``, ``"stripe"``, ``"redis_queue"``).
        mode: Failure mode (e.g. ``"timeout"``, ``"connection_error"``, ``"unexpected_error"``).
    """
    try:
        from metrics import DEGRADATION_COUNTER

        DEGRADATION_COUNTER.labels(source=source, mode=mode).inc()
    except Exception:
        pass  # Metrics not available — graceful degradation of the degradation tracker


def graceful_fallback(
    fallback_value: Any = None,
    source: str = "unknown",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: catch errors and return fallback, log degradation, increment metric.

    The decorated function MUST be async (coroutine function).

    Catches: ``asyncio.TimeoutError``, ``ConnectionError``, ``OSError``,
    and generic ``Exception`` as a last resort.

    Args:
        fallback_value: Value to return on failure. Defaults to ``None``.
        source: Dependency name for the ``smartlic_degradation_total`` label.

    Returns:
        Decorated async function that never raises — returns ``fallback_value`` instead.

    Example::

        @graceful_fallback(fallback_value=[], source="pncp")
        async def fetch_data(uf: str) -> list:
            return await http_client.get(...)

        # When PNCP is unreachable:
        result = await fetch_data("SP")  # -> [], logged, metric incremented
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except asyncio.TimeoutError:
                _log_and_track(source, "timeout", func.__name__)
                return fallback_value
            except (ConnectionError, OSError):
                _log_and_track(source, "connection_error", func.__name__)
                return fallback_value
            except Exception as exc:
                mode = _classify_exception(exc)
                _log_and_track(source, mode, func.__name__)
                return fallback_value

        return wrapper

    return decorator


def _classify_exception(exc: Exception) -> str:
    """Classify an exception into a degradation mode string."""
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    if isinstance(exc, (ConnectionError, OSError)):
        return "connection_error"
    exc_name = type(exc).__name__.lower()
    if "rate" in exc_name or "429" in str(exc):
        return "rate_limited"
    if "timeout" in exc_name:
        return "timeout"
    return "unexpected_error"


def _log_and_track(source: str, mode: str, operation: str) -> None:
    """Log degradation warning and increment metric."""
    logger.warning(
        "Degradation: source=%s mode=%s operation=%s — using fallback",
        source,
        mode,
        operation,
    )
    track_degradation(source, mode)


def handle_sync_call(
    source: str,
    fallback: Any = None,
    logger_warning: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for **sync** functions (safe for ``asyncio.to_thread`` context).

    Same behavior as ``graceful_fallback`` but for synchronous callables.

    Usage::

        @handle_sync_call(source="stripe", fallback=None)
        def create_stripe_checkout(customer_id: str) -> dict:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return func(*args, **kwargs)
            except asyncio.TimeoutError:
                if logger_warning:
                    logger.warning(
                        "Degradation: source=%s mode=%s operation=%s — using fallback",
                        source, "timeout", func.__name__,
                    )
                track_degradation(source, "timeout")
                return cast(T, fallback)
            except (ConnectionError, OSError):
                if logger_warning:
                    logger.warning(
                        "Degradation: source=%s mode=%s operation=%s — using fallback",
                        source, "connection_error", func.__name__,
                    )
                track_degradation(source, "connection_error")
                return cast(T, fallback)
            except Exception:
                if logger_warning:
                    logger.warning(
                        "Degradation: source=%s mode=%s operation=%s — using fallback",
                        source, "unexpected_error", func.__name__,
                    )
                track_degradation(source, "unexpected_error")
                return cast(T, fallback)

        return wrapper

    return decorator


__all__ = [
    "track_degradation",
    "graceful_fallback",
    "handle_sync_call",
]
