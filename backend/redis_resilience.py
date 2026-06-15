"""Redis resilience utilities — safe calls with timeout + graceful fallback.

Every Redis operation in the codebase should go through ``safe_redis_call``
to ensure the system degrades gracefully when Redis is unavailable.

Timeout defaults (per operation category):
    - Read (get, exists, ttl, ping): 500ms
    - Write (set, setex, incr, expire): 1s
    - Scan (keys, scan, mget): 3s
    - Complex (eval, pipeline): 3s
    - Health (ping): 500ms

Metrics:
    - ``smartlic_redis_fallback_total{module,method,reason}`` — Counter
      incremented each time ``safe_redis_call`` returns a fallback value.
      ``reason`` is one of ``timeout``, ``connection_error``, ``unexpected_error``.
"""

import asyncio
import logging
from typing import Any, Coroutine, Optional

logger = logging.getLogger(__name__)

# Lazy-loaded Prometheus counter — resolved at call time so metrics module
# can be unavailable without breaking Redis resilience.
def _increment_fallback_counter(module: str, method: str, reason: str) -> None:
    """Increment the Redis fallback counter (best-effort, never raises)."""
    try:
        from metrics import REDIS_FALLBACK_TOTAL
        REDIS_FALLBACK_TOTAL.labels(
            module=module, method=method, reason=reason,
        ).inc()
    except Exception:
        pass  # Metrics not configured — graceful degradation

# Timeout defaults (seconds) — conservative for shared Railway Redis
TIMEOUT_READ_S: float = 0.5
TIMEOUT_WRITE_S: float = 1.0
TIMEOUT_SCAN_S: float = 3.0
TIMEOUT_COMPLEX_S: float = 3.0
TIMEOUT_HEALTH_S: float = 0.5


# ---------------------------------------------------------------------------
# Categories of Redis commands for timeout selection
# ---------------------------------------------------------------------------
_READ_COMMANDS = frozenset({
    "get", "mget", "hget", "hgetall", "hmget",
    "exists", "hexists",
    "ttl", "pttl",
    "ping",
    "lrange", "llen",
    "smembers", "scard",
    "zcard", "zrange", "zrevrange", "zrank", "zscore",
    "getset",
    "type",
    "strlen",
    "xlen",
    "xrange", "xrevrange", "xread",
})

_WRITE_COMMANDS = frozenset({
    "set", "setex", "psetex", "setnx",
    "incr", "incrby", "incrbyfloat",
    "decr", "decrby",
    "expire", "expireat", "pexpire",
    "delete", "del",
    "lpush", "rpush", "ltrim", "lrem", "lpop", "rpop",
    "sadd", "srem",
    "zadd", "zrem", "zremrangebyscore",
    "hset", "hdel",
    "xadd", "xtrim",
    "flushdb", "flushall",
    "rename",
})

_SCAN_COMMANDS = frozenset({
    "keys", "scan", "sscan", "hscan", "zscan",
})

_COMPLEX_COMMANDS = frozenset({
    "eval", "evalsha",
    "pipeline",
    "script",
    "sort",
    "multi", "exec",
})


def _infer_timeout(method_name: str) -> float:
    """Infer appropriate timeout based on Redis command name."""
    if method_name in _READ_COMMANDS:
        return TIMEOUT_READ_S
    elif method_name in _WRITE_COMMANDS:
        return TIMEOUT_WRITE_S
    elif method_name in _SCAN_COMMANDS:
        return TIMEOUT_SCAN_S
    elif method_name in _COMPLEX_COMMANDS:
        return TIMEOUT_COMPLEX_S
    return TIMEOUT_WRITE_S


def _infer_fallback(method_name: str) -> Any:
    """Return a sensible no-op/zero fallback for common Redis command names.

    Callers that need specific fallback logic (e.g. rate limiter fail-open)
    should continue to handle None from ``get_redis_pool()`` explicitly.
    This provides a safe default that prevents AttributeError crashes.
    """
    ml = method_name.lower()

    # --- Read operations ---
    if ml in ("get", "hget", "hgetall", "hmget", "getset", "zscore", "zrank", "type", "strlen"):
        return None
    if ml in ("mget",):
        return []
    if ml in ("lrange", "zrange", "zrevrange", "xrange", "xrevrange", "xread"):
        return []
    if ml in ("smembers",):
        return set()
    if ml in ("keys", "sort"):
        return []
    if ml in ("llen", "xlen", "scard"):
        return 0

    # --- Check operations ---
    if ml in ("exists", "hexists"):
        return False
    if ml in ("ping",):
        return False

    # --- Time operations ---
    if ml in ("ttl", "pttl"):
        return -2  # Key does not exist

    # --- Write operations (fire-and-forget) ---
    if ml in (
        "set", "setex", "psetex", "setnx",
        "expire", "expireat", "pexpire",
        "lpush", "rpush", "ltrim", "lrem", "lpop", "rpop",
        "sadd", "srem",
        "xadd", "xtrim",
        "hset", "hdel",
        "flushdb", "flushall",
        "rename",
    ):
        return True

    # --- Delete ---
    if ml in ("delete", "del"):
        return 0  # Nothing deleted

    # --- Count operations ---
    if ml in ("incr", "incrby"):
        return 1
    if ml in ("incrbyfloat",):
        return 1.0
    if ml in ("decr", "decrby"):
        return -1
    if ml in ("zcard",):
        return 0
    if ml in ("zrem", "zremrangebyscore", "hdel"):
        return 0

    # --- Scan ---
    if ml in ("scan", "sscan", "hscan", "zscan"):
        return (0, [])

    # --- Complex ---
    if ml in ("eval", "evalsha"):
        return None

    return None


