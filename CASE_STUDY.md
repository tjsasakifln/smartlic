# SmartLic — Engineering Case Study

> **Audience:** recruiters, tech leads, founders evaluating technical capability.
> **Purpose:** demonstrate system design, architecture decisions, production operations,
> and engineering judgment — not pitch the business.
> **Author:** Tiago Sasaki, solo technical founder.
> **Date:** 2026-06-08

---

## 1. Problem

Brazil's government buys $500B+/year in goods and services through public tenders. The official
procurement portal (PNCP) publishes ~10,000 tenders per day across 5,000+ agencies. A supplier
in, say, the cleaning services sector must manually scan hundreds of daily listings to find the
2-3 that match — spread across 3 government portals, each with different APIs, schemas, and
reliability characteristics.

**The engineering problem:** ingest, normalize, deduplicate, classify, and deliver relevant
tenders to B2G suppliers at scale, with low latency, at a cost structure viable for a SaaS
business charging R$297–997/month.

---

## 2. Domain Constraints

Government procurement data is hostile to automation:

- **Schema instability.** PNCP's API silently changed `tamanhoPagina` max from 500 to 50 in
  February 2026. Requests with >50 returned HTTP 400 with no error body. Detection required a
  dedicated canary cron job probing the boundary every 10 minutes.
- **Ambiguous descriptions.** A tender titled "MELHORIAS URBANAS [...] incluindo uniformes"
  for R$47.6M is 99% infrastructure, 1% uniforms. Keyword-only matching misclassifies this as
  relevant to a uniform supplier. Requires semantic understanding.
- **Multi-source duplication.** The same tender appears on PNCP, ComprasGov, and PCP v2 with
  different identifiers, field names, and value formats. Deduplication requires fuzzy matching
  across inconsistent schemas.
- **Latency budget.** Users abandon search after ~30 seconds. A naive multi-source fetch
  (27 states × 6 modalities × 3 sources = 486 requests) would take minutes.
- **Cost per classification.** At 10,000 tenders/day, naive GPT-4 classification would cost
  ~$50/day. LLM must be applied selectively to ambiguous cases only.

---

## 3. Architecture

### 3-Layer Data Architecture

```
Layer 1: Periodic Ingestion (ETL → Supabase)
  ARQ cron: full daily (2am BRT), incremental 3×/day (8am/2pm/8pm BRT)
  27 UFs × 6 modalities, 5 concurrent, 2s delay between batches
  Content hash dedup, GIN full-text index (Portuguese)
  Retention: 400 days (tenders), unlimited (contracts)

Layer 2: Search Pipeline (queries local DB)
  PostgreSQL full-text search via `search_datalake` RPC
  <100ms p95 — no live API calls during search
  tsquery Portuguese, UF/date/modality/value/esfera filters
  Async-first: POST /buscar → 202, results via SSE

Layer 3: Results Cache (passive, per-request)
  L1 InMemoryCache (4h, LRU 10k) → L2 Redis (4h) → L3 Supabase (24h)
  SWR: serve stale on cache miss, trigger background refresh
  No proactive warming — DataLake p95 <100ms made it waste
```

**Key decision: query local, not live.** Search queries the DataLake (PostgreSQL), not the
government APIs. The live PNCP/PCP/ComprasGov APIs are fallback only — used when the DataLake
returns 0 results or the feature flag is toggled. This eliminates external dependency latency
from the hot path.

### Time Budget Waterfall

Every search request carries a deterministic timeout chain:

```
Railway proxy     [========================== 120s ==========================]
Gunicorn worker   [======================= 110s ========================]
Pipeline budget   [==================== 100s ====================]
  Consolidation   [================== 90s ===================]
    PerSource     [============= 70s =============]
      PerUF       [===== 25s =====]
        httpx r/w [10c+15r]
```

Invariant: `pipeline(100) > consolidation(90) > per_source(70) > per_uf(25) > (per_modality 20 + httpx 15)`.
Enforced by `backend/tests/test_timeout_invariants.py`. Timeout is applied via `_run_with_budget`
which wraps every pipeline call site.

**Route-level safety net:** asyncio timeout middleware at 60s returns 503 before Railway's 120s
proxy kill. SSE, health, and webhook routes exempt.

### API Surface

187 endpoints across 65 registered routers. FastAPI with Pydantic v2 — every route declares
`response_model=`, which auto-generates the OpenAPI schema. This schema is checked into the
frontend repo via `openapi-typescript`, CI-gated against drift.

### Frontend

