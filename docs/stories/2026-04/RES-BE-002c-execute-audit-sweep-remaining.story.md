# RES-BE-002c: Audit completo `.execute()` remaining (continuação PR #549)

**Priority:** P0
**Effort:** 1.5d
**Squad:** @data-engineer (audit) → @dev (sweep)
**Status:** InProgress (Phase 0 + top-tier sweep done; mid+low tier deferred)
**Epic:** [EPIC-RES-BE-2026-Q2](EPIC-RES-BE-2026-Q2.md)
**Sprint:** Sprint Atual (2026-04-29 → 2026-05-12)
**Tipo:** Resilience / Sweep
**Bloqueado por:** SEN-BE-010 prefira merge antes (memory leak fix priority)

---

## Contexto

PR #549 (RES-BE-002b) merged 2026-04-29 cobriu 9 callsites com `_run_with_budget` + negative cache pattern (`docs/sessions/2026-04/2026-04-29-chief-savvy-jasmine.md` → swift-mendel). Lista exata de rotas remaining sem `_run_with_budget` é **LACUNA confirmada** (`docs/analysis/chief-stage7-definitive-solution.md:39`).

Stage 4-7 cycle proven: routes DB-bound sem budget+wait_for + sync `.execute()` em handler async = wedge sob bot/cron load. PR #549 + #535 cobriram batch principal mas residuais existem em SEO programmatic + admin + raros. Sweep universal cobre todos remaining em 1 PR (memory `feedback_sweep_single_pr_required` + `feedback_cluster_sweep_pattern`: hypothesis-first, 1-commit-per-cluster).

---

## Acceptance Criteria

### AC1: Phase 0 audit — listar callsites remaining

**Given** PR #549 cobriu 9 callsites; remaining unknown
**When** @data-engineer roda audit grep
**Then**:

- [ ] Comando audit executado:
  ```bash
  grep -rEn "\.execute\(" backend/routes/ \
    | grep -v "_run_with_budget" \
    | grep -v "asyncio.to_thread" \
    | grep -v "test_"
  ```
- [ ] Output salvo em `docs/audit/execute-callsites-2026-04-29.md` com:
  - File:line
  - Context (route name)
  - Sentry impressions count last 7d (Sentry API query)
  - Risk tier (high=>1k impressions, medium=100-1k, low=<100)

### AC2: Ranquear por Sentry impressions

- [ ] Top routes saturated identified (high tier)
- [ ] Match contra Stage 4-7 sessions evidence:
  - `/v1/empresa/*/perfil-b2g` (Stage 5 Sentry-priorized P0)
  - `/v1/contratos/*` publicos
  - `/v1/orgaos/publicos/*`
  - SEO programmatic routes (18 routers)
- [ ] Output `docs/audit/execute-sweep-priority-list.md`

### AC3: Sweep universal (single PR)

**Given** AC1 + AC2 produzem priority list
**When** @dev wrap remaining em `_run_with_budget`
**Then**:

- [ ] Pattern aplicado:
  ```python
  result = await _run_with_budget(
      asyncio.to_thread(lambda: supabase.from_("...").select("...").execute()),
      timeout=10,
      phase="route_X"
  )
  ```
- [ ] Reusable: `backend/pipeline/budget.py::_run_with_budget`
- [ ] Single PR multi-arquivo (NOT per-route — memory `feedback_sweep_single_pr_required` confirmado 2× em Stages 4+5)

### AC4: Aggressive negative cache em rotas bot-thrashable

**Given** rotas bot-thrashable identificadas (perfil-b2g, fornecedor profile, sitemap endpoints)
**When** @dev adiciona negative cache layer
**Then**:

- [ ] TTL 300s em response 404/empty antes de DB query expensive
- [ ] Redis key pattern: `negcache:{route}:{key_hash}`
- [ ] Reusable: cache pattern em `backend/cache/manager.py`
- [ ] Cache hit short-circuits BEFORE DB call

### AC5: Tests + ruff

