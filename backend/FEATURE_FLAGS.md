# Feature Flags — SmartLic Backend

This document is the source of truth for all feature flags in the SmartLic backend. Updated as part of DEBT-128 AC2, AC7, AC8.

---

## PERMANENT (Operational Toggles)

These flags control infrastructure and operational behavior. They are expected to live indefinitely.

| Flag | Default | File | Purpose | When to Toggle |
|------|---------|------|---------|---------------|
| `METRICS_ENABLED` | `true` | `config/features.py` | Prometheus metrics collection | Disable if metrics endpoint causes performance issues |
| `FILTER_DEBUG_MODE` | `false` | `config/features.py` | Verbose filter debug logging | Enable temporarily when debugging filter behavior |
| `HEALTH_CANARY_ENABLED` | `true` | `config/pipeline.py` | PNCP health canary checks every 5 min | Disable if canary causes PNCP rate limiting |
| `WARMUP_ENABLED` | `true` | `config/pipeline.py` | Startup cache warm-up | Disable if warmup causes slow startup |
| `CACHE_LEGACY_KEY_FALLBACK` | `true` | `config/pipeline.py` | Fallback to legacy cache key format | Disable after all caches have migrated to new keys |
| `SHOW_CACHE_FALLBACK_BANNER` | `true` | `config/pipeline.py` | Show cache fallback banner in frontend | Disable when cache migration is complete |
| `CACHE_WARMING_POST_DEPLOY_ENABLED` | `true` | `config/pipeline.py` | Cache warming after deploy | Disable if post-deploy warming causes startup issues |
| `ALERTS_ENABLED` | `true` | `config/pipeline.py` | Alert notifications cron job | Disable to stop alert emails |
| `RECONCILIATION_ENABLED` | `true` | `config/pipeline.py` | Reconciliation cron job | Disable to stop reconciliation |
| `COMPRASGOV_ENABLED` | `false` | `config/pncp.py` | ComprasGov v3 data source (API down since 2026-03-03) | Enable when ComprasGov API is back online |
| `COMPRASGOV_CB_ENABLED` | `true` | `config/pncp.py` | ComprasGov circuit breaker | Disable only to bypass CB for testing |
| `USE_REDIS_CIRCUIT_BREAKER` | `true` | `config/pncp.py` | Redis-backed circuit breaker | Set to `false` to roll back to in-memory CB |

---

## EXPERIMENTAL (Actively Being Tested)

These flags gate features that are implemented but not yet validated for general use. Review periodically — if a flag has been `false` for 90+ days without activation, consider whether the feature is still planned.

| Flag | Default | File | Purpose | When to Toggle |
|------|---------|------|---------|---------------|
| `ASYNC_ZERO_MATCH_ENABLED` | `false` | `config/features.py` | Async job queue for zero-match classification | Enable to test ARQ-based zero-match processing |
| `SEARCH_ASYNC_ENABLED` | `false` | `config/pipeline.py` | Async search via ARQ job queue (202 pattern) | Enable for async-first search architecture |
| `CACHE_WARMING_ENABLED` | `false` | `config/pipeline.py` | Proactive cache warming on schedule | Enable after performance validation |
| `CACHE_REFRESH_ENABLED` | `false` | `config/pipeline.py` | Periodic cache refresh job | Enable after stability validation |
| `TERM_SEARCH_LLM_AWARE` | `false` | `config/features.py` | LLM-aware term search quality parity | Enable when STORY-267 AC2 is ready |
| `TERM_SEARCH_SYNONYMS` | `false` | `config/features.py` | Synonym expansion for term search | Enable when STORY-267 AC4 is ready |
| `TERM_SEARCH_VIABILITY_GENERIC` | `false` | `config/features.py` | Generic viability scoring for term search | Enable when STORY-267 is ready |
| `TERM_SEARCH_FILTER_CONTEXT` | `false` | `config/features.py` | Filter context propagation for term search | Enable when STORY-267 is ready |
| `DIGEST_ENABLED` | `false` | `config/pipeline.py` | Email digest cron job | Enable when digest feature is complete |

---

## FEATURE GATES (Incomplete Features — SHIP-002)

These flags gate features that are not yet shipped. They will be removed once each feature reaches production.

| Flag | Default | File | Purpose |
|------|---------|------|---------|
| `ORGANIZATIONS_ENABLED` | `false` | `config/pipeline.py` | Organizations feature (SHIP-002) |
| `MESSAGES_ENABLED` | `false` | `config/pipeline.py` | Messages feature (SHIP-002) |
| `ALERTS_SYSTEM_ENABLED` | `false` | `config/pipeline.py` | Alerts system feature (SHIP-002) |
| `PARTNERS_ENABLED` | `false` | `config/pipeline.py` | Partners feature (SHIP-002) |

---

## ALWAYS-ON (Candidates for Future Cleanup)

These flags default to `true` and still have conditional `if` checks in the code. If they remain `true` for 30+ consecutive days without being toggled, they are candidates for permanent removal: keep the `True` code path, delete the flag and the dead `False` branch.