Next.js 16 App Router, ~25 core pages + 10k+ programmatic SEO pages (ISR `revalidate=3600`).
Search page is the activation surface — SSE progress streaming, filter panel with UF grid,
results grid with viability badges. Kanban pipeline for opportunity management via `@dnd-kit`.

---

## 4. Data Pipeline

### Ingestion

```
PNCP API ──┐
ComprasGov ──┼──→ crawler.py ──→ transformer.py ──→ loader.py ──→ pncp_raw_bids
PCP v2    ──┘         │                  │                │
                       │                  │                └── upsert_pncp_raw_bids RPC
                       │                  │                    (500 rows/batch, content_hash dedup)
                       │                  └── normalize fields, extract CNPJ,
                       │                      compute content_hash, map modalities
                       └── paginate, retry (exponential backoff),
                           circuit break (15 failures → 60s cooldown)
```

- **Checkpoint system:** `ingestion_checkpoints` + `ingestion_runs` tables enable resume from
  the last successful page after failure. No re-crawling from scratch.
- **pg_cron backup:** `purge-old-bids` runs server-side via PostgreSQL cron scheduler — works
  even if Railway worker is offline. Monitored hourly with Sentry alert if stale (>25h).
- **Supplier contracts:** separate 3×/week crawl of `pncp_supplier_contracts`. 2M+ rows feed
  SEO programmatic pages (CNPJ-level supplier profiles, agency spending analysis).

### Deduplication

5-layer engine, applied during consolidation:
1. **Content hash** — SHA-256 of normalized description + UF + modality (fastest, catches most)
2. **PNCP ID match** — exact match on government-assigned identifier
3. **Title similarity** — Levenshtein distance on normalized titles
4. **Cross-source fuzzy** — value range overlap + date proximity + title similarity
5. **Priority resolution** — PNCP=1 > PCP=2 > ComprasGov=3 when duplicates span sources

### Full-Text Search

PostgreSQL GIN index with `tsvector` (Portuguese dictionary). The `search_datalake` RPC
accepts: text query, UF list, date range, value range, modalities, esfera (federal/state/municipal),
status filter, sector filter. Returns ranked results with ts_rank normalization.

---

## 5. AI Classification Pipeline

This is the subsystem that differentiates SmartLic from a simple search engine.

### Hybrid Pipeline (3 Tiers)

```
Tender text
    │
    ▼
[Tier 1: Deterministic Filters]
    ├── UF match (exact)
    ├── Value range check
    ├── Date range check
    └── Modality filter
    │ ~80% eliminated here, zero LLM cost
    ▼
[Tier 2: Keyword Density Scoring]
    ├── Sector keywords from sectors_data.yaml (20 sectors)
    ├── Density = matched_keywords / total_tokens
    ├── >5% density → "keyword" (automatic approve, no LLM)
    ├── 2-5% density → "llm_standard" (LLM double-check)
    ├── 1-2% density → "llm_conservative" (higher bar for approval)
    └── <1% density → "llm_zero_match" (LLM decides YES/NO)
    │ ~95% handled by tiers 1+2
    ▼
[Tier 3: LLM Arbiter] (~5% of volume, ~2-4% of cost)
    ├── GPT-4.1-nano with structured output (JSON schema)
    ├── Prompt includes: sector definition, keywords, context_required_keywords
    ├── Must cite EVIDENCE from tender text for each classification
    ├── temperature=0 (deterministic, no creative variance)
    └── Fallback: PENDING_REVIEW on malformed JSON or timeout
```

### Anti-Hallucination Measures

1. **Structured output only.** LLM response is parsed against a Pydantic schema. Malformed
   responses are rejected — the system falls back to PENDING_REVIEW, never passes bad data
   to the user.
2. **Evidence requirement.** The prompt requires the LLM to quote the relevant text snippet
   that supports its classification. This is checked for presence (non-empty string) in
   post-processing.
3. **Schema canary.** PNCP response shape is validated against a JSON Schema snapshot
   (`contracts/schemas/pncp_search_response.schema.json`) every 10 minutes. Shape drift
   triggers Sentry fatal alert.
4. **Bounded role.** The LLM is an *arbiter*, not a *generator*. Its output space is
   `{APPROVE, REJECT}` with required evidence. No free-text generation in the classification
   path. Executive summaries are a separate, non-critical path.
5. **Cost control.** LLM is invoked only for ambiguous cases (~2-4% of tender volume).
   Classification cost is tracked per sector, per search session. Prometheus counter
   `smartlic_llm_fallback_rejects_total` surfaces misclassification trends.

