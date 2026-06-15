# Redis Failure Modes — Graceful Degradation (#1801 / #1881)

## Overview

Redis is used across multiple critical paths: cache, rate limiter, SSE state
tracking, ARQ job queue, distributed locks, circuit breaker state, and feature
flag overrides. If Redis goes offline, the system must degrade gracefully
rather than crash.

This document describes the behavior of each subsystem when Redis is
unavailable, and the resilience layer (`safe_redis_call` / `ResilientRedis`)
that wraps every Redis operation.

## Resilience Layer (#1881)

Every Redis operation in the codebase now goes through one of two wrappers:

1. **`safe_redis_call(coro, fallback, timeout_s, method_name, module)`** —
   async wrapper with per-command timeouts and inferred fallback values.
   Never raises. Returns the fallback value on any failure.

2. **`ResilientRedis(redis)`** — proxy class that wraps every method of a Redis
   client through ``safe_redis_call``. When the underlying client is ``None``,
   all methods return safe defaults without any network call.

### Prometheus Metrics

The following metric is incremented on every fallback:

- ``smartlic_redis_fallback_total{module, method, reason}`` — Counter
  - ``module``: identifies the caller (e.g. ``sse``, ``rate_limiter``,
    ``feature_flags``, ``swr_cache``)
  - ``method``: the Redis command name (e.g. ``xread``, ``get``, ``set``,
    ``incr``, ``eval``)
  - ``reason``: ``timeout`` | ``connection_error`` | ``unexpected_error``

## Failure Mode: Redis DOWN

When `get_redis_pool()` returns `None` (Redis URL not configured or connection
failed at startup), all callers that check the return value see `None` and take
their fallback path.

When Redis is **alive but slow**, the `ResilientRedis` proxy (from
`redis_resilience.py`) wraps each operation with `asyncio.wait_for()` and
per-operation timeouts:

| Operation Type | Timeout | Fallback |
|---|---|---|
| Read (get, exists, ttl, ping) | 500ms | None / False / -2 |
| Write (set, incr, expire, delete) | 1s | True / 1 / 0 |
| Scan (keys, scan) | 3s | ([], 0) |
| Complex (eval, pipeline) | 3s | None |

### Affected Functionalities (#1881 — All use safe_redis_call)

| Feature | Redis DOWN Behavior | Impact |
|---------|-------------------|--------|
| Rate limiter (`rate_limiter.py`) | Fail-open via `safe_redis_call` + in-memory fallback in `RateLimiter._check_memory()`. All Redis calls (incr, expire, ttl, eval, hmget) wrapped. | No rate limiting during outage. Bot protection degraded. |
| Auth cache (L2) | L1 memory cache continues. L2 Redis skip = cache miss, re-fetch from Supabase. | Slightly slower auth (every request hits Supabase). |
| Search results cache | L1 InMemoryCache continues (4h TTL). Sync Redis calls already wrapped in try/except. | No impact if data in L1. Cache misses fall through to DataLake (<100ms). |
| SSE progress tracking (`search_sse.py`) | Redis `xread` wrapped with `safe_redis_call`. On fallback returns `[]` = no new data, loop continues polling. | SSE still works for active sessions. Redis Streams fallback uses Supabase polling. |
| ARQ job queue (distributed locks) | `_acquire_lock` returns True (proceed). Risk of duplicate job execution. | Acceptable — jobs are idempotent (upsert semantics). |
| ARQ queue itself | ARQ uses its own Redis connection. If same Redis: queue unavailable. | Background jobs (summaries, Excel) deferred until Redis recovers. |
| Circuit breaker (PNCP, PCP) | Falls back to local in-memory state. | CB still functions within a single process, but state is not shared across workers. |
| LLM budget tracking | `track_llm_cost` returns 0.0 (no-op). `is_budget_exceeded` returns False. | Budget enforcement disabled. Alert dedup disabled. |
| LLM batch API | Batch meta not persisted. Pending batch detection falls back to empty list. | Batch jobs not tracked across restarts. |
| Login activity tracking | Falls back to in-memory buffer. | Login data not persisted to DB. Recovered when Redis is back. |
| PNCP canary | Failure counting disabled. Alerting disabled. | No auto-detection of PNCP API breaking changes. |
| Feature flags (`routes/feature_flags.py`) | All Redis get/set/delete wrapped with `safe_redis_call`. Falls back to env-var + in-memory defaults. | Flag overrides not applied until Redis recovers. |
| SWR Cache (`cache/swr.py`) | Redis exists/set/delete wrapped with `safe_redis_call`. Falls back to InMemoryCache. | Slightly more DB queries under bot crawl storms. |
| Products / Founders / Orgao cache | Falls back to InMemoryCache or direct DB query. | Slightly slower on cache miss. |
| Metrics cache | Computes metrics directly instead of reading from Redis. | More DB/API calls on each metrics request. |
| Stripe webhook dedup | Dedup window lost. Risk of double-processing webhook events. | Stripe events may be processed twice (idempotency keys protect). |
| Admin session revoke | Revoke not propagated across workers. | Revoke takes effect only on next auth cache refresh (5 min). |
| Reports/Contracts crawler checkpoint | Checkpoint not saved. Progress may regress on worker restart. | Acceptable — crawler resumes from last DB checkpoint on next cycle. |
| Billing cron (distributed locks) | Lock acquisition succeeds. Multiple workers may process billing. | Acceptable — billing is idempotent (upsert + dedup). |
| Quota fallback (`quota/quota_fallback.py`) | Sync Redis eval wrapped in try/except (async `safe_redis_call` not applicable). Layer 3 fail-open returns True. | More fallback allowances granted than the daily limit. |

