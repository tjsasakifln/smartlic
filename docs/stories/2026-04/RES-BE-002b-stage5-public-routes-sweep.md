# RES-BE-002b: Sweep Stage 5 — Rotas Públicas Programmatic Restantes

**Priority:** P0
**Effort:** M (2-3 dias)
**Squad:** @dev + @architect (impact analysis prévio em routes async helpers)
**Status:** Ready
**Epic:** [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md)
**Sprint:** Sprint 1 (2026-04-29 → 2026-05-05) — paralelo a [RES-BE-002](RES-BE-002-budget-top5-routes.md), executar IMEDIATAMENTE pós-merge RES-BE-002.
**Origem:** Sessão `/chief savvy-jasmine` 2026-04-28 — sweep mapping pós-Stage 5 saturação. Ver [handoff](../../sessions/2026-04/2026-04-28-chief-savvy-jasmine.md), memory `project_backend_outage_2026_04_29_stage5`, memory `feedback_sweep_single_pr_required`.
**Dependências bloqueadoras:** [RES-BE-001](RES-BE-001-audit-execute-without-budget.md) (gate CI auditoria). Helper canônico `_run_with_budget` já existe em `backend/pipeline/budget.py` (STORY-4.4 TD-SYS-003 — pre-existente, não depende de RES-BE-002 ship).

---

## Story

**As a** SmartLic engineering team facing recurring P0 wedges on programmatic public routes,
**I want** all `.execute()` callsites in 8 public-facing route modules wrapped in `_run_with_budget` budget + the `empresa_publica.perfil_b2g` async-helper bottleneck investigated and fixed + negative-cache pattern in 3 P0 endpoints,
**so that** the next Googlebot wave (expected 7-14d window) cannot trigger a Stage 6 wedge under WC=1, the SEO trust-score is preserved, and the Sprint 1 `WEB_CONCURRENCY=1→2` bump becomes safe to execute post-soak.

---

## Contexto

Stage 4 wedge (keen-neumann 2026-04-29 ~00:30 UTC) e Stage 5 saturação (savvy-jasmine ~01:30 UTC) confirmaram empíricamente o que o EPIC-RES-BE-2026-Q2 antecipou:

> **Memory `feedback_sweep_single_pr_required` (2x validado):** "Fix-per-route incremental confirmado insufficient. Sob WC=1, qualquer rota DB-bound não-coberta vira gargalo na próxima wave. Single PR multi-arquivo Sentry-priorized é o caminho."

RES-BE-002 cobre top-5 traffic auth-flow (mfa, referral, founding, conta) + sitemap_*. Stage 5 evidenciou que **rotas públicas programmatic SEO** (`empresa_publica`, `contratos_publicos`, `orgao_publico`, `itens_publicos`, `blog_stats`, `comparador`, `compliance_publicos`, `indice_municipal`) são o cluster que recebe a maior parte do crawl Googlebot e contém callsites residuais não cobertos pelo escopo RES-BE-002.

Sentry 24h pré-savvy-jasmine confirma:

| Endpoint | Events 14d | p99 latency | File path | Status pré-fix |
|---|---|---|---|---|
| `/v1/empresa/{cnpj}/perfil-b2g` | **482** | 2248s | `routes/empresa_publica.py:158` (async handler + helpers `_fetch_*`) | budget docstring linha 32, mas helpers async sem `_run_with_budget` |
| `/v1/orgao/{cnpj}/stats` | **478** | 130s | `routes/orgao_publico.py:225, 376` | 2 `.execute()` desprotegidos |
| `/v1/fornecedores/{cnpj}/profile` (em `contratos_publicos`) | **224** | 3027s | `routes/contratos_publicos.py:184, 236, 578` | 2 `.execute()` desprotegidos + handler `/fornecedores/{cnpj}/profile` |
| `contratos_publicos.py` (ConnectionTerminated cluster) | **99** | n/a | `routes/contratos_publicos.py` | pool exhaustion sob saturação |
| `/v1/itens/{id}/profile` | **49** | 2248s | `routes/itens_publicos.py:443` | 1 `.execute()` desprotegido |
| `/v1/blog/stats/cidade/.../setor/...` | **1 recente × 965s** | 965s | `routes/blog_stats.py:924` | partial (3 budget refs but 1 `.execute()` residual em `__resolve_supplier_count`) |
| `/v1/comparador` | low | desconhecido | `routes/comparador.py:165` | 1 `.execute()` desprotegido |
| `/v1/compliance/{cnpj}` | low | desconhecido | `routes/compliance_publicos.py:177` | 1 `.execute()` desprotegido |
| `/v1/indice-municipal/{municipio}` | low | desconhecido | `routes/indice_municipal.py:266` | 1 `.execute()` desprotegido |

