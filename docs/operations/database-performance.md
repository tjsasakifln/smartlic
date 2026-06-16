# Database Performance Monitoring

> Referencia operacional para monitoramento de performance de queries em producao.
> Ultima atualizacao: 2026-06-15

## Visao Geral

O SmartLic usa PostgreSQL 17 via Supabase Cloud. Este documento descreve as ferramentas
de monitoramento de performance de queries implementadas pela issue #1866.

## pg_stat_statements

O `pg_stat_statements` e o principal mecanismo de tracing de queries. Ele registra
metricas de execucao (tempo de planejamento, execucao, linhas, I/O) para todas as
queries executadas desde o ultimo reset.

### Ativacao

1. **shared_preload_libraries**: Requer ticket de suporte no Supabase para adicionar
   `pg_stat_statements` ao `shared_preload_libraries`. Apos aprovacao, a migration
   `20260615090000_enable_pg_stat_statements.sql` cria a extension e concede acesso
   ao `service_role`.

2. **Verificacao**:
   ```sql
   SELECT * FROM extensions.pg_stat_statements LIMIT 1;
   ```

3. **Reset de estatisticas** (apenas durante manutencao):
   ```sql
   SELECT extensions.pg_stat_statements_reset();
   ```

### Queries Criticas Monitoradas

As 5 queries mais frequentes no DataLake que sao monitoradas via Prometheus:

| Query Name | Descricao | Tipo | Fonte |
|-----------|-----------|------|-------|
| `query_datalake_total` | Tempo total da funcao `query_datalake()` | Histogram | `datalake_query.py` |
| `search_datalake` | RPC principal de busca full-text | Histogram | `datalake_query.py` |
| `search_datalake_trigram_fallback` | RPC de fallback trigram (quando FTS retorna 0) | Histogram | `datalake_query.py` |

Metrica: `smartlic_db_query_duration_ms{query_name,le}` no endpoint `/metrics`.

## Scripts de Analise

### analyze-slow-queries.py

Extrai o top 20 queries do `pg_stat_statements` por `total_time`, `mean_time` e `calls`,
e gera EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) para queries acima de 100ms.

```bash
# Analise completa
python scripts/analyze-slow-queries.py --limit 20 --output report.json

# Modo CI — falha se alguma query > 500ms mean_time
python scripts/analyze-slow-queries.py --fail-mean-ms 500

# Apenas EXPLAIN para queries conhecidas
python scripts/analyze-slow-queries.py --explain-only
```

**Variaveis de ambiente necessarias:**
- `SUPABASE_URL` — URL do projeto Supabase
- `SUPABASE_SERVICE_ROLE_KEY` — Service role key

**Exit codes:**
- `0` — todas as queries dentro do limite
- `1` — queries acima do threshold `--fail-mean-ms`
- `2` — erro de conexao

### check-unused-indexes.py

Detecta indices nunca escaneados (`idx_scan = 0`) via `pg_stat_user_indexes`,
excluindo primary keys e unique constraints.

```bash
# Relatorio completo
python scripts/check-unused-indexes.py

# Apenas indices > 10MB
python scripts/check-unused-indexes.py --min-size-mb 10
```

**Exit codes:**
- `0` — nenhum indice nao utilizado
- `1` — indices nao utilizados encontrados
- `2` — erro de conexao

## CI Semanal

O workflow `.github/workflows/db-performance-audit.yml` roda toda segunda-feira as 09:00 UTC:

1. Executa `analyze-slow-queries.py` com `--fail-mean-ms 500`
2. Executa `check-unused-indexes.py` (advisory, nao bloqueia)
3. Se queries acima de 500ms: cria uma issue no GitHub e falha o workflow

## Metricas Prometheus (#1866 AC3)

| Metrica | Tipo | Labels | Descricao |
|---------|------|--------|-----------|
| `smartlic_db_query_duration_ms` | Histogram | `query_name` | Latencia de queries do banco em ms |

Buckets: 1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000 ms

## Alertas Sugeridos

### Grafana / Sentry

| Condicao | Severidade | Acao |
|----------|-----------|------|
| `rate(smartlic_db_query_duration_ms_sum[5m]) / rate(smartlic_db_query_duration_ms_count[5m]) > 500` | WARNING | Verificar EXPLAIN plans no relatorio semanal |
| `rate(smartlic_db_query_duration_ms_sum[5m]) / rate(smartlic_db_query_duration_ms_count[5m]) > 1000` | CRITICAL | Investigacao imediata — timeout Railway (120s) pode ser atingido |
| `increase(smartlic_route_timeout_total[1h]) > 5` | CRITICAL | Timeouts de rota podem ser causados por queries lentas |

## Procedimentos

### Investigar Query Lenta

1. Rodar analise local:
   ```bash
   python scripts/analyze-slow-queries.py --limit 20
   ```
2. Revisar EXPLAIN plans no output JSON (campo `slow_queries_explain`)
3. Verificar indices ausentes:
   ```sql
   SELECT indexname, tablename, idx_scan
   FROM pg_stat_user_indexes
   WHERE idx_scan = 0 AND schemaname = 'public'
   ORDER BY pg_relation_size(indexrelid::regclass) DESC;
   ```
4. Verificar se a query esta no budget de tempo (STORY-4.4):
   - Pipeline: 100s
   - Consolidacao: 90s
   - Por fonte: 70s
   - Por UF: 25s

### Resetar Estatisticas do pg_stat_statements

Apenas durante janela de manutencao:

```bash
python -c "
import httpx
headers = {'apikey': '$SUPABASE_SERVICE_ROLE_KEY', 'Authorization': f'Bearer $SUPABASE_SERVICE_ROLE_KEY'}
resp = httpx.post(f'{SUPABASE_URL}/rest/v1/sql',
    headers=headers,
    content='SELECT extensions.pg_stat_statements_reset();')
print(resp.status_code, resp.text)
"
```
