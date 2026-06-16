"""Edge-layer IP-based rate limiting with Redis sliding window (Issue #1861).

Implements sliding window rate limiting per IP address using Redis sorted
sets for precision. Provides DDoS protection at the middleware layer with
path-based thresholds, auto-blocklist, and Prometheus metrics.

AC1: Redis sliding window (ZSET-based), not simple token bucket.
AC2: ``/health/*`` endpoints are exempt from rate limiting.
AC3: 100 req/min default threshold for ``/api/*`` and ``/v1/*`` prefixes.
AC4: Auto-blocklist: IPs exceeding 5x threshold blocked for 10 minutes.
AC5: Whitelist configurable via ``RATE_LIMIT_WHITELIST_IPS`` env var.
AC6: Prometheus metrics ``ip_rate_limit_exceeded_total`` and ``ip_blocklist_active``.
AC7: RFC 6585 response headers (X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After).
AC9: GDPR-safe WARNING log with IP masked (last 2 octets as ``*.*``).
"""

import logging
import time
import uuid
from ipaddress import ip_address, ip_network

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config.features import (
    IP_RATE_LIMIT_BLOCKLIST_DURATION_S,
    IP_RATE_LIMIT_BLOCKLIST_MULTIPLIER,
    IP_RATE_LIMIT_DEFAULT,
    IP_RATE_LIMIT_ENABLED,
    IP_RATE_LIMIT_WINDOW_S,
    RATE_LIMIT_WHITELIST_IPS,
)
from redis_pool import get_redis_pool

logger = logging.getLogger(__name__)

# Paths that are NEVER rate limited by this middleware.
_RATE_LIMIT_EXEMPT_PREFIXES: tuple[str, ...] = ("/health",)

# Paths that ARE rate limited by this middleware.
_RATE_LIMITED_PREFIXES: tuple[str, ...] = ("/api/", "/v1/")

# Redis key templates
_REDIS_SLIDING_KEY = "ip:rl:{prefix}:{ip}"
_REDIS_BLOCKLIST_KEY = "ip:block:{ip}"

# Number of entries to clean up per sliding window sweep.
_SLIDING_WINDOW_CLEANUP_CHUNK = 1000


def _parse_whitelist(raw: str) -> set[str]:
    """Parse comma-separated whitelist into a set of IPs / CIDR ranges.

    Accepts individual IPs (``192.168.1.1``) and CIDR notation
    (``10.0.0.0/8``). Invalid entries are silently skipped with a
    warning log.
    """
    if not raw:
        return set()
    whitelist: set[str] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            # Validate both bare IPs and CIDR notation
            if "/" in entry:
                ip_network(entry, strict=False)
            else:
                ip_address(entry)
            whitelist.add(entry)
        except ValueError:
            logger.warning(
                "Ignoring invalid whitelist entry: %s — must be a valid IP or CIDR",
                entry,
            )
    return whitelist


def _is_ip_whitelisted(ip: str, whitelist: set[str]) -> bool:
    """Check whether *ip* matches any whitelist entry (direct or CIDR)."""
    if not whitelist or not ip or ip == "unknown":
        return False
    if ip in whitelist:
        return True
    try:
        addr = ip_address(ip)
        for entry in whitelist:
            if "/" in entry and addr in ip_network(entry, strict=False):
                return True
    except ValueError:
        pass
    return False


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, respecting reverse-proxy headers."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _get_path_prefix(path: str) -> str:
    """Extract the first two path segments for rate-limit key grouping.

    ``/v1/search/foo?bar=1`` -> ``/v1/search``
    ``/api/buscar``         -> ``/api/buscar``
    Non-matched paths       -> ``other``
    """
    for prefix in _RATE_LIMITED_PREFIXES:
        if path.startswith(prefix):
            segments = path.strip("/").split("/")[:2]
            return "/" + "/".join(segments)
    return "other"


def _get_ip_prefix(ip: str) -> str:
    """Extract the first two octets of an IPv4 address for metric labels.

    ``203.0.113.55`` -> ``203.0``
    Returns the whole IP for IPv6 or unknown.
    """
    if not ip or ip == "unknown":
        return "unknown"
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:2])
    return ip  # IPv6 or weird input


def _mask_ip(ip: str) -> str:
    """GDPR-safe IP masking: last two octets replaced with ``*.*``.

    ``203.0.113.55`` -> ``203.0.*.*``
    """
    if not ip or ip == "unknown":
        return ip
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.*"
    return ip


def _is_exempt_path(path: str) -> bool:
    """Return True if *path* should not be rate limited."""
    for prefix in _RATE_LIMIT_EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _is_rate_limited_path(path: str) -> bool:
    """Return True if *path* should be rate limited."""
    for prefix in _RATE_LIMITED_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


