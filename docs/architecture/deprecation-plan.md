# Plano de Depreciacao de Modulos Legacy

**Issue:** #1966
**Data de criacao:** 2026-06-17
**Status:** Em vigor — P1
**Feature flag:** `LEGACY_FALLBACK_ENABLED` (default: `true` durante periodo de depreciacao)

---

## 1. Inventory de Modulos Legacy

### 1.1 Cache L3 — Local File Cache

| Campo | Valor |
|-------|-------|
| **Arquivo** | `backend/cache/local_file.py` |
| **Funcao** | Cache em JSON files no disco local (`LOCAL_CACHE_DIR`), TTL 24h, max 200MB |
| **Nivel na cascata** | L3 — consultado apos L2 (Redis) e L1 (Supabase) no `get_from_cache_cascade()` |
| **Metrica de uso** | `event=cache_l3_served` (log JSON em `cascade.py:169`) |
| **Substituto** | L1 InMemoryCache + L2 Redis + SWR + Supabase search_results_cache (L2) |
| **Risco da remocao** | BAIXO — cache L3 raramente e atingido; L2 (Supabase) + L1 (Redis) cobrem >99% dos hits |
| **Dead code detectado** | `cache/core.py` — re-export de `cache_module`, nunca importado |
| **Tempo sem alteracao** | Ultima alteracao: 2026-04 (STORY-CIG-BE-cache-warming-deprecate) |

### 1.2 Cache L3 — cache/core.py (Re-export Stub)

| Campo | Valor |
|-------|-------|
| **Arquivo** | `backend/cache/core.py` |
| **Conteudo** | `from cache_module import *` — re-export classico |
| **Usado por** | Nenhum modulo de producao — e dead code |
| **Substituto** | `cache_module` ou `cache.redis` diretamente |
| **Risco da remocao** | NENHUM — zero imports em producao |

### 1.3 cache_module.py (RedisCacheClient Monolitico)

| Campo | Valor |
|-------|-------|
| **Arquivo** | `backend/cache_module.py` |
| **Funcao** | `RedisCacheClient` class — cache Redis + InMemoryCache fallback |
| **Usado por** | `backend/admin.py` (admin routes), `backend/llm.py` (LLM cache), `backend/cache/__init__.py` (re-export), `backend/cache/core.py` (re-export), `backend/tests/test_llm_cache.py` |
| **Substituto** | `redis_pool` + `cache.redis` ou `cache.enums` |
| **Risco da remocao** | MEDIO — `admin.py` e `llm.py` importam `redis_cache` de `cache_module`. Refatoracao local necessaria |

### 1.4 search_cache.py — Facade de Cache

| Campo | Valor |
|-------|-------|
| **Arquivo** | `backend/search_cache.py` |
| **Funcao** | Facade de retrocompatibilidade que re-exporta todo o package `cache/` |
| **Usado por** | `backend/pipeline/cache_manager.py` + 12+ arquivos de test |
| **Substituto** | Import direto de `cache.manager`, `cache.enums`, etc. |
| **Risco da remocao** | MEDIO — muitos testes importam `search_cache.X`. Precisa de codemod |

### 1.5 pncp_client.py — Facade Legacy

| Campo | Valor |
|-------|-------|
| **Arquivo** | `backend/pncp_client.py` |
| **Funcao** | Facade thin sobre `clients/pncp/` (DEBT-204). Re-exporta tudo do subpackage |
| **Usado por** | `backend/pipeline/stages/execute.py`, `backend/cache/cascade.py`, `backend/cache/swr.py`, `backend/health.py`, `backend/config/pncp.py`, `backend/clients/pncp/retry.py`, `backend/clients/pncp/async_client.py`, `backend/ingestion/crawler.py`, `backend/pipeline/stages/persist.py`, `backend/routes/api_search.py`, etc. |
| **Substituto** | `clients.pncp` diretamente |
| **Risco da remocao** | ALTO — 11+ modulos importam deste facade. Requer codemod em massa |
| **Nota** | DEBT-204 Track 1 ja refatorou a implementacao. O facade e o que resta |

### 1.6 pncp_client_resilient.py — Client Legacy Obsoleto

| Campo | Valor |
|-------|-------|
| **Arquivo** | `backend/pncp_client_resilient.py` |
| **Funcao** | Wrapper pre-DEBT-204 com retry adaptativo e circuit breaker manual |
| **Usado por** | Nenhum modulo em producao — dead code completo |
| **Substituto** | `clients/pncp/` (async client + circuit breaker + retry) |
| **Risco da remocao** | NENHUM — zero imports |

