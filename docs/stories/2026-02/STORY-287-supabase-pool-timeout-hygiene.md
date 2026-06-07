# STORY-287: Supabase Connection Pool & Timeout Hygiene

**Priority:** P1
**Effort:** S (0.5 day)
**Squad:** @dev
**Fundamentacao:** GTM Readiness Audit Track 6 (Performance) — sem connection pool config, timeout inconsistente
**Status:** InProgress
**Sprint:** GTM Sprint 1

---

## Contexto

O audit identificou dois gaps de performance:

1. **Supabase connection pool** nao configurado explicitamente — usa defaults do supabase-py. Sob carga concorrente, risco de connection exhaustion.
2. **SEARCH_FETCH_TIMEOUT** em 360s (6 min) para background async fetch e excessivo e consome recursos desnecessariamente.
3. **CONSOLIDATION_TIMEOUT** inconsistente entre `config.py` (100s) e `source_config/sources.py` (300s).

---

## Acceptance Criteria

### AC1: Configure Supabase connection pool
- [x] Investigar se `supabase-py` expone configuracao de pool (httpx pool limits)
- [x] Configurado via `_configure_httpx_pool()` em `supabase_client.py` (CRIT-046/DEBT-018)
  - `max_connections=10`, `max_keepalive_connections=5` via env vars (reduzido intencionalmente para free tier)
  - `timeout=30s`, `connect_timeout=10s`
  - Pool health logging periodico (cada ~50 calls)
- [ ] N/A: Limitacao ja documentada no codigo (supabase-py expoe pool via httpx)
- [ ] Teste de carga: 10 buscas concorrentes sem connection errors

### AC2: Reduce SEARCH_FETCH_TIMEOUT
- [x] Reduzir `SEARCH_FETCH_TIMEOUT` de 360s para 180s (via `3 * 60` nos arquivos)
- [x] Manter como env-configurable via `SEARCH_FETCH_TIMEOUT` env var
- [x] Documentar razao da mudanca (comentarios nos arquivos)

### AC3: Reconcile CONSOLIDATION_TIMEOUT values
- [x] Investigado: CONSOLIDATION_TIMEOUT (90s em config/pncp.py) e CONSOLIDATION_TIMEOUT_GLOBAL (90s em sources.py) ja estao sincronizados em 90s
- [x] Story desatualizada: valores originais mencionados (300s/100s) foram reconciliados por STORY-4.4 TD-SYS-003
- [ ] N/A: Nao requer acao — valores ja reconciliados

### AC4: Documentation cleanup
- [x] Atualizar arquivos de configuracao (comentarios nos arquivos alterados)
- [ ] N/A: CLAUDE.md timeout chain ja reflete waterfall STORY-4.4 (nada mudou)
- [ ] N/A: gtm-resilience-summary.md nao requer atualizacao

---

## Arquivos Impactados

| Arquivo | Mudanca |
|---------|---------|
| `backend/pipeline/stages/execute.py` | SEARCH_FETCH_TIMEOUT: 360s -> 180s |
| `backend/routes/search_state.py` | SEARCH_FETCH_TIMEOUT: 360s -> 180s |
| `backend/supabase_client.py` | Pool health logging adicionado (periodico a cada ~50 calls) |
