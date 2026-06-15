# Estrategia de Fallback — Busca Multi-Fonte

## Visao Geral

O SmartLic implementa uma **arquitetura de busca em 3 camadas** com fallback progressivo para garantir que o usuario sempre receba resultados, mesmo quando fontes externas estao indisiveis. A busca passa por DataLake local, cache multi-nivel, e ate 3 fontes governamentais externas, cada uma com circuit breaker e timeout proprios.

---

## Ordem de Fontes

A pipeline de execucao segue a ordem de prioridade abaixo. Cada etapa so e executada se a anterior retornar **0 resultados** ou falhar:

```
1. Cache L1 (InMemory) + Cache L2 (Supabase)
   └─ hit → serve imediatamente
2. DataLake (pncp_raw_bids — PostgreSQL FTS local)
   └─ retorna > 0 → pula fontes externas
   └─ retorna 0 → cai para fontes live
3. Multi-Source Consolidation
   ├─ PNCP (prioridade 1)
   ├─ PCP v2 (prioridade 2)
   └─ ComprasGov (prioridade 3, atualmente desabilitado)
4. Cache Stale/Expired (fallback final)
   └─ se todas as fontes falham
```

### Fluxo Detalhado (`stage_execute`)

```
stage_execute()
  │
  ├─ DATALAKE_QUERY_ENABLED=true?
  │   ├─ Sim → query_datalake()
  │   │   ├─ retornou resultados → usa, pula fontes live
  │   │   └─ retornou 0 ou erro → fall through para cache
  │   └─ Nao → pula
  │
  ├─ force_fresh=false?
  │   ├─ Sim → busca cache L1 (InMemory) + L2 (Supabase)
  │   │   ├─ cache hit (fresh) → serve + background revalidation se stale
  │   │   ├─ cache hit (stale) → serve + background refresh
  │   │   └─ cache miss → continua
  │   └─ Nao → pula (force_fresh=true)
  │
  ├─ ENABLE_MULTI_SOURCE=true?
  │   ├─ Sim → ConsolidationService (PNCP + PCP + ComprasGov)
  │   └─ Nao → PNCP-only fetch
  │
  └─ Erro/Timeout em qualquer etapa?
      ├─ Cache stale disponivel → serve com ctx.is_partial=true
      └─ Sem cache → empty_failure com guidance
```

---

## DataLake (Camada Preferencial)

### Modo de Operacao

Quando `DATALAKE_QUERY_ENABLED=true` (default), `stage_execute` chama `query_datalake()` em vez de `PNCPClient`. Os registros retornados estao no **mesmo formato** de `PNCPClient._normalize_item()`, entao todas as etapas downstream (filter, LLM, Excel) funcionam sem alteracao.

### O que acontece quando o DataLake falha

| Cenario | Comportamento |
|---------|--------------|
| DataLake retorna 0 resultados | Fall through para cache + fontes live |
| Supabase indisponivel | Retorna `[]` (fail-open), fall through para cache + fontes live |
| Statement timeout | Retorna `[]` (fail-open) |
| Semaphore pool cheio | Retorna `[]` (shed request, 2s timeout) |

### Concurrency Limiter

Um semaforo `asyncio.Semaphore(5) + timeout 2s` evita que crawlers/bots saturem o pool de conexao Supabase. Cache hits bypassam o semaforo.

### Trigram Fallback (STORY-437)

Quando FTS retorna 0 resultados, ativa automaticamente `search_datalake_trigram_fallback` (similaridade trigram GIN index). Limite de 2 retries com backoff exponencial (1s, 2s) em caso de statement timeout.

---

## Cache (Camada Intermediaria)

### Estrutura de Cache

```
L1: InMemoryCache (4h TTL, LRU 10k entries)
L2: Supabase search_results_cache (24h TTL)
SWR: Stale-while-revalidate (6-24h: serve stale + background refresh)
```

### Cache Cascade (A-03)

Quando todas as fontes falham, o sistema tenta 3 niveis em cascata:

1. **L2 (Supabase)**: Cache recente (0-24h)
2. **L1 (InMemory)**: Cache em memoria
3. **L3 (Expired)**: Cache expirado (>24h) — apenas se `allow_expired=true`

### Qualidade do Cache (CRIT-056)

A qualidade do cache e calculada baseada no estado das fontes:

| Qualidade | Cenario |
|-----------|---------|
| 1.0 | PNCP ok, sem fontes degradadas |
| 0.7 | PNCP ok, fontes secundarias degradadas |
| 0.3 | Apenas fontes secundarias OK |
| 0.0 | Todas as fontes falharam |

Resultados com qualidade < 0.5 e zero registros **nao sao cacheados** para evitar poluir o cache com resultados vazios.

### Background Revalidation (B-01)

Cache stale (6-24h) dispara revalidacao em background:
- Max 3 revalidacoes simultaneas
- Timeout de 180s
- Atualiza cache ao completar

---

## Fontes Live (Multi-Source Consolidation)

### Ativacao