**Total real callsites residuais cobertos por esta story:** 9 (`.execute()` literais) + investigação async helpers `_fetch_*` em `empresa_publica.py` (perfil-b2g handler é o top Sentry mas o gargalo está em chamadas internas, não no `.execute()` direto — ver AC1).

Hotfix PR #547 cobriu apenas `routes/observatorio.py` (1 callsite, reference pattern). Hotfixes PRs #529/#533/#535 cobriram callsites isolados em `empresa_publica.py:169` + `contratos_publicos.py:450` + `blog_stats.py` parcial — inadequado para fechar a janela.

Padrão canônico `_run_with_budget(coro, *, budget, phase, source, fallback=None)` definido em `backend/pipeline/budget.py` (STORY-4.4 TD-SYS-003, pre-existente). Internalmente usa `asyncio.wait_for(coro, timeout=budget)` + `_record_exceeded` Prometheus counter `PIPELINE_BUDGET_EXCEEDED_TOTAL`. Default `budget=5.0s` para programmatic SEO (queries agregadas), `budget=3.0s` para lookups simples.

**NOTA AMEND 2026-04-29 chief-stage6-firefight:** Story original referia `_maybe_wrap` (vapor — não existe no codebase). Stage 6 firefight discriminator empírico revelou helper real é `_run_with_budget`. Toda referência amendada nesta versão. Pattern PR #547 observatorio.py usou apenas `asyncio.to_thread` sem wrap timeout — esta story ENVELOPA tudo em `_run_with_budget` para garantir budget enforcement.

---

## Acceptance Criteria

### AC1: Investigação + Fix `routes/empresa_publica.py` (perfil-b2g handler)

- [ ] Read `backend/routes/empresa_publica.py` lines 154-600 — handler `perfil_b2g(cnpj)` linha 158 + helpers `_fetch_brasilapi`, `_fetch_contratos_pncp`, `_fetch_contratos_pt`, `_fetch_contratos_local`, `_fetch_contratos_pt_normalized`, `_fetch_editais_abertos`, `_build_perfil`
- [ ] Identificar onde a latência 2248s p99 é introduzida — provavelmente em `_fetch_contratos_local` (Supabase query `pncp_supplier_contracts` por `ni_fornecedor`) ou `_fetch_editais_abertos` (datalake search). Sentry trace + Prometheus histogram pode confirmar via `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{handler="perfil_b2g"}[5m]))`.
- [ ] Wrap async helpers DB-bound em `_run_with_budget(coro, budget=5.0, phase="route", source="empresa.perfil_b2g.<helper>")`. Se o helper já é async (i.e., usa Supabase async API ou httpx), `_run_with_budget` direto. Se sync `.execute()`, wrap em `asyncio.to_thread` primeiro.
- [ ] Adicionar `asyncio.gather(...)` com `return_exceptions=True` para paralelizar `_fetch_brasilapi` + `_fetch_contratos_local` + `_fetch_editais_abertos` se ainda sequenciais (P99 2248s sugere serial execution dos 3-4 helpers).
- [ ] Negative cache em handler-level: se qualquer helper falha, retornar partial response (already implemented at line 173 `perfil_b2g: total budget %.0fs exceeded for %s — returning unavailable partial`) — confirmar lógica pre-existente continua válida pós-wrap.
- [ ] Source labels: `empresa.perfil_b2g.brasilapi`, `empresa.perfil_b2g.contratos_local`, `empresa.perfil_b2g.editais_abertos`, `empresa.perfil_b2g.contratos_pt`, `empresa.perfil_b2g.contratos_pncp`.

### AC2: Wrap `.execute()` em `routes/contratos_publicos.py` (3 callsites)

- [ ] **Linha 184:** dentro de função relacionada a `/fornecedores/{setor}/{uf}/stats`. Wrap em `_run_with_budget(asyncio.to_thread(lambda: ...), budget=5.0, phase="route", source="contratos.fornecedores_setor_uf_stats")`.
- [ ] **Linha 236:** dentro de função relacionada a stats (verificar contexto). Source label: `contratos.<função>` baseado no contexto da função.
- [ ] **Handler `/fornecedores/{cnpj}/profile`** (declarado linha 578) — investigar se contém `.execute()` adicional ou usa helper já protegido. Aplicar mesmo pattern AC1 se chamadas async helpers DB-bound presentes (Sentry 224 events × 3027s sugere bottleneck similar a perfil-b2g).
- [ ] Adicionar negative cache: se query falha, registrar em Redis com TTL=300s; subsequent requests retornam fallback estruturado em vez de retentar query travada.
- [ ] Linha 650 já contém comment `# of bare .execute() so a Supabase outage trips the CB and fast-fails` — confirmar circuit breaker está ativo no callsite.

### AC3: Wrap `.execute()` em `routes/orgao_publico.py` (2 callsites)

