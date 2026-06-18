# Capacity Planning — SmartLic

**Issue:** [#1962](https://github.com/tjsasakifln/SmartLic/issues/1962)
**Status:** v1 (2026-06-17) — snapshot inicial, revisoes periodicas a cada 3 meses
**Autor:** Dex (Builder) via AIOX Dev agent

---

## Tabela de Conteudo

1. [Current Capacity Snapshot](#1-current-capacity-snapshot)
2. [Bottleneck Analysis](#2-bottleneck-analysis)
3. [Growth Projections](#3-growth-projections)
4. [Scale Triggers](#4-scale-triggers)
5. [Railway Upgrade Path](#5-railway-upgrade-path)
6. [Action Items](#6-action-items)

---

## 1. Current Capacity Snapshot

Levantamento da capacidade atual da infraestrutura de producao, coletado dos arquivos de configuracao, plano de assinatura e metricas existentes.

### 1.1 Container Infrastructure (Railway)

| Recurso | Backend (smartlic-backend) | Frontend (bidiq-frontend) |
|---------|---------------------------|---------------------------|
| **Runtime** | Python 3.12, FastAPI, Uvicorn | Node.js 20, Next.js 16 |
| **Workers** | 2 uvicorn workers (ou 1 com `WORKER_COLOCATED=true`) | 1 processo Node.js |
| **Memoria** | Partilhada com Redis embarcado (~128MB Redis + worker) | 512MB heap (`--max-old-space-size=512`) |
| **CPU** | 1 vCPU compartilhado Railway | 1 vCPU compartilhado Railway |
| **Timeout proxy** | 120s (hard limit Railway) | 120s (hard limit Railway) |
| **Healthcheck** | `/health/live`, timeout 300s, 10 retries | `/api/health`, timeout 600s, 10 retries |
| **Drain** | 120s overlap + 120s draining | 30s overlap + 120s draining |

### 1.2 Cache Layer

| Componente | Capacity | Limite Configurado |
|------------|----------|-------------------|
| **Redis (embarcado)** | 128MB maxmemory, allkeys-lru | `redis-server --maxmemory 128mb` |
| **Pool Redis (persistente)** | 50 conexoes | `POOL_MAX_CONNECTIONS = 50` |
| **Pool Redis (SSE)** | 10 conexoes | `SSE_SOCKET_TIMEOUT = 60s` |
| **Pool Redis (sync)** | 12 conexoes (para ThreadPoolExecutor) | `_SYNC_POOL_MAX_CONNECTIONS = 12` |
| **InMemoryCache (fallback)** | 5.000 entradas LRU | `INMEMORY_MAX_ENTRIES = 5000` |
| **L1 InMemoryCache (search)** | 4h TTL, hot/warm/cold | Cache de busca em memoria |
| **L2 Supabase search_cache** | 24h TTL | `RESULTS_SUPABASE_TTL_HOURS = 24` |
| **State Store Redis prefix** | `smartlic:` | `STATE_STORE_REDIS_PREFIX` |

### 1.3 Database (Supabase PostgreSQL)

| Recurso | Valor Estimado | Fonte |
|---------|---------------|-------|
| **Pool de conexoes (httpx)** | 25/worker x 2 workers = 50 max | `_POOL_MAX_CONNECTIONS = 25` (env var overridable) |
| **Keepalive** | 10 conexoes | `_POOL_MAX_KEEPALIVE = 10` |
| **Pool timeout** | 30s | `_POOL_TIMEOUT = 30.0` |
| **statement_timeout** | 15s | Configuracao Railway (CRIT-046) |
| **P95 DataLake RPC** | <100ms | Dado operacional historico |
| **Tabela `pncp_raw_bids`** | ~1.5M rows, 400d retention | Ingestion ETL |
| **Tabela `pncp_supplier_contracts`** | ~2M+ rows | 3x/week crawl |
| **Bulkhead DataLake** | 5 conexoes simultaneas | Semaphore config |
| **Bulkhead Blog SEO** | 3 conexoes simultaneas | Semaphore config |

### 1.4 Rate Limits Atuais

| Recurso | Limite | Escopo |
|---------|--------|--------|
| **Buscas por usuario/minuto** | 10 (free/trial), 60 (Pro), 120 (Command) | Por usuario |
| **Buscas por usuario/mes** | 10 (free) a 5000 (Command/Consultoria) | Por usuario/org |
| **Auth (login/signup)** | 5/5min por IP, 3/10min signup | Por IP |
| **Bot crawl** | 10 requisicoes/min | Por bot detectado |
| **Humano** | 60 requisicoes/min | Por usuario autenticado |
| **SSE conexoes** | 3 por usuario | Por usuario |
| **SSE reconnect** | 10 por 60s | Por usuario |
| **Feedback** | 50 requests | Global (rate bucket) |
| **Deep Analysis** | 20 requests | Global (rate bucket) |
| **PNCP Bulkhead** | 5 UFs simultaneas | `PNCP_BULKHEAD_CONCURRENCY` |
| **PCP Bulkhead** | 3 simultaneos | `PCP_BULKHEAD_CONCURRENCY` |
| **ComprasGov Bulkhead** | 3 simultaneos | `COMPRASGOV_BULKHEAD_CONCURRENCY` |

### 1.5 Circuit Breakers

| Servico | Threshold (falhas) | Cooldown |
|---------|-------------------|----------|
| PNCP | 15 | 60s |
| PCP v2 | 15 | 60s |
| ComprasGov v3 | 15 | 60s |
| BrasilAPI | 3 | 60s |
| IBGE | 5 | 120s |

### 1.6 LLM (GPT-4.1-nano)

| Recurso | Valor |
|---------|-------|
| Modelo | `gpt-4.1-nano` |
| Max concorrencia | 50 chamadas simultaneas |
| Timeout por chamada | 5s (`OPENAI_TIMEOUT_S`) |
| Timeout future (batch) | 20s |
| Zero-match batch | 20 itens por batch |
| Max tokens classificacao | 1 (`LLM_ARBITER_MAX_TOKENS`) |
| Max tokens summary | 200 a 20.000 (por plano) |
| Custo alerta | $1/hora |

### 1.7 Time Budget Waterfall

```
Railway proxy     [========================== 120s ==========================]
Route timeout     [=================== 60s ===================]
Pipeline budget   [==================== 100s ====================]
  Consolidation   [================== 90s ===================]
    PerSource     [============= 70s =============]
      PerUF       [===== 25s =====]
        httpx r/w [10c+15r]
```

---

## 2. Bottleneck Analysis

### 2.1 Identificacao dos Gargalos Atuais

#### Gargalo #1 — Redis (Critico)
**Sintoma:** Redis embarcado com apenas **128MB de maxmemory**, compartilhando container com o backend uvicorn (que ja consome ~200-400MB RSS). Quando o Redis atinge o limite, entradas sao evictadas LRU — degradacao de cache search/state/arbiter.
- **Limite teorico:** ~1.3 milhoes de keys de 100 bytes, ou ~2.500 resultados de busca de 50KB cada, ou ~12.800 entradas de state store de 10KB cada.
- **Impacto:** Cache miss forcado -> reprocessamento -> aumento de latencia p95.
- **Gravidade:** Alta (afeta experiencia de busca e SSE)
- **Mitigacao atual:** InMemoryCache como fallback (5.000 entradas, ~250MB worst case)

#### Gargalo #2 — Supabase Pool (Moderado)
**Sintoma:** Pool de 25 conexoes httpx por worker com 2 workers = 50 conexoes totais. O semaphore interno (5 datalake + 3 blog) limita concorrencia efetiva a ~8/worker, mas pool httpx precisa de headroom para keepalive + overshoot.
- **Ponto de saturacao:** ~10 requisicoes simultaneas por worker (25 slots - overshoot)
- **Alem de 15 conexoes ativas:** high-water warning logado
- **Impacto:** Degradacao gradual, nao falha abrupta — conexoes aguardam em fila

#### Gargalo #3 — Timeout Chain (Observado)
**Sintoma:** Cadeia de timeouts aninhados (pipeline 100s > route 60s > Railway proxy 120s). Se o pipeline excede 60s, route timeout retorna 503 antes do Railway matar a requisicao.
- **Incidentes historicos:** CRIT-010 (404s), CRIT-080 (SIGSEGV POST), Stage 2-8 wedge
- **Gatilho:** Mais de 3 buscas concorrentes com 27 UFs cada saturam o pool e disparam timeouts
- **Mitigacao:** `_run_with_budget`, `EARLY_RETURN_THRESHOLD_PCT=0.66`

#### Gargalo #4 — Conexoes com APIs Governamentais (Moderado)
**Sintoma:** PNCP tem bulkhead de 5 UFs simultaneas, 2s delay entre batches. 27 UFs x 6 modalidades = ateh 162 requests em sequencia.
- **Latencia minima:** 27 UFs / 5 batch * 2s delay + 27 UFs * 6 modalidades * ~3s call = ~540s (completo)
- **Na pratica:** Early return apos 66% das UFs (threshold 0.66) -> ~360s no worst case
- **Mas:** Route timeout de 60s corta antes -> apenas ~3-5 UFs completas por busca sincrona

#### Gargalo #5 — LLM Concurrency (Baixo)
**Sintoma:** 50 chamadas simultaneas ao GPT-4.1-nano. Cada chamada ~1s p99.
- **Capacidade teorica:** 50 requisicoes/s de classificacao
- **Gargalo real:** OpenAI rate limits da API key (nao controlado por nos)
- **Impacto:** Se OpenAI limita, fallback para `PENDING_REVIEW` com `LLM_FALLBACK_PENDING_ENABLED=true`

### 2.2 Matriz de Saturacao

| Componente | Capacidade | Uso Estimado Atual | Folga | Risco |
|------------|-----------|--------------------|-------|-------|
| Redis 128MB | ~1.3M keys (100B) | ~200K-500K keys (busca + state + CB + rate limit) | ~60% | **Alto** — colocado com worker |
| Supabase pool (50) | 50 conexoes | ~5-15 conexoes (pico) | ~70% | **Medio** — crescimento linear |
| Backend CPU | 1 vCPU | ~30-50% (pico busca) | ~50% | **Medio** — burst curto |
| Backend memory | ~512MB livre | ~200-350MB (uvicorn + app) | ~30-50% | **Medio** — proximo ao limite |
| Frontend memory | 512MB heap | ~200-400MB (Next.js SSR + ISR) | ~20-60% | **Medio** — depende do padrao de acesso |
| PNCP bulkhead (5) | 5 UFs simultaneas | 5 (sempre no limite durante busca) | **0%** | **Alto** — sempre no teto |
| LLM concurrency (50) | 50 chamadas | ~1-10 chamadas (pico) | ~80% | **Baixo** — folga confortavel |
| Railway timeout (120s) | N/A | 60s route timeout | 50% | **Baixo** — middleware protege |

---

## 3. Growth Projections

### 3.1 Cenario 10x (50-100 usuarios pagos simultaneos)

**Premissas:** 10x o trafego atual estimado (~5-10 usuarios simultaneos -> 50-100).

| Componente | Comportamento | Quem Quebra Primeiro |
|------------|--------------|---------------------|
| **Redis 128MB** | 10x keys = 2M-5M keys > 128MB -> **eviction massivo** | **QUEBRA** |
| **Supabase pool 50** | 10x conexoes = 50-150 -> **pool esgota** (max 50) | **QUEBRA** |
| **Backend CPU 1 vCPU** | 10x requests = saturacao de CPU sostenida | Degradacao severa |
| **Backend memory 512MB** | 10x state stores + conexoes = OOM risk | Degradacao |
| **PNCP bulkhead 5** | 10x buscas -> fila de espera -> timeout em massa | Degradacao severa |
| **LLM concorrencia 50** | 10x = 10-100 chamadas -> ainda dentro do limite | OK |
| **Railway 120s timeout** | Mais requisicoes lentas -> mais 503s | Degradacao |

**Gargalo Primario 10x:** **Redis** (128MB esgota primeiro) seguido de **Supabase pool** (50 conexoes).

**Custo estimado 10x sem upgrade:** Degradacao generalizada, cache miss 100%, timeouts frequentes, p95 >30s.

### 3.2 Cenario 100x (500-1000 usuarios pagos simultaneos)

| Componente | Comportamento | Quem Quebra Primeiro |
|------------|--------------|---------------------|
| **Redis** | 20M+ keys -> 100% eviction -> InMemoryCache 5K entries -> **cascading miss** | **QUEBRA** |
| **Supabase pool** | 500-1000 conexoes -> **Erros de conexao generalizados** | **QUEBRA** |
| **Backend CPU** | 100x -> 5-10 vCPU equivalentes em 1 vCPU -> **fila de request** | **QUEBRA** |
| **Backend memory** | Sob demanda -> **OOM repetido** | **QUEBRA** |
| **PNCP** | Bulkhead 5 -> 100x fila -> **timeout permanente** | **QUEBRA** |
| **LLM** | 500-1000 chamadas simultaneas -> OpenAI rate limit | **QUEBRA** |
| **Supabase DB CPU** | 100x mais queries -> **DB contention** | **QUEBRA** |
| **Storage (pncp_raw_bids 1.5M)** | 100x dados = 150M rows -> **storage excede plano** | **QUEBRA** |

**Gargalo Primario 100x:** **Backend single-container CPU** (1 vCPU nao escala horizontal), seguido de **storage PostgreSQL**.

**Custo estimado 100x sem upgrade:** Sistema inoperante para usuarios pagos. Tempo de resposta em minutos.

### 3.3 Cenario 1000x (5000-10000 usuarios pagos simultaneos)

Todos os componentes da camada atual quebram antes de chegar aqui. **Arquitetura precisa ser refatorada**:

| Mudanca Necessaria | Por que |
|--------------------|---------|
| Multi-container backend (horizontal scaling) | 1 vCPU nao sustenta |
| Redis externo gerenciado (Upstash/Redis Cloud) | 128MB embarcado inviavel |
| Cache distribuido (Redis Cluster) | InMemoryCache nao replica entre pods |
| Read replicas PostgreSQL | Pool de 50 conexoes saturado |
| Fila de processamento dedicada (ARQ workers separados) | WORKER_COLOCATED nao escala |
| CDN para SEO pages (10k+ ISR) | Cache de edge para descarregar Node.js |
| OpenAI API key tier upgrade | Rate limit de API key |

---

## 4. Scale Triggers

Definicao de limites percentuais de saturacao que disparam planos de acao automaticos ou manuais.

### 4.1 Tabela de Triggers

| Componente | Gatilho (70%) | Gatilho (85%) | Gatilho (95%) |
|-----------|--------------|--------------|--------------|
| **Redis memory** | ~90MB usado das 128MB | ~109MB usado | ~122MB usado |
| **Supabase pool** | ~35 conexoes ativas | ~42 conexoes | ~47 conexoes |
| **Backend CPU (1m avg)** | ~70% sostenido | ~85% | ~95% |
| **Backend RSS memory** | ~360MB | ~435MB | ~490MB |
| **Rate limit atingido** | >70% das requests rate-limited | >85% | >95% |
| **Route timeouts / hora** | >7/hr (70% de 10/hr) | >8.5/hr | >9.5/hr |
| **Error rate p95** | >1.4% (70% de 2%) | >1.7% | >1.9% |

### 4.2 Quando Escalar: Planos de Acao

**Trigger Nivel 1 — Preventivo (70%):**

| Gatilho | Acao | Responsavel | SLA |
|---------|------|-------------|-----|
| Redis >90MB | Migrar Redis para Upstash (free tier 30MB ou 1GB $5/mo) | DevOps | 7 dias |
| Supabase pool >35 | Aumentar `SUPABASE_POOL_MAX_CONNECTIONS=50` (env var) | DevOps | 24h |
| CPU >70% sostenido | Aumentar `WEB_CONCURRENCY=3-4` (se memory permitir) | DevOps | 24h |
| Route timeouts >7/h | Investigar slow queries, verificar `_run_with_budget` coverage | Dev | 48h |
| Erros 4xx/5xx >1.4% | Investigar fonte (gargalo externo vs interno) | Dev + DevOps | 24h |

**Trigger Nivel 2 — Critico (85%):**

| Gatilho | Acao | Responsavel | SLA |
|---------|------|-------------|-----|
| Redis >109MB | **Urgente:** Migrar Redis para Upstash ou reduzir TTLs/Tamanho | DevOps | 24h |
| Supabase pool >42 | **Urgente:** Aumentar pool OU adicionar PgBouncer / read replica | DevOps | 12h |
| CPU >85% sostenido | **Urgente:** Adicionar mais workers OU 2o container Railway | DevOps | 12h |
| RSS memory >435MB | **Urgente:** Investigar leak (Prometheus `smartlic_process_memory_rss_bytes`) | Dev | 24h |
| Error rate >1.7% | **Urgente:** Post-mortem imediato | Dev + DevOps | 6h |

**Trigger Nivel 3 — Emergencial (95%):**

| Gatilho | Acao | Responsavel | SLA |
|---------|------|-------------|-----|
| Qualquer recurso >95% | **Emergencia:** Escalar Railway plano + recursos OU deploy de mitigacao | DevOps | 1h |
| OOM detectado | **Emergencia:** Aumentar memoria do container Railway (via plano) | DevOps | 30min |
| Erro generalizado (>5%) | **Emergencia:** Ativar modo degraded via feature flag | Dev + DevOps | 15min |
| Storage PostgreSQL >80% | **Emergencia:** Purgar dados antigos OU upgrade de plano | DevOps | 4h |

### 4.3 Monitoramento dos Triggers

**Como detectar automaticamente:**

| Metrica Prometheus | Gatilho | Alerta |
|-------------------|---------|--------|
| `smartlic_process_memory_rss_bytes` | >360MB (70%), >435MB (85%) | Sentry warning/critical |
| `smartlic_redis_available == 0` | Redis em fallback | Sentry error |
| `smartlic_supabase_pool_active_connections` | >35 (70%), >42 (85%) | Log high-water warning |
| `smartlic_route_timeout_total` | >7/hr (70%), >8.5/hr (85%) | Sentry warning/critical |
| `rate(smartlic_route_timeout_total[5m]) > 0.003` | Timeout rate alto | Prometheus alert |
| `smartlic_process_cpu_seconds_total` | 70-95% sostenido | Railway dashboard |
| `smartlic_rate_limit_hits_total` | >70% rate-limited | Log / admin dashboard |

**Lacuna de monitoramento:** Nao ha Prometheus AlertManager configurado atualmente (ver `docs/architecture/monitoring-setup.md` Secao 4.1). A deteccao destes triggers depende de monitoramento manual dos dashboards Railway + Sentry.

---

## 5. Railway Upgrade Path

### 5.1 Planos Railway (2026-06)

| Plano | Preco | RAM/Container | CPU | Features | Indicado Para |
|-------|-------|--------------|-----|----------|---------------|
| **Free** | Gratuito | 512MB | 1 vCPU (limitado) | $5 credit/mo, sleep apos 15min idle | Dev/Staging |
| **Starter** | $25/mo | 1GB | 1 vCPU | $25 credit/mo, sem sleep, 2 services | **ATUAL (suspeito)** |
| **Growth** | $50/mo | 2GB | 2 vCPU | $50 credit/mo, 10 services, metrics | Proximo upgrade |
| **Scale** | $100/mo | 4GB | 4 vCPU | $100 credit/mo, 25 services, teams | Escala media |
| **Enterprise** | Custom | Custom | Custom | Custom, SLA, support dedicado | Grande escala |

### 5.2 Upgrade Path Recomendado

**Nivel 0 — Atual (starter/growth):**
- Backend: ~1GB RAM, 1 container
- Redis: embarcado 128MB (gratuito mas limitado)
- Frontend: ~1GB RAM, 1 container
- Custo estimado: ~$50-100/mo (2 containers + credits)

**Nivel 1 — Proximo upgrade ($75-125/mo):**
- **Trigger:** Redis >90MB OU Supabase pool >35 OU usuarios simultaneos >20
- **Acoes:**
  1. Migrar Redis para Upstash (1GB free tier ou $5/mo) — elimina gargalo #1
  2. Aumentar `WEB_CONCURRENCY=3` (se memoria permitir)
  3. Aumentar `SUPABASE_POOL_MAX_CONNECTIONS` para 40-50
  4. Considerar Railway Growth ($50/mo) para 2GB RAM + 2 vCPU
- **Impacto esperado:** Suporta 10x sem degradacao severa

**Nivel 2 — Escala media ($150-300/mo):**
- **Trigger:** Usuarios simultaneos >100 OU storage >80%
- **Acoes:**
  1. Separar worker do backend (`WORKER_COLOCATED=false`) — 2 containers Railway
  2. Upgrade Railway Scale ($100/mo) para 4GB RAM + 4 vCPU no backend
  3. Upstash Redis Pro (~$15-30/mo) para 1-5GB
  4. Supabase Pro -> Team ($75/mo) para 8GB RAM + conexoes extras
  5. Adicionar segundo frontend container com load balancer Railway
  6. Configurar CDN (Cloudflare ~$20/mo ou similar) para ISR pages
- **Impacto esperado:** Suporta 100x com degradacao controlada

**Nivel 3 — Escala grande ($500+/mo):**
- **Trigger:** Usuarios simultaneos >500
- **Acoes:**
  1. Multi-container backend com Redis Cluster e cache distribuido
  2. Read replicas PostgreSQL (Supabase Team ou Enterprise)
  3. Filas ARQ dedicadas (worker pool separado)
  4. CDN full para SEO programmatic pages (10k+ pages)
  5. OpenAI Tier 2+ (higher rate limits)
  6. Railway Enterprise (custom pricing)
- **Impacto esperado:** Suporta 1000x

### 5.3 Custo por Usuario

Estimativa de custo de infraestrutura por usuario pago ativo:

| Nivel | Custo Mensal Infra | Usuarios Estimados | Custo/Usuario |
|-------|-------------------|-------------------|---------------|
| Atual (N0) | ~$50-100 | ~5-10 pagos | $10-20/user |
| Proximo (N1) | ~$100-200 | ~50-100 pagos | $2-4/user |
| Escala media (N2) | ~$200-400 | ~500-1000 pagos | $0.40-0.80/user |
| Escala grande (N3) | ~$500-2000 | ~5000+ pagos | $0.10-0.40/user |

Nota: Custo de LLM (OpenAI) e adicional — estimado em ~$0.50-2.00/1000 searches com GPT-4.1-nano.

---

## 6. Action Items

### Imediatos (proximos 30 dias)

| # | Acao | Justificativa | Esforco |
|---|------|---------------|---------|
| 1 | Monitorar `smartlic_process_memory_rss_bytes` e `smartlic_redis_fallback_duration_seconds` diariamente | Dados historicos para calibrar triggers | 2h |
| 2 | Criar alertas Sentry para memory >360MB e pool Supabase >35 | Deteccao precoce dos triggers N1 | 4h |
| 3 | Configurar UptimeRobot (gratuito) conforme `docs/architecture/monitoring-setup.md` Secao 5.1 | Monitoramento externo | 2h |
| 4 | Validar se Railway e Starter ou Growth — coletar metrica de memoria real | Base para upgrade path | 1h |

### Curto Prazo (60 dias)

| # | Acao | Justificativa | Esforco |
|---|------|---------------|---------|
| 5 | Migrar Redis para Upstash free tier (elimina gargalo #1) | Cache isolation, nao compete com worker por memoria | 1 dia |
| 6 | Aumentar `SUPABASE_POOL_MAX_CONNECTIONS=40` (validar com Supabase) | Headroom para 10x usuarios | 30min |
| 7 | Review do timeout budget: verificar se `PIPELINE_TIMEOUT=100` ainda faz sentido com route timeout=60 | A rota timeout de 60s corta antes do pipeline budget | 4h |
| 8 | Documentar resultado do k6 load test (#1968) no `load-test-2026-06.md` | Validar thresholds com dados reais | 4h |

### Medio Prazo (90 dias)

| # | Acao | Justificativa | Esforco |
|---|------|---------------|---------|
| 9 | Executar k6 load test (templates em `tests/load/`) e preencher resultados | Benchmark baselines para triggers | 2 dias |
| 10 | Decidir upgrade Railway Starter -> Growth ($25 -> $50/mo) se triggers N1 forem atingidos | Cabeca de ponte para 10x | 1 dia |
| 11 | Revisar e atualizar este documento com dados reais de uso | Ciclo de revisao trimestral | 4h |

---

## Apendice A: Referencias

| Documento | Conteudo |
|-----------|----------|
| `docs/architecture/monitoring-setup.md` | Stack de observabilidade, metricas Prometheus, alertas |
| `docs/architecture/load-test-2026-06.md` | Template de k6 load test (#1968) |
| `docs/architecture/error-budget-slo.md` | SLOs e error budget |
| `docs/architecture/graceful-degradation-matrix.md` | Matriz de degradacao graciosa |
| `backend/config/pncp.py` | Timeout chain, circuit breakers, bulkheads |
| `backend/config/pipeline.py` | Cache config, revalidation, concorrencia |
| `backend/config/features.py` | LLM config, trial, rate limits |
| `backend/redis_pool.py` | Pool sizes, fallback cache |
| `backend/supabase_client.py` | Conexoes Supabase, pool limits |
| `backend/rate_limiter.py` | Rate limits por plano e tipo |
| `backend/quota/quota_core.py` | Plan capabilities, quotas por plano |
| `railway.toml` (backend/frontend) | Railway config, healthcheck, deploy |

## Apendice B: Glossario

| Termo | Significado |
|-------|-------------|
| **Bulkhead** | Tecnica de isolamento de recursos para evitar que uma fonte de dados lenta degrade as demais |
| **CB** | Circuit Breaker — padrao de resiliencia que interrompe requisicoes apos N falhas consecutivas |
| **OOM** | Out Of Memory — processo morto pelo sistema operacional por exceder memoria |
| **SWR** | Stale-While-Revalidate — estrategia de cache que serve dados obsoletos enquanto revalida em background |
| **RSS** | Resident Set Size — memoria fisica real ocupada por um processo |
| **p95/p99** | Percentil 95/99 — 95%/99% das requisicoes completam dentro deste tempo |

---

*Documento gerado em 2026-06-17. Proxima revisao: 2026-09-17 (ciclo trimestral).*