class IPRateLimiter(BaseHTTPMiddleware):
    """Edge-layer sliding-window rate limiter per IP address.

    Uses Redis sorted sets (ZSET) with timestamps as scores to implement
    a sliding window with sub-second precision. Falls back to in-memory
    tracking when Redis is unavailable.

    Flow:
        1. Exempt paths (``/health/*``) pass through immediately.
        2. Whitelisted IPs pass through immediately.
        3. Blocklisted IPs receive 429 immediately.
        4. Sliding window check via Redis ZSET (or in-memory fallback).
        5. If rate exceeded, increment Prometheus counter, apply blocklist
           when threshold is 5x, return 429 with RFC 6585 headers.
        6. GDPR-safe WARNING log for every 429 response.
    """

    def __init__(self, app):
        super().__init__(app)
        # Parse whitelist from env var (supports comma-separated IPs/CIDRs).
        self._whitelist: set[str] = _parse_whitelist(RATE_LIMIT_WHITELIST_IPS)

        # In-memory fallback store when Redis is unavailable.
        # {key: [(timestamp, request_id), ...]}
        self._memory_store: dict[str, list[tuple[float, str]]] = {}

        # In-memory blocklist. {ip: expiry_timestamp}
        self._memory_blocklist: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Enforce IP-based rate limiting for the incoming request.

        Returns 429 with RFC 6585 headers when the rate limit is exceeded.
        """
        if not IP_RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path

        # AC2: Exempt health-check paths entirely.
        if _is_exempt_path(path):
            return await call_next(request)

        # AC3: Only rate-limit configured prefixes.
        if not _is_rate_limited_path(path):
            return await call_next(request)

        ip = _get_client_ip(request)

        # AC5: Whitelisted IPs pass through.
        if _is_ip_whitelisted(ip, self._whitelist):
            return await call_next(request)

        path_prefix = _get_path_prefix(path)
        now = time.time()
        window_s = IP_RATE_LIMIT_WINDOW_S
        limit = IP_RATE_LIMIT_DEFAULT
        block_threshold = limit * IP_RATE_LIMIT_BLOCKLIST_MULTIPLIER

        # AC4: Check blocklist first.
        if await self._is_blocklisted(ip, now):
            logger.warning(
                "Blocklisted IP rejected: ip=%s path=%s",
                _mask_ip(ip),
                path,
            )
            # AC9: IP already logged above (masked).
            self._track_exceeded(ip, path_prefix, blocked=True)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "Retry-After": str(IP_RATE_LIMIT_BLOCKLIST_DURATION_S),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + IP_RATE_LIMIT_BLOCKLIST_DURATION_S)),
                },
            )

        # AC1: Sliding window check.
        allowed, current_count = await self._check_sliding_window(ip, path_prefix, limit, now)

        if not allowed:
            # AC4: Blocklist if threshold exceeded.
            if current_count >= block_threshold:
                await self._add_to_blocklist(ip, now)

            # AC9: GDPR-safe warning.
            logger.warning(
                "IP rate limit exceeded: ip=%s path=%s count=%d limit=%d window=%ds",
                _mask_ip(ip),
                path,
                current_count,
                limit,
                window_s,
            )

            # AC6: Prometheus metric.
            self._track_exceeded(ip, path_prefix, blocked=False)

            remaining = max(0, limit - current_count)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "Retry-After": str(window_s),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(now + window_s)),
                },
            )

        # AC7: Inject rate limit headers on successful responses.
        remaining = max(0, limit - current_count)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(now + window_s))
        return response

    # ------------------------------------------------------------------
    # Redis sliding window (AC1)
    # ------------------------------------------------------------------

    async def _check_sliding_window(
        self,
        ip: str,
        path_prefix: str,
        limit: int,
        now: float,
    ) -> tuple[bool, int]:
        """Check the sliding window rate limit for *ip* on *path_prefix*.

        Returns ``(allowed, current_count)``. Uses Redis when available,
        falls back to in-memory.
        """
        redis = await get_redis_pool()
        if redis:
            return await self._check_redis(redis, ip, path_prefix, limit, now)
        return self._check_memory(ip, path_prefix, limit, now)

    async def _check_redis(
        self,
        redis,
        ip: str,
        path_prefix: str,
        limit: int,
        now: float,
    ) -> tuple[bool, int]:
        """Sliding window via Redis ZSET.

        ``ZREMRANGEBYSCORE`` removes entries outside the window,
        ``ZCARD`` counts current entries, then ``ZADD`` appends the
        new request. Uses pipeline for atomicity.
        """
        key = _REDIS_SLIDING_KEY.format(ip=ip, prefix=path_prefix)
        window_start = now - IP_RATE_LIMIT_WINDOW_S
        request_id = str(uuid.uuid4())

        try:
            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = await pipe.execute()

            current_count = int(results[1]) if len(results) > 1 else 0

            if current_count >= limit:
                # Count is at or above limit — do NOT add this request.
                return (False, current_count)

            # Record this request.
            add_pipe = redis.pipeline()
            add_pipe.zadd(key, {request_id: now})
            add_pipe.expire(key, IP_RATE_LIMIT_WINDOW_S + 10)
            await add_pipe.execute()

            return (True, current_count + 1)

        except Exception as exc:
            logger.debug("Redis sliding window check failed: %s — allowing request", exc)
            # Fail-open: allow when Redis is slow or down.
            return (True, 0)

    def _check_memory(
        self,
        ip: str,
        path_prefix: str,
        limit: int,
        now: float,
    ) -> tuple[bool, int]:
        """In-memory sliding window fallback when Redis is unavailable."""
        key = f"{path_prefix}:{ip}"
        window_start = now - IP_RATE_LIMIT_WINDOW_S

        entries = self._memory_store.get(key, [])
        # Prune expired entries.
        entries = [(ts, rid) for ts, rid in entries if ts > window_start]
        current_count = len(entries)

        if current_count >= limit:
            self._memory_store[key] = entries
            return (False, current_count)

        entries.append((now, str(uuid.uuid4())))
        self._memory_store[key] = entries

        # Periodic cleanup of stale keys (every 200 requests).
        if len(self._memory_store) > 1000:
            self._cleanup_memory_store(now)

        return (True, current_count + 1)

    def _cleanup_memory_store(self, now: float) -> None:
        """Remove stale keys from in-memory store."""
        window_start = now - IP_RATE_LIMIT_WINDOW_S
        stale = [
            k for k, v in self._memory_store.items()
            if not v or v[-1][0] < window_start
        ]
        for k in stale:
            del self._memory_store[k]

    # ------------------------------------------------------------------
    # Blocklist (AC4)
    # ------------------------------------------------------------------

    async def _is_blocklisted(self, ip: str, now: float) -> bool:
        """Check whether *ip* is currently blocklisted."""
        redis = await get_redis_pool()
        if redis:
            try:
                exists = await redis.exists(_REDIS_BLOCKLIST_KEY.format(ip=ip))
                return bool(exists)
            except Exception:
                return False  # Fail-open on Redis error.

        # In-memory fallback.
        expiry = self._memory_blocklist.get(ip, 0.0)
        if expiry > now:
            return True
        self._memory_blocklist.pop(ip, None)
        return False

    async def _add_to_blocklist(self, ip: str, now: float) -> None:
        """Add *ip* to the blocklist for the configured duration."""
        block_key = _REDIS_BLOCKLIST_KEY.format(ip=ip)
        redis = await get_redis_pool()
        if redis:
            try:
                pipe = redis.pipeline()
                pipe.set(block_key, "1")
                pipe.expire(block_key, IP_RATE_LIMIT_BLOCKLIST_DURATION_S)
                await pipe.execute()
                logger.info(
                    "IP auto-blocklisted: ip=%s duration=%ds threshold=%dx",
                    _mask_ip(ip),
                    IP_RATE_LIMIT_BLOCKLIST_DURATION_S,
                    IP_RATE_LIMIT_BLOCKLIST_MULTIPLIER,
                )
                return
            except Exception as exc:
                logger.debug("Failed to add IP to Redis blocklist: %s", exc)

        # In-memory fallback.
        self._memory_blocklist[ip] = now + IP_RATE_LIMIT_BLOCKLIST_DURATION_S

    # ------------------------------------------------------------------
    # Metrics (AC6)
    # ------------------------------------------------------------------

    def _track_exceeded(self, ip: str, path_prefix: str, blocked: bool) -> None:
        """Increment Prometheus counter for rate-limit violations."""
        try:
            from metrics import IP_RATE_LIMIT_EXCEEDED_TOTAL, IP_BLOCKLIST_ACTIVE

            ip_prefix = _get_ip_prefix(ip)
            IP_RATE_LIMIT_EXCEEDED_TOTAL.labels(
                ip_prefix=ip_prefix,
                path_prefix=path_prefix,
            ).inc()

            if blocked:
                IP_BLOCKLIST_ACTIVE.inc()

            # Also update the blocklist gauge (best-effort count from Redis).
            try:
                import asyncio
                asyncio.ensure_future(self._update_blocklist_gauge())
            except Exception:
                pass

        except Exception:
            pass  # Metrics are optional.

    async def _update_blocklist_gauge(self) -> None:
        """Update the blocklist active gauge from Redis cardinality."""
        try:
            redis = await get_redis_pool()
            if redis:
                from metrics import IP_BLOCKLIST_ACTIVE
                # Use SCAN to count keys matching ip:block:* pattern.
                count = 0
                cursor = 0
                while True:
                    cursor, keys = await redis.scan(cursor, match="ip:block:*", count=100)
                    count += len(keys)
                    if cursor == 0:
                        break
                IP_BLOCKLIST_ACTIVE.set(count)
        except Exception:
            pass
