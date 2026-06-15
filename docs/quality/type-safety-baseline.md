# Type Safety Baseline (Issue #1870)

## Frontend (TypeScript) — noUncheckedIndexedAccess Baseline

**Config:** `strict: true`, `noUncheckedIndexedAccess: true` in `tsconfig.json`
**CI gate:** `tsc --noEmit` in `.github/workflows/frontend-tests.yml` (line 57)

### Known Violations

These files have pre-existing errors from `noUncheckedIndexedAccess: true`.
Each should be fixed gradually, starting with the most impactful.

| File | Errors | Common Pattern |
|------|--------|----------------|
| `components/tour/Tour.tsx` | 7 | `steps[i]` array access |
| `app/api/admin/metrics/route.ts` | 7 | `metrics[name]` record access |
| `lib/error-messages.ts` | 5 | `errorMessages[key]` record access |
| `app/components/conversion/SimuladorOportunidades.tsx` | 5 | state destructuring |
| `app/blog/weekly/page.tsx` | 5 | `find()` result access |
| `app/perguntas/[slug]/json-ld.ts` | 5 | array element access |
| `app/api/buscar/route.ts` | 4 | `headers.get()` result |
| `lib/ab-testing.ts` | 4 | dynamic property access |
| `components/RegionalDependencyMap.tsx` | 4 | `coords` from map lookup |
| `app/components/LoadingProgress.tsx` | 4 | array element access |
| `components/BottomNav.tsx` | 3 | array element access |
| `components/seo/AuthorByline.tsx` | 3 | array element access |
| `app/blog/licitacoes/[setor]/[uf]/page.tsx` | 3 | array element + record access |
| `app/components/landing/DifferentialsGrid.tsx` | 3 | array element access |
| `lib/copy/comparisons.ts` | 3 | string access |

**Total:** 138 errors across 72 files.
**Goal:** Fix gradually, file by file, starting with critical paths (`/buscar`, `/pipeline`, `/api`).

---

## Backend (mypy) — Per-Module Strict Baseline

**Config:** `strict = true` for modules in `pyproject.toml`:
- `auth`, `authorization`
- `quota.*`, `filter.*`, `pipeline.*`

**CI gate:** `.github/workflows/backend-tests.yml` — mypy step (currently advisory `continue-on-error: true`)

### Known Violations in Strict Modules

| Module | Errors | Common Issues |
|--------|--------|---------------|
| `quota/quota_core.py` | 13 | `PlanCapabilities` TypedDict extra keys |
| `quota/plan_enforcement.py` | 8 | `PlanCapabilities` vs `dict[Any, Any]` |
| `quota/session_tracker.py` | 6 | Return type + assignment type errors |
| `auth.py` | 1 | `SanitizedLogAdapter` vs `Logger` |
| `authorization.py` | 1 | `PlanCapabilities` vs `dict[Any, Any]` |
| `quota/plan_auth.py` | 1 | Implicit `Optional` parameter default |

**Total:** 30 errors across 6 core strict modules + 22 in transitive deps.

### Resolution Plan

1. **Short-term (this PR):** Per-module `strict = true` config — CI non-blocking.
2. **Medium-term:** Fix `PlanCapabilities` TypedDict to include extra keys, fix return types in `session_tracker.py`.
3. **Long-term:** `strict = true` for all modules; remove `type: ignore` from non-core.

---

## Current type:ignore Inventory (non-core only)

These are acceptable for now. Tracked for future cleanup.

| File | Line | Reason |
|------|------|--------|
| `admin.py` | 1226 | `_redis_pool` import |
| `health.py` | 1087 | `counter.collect()` attr |
| `pncp_canary.py` | 88,222-224 | Test import + env assignments |
| `seo_404_middleware.py` | 100 | `dispatch` override |
| `clients/base.py` | 391 | Generator yield |
| `clients/pncp/_parallel_mixin.py` | 90,161,277,282 | Mixin attr-defined |
| `consolidation/dedup.py` | 334,336 | Dynamic attr assignment |
| `jobs/cron/indice_municipal.py` | 28 | Conditional import |
| `jobs/cron/gsc_sync.py` | 35,56,174 | Conditional imports |
| `llm_arbiter/async_runtime.py` | 110 | Sentinel assignment |
| `pipeline/budget.py` | 72 | Return type narrowing |
| `models/__init__.py` | 18,23 | Lazy imports |
| `routes/*.py` | various | Runtime type coercion |
| `schemas/contract.py` | 231 | Conditional import |

**Total:** 27 `type: ignore` across ~14 non-core files.
