# ADR-ARCH-001 — Godmodule Split Strategy

**Status:** Accepted
**Date:** 2026-05-08
**Issue:** #903 (P0 Refactoring Architectural Score 94% → 100%)
**Owners:** @architect, @dev
**Related:** RES-BE-014, REF-VAL-002, REF-VAL-003, REF-VAL-005, REF-MON-002, REF-MON-003, REF-MON-004, REF-SCALE-003, REF-SCALE-004, REF-SCALE-005, FOUND-SCALE-002

---

## 1. Context

As the SmartLic backend grew from prototype to production (v0.5, ~5131 passing tests), several modules accumulated responsibility beyond their original scope. These "godmodules" — files with >800 LOC and more than two distinct concerns — impose measurable costs:

- **Cognitive load:** a developer reading `filter/pipeline.py` (1918 LOC) must hold the full filter orchestration, keyword matching, LLM dispatch, and stage sequencing in mind simultaneously. Context-switch cost is high.
- **Wedge risk:** a regression in one concern (e.g. LLM timeout handling) can silently break an unrelated concern (e.g. keyword pre-filter) in the same file. `filter/pipeline.py` and `pipeline/stages/execute.py` together form a 3158-LOC entangled pair that has already produced incidents (RES-BE-014, CRIT-084).
- **Onboarding friction:** new contributors cannot locate the right abstraction boundary without reading the entire file. Files >1000 LOC regularly trigger "where do I add this?" confusion.
- **Test isolation:** godmodules are typically tested through integration paths rather than unit paths, making it harder to achieve targeted coverage and faster to hit cascading failures.

Reversa Architect analysis (2026-04-27, `_reversa_sdd/review-report.md`) identified architectural consistency at 89% — the remaining 11% is directly attributable to these godmodules and the absence of canonical pattern assignments for their split.

This ADR establishes the godmodule criterion, the pattern selection decision tree, and the execution order for all pending split stories.

---

## 2. Godmodule Criterion

A file is classified as a godmodule and is subject to mandatory split if it meets **both** conditions:

1. **LOC > 800** (measured by `wc -l`, excluding blank lines and docstrings adds trivial variance — raw line count is the gate)
2. **Multi-concern:** the file contains more than two logically distinct responsibilities (e.g. data retrieval + transformation + orchestration + external I/O are four distinct concerns)

Meeting only one condition is a warning, not a mandatory split:
- High LOC with single concern (e.g. a large but coherent algorithm) → annotate with `# SINGLE-CONCERN-LARGE` and defer to natural growth boundary
- Multi-concern with low LOC → refactor inline without a dedicated story

### Current Godmodule Inventory (backend Python, excluding tests/venv)

| File | LOC | Concerns | Priority | Story |
|------|-----|----------|----------|-------|
| `backend/filter/pipeline.py` | 1918 | Filter orchestration, stage sequencing, LLM dispatch, circuit breaker, budget tracking | P0 | RES-BE-014 |
| `backend/metrics.py` | 1326 | Prometheus counters, OpenTelemetry spans, Stripe event metrics, search analytics, system health metrics | P1 | REF-MON-004 |
| `backend/routes/blog_stats.py` | 1279 | Blog post CRUD, stats aggregation, SEO metadata, sitemap generation | P2 | REF-SCALE-004 |
| `backend/pipeline/stages/execute.py` | 1240 | Per-UF execution, concurrency orchestration, budget enforcement, result collection, error recovery | P0 | RES-BE-014 |
| `backend/admin.py` | 1240 | User management, billing overrides, feature flags, analytics dashboards, system config | P0 | REF-MON-002 adjacent |
| `backend/filter/keywords.py` | 1116 | Keyword extraction, normalization, synonym expansion, sector mapping, exclusion logic | P1 | REF-VAL-002 |
| `backend/health.py` | 1096 | Liveness probes, readiness checks, dependency health (DB/Redis/OpenAI), Prometheus scrape endpoint | P2 | REF-MON-003 |
| `backend/llm.py` | 795 | LLM summarization, LLM orchestration, prompt construction, retry logic | P2 | REF-VAL-005 |

