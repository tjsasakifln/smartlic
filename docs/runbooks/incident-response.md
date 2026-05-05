# Incident Response Runbook — SmartLic

**Issue #640 — MTTR target: <30 min**

This runbook provides structured diagnosis and remediation steps for each alert type.
Each section follows: Symptom → Diagnose → Fix → Rollback.

---

## Table of Contents

1. [Downtime / Service Unavailable](#1-downtime--service-unavailable)
2. [Pipeline Wedge (Sync .execute() / Budget Exceeded)](#2-pipeline-wedge)
3. [High Error Rate (HTTP 5xx spike)](#3-high-error-rate)
4. [Pool Saturation (DB / Redis)](#4-pool-saturation)
5. [Sentry Alert Rules to Configure Manually](#5-sentry-alert-rules)
6. [BetterStack External Probe Setup](#6-betterstack-external-probe)
7. [wedge_risk Field Reference](#7-wedge_risk-field-reference)

---

## 1. Downtime / Service Unavailable

**Symptom:** BetterStack probe returns non-200 for `/health/live`. Railway dashboard shows CRASHED or STOPPED replicas.

### Diagnose

```bash
# Check Railway deploy status and recent logs
railway logs --tail --service bidiq-backend | head -100

# Check recent GitHub Actions runs (billing-gate issue — CRIT-080)
gh api /repos/confenge/smartlic/actions/runs --jq '.workflow_runs[:5] | .[] | {status, conclusion, name, created_at}'

# Check readiness endpoint (should return 503 if unhealthy)
curl -s https://api.smartlic.tech/health/ready | jq .

# Check liveness (always 200 if process alive)
curl -s https://api.smartlic.tech/health/live | jq .

# Check if Supabase is reachable directly
curl -s "https://fqqyovlzdzimiwfofdjk.supabase.co/rest/v1/profiles?select=id&limit=1" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" | head -50
```

### Fix

1. **If Railway process crashed (SIGSEGV/OOM):**
   ```bash
   # Emergency redeploy — bypasses GH Actions
   railway redeploy --service bidiq-backend -y
   ```

2. **If Supabase is down (upstream):** Wait for Supabase status page. No action required.

3. **If GitHub Actions queued/null (billing gate CRIT-080):**
   - Check repo visibility first: public repos do NOT trigger billing issues.
   - Go to GitHub Settings > Billing & plans > Actions > resolve pending payment.

4. **If gunicorn/uvicorn runner issue (CRIT-084):**
   - Verify `RUNNER=uvicorn` in Railway env vars (NOT gunicorn).
   - If set incorrectly, fix via:
     ```bash
     railway variables set RUNNER=uvicorn --service bidiq-backend
     railway redeploy --service bidiq-backend -y
     ```

### Rollback

```bash
# Roll back to the previous known-good deploy
railway rollback --service bidiq-backend
```

---

## 2. Pipeline Wedge

**Symptom:** Searches hang, `wedge_risk=high` in `/health/ready`, Sentry alert `smartlic_pipeline_budget_exceeded_total > 2/5min`.

**Root cause pattern (CRIT-080/CRIT-083/CRIT-084):** A `.execute()` call runs synchronously inside an async route without `_run_with_budget` wrapping, blocking the event loop under load.

**CI Gate:** `.github/workflows/audit-execute-without-budget.yml` (RES-BE-001/015) blocks PRs that introduce new `.execute()` calls outside `_run_with_budget`. If you see a wedge pattern after a deploy, check if this CI gate was bypassed.

### Diagnose

```bash
# Check wedge_risk field
curl -s https://api.smartlic.tech/health/ready | jq '{wedge_risk, checks}'

# Check route timeouts (sync execute wedge indicator)
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_route_timeout_total'

# Check pipeline budget exceeded counter
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_pipeline_budget_exceeded'

# Check Railway logs for timeout/wedge signatures
railway logs --tail --service bidiq-backend | grep -E "budget_exceeded|timeout|wedge|execute"

# Check Sentry for recent pipeline errors
# Sentry: org=confenge, project=smartlic-backend
# Filter: tags[source]=pncp AND fingerprint contains "pipeline"
```

### Fix

1. **Immediate (no-code):** Reduce `ROUTE_TIMEOUT_S` to fail-fast sooner:
   ```bash
   railway variables set ROUTE_TIMEOUT_S=45 --service bidiq-backend
   # No redeploy needed — env var is read at startup
   railway redeploy --service bidiq-backend -y
   ```

2. **If a specific ARQ job is wedged:** Restart the worker:
   ```bash
   railway redeploy --service bidiq-worker -y
   ```

3. **Code fix (if CI gate was bypassed):** Wrap the offending `.execute()` call in `_run_with_budget`:
   ```python
   from pipeline.budget import _run_with_budget
   result = await _run_with_budget(
       coro=some_client.execute(params),
       budget_s=70,
       phase="per_source",
       source="pncp",
   )
   ```

4. **Emergency: disable route timeout (last resort):**
   ```bash
   railway variables set ROUTE_TIMEOUT_S=0 --service bidiq-backend
   railway redeploy --service bidiq-backend -y
   ```

### Rollback

```bash
# Roll back to commit before the offending PR was merged
railway rollback --service bidiq-backend
```

---

## 3. High Error Rate

**Symptom:** Sentry alert `HTTP 5xx rate > 10/min`. Users report search failures or 500 errors.

### Diagnose

```bash
# Check Prometheus 5xx counter
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_api_errors_total'

# Check recent error logs
railway logs --tail --service bidiq-backend | grep -E '"status":5[0-9][0-9]|ERROR|Exception|Traceback'

# Check Sentry for current error clusters
# Sentry project: smartlic-backend (ID: 4509666928623616)
# Filter: level=error, last 1h

# Check if Supabase is the source (DB errors cascade to 500s)
curl -s https://api.smartlic.tech/health/ready | jq '.checks'

# Check circuit breaker states
curl -s https://api.smartlic.tech/health | jq '.sources | to_entries[] | select(.value.circuit_breaker == "open")'
```

### Fix

1. **If PNCP circuit breaker is OPEN:**
   - The system will auto-recover via `try_recover()` on next health cycle.
   - If stuck: check PNCP API status at `https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao`.
   - Manual reset not required — circuit breaker auto-recovers after cooldown (60s).

2. **If Supabase errors:** Check Supabase dashboard for DB load/disk IO.
   - Quick check: increase `SUPABASE_STATEMENT_TIMEOUT` if queries are timing out:
     ```bash
     railway variables set SUPABASE_STATEMENT_TIMEOUT=20000 --service bidiq-backend
     ```

3. **If LLM errors (OpenAI 429/503):**
   - Set `LLM_ZERO_MATCH_ENABLED=false` to disable LLM classification:
     ```bash
     railway variables set LLM_ZERO_MATCH_ENABLED=false --service bidiq-backend
     ```

4. **If generic 500s with no clear cause:** Enable debug logging temporarily:
   ```bash
   railway variables set LOG_LEVEL=DEBUG --service bidiq-backend
   railway redeploy --service bidiq-backend -y
   # After diagnosis, revert:
   railway variables set LOG_LEVEL=INFO --service bidiq-backend
   ```

### Rollback

```bash
railway rollback --service bidiq-backend
```

---

## 4. Pool Saturation

**Symptom:** `wedge_risk=medium` or `wedge_risk=high` in `/health/ready`. Sentry alert `smartlic_redis_pool_connections_used > 80%`.

### Diagnose

```bash
# Get current wedge_risk and checks
curl -s https://api.smartlic.tech/health/ready | jq '{wedge_risk, checks}'

# Check Redis pool stats via Prometheus
curl -s https://api.smartlic.tech/metrics | grep -E 'smartlic_redis_pool_connections'

# Check Redis memory and connection info
railway run --service bidiq-backend python -c "
import asyncio
from redis_pool import get_redis_pool, get_pool_stats
async def main():
    r = await get_redis_pool()
    info = await r.info('all')
    print('connected_clients:', info.get('connected_clients'))
    print('used_memory_human:', info.get('used_memory_human'))
    print('rejected_connections:', info.get('rejected_connections'))
    print('pool_stats:', get_pool_stats())
asyncio.run(main())
"

# Check Supabase active connections (if DB pool saturated)
# Via Supabase Management API
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT count(*) as active_conns FROM pg_stat_activity WHERE state = '"'"'active'"'"'"}' | jq .
```

### Fix

1. **Redis pool near-saturation (medium, 50–80%):**
   - Increase `REDIS_MAX_CONNECTIONS`:
     ```bash
     railway variables set REDIS_MAX_CONNECTIONS=30 --service bidiq-backend
     railway redeploy --service bidiq-backend -y
     ```

2. **Redis pool fully saturated (high, >80%):**
   - Restart backend (clears all connections):
     ```bash
     railway redeploy --service bidiq-backend -y
     ```
   - If recurring: reduce `WEB_CONCURRENCY` by 1:
     ```bash
     railway variables set WEB_CONCURRENCY=2 --service bidiq-backend
     ```
   - Note: `WEB_CONCURRENCY=3` is the current Railway Pro setting (project_railway_pro_upgrade_2026_04_30).

3. **Supabase connection pool saturation:**
   - Verify `statement_timeout=15000` is set (FLOOR — see `reference_supabase_service_role_no_timeout_default.md`):
     ```sql
     -- Run via Supabase SQL editor or Management API
     ALTER ROLE service_role SET statement_timeout = '15s';
     ```
   - If overloaded by SSG build (see `feedback_build_hammers_backend_cascade.md`): deploy frontend with `AbortSignal.timeout` guards on SSG fetches.

### Rollback

Pool saturation issues are configuration-level. There is no code rollback — revert the env var changes:

```bash
railway variables set REDIS_MAX_CONNECTIONS=20 --service bidiq-backend
railway variables set WEB_CONCURRENCY=3 --service bidiq-backend
```

---

## 5. Sentry Alert Rules

These rules must be created **manually** in the Sentry UI:
- Org: `confenge`
- Project (backend): `smartlic-backend` (ID: 4509666928623616)
- Project (frontend): `smartlic-frontend` (ID: 4510878216224768)

### Rule 1: Pipeline Wedge Detected

- **Metric:** `smartlic_pipeline_budget_exceeded_total`
- **Condition:** Count > 2 in 5 minutes
- **Alert:** "Pipeline wedge detectado — `.execute()` sem `_run_with_budget` ou timeout de fase excedido"
- **Severity:** `error`
- **Fingerprint:** `["pipeline_wedge", "budget_exceeded"]`
- **Runbook link:** This document, section 2

### Rule 2: High Error Rate

- **Metric:** HTTP 5xx responses (via `smartlic_api_errors_total` or Sentry native issue volume)
- **Condition:** Count > 10 in 1 minute
- **Alert:** "High error rate — verifique logs do backend e circuit breakers"
- **Severity:** `error`
- **Fingerprint:** `["high_error_rate"]`
- **Runbook link:** This document, section 3

### Rule 3: DB Pool Approaching Saturation

- **Metric:** `smartlic_redis_pool_connections_used`
- **Condition:** Value > 80% of `smartlic_redis_pool_connections_max`
- **Alert:** "Redis pool saturation alta — risco de wedge iminente"
- **Severity:** `warning`
- **Fingerprint:** `["pool_saturation", "redis"]`
- **Runbook link:** This document, section 4

### How to Create in Sentry

1. Sentry > `confenge` org > `smartlic-backend` project
2. Alerts > Create Alert > Metric Alert
3. Set metric, threshold, and timewindow as above
4. Set notification to email: `tiago.sasaki@gmail.com`
5. Add runbook URL in the "Additional notes" field

---

## 6. BetterStack External Probe

BetterStack provides external uptime monitoring (HTTP probe from external IPs — cannot be spoofed by internal health).

**Setup is manual — ops performs once:**

1. Go to [betterstack.com](https://betterstack.com) > Sign up (free tier available)
2. Create monitor:
   - **URL:** `https://api.smartlic.tech/health/live`
   - **Method:** GET
   - **Expected status:** 200
   - **Check interval:** 1 minute
   - **Regions:** São Paulo (or nearest to Brazil)
3. Create second monitor:
   - **URL:** `https://smartlic.tech` (frontend)
   - **Method:** GET
   - **Expected status:** 200
4. Configure alert: email `tiago.sasaki@gmail.com` on downtime

**Why `/health/live` and not `/health/ready`:**
`/health/live` always returns 200 if the process is alive (HARDEN-016 AC1). `/health/ready` returns 503 during graceful shutdown drain — external probes should not alert during intentional deploys.

---

## 7. wedge_risk Field Reference

The `/health/ready` endpoint returns a `wedge_risk` field (Issue #640):

| Value | Meaning | Action |
|-------|---------|--------|
| `low` | All pools nominal, no budget exceeded | No action needed |
| `medium` | Redis pool 50–80% saturated | Monitor; prepare to scale |
| `high` | Pool >80% OR pipeline budget exceeded OR route timeouts triggered | Investigate immediately — see sections 2 and 4 |
| `unknown` | Could not compute (Redis offline or import error) | Check Redis first |

**Example:**

```bash
curl -s https://api.smartlic.tech/health/ready | jq '{ready, wedge_risk, checks}'
# {
#   "ready": true,
#   "wedge_risk": "low",
#   "checks": {
#     "redis": {"status": "up", "latency_ms": 3},
#     "supabase": {"status": "up", "latency_ms": 12},
#     "mixpanel": {"status": "configured"}
#   }
# }
```

`wedge_risk` is **additive** — it never changes the HTTP status code of `/health/ready`. A `wedge_risk=high` with `ready=true` means the system is serving requests but accumulating risk.

---

## CRIT-080 Pattern Reference

**CRIT-080:** `jemalloc LD_PRELOAD` + `Sentry StarletteIntegration` + `cryptography>=46` caused SIGSEGV on POST requests (auth → TLS handshake in forked Gunicorn child). GET requests worked; POST crashed.

**Current fix (CRIT-084):** `RUNNER=uvicorn` with `--workers` flag uses `multiprocessing.spawn()` not `os.fork()` — eliminating the SIGSEGV.

**If SIGSEGV pattern re-emerges:**
1. Check `requirements.txt` for `cryptography` version (must NOT be fork-safe assumption).
2. Verify `RUNNER=uvicorn` in Railway env.
3. Never re-enable `RUNNER=gunicorn` without staging validation.

See `backend/CHANGELOG.md` and `CRIT-080/CRIT-084` entries for full history.