- [ ] 197+ backend tests pass (Zero-Failure Policy CLAUDE.md)
- [ ] `ruff check . && mypy .` clean
- [ ] Add regression test: cada nova `_run_with_budget` callsite tem unit test verifying timeout + budget exceeded behavior

### AC6: 24h soak post-merge

- [ ] Deploy PR sweep
- [ ] Monitor 24h:
  - Zero `/sitemap/*after 3 attempts` Sentry events
  - Zero new Stage 4-7 pattern (worker stuck simultâneo)
  - p95 latency `/v1/empresa/*/perfil-b2g` <2s sustained
- [ ] Critério ROLLBACK: ≥3 wedge events em 24h pós-deploy → revert + escalate

---

## Scope

**IN:**
- Phase 0 audit grep + Sentry priority ranking
- Single PR sweep universal `_run_with_budget` pattern
- Aggressive negative cache em rotas bot-thrashable
- Test regression
- 24h soak monitoring

**OUT:**
- WC bump (escopo separate post-soak — memory `feedback_web_concurrency_4_amplifier`)
- Memory leak fix (escopo SEN-BE-010)
- Frontend resilience (escopo SEN-FE-002 + FOUND-SCALE-002)
- Sitemap particionado (escopo SEO-PROG-006)
- MV/ETL licitacoes-indexable (escopo SEN-BE-009)

---

## Definition of Done

- [ ] AC1 audit doc commited + Sentry data captured
- [ ] AC2 priority list documented
- [ ] AC3 single PR multi-arquivo merged
- [ ] AC4 negative cache verified hit rate >50% sob bot wave
- [ ] AC5 tests + ruff clean
- [ ] AC6 24h soak passa critério
- [ ] PR aprovado @data-engineer + @dev + @qa
- [ ] Change Log atualizado

---

## Dev Notes

### Paths absolutos

- **Audit script reusable:** `/mnt/d/pncp-poc/scripts/audit_execute_callsites.sh` (NEW)
- **Audit output:** `/mnt/d/pncp-poc/docs/audit/execute-callsites-2026-04-29.md` (NEW)
- **Priority list:** `/mnt/d/pncp-poc/docs/audit/execute-sweep-priority-list.md` (NEW)
- **Routes suspect:**
  - `backend/routes/empresa_publica.py`
  - `backend/routes/orgao_publico.py`
  - `backend/routes/contratos_publicos.py`
  - 18 SEO programmatic `*_publicos.py`
  - admin routes
- **Pattern reusable:** `backend/pipeline/budget.py::_run_with_budget`
- **Cache pattern:** `backend/cache/manager.py`

### Memory references

- `project_sitemap_endpoints_wedge_2026_04_27` — root cause structural
- `feedback_sweep_single_pr_required` — confirmed 2× Stages 4+5
- `feedback_cluster_sweep_pattern` — hypothesis-first BTS-style
- `project_backend_outage_2026_04_29_stage5` — 10 routes mapped Sentry-priorized

### Sentry API query (audit)

```bash
SENTRY_TOKEN=$(grep SENTRY_AUTH_TOKEN .env | cut -d= -f2)
curl -H "Authorization: Bearer $SENTRY_TOKEN" \
  "https://sentry.io/api/0/organizations/confenge/issues/?project=smartlic-backend&statsPeriod=7d&query=is:unresolved" \
  | jq '.[] | {title, count, culprit}'
```

### Reusable pattern

```python
# Wrap any synchronous .execute() Supabase call
async def _safe_db_query(table: str, query_fn, timeout: float = 10.0, phase: str = "default"):
    return await _run_with_budget(
        asyncio.to_thread(query_fn),
        timeout=timeout,
        phase=phase
    )
```

---

## Risk & Rollback

| Trigger | Ação |
|---------|------|
| Sweep introduz regressão em route não-saturated | Revert PR; adicionar test isolated |
| Negative cache TTL muito agressivo (304 stale) | Tune TTL via env var `NEGCACHE_TTL_SECONDS` |
| Audit grep miss callsites em files nested | Re-grep com `--include="*.py"` glob recursive |

**Rollback path:** revert PR via @devops; sweep granular per-route se single PR conflita com merge train.

---

## Dependencies