---

## 3. Pattern Selection

Three structural patterns are available for godmodule splits. Pattern selection is determined by the **nature of the variation** within the module, not by personal preference or familiarity.

### 3.1 Strategy Pattern

**Use when:** variants of an algorithm or processing step coexist and must be interchangeable at runtime or configuration time. The caller does not need to know which variant is active.

**Canonical signals:**
- `if source == 'pncp': ... elif source == 'comprasgov': ...` repeated across multiple methods
- `if use_llm: ... else: keyword_only: ...` dispatch
- Stage objects with identical interfaces but different implementations

**Applied to:**
- `RES-BE-014` — `pipeline/stages/execute.py`: each pipeline stage becomes a `PipelineStage` ABC with `.execute(context) -> StageResult`; the orchestrator selects stages from a registry. RES-BE-014 has been previously flagged with this exact pattern (`stages.execute` → Strategy).
- `REF-VAL-002` — LLM arbiter classification: `KeywordStrategy`, `LLMStandardStrategy`, `LLMZeroMatchStrategy` implement a common `ClassificationStrategy` interface; tier selection is driven by config, not inline conditionals.

### 3.2 ABC / Template Method Pattern

**Use when:** handlers share a common lifecycle structure (setup → execute → teardown, or validate → process → record) but differ only in their core implementation step. The common scaffolding must be enforced, not merely repeated.

**Canonical signals:**
- Multiple handlers with the same `try/except/log/audit` wrapper
- Webhook handlers where every handler must perform signature verification, idempotency check, and audit log — only the business logic differs
- Route handlers where every endpoint requires role check + quota gate + telemetry

**Applied to:**
- `REF-MON-002` — Stripe webhook handlers: `BaseStripeHandler` ABC enforces `validate() → handle() → record_audit()` lifecycle; each event handler (`CheckoutHandler`, `SubscriptionHandler`, `InvoiceHandler`, `FoundingHandler`) overrides only `handle()`.

### 3.3 Factory Pattern

**Use when:** object creation is complex, conditional, or involves shared boilerplate that is not behavioral variation. Factories are about *instantiation*, not *execution*.

**Canonical signals:**
- Route registration that repeats the same middleware stack across many endpoints
- Client construction that selects among multiple backend sources based on config
- Schema builders that apply the same validation decorators conditionally

**Applied to:**
- `REF-VAL-003` — `publicos` routes: `PublicRouteFactory` registers the common middleware stack (rate limiter, cache headers, bot detection) once; individual route handlers are registered via `factory.register(path, handler)`.
- `REF-SCALE-004` — Sitemap routes: a `SitemapRouteFactory` eliminates the repeated `cache_control + gzip + 503-on-empty` boilerplate across 8 sitemap route files.

### 3.4 Package Decomposition

**Use when:** a file is acting as a namespace rather than a domain. It contains logically independent sub-domains that happen to share an import path but have no functional coupling.

**Canonical signals:**
- File is named after a category (`metrics.py`, `ingestion.py`) rather than a domain concept
- Sub-sections of the file can be extracted without changing any call site except the import path
- File has grown by accretion of unrelated features over multiple sprints

**Applied to:**
- `REF-SCALE-003` — `backend/ingestion/`: already partially a package; crawler, transformer, loader, checkpoint, and scheduler should each be a module with explicit public interfaces.
- `REF-MON-003` + `REF-MON-004` — `backend/metrics.py` and quota enforcement split into `metrics/prometheus.py`, `metrics/otel.py`, `metrics/analytics.py`; quota into `quota/plan_enforcement.py` (already exists) and `quota/conversion_events.py` (new).
- `REF-VAL-005` — `backend/llm.py`: split into `llm/summarization.py` (summary generation, Excel/PDF context) and `llm/orchestration.py` (retry, rate-limit management, token budget).

---

## 4. Execution Order

Stories are batched by architectural impact and inter-dependency. Each batch must be complete and merged to `main` before the next batch begins, to avoid compound merge conflicts on shared import paths.

### P0 Batch 1 — Maximum Architectural Impact (+2 pts: 94% → 96%)