Quando DataLake retorna 0 resultados **ou** `DATALAKE_QUERY_ENABLED=false`, a pipeline usa `ConsolidationService` para buscar em multiplas fontes simultaneamente.

### Fontes e Prioridades

| Fonte | Prioridade | Status | Circuit Breaker |
|-------|-----------|--------|-----------------|
| **PNCP** (`pncp.gov.br`) | 1 | Ativa | 15 falhas → 60s cooldown |
| **PCP v2** (`portaldecompraspublicas.com.br`) | 2 | Ativa | 15 falhas → 60s cooldown |
| **ComprasGov v3** (`dadosabertos.compras.gov.br`) | 3 | **DESABILITADA** (offline desde 2026-03-03) | 15 falhas → 60s cooldown |

### O que acontece quando cada fonte falha

| Evento | Comportamento |
|--------|--------------|
| **PNCP timeout** (70s per-source) | Marca como `error`, tenta PCP + ComprasGov |
| **PNCP circuit breaker OPEN** | Skipa PNCP, loga `skipped_sources`, usa demais fontes |
| **PNCP health canary timeout** | Marca PNCP como `degraded`, usa cache stale |
| **PCP timeout** (30s per-source) | Marca como `error`, continua com PNCP |
| **PCP circuit breaker OPEN** | Skipa PCP |
| **PCP health registry DOWN** | Skipa PCP |
| **ComprasGov timeout** | Marca como `error` (fonte ja desabilitada) |
| **Todas as fontes falham** | `AllSourcesFailedError` → tenta cache stale/expired |
| **Todas as fontes com CB OPEN** | ConsolidationService recebe 0 adapters → `AllSourcesFailedError` |

### Degradacao vs Erro Total

A pipeline distingue entre **resultados parciais** (pelo menos uma fonte respondeu) e **falha total** (nenhuma fonte respondeu):

- **`is_partial = true`**: Pelo menos uma fonte retornou dados. `response_state = "degraded"`
- **`AllSourcesFailedError`**: Nenhuma fonte retornou. Tenta cache stale.
- **Cache stale encontrado**: `response_state = "cached"` com `is_partial = true`
- **Cache expirado encontrado**: `response_state = "degraded_expired"` com aviso de dados desatualizados
- **Sem cache**: `response_state = "empty_failure"` com mensagem de indisponibilidade

---

## Time Budget Waterfall

### Hierarquia de Timeouts

A pipeline opera dentro de uma hierarquia rigorosa de timeouts para garantir que o Railway proxy (~120s) nunca mate a requisicao antes de uma resposta ser gerada:

```
Railway proxy     [========================== 120s ==========================]
Route middleware  [======================= 60s ========================]
Pipeline budget   [==================== 100s ====================]
  Consolidation   [================== 90s ===================]
    PerSource     [============= 70s =============]
      PerUF       [===== 25s =====]
        Modality  [=== 20s ===]
          httpx r/w [10c+15r]
```

### Invariante (testada em `test_timeout_invariants.py`)

```
pipeline(100s) > consolidation(90s) > per_source(70s) > per_uf(25s) > modality(20s) + httpx(15s)
```

### O que acontece em cada timeout

| Nivel | Timeout | Consequencia |
|-------|---------|-------------|
| **Pipeline** (100s) | `PIPELINE_TIMEOUT` | LLM classification pulada (fallback pending_review) |
| **Consolidation** (90s) | `CONSOLIDATION_TIMEOUT` | Early return com resultados parciais |
| **PerSource** (70s) | `PNCP_TIMEOUT_PER_SOURCE` | Fonte marcada como `error`, tenta proxima fonte |
| **PerUF** (25s) | `PNCP_TIMEOUT_PER_UF` | UF marcada como `failed`, continua com outras UFs |
| **PerModality** (20s) | `PNCP_TIMEOUT_PER_MODALITY` | Modalidade pulada, continua com outras |
| **Route middleware** (60s) | `ROUTE_TIMEOUT_S` | Retorna 503 + Retry-After:5 |

### Observabilidade

Cada timeout e registrado via `_run_with_budget` (em `backend/pipeline/budget.py`), que incrementa o Prometheus counter `smartlic_pipeline_budget_exceeded_total{phase, source}` e gera log estruturado.

---

## Circuit Breaker Behavior

### Implementacao

```
backend/clients/pncp/circuit_breaker.py
```

Cada fonte tem seu proprio circuit breaker nomeado (PNCP, PCP, ComprasGov), com estado compartilhado via Redis (Lua script atomico) ou local (in-memory).

### Estados

```
CLOSED (saudavel)
  │ ConsecutiveFailures >= threshold (15)
  ▼
OPEN (degradado)
  │ Cooldown (60s)
  ▼
HALF-OPEN (try_recover)
  ├─ Sucesso → CLOSED
  └─ Falha → OPEN (reset contagem)
```

### Tabela de Configuracao

| Fonte | Threshold | Cooldown | Redis Key |
|-------|-----------|----------|-----------|
| PNCP | 15 falhas | 60s | `circuit_breaker:pncp:*` |
| PCP | 15 falhas | 60s | `circuit_breaker:pcp:*` |
| ComprasGov | 15 falhas | 60s | `circuit_breaker:comprasgov:*` |

