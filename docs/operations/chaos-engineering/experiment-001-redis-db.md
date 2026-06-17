# Chaos Experiment #001: Redis Failure + DB Failover

> **Status:** Draft
> **Owner:** @devops (Gage)
> **Environment:** staging
> **Blast Radius:** Single service `bidiq-backend` in staging only. No production traffic.
> **Issue:** #1922

---

## Hypothesis

**Primary:** SmartLic remains operational (graceful degradation) when Redis becomes unavailable. All user-facing functionality degrades predictably with documented fallback behavior. The system never crashes, hangs indefinitely, or returns 500 errors due to Redis unavailability.

**Secondary:** When the Supabase connection pool reaches 90% utilization, new requests return 503 with a meaningful error message rather than hanging or crashing the process. Existing in-flight requests continue to completion.

**Tertiary:** Recovery is fully automatic within 30 seconds of failure condition removal. No manual intervention required (except restarting ARQ worker if it lost Redis entirely).

---

## Steady State Metrics

Before injecting chaos, confirm the following baseline:

| Metric | Target | Measurement |
|--------|--------|-------------|
| Health liveness (`/health/live`) | `200` | curl check |
| Health readiness (`/health/ready`) | `200`, status `healthy` | curl + parse |
| Health comprehensive (`/health`) | `200`, status `healthy` | curl |
| Redis component status | `"status": "ok"` | from `/health/ready` |
| Supabase component status | `"status": "ok"` | from `/health/ready` |
| Supabase pool utilization | `< 50%` | from `/health/ready` |
| Search latency p95 (recent) | `< 2s` | Prometheus / Mixpanel |
| Error rate (recent 5m) | `< 1%` | Prometheus / Sentry |
| Redis fallback counter | 0 | `smartlic_redis_fallback_total` Prometheus |
| Circuit breaker state (redis) | `closed` | from `/health` |

---

## Scenarios

### Scenario A: Redis Latency Spike (500ms added delay)

**Method:** Add artificial latency to the Redis port using `tc` (traffic control) on the staging server.

```bash
# Inject: add 500ms latency to Redis traffic (port 6379)
tc qdisc add dev eth0 root netem delay 500ms 100ms distribution normal

# Verify:
ping <redis-host>  # should show ~500ms

# Remove:
tc qdisc del dev eth0 root netem
```

**Expected Behavior:**

| Component | Expected Response |
|-----------|-------------------|
| `/health/ready` | `status: degraded`, redis check shows `degraded` with `error: timeout` |
| `/health/live` | `200` (always live) |
| Search (GET) | InMemoryCache fallback, higher latency, eventual success |
| ARQ Queue | Redis operations internally retry, rate limiter degraded |
| SSE state | Degraded — state stored in memory only |
| Cache reads | `safe_redis_call` times out after 500ms → InMemoryCache hit |
| Cache writes | `safe_redis_call` times out after 1s → falls through silently |
| Circuit breaker state | Stored in memory, not persisted to Redis |
| User experience | Slightly slower searches, potentially stale cache data |

**Duration:** 5 minutes

**Metrics to Watch:**
- `smartlic_redis_fallback_total{reason="timeout"}` — should increase
- `/health/ready` → `checks.redis` → `degraded`
- Search response time p95
- Redis InMemoryCache hit rate

**Rollback:**
```bash
tc qdisc del dev eth0 root netem
# Verify: ping <redis-host> should return to normal latency
```

---

### Scenario B: Redis Connection Refused

**Method:** Block all traffic to Redis port using `iptables`.

```bash
# Inject: DROP all outbound traffic to Redis port
sudo iptables -A OUTPUT -p tcp --dport 6379 -j DROP

# Verify:
redis-cli -h <redis-host> ping  # should hang/refuse

# Remove:
sudo iptables -D OUTPUT -p tcp --dport 6379 -j DROP
```

**Expected Behavior:**

| Component | Expected Response |
|-----------|-------------------|
| `/health/ready` | `status: degraded`, redis check shows `degraded` with `error: connection error` |
| `/health/live` | `200` (always live) |
| Cache reads | `get_redis_pool()` returns `None` → InMemoryCache hit |
| Cache writes | Silently skipped — Prometheus counter incremented |
| ARQ Queue | `is_queue_available()` returns `False` |
| SSE state | Falls back to in-memory state |
| Rate limiter | Bypassed (no Redis token bucket) |
| Circuit breaker | Stored in memory, survives until process restart |
| User experience | Transparent — no visible errors, may see DegradationBanner |
| ARQ Worker process | If running, it will be unable to process jobs |
| Background jobs | Scheduled cron jobs will fail (no ARQ) |

**Duration:** 5 minutes

**Metrics to Watch:**
- `smartlic_redis_fallback_total{reason="connection_error"}` — should increase
- `REDIS_FALLBACK_TOTAL{module="",method="",reason="connection_error"}`
- `/health/ready` checks → degraded
- ARQ queue depth (if ARQ is still pushing jobs)
- SSE progress updates (should continue via in-memory)

**Rollback:**
```bash
sudo iptables -D OUTPUT -p tcp --dport 6379 -j DROP
# Verify: redis-cli ping should work
```

---

### Scenario C: DB Connection Pool at 90% Utilization

**Method:** Open multiple Supabase connections and hold them open, then trigger a search request.