Target: eliminate the two most wedge-prone godmodules and establish the Strategy + ABC patterns as in-codebase reference implementations.

| Story | File | Pattern | Rationale |
|-------|------|---------|-----------|
| `RES-BE-014` | `filter/pipeline.py` + `pipeline/stages/execute.py` | Strategy | Largest file (1918 LOC). Entangled with execute.py (1240 LOC). Both caused CRIT-084 cascades. Split unblocks safe testing of individual pipeline stages. |
| `REF-VAL-002` | `filter/keywords.py` (partially) + LLM arbiter | Strategy | Keywords module feeds directly into pipeline stages — splitting pipeline without splitting the classification tier creates a new coupling. |
| `REF-MON-002` | Stripe webhook handlers (`backend/webhooks/handlers/`) | ABC | Stripe idempotency validation (current branch `fix/718-stripe-idempotency-validation`) benefits directly from the ABC lifecycle; ships clean foundation before Batch 2 handler proliferation. |

**Dependency note:** `RES-BE-014` must merge before `REF-VAL-002` because `keywords.py` is imported by both `pipeline.py` and the LLM arbiter — a shared file touched by two concurrent PRs creates guaranteed conflict.

### P1 Batch 2 — Pattern Consolidation (+1 pt: 96% → 97%)

Target: apply Factory pattern to routes and complete ingestion package split.

| Story | File | Pattern | Rationale |
|-------|------|---------|-----------|
| `REF-VAL-003` | `publicos` routes | Factory | Batch 1 established Strategy as reference; Factory is the second canonical pattern — introducing it here while Strategy is fresh reduces cognitive switching. |
| `REF-SCALE-003` | `backend/ingestion/` package | Package decomposition | Ingestion is already partially decomposed (`backend/ingestion/*.py`). Completing the split is low-risk, high-clarity work. Completes the ingestion module for SCALE-series epic. |

### P2 Batch 3 — Monitoring and Analytics (+1 pt: 97% → 98%)

Target: split `metrics.py` and `health.py`; complete LLM decomposition.

| Story | File | Pattern | Rationale |
|-------|------|---------|-----------|
| `REF-MON-003` | `backend/health.py` | Package decomposition | Depends on Batch 2 ingestion split (health probes check ingestion checkpoint state). |
| `REF-MON-004` | `backend/metrics.py` | Package decomposition | `metrics.py` is imported by nearly every module; splitting it last in this batch minimizes the import-path churn radius. |
| `REF-VAL-005` | `backend/llm.py` | Package decomposition | Near-threshold (795 LOC, REF-VAL-005 has a defer clause). Proceed in Batch 3 once LLM arbiter (REF-VAL-002) is stable, to avoid split-before-stabilize. |

### P3 Batch 4 — Defer-Acceptable (+2 pts: 98% → 100%)

Target: complete sitemap factory consolidation, frontend Sentry alignment, and datalake Builder.

| Story | File | Pattern | Rationale |
|-------|------|---------|-----------|
| `REF-SCALE-004` | Sitemap routes | Factory | `blog_stats.py` (1279 LOC) and sitemap routes share boilerplate. Defer is acceptable because these routes have no wedge risk — they fail independently. |
| `FOUND-SCALE-002` | Frontend Sentry SSG/ISR init | Alignment | Frontend concern; independent of backend split series. Can proceed in parallel once Batch 3 is complete. |
| `REF-SCALE-005` | `datalake_query.py` | Builder pattern | Explicit defer annotation in story. Builder pattern is the most complex to introduce; defer until Batches 1–3 establish pattern vocabulary in the team. |

---

## 5. Score Impact Model

The composite architectural consistency score used in `_reversa_sdd/review-report.md` is derived from five dimensions. Godmodule splits affect primarily **Architectural consistency** (+2% per batch that establishes a new canonical pattern) and secondarily **Test/CI gates** (+1% when a CI gate enforces the new threshold).