### TTL de Seguranca (B-06 AC12)

Redis keys expiram apos `CB_REDIS_TTL` (default 300s) para evitar estado "fantasma" apos deploy.

### Inicializacao

`RedisCircuitBreaker.initialize()` restaura estado do Redis ao startup para que workers novos hermem o estado degradado de workers existentes.

---

## Partial Results (SSE)

### Mecanismo

A pipeline emite eventos SSE progressivos para que o frontend exiba resultados parciais em tempo real:

1. `fetching` (10%) — Iniciando analise em N estados
2. `uf_complete` — Cada UF concluida
3. `source_complete` / `source_error` — Cada fonte externa
4. `progressive_results` — Resultados parciais incrementais
5. `partial_data` — Dados brutos antes da filtragem
6. `degraded` — Fontes com problema (mostra banner no frontend)

### Estados de Resposta (response_state)

| Estado | Significado | Frontend |
|--------|-------------|----------|
| `cached` | Resultados de cache (fresh ou stale) | Resultados normais |
| `degraded` | Resultados parciais com degradacao | Banner "dados parciais" |
| `degraded_expired` | Cache expirado servido como fallback | Banner "dados podem estar desatualizados" |
| `empty_failure` | Nenhum resultado disponivel | Mensagem "fontes indisponiveis, tente novamente" |

### CacheBanner / DegradationBanner

O frontend possui dois componentes para exibir estados de degradacao:
- `CacheBanner` — Exibe quando resultados sao de cache
- `DegradationBanner` — Exibe quando fontes estao com problemas
- `PartialResultsPrompt` — Oferece opcao de continuar com resultados parciais
- `SourcesUnavailable` — Exibe quando todas as fontes falharam

---

## Arquivos Relevantes

| Arquivo | Proposito |
|---------|-----------|
| `backend/search_pipeline.py` | Orquestrador 7-stage da pipeline |
| `backend/pipeline/stages/execute.py` | Stage 3: execucao multi-fontes |
| `backend/pipeline/budget.py` | `_run_with_budget` — timeout com observabilidade |
| `backend/datalake_query.py` | Query no DataLake PostgreSQL |
| `backend/clients/pncp/circuit_breaker.py` | Circuit breaker por fonte |
| `backend/consolidation/` | Consolidacao e dedup multi-fontes |
| `backend/cache/cascade.py` | Cache cascade L1-L2-L3 |
| `backend/cache/swr.py` | Stale-while-revalidate |
| `backend/config/pncp.py` | Timeouts, circuit breaker, batching configs |
| `backend/tests/test_timeout_invariants.py` | Teste da hierarquia de budgets |

---

## Env Vars (Resumo)

### Timeout Chain

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `PIPELINE_TIMEOUT` | 100s | Pipeline total |
| `CONSOLIDATION_TIMEOUT` | 90s | Consolidacao multi-fontes |
| `PNCP_TIMEOUT_PER_SOURCE` | 70s | Por fonte externa |
| `PNCP_TIMEOUT_PER_UF` | 25s | Por UF |
| `PNCP_TIMEOUT_PER_UF_DEGRADED` | 12s | Por UF em modo degradado |
| `PNCP_TIMEOUT_PER_MODALITY` | 20s | Por modalidade |
| `EARLY_RETURN_TIME_S` | 80s | Early return na consolidacao |
| `EARLY_RETURN_THRESHOLD_PCT` | 0.66 | Threshold % para early return |
| `PIPELINE_SKIP_LLM_AFTER_S` | 90s | Skip LLM apos N segundos |
| `PIPELINE_SKIP_VIABILITY_AFTER_S` | 100s | Skip viabilidade apos N segundos |
| `ROUTE_TIMEOUT_S` | 60s | Route-level timeout middleware |

### Circuit Breaker

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `PNCP_CIRCUIT_BREAKER_THRESHOLD` | 15 | Falhas consecutivas para abrir |
| `PNCP_CIRCUIT_BREAKER_COOLDOWN` | 60s | Tempo em degraded |
| `PCP_CIRCUIT_BREAKER_THRESHOLD` | 15 | Falhas consecutivas para abrir |
| `PCP_CIRCUIT_BREAKER_COOLDOWN` | 60s | Tempo em degraded |
| `COMPRASGOV_CIRCUIT_BREAKER_THRESHOLD` | 15 | Falhas consecutivas para abrir |
| `COMPRASGOV_CIRCUIT_BREAKER_COOLDOWN` | 60s | Tempo em degraded |
| `USE_REDIS_CIRCUIT_BREAKER` | true | Usar Redis para estado compartilhado |
| `CB_REDIS_TTL` | 300s | TTL de seguranca para keys Redis |

### DataLake

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `DATALAKE_QUERY_ENABLED` | true | Usar DataLake como fonte primaria |
| `DATALAKE_ENABLED` | true | Ingestion ligado |
| `EMBEDDING_ENABLED` | false | Busca semantica via pgvector |