- [ ] **Linha 225:** wrap pattern `_run_with_budget(asyncio.to_thread(...), budget=5.0, source="orgao.<função>")`.
- [ ] **Linha 376:** mesmo pattern. Source label distinto.
- [ ] `/v1/orgao/{cnpj}/stats` (Sentry 478 events × 130s) — handler é o top wedge source secundário; budget agressivo `3.0s` se query é simples lookup ou `5.0s` se agregação.

### AC4: Wrap `.execute()` em routes restantes (5 callsites)

- [ ] **`routes/itens_publicos.py:443`** — `/v1/itens/{id}/profile`. Source: `itens.profile`. Budget: 5.0s.
- [ ] **`routes/blog_stats.py:924`** — partial cleanup (file já tem 3 budget refs, 1 `.execute()` residual em `__resolve_supplier_count` ou similar). Source: `blog_stats.<função>`. Budget: 5.0s.
- [ ] **`routes/comparador.py:165`** — `result = sb.table("pncp_raw_bids").select("*").in_("pncp_id", id_list).execute()`. Source: `comparador.fetch_bids`. Budget: 5.0s.
- [ ] **`routes/compliance_publicos.py:177`** — Source: `compliance.<função>`. Budget: 5.0s.
- [ ] **`routes/indice_municipal.py:266`** — `/v1/indice-municipal/{municipio-uf}`. Source: `indice_municipal.<função>`. Budget: 5.0s.

### AC5: Negative cache pattern em rotas P0

- [ ] Para `empresa.perfil_b2g`, `contratos.fornecedores_profile`, `orgao.stats` (3 endpoints top-Sentry), adicionar cache stub em Redis quando query falha:
  ```python
  CACHE_KEY = f"negative_cache:{source}:{cnpj}"
  if await redis.exists(CACHE_KEY):
      logger.warning("negative_cache hit for %s, returning fallback", source)
      return _fallback_response(reason="upstream_unavailable")
  try:
      result = await _run_with_budget(...)
  except (TimeoutError, Exception) as exc:
      await redis.setex(CACHE_KEY, 300, "1")  # 5min negative cache
      raise
  ```
- [ ] TTL=300s default; configurable via env `NEGATIVE_CACHE_TTL_S=300`.
- [ ] Helper compartilhado em `backend/cache/negative.py` (criar) ou reuse `backend/cache/swr.py::trigger_background_revalidation` se aplicável.
- [ ] Métrica Prometheus: `smartlic_negative_cache_hits_total{source}` incrementa em cada hit.

### AC6: Métrica Prometheus + Sentry específicos para programmatic routes

- [ ] Counter `smartlic_pipeline_budget_exceeded_total{phase="route", source}` já existente (RES-BE-002 AC5) — confirmar incrementa para todos os 9 callsites desta story.
- [ ] Adicionar tag `route_class="programmatic_public"` para distinguir de auth-flow routes.
- [ ] Sentry capture nível `warning` em timeout — fingerprint `["route_budget_exceeded_programmatic", source]`. Permite filtro distinto para programmatic vs auth.
- [ ] Dashboard Grafana: panel `programmatic routes p99 latency by source` para visibilidade contínua.

### AC7: Testes timeout invariant + smoke

- [ ] Estender `backend/tests/test_route_timeout_invariants.py` (criado por RES-BE-002 AC6) com testes para 5 sources programmatic:
  - `test_empresa_perfil_b2g_respects_budget`
  - `test_orgao_stats_respects_budget`
  - `test_contratos_fornecedor_profile_respects_budget`
  - `test_itens_profile_respects_budget`
  - `test_indice_municipal_respects_budget`
- [ ] Cada teste: monkeypatch Supabase client com `time.sleep(7)` em `.execute()`; assert TimeoutError raised dentro de `budget + 0.5s`; assert counter `smartlic_pipeline_budget_exceeded_total{phase="route", source=<route_source>}` incrementa por 1.
- [ ] Smoke test sintético em `backend/tests/integration/test_route_smoke_budget.py` (criado por RES-BE-002 AC8) — adicionar 5 hits programmatic routes com mock slow Supabase; cada hit retorna 504/503/partial em <6s, não wedge.
- [ ] Test garante negative cache (AC5): 1ª request com falha registra cache; 2ª request <300s retorna fallback sem hit DB.

### AC8: Validação não-regressão via gate RES-BE-001

- [ ] Após implementação, rodar `python backend/scripts/audit_execute_without_budget.py --output-md`. Esperado count desprotegido cair de ~31 (pós-RES-BE-002) → ~22 (-9 desta story).
- [ ] Atualizar `backend/scripts/audit-baseline.json` na mesma PR (`--update-baseline`).
- [ ] Atualizar `docs/audit/execute-without-budget-{date}.md` com novo snapshot.
- [ ] CI gate (RES-BE-001) deve passar verde no PR.

