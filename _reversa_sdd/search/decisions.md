# Decisões Arquiteturais — Módulo `search`

> Gerado pelo Writer (Reversa) em 2026-06-08 | Fonte: `backend/search/`, ADRs 002/003/004/010

---

## DEC-SRC-001: Arquitetura de 3 camadas (datalake-first) 🟢
**Decisão:** Busca em 3 camadas: Ingestion ETL (L1) → Search Pipeline PostgreSQL (L2) → Results Cache L1+L2 SWR (L3). Fallback para live APIs apenas quando datalake retorna 0 resultados.
**Evidência:** `datalake_query.py`, `cache/`, ADR-002, ADR-010
**Trade-off:** Complexidade de 3 camadas vs latência <100ms p95 (era 30-120s).

## DEC-SRC-002: Máquina de estados explícita com 11 estados 🟢
**Decisão:** Substituir status string livre por máquina de estados determinística com 11 estados e transições validadas.
**Evidência:** `models/search_state.py`, `search_state_transitions` (audit log append-only)
**Trade-off:** 11 estados = complexidade vs debug determinístico e progresso real.

## DEC-SRC-003: Time budget waterfall com invariante testado 🟢
**Decisão:** Waterfall: pipeline(100) > consolidation(90) > per_source(70) > per_uf(25). Cada camada usa `_run_with_budget()`.
**Evidência:** `pipeline/budget.py`, `tests/test_timeout_invariants.py`, CI gate ativo.
**Trade-off:** 5 valores de timeout vs fontes rápidas não bloqueadas por fontes lentas.

## DEC-SRC-004: Dual-connection SSE + polling 🟢
**Decisão:** SSE (EventSource primário) + JSON polling (fallback). SSE via Redis pub/sub desacopla worker de busca do worker HTTP.
**Evidência:** `routes/search/sse.py` (Redis pub/sub channel `search:{search_id}`)
**Trade-off:** Duas conexões por busca vs resiliência máxima.

## DEC-SRC-005: Cache SWR sem aquecimento proativo 🟢
**Decisão:** Cache L1 InMemory (4h) + L2 Supabase (24h) com SWR. Sem aquecimento — populado sob demanda.
**Evidência:** `cache/`, ADR-010
**Trade-off:** Primeira busca após expiração = 100ms vs 0ms (imperceptível).

## DEC-SRC-006: Ordenação por confiança como padrão 🟢
**Decisão:** Resultados ordenados por `combined_score`. Anteriormente `data_publicacao` (STORY-1430).
**Evidência:** `search_pipeline.py`

---

## DEC-SRC-GAP-01: Cache stale cleanup — TTL nativo + pg_cron safety net 🟢
**Resolve:** GAP-003 (issue #1580), DEC-SRC-GAP-01 formal ADR, GAP-015 (TTL confirmation)

**Decisão:** TTL nativo (Redis EXPIRE) como mecanismo primário de expurgo, com pg_cron como safety net para evitar acúmulo de entradas órfãs no Supabase. Sem ARQ job adicional.

**Mecanismo:**

1. **L1 Redis:** `SET key value EX <ttl>` em toda escrita no cache. TTL base definido por prioridade (`REDIS_TTL_BY_PRIORITY`: HOT=7200s, WARM=21600s, COLD=3600s). Cada TTL recebe jitter aleatório +0-10% (`random.randint(0, int(ttl * 0.1))`) para evitar cache stampede (thundering herd) quando múltiplos workers expiram a mesma chave simultaneamente.

2. **L2 Supabase:** Coluna `expires_at` (TIMESTAMPTZ) em `search_results_cache`, computada como `created_at + CACHE_STALE_HOURS` (24h) no momento da escrita. Índice `idx_search_results_cache_expires_at` para queries eficientes.

3. **Safety net:** pg_cron job `cleanup-expired-cache` executa `DELETE FROM search_results_cache WHERE expires_at < now()` diariamente às 3h UTC (00h BRT), horário de baixo tráfego.

**Alternativas consideradas:**
| Alternativa | Rejeitada por |
|-------------|---------------|
| pg_cron-only (sem TTL Redis) | Redis não teria expurgo automático — entidades stale consumiriam memória até o próximo cron |
| ARQ job dedicado | Complexidade desnecessária — Redis `EXPIRE` é zero-ops e padrão de mercado. ARQ worker pode estar offline; pg_cron roda no PostgreSQL independente |
| TTL-only (sem pg_cron) | Supabase acumularia entidades stale indefinidamente — sem safety net para falhas de aplicação (ex: worker crash antes de popular cache fresco) |
| TTL fixo sem jitter | Risco de cache stampede em picos de tráfego (múltiplos usuários fazendo mesma busca simultaneamente) |

**Evidência:** `backend/cache/redis.py` (jitter), `backend/cache/supabase.py` (expires_at write), `backend/models/cache.py` (`SearchResultsCacheRow.expires_at`), `supabase/migrations/20260608120000_add_cache_expires_at.sql` (coluna + índice), `supabase/migrations/20260608120001_schedule_expired_cache_cleanup.sql` (pg_cron)

**Trade-off:** Complexidade de duas camadas de expurgo vs zero-ops com Redis EXPIRE (padrão de mercado, OneUptime 2026-03). pg_cron adiciona latência de até 24h para remoção de entradas stale, mas isso é aceitável dado que o safety net é para prevenção de bloat, não para consistência de cache.

---

## 🔴 Lacunas

| # | Lacuna |
|---|--------|
| DEC-SRC-GAP-02 | Fallback SSE quando Redis pub/sub falha — polling silencioso? Retry? |
| DEC-SRC-GAP-03 | Limite de concorrência de buscas por usuário — atualmente ilimitado? |
