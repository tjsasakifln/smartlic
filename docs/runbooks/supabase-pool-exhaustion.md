# Runbook: Supabase Pool Exhaustion (CRIT-046)

**Versao:** 1.0
**Criado:** 2026-06-17
**Owner:** @devops
**Severidade tipica:** SEV2 (pode escalar SEV1)
**Referencia:** CRIT-046, `incident-response.md` secao 3.2

---

## 1. Sintomas

### Alertas
- Sentry: `smartlic_supabase_pool_timeouts_total > 0`
- Metrica: `wedge_risk=high` no health check
- Railway log: `PoolTimeout` ou `ConnectionError` em queries Supabase
- Usuario reporta: buscas falham, login demora, pipeline nao carrega

### Comportamento Observado
```
Log: "sqlalchemy.exc.TimeoutError: QueuePool limit of size X overflow Y reached"
Log: "psycopg2.OperationalError: connection to server at ... timed out"
Health: curl -s https://api.smartlic.tech/health/ready | jq '.wedge_risk'
  → "high"
```

### Impacto Progressivo
| Estagio | Sintoma | Acao |
|---------|---------|------|
| Leve (< 50% pool) | Queries mais lentas (p95 > 5s) | Monitorar |
| Moderado (50-80% pool) | Timeouts intermitentes em login | Diagnosticar |
| Critico (> 80% pool) | Pipeline travado, buscas falhando | Mitigar IMEDIATAMENTE |
| Exaustao (100% pool) | Backend incapaz de responder | Emergency |

---

## 2. Diagnostico

### 2.1 Pool Metrics via Prometheus

```bash
# Pool utilization
curl -s https://api.smartlic.tech/metrics | grep -E 'smartlic_supabase_pool_(active|idle|max|timeouts|retry|waiting)'

# Wedge risk + health
curl -s https://api.smartlic.tech/health/ready | jq '{wedge_risk: .wedge_risk, checks: .checks}'
```

### 2.2 Conexoes Ativas (Supabase Management API)

```bash
# Total ativas
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT count(*) as active_conns FROM pg_stat_activity WHERE state = '\''active'\''"}' | jq .

# Por origem (aplicacao vs pgadmin vs outros)
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT application_name, count(*) FROM pg_stat_activity GROUP BY application_name ORDER BY count DESC"}' | jq .
```

### 2.3 Queries Lentas (> 10s)

```bash
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT pid, now() - query_start AS duration, query, state, wait_event FROM pg_stat_activity WHERE state != '\''idle'\'' AND now() - query_start > interval '\''10 seconds'\'' ORDER BY duration DESC"}' | jq .
```

### 2.4 Bloqueios / Locks

```bash
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT blocked_locks.pid AS blocked_pid, blocking_locks.pid AS blocking_pid, blocked_activity.query AS blocked_query, blocking_activity.query AS blocking_query FROM pg_locks blocked_locks JOIN pg_stat_activity blocked_activity ON blocked_locks.pid = blocked_activity.pid JOIN pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid AND blocking_locks.pid != blocked_locks.pid WHERE NOT blocked_locks.GRANTED;"}' | jq .
```

### 2.5 Railway Logs

```bash
railway logs --tail --service bidiq-backend | grep -E "supabase|pool|timeout|connection|psycopg|sqlalchemy"
```

### 2.6 Verificar Deploy Recente

```bash
gh api /repos/confenge/smartlic/actions/runs --jq '.workflow_runs[:3] | .[] | {name, status, conclusion, created_at}'
```

---

## 3. Causas Comuns

| Causa | Indicador | Probabilidade |
|-------|-----------|---------------|
| `statement_timeout` alto (queries rodam > 30s) | Queries lentas em `pg_stat_activity` | Alta |
| Pico de requests simultaneos | Pool ativo proximo ao max, CPU alta | Media |
| SSG build hammering backend | Build logs mostram fetch concorrente | Media |
| Conexoes vazando (sem cleanup) | Active connections cresce monotonicamente | Alta se codigo novo |
| Supabase PG restart / failover | Pool reseta, conexoes antigas invalidas | Baixa |
| RLS policy cara (full scan) | Queries simples demorando > 5s | Media |