### AC9: Soak monitoring 24h pós-deploy

- [ ] Após merge + Railway deploy, observar Sentry 24h:
  - `smartlic_pipeline_budget_exceeded_total{phase="route", route_class="programmatic_public"}` < 50 events em 24h (vs ~1184 events pré-fix)
  - `slow_request` >60s para `/v1/empresa/perfil-b2g`, `/v1/orgao/*/stats`, `/v1/fornecedores/*/profile`, `/v1/itens/*/profile` count = 0
  - `ConnectionTerminated` errors em `contratos_publicos`/`itens_publicos`/`blog_stats` count → 0
- [ ] Confirmar `/health/live` p99 < 2s sustained 24h (atualmente 502 timeout 16s sob saturação).
- [ ] **Apenas após soak limpo, gatilhar STORY paralela WEB_CONCURRENCY=1→2 bump** (memory `feedback_web_concurrency_4_amplifier` warn — não pular para 4).

---

## Tasks / Subtasks

- [ ] **Task 1: Investigate empresa_publica.perfil_b2g async-helper bottleneck (AC1)**
  - [ ] Read `backend/routes/empresa_publica.py` lines 154-600 — handler + helpers
  - [ ] Profile via Sentry trace + Prometheus `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{handler="perfil_b2g"}[5m]))` to identify the slowest helper
  - [ ] Verify whether `_fetch_brasilapi`, `_fetch_contratos_local`, `_fetch_editais_abertos` are serial or parallel (`asyncio.gather`)
  - [ ] Confirm or update docstring "Hard request budget: perfil-b2g must respond within 30s" (line 32) based on findings
  - [ ] Document investigation outcome in PR description (root cause + remediation choice)

- [ ] **Task 2: Wrap `empresa_publica.perfil_b2g` async helpers (AC1)**
  - [ ] Apply `_run_with_budget(coro, budget=5.0, phase="route", source="empresa.perfil_b2g.<helper>")` to each DB-bound helper
  - [ ] Wrap sync `.execute()` in `asyncio.to_thread` first if applicable
  - [ ] Convert serial helper calls to `asyncio.gather(..., return_exceptions=True)` if helpers are independent
  - [ ] Confirm partial-response fallback (line 173 `perfil_b2g: total budget %.0fs exceeded`) still triggers post-wrap

- [ ] **Task 3: Wrap `.execute()` in contratos_publicos.py (AC2)**
  - [ ] Wrap line 184 — source label tied to handler context
  - [ ] Wrap line 236 — source label tied to handler context
  - [ ] Inspect handler `/fornecedores/{cnpj}/profile` (line 578) — apply same pattern as Task 2 if async helpers found
  - [ ] Add negative-cache hook (Task 6 helper) when query fails

- [ ] **Task 4: Wrap `.execute()` in orgao_publico.py + itens_publicos.py + blog_stats.py + comparador.py + compliance_publicos.py + indice_municipal.py (AC3, AC4)**
  - [ ] orgao_publico.py: wrap lines 225, 376 (budget=5.0s aggregation OR 3.0s if simple lookup)
  - [ ] itens_publicos.py: wrap line 443 (budget=5.0s, source=`itens.profile`)
  - [ ] blog_stats.py: wrap line 924 residual (file already has 3 budget refs)
  - [ ] comparador.py: wrap line 165 (source=`comparador.fetch_bids`)
  - [ ] compliance_publicos.py: wrap line 177
  - [ ] indice_municipal.py: wrap line 266

- [ ] **Task 5: Implement negative-cache helper `backend/cache/negative.py` (AC5)**
  - [ ] Create file with `check_negative_cache(source, key)` + `set_negative_cache(source, key, ttl=300)`
  - [ ] Reuse `redis_client.get_redis()` connection pool
  - [ ] Add env vars `NEGATIVE_CACHE_ENABLED=true`, `NEGATIVE_CACHE_TTL_S=300` to `backend/config.py`
  - [ ] Document in `CLAUDE.md` "Critical Implementation Notes" rollback toggle

- [ ] **Task 6: Apply negative-cache pattern in 3 P0 endpoints (AC5)**
  - [ ] `empresa.perfil_b2g`: wrap handler with `check_negative_cache` pre-call + `set_negative_cache` on TimeoutError
  - [ ] `contratos.fornecedores_profile`: same pattern
  - [ ] `orgao.stats`: same pattern
  - [ ] Each endpoint returns `_fallback_response(reason="upstream_unavailable", retry_after=300)` on cache hit

