# Horizontal Scaling — Configuracao de Workers

> Guia de configuracao de workers, seguranca de cron loops e metricas de monitoramento.
> Issue #1867 | Ultima atualizacao: 2026-06-15

---

## 1. Workers Recomendados por Tier Railway

O SmartLic usa **Uvicorn** com `--workers` (multiprocessing.spawn, nao os.fork).
A configuracao de workers e controlada pela env var `WEB_CONCURRENCY`.

### Tabela de Recomendacao

| Tier Railway | RAM  | Workers Colocated | Workers Standalone | Colocated Worker? | Notas |
|-------------|------|-------------------|--------------------|-------------------|-------|
| Starter     | 512MB | 1                 | —                  | NAO recomendado   | Worker colocado exige ~150MB extras |
| Dev         | 1GB  | 1                 | 2                  | Opcional          | Com colocated, usar 1 worker web |
| Standard    | 2GB  | 1-2               | 2-3                | Sim               | Configuracao recomendada para producao |
| Performance | 4GB  | 2-3               | 4                  | Sim               | Suporta picos de Googlebot ISR |
| High Memory | 8GB  | 3-4               | 6                  | Sim               | Para escalonamento agressivo |

**Regra pratica:** `WEB_CONCURRENCY = floor(RAM_GB * 0.6)` para standalone, `floor(RAM_GB * 0.3)` para colocated.

### Variaveis de Ambiente

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `WEB_CONCURRENCY` | `2` (standalone), `1` (colocated) | Numero de processos worker |
| `WORKER_COLOCATED` | `false` | Se `true`, executa ARQ worker como subprocesso no mesmo container |
| `GUNICORN_MAX_REQUESTS` | `50000` | Max requests antes de reciclar worker (previne memory leak) |
| `UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN` | `120` | Tempo para shutdown graceful |

### Configuracao para Colocated (COST-OPT)

Quando `WORKER_COLOCATED=true`, o worker web divide a RAM com o worker ARQ:

```bash
# Railway env vars recomendados para tier Standard (2GB)
WEB_CONCURRENCY=1
WORKER_COLOCATED=true
GUNICORN_MAX_REQUESTS=50000
```

O worker ARQ consome ~150MB adicionais. Com `WEB_CONCURRENCY=1`, cada worker web
tem ~1.8GB disponivel (assumindo 2GB total e 200MB para Redis + worker ARQ).

---

## 2. Seguranca de Cron Loops com Multi-Worker

### Problema

Com `WEB_CONCURRENCY > 1`, cada worker dispara suas proprias tarefas de background
(lifespan tasks registradas no `task_registry`). Sem protecao, 19 loops de cron
executariam simultaneamente em cada worker.

### Solucao: Redis Distributed Locks

Todas as tarefas de cron usam `acquire_redis_lock()` / `release_redis_lock()` do
`cron/_loop.py`. O lock Redis NX (SET if Not eXists) com TTL garante que apenas
um worker execute cada tarefa por ciclo:

```python
async def acquire_redis_lock(key: str, ttl: int) -> bool:
    """Try to acquire a Redis NX lock. Returns True if acquired or Redis unavailable."""
    redis = await get_redis_pool()
    if redis:
        acquired = await redis.set(key, timestamp, nx=True, ex=ttl)
        if not acquired:
            return False  # Outro worker ja adquiriu o lock
    return True  # Redis indisponivel = prossegir (graceful degradation)
```

**Mecanismo de seguranca:**

1. Cada tarefa de cron tem uma chave de lock unica (ex: `reconciliation_lock`, `alerts_lock`)
2. O TTL do lock cobre o tempo maximo esperado de execucao da tarefa
3. Se o Redis estiver indisponivel, `acquire_redis_lock` retorna `True` (prossegir sem lock)
4. Tasks do ARQ worker (WorkerSettings._worker_cron_jobs) tem protecao similar via
   `_worker_on_startup` + Redis health-check key

### Tarefas Lifespan Protegidas por Redis Lock

| Tarefa | Lock Key | TTL | Frequencia |
|--------|----------|-----|------------|
| `reconciliation` | `reconciliation_lock` | 300s | Diario |
| `revenue_share` | `revenue_share_lock` | 300s | Diario |
| `plan_reconciliation` | `plan_reconciliation_lock` | 300s | Diario |
| `alerts` | `alerts_lock` | 300s | Periodico |
| `api_metered_billing` | `api_metered_billing_lock` | 300s | Periodico |
| `trial_sequence`, `health_canary`, etc. | NX lock interno | Variavel | Periodico |

### Riscos Conhecidos

1. **Cache L1 (InMemoryCache):** Cada worker tem seu proprio cache em memoria.
   Um item quente em um worker pode estar frio em outro. Mitigado pelo Redis L2
   compartilhado (STORY-5.1).

2. **SSE Progress Tracker:** O tracker de progresso e in-memory (asyncio.Queue).
   Com multi-worker, um POST /buscar pode cair no worker A e o SSE GET no worker B.
   Mitigado pelo Redis Streams (STORY-276/STORY-294) quando Redis esta disponivel.

