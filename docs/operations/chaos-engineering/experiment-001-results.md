# Chaos Experiment #001: Results

> **DO NOT COMMIT WITH PLACEHOLDER VALUES.** Fill all `?` fields before committing.
> Copy this file for each experiment run: `experiment-001-results-YYYY-MM-DD.md`

---

**Date:** YYYY-MM-DD
**Executor:** NAME
**Scenario(s):** A / B / C / All
**Environment:** staging
**Duration (total):** ? minutes
**System version:** `git rev-parse HEAD` output

---

## Pre-Experiment State

| Check | Result | Notes |
|-------|--------|-------|
| `/health/live` | `200` | — |
| `/health/ready` | `200`, `healthy` | All checks ok |
| `/health` | `200`, `healthy` | All deps ok |
| Redis latency | `< 5ms` | Baseline |
| Supabase pool | `< 30%` | Active connections |

---

## Scenario A: Redis Latency Spike (500ms)

**Duration:** 5 minutes
**Injection method:** `tc qdisc add dev eth0 root netem delay 500ms`

### Observations

| Timestamp | Event | Observed |
|-----------|-------|----------|
| `T+0s` | Injection applied | ? |
| `T+10s` | Health check | ? |
| `T+30s` | Search request | ? |
| `T+60s` | Health check | ? |
| `T+120s` | Search request | ? |
| `T+180s` | Health check | ? |
| `T+240s` | ARQ check | ? |
| `T+300s` | Rollback applied | ? |
| `T+310s` | Recovery check | ? |

### Metrics

| Metric | Before | During (min) | During (max) | After |
|--------|--------|-------------|-------------|-------|
| `/health/ready` status | healthy | ? | ? | healthy |
| Redis check status | ok | ? | ? | ok |
| Search latency p95 (ms) | ? | ? | ? | ? |
| Error rate (%) | ? | ? | ? | ? |
| `redis_fallback_total` | 0 | ? | ? | ? |
| InMemoryCache hit rate (%) | ? | ? | ? | ? |
| Route timeouts | 0 | ? | ? | 0 |

### Grading

| Criteria | Pass/Fail | Evidence |
|----------|-----------|----------|
| System never returned 500 | ? | ? |
| Health checks showed degraded | ? | ? |
| Searches completed (maybe slower) | ? | ? |
| Recovery within 30s of rollback | ? | ? |
| No crash/restart of worker | ? | ? |
| DegradationBanner shown to user | ? | ? |

### Unexpected Behavior

- ?
- ?

---

## Scenario B: Redis Connection Refused

**Duration:** 5 minutes
**Injection method:** `iptables -A OUTPUT -p tcp --dport 6379 -j DROP`

### Observations

| Timestamp | Event | Observed |
|-----------|-------|----------|
| `T+0s` | Injection applied | ? |
| `T+10s` | Health check | ? |
| `T+30s` | Search request | ? |
| `T+60s` | Health check | ? |
| `T+120s` | Search request | ? |
| `T+180s` | Health check | ? |
| `T+240s` | ARQ check | ? |
| `T+300s` | Rollback applied | ? |
| `T+310s` | Recovery check | ? |

### Metrics

| Metric | Before | During (min) | During (max) | After |
|--------|--------|-------------|-------------|-------|
| `/health/ready` status | healthy | ? | ? | healthy |
| Redis check status | ok | ? | ? | ok |
| Search latency p95 (ms) | ? | ? | ? | ? |
| Error rate (%) | ? | ? | ? | ? |
| `redis_fallback_total` | 0 | ? | ? | ? |
| InMemoryCache hit rate (%) | ? | ? | ? | ? |
| ARQ queue depth (delta) | ? | ? | ? | ? |
| SSE progress (pass/fail) | pass | ? | ? | pass |

### Grading

| Criteria | Pass/Fail | Evidence |
|----------|-----------|----------|
| System never returned 500 | ? | ? |
| Health checks showed degraded | ? | ? |
| Searches completed via InMemoryCache | ? | ? |
| Recovery within 30s of rollback | ? | ? |
| ARQ worker recovered | ? | ? |
| No crash/restart | ? | ? |
| Rate limiter gracefully bypassed | ? | ? |

### Unexpected Behavior

- ?
- ?

---

## Scenario C: DB Connection Pool at 90%

**Duration:** 3 minutes
**Injection method:** Hold 23 connections via Python script

### Observations

| Timestamp | Event | Observed |
|-----------|-------|----------|
| `T+0s` | Injection applied | ? |
| `T+10s` | Health check | ? |
| `T+30s` | Search request | ? |
| `T+60s` | Health check | ? |
| `T+90s` | Search request | ? |
| `T+120s` | Health check | ? |
| `T+150s` | Search request | ? |
| `T+180s` | Rollback applied | ? |
| `T+190s` | Recovery check | ? |

### Metrics

| Metric | Before | During (min) | During (max) | After |
|--------|--------|-------------|-------------|-------|
| `/health/ready` status | healthy | ? | ? | healthy |
| Pool utilization (%) | ? | ? | ? | ? |
| Pool check status | ok | ? | ? | ok |
| Search latency p95 (ms) | ? | ? | ? | ? |
| Error rate (%) | ? | ? | ? | ? |
| `route_timeout_total` | 0 | ? | ? | 0 |
| 503 responses | 0 | ? | ? | 0 |
| Existing requests (pass/fail) | pass | ? | ? | pass |

### Grading

| Criteria | Pass/Fail | Evidence |
|----------|-----------|----------|
| System returned 503 (not crash) | ? | ? |
| /health/ready showed pool degraded | ? | ? |
| Existing requests completed | ? | ? |
| Recovery within 30s of rollback | ? | ? |
| No Sentry critical alert | ? | ? |
| Error message was meaningful | ? | ? |

### Unexpected Behavior

- ?
- ?

---

## Summary

| Scenario | Result | Action Items |
|----------|--------|--------------|
| A: Redis Latency | ? | ? |
| B: Redis Refused | ? | ? |
| C: DB Pool 90% | ? | ? |

### Key Findings

1. ?
2. ?
3. ?

### Action Items

| # | Item | Priority | Owner |
|---|------|----------|-------|
| 1 | ? | P0 | ? |
| 2 | ? | P1 | ? |
| 3 | ? | P2 | ? |

### Follow-up Experiments

- Experiment #002: ?
- Experiment #003: ?

---

## Attachments

- (link to monitoring dashboard screenshots)
- (link to Sentry timeline)
- (link to Prometheus query results)
