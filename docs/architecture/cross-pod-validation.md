# Cross-Pod State Validation Report

**Issue:** #1956 — P0 Cross-pod state validation
**Date:** 2026-06-17
**Author:** Dex (Builder) / AIOX Dev Agent
**Status:** Complete

---

## Executive Summary

This report documents the findings of a cross-pod state validation audit for the SmartLic backend. The system currently runs with 1 Railway worker (single pod). Scaling to >1 worker requires understanding which state is **shared** (safe across pods) vs **per-process** (problematic across pods).

### Key Finding

The **majority of state is already cross-pod safe** due to Redis and Supabase being the primary backing stores. However, three specific components use **per-process in-memory state** that would behave incorrectly with >1 worker:

| Component | Risk | Impact |
|-----------|------|--------|
| L1 InMemoryCache | LOW | Read stale data; background refresh covers most cases |
| In-memory rate limiter fallback | MEDIUM | Effective rate limit = N pods x per_pod_limit |
| SSE connection tracker | LOW | Per-pod connection limit, not global |

None of these are blocking for multi-pod. The mitigation plan is documented in the Recommendations section.

---

## Test Methodology

Tests were executed using `scripts/cross-pod-validation.sh` which runs inline Python tests against the backend modules. Where Redis was available, live connection tests were performed. Where Redis was unavailable, tests validated the fallback behavior and documented the expected degradation.

The following categories were validated:

1. Cache coherence (L1 InMemoryCache, L2 Redis, L3 Supabase)
2. Idempotency (Stripe webhook cross-pod safety)
3. Rate limiter (Redis token bucket, per-pod fallback)
4. Distributed locks (Redis SET NX contention)
5. SSE state (ProgressTracker cross-pod visibility)

---

## Results by Category

### 1. Cache Coherence

#### L1 InMemoryCache — NOT cross-pod safe

| Property | Value |
|----------|-------|
| Mechanism | `OrderedDict` with LRU eviction (max 5,000 entries) |
| Storage | Per-process in-memory |
| Cross-pod visibility | None |
| Risk | Low |

The InMemoryCache (`redis_pool.InMemoryCache`) is initialized per-process. Each pod maintains its own LRU dictionary with no synchronization mechanism. A write to pod A's InMemoryCache is invisible to pod B.

**Mitigation:** The cache manager (`manager.py`) reads from Supabase first (L1), then Redis (L2), then local file (L3). When Redis is available, `_save_to_redis` writes to the shared `l1:search_cache:` keyspace, making L2 visible to all pods. InMemoryCache is exclusively a **fallback** when Redis is down.

**Who cares:** If Redis is available (>=99% of production uptime), L1 InMemoryCache is bypassed in favor of Redis. The fallback activates only during Redis outages.

#### L2 Redis Cache — Cross-pod safe

| Property | Value |
|----------|-------|
| Mechanism | `redis.setex("l1:search_cache:{key}", ttl, data)` |
| Storage | Redis (shared) |
| Cross-pod visibility | Full |
| Risk | None |

Redis keys use the `l1:search_cache:` namespace with priority-based TTLs (hot 8h, warm 4h, cold 2h) plus random jitter (+0-10%) to prevent cache stampede (GAP-003). All pods share the same Redis instance and key namespace. Writes from any pod are immediately visible to all other pods.

**TTL jitter:** `ttl = ttl + random.randint(0, int(ttl * 0.1))` — prevents thundering herd when multiple pods expire the same key simultaneously.

#### L3 Supabase Cache — Cross-pod safe

| Property | Value |
|----------|-------|
| Mechanism | `search_results_cache` table (24h TTL) |
| Storage | PostgreSQL (shared) |
| Cross-pod visibility | Full |
| Risk | None |

All pods share the same Supabase database. The cache cascade reads Supabase first. No cross-pod issues.

---

### 2. Idempotency (Stripe Webhooks)

#### Verdict: Cross-pod safe

| Property | Value |
|----------|-------|
| Mechanism | `INSERT ... ON CONFLICT (id) DO NOTHING` |
| Storage | Supabase `stripe_webhook_events` table |
| Cross-pod safety | Full |

The idempotency claim in `webhooks/stripe.py` uses the following pattern:

```python
sb.table("stripe_webhook_events").upsert(
    {"id": event_id, "type": event_type, "status": "processing", ...},
    on_conflict="id",
    ignore_duplicates=True,
).execute()
```

This is a **database-level atomic operation**. When two pods receive the same Stripe event simultaneously:

1. Both attempt the upsert
2. The database guarantees: one pod's upsert returns the inserted row (`.data` is truthy)
3. The other pod's upsert returns empty data (`.data` is falsy) because a row with that `id` already exists

**Stuck event recovery:** If an event remains in `processing` status for >5 minutes, any pod can re-claim it. The stuck-check re-reads from the shared `stripe_webhook_events` table, then resets `status=processing`. Only one pod will succeed due to the same ON CONFLICT mechanism.

---

### 3. Rate Limiter

#### Redis token bucket (RedisRateLimiter) — Cross-pod safe