```bash
# Script to open and hold connections (uses supabase_client internals)
# Connection pool max is 25 (SUPABASE_POOL_MAX_CONNECTIONS)
# Target: 90% utilization = 23 active connections

# Open 23 connections and hold them:
python3 -c "
import httpx, os, asyncio

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']

async def hold_connection(n):
    headers = {'apikey': SUPABASE_KEY, 'Authorization': f'Bearer {SUPABASE_KEY}'}
    async with httpx.AsyncClient() as client:
        # Keep connection idle but alive
        await asyncio.sleep(300)
    
async def main():
    tasks = [hold_connection(i) for i in range(23)]
    await asyncio.gather(*tasks)

asyncio.run(main())
" &
HOLD_PID=$!
echo "Holding connections with PID $HOLD_PID"
```

**Expected Behavior:**

| Component | Expected Response |
|-----------|-------------------|
| `/health/ready` | `pool.utilization_pct > 85%` → `degraded` |
| `/health/live` | `200` (always live) |
| **New search requests** | May get 503 from route timeout or Supabase errors |
| **Existing requests** | Continue to completion |
| **User experience** | Some searches may fail with "service temporarily unavailable" |
| **Middleware** | Route-level timeout returns 503 before pool completely deadlocks |

**Duration:** 3 minutes

**Metrics to Watch:**
- `_pool_active_count` / `_POOL_MAX_CONNECTIONS` ratio in `/health/ready`
- `HEALTH_CHECK_FAILURES{check="supabase"}` — may increment
- Search error rate
- `smartlic_route_timeout_total` — may increase
- `smartlic_pipeline_budget_exceeded_total` — may increase

**Rollback:**
```bash
kill $HOLD_PID
# Verify: pool utilization returns to normal
```

---

## Experiment Execution Procedure

### Pre-flight Checklist

- [ ] Staging environment confirmed healthy (all checks green)
- [ ] No production traffic routed through staging
- [ ] Monitoring dashboard open (Prometheus + Sentry)
- [ ] Blast radius confirmed: staging only
- [ ] Rollback plan reviewed and understood
- [ ] Incident response runbook ready
- [ ] Communication channel open (Slack #ops)
- [ ] Experiment start time recorded
- [ ] Backup of current staging state (optional)

### Execution

1. Record pre-experiment metrics
2. Execute chosen scenario (A, B, or C)
3. Observe system behavior for specified duration
4. Record observations every 30 seconds
5. Execute rollback
6. Record post-experiment metrics
7. Allow 5 minutes for system stabilization
8. Run next scenario (optional)

### Post-experiment

1. Collect all metric snapshots
2. Document findings in `experiment-001-results.md`
3. Flag any unexpected behavior as a bug
4. Review and update runbooks
5. Share results with the team

---

## Monitoring Commands

```bash
# Continuous health monitoring (use health-check-loop.sh)
./scripts/chaos/health-check-loop.sh --url https://staging.smartlic.tech --interval 5

# Redis specific checks
redis-cli -h <redis-host> ping
redis-cli -h <redis-host> info memory | grep used_memory_human

# Prometheus metrics (raw)
curl -s https://staging.smartlic.tech/metrics | grep -E "redis_fallback|circuit_breaker|pool_active"

# Supabase pool check
curl -s https://staging.smartlic.tech/health/ready | python3 -m json.tool
```

---

## Known Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Script doesn't fully revert | Low | Staging degraded | Document manual cleanup; test rollback first |
| Worker crashes and doesn't restart | Medium | No background jobs | Railway auto-restarts; health-check-loop alerts |
| Connection pool deadlock | Low | All requests hang | Route timeout returns 503; hard limit at pool level |
| iptables persists across reboots | Low | Redis always blocked | Use `--wait` or script cleanup in pre-experiment |
| tc rules conflict with existing qdisc | Medium | Rule not applied | Check `tc qdisc show` before applying |
| Staging pointed at production Redis | High! | Production impacted | **Verify `REDIS_URL` in staging before experiment** |

---

## Architecture Context

### Redis Dependencies

| Module | Redis Usage | Fallback Behavior |
|--------|-------------|-------------------|
| `redis_pool.py` | Connection pool | Returns `None` → InMemoryCache |
| `redis_resilience.py` | `safe_redis_call` | Timeout → fallback value + Prometheus counter |
| `job_queue.py` (ARQ) | Queue storage | `is_queue_available()` → `False` |
| `rate_limiter.py` | Token bucket | Rate limiting bypassed |
| `search_cache.py` | L2 cache | Falls back to L1 InMemoryCache |
| `pncp_client.py` | Circuit breaker state | Stored in memory only |
| `middleware.py` | SSE state | Falls back to in-memory tracking |
| `cron_jobs.py` | Distributed locks | Locks bypassed (risk of duplicate execution) |
| `progress.py` | SSE progress | Falls back to in-memory Queue |

### Supabase Dependencies

| Module | DB Usage | Fallback Behavior |
|--------|----------|-------------------|
| `supabase_client.py` | Query execution | `_run_with_budget` → TimeoutError → 503 |
| `health.py` | Health persistence | CircuitBreaker → graceful skip |
| `datalake_query.py` | Search queries | Timeout → falls through to live API |
| `auth.py` | Auth verification | Returns Unauthorized |

---

## References

- `backend/redis_pool.py` — Redis connection pool + InMemoryCache
- `backend/redis_resilience.py` — `safe_redis_call` wrappers
- `backend/supabase_client.py` — Supabase client + pool monitoring
- `backend/routes/health_core.py` — Health endpoints (`/health/live`, `/health/ready`, `/health`)
- `backend/health.py` — System health logic + incident detection
- `backend/middleware.py` — Route timeout middleware (RES-BE-016 AC4)
- `backend/job_queue.py` — ARQ job queue (Redis-backed)
- `docs/operations/monitoring.md` — Monitoring dashboard
- `docs/operations/incident-playbook.md` — Incident response
