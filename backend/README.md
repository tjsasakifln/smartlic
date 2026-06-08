# Backend — SmartLic API

FastAPI application in production at `api.smartlic.tech`. 187 endpoints, 65 registered routers,
3-layer data architecture (ingestion → search pipeline → cache).

## Entry Point

`main.py` is **intentionally thin** (29 LOC). It enables faulthandler, loads environment
variables, and calls `startup.app_factory.create_app()`. All initialization — middleware, routes,
lifespan tasks, exception handlers, Sentry, OpenTelemetry — lives in the `startup/` package.

```python
# main.py — the whole file
import faulthandler
faulthandler.enable()

from dotenv import load_dotenv
load_dotenv()

from startup.app_factory import create_app
app = create_app()
```

## Module Map

| Category | Key Modules | Purpose |
|----------|------------|---------|
| **Startup** | `startup/` (app_factory, routes, lifespan, middleware_setup, exception_handlers, sentry, state, endpoints) | App bootstrap. 11 modules, each single-responsibility. |
| **Search Pipeline** | `search_pipeline.py`, `search_state_manager.py`, `pipeline/` (budget, cache_manager, stages, worker, tracing), `consolidation/` (dedup, source_merger) | 7-stage state machine with time budget waterfall. Async-first (202 → SSE). |
| **Filter / Classification** | `filter/` package (pipeline, keywords, density, term_parser, synonyms, status_inference), `llm_arbiter/` package (classification, zero_match, async_runtime, batch_api, prompt_builder), `relevance.py`, `viability.py` | Keyword density tiers + GPT-4.1-nano arbiter. 4-factor viability scoring. |
| **Ingestion (DataLake)** | `ingestion/` (config, crawler, transformer, loader, checkpoint, scheduler, enricher), `datalake_query.py` | ETL: 27 UFs × 6 modalities, 400-day retention. `pncp_raw_bids` (1.5M+ rows) + `pncp_supplier_contracts` (2M+ rows). |
| **Cache** | `cache/` (manager, cascade, swr, _ops, admin, enums), `redis_pool.py`, `redis_client.py`, `search_cache.py` | L1 InMemoryCache (4h, LRU 10k) + L2 Redis (4h) + L3 Supabase (24h). SWR per-request reactive. |
| **Auth** | `auth.py` (JWT 3-strategy: JWKS ES256 > PEM > HS256), `authorization.py` (admin/master roles), `oauth.py` (Google Sheets) | Supabase Auth JWT validation with LRU cache. RLS + service-role bypass. |
| **Billing** | `services/billing.py`, `quota/` (quota_core, quota_atomic, plan_enforcement, session_tracker), `webhooks/stripe.py`, `webhooks/handlers/` | 9 plans, 12 Stripe webhook events with idempotency. Atomic quota via RPC. |
| **Jobs** | `jobs/queue/` (ARQ worker), `jobs/cron/` (canary, billing, notifications, session_cleanup, pncp_canary, llm_batch_poll, new_bids_notifier, trial_emails, seo_snapshot) | ARQ worker + 9 cron schedules + 19 lifespan loops with Redis distributed locks. |
| **Routes** | `routes/` — 71 router files, 65 registered | Tag-grouped: search, pipeline, billing, analytics, admin, SEO public, sitemaps. |
| **Exports** | `excel.py` (openpyxl), `google_sheets.py` (OAuth), `pdf_generator_edital.py` (ReportLab) | Excel with styled headers, watermarked PDF (trial), Google Sheets export (paid). |
| **Observability** | `metrics.py` (Prometheus), `telemetry.py` (OpenTelemetry), `audit.py`, `log_sanitizer.py`, `health.py`, `rate_limiter.py` | Sentry + Mixpanel + Prometheus + OTel. Health probes at `/health/live`, `/health/ready`. |

## Quick Start

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Environment (copy and fill)
cp ../.env.example ../.env

# Dev server
uvicorn main:app --reload --port 8000

# Docs
open http://localhost:8000/docs       # Swagger UI
open http://localhost:8000/redoc      # ReDoc
```

## Environment Variables

All configuration via `.env`. See project root `.env.example` for full reference.

Critical variables:
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` — database + auth
- `OPENAI_API_KEY` — LLM classification and summaries
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` — billing
- `REDIS_URL` — cache, queue, rate limiter, distributed locks
- `RESEND_API_KEY` — transactional email
- `ENVIRONMENT` — `development` | `production` (controls Sentry, log level)

## Testing

```bash
# Single test (fast, preferred for development)
pytest -k "test_name"

