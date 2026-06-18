# Diagnóstico de Disk IO — SmartLic

> **Issue:** [#2039](https://github.com/tjsasakifln/SmartLic/issues/2039) — Supabase Disk IO Budget depletion
> **Uso:** Execute cada seção no [SQL Editor do Supabase](https://supabase.com/dashboard/project/_/sql/new) separadamente.

## 1. Cache Hit Rate (eficiência do buffer cache)

```sql
SELECT
  'cache_hit_ratio' AS metric,
  ROUND(
    (100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0)),
    2
  ) AS pct_value,
  CASE
    WHEN (100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0)) >= 95 THEN '🟢 Saudável'
    WHEN (100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0)) >= 90 THEN '🟡 Atenção'
    ELSE '🔴 Crítico'
  END AS status
FROM pg_statio_user_tables;
```

**Interpretação:**
- ≥ 95%: Saudável — maioria das reads vem da RAM
- 90-95%: Atenção — buffer cache subdimensionado
- < 90%: CRÍTICO — queries indo direto ao disco

## 2. Top 20 tabelas por Sequential Scan

Tabelas com `seq_scan` alto e `idx_scan` baixo = queries fazendo table scan. Cada seq_scan lê o disco inteiro.

```sql
SELECT
  relname AS table_name,
  seq_scan,
  idx_scan,
  n_live_tup AS estimated_rows,
  CASE
    WHEN idx_scan = 0 AND seq_scan > 0 THEN '🔴 Sem índice usado'
    WHEN seq_scan > idx_scan * 2 THEN '🟡 Seq scan excessivo'
    WHEN seq_scan > 1000 THEN '🟡 Muitos seq scans'
    ELSE '🟢 OK'
  END AS status,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_scan DESC
LIMIT 20;
```

## 3. Top 20 tabelas por dead tuples (precisam de VACUUM)

Dead tuples = espaço em disco ocupado por rows deletadas/atualizadas que ainda não foram limpas pelo autovacuum. Causam table bloat e forçam mais IO por query.

```sql
SELECT
  relname AS table_name,
  n_live_tup AS live_rows,
  n_dead_tup AS dead_rows,
  ROUND(
    (100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0)), 2
  ) AS dead_pct,
  CASE
    WHEN (100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0)) > 20 THEN '🔴 Crítico — VACUUM urgente'
    WHEN (100.0 * n_dead_tup / NULLIF(n_live_tup + n_dead_tup, 0)) > 10 THEN '🟡 Atenção — VACUUM recomendado'
    ELSE '🟢 OK'
  END AS status,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
  last_vacuum,
  last_autovacuum
FROM pg_stat_user_tables
WHERE n_dead_tup > 0
ORDER BY n_dead_tup DESC
LIMIT 20;
```

## 4. Índices não utilizados (desperdiçam write IO)

Índices com `idx_scan = 0` consomem IO em cada INSERT/UPDATE/DELETE sem benefício de leitura.

```sql
SELECT
  indexrelname AS index_name,
  relname AS table_name,
  idx_scan,
  pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
  CASE
    WHEN idx_scan = 0 THEN '🔴 Não utilizado — considere DROP'
    WHEN idx_scan < 10 THEN '🟡 Baixo uso'
    ELSE '🟢 OK'
  END AS status
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%pkey%'
  AND indexrelname NOT LIKE '%_unique%'
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 20;
```

## 5. Queries lentas ativas (>1s)

```sql
SELECT
  pid,
  now() - pg_stat_activity.query_start AS duration,
  state,
  LEFT(query, 150) AS query_preview,
  wait_event_type,
  wait_event
FROM pg_stat_activity
WHERE
  state = 'active'
  AND now() - pg_stat_activity.query_start > interval '1 second'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY duration DESC
LIMIT 20;
```

## 6. Métricas de Disk IO (pg_stat_bgwriter + pg_stat_checkpointer)

> **PG17:** As colunas `checkpoints_timed`, `checkpoints_req` e `buffers_checkpoint`
> foram movidas para `pg_stat_checkpointer`. A query abaixo usa as novas colunas
> com fallback para `pg_stat_bgwriter` (compatível com PG ≤16).

- `num_timed`: checkpoints agendados (write IO)
- `num_requested`: checkpoints forçados (write IO)
- `buffers_written`: páginas escritas por checkpoint (write IO)
- `buffers_clean`: páginas escritas pelo background writer (write IO)
- `buffers_alloc`: páginas alocadas (read IO do disco)

```sql
-- Colunas movidas para pg_stat_checkpointer no PostgreSQL 17
SELECT 'checkpoints_timed' AS metric, num_timed AS value
FROM pg_stat_checkpointer
UNION ALL
SELECT 'checkpoints_req', num_requested FROM pg_stat_checkpointer
UNION ALL
SELECT 'buffers_checkpoint (writes)', buffers_written FROM pg_stat_checkpointer
UNION ALL
-- Estas colunas permanecem em pg_stat_bgwriter
SELECT 'buffers_clean (writes)', buffers_clean FROM pg_stat_bgwriter
UNION ALL
SELECT 'buffers_alloc (reads from disk)', buffers_alloc FROM pg_stat_bgwriter
UNION ALL
SELECT 'maxwritten_clean', maxwritten_clean FROM pg_stat_bgwriter;
```

## 7. Tamanho total do banco e tabelas >100MB

```sql
SELECT
  relname AS table_name,
  pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
  pg_size_pretty(pg_relation_size(relid)) AS table_size,
  pg_size_pretty(pg_indexes_size(relid)) AS indexes_size,
  n_live_tup AS estimated_rows
FROM pg_stat_user_tables
WHERE pg_total_relation_size(relid) > 100 * 1024 * 1024
ORDER BY pg_total_relation_size(relid) DESC;
```

## 8. Conexões ativas por estado

```sql
SELECT
  state,
  count(*) AS connections
FROM pg_stat_activity
GROUP BY state
ORDER BY connections DESC;
```

---

## Como interpretar os resultados

1. **Cache Hit Rate < 95%** → Aumentar `effective_cache_size` ou RAM do compute. Queries estão indo ao disco.
2. **Tabelas com seq_scan alto** → Criar índices nas colunas usadas nos WHERE/JOIN/ORDER BY.
3. **Dead tuples > 20%** → Rodar `VACUUM FULL` na tabela (cuidado: locks exclusive).
4. **Índices não utilizados > 0** → Remover índices que só consomem write IO.
5. **buffers_alloc muito alto** → Read IO excessivo. Verificar cache hit rate e índices.
