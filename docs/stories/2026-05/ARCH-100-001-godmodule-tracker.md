# ARCH-100-001 — Godmodule Split Tracker

**Issue:** #903  
**Score alvo:** 94% → 100% architectural  
**ADR:** [ADR-ARCH-001](../../adr/ADR-ARCH-001-godmodule-split-strategy.md)  
**CI Gate:** `.github/workflows/audit-godmodule-loc.yml`  
**Atualizado:** 2026-05-08

## Batches de Execução

### P0 Batch 1 — Score +2pts → 96% (prioridade imediata)

| Story | Módulo Alvo | LOC Atual | Padrão | Status |
|-------|-------------|-----------|--------|--------|
| [RES-BE-014](../2026-04/RES-BE-014-godmodule-split-pipeline-stages-execute.md) | `filter/pipeline.py` | 1918 | Strategy | Ready |
| [REF-VAL-002](../2026-04/REF-VAL-002-llm-arbiter-classification-strategy-pattern.story.md) | `bid_analyzer.py` (llm_arbiter) | 437 | Strategy | Ready |
| [REF-MON-002](../2026-04/REF-MON-002-stripe-webhook-handlers-abc-base.story.md) | `webhooks/handlers/` (625+589+578+569 LOC) | 2806 | ABC | Ready |

### P1 Batch 2 — Score +1pt → 97%

| Story | Módulo Alvo | LOC Atual | Padrão | Status |
|-------|-------------|-----------|--------|--------|
| [REF-VAL-003](../2026-04/REF-VAL-003-publicos-routes-base-factory.story.md) | `routes/publicos*` | ~? | Factory | Ready |
| [REF-SCALE-003](../2026-04/REF-SCALE-003-ingestion-package-decomposition.story.md) | `ingestion/` package | ~? | Package | Ready |

### P2 Batch 3 — Score +1pt → 98%

| Story | Módulo Alvo | LOC Atual | Padrão | Status |
|-------|-------------|-----------|--------|--------|
| [REF-MON-003](../2026-04/REF-MON-003-quota-plan-enforcement-decompose.story.md) | quota/plan enforcement | ~? | Decompose | Ready |
| [REF-MON-004](../2026-04/REF-MON-004-analytics-split-conversion-vs-usage.story.md) | analytics split | ~? | Split | Ready |
| [REF-VAL-005](../2026-04/REF-VAL-005-llm-py-decompose-summaries-vs-orchestration.story.md) | `llm.py` summaries vs orchestration | ~? | Decompose | Ready |

### P3 Batch 4 — Score +2pts → 100%

| Story | Módulo Alvo | LOC Atual | Padrão | Status |
|-------|-------------|-----------|--------|--------|
| [REF-SCALE-004](../2026-04/REF-SCALE-004-sitemap-routes-factory-consolidation.story.md) | sitemap routes | ~? | Factory | Ready |
| [FOUND-SCALE-002](../2026-04/FOUND-SCALE-002-frontend-sentry-ssg-isr-init.story.md) | frontend Sentry/SSG/ISR init | ~? | Split | Ready |
| [REF-SCALE-005](../2026-04/REF-SCALE-005-datalake-query-builder-pattern.story.md) | `datalake_query.py` | ~? | Builder | Ready (P3 defer) |

## Score Impact Model

| Batch | Stories | Δ Score | Score Final | Critério |
|-------|---------|---------|-------------|---------|
| P0 Batch 1 | RES-BE-014, REF-VAL-002, REF-MON-002 | +2 | 96% | Godmodules críticos (>1500 LOC + multi-concern) |
| P1 Batch 2 | REF-VAL-003, REF-SCALE-003 | +1 | 97% | Pattern consolidation cross-rota |
| P2 Batch 3 | REF-MON-003, REF-MON-004, REF-VAL-005 | +1 | 98% | Monitoring/analytics decompose |
| P3 Batch 4 | REF-SCALE-004, FOUND-SCALE-002, REF-SCALE-005 | +2 | 100% | Frontend + defer aceitável |

## LOC de Referência (2026-05-08)

| Módulo | LOC | Observação |
|--------|-----|------------|
| `filter/pipeline.py` | 1918 | Maior godmodule backend — P0 |
| `webhooks/handlers/subscription.py` | 625 | |
| `webhooks/handlers/invoice.py` | 589 | |
| `webhooks/handlers/checkout.py` | 578 | |
| `webhooks/handlers/founding.py` | 569 | |
| `webhooks/handlers/stripe_product_price.py` | 441 | |
| `bid_analyzer.py` (llm arbiter) | 437 | |
| `routes/billing.py` | 383 | |
| `llm_budget.py` | 232 | |
| `webhooks/handlers/_shared.py` | 78 | |

## Progress

- [x] ADR criado: `docs/adr/ADR-ARCH-001-godmodule-split-strategy.md`
- [x] CI gate: `.github/workflows/audit-godmodule-loc.yml`
- [ ] Batch 1 executado (RES-BE-014, REF-VAL-002, REF-MON-002)
- [ ] Batch 2 executado (REF-VAL-003, REF-SCALE-003)
- [ ] Batch 3 executado (REF-MON-003, REF-MON-004, REF-VAL-005)
- [ ] Batch 4 executado (REF-SCALE-004, FOUND-SCALE-002, REF-SCALE-005)
