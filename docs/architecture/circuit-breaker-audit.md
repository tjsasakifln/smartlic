# Circuit Breaker Audit — Issue #1919

## Coverage Matrix

| Source | CB Class | Threshold | Cooldown | Redis | Metrics | Tested |
|--------|----------|-----------|----------|-------|---------|--------|
| PNCP | `PNCPCircuitBreaker`/`RedisCircuitBreaker` | 15 | 60s | Yes | Yes | Yes |
| PCP v2 | `PNCPCircuitBreaker`/`RedisCircuitBreaker` | 15 | 60s | Yes | Yes | Yes |
| ComprasGov v3 | `PNCPCircuitBreaker`/`RedisCircuitBreaker` | 15 | 60s | Yes | Yes | Yes |
| BrasilAPI | `PNCPCircuitBreaker`/`RedisCircuitBreaker` | 3 | 60s | Yes | Yes | Yes |
| IBGE | `PNCPCircuitBreaker`/`RedisCircuitBreaker` | 5 | 120s | Yes | Yes | Yes |
| Supabase (read) | `SupabaseCircuitBreaker` | 60%/3 streak | 30s | No | Yes | Yes |
| Supabase (write) | `SupabaseCircuitBreaker` | 60%/3 streak | 30s | No | Yes | Yes |
| Supabase (RPC) | `SupabaseCircuitBreaker` | 60%/3 streak | 30s | No | Yes | Yes |

## Threshold Rationale

### BrasilAPI (threshold=3, cooldown=60s)
BrasilAPI is called for CNPJ enrichment in the ingestion pipeline. It's a critical
but lightweight dependency — 3 failures (approx. 45s with default timeouts) is
enough to detect outage without excessive false positives. 60s cooldown allows
quick recovery since CNPJ data is non-critical for search results.

### IBGE (threshold=5, cooldown=120s)
IBGE is called for `indice_municipal` quarterly recalculation and municipio
data. It's a batch-oriented dependency with lower request volume. 5 failures
(approx. 75s) prevents flapping during transient network issues. 120s cooldown
accommodates longer recovery windows for government APIs.

## State Transitions

```
CLOSED --(threshold failures)-- OPEN
OPEN   --(cooldown expired)---- HALF_OPEN
HALF_OPEN --(success)---------- CLOSED
HALF_OPEN --(failure)---------- OPEN
```

## Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `smartlic_circuit_breaker_degraded` | Gauge | `source` | 1=degraded, 0=healthy (legacy) |
| `smartlic_cb_state` | Gauge | `source` | 0=closed, 1=open, 2=half_open |
| `smartlic_cb_open_duration_seconds` | Gauge | `source` | Time the CB has been in open state |
| `smartlic_circuit_breaker_trips_total` | Counter | `cb_type`, `cb_name` | Total trip events (#1800) |

## Admin Endpoint

```
GET /v1/admin/circuit-breakers
```

Returns:

```json
{
  "circuit_breakers": {
    "pncp": {
      "status": "healthy",
      "degraded": false,
      "failures": 0,
      "degraded_until": null,
      "opened_at": null,
      "open_duration_seconds": 0.0,
      "threshold": 15,
      "cooldown_seconds": 60,
      "backend": "local"
    }
  }
}
```

## Future Improvements

- Add per-source CB to all httpx-based external API calls in the ingestion pipeline
- Add CB to OpenAI/LLM API calls
- Implement circuit breaker metrics dashboard in Grafana
- Add automatic CB state alerts based on `smartlic_cb_open_duration_seconds`