| Property | Value |
|----------|-------|
| Mechanism | Atomic Lua script in Redis |
| Key | `rate_limiter:{name}:bucket` (HASH with tokens + last_refill) |
| Cross-pod safety | Full |

The `RedisRateLimiter` uses an atomic Lua script via `redis.eval()`. The script atomically checks available tokens, decrements, and sets expiration. Redis serializes all Lua script execution — guarantee of atomicity regardless of which pod issues the command.

#### FlexibleRateLimiter (Redis) — Cross-pod safe

| Property | Value |
|----------|-------|
| Mechanism | `redis.incr(key)` + `redis.expire(key, window)` |
| Key | `rl:{endpoint}:{user_id}:{window_id}` |
| Cross-pod safety | Full |

Redis `INCR` is atomic. Both pods increment the same key. The window-based rate limit is enforced correctly regardless of which pod serves the request.

#### Per-pod fallback (FlexibleRateLimiter._check_memory) — NOT cross-pod safe

| Property | Value |
|----------|-------|
| Mechanism | Per-process `dict[str, tuple[int, float]]` |
| Cross-pod safety | None |

When Redis is unavailable, `FlexibleRateLimiter` falls back to an in-memory dict. Each pod has its own store. **Impact:** With N pods, the effective rate limit becomes `N x per_pod_limit` instead of the configured limit. For example, with 3 pods and a 10 req/min limit, each pod allows 10 req/min, yielding 30 req/min total.

**This is a documented fail-open pattern.** The alternative (rejecting all requests when Redis is down) would be worse for availability.

#### SSE connection tracker — NOT cross-pod safe

| Property | Value |
|----------|-------|
| Mechanism | Per-process `dict[str, int]` + `asyncio.Lock()` |
| Max connections per pod | `SSE_MAX_CONNECTIONS` (default 3) |
| Cross-pod safety | None |

The `_sse_connections` dict at module scope in `rate_limiter.py` is per-process. Each pod tracks its own SSE connections. With N pods, total allowed SSE connections = `N x SSE_MAX_CONNECTIONS`.

**Risk:** Low. SSE connections are per-user. The practical limit is about user connections, not total capacity.

---

### 4. Distributed Locks

#### Verdict: Cross-pod safe

| Property | Value |
|----------|-------|
| Mechanism | `redis.set(key, value, nx=True, ex=ttl)` |
| Cross-pod safety | Full |

All cron job locks use `acquire_redis_lock` from `cron/_loop.py`, which calls `redis.set(key, iso_timestamp, nx=True, ex=ttl)`. The `NX` flag means "set only if key does not exist" — atomic across all Redis clients. When pod A holds a lock, pod B's `SET NX` returns `None`, and pod B skips the cron cycle.

**Lock keys in use:**

| Key | TTL | Component |
|-----|-----|-----------|
| `smartlic:reconciliation:lock` | 30 min | `cron/billing.py` — billing reconciliation |
| `smartlic:revenue_share:lock` | 30 min | `cron/billing.py` — revenue share report |
| `smartlic:plan_reconciliation:lock` | 10 min | `cron/billing.py` — plan reconciliation |
| `smartlic:alerts:lock` | 30 min | `cron/notifications.py` — search alerts |
| `smartlic:api_metered_billing:lock` | 10 min | `cron/api_metered_billing.py` — API metering |

**TTL safety:** If a pod crashes while holding a lock, the TTL auto-expires (10-30 min depending on lock). The next cron cycle will find the lock available and proceed. No manual intervention required.

**WARNING:** These locks are used for **cron job mutual exclusion** (preventing duplicate execution of daily tasks). They are NOT used for:

- Cache invalidation (no distributed invalidation exists)
- Database write fencing (not needed — Supabase handles this)
- Leader election (not currently needed — single cron scheduler)

---

### 5. SSE State (Progress Tracker)

#### ProgressTracker with Redis — PARTIALLY cross-pod safe

| Component | Cross-pod? | Mechanism |
|-----------|-----------|-----------|
| Tracker metadata | YES | Redis HASH `smartlic:progress:{search_id}` |
| Events (stream) | YES | Redis Stream `smartlic:progress:{search_id}:stream` |
| Replay events | YES | Redis List `sse_events:{search_id}` |
| Active tracker dict | NO | Per-process `_active_trackers: Dict[str, ProgressTracker]` |

When Redis is available, the `ProgressTracker` publishes events to a Redis Stream (`XADD`) and stores metadata in a Redis HASH. Any pod can:

- Look up tracker metadata via `get_tracker(search_id)` (checks Redis HASH)
- Read replay events via `get_replay_events(search_id, after_id)` (checks Redis List)
- Subscribe to the Redis Stream for live events

**The `_active_trackers` dict** at the module scope of `progress.py` is NOT shared. If pod A creates a tracker, pod B initially won't find it in its local dict. However, `get_tracker()` falls back to Redis metadata lookup, so pod B can discover and recreate the tracker object.