### Classification SLA

- **Precision ≥ 85%** — measured against 15 labeled samples/sector (300-label evaluation set)
- **Recall ≥ 70%** — same benchmark
- **Benchmark re-run** on every prompt change via `tests/test_llm_arbiter_benchmark.py`

The SLA acknowledges that perfect classification is impossible with ambiguous government text.
The system optimizes for precision over recall (false positives erode trust more than false
negatives). Users can submit feedback on misclassifications, which feeds a bi-gram analysis
for false positive exclusion rule suggestions.

---

## 6. Billing & Quota

Stripe integration with 9 plans, 12 webhook events, and idempotency via `events_processed` table.

### Key Decisions

- **Atomic quota enforcement.** `check_and_increment_quota_atomic` RPC runs in a Supabase
  transaction — no race condition between check and increment.
- **Fail to last known plan.** On transient DB error during plan lookup, the system retains
  the previously cached plan. Never falls back to free_trial.
- **3-day grace period.** `SUBSCRIPTION_GRACE_DAYS` allows brief payment gaps without
  immediate service cutoff.
- **Trial caps.** 5 pipeline items max, paywall preview on Excel (blurred), watermark on PDF.
  Enforced server-side — not just UI gating.
- **Quota tracking.** Separate counters for searches, Excel exports, pipeline items, and
  alerts. Tracked per billing period, reset on renewal.

---

## 7. Observability

### Signals

| Signal | Tool | What It Catches |
|--------|------|----------------|
| Errors | Sentry | Unhandled exceptions, route timeouts, PNCP API failures |
| Performance | Sentry Performance | p95 latency per endpoint, DB query timing |
| Metrics | Prometheus | Request rate, error rate, LLM classification counts, quota usage |
| Traces | OpenTelemetry | End-to-end request flow, pipeline stage timing |
| Health | `/health/ready` | DB connectivity, Redis connectivity, PNCP API reachability |
| Cron health | `GET /v1/admin/cron-status` | pg_cron job execution: last run, latency, failures (Sentry alert if >25h stale) |
| PNCP canary | ARQ cron (10min) | Page size change, shape drift, 3-consecutive-failure detection |
| Analytics | Mixpanel | User behavior: search completion rate, onboarding funnel, feature adoption |

### SLO Targets

| Metric | Target | Measurement |
|--------|--------|------------|
| API latency (search) | p95 < 2s | Sentry Performance, `/buscar` endpoint |
| Uptime | > 99.5% | `/health/ready` probe, external monitoring |
| MTTR | < 30min | Time from first Sentry alert to confirmed fix |

### Key Incidents

**CRIT-083 (2026-04): SIGSEGV on POST requests.**
Gunicorn prefork (`os.fork()`) + `cryptography>=46` OpenSSL C bindings caused segmentation
faults in forked children during TLS handshake. GET worked; POST crashed. Fixed by switching
from Gunicorn to Uvicorn with `--workers` (uses `multiprocessing.spawn()`, not `os.fork()`).

**CRIT-072 (2026-03): Railway 120s proxy timeout.**
Synchronous PNCP fetch in search pipeline exceeded Railway's hard timeout. Fixed by converting
search to async-first: `POST /buscar` returns 202 immediately, results stream via SSE with
heartbeat. Added route-level asyncio timeout middleware at 60s as safety net.

**PNCP breaking change (2026-02): Silent `tamanhoPagina` reduction.**
PNCP reduced max page size from 500 to 50 without announcement. Detection was accidental.
Added dedicated canary cron probing the boundary every 10 minutes, with Redis-deduped Sentry
alerts and JSON Schema validation of response shape.

---

## 8. Cost Engineering

| Component | Monthly Cost | Strategy |
|-----------|-------------|----------|
| GPT-4.1-nano (classification) | ~$5–15 | LLM only on ambiguous cases (~2-4% of volume). Tracked per sector. |
| GPT-4.1-nano (summaries) | ~$3–10 | ARQ background jobs, cached per search session |
| Supabase | ~$25 (Pro plan) | Connection pooling, statement_timeout=15s |
| Railway (web) | ~$20 | Single worker, uvicorn |
| Railway (worker) | ~$20 | ARQ worker, background jobs |
| Redis (Upstash) | ~$0 (free tier) | Cache + queue + rate limiter + distributed locks |
| Resend (email) | ~$0 (free tier) | Transactional emails, trial sequences |
| **Total** | **~$75–90/month** | Production infrastructure for a SaaS charging R$297–997/month |