| Flag | Default | Purpose |
|------|---------|---------|
| `LLM_FALLBACK_PENDING_ENABLED` | `true` | Return fallback summary if LLM job is pending |
| `TRIAL_EMAILS_ENABLED` | `true` | Send trial reminder emails at day 7 |
| `TRIAL_PAYWALL_ENABLED` | `true` | Enforce trial paywall after day 7 |
| `ZERO_RESULTS_RELAXATION_ENABLED` | `true` | Auto-relax filters when zero results are returned |
| `BID_ANALYSIS_ENABLED` | `true` | Bid analysis feature |
| `CO_OCCURRENCE_RULES_ENABLED` | `true` | Keyword co-occurrence rules |
| `RATE_LIMITING_ENABLED` | `true` | Redis token-bucket rate limiting |
| `SECTOR_RED_FLAGS_ENABLED` | `true` | Sector-specific red flag detection |

---

---

## REMOVED (DEBT-128)

These flags were permanently enabled and the flag + dead code path has been deleted. The `true` code path remains.

| Flag | Removed Date | Reason |
|------|-------------|--------|
| `VIABILITY_ASSESSMENT_ENABLED` | 2026-03-11 | Stable since Feb 2026, promoted to core feature |
| `SYNONYM_MATCHING_ENABLED` | 2026-03-11 | Was always `true`, conditional branch never exercised |
| `LLM_ZERO_MATCH_BATCH_ENABLED` | 2026-03-11 | Batch mode always-on |
| `LLM_STRUCTURED_OUTPUT_ENABLED` | 2026-03-11 | Structured JSON always-on |
| `TRIAL_14_DAYS_ENABLED` | 2026-03-11 | Always true, no code references |
| `LLM_ARBITER_ENABLED` | 2026-06-06 | Always-on since Oct 2025 (>8 months stable) |
| `LLM_ZERO_MATCH_ENABLED` | 2026-06-06 | Always-on since Oct 2025 (>8 months stable) |
| `PARTIAL_DATA_SSE_ENABLED` | 2026-06-06 | Always-on since Dec 2025 (>6 months stable) |
| `PROXIMITY_CONTEXT_ENABLED` | 2026-06-06 | Always-on since Dec 2025 (>6 months stable) |
| `TRIGRAM_FALLBACK_ENABLED` | 2026-06-06 | Always-on since Mar 2026 (>3 months stable) |

---

## Adding a New Feature Flag

Follow these steps every time a new flag is introduced.

### 1. Naming

Use `UPPER_SNAKE_CASE` with an `_ENABLED` suffix for boolean flags. Be specific — the name should make the purpose obvious without reading the code (e.g., `CACHE_REFRESH_ENABLED`, not `NEW_CACHE`).

### 2. Definition

Add the flag to the appropriate config file:

- `config/features.py` — AI/LLM, search quality, UX feature flags
- `config/pipeline.py` — pipeline orchestration, cron jobs, cache strategy flags
- `config/pncp.py` — data source flags (PNCP, PCP, ComprasGov)

```python
# config/features.py (example)
MY_FLAG_ENABLED: bool = Field(
    default=False,
    description="Short description of what this flag controls.",
)
```

### 3. Default Value

- New experimental features: default `false`
- Operational toggles (infrastructure, safety nets): default `true`
- Never default `true` for an incomplete feature that could break production

### 4. Re-export

Add the flag to `config/__init__.py` so existing `from config import MY_FLAG_ENABLED` imports continue to work:

```python
# config/__init__.py
from config.features import MY_FLAG_ENABLED
```

### 5. Runtime Registry (if reloadable)

If the flag should be reloadable at runtime without a deploy, add it to `_FEATURE_FLAG_REGISTRY` in `config/features.py`:

```python
_FEATURE_FLAG_REGISTRY["MY_FLAG_ENABLED"] = lambda: settings.MY_FLAG_ENABLED
```

### 6. Admin UI Description

Add a human-readable description to `_FLAG_DESCRIPTIONS` in `routes/feature_flags.py` so the admin panel shows context:

```python
_FLAG_DESCRIPTIONS["MY_FLAG_ENABLED"] = "Enables X behavior. Safe to toggle without deploy."
```

### 7. Documentation

Add the flag to this file under the correct category (Permanent, Experimental, or Feature Gate) with:
- Default value
- Config file
- Purpose (one sentence)
- When to toggle (for Permanent) or readiness condition (for Experimental)

### 8. Lifecycle and Removal

Set a review date in the PR description when adding the flag. Removal criteria:

| Category | Removal trigger |
|----------|----------------|
| Experimental (`false`) | Flag has been `false` for 90+ days without activation — feature is no longer planned |
| Experimental (`true`) | Flag has been `true` for 30+ days without being toggled — promote to permanent code |
| Always-on (`true`) | Flag has been `true` for 30+ days without being toggled — delete flag and dead `false` branch |
| Feature Gate | Feature ships to production — delete flag, keep `true` path |
| Permanent | Operational concern no longer exists — confirm with team before removing |

**Removal checklist:**
1. Delete the flag constant from the config file
2. Delete the `false` (dead) branch from all conditional checks
3. Keep the `true` code path as unconditional code
4. Remove from `config/__init__.py` re-exports
5. Remove from `_FEATURE_FLAG_REGISTRY` and `_FLAG_DESCRIPTIONS`
6. Move the flag to the REMOVED table in this file with the removal date and reason
7. Search the codebase for any remaining references (`grep -r "MY_FLAG_ENABLED"`)