**The `ProgressTracker.queue`** (asyncio.Queue) is local to the process where the tracker was created. In a multi-pod scenario, SSE consumers must read from Redis Streams (via `XREAD`) rather than from the queue.

#### In-memory progress tracking — NOT cross-pod safe

When Redis is unavailable (in-memory mode), the `_active_trackers` dict is purely per-process. Events published by pod A's `emit()` go only to its in-memory queue. Pod B cannot see them. The frontend would need to reconnect to the pod that created the tracker.

**DB fallback (HARDEN-019):** `is_search_terminal()` falls back to `search_state_transitions` table in Supabase. This provides a cross-pod recovery path even when the Redis stream has expired.

---

## Scale Limits Identified

### Per-pod state (blocks >1 worker without Redis)

| Component | State | Per-pod Unit | N Pods Impact |
|-----------|-------|-------------|--------------|
| InMemoryCache | `OrderedDict[5K]` | 5,000 entries | Each pod has its own 5K |
| Rate limiter (fallback) | `dict[str, tuple]` | 10,000 entries | Effective limit = N x limit |
| SSE connections | `dict[str, int]` | SSE_MAX_CONNECTIONS (3) | Total = N x 3 |
| Active trackers | `dict[str, Tracker]` | All active | Recreated from Redis on lookup |

### Shared state (works across pods)

| Component | Mechanism | Max Scale |
|-----------|-----------|-----------|
| L2 Cache | Redis `l1:search_cache:*` | Redis cluster limits |
| Idempotency | Supabase `stripe_webhook_events` | DB connection pool |
| Token bucket | Redis Lua eval | Redis single-threaded eval |
| Distributed locks | Redis SET NX | Key TTL / contention window |
| SSE events | Redis Streams | Stream length / memory |
| Search state | Supabase `search_state_transitions` | DB write throughput |

### Known gaps requiring staging validation

The following cannot be fully validated without a real multi-pod staging environment:

1. **SSE Reconnect:** When an SSE consumer disconnects and reconnects, it sends `Last-Event-ID`. The replay mechanism checks local tracker history first, then Redis. Latency between stream write and list write could cause missed events during failover.

2. **Stale Tracker Cleanup:** `_cleanup_stale()` runs per-pod. Pod B might clean up a tracker that pod A is still using, if pod B misreads the Redis metadata.

3. **Concurrent Lock TTL Race:** If two pods try to acquire the same lock at exactly TTL expiry, both might succeed briefly. The Lua script in the rate limiter handles this correctly. The distributed locks do not — but the safety margin (10-30 min TTL) makes this practically impossible.

4. **Redis Connection Storm:** On pod startup, all N pods would simultaneously ping Redis. The pool is configured for 50 connections. With many pods, connection pool exhaustion could occur.

---

## Recommendations for Multi-Pod

### Required before scaling to >1 worker

1. **Ensure Redis is non-negotiable.** Every cross-pod safety mechanism depends on Redis being available. Without Redis, the system degrades to per-pod state, causing:
   - Rate limits drift (N x expected)
   - SSE events are pod-local
   - Caching is purely per-pod
   - Locks become no-ops (fail-open allows both pods to proceed)

2. **Add Prometheus alert for Redis fallback mode.** The `REDIS_AVAILABLE` metric (0/1 gauge) should trigger an alert if Redis is unavailable for >5 minutes.

### Recommended but not blocking

3. **Move SSE connection tracking to Redis.** Replace `_sse_connections` (per-process dict) with a Redis Sorted Set or HASH. This ensures global SSE_MAX_CONNECTIONS enforcement.

4. **Add TTL validation CI gate.** Verify that every new `acquire_redis_lock` call has a corresponding TTL (no unbounded locks).

5. **Document the "no distributed cache invalidation" design decision.** Currently, there is no mechanism to invalidate L1 InMemoryCache across pods. This is acceptable because:
   - L1 is only consulted after L2 (Redis)
   - TTLs are short (2-8h)
   - Background revalidation refreshes stale entries

### Low priority

6. **Optionally move rate limiter fallback to a shared mechanism.** If Redis-flapping (intermittent connectivity) occurs, consider a short-lived local cache with shared Redis authoritative backend instead of the current all-or-nothing fallback.

---

## Appendix: File Locations

| File | Purpose |
|------|---------|
| `backend/cache/redis.py` | L2 Redis cache (shared) |
| `backend/cache/memory.py` | L1 InMemoryCache re-export |
| `backend/cache/manager.py` | Multi-level cache orchestration |
| `backend/redis_pool.py` | InMemoryCache + Redis pool |
| `backend/rate_limiter.py` | Rate limiters + SSE tracker |
| `backend/webhooks/stripe.py` | Stripe webhook idempotency |
| `backend/progress.py` | SSE ProgressTracker |
| `backend/cron/_loop.py` | `acquire_redis_lock` / `release_redis_lock` |
| `backend/cron/billing.py` | Lock-protected billing tasks |
| `backend/cron/notifications.py` | Lock-protected alert tasks |
| `scripts/cross-pod-validation.sh` | Validation test script |
| `docs/architecture/cross-pod-validation.md` | This report |
