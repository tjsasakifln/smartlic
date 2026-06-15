# Development Changelog

Records significant codebase changes, refactors, and removals.

## 2026-06-15 — TD-1875: Legacy Code Removal (Shims, Facades, Obsolete Re-exports)

Removed approximately 300+ LOC of dead code. All changes are backward compatible
at the import level (tests pass, production code references updated).

### Removed Files

| File | LOC | Reason |
|------|-----|--------|
| `backend/billing/__init__.py` | 9 | Empty package shim |
| `backend/billing/quota.py` | 2 | Shim re-exporting `from quota import *` |
| `backend/billing/service.py` | 2 | Shim re-exporting `from services.billing import *` |
| `backend/cron_jobs.py` | 141 | Facade that only re-exported from `jobs.cron.*` and `cron.*` + canary state |
| `backend/cache/core.py` | 2 | Shim re-exporting `from cache_module import *` |
| `backend/cache/memory.py` | 8 | Shim re-exporting `from redis_pool import InMemoryCache, get_fallback_cache` |
| `backend/cache/redis_pool.py` | 2 | Shim re-exporting `from redis_pool import *` |

### Simplified Files

| File | Before | After | Change |
|------|--------|-------|--------|
| `backend/job_queue.py` | 178 LOC | ~50 LOC | Removed all re-exports (job functions, result store, worker config). Kept real ARQ pool management functions. |

### Updated Files

| File | Change |
|------|--------|
| `backend/cache/__init__.py` | Removed `from cache_module import *` and `from cache.memory import ...`; added `from redis_pool import InMemoryCache, get_fallback_cache` |
| `backend/search_cache.py` | Added `DeprecationWarning` at import time; added `InMemoryCache` re-export from `redis_pool` |
| `backend/jobs/cron.py` | Changed from `from cron_jobs import *` to explicit re-exports from `jobs.cron.*` and `cron.*` submodules |
| `backend/jobs/queue.py` | Changed from `from job_queue import *` to explicit re-exports from `job_queue` (real functions) and `jobs.queue.*` submodules |
| `backend/jobs/cron_billing.py` | Changed import source from `cron_jobs` to `jobs.cron.billing` |
| `backend/jobs/cron_notifications.py` | Changed import source from `cron_jobs` to `jobs.cron` |
| `backend/jobs/cron_health.py` | Changed import source from `cron_jobs` to `jobs.cron.canary` |
| `backend/jobs/cron/canary.py` | Inlined canary state (`_pncp_cron_status_lock`, `_pncp_cron_status`, `_pncp_recovery_epoch`) that previously lived in `cron_jobs.py` |
| `backend/jobs/__init__.py` | Updated docstring to reflect removed `cron_jobs` facade |
| `backend/cron/__init__.py` | Updated docstring to reflect removed `cron_jobs` dependency |
| `backend/routes/search/__init__.py` | Updated docstring to note deferred migration of `buscar_licitacoes` |

### Import Path Changes (Production Code)

| Old Import | New Import |
|------------|-----------|
| `from cron_jobs import ...` | `from jobs.cron import ...` (6 files updated) |
| `from job_queue import get_job_result` | `from jobs.queue.result_store import get_job_result` (5 files updated) |
| `from job_queue import release_search_slot` | `from jobs.queue.result_store import release_search_slot` |
| `from job_queue import acquire_search_slot` | `from jobs.queue.result_store import acquire_search_slot` |
| `from job_queue import get_zero_match_results` | `from jobs.queue.result_store import get_zero_match_results` |
| `from job_queue import persist_job_result` | `from jobs.queue.result_store import persist_job_result` |
| `from job_queue import store_pending_review_bids` | `from jobs.queue.result_store import store_pending_review_bids` |

### Test File Updates

15 test files updated to use new import paths. All `@patch("cron_jobs.X")` changed
to `@patch("jobs.cron.X")`.

### Not Changed (Deferred)

- `routes/search/__init__.py` — `buscar_licitacoes` kept in `__init__` for test
  patch compatibility. Move to `post_handler.py` deferred (requires updating
  ~50+ test patch targets).