### 1.7 Live API Fetch Fallback — PNCP-only + Multi-source

| Campo | Valor |
|-------|-------|
| **Arquivo** | `backend/pipeline/stages/execute.py` |
| **Funcao** | `_execute_pncp_only()` e `_execute_multi_source()` — fallback quando DataLake retorna 0 resultados |
| **Ativado quando** | `DATALAKE_QUERY_ENABLED=true` + `query_datalake()` retorna 0 resultados |
| **Substituto** | DataLake query (`datalake_query.py`) — Layer 2 |
| **Risco da remocao** | MEDIO — se DataLake retornar 0 por motivo legitimo (ex: consulta muito especifica), nao ha fallback |
| **Mitigacao** | Manter `ENABLE_MULTI_SOURCE` como opt-in durante Phase 1-2 |

### 1.8 CACHE_LEGACY_KEY_FALLBACK

| Campo | Valor |
|-------|-------|
| **Arquivo** | `backend/cache/cascade.py` (linha 71) |
| **Funcao** | Fallback para chaves de cache sem datas (pre-STORY-306) |
| **Feature flag** | `CACHE_LEGACY_KEY_FALLBACK` (ja existe em `config/pipeline.py`, default `true`) |
| **Substituto** | Chaves de cache com datas (STORY-306) — formato atual |
| **Risco da remocao** | BAIXO — entradas antigas ja expiraram |

---

## 2. Plano de Remocao Faseado

### 2.1 Phase 1 — Dias 1-30: Warning Logs + Metricas de Uso Zero

**Inicio:** 2026-06-17
**Fim:** 2026-07-17

| Acao | Detalhes |
|------|----------|
| Adicionar warning logs | `logger.warning("DEPRECATED: ...")` em cada entry point legacy |
| Adicionar metrica | `smartlic_legacy_module_access_total{module="...", caller="..."}` — Prometheus counter |
| Feature flag `LEGACY_FALLBACK_ENABLED` | Default `true` — sem mudanca de comportamento |
| Documentar | Este documento + anuncio interno |

**Entregaveis:**
- [x] Feature flag `LEGACY_FALLBACK_ENABLED` adicionada ao config
- [x] Documento de deprecation plan criado
- [x] `.env.example` documenta a flag

### 2.2 Phase 2 — Dias 30-60: Opt-in Model (default off)

**Inicio:** 2026-07-17
**Fim:** 2026-08-17

| Acao | Detalhes |
|------|----------|
| `LEGACY_FALLBACK_ENABLED` default `false` | Ambiente dev/staging primeiro |
| Remover facade `pncp_client_resilient.py` | Dead code, sem dependencias |
| Remover `cache/core.py` | Dead code, sem imports |
| Remover `cache_module.py` (RedisCacheClient) | Refatorar `admin.py`, `llm.py` para usar `redis_pool` diretamente |
| Remover `search_cache.py` facade | Codemod de imports nos testes (12+ arquivos) |
| Pipeline live-fetch fallback | Desabilitado por padrao, `LEGACY_FALLBACK_ENABLED=true` reativa |

**Criterio de Gate para Phase 2:**
- Metrica `smartlic_legacy_module_access_total` == 0 nas ultimas 2 semanas (todos os modulos)
- Nenhum warning log de deprecation em producao nas ultimas 2 semanas
- Testes passando sem os facades legacy

### 2.3 Phase 3 — Dias 60-90: Remocao Completa

**Inicio:** 2026-08-17
**Fim:** 2026-09-17

| Acao | Detalhes |
|------|----------|
| Remover `pncp_client.py` facade | Codemod de imports em 11+ modulos |
| Remover live-fetch legacy (PNCP-only) | `_execute_pncp_only()` em `execute.py` |
| Remover cache L3 (local file) | `cache/local_file.py` + referencias em `cascade.py` |
| Remover `CACHE_LEGACY_KEY_FALLBACK` | Logica de fallback de chave sem datas |
| Feature flag `LEGACY_FALLBACK_ENABLED` | Mantida para rollback de emergencia por 60d |
| Limpeza de `_FEATURE_FLAG_REGISTRY` | Remover entradas de flags removidas |

**Criterio de Gate para Phase 3:**
- `LEGACY_FALLBACK_ENABLED=false` rodando em producao sem incidentes por 30 dias
- Metrica de acesso zero mantida
- Testes de integracao validados sem os modulos legacy