- [ ] **Task 7: Add Prometheus + Sentry instrumentation (AC6)**
  - [ ] Add tag `route_class="programmatic_public"` to `_record_exceeded` calls
  - [ ] Counter `smartlic_negative_cache_hits_total{source}` increment in `check_negative_cache` on hit
  - [ ] Sentry fingerprint `["route_budget_exceeded_programmatic", source]` in `_record_exceeded` when `route_class="programmatic_public"`
  - [ ] Open Grafana panel "programmatic routes p99 latency by source" (link or YAML in PR)

- [ ] **Task 8: Extend test suites (AC7)**
  - [ ] `backend/tests/test_route_timeout_invariants.py`: add 5 tests (`test_empresa_perfil_b2g_respects_budget`, `test_orgao_stats_respects_budget`, `test_contratos_fornecedor_profile_respects_budget`, `test_itens_profile_respects_budget`, `test_indice_municipal_respects_budget`)
  - [ ] `backend/tests/integration/test_route_smoke_budget.py`: add 5 hits programmatic routes with mock slow Supabase
  - [ ] Add 1 test verifying negative cache: 1st call sets cache, 2nd within 300s returns fallback without DB hit
  - [ ] Coverage ≥85% on touched lines (`pytest --cov=backend/routes/empresa_publica,backend/routes/contratos_publicos,backend/routes/orgao_publico,backend/routes/itens_publicos,backend/routes/blog_stats,backend/routes/comparador,backend/routes/compliance_publicos,backend/routes/indice_municipal,backend/cache/negative`)

- [ ] **Task 9: Update audit baseline + gate CI (AC8)**
  - [ ] Run `python backend/scripts/audit_execute_without_budget.py --output-md`
  - [ ] Confirm count drops from ~31 (post RES-BE-002) → ~22
  - [ ] `--update-baseline` to refresh `backend/scripts/audit-baseline.json`
  - [ ] Update `docs/audit/execute-without-budget-{date}.md`
  - [ ] CI gate (RES-BE-001) green on PR

- [ ] **Task 10: Soak monitor 24h post-deploy (AC9)**
  - [ ] After PR merged + Railway deploy, set timer 24h
  - [ ] Query Sentry: `smartlic_pipeline_budget_exceeded_total{phase="route", route_class="programmatic_public"}` < 50 events / 24h
  - [ ] Verify `slow_request` >60s for the 4 P0 endpoints = 0
  - [ ] Verify `ConnectionTerminated` errors in `contratos_publicos`/`itens_publicos`/`blog_stats` = 0
  - [ ] Verify `/health/live` p99 < 2s sustained
  - [ ] Document soak findings in PR description or follow-up handoff
  - [ ] **Only after soak GREEN: trigger paralelo story `WEB_CONCURRENCY=1→2`** (do NOT bundle)

---

## Scope

**IN:**
- Wrap de 9 callsites `.execute()` literais em 8 arquivos (empresa_publica investigation, contratos_publicos × 3, orgao_publico × 2, itens_publicos, blog_stats residual, comparador, compliance_publicos, indice_municipal)
- Investigation + fix async helpers em `empresa_publica.py::perfil_b2g` handler (top Sentry source 482×2248s)
- Negative cache pattern em 3 endpoints P0 (empresa.perfil_b2g, contratos.fornecedores_profile, orgao.stats)
- Métrica `route_class` tag programática para visibilidade Grafana
- Testes invariantes 5 sources programmatic + smoke
- Soak monitor 24h pós-merge

**OUT:**
- Wrap de callsites residuais em routes auth-flow restantes (já cobertos por RES-BE-002)
- Wrap de routes admin/devops (`admin*.py`, `seo_admin.py`) — backlog Sprint 2
- Bulkhead per-source (RES-BE-010)
- Circuit breaker Supabase upgrade (RES-BE-012)
- Cache positive layer (já existente `backend/cache/swr.py`)
- WEB_CONCURRENCY=1→2 (story paralela post-soak — memory warn)
- DB index optimization para queries lentas (RES-BE-009 triage)

---

## Definition of Done

- [ ] 9 callsites `.execute()` wrappados via `_run_with_budget`
- [ ] empresa_publica.py async helpers fixed (paralelização + budget)
- [ ] Negative cache implementado em 3 endpoints P0
- [ ] `audit-baseline.json` atualizado, gate CI verde
- [ ] Cobertura testes ≥85% nas linhas tocadas
- [ ] Sem regressão em testes existentes (5131+ passing, 0 failures)
- [ ] Suite tempo total CI <8min mantido
- [ ] Sentry capture validado em staging (warning visível por source)
- [ ] CodeRabbit review clean (CRITICAL=0, HIGH=0)
- [ ] PR review por @architect (Aria) + @qa (Quinn) com verdict PASS
- [ ] Deploy staging passa smoke test sintético sem wedge
- [ ] Soak 24h prod limpo (AC9 metrics)
- [ ] Rollback runbook validado (toggle `ENABLE_BUDGET_WRAP=false` → comportamento pre-wrap em <2min)

---