# Single file
pytest tests/test_search_pipeline.py

# Full suite (Linux/CI — uses signal-based timeout)
pytest --timeout=30

# Full suite (Windows-safe — subprocess isolation per file)
python scripts/run_tests_safe.py
python scripts/run_tests_safe.py --parallel 4

# Coverage (threshold: 70%)
pytest --cov=. --cov-fail-under=70

# Integration tests only
pytest tests/integration/

# Lint
ruff check . && mypy .
```

**Stats (latest main):** 5,131+ tests passing, 0 failures, CI green on every commit.
Source: `.github/workflows/backend-tests.yml` — runs on every push.

## Observability

| Signal | Tool | Access |
|--------|------|--------|
| Errors + Performance | Sentry | https://confenge.sentry.io/projects/smartlic-backend/ |
| Metrics | Prometheus | `GET /metrics` (conditional, internal) |
| Traces | OpenTelemetry | Exported to configured OTLP endpoint |
| Health | Built-in | `GET /health/live` (liveness), `GET /health/ready` (readiness) |
| Cron health | Built-in | `GET /v1/admin/cron-status` (admin-only, pg_cron monitoring) |

## API Documentation

Interactive docs at `/docs` (Swagger) and `/redoc` (ReDoc) when running locally.
Production: https://api.smartlic.tech/docs (protected behind `DOCS_ACCESS_TOKEN` query param).

OpenAPI schema auto-generates frontend types:
```bash
npm --prefix ../frontend run generate:api-types
```
Output: `frontend/app/api-types.generated.ts` — committed, CI-gated against drift.

## Architecture Docs

- [System Architecture](../docs/architecture/system-architecture.md) — full module map, ERD, C4 diagrams
- [AI Classification Pipeline](../docs/ai-pipeline.md) — hybrid keyword + LLM pipeline
- [LLM Arbiter](../docs/architecture/llm-arbiter.md) — 4-layer false positive elimination
- [Operational Reliability](../_reversa_sdd/operational-reliability-2026-05.md) — SLO, incidents, MTTR
- [Code Analysis](../_reversa_sdd/code-analysis.md) — 18-module deep-dive with metrics
- [CASE STUDY](../CASE_STUDY.md) — engineering narrative for external evaluation

## Key Technical Decisions

- **Uvicorn, not Gunicorn.** Gunicorn prefork + `cryptography` C extensions = SIGSEGV on POST (CRIT-083).
  Uvicorn uses `multiprocessing.spawn()`, avoiding the fork-safety issue.
- **Async-first search.** `POST /buscar` returns 202 immediately. Results stream via SSE
  (`GET /buscar-progress/{id}`) with fallback polling. Prevents Railway 120s proxy timeout.
- **DataLake queries, not live API.** Search queries local PostgreSQL via `search_datalake` RPC
  (<100ms p95). Live PNCP/PCP/ComprasGov APIs are fallback only (when DataLake returns 0 results
  or `DATALAKE_QUERY_ENABLED=false`).
- **Hybrid classification.** Deterministic keyword filters eliminate ~80% of candidates.
  GPT-4.1-nano arbitrates only ambiguous cases (~2-4% of volume), keeping LLM cost negligible.
- **Route-level timeout middleware.** Returns 503 before Railway's 120s proxy kill, preventing
  orphaned event-loop work. SSE, health, and webhook routes exempt.

## Dependencies

Python 3.12, FastAPI 0.136, Pydantic 2.13, httpx 0.28, OpenAI SDK 1.109, Supabase 2.30,
Redis (via redis-py), ARQ 0.26+, openpyxl 3.1, ReportLab 4.5, Stripe 11.4, Resend SDK,
Prometheus client, OpenTelemetry SDK, Sentry SDK.

Full pinned list: `requirements.txt` — regenerated with hash verification via `pip-compile`.

---

© 2024–2026 CONFENGE AVALIAÇÕES E INTELIGÊNCIA ARTIFICIAL LTDA. Proprietary.
