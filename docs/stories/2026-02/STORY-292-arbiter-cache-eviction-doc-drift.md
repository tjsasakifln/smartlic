# STORY-292: LLM Arbiter Cache Eviction & Documentation Drift Fix

**Priority:** P2
**Effort:** S (0.5 day)
**Squad:** @dev
**Fundamentacao:** GTM Readiness Audit Track 4 (Pipeline) — T4-LLM-01, T4-PNCP-02, T4-CACHE-01
**Status:** TODO
**Sprint:** GTM Sprint 3

---

## Contexto

O audit identificou 3 items de debt tecnico menores no pipeline:

1. `_arbiter_cache` dict em `llm_arbiter.py` cresce sem limite (sem LRU eviction)
2. CLAUDE.md documenta health canary com `tamanhoPagina=10` mas codigo usa 50
3. CLAUDE.md descreve L1 cache como "InMemoryCache" mas L1 real e Redis

---

## Acceptance Criteria

### AC1: Add LRU eviction to arbiter cache
- [x] Substituir `_arbiter_cache = {}` por `OrderedDict` com max 5000 entries
- [x] Ou usar `functools.lru_cache` se aplicavel
- [x] Quando cache atinge max, evictar entries mais antigas (LRU)
- [x] Teste: cache nao cresce alem do limite

### AC2: Fix CLAUDE.md documentation drift
- [ ] Corrigir secao "PNCP API Critical Notes": health canary usa tamanhoPagina=50 (nao 10)
- [ ] Corrigir secao "Cache Strategy": L1 e Redis (4h TTL), InMemoryCache e o fallback do Redis com LRU
- [ ] Verificar timeout chain values contra `config.py` atual e atualizar se necessario
- [ ] Corrigir contagem de "15 failures threshold" se valor mudou

### AC3: Fix Google Analytics test with old price
- [ ] `frontend/__tests__/components/GoogleAnalytics.test.tsx` line 235: alterar 1999.99 para 397.00
- [ ] Verificar se ha outros testes com preco antigo

---

## Arquivos Impactados

| Arquivo | Mudanca |
|---------|---------|
| `backend/llm_arbiter/classification.py` | LRU cache eviction + eviction logging |
| `docs/stories/2026-02/STORY-292-arbiter-cache-eviction-doc-drift.md` | Story progress update |