# ---------------------------------------------------------------------------
# Cache for fallback values by method name (avoids repeated dict lookups)
# ---------------------------------------------------------------------------
_FALLBACK_CACHE: dict[str, Any] = {}


def _cached_fallback(method_name: str) -> Any:
    """Cached version of _infer_fallback."""
    if method_name not in _FALLBACK_CACHE:
        _FALLBACK_CACHE[method_name] = _infer_fallback(method_name)
    return _FALLBACK_CACHE[method_name]


async def safe_redis_call(
    coro: Coroutine,
    fallback: Any = None,
    timeout_s: Optional[float] = None,
    method_name: str = "redis_operation",
    logger_warning: bool = True,
    module: str = "unknown",
) -> Any:
    """Execute a Redis coroutine with timeout and fallback.

    The Swiss-army-knife wrapper for all Redis operations.
    Never raises — always returns ``fallback`` on any failure.

    Args:
        coro: The Redis coroutine to execute (e.g. ``redis.get("key")``).
        fallback: Value to return on failure. If None, inferred from
            ``method_name`` via ``_infer_fallback``.
        timeout_s: Timeout in seconds. If None, inferred from method_name.
        method_name: Human-readable name for logging (default: "redis_operation").
        logger_warning: Whether to log a warning on failure (default: True).
        module: Module name for Prometheus label (default: "unknown").

    Returns:
        The Redis result on success, or ``fallback`` on failure.

    Example::

        # Redis DOWN -> returns None (safe for cache miss), never raises
        data = await safe_redis_call(redis.get("key"), method_name="get")

        # Redis DOWN -> returns default empty list
        items = await safe_redis_call(
            redis.lrange("k", 0, -1), fallback=[], method_name="lrange"
        )

        # Rate limiter: Redis DOWN -> allow request (fail-open)
        count = await safe_redis_call(
            redis.incr("key"), fallback=0, method_name="incr"
        )
    """
    if fallback is None:
        fallback = _cached_fallback(method_name)
    if timeout_s is None:
        timeout_s = _infer_timeout(method_name)

    try:
        return await asyncio.wait_for(coro, timeout=timeout_s)
    except asyncio.TimeoutError:
        _increment_fallback_counter(module, method_name, "timeout")
        if logger_warning:
            logger.warning(
                "Redis %s timed out after %.1fs - using fallback",
                method_name, timeout_s,
            )
        return fallback
    except (ConnectionError, OSError) as exc:
        # ConnectionError: Redis connection refused/reset
        # OSError: socket errors
        _increment_fallback_counter(module, method_name, "connection_error")
        if logger_warning:
            logger.warning(
                "Redis %s failed (%s: %s) - using fallback",
                method_name, type(exc).__name__, exc,
            )
        return fallback
    except Exception as exc:
        # Catch-all: any other Redis error (data errors, type errors, etc.)
        _increment_fallback_counter(module, method_name, "unexpected_error")
        if logger_warning:
            logger.warning(
                "Redis %s unexpected error (%s: %s) - using fallback",
                method_name, type(exc).__name__, exc,
            )
        return fallback


class ResilientRedis:
    """Proxy that wraps a Redis client with ``safe_redis_call`` for every method.

    If the underlying ``_redis`` is None, all method calls return safe defaults
    without any network attempt - the system continues in degraded mode.

    Usage::

        from redis_resilience import ResilientRedis

        redis_raw = await get_redis_pool()       # may be None
        safe = ResilientRedis(redis_raw)
        data = await safe.get("key")             # never raises
    """

    def __init__(self, redis: Any):
        self._redis = redis
        self._alive = redis is not None

    def is_alive(self) -> bool:
        """Return True if the underlying Redis client is available."""
        return self._alive

    def __getattr__(self, name: str) -> Any:
        """Dynamically proxy any Redis method with safe_redis_call."""
        if name.startswith("_"):
            raise AttributeError(f"ResilientRedis has no attribute {name!r}")

        # If Redis is dead, return a function that returns fallback immediately
        if not self._alive:
            async def _dead_method(*args: Any, **kwargs: Any) -> Any:
                return _cached_fallback(name)
            return _dead_method

        # Real Redis is alive - proxy with safe_redis_call
        real_method = getattr(self._redis, name, None)
        if real_method is None:
            async def _missing_method(*args: Any, **kwargs: Any) -> Any:
                return _cached_fallback(name)
            return _missing_method

        async def _safe_method(*args: Any, **kwargs: Any) -> Any:
            coro = real_method(*args, **kwargs)
            return await safe_redis_call(
                coro,
                method_name=name,
            )

        return _safe_method