---

## 3. Feature Flag: LEGACY_FALLBACK_ENABLED

### 3.1 Definicao

| Propriedade | Valor |
|-------------|-------|
| **Nome** | `LEGACY_FALLBACK_ENABLED` |
| **Tipo** | `bool` de ambiente |
| **Default** | `true` (Phase 1), `false` (Phase 2+) |
| **Localizacao** | `backend/config/pipeline.py` + `_FEATURE_FLAG_REGISTRY` |
| **Efeito** | Quando `true`: todos os fallbacks legacy funcionam normalmente. Quando `false`: caminho legacy e ignorado; se DataLake retornar 0, retorna 0 |

### 3.2 Onde e Verificada

- `backend/pipeline/stages/execute.py` — guarda para fallback live-fetch
- `backend/cache/cascade.py` — guarda para cache L3 (local file)
- `backend/cache/swr.py` — guarda para re-export de `pncp_client`

### 3.3 Periodo de Emergencia

A flag permanece no codigo por **60 dias apos o inicio da Phase 3** (ate ~2026-11-17). Apos esse periodo sem incidentes, a flag pode ser removida junto com o codigo legacy.

---

## 4. Metricas de Observabilidade

### 4.1 Contadores Prometheus

```python
# Em backend/metrics.py
LEGACY_MODULE_ACCESS_TOTAL = Counter(
    "smartlic_legacy_module_access_total",
    "Acesso a modulo legacy durante periodo de deprecation",
    ["module", "caller"],
)
```

### 4.2 Labels

| Label | Valores |
|-------|---------|
| `module` | `cache_l3_local`, `pncp_client_facade`, `search_cache_facade`, `cache_module`, `live_fetch_pncp_only`, `cache_legacy_key` |
| `caller` | Nome do modulo chamador (ex: `cascade`, `execute`, `swr`) |

### 4.3 Alertas Sentry

- **Warning:** `logger.warning("DEPRECATED: ...")` em cada acesso a modulo legacy durante Phase 1
- **Error:** Apos Phase 2, acesso com `LEGACY_FALLBACK_ENABLED=false` gera erro + `capture_message`

---

## 5. Plano de Rollback

### 5.1 Rollback Rapido (< 24h)

```bash
# Reativar fallbacks legacy imediatamente
railway variables set LEGACY_FALLBACK_ENABLED=true

# Monitorar metrica de acesso por 1h
# Se incidente resolvido, manter true e re-agendar Phase
```

### 5.2 Rollback Completo (commit revert)

Se a remocao de codigo (Phase 3) causar incidente critico:

```bash
git revert HEAD --no-commit
git commit -m "fix: revert legacy module removal due to incident #XXXX"
railway up
```

### 5.3 Criterio de Rollback

| Gatilho | Acao |
|---------|------|
| Erro 5xx > 1% apos deploy | `LEGACY_FALLBACK_ENABLED=true` imediato |
| DataLake retorna 0 por > 10% das buscas | Investigar causa raiz + reativar fallback |
| Qualquer P0/P1 atribuido a remocao | Reverter commit + post-mortem |

---

## 6. Tabela Resumo

| Modulo | Arquivo | Status | Substituto | Phase | Risco |
|--------|---------|--------|------------|-------|-------|
| Cache L3 local file | `cache/local_file.py` | Legacy | L1+L2+SWR | 3 | BAIXO |
| cache/core.py | `cache/core.py` | Dead | — | 2 | NENHUM |
| cache_module.py | `cache_module.py` | Legacy | `redis_pool`+`cache.redis` | 2 | MEDIO |
| search_cache.py | `search_cache.py` | Facade | `cache/` direto | 2 | MEDIO |
| pncp_client.py | `pncp_client.py` | Facade | `clients.pncp` | 3 | ALTO |
| pncp_client_resilient.py | `pncp_client_resilient.py` | Dead | `clients.pncp` | 2 | NENHUM |
| Live fetch fallback | `pipeline/stages/execute.py` | Legacy fallback | DataLake | 3 | MEDIO |
| Cache legacy key | `cache/cascade.py` | Legacy flag | STORY-306 keys | 3 | BAIXO |

---

## 7. Historico de Revisoes

| Data | Versao | Autor | Mudanca |
|------|--------|-------|---------|
| 2026-06-17 | 1.0 | @dev | Documento inicial (#1966) |