This cost structure is viable at low scale because the architecture pushes computation to
deterministic paths (PostgreSQL full-text search, keyword density) and uses LLM sparingly
as a bounded arbiter, not as the primary engine.

---

## 9. Testing Strategy

5,131+ backend tests, 2,681+ frontend tests, 60 E2E tests. Zero-failure policy — CI blocks
merge on any failure.

### What Tests Protect

| Concern | Test Location | Example |
|---------|--------------|---------|
| Search pipeline contracts | `tests/test_search_pipeline.py` | 7-stage state transitions, timeout invariants |
| LLM response parsing | `tests/test_llm_arbiter*.py` | Structured output validation, malformed JSON fallback, benchmark precision/recall |
| Deduplication | `tests/test_consolidation*.py` | Content hash, fuzzy title match, cross-source priority |
| Billing enforcement | `tests/test_billing*.py`, `tests/test_quota*.py` | Stripe webhook signatures, plan fallback, quota atomicity |
| Auth | `tests/test_auth*.py` | JWT 3-strategy validation, RLS, role checks |
| Cache | `tests/test_cache*.py` | SWR staleness, L1/L2/L3 fallthrough, key invalidation |
| Ingestion | `tests/test_ingestion*.py` | Content hash dedup, checkpoint resume, retention enforcement |
| API contracts | `backend/tests/snapshots/openapi_schema.diff.json` | Schema drift detection |
| Security | `.github/workflows/backend-tests.yml` (pip-audit), `.github/workflows/codeql.yml` | Dependency CVEs, static analysis |

### CI Gates

- **Backend (blocking):** `pytest` (71% coverage threshold) + per-module coverage check + `pip-audit` (CVE scan)
- **Backend (advisory):** `ruff check` + `mypy` — non-blocking, output reported but does not fail CI
- **Frontend:** `tsc --noEmit` + `npm test` (60% coverage threshold) + `npm run build`
- **API types:** CI fails if committed `api-types.generated.ts` drifts from backend OpenAPI schema
- **Resilience:** `audit-execute-without-budget.yml` blocks PRs with `.execute()` outside
  `_run_with_budget`; `audit-prod-env.yml` detects debug flags in Railway prod env

---

## 10. What I'd Do Differently

1. **DataLake from day one.** Started with live API fetches during search. Migrated to
   pre-ingested DataLake after hitting timeout and reliability issues. The 3-layer architecture
   (ingestion → query → cache) is the correct pattern; building it earlier would have saved
   months of latency troubleshooting.

2. **Async-first earlier.** Synchronous multi-source fetch couldn't meet latency targets.
   The 202 → SSE pattern (return immediately, stream results) was retrofitted. Should have
   been the initial design.

3. **Schema canary from the start.** Government APIs change silently. The PNCP canary
   (page size probe + shape validation) was added after a breaking change caused silent
   data loss. Should have been part of the initial health check design.

4. **Structured LLM output sooner.** Early versions used free-text classification prompts.
   Switched to JSON schema-enforced structured output after hitting hallucination issues.
   The bounded arbiter pattern (temperature=0, evidence required, schema-validated) is
   now the default for any LLM integration point.

5. **Test infrastructure investment.** 5,131 tests isn't vanity — it's what allowed confident
   refactoring of the search pipeline from synchronous to async, the ingestion retry logic,
   and the billing enforcement. Without the test suite, each of those changes would have
   been a leap of faith.

---

## 11. Next Technical Steps

- **WebSocket upgrade for search progress.** SSE works but has browser connection limits.
  WebSocket would allow multiplexed progress streams.
- **LLM cost optimization.** Evaluate GPT-4.1-nano vs open-weight models (Llama 4, Mistral)
  for classification. The bounded arbiter pattern makes model swapping low-risk — just
  re-benchmark precision/recall against the evaluation set.
- **Horizontal scaling.** Current single-worker uvicorn handles current load. Next step:
  Redis-backed session state to enable multiple uvicorn workers behind a load balancer.
- **Observability maturity.** Add SLO-based alerting (burn rate alerts) instead of static
  thresholds. Add distributed tracing across the full request lifecycle (frontend → backend →
  Supabase → Redis).
- **CI speed.** Full backend test suite takes ~8 minutes. Parallelize by test category
  (pipeline, billing, ingestion, filter) to reduce feedback loop.

---

## Links

- **Production:** https://smartlic.tech
- **API:** https://api.smartlic.tech/docs
- **Source:** https://github.com/tjsasakifln/SmartLic
- **Author:** tiago.sasaki@confenge.com.br