3. **ARQ Pool `_arq_pool`:** Cada worker cria sua propria conexao ARQ com Redis.
   Protegido por `asyncio.Lock` + `threading.Lock` (Issue #1867 AC1).

---

## 3. Metricas de Monitoramento

### Metricas Prometheus (Issue #1867 AC3)

| Metrica | Tipo | Descricao |
|---------|------|-----------|
| `smartlic_web_workers_configured` | Gauge | Numero de workers configurados (via WEB_CONCURRENCY) |
| `smartlic_web_requests_total{worker_pid}` | Counter | Requests por worker PID |

### Metricas Existentes Relevantes

| Metrica | Tipo | Descricao |
|---------|------|-----------|
| `smartlic_worker_timeout_total{reason}` | Counter | Timeouts de worker |
| `smartlic_worker_memory_bytes{worker_pid}` | Gauge | RSS por worker (CRIT-083 AC5) |
| `smartlic_route_timeout_total{route,method}` | Counter | Requests que excederam ROUTE_TIMEOUT_S |
| `smartlic_process_memory_rss_bytes` | Gauge | RSS total do processo |
| `smartlic_redis_available` | Gauge | Disponibilidade do Redis (1=OK, 0=fallback) |

### Alertas Sugeridos (Sentry/Grafana)

| Alerta | Condicao | Acao |
|--------|----------|------|
| `worker_memory_high` | `worker_memory_bytes > 512MB` | Verificar memory leak, reduzir WEB_CONCURRENCY |
| `worker_timeout_rate` | `rate(worker_timeout_total[15m]) > 5` | Investigar slow queries, aumentar ROUTE_TIMEOUT_S |
| `worker_request_imbalance` | Um worker com >60% dos requests | Investigar sticky routing / health check |
| `worker_oom` | Exit code -9 no worker_exit | Reduzir WEB_CONCURRENCY, aumentar RAM |

---

## 4. Sinais de Que Precisa Escalar

### Quando Aumentar Workers

- **CPU usage > 80%** sustained por > 5 minutos (todos os workers)
- **P95 latency** de busca > 30s para datalake queries
- **Rate limit hits frequentes** (429) para usuarios pagantes
- **SSE connections** simultaneas > 50
- **Queue depth** do ARQ > 50 jobs pendentes

### Quando Reduzir Workers

- **OOM kills frequentes** (exit code -9 em `worker_exit`)
- **RSS por worker > 512MB** com tendencia de crescimento
- **Googlebot bursts** causando 502/503 (reduzir workers libera mais RAM por processo)
- **Colocated worker competindo** por memoria com web worker

### Plano de Escala Tipico

```
Estagio 1 (512MB Starter):
  WEB_CONCURRENCY=1, standalone
  ~30 usuarios concorrentes

Estagio 2 (2GB Standard):
  WEB_CONCURRENCY=1-2, colocated
  ~100 usuarios concorrentes

Estagio 3 (4GB Performance):
  WEB_CONCURRENCY=2-3, colocated
  ~250 usuarios concorrentes

Estagio 4 (8GB High Memory):
  WEB_CONCURRENCY=3-4, colocated
  ~500+ usuarios concorrentes
```

---

## 5. Runner History & Restricoes

### CRIT-083: Gunicorn prefork + cryptography SIGSEGV

O projeto usava Gunicorn com prefork (`os.fork`), mas `cryptography>=46` nao e
fork-safe — POST requests com TLS handshake causavam SIGSEGV. GET requests
funcionavam, POST crashavam.

**Solucao (CRIT-084):** Uvicorn com `--workers` usa `multiprocessing.spawn()`,
que nao invoca `os.fork()`. Gunicorn esta deprecated e nao deve ser reativado
enquanto cryptography nao remover a restricao de fork.

### RES-BE-016: Route-level asyncio timeout

Middleware de timeout a 60s retorna 503 antes do Railway proxy kill a 120s.
Libera o event loop para proximos requests; threads subjacentes continuam ate
`statement_timeout=15s` do Supabase.

### Validacao Pre-Producao

Antes de alterar `WEB_CONCURRENCY` em producao:

1. Validar em staging que nao ha aumento de `worker_timeout_total`
2. Verificar `worker_memory_bytes` de cada worker < 512MB
3. Confirmar que SSE progress funciona cross-worker (Redis Streams)
4. Rodar os testes `test_crit033_enqueue_fix.py` (ARQ pool thread safety)

---

## Referencias

- `backend/start.sh` — Entrypoint com configuracao de workers
- `backend/gunicorn_conf.py` — Hooks de worker lifecycle (deprecated, gunicorn apenas)
- `backend/cron/_loop.py` — Redis lock helpers
- `backend/job_queue.py` — ARQ pool com thread safety (Issue #1867)
- `backend/metrics.py` — Todas as metricas Prometheus
- `docs/operations/capacity-limits.md` — Limites de capacidade atuais
- .claude/rules/critical-impl-notes.md — Runner history (CRIT-083/084/RES-BE-016)