## Dev Notes

### Paths absolutos

- `/mnt/d/pncp-poc/backend/routes/empresa_publica.py` — investigate handler `perfil_b2g` linha 158 + helpers `_fetch_*` (linhas 240-562)
- `/mnt/d/pncp-poc/backend/routes/contratos_publicos.py` — wrap linhas 184, 236; handler `/fornecedores/{cnpj}/profile` linha 578 investigate
- `/mnt/d/pncp-poc/backend/routes/orgao_publico.py` — wrap linhas 225, 376
- `/mnt/d/pncp-poc/backend/routes/itens_publicos.py` — wrap linha 443
- `/mnt/d/pncp-poc/backend/routes/blog_stats.py` — wrap linha 924 (residual)
- `/mnt/d/pncp-poc/backend/routes/comparador.py` — wrap linha 165
- `/mnt/d/pncp-poc/backend/routes/compliance_publicos.py` — wrap linha 177
- `/mnt/d/pncp-poc/backend/routes/indice_municipal.py` — wrap linha 266
- `/mnt/d/pncp-poc/backend/cache/negative.py` (CRIAR) — helper negative cache compartilhado
- `/mnt/d/pncp-poc/backend/pipeline/budget.py` — `_run_with_budget` (existente pós RES-BE-002)
- `/mnt/d/pncp-poc/backend/tests/test_route_timeout_invariants.py` — extender com 5 testes
- `/mnt/d/pncp-poc/backend/tests/integration/test_route_smoke_budget.py` — extender com 5 hits programmatic

### Pattern reference: PR #547 (`backend/routes/observatorio.py`)

Reference fix do mesmo cluster (single callsite). Replicar para os 9 desta story.

### Padrão de wrap canônico (igual RES-BE-002)

```python
import asyncio
from pipeline.budget import _run_with_budget

# Antes (vulnerável):
result = supabase.from_("orgao_stats").select("*").eq("cnpj", cnpj).execute()

# Depois (protegido):
result = await _run_with_budget(
    asyncio.to_thread(
        lambda: supabase.from_("orgao_stats")
        .select("*")
        .eq("cnpj", cnpj)
        .execute()
    ),
    budget=5.0,
    phase="route",
    source="orgao.fetch_stats",
)
```

### Padrão negative cache (novo, AC5)

```python
# backend/cache/negative.py
from redis_client import get_redis

async def check_negative_cache(source: str, key: str) -> bool:
    redis = await get_redis()
    cache_key = f"negative_cache:{source}:{key}"
    return bool(await redis.exists(cache_key))

async def set_negative_cache(source: str, key: str, ttl: int = 300) -> None:
    redis = await get_redis()
    cache_key = f"negative_cache:{source}:{key}"
    await redis.setex(cache_key, ttl, "1")
```

Aplicação no handler:

```python
# backend/routes/empresa_publica.py
from cache.negative import check_negative_cache, set_negative_cache

async def perfil_b2g(cnpj: str):
    if await check_negative_cache("empresa.perfil_b2g", cnpj):
        return _fallback_response(reason="upstream_unavailable", retry_after=300)
    try:
        result = await _run_with_budget(...)
    except TimeoutError:
        await set_negative_cache("empresa.perfil_b2g", cnpj, ttl=300)
        raise
```

### Budgets por rota

| Rota | Budget | Justificativa |
|---|---|---|
| empresa.perfil_b2g.* | 5.0s (per-helper); 30s total handler (mantém budget existente) | Multi-fonte: BrasilAPI + DataLake + supplier_contracts |
| contratos.fornecedores_profile | 5.0s | Lookup `pncp_supplier_contracts` por `ni_fornecedor` (indexed) |
| orgao.stats | 3.0s | Aggregation simples |
| itens.profile | 5.0s | Lookup + agregação |
| blog_stats.* | 5.0s | Aggregation por cidade/setor |
| comparador.fetch_bids | 5.0s | `pncp_raw_bids` IN (id_list) batch |
| compliance.* | 5.0s | Multi-tabela join |
| indice_municipal.* | 5.0s | Aggregation com IBGE join |

Se algum endpoint genuinamente precisa >5s, levantar com @architect — sinal de query mal otimizada (deferir para RES-BE-009 triage). NÃO subir budget arbitrariamente.

### Frameworks de teste

- pytest 8.x + pytest-asyncio
- File location: `backend/tests/test_route_timeout_invariants.py` (extender), `backend/tests/integration/test_route_smoke_budget.py` (extender)
- Marks: `@pytest.mark.timeout(10)` para testes timeout invariant
- Fixtures: `monkeypatch` Supabase client (não fixture global; isolado)
- Auth: `app.dependency_overrides[require_auth]` para bypass se aplicável (programmatic routes são públicas — pode não ser necessário)
- Pattern de mock para negative cache: usar `fakeredis` ou monkeypatch `cache.negative.check_negative_cache`