| Batch | Stories | Delta | Projected Score |
|-------|---------|-------|----------------|
| Baseline | — | — | 94% |
| Batch 1 (P0) | RES-BE-014 + REF-VAL-002 + REF-MON-002 | +2 pts | 96% |
| Batch 2 (P1) | REF-VAL-003 + REF-SCALE-003 | +1 pt | 97% |
| Batch 3 (P2) | REF-MON-003 + REF-MON-004 + REF-VAL-005 | +1 pt | 98% |
| Batch 4 (P3) | REF-SCALE-004 + FOUND-SCALE-002 + REF-SCALE-005 | +2 pts | 100% |

Score increments reflect: Batch 1 earns +2 because it eliminates both entangled wedge-risk files and establishes two canonical patterns simultaneously. Batch 4 earns +2 because it completes full coverage (zero remaining godmodules above threshold) and the CI gate is activated.

---

## 6. CI Gate

Upon completion of Batch 4, a GitHub Actions workflow `audit-godmodule-loc.yml` will enforce the godmodule threshold on every PR:

```yaml
# .github/workflows/audit-godmodule-loc.yml
name: Godmodule LOC Gate

on: [pull_request]

jobs:
  check-loc:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check for new godmodules (>1000 LOC, excluding tests/venv/migrations)
        run: |
          python scripts/audit_godmodule_loc.py --threshold 1000 --fail-on-new
```

The threshold for the CI gate is set at **1000 LOC** (not 800) to allow modest growth without triggering false positives on files that are legitimately large but single-concern. The 800-LOC criterion in section 2 is the *human review* threshold; the CI gate fires at 1000 to reduce noise.

Files already above 1000 LOC at the time the gate is enabled are grandfathered via an explicit allowlist in `scripts/audit_godmodule_loc.py`. New files added after the gate is active must stay below 1000 LOC or carry an explicit `# GODMODULE-EXEMPT: <reason>` annotation reviewed in the PR.

---

## 7. Consequences

### Positive

- Eliminates the primary source of wedge risk in the filter/pipeline subsystem (CRIT-084 family).
- Each split introduces a canonical in-codebase example of the chosen pattern, reducing the "where do I add this?" friction for contributors.
- Individual modules become independently testable at unit scope (mock the strategy / mock the factory output), improving test isolation and reducing integration-only coverage paths.
- The CI gate prevents regression to godmodule state without explicit review bypass.

### Negative / Trade-offs

- Import paths change across Batches 1–3, requiring coordinated frontend/backend type regeneration (`npm run generate:api-types`) after any split that touches exported schemas.
- The ABC pattern for Stripe webhook handlers (REF-MON-002) introduces a base class hierarchy that must be documented to avoid future subclass proliferation.
- Package decomposition splits (REF-SCALE-003, REF-MON-004) increase the number of files a developer must navigate; offset by explicit `__init__.py` re-exports that preserve existing import surfaces.

### Out of Scope

- `backend/main.py` — bootstrap file; large but single-concern (application startup). Not a godmodule by the criterion in section 2.
- `backend/search_pipeline.py` — already partially decomposed across `backend/pipeline/`; covered by existing STORY-3.1 and DEBT-115 stories which predated this ADR.
- `backend/pncp_client.py` — client file with high LOC but single external concern (PNCP API calls + retry logic). Defer indefinitely.

---

## 8. Alternatives Considered

- **LOC-only threshold (no multi-concern requirement).** Rejected: penalises legitimately large single-concern files (e.g. a comprehensive state machine) and generates noise without architectural benefit.
- **Single universal pattern (ABC for everything).** Rejected: ABC is inappropriate for algorithmic variants (Strategy) and for object creation (Factory). Forcing ABC produces inheritance hierarchies that are harder to test than composition.
- **Defer all splits to post-revenue milestone.** Rejected: `filter/pipeline.py` + `pipeline/stages/execute.py` have already caused production incidents (RES-BE-014, CRIT-084). The wedge risk is not theoretical.
- **Parallel execution of all batches.** Rejected: `filter/keywords.py` is imported by both `pipeline.py` (RES-BE-014) and the LLM arbiter (REF-VAL-002). Parallel PRs on the same file produce guaranteed merge conflicts with no net velocity gain.
