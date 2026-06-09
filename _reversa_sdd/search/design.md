# Design — Módulo `search`

> Gerado pelo Writer (Reversa) em 2026-06-08
> Fonte: `backend/search/`, `backend/routes/search/`, `backend/models/search_state.py`

---

## Visão Geral

Motor de busca assíncrono com pipeline de 7 estágios, SSE para progresso em tempo real, e cache L1/L2 com SWR (stale-while-revalidate). Suporta busca multi-fonte (datalake primário + live APIs como fallback).

## Arquitetura Interna

```
POST /buscar (params)
  │
  ├─ 1. Validação (quota, permissões, parâmetros)
  ├─ 2. Cria SearchSession (estado: CREATED)
  ├─ 3. Retorna 202 + search_id
  └─ Pipeline assíncrono (ARQ job):
       │
       ├─ VALIDATING (params + quota check)
       ├─ FETCHING (datalake RPC ou live APIs)
       ├─ FILTERING (UF → valor → keyword → LLM)
       ├─ ENRICHING (órgão, contratos, afinidade)
       ├─ GENERATING (resumo LLM + Excel)
       ├─ PERSISTING (cache L1 + L2 + DB)
       └─ COMPLETED

GET /buscar/{id}/state (polling)
GET /buscar/{id}/events (SSE)
```

## Máquina de Estados

```
CREATED ──► VALIDATING ──► FETCHING ──► FILTERING ──► ENRICHING ──► GENERATING ──► PERSISTING ──► COMPLETED
   │            │             │            │             │              │              │
   └────────────┴─────────────┴────────────┴─────────────┴──────────────┴──────────────┴──► FAILED
                │
                └──► RATE_LIMITED

FETCHING ──► TIMED_OUT
```

### Regras de Transição
- Só `CREATED → VALIDATING` ou `CREATED → FAILED` são válidas a partir de CREATED
- Qualquer estado pode transitar para FAILED
- Estados terminais (COMPLETED, FAILED, RATE_LIMITED, TIMED_OUT): sem saída
- Transição inválida → log CRITICAL + rejeição

## Cache Strategy (SWR)

```
Cache L1 (Redis/InMemory, TTL priorizado + jitter)
  │
  ├─ Hit fresco (age < CACHE_FRESH_HOURS=4h) → retorna imediatamente
  ├─ Hit stale (age 4-24h) → retorna stale + revalida em background (SWR)
  └─ Miss → executa pipeline → popula L1 + L2

Cache L2 (Supabase, 24h TTL via expires_at)
  │
  ├─ Populado após pipeline concluir
  └─ Chave = hash normalizado dos parâmetros de busca
```

### TTL Mechanism (GAP-003, confirmado #1580)

**L1 Redis:** TTL nativo via `SET key value EX <ttl>`:
- TTL base por prioridade: HOT=7200s (2h), WARM=21600s (6h), COLD=3600s (1h)
- Jitter aleatório +0-10% via `random.randint(0, int(ttl * 0.1))` — anti cache stampede
- Fallback InMemoryCache usa o mesmo TTL com jitter

**L2 Supabase:** Coluna `expires_at` (TIMESTAMPTZ) em `search_results_cache`:
- Computada como `created_at + CACHE_STALE_HOURS` (24h) no momento da escrita
- Índice `idx_search_results_cache_expires_at` para DELETE eficiente
- pg_cron safety net: `cleanup-expired-cache` diário às 3h UTC
  (`DELETE FROM search_results_cache WHERE expires_at < now()`)

**Read-time expiry check** (`_process_cache_hit` em `cache/_ops.py`):
- `CACHE_FRESH_HOURS = 4` → entradas com <4h são FRESH
- `CACHE_STALE_HOURS = 24` → entradas 4-24h são STALE (servidas + SWR)
- Entradas >24h → EXPIRED (não servidas a menos que `allow_expired=True`)

## Dependências

| Dependência | Uso |
|-------------|-----|
| `pipeline/` | Orquestração dos 7 estágios |
| `filter/` | Estágio FILTERING |
| `llm_arbiter/` | Classificação setorial |
| `consolidation/` | Dedup resultados |
| `cache/` | L1 + L2 cache |
| `quota/` | Verificação de quota pré-busca |
| `datalake_query.py` | RPC de busca no datalake |
| `routes/search/sse.py` | SSE broker (Redis pub/sub) |
| `models/search_state.py` | State machine |

## 🔴 Lacunas

| # | Lacuna |
|---|--------|
| DES-SRC-002 | Comportamento exato do SSE quando Redis pub/sub falha — fallback para polling apenas? |