### Convenções

- Não alterar response model das rotas (apenas wrap interno + adicionar campo `degraded: bool` opcional em fallback)
- Logger usa `logger.warning(...)` em path de timeout
- Sentry captura via integração existente
- Type hints obrigatórios

### Investigação `empresa_publica.py::perfil_b2g` (AC1)

Handler linha 158 já tem comment "Hard request budget: perfil-b2g must respond within 30s or fall back" (linha 32). Investigar:

1. **Existe budget timeout no handler?** Buscar `asyncio.wait_for(.., timeout=30)` ou similar wrapper no `perfil_b2g(cnpj)`.
2. **Helpers async são paralelizados?** Verificar se `_fetch_brasilapi`, `_fetch_contratos_local`, `_fetch_editais_abertos` são chamados em `asyncio.gather` ou serialmente.
3. **Cada helper tem budget próprio?** Provável que `_fetch_contratos_local` (Supabase query supplier_contracts por ni_fornecedor) é o gargalo — query pode hit table-scan se index `ni_fornecedor` está faltando.
4. **Resultado p99 2248s indica:** ou (a) handler timeout 30s não está aplicando, ou (b) helpers serial + cada um com latência ~600-800s sob saturação WC=1.

Output AC1: relatório breve em PR description + atualização linha 32 docstring se budget escalonamento mudar.

---

## Risk & Rollback

| Trigger | Ação |
|---|---|
| p99 latency programmatic routes > 2x baseline pós-deploy | `railway variables --service bidiq-backend --set ENABLE_BUDGET_WRAP=false`; rollback effective em ~30s |
| Counter `smartlic_pipeline_budget_exceeded_total{phase="route", route_class="programmatic_public"}` >5/min sustained | Identificar source via label; ajustar budget para 7s ou 10s para essa rota específica via env override `BUDGET_OVERRIDE_<source>=10` |
| Negative cache estourando memória Redis | Reduzir TTL para 60s ou desabilitar via `NEGATIVE_CACHE_ENABLED=false` |
| Sentry flood programmatic (>50 events/min) | Aumentar fingerprint dedup ou subir threshold; não desabilitar wrap |
| Soak 24h falha (AC9 metrics não atingidas) | Investigar source(s) específicos via `route_class` tag; iterar fix antes de WC bump |
| Empresa.perfil_b2g async paralelização introduz race condition | Reverter para serial; adicionar lock per-cnpj se necessário |

**Rollback completo:** revert PR. Feature flag `ENABLE_BUDGET_WRAP` permite rollback parcial sem revert (pré-existente RES-BE-002).

---

## Dependencies

**Entrada:**
- [RES-BE-001](RES-BE-001-audit-execute-without-budget.md) — gate CI ativo (audit script)
- [RES-BE-002](RES-BE-002-budget-top5-routes.md) — helper `_run_with_budget` em `backend/pipeline/budget.py` + feature flag `ENABLE_BUDGET_WRAP` em `backend/config.py`
- `backend/cache/swr.py` — reference pattern para negative cache helper

**Saída (esta story bloqueia):**
- **WC bump 1→2 (story paralela)** — não criar até soak 24h limpo (AC9). Memory `feedback_web_concurrency_4_amplifier` warn.
- [RES-BE-003](RES-BE-003-negative-cache-failure-paths.md) — esta story implementa subset do escopo RES-BE-003 (3 endpoints P0); RES-BE-003 fica reduzido a routes residuais
- [RES-BE-010](RES-BE-010-bulkheads-critical-routes.md) — bulkhead complementa budget+negative cache
- [RES-BE-012](RES-BE-012-circuit-breaker-supabase.md) — breaker downstream

