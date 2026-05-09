# DATA-CAP-001: PostgREST max-rows=1000 silent truncation fix em 7 routes

**Priority:** P0
**Effort:** M (1-2d)
**Squad:** @dev (lead) + @data-engineer + @qa
**Status:** Draft
**Epic:** [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2/) — eixo operational reliability + UX credibilidade
**Sprint:** TBD
**Dependências bloqueadoras:** Nenhuma
**Reversa anchor:** `_reversa_sdd/review-report.md §11.1` (counts realinhados) + `.reversa/drift-2026-05-09.md`
**Score Δ:** ops reliability +6 (84% → 90%)

---

## Contexto

PostgREST `supabase/config.toml:max_rows = 1000` cap silencioso em 7 routes públicas. Bug visível ao user: entes contratantes com 1001+ contratos retornam **sempre 1000 redondos** → degrada credibilidade dos dados públicos da plataforma.

`backend/datalake_query.py:L195-218` já implementa o pattern correto (per-UF pagination + truncation suspect logging + `DATALAKE_TRUNCATION_SUSPECTED` Prometheus counter). `backend/routes/sitemap_orgaos.py` + `sitemap_cnpjs.py` usam pattern alternativo (RPC `RETURNS json scalar` que bypassa max-rows).

7 routes restantes passam `.limit(2000-5000)` para PostgREST que silently caps a 1000:

| Arquivo | Linha | `.limit()` | Sintoma |
|---------|-------|-----------|---------|
| `backend/routes/contratos_publicos.py` | 198 | `.limit(5000)` | Lista contratos do orgão truncada |
| `backend/routes/contratos_publicos.py` | 280 | `.limit(5000)` | mesma rota outra query |
| `backend/routes/orgao_publico.py` | 279 | `.limit(5000)` | Page orgão público |
| `backend/routes/orgao_publico.py` | 445 | `.limit(2000)` | `_fetch_contracts_data` agg top |
| `backend/routes/empresa_publica.py` | 532 | `limit=2000` | CNPJ supplier history |
| `backend/routes/itens_publicos.py` | 446 | `.limit(1000)` | Already at cap (silent) |
| `backend/routes/blog_stats.py` | 943 | `.limit(5000)` | Blog stats aggregation |
| `backend/routes/observatorio.py` | 331 | `.limit(5000)` | Observatorio metric |
| `backend/routes/seo_admin.py` | 206 | `.limit(5000)` | Admin SEO panel |

Memory `reference_supabase_management_api_query` confirma: PostgREST max-rows não-tunável via Supabase platform (config.toml local apenas docs alignment).

---

## Acceptance Criteria

### AC1: Pattern A — RPC RETURNS json scalar (preferencial para aggregates)

Para queries agregadoras (top-N por valor, count distinct, etc.):

- [ ] Criar RPC PostgreSQL `get_<route>_<query>_json()` retornando `RETURNS json` scalar (modelo: `supabase/migrations/20260408200000_sitemap_rpc_json.sql`)
- [ ] Aplicar a:
  - `orgao_publico:445` `_fetch_contracts_data` → `get_orgao_top_contracts_json(orgao_cnpj, limit)`
  - `blog_stats:943` → `get_blog_stats_aggregated_json()`
- [ ] Each RPC migration paired com `.down.sql`

### AC2: Pattern B — Per-batch pagination via `.range()` em loop

Para queries que precisam dos rows brutos:

- [ ] Implementar helper `backend/utils/postgrest_paginate.py:paginate_full(query_builder, batch_size=1000, max_total=10000)` que:
  - Executa `.range(offset, offset+batch_size-1).execute()` em loop
  - Detecta truncation: se `len(batch) == batch_size`, continua; se `< batch_size`, encerra
  - Emite log + métrica em truncation suspect (mesma de `DATALAKE_TRUNCATION_SUSPECTED`)
  - Cap `max_total` para evitar runaway (default 10k)
- [ ] Aplicar a:
  - `contratos_publicos:198, 280`
  - `orgao_publico:279`
  - `empresa_publica:532`
  - `itens_publicos:446`
  - `observatorio:331`
  - `seo_admin:206`

### AC3: Telemetria + audit script

- [ ] Promote `DATALAKE_TRUNCATION_SUSPECTED` counter de `metrics.py` para uso global (label=`route`, `entity_type`)
- [ ] Sentry breadcrumb em truncation suspect
- [ ] `backend/scripts/audit_postgrest_max_rows.py` — grep `\.limit\((1000|[2-9]\d{3,})\)` em `routes/` e fail se encontrar bare execute
- [ ] CI gate `.github/workflows/audit-postgrest-cap.yml` — exige zero violations

### AC4: Tests

- [ ] `backend/tests/test_postgrest_paginate.py` — unit tests do helper:
  - 0 rows → return []
  - <batch_size rows → 1 query, return all
  - Exatos batch_size rows → 2 queries (segunda vazia)
  - >batch_size rows → N queries até completar
  - max_total cap respeitado
- [ ] `backend/tests/integration/test_routes_no_silent_truncation.py` — fixture orgão sintético com 1500 contratos, confirmar route retorna 1500 (não 1000)
- [ ] Frontend: `/orgaos/[cnpj]` page snapshot test — count exibido = count real

### AC5: Doc + observabilidade

- [ ] Update `_reversa_sdd/review-report.md` — close gap em §11.4 (DATA-CAP-001 RESOLVED)
- [ ] Doc `docs/architecture/postgrest-pagination-patterns.md` — pattern A vs B decision tree + exemplos
- [ ] Sentry alert: trigger se `DATALAKE_TRUNCATION_SUSPECTED` rate > 10/h

---

## DoD

- [ ] 9 callsites refactored (Pattern A: 2; Pattern B: 7)
- [ ] Helper `postgrest_paginate.py` 100% covered
- [ ] CI gate ativo (zero violations baseline)
- [ ] Integration test orgão 1500-contratos PASS
- [ ] Frontend page exibe count real (validação Playwright snapshot)
- [ ] Sentry alert configurado
- [ ] Doc patterns + review-report close-out
- [ ] Memory entry: `feedback_postgrest_max_rows_silent_cap.md`

---

## Dependências

- Helper `_run_with_budget` existente — paginate loop deve respeitar budget (cada batch dentro de budget remanescente)

---

## Notes

- Memory `feedback_chief_revenue_aware_routing` Gate D: P0 reliability (n_paid não-zero, dados públicos visíveis = trust signal direto). NÃO defer.
- Não tocar `datalake_query.py` (já correto desde STORY-437). Replicar pattern.