---

## 4. Mitigacao

### 4.1 Imediata: Reduzir statement_timeout (2 min)

```bash
# Reduzir de 30s para 15s
railway variables set SUPABASE_STATEMENT_TIMEOUT=15000 --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

**Impacto:** Queries que excederiam 15s sao canceladas, liberando conexoes. Resultados parciais sao melhores que timeout total.

### 4.2 Se persistir: Aumentar pool size

```bash
# Aumentar max connections (cuidado: Supabase PG tem limite)
railway variables set SUPABASE_POOL_MAX_CONNECTIONS=25 --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

**Impacto:** Mais conexoes = mais concorrencia, mas cada conexao consome RAM do PG. Se o Supabase PG estiver proximo do limite de conexoes (`max_connections`), isso nao resolve.

### 4.3 Se persistir: Reduzir WEB_CONCURRENCY

```bash
# Menos workers = menos conexoes simultaneas
railway variables set WEB_CONCURRENCY=2 --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

**Impacto:** Reduz throughput, mas cada request tem mais recursos. Preferivel a downtime total.

### 4.4 Emergency: Matar queries locks

```bash
# Identificar PID da query bloqueante
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT pg_terminate_backend(<PID>);"}' | jq .
```

### 4.5 Emergency: Rollback

Se deploy recente introduziu o problema, rollback e a acao mais rapida:

```bash
railway rollback --service bidiq-backend
```

---

## 5. Resolucao

### 5.1 Verificar pool apos mitigacao

```bash
curl -s https://api.smartlic.tech/health/ready | jq '.wedge_risk'
# Esperado: "low"

curl -s https://api.smartlic.tech/metrics | grep 'smartlic_supabase_pool_active'
# Esperado: < 50% do max
```

### 5.2 Verificar funcionalidade critica

```bash
# Testar busca simples
curl -s -X POST https://api.smartlic.tech/v1/buscar \
  -H "Content-Type: application/json" \
  -d '{"ufs": ["SC"], "dataInicial": "2026-06-01", "dataFinal": "2026-06-10"}' | jq '.status'

# Testar health endpoint
curl -s https://api.smartlic.tech/health/ready | jq '.ready'
```

### 5.3 Se resolveu com statement_timeout reduzido

Manter a reducao permanentemente e monitorar por 24h. Se `wedge_risk` permanecer baixo e nao houver queries legitimamente lentas sendo truncadas, a reducao e segura.

### 5.4 Se foi deploy: criar hotfix

```bash
git log --oneline -3                    # Identificar commit problemático
git revert HEAD                         # Reverter
# Criar fix adequado, testar, commitar
```

---

## 6. Prevencao

### Monitoramento Continuo
- Gauge: `smartlic_supabase_pool_active` — alertar se > 70% do max por > 5 min
- Gauge: `smartlic_supabase_pool_timeouts_total` — alertar se > 0
- Health: `wedge_risk=high` — disparar alerta Sentry
- Slow query log: qualquer query > 5s deve gerar warning

### Codigo
- `get_supabase()` sempre com `try/finally` para garantir cleanup
- Connection pool config com `pool_pre_ping=True` (conexoes stale)
- Statement timeout configurado via env var (nao hardcoded)
- Queries batch processadas com limit/offset e timeout individual

### CI Gate
- Testes de integracao devem usar pool minimo (2 conexoes) para detectar leaks
- Code review checklist: "conexao Supabase foi fechada?"

### Referencia

**CRIT-046 (2026-04):** Pool saturation durante pico de uso. `statement_timeout` estava em 30s (default). Fix: reduzir para 15s. Criados gauges de pool para monitoramento continuo.

---

## 7. Referencias

- `incident-response.md` secao 3.2 — Playbook resumido Supabase Pool Exhaustion
- `backend/config.py` — `SUPABASE_STATEMENT_TIMEOUT`, `SUPABASE_POOL_MAX_CONNECTIONS`
- `docs/architecture/system-architecture.md` — Diagrama de conexoes
- Supabase Status: https://status.supabase.com
- Supabase Docs: https://supabase.com/docs/guides/platform/database-size-and-performance