**Cross-reference:**
- Memory `project_backend_outage_2026_04_29_stage5` — Stage 5 saturação root cause
- Memory `feedback_sweep_single_pr_required` — sweep multi-route mandate
- [Handoff savvy-jasmine](../../sessions/2026-04/2026-04-28-chief-savvy-jasmine.md) — bootstrap empírico + mapping origem
- PR #547 (observatorio.py) — reference pattern fix
- Issue #541 — schema drift `top_result_*` (UNRELATED, separate story)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-28
**Verdict:** GO (Conditional → applied)
**Score:** 9/10
**Implementation Readiness:** 9/10
**Confidence Level:** High

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|---|---|---|
| 1 | Clear and objective title | ✓ | "Sweep Stage 5 — Rotas Públicas Programmatic Restantes" — escopo claro, complementaridade a RES-BE-002 explícita. |
| 2 | Complete description | ✓ | Conecta Stage 4 + Stage 5 incidents → 9 callsites residuais + investigation `empresa_publica`; tabela Sentry events table comprovação empírica. |
| 3 | Testable acceptance criteria | ✓ | 9 ACs testáveis; AC7 fornece testes específicos por source; AC9 critérios numéricos soak (<50 events/24h, p99 <2s). |
| 4 | Well-defined scope | ✓ | IN/OUT explícitos; OUT delimita admin routes + bulkhead + DB index optimization (defer Sprint 2/3). |
| 5 | Dependencies mapped | ✓ | Entrada RES-BE-001 + RES-BE-002 (helper `_run_with_budget`); saída RES-BE-003 (escopo reduzido), RES-BE-010, RES-BE-012; bloqueia WC bump 1→2. |
| 6 | Complexity estimate | ✓ | M (2-3 dias) realista para 9 callsites + investigation + negative cache helper + tests + soak. Comparable a RES-BE-002 (M, 3 dias, 25 callsites simples vs 9 complexos). |
| 7 | Business value | ✓ | "Janela 7-14d antes próxima onda Googlebot" empíricamente confirmada (Stage 5 recidivou em ~24h). Pré-requisito de WC bump 1→2 (Sprint 1 must). |
| 8 | Risks documented | ✓ | 6 cenários incluindo race condition empresa_publica paralelização + Sentry flood + Redis memory; rollback feature flag <2min. |
| 9 | Criteria of Done | ✓ | 13 itens incluindo soak 24h prod limpo (AC9 metrics) + rollback runbook validado. |
| 10 | Alignment with PRD/Epic | ✓ | Métrica #1 EPIC ("smartlic_route_timeout_total = 0 sob 5x carga") testada por AC7+AC9. |

### Required Fixes (applied autonomously by PO during validation)

1. ✅ **Added `## Story` section** — As a / I want / so that template-text format. Source: PO autonomous prep per `core_principles.Autonomous Preparation of Work`.
2. ✅ **Added `## Tasks / Subtasks` section** — 10 tasks linkando explicitamente aos ACs com paths absolutos + line numbers + comandos shell. Pattern reuse de RES-BE-002.

Both fixes are template-completeness (NOT scope/AC modifications) — autorizadas sob PO autonomous-preparation principle. @sm collaboration acknowledged.

### Should-Fix (not blocking; tracked for Sprint follow-up)

- AC1 investigation outcome may expand fix scope >2x estimate. Risk row 6 documents escalation path via @architect — sufficient for now.
- AC5 negative cache TTL=300s default is empirical guess; could be tuned via `NEGATIVE_CACHE_TTL_S` env post-soak based on observed recovery time.

### Nice-to-Have

- Add explicit DataLake query budget for `_fetch_editais_abertos` em AC1 — defer to investigation outcome.
- Grafana dashboard JSON checked-in vs link-only — defer to @architect.

### Observations

- Story-checklist mental run by @sm (River) reportou PASS pre-validation. Confirmado 9/10 score.
- Empresa_publica investigation (AC1) é a maior incerteza, mas PO accepts investigation+fix combined as 1 AC pq trace + remediation são tightly coupled (não vale separar em 2 stories).
- Pattern reuse (`_run_with_budget` from RES-BE-002, observatório.py PR #547 reference) reduz risco implementação.
- Soak monitoring (AC9) é gate explícito antes de WC bump — discriminator goes blind se bundled. Reforçado em memory `feedback_web_concurrency_4_amplifier`.
- Story 100% rastreável a Stage 5 incident (handoff savvy-jasmine) + memory updates — Constitution Article IV (No Invention) compliant.

### Status Transition

`Draft → Ready` aplicado. @dev pode iniciar `*develop-story` quando capacity disponível. RES-BE-002 deve mergear ANTES (helper `_run_with_budget` é pré-requisito).

---

## Change Log

| Data | Versão | Descrição | Autor |
|---|---|---|---|
| 2026-04-28 | 1.0 | Story criada — sweep Stage 5 routes públicas programmatic complementar a RES-BE-002. Origem: chief-savvy-jasmine handoff. | @sm (River) |
| 2026-04-28 | 1.1 | PO validation 10-point: GO conditional (9/10). PO autonomous-prep applied 2 template fixes: added `## Story` section + `## Tasks / Subtasks` (10 tasks). Status: Draft → Ready. RES-BE-002 merge é pré-requisito (helper `_run_with_budget`). | @po (Pax) |
| 2026-04-29 | 1.2 | **AMEND post-Stage 6 firefight (chief session):** Substituído `_maybe_wrap` (vapor — não existe) por `_run_with_budget` (canônico, em `backend/pipeline/budget.py` STORY-4.4 TD-SYS-003 pre-existente) em 18 ocorrências. Removida dependência bloqueadora RES-BE-002 (helper já existe há semanas, era erro de spec). Status mantém Ready. Implementação pode iniciar imediatamente. | @po (Pax) via /chief |