### Behavior per Component Type

**Rate Limiter** (`rate_limiter.py`, `api_key_rate_limit.py`):
- `get_redis_pool()` returns `None` -> `RateLimiter._check_memory()` takes over
- `RedisRateLimiter` in circuit breaker also falls back to memory
- **Fail-open**: all requests allowed (no 429s), bot protection degraded

**Cache** (`cache_module.py`, `cache/redis.py`):
- `None` from `get_redis_pool()` triggers `get_fallback_cache()` (InMemoryCache)
- All Redis operations wrapped in try/except with InMemoryCache fallback

**Auth** (`auth.py`):
- L1 memory cache (5 min TTL) continues serving
- L2 Redis lookup skipped -> cache miss -> re-fetch from Supabase
- `_check_session_revoked`: returns `False` (fail-open, allows request)

**ARQ/Locks** (`cron/_loop.py`, `jobs/cron/*`):
- `_acquire_lock`: returns `True` if Redis unavailable (proceed without lock)
- Risk: duplicate execution of cron jobs across workers

**SSE** (`progress.py`, `routes/search_sse.py`):
- `progress._publish_to_redis`: returns early, events stay in-memory only
- SSE stream still works from in-memory queue
- XREAD polling in SSE route: uses separate `get_sse_redis_pool()`

### Health Check

The health endpoint (`backend/health.py::get_system_health()`) reports Redis as:

| Redis State | Status | Overall |
|-------------|--------|---------|
| Connected + ping OK | `up` | Depends on other components |
| URL configured but connection failed | `down` | `unhealthy` |
| URL not configured | `down` | `unhealthy` |

The readiness probe (`backend/health.py::check_redis`) is advisory — it reports
degraded but does NOT remove the instance from the load balancer.

### Recovery Procedure

1. **Check Redis connectivity** from Railway dashboard or directly:
   ```bash
   railway run redis-cli -u $REDIS_URL ping
   ```

2. **If Redis is up but connection pool is saturated:**
   ```bash
   railway run redis-cli -u $REDIS_URL CLIENT LIST | wc -l
   ```

3. **Monitor** Prometheus gauges:
   - `smartlic_redis_available` (0/1)
   - `smartlic_redis_fallback_duration_seconds` (seconds since fallback)
   - `smartlic_redis_fallback_total{module,method,reason}` (per-operation fallback counter)
   - `smartlic_redis_pool_connections_used` / `max`

4. **After recovery**: verify:
   - Auth cache repopulates on next request
   - Rate limiter returns to Redis mode
   - ARQ jobs resume (may need `railway redeploy --service worker`)

### Design Decisions

1. **Why not mark as unhealthy when Redis is down?**
   Redis is a cache/accelerator, not a source of truth. The system functions
   without it (degraded). Marking unhealthy would cause Railway to kill and
   restart the instance, which doesn't help.

2. **Why fail-open rate limiter?**
   A false positive (blocking a legitimate user) is worse than a false negative
   (allowing a bot). During an outage, it's better to serve traffic without
   protection than to block all traffic.

3. **Why allow duplicate cron jobs?**
   Cron jobs handle their own idempotency (upsert semantics, `ON CONFLICT DO
   NOTHING`). The risk of double-processing is low and the impact is limited to
   extra API calls, not data corruption.

4. **Why not crash on Redis pipeline None?**
   Pipeline operations are wrapped in try/except in `check_api_key_rate_limit`
   and circuit breaker. If pipeline creation fails, the exception handler takes
   the fail-open path.