**Entrada:**
- PR #549 merged ✅
- pattern `backend/pipeline/budget.py` available

**Saída:**
- Desbloqueia OPS-CI-002 (load test post-sweep)
- Reduce Stage 8 risk

**Paralelas:**
- SEN-BE-009 (MV/ETL — independente)
- SEN-BE-010 (memory leak — recomenda merge antes)
- SEN-FE-002 + FOUND-SCALE-002 (frontend layer)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-29
**Verdict:** GO
**Score:** 10/10

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Clear and objective title | OK | Audit `.execute()` remaining continuação PR #549 |
| 2 | Complete description | OK | Pattern PR #549 estabelecido; gap LACUNA confirmada chief-stage7-definitive-solution.md:39 |
| 3 | Testable acceptance criteria | OK | AC1-AC6 com Sentry priority ranking + 24h soak |
| 4 | Well-defined scope | OK | OUT exclude WC bump, leak fix, frontend, sitemap partition |
| 5 | Dependencies mapped | OK | PR #549 ✅ available; saída OPS-CI-002 |
| 6 | Complexity estimate | OK | 1.5d consistente — audit 0.5d + sweep 1d |
| 7 | Business value | OK | Stage 8 recurrence guard; pattern proven em 2 outage stages |
| 8 | Risks documented | OK | 3 triggers + rollback |
| 9 | Criteria of Done | OK | 24h soak + zero wedge events explícito |
| 10 | Alignment with PRD/Epic | OK | EPIC-RES-BE-2026-Q2 |

Status: Draft → Ready.

## Change Log

| Data | Versão | Descrição | Autor |
|------|--------|-----------|-------|
| 2026-04-29 | 1.0 | Story criada via batch sm-briefing-100pct §3.2.3. Continuação direta PR #549 (RES-BE-002b). NEW story, anti-duplicate grep zero matches em RES-BE-002c. | @sm (River) |
| 2026-04-29 | 1.1 | PO validation: GO (10/10). Status: Draft → Ready. | @po (Pax) |
| 2026-04-29 | 1.2 | **Implementado Wave 5 — zany-kurzweil session.** AC1+AC2 done: audit script `scripts/audit_execute_callsites.sh` (re-runnable) + outputs `docs/audit/execute-callsites-2026-04-29.md` (57 callsites listed) + `docs/audit/execute-sweep-priority-list.md` (3-tier classification). AC3+AC4 top-tier sweep done (5 callsites Stage 5 P0 — memory `project_backend_outage_2026_04_29_stage5`): `contratos_publicos.py:184,236` + `orgao_publico.py:225,376` + `municipios_publicos.py:378`. Pattern: `await _run_with_budget(asyncio.to_thread(_query), budget=10s, phase="public_route", source=...)`. Negative cache 5min em `contratos_publicos.py:236` (Googlebot retry storm prevention). Graceful degradation: 503 ou empty result on TimeoutError. AC5 regression tests `backend/tests/test_publicos_budget.py` (5 test cases — happy path + timeout 503/zero result). AC6 24h soak handoff post-merge (Sentry monitor). **Mid+low tier deferred next session:** mfa.py 10 callsites, conta.py 4, referral.py 7, etc. = ~25 callsites — auth path baixo bot impact, sweep proximo apos top-tier soak verde. Status: Ready → InProgress. | @dev (James) |

## File List

- `scripts/audit_execute_callsites.sh` (NEW chmod +x — AC1 audit script re-runnable)
- `docs/audit/execute-callsites-2026-04-29.md` (NEW — AC1 output 57 callsites)
- `docs/audit/execute-sweep-priority-list.md` (NEW — AC2 3-tier classification)
- `backend/routes/contratos_publicos.py` (sweep 2 callsites + negcache TTL on timeout — AC3+AC4)
- `backend/routes/orgao_publico.py` (sweep 2 callsites + import asyncio + negcache constant — AC3+AC4)
- `backend/routes/municipios_publicos.py` (sweep 1 callsite + import budget — AC3)
- `backend/tests/test_publicos_budget.py` (NEW regression tests — AC5)
