# Capacity Planning — SmartLic

> Projecoes de crescimento, limites do sistema e triggers de escala.
> Atualizado: 2026-06-15 | Issue: #1879

---

## 1. Capacidade Atual (Medida)

Dados obtidos de load testing (k6, #1796) e monitoramento de producao.

### 1.1 Throughput Maximo

| Metrica | Valor | Fonte |
|---------|-------|-------|
| Usuarios concorrentes | ~30 | p95 observado em producao |
| Requests/segundo sustentados | ~5 | k6 stress test (#1796) |
| Buscas ativas simultaneas | ~10-15 | `smartlic_active_searches` gauge |
| SSE connections simultaneas | ~50 | `smartlic_sse_connection_errors_total` |
| P95 latencia /buscar (carga baixa) | ~8s | k6 search load test |
| P95 latencia /buscar (30 usuarios) | ~15s | k6 stress test — limite aceitavel |
| Error rate em pico | <3% | k6 thresholds |

### 1.2 Limites de Infraestrutura

| Componente | Configuracao Atual | Limite Conhecido |
|------------|-------------------|-------------------|
| Gunicorn workers | 1 (WEB_CONCURRENCY=1) | ~30 usuarios concorrentes |
| ThreadPoolExecutor (LLM) | 10 (arbiter) + 3 (batch) + 5 (summary) | ~18 threads simultaneas |
| asyncio.Queue (SSE) | maxsize=500 eventos/tracker | ~50 trackers ativos |
| Redis (Upstash Free) | 256 MB, 500K commands/mes | 256 MB cache |
| Supabase (Free/Pro) | 500 MB / 8 GB DB | Conexoes ~15-25 ativas |
| Railway request timeout | ~120s (hard proxy limit) | N/A |

### 1.3 Load Testing Summary (#1796)

O script `tests/load/k6-stress-test.js` executa rampa de 10 a 500 VUs em 7 fases,
com sustencao prolongada para detectar memory leaks.

**Resultados conhecidos:**
- Single instance (1 web + 1 worker): ponto de saturacao em ~30 usuarios concorrentes
- Gargalo primario: ThreadPoolExecutor(10) para LLM calls + single Gunicorn worker
- Railway proxy timeout (~120s) corta searches que excedem budget de pipeline

> **Nota:** Resultados completos do k6 exigem execucao contra staging. Os valores acima
> sao extrapolacoes conservadoras baseadas na arquitetura e metricas de producao.

---

## 2. Projecoes de Crescimento

Premissas comportamentais (baseadas em analytics de beta e trials):
- Usuarios light (10%): ~3 searches/dia
- Usuarios typical (40%): ~1 search/dia
- Usuarios trial (50%): ~0.5 search/dia
- Pico de concorrencia: 20% dos usuarios ativos simultaneamente (horario comercial)

### 2.1 Tabela Consolidada

| Usuarios | Searches/mo | Pico conc. | Redis (MB) | Tier Infra | Custo $/mo | Gargalo Primario |
|----------|-------------|------------|------------|------------|------------|-------------------|
| **100** | 2.850 | 20 | 92.8 | Hobby/Pro Starter | $58 | Nenhum (dentro da capacidade) |
| **500** | 14.250 | 100 | 463.9 | Pro Single Instance | $119 | Gunicorn workers |
| **1.000** | 28.500 | 200 | 927.7 | Pro Multi Instance | $144 | Gunicorn workers |
| **5.000** | 142.500 | 1.000 | 4.638,7 | Enterprise Distributed | $304 | Gunicorn workers |

### 2.2 Detalhamento por Tier

#### 100 Usuarios Ativos

| Dimensao | Valor | Nota |
|----------|-------|------|
| Searches/dia | 95 | ~8 buscas/hora em horario comercial |
| Searches/mes | 2.850 | Bem abaixo do plano Pro |
| Pico concorrente | 20 | Dentro do limite de 30 usuarios |
| DB rows/mes | 1.425.000 | ~500 resultados por busca |
| Redis memory | 92.8 MB | 36% do free tier (256 MB) |
| Redis commands/mes | 34.200 | 6.8% do free tier (500K) |
| Custo Railway | $57.50/mo | Mesmo tier atual (inclui taxa Pro $20) |
| Custo Supabase | $0/mo | Free tier suficiente |
| Custo Redis | $0/mo | Free tier |
| Custo LLM (OpenAI) | $0.86/mo | ~$0.000303/search |
| **Custo Total** | **~$58/mo** | Sem custos variaveis significativos |

**Gargalo:** LLM ThreadPoolExecutor(10) — com 20 searches concorrentes, 10 threads de LLM
disputam recurso. P95 de busca pode subir para ~12s.

**Acao:** Monitorar `smartlic_llm_call_duration_seconds` e `smartlic_active_searches`.
Considerar aumentar `max_workers` no `filter_llm.py` para 15.

#### 500 Usuarios Ativos

| Dimensao | Valor |
|----------|-------|
| Searches/dia | 475 |
| Searches/mes | 14.250 |
| Pico concorrente | 100 |
| DB rows/mes | 7.125.000 |
| Redis memory | 463.9 MB |
| Redis commands/mes | 171.000 |
| Custo Railway | $90.00/mo |
| Custo Supabase | $25.00/mo (Pro) |
| Custo Redis | $0/mo (free tier) |
| Custo LLM | $4.32/mo |
| **Custo Total** | **~$119/mo** |

**Gargalo:** Gunicorn workers — 1 worker sustenta ~30 usuarios. Com 100 concorrentes,
precisa de WEB_CONCURRENCY=3-4.

**Acao:** Aumentar `WEB_CONCURRENCY` para 4. Necessario Redis para SSE progress sharing
(ja implementado). Atualizar Railway para instancia com 2GB RAM.

#### 1.000 Usuarios Ativos

| Dimensao | Valor |
|----------|-------|
| Searches/dia | 950 |
| Searches/mes | 28.500 |
| Pico concorrente | 200 |
| DB rows/mes | 14.250.000 |
| Redis memory | 927.7 MB |
| Redis commands/mes | 342.000 |
| Custo Railway | $110.00/mo |
| Custo Supabase | $25.00/mo (Pro) |
| Custo Redis | $0/mo (ainda free) |
| Custo LLM | $8.64/mo |
| **Custo Total** | **~$144/mo** |

**Gargalo:** Redis commands se aproximando de 70% do free tier (500K/mes). LLM
ThreadPoolExecutor precisa de 20+ threads.

**Acao:**
- Migrar para 2 instancias web load-balanceadas
- Redis Pub/Sub obrigatorio para SSE cross-worker
- Aumentar `REDIS_POOL_MAX` proporcional
- Considerar rate limiting por usuario mais agressivo

#### 5.000 Usuarios Ativos

| Dimensao | Valor |
|----------|-------|
| Searches/dia | 4.750 |
| Searches/mes | 142.500 |
| Pico concorrente | 1.000 |
| DB rows/mes | 71.250.000 |
| Redis memory | 4.638,7 MB |
| Redis commands/mes | 1.710.000 |
| Custo Railway | $230.00/mo |
| Custo Supabase | $28.25/mo (Pro + overage) |
| Custo Redis | $2.42/mo (pay-as-you-go) |
| Custo LLM | $43.18/mo |
| **Custo Total** | **~$304/mo** |

**Gargalo:** Redis memory (175 MB / 256 MB free tier = 68%). Railway compute precisa
de 3+ web instances.

**Acao:**
- Migrar para cluster de 3+ instancias web
- Redis cluster ou Upstash Pro
- Supabase PgBouncer para pool de conexoes
- Filas de LLM batch processing
- CDN para assets estaticos do frontend

---

## 3. Gargalo Primario

### 3.1 Identificacao

O gargalo primario do sistema na configuracao atual e:

**ThreadPoolExecutor para LLM calls + single Gunicorn worker**

Cada busca pode spawnar ate 10 threads para classificacao LLM (arbiter + zero-match).
Com 10 searches simultaneas, sao 100 threads disputando:
- CPU (cada thread faz chamada HTTP para OpenAI)
- Conexoes de rede (httpx connection pool)
- Memoria (cada thread mantem contexto do prompt)

Alem disso, o single Gunicorn worker (WEB_CONCURRENCY=1) limita o throughput a ~30
usuarios concorrentes, pois todas as requisicoes passam por um unico processo.

### 3.2 Segundo Gargalo (proximo da escala)

| Escala | Segundo Gargalo | Threshold |
|--------|----------------|-----------|
| 100 usuarios | LLM thread contention | >15 searches ativas simultaneas |
| 500 usuarios | Gunicorn worker limit | >30 concorrentes por worker |
| 1.000 usuarios | Redis command quota | >400K commands/mes |
| 5.000 usuarios | Redis memory limit | >200 MB cache |

### 3.3 Custos Marginais por Componente

Componente com maior impacto incremental no custo conforme a base cresce:

| Componente | Custo/100 users add | Elasticidade |
|------------|--------------------|--------------|
| Railway compute | $8-15/mo | Step (precisa nova instancia) |
| Supabase | $0-5/mo | Quase fixo ate 8GB DB |
| Redis | $0-1/mo | Quase fixo ate 500K cmd/mes |
| LLM (OpenAI) | $0.55/mo | Linear (mais barato) |

**Conclusao:** O custo escala predominantemente em **steps discretos** de Railway
compute, nao linearmente. Adicionar 100 usuarios custa ~$9/mo marginal.

---

## 4. Custos Projetados por Tier de Crescimento

### 4.1 Tabela de Custos

| Usuarios | Railway | Supabase | Redis | LLM | Outros | **Total $/mo** | **Total R$/mo** |
|----------|---------|----------|-------|-----|--------|---------------|-----------------|
| **100** | $57.50 | $0.00 | $0 | $0.86 | $1 | **$58.36** | **R$ 338** |
| **500** | $90.00 | $25.00 | $0 | $4.32 | $1 | **$119.32** | **R$ 692** |
| **1.000** | $110.00 | $25.00 | $0 | $8.64 | $1 | **$143.64** | **R$ 833** |
| **5.000** | $230.00 | $28.25 | $2.42 | $43.18 | $1 | **$303.85** | **R$ 1.762** |

> **Nota 1:** Valores em R$ usam cambio USD 1 = BRL 5.80.
> **Nota 2:** Supabase Free tier ($0) para 100 usuarios. Pro ($25/mo) para 500+. Overage para 5.000.
> **Nota 3:** "Outros" inclui dominio ($1/mo). Sentry, Mixpanel, Resend permanecem free.

### 4.2 Custo por Usuario (diminui com escala)

| Usuarios | Custo total/mes | Custo/usuario/mes |
|----------|----------------|-------------------|
| 100 | $58 | **$0.58** |
| 500 | $119 | **$0.24** |
| 1.000 | $144 | **$0.14** |
| 5.000 | $304 | **$0.06** |

### 4.3 Projecao de Margem (assumindo SmartLic Pro R$397/mes)

| Usuarios pagantes | Receita/mes | Custo/mes | Lucro/mes | Margem |
|-------------------|-------------|-----------|-----------|--------|
| 10 | R$ 3.970 | R$ 338 | R$ 3.632 | **91.5%** |
| 50 | R$ 19.850 | R$ 692 | R$ 19.158 | **96.5%** |
| 100 | R$ 39.700 | R$ 833 | R$ 38.867 | **97.9%** |
| 500 | R$ 198.500 | R$ 1.762 | R$ 196.738 | **99.1%** |

> **Conclusao:** Margem melhora com escala porque custo fixo de infraestrutura
> domina o total. O custo marginal por usuario adicional e baixissimo (~$0.05-0.64).

---

## 5. Triggers de Escala

Documentacao dos limites que disparam acoes de scaling. Organizado por recurso.

### 5.1 Gunicorn Workers — WEB_CONCURRENCY

| Gatilho | Acao | Prioridade |
|---------|------|------------|
| `active_searches` > 8 por mais de 5 min | Aumentar WEB_CONCURRENCY para 2 | Media |
| `active_searches` > 15 por mais de 2 min | Aumentar WEB_CONCURRENCY para 3-4 | Alta |
| `process_cpu_usage` > 80% por 2 min | Adicionar segunda instancia web | Alta |
| `process_memory_rss` > 70% do limite RAM | Aumentar RAM da instancia Railway | Media |

**Como escalar:**
```bash
# Railway: set env var + redeploy
railway variables set WEB_CONCURRENCY=4
# Ou no railway.toml:
# [variables] WEB_CONCURRENCY=4
```

### 5.2 LLM ThreadPoolExecutor

| Gatilho | Acao | Prioridade |
|---------|------|------------|
| `llm_call_duration_seconds` p99 > 5s | Aumentar max_workers para 15 | Baixa |
| `search_duration_seconds` p99 > 30s | Implementar LLM batching | Media |
| `llm_batch_timeout_total` > 5/min | Reduzir MAX_ZERO_MATCH_ITEMS | Alta |
| LLM calls/sec > 50 | Rate limit por usuario mais agressivo | Media |

### 5.3 Redis

| Gatilho | Acao | Prioridade |
|---------|------|------------|
| `redis_pool_connections_used` > 80% do max | Aumentar REDIS_POOL_MAX | Media |
| Cache hit rate < 60% | Aumentar TTL ou warming | Baixa |
| Redis memory usage > 200 MB (80% free) | Migrar para Upstash paid tier | Media |
| Redis commands/month > 400K (80% free) | Atualizar para pay-as-you-go | Alta |
| Redis connection errors > 1/min | Verificar pool sizing | Alta |

### 5.4 Supabase

| Gatilho | Acao | Prioridade |
|---------|------|------------|
| `supabase_pool_active_connections` > 20 | Ativar PgBouncer connection pooler | Alta |
| DB storage > 6 GB (75% Pro) | Limpar cache stale ou aumentar storage | Media |
| Query p99 > 500ms | Revisar indices e queries lentas | Media |
| RLS policy evaluation > 100ms | Otimizar policies | Baixa |

### 5.5 Railway Compute

| Gatilho | Acao | Prioridade |
|---------|------|------------|
| CPU > 80% sustained (5 min) | Upgrade para Pro ($20/mo) com mais vCPU | Alta |
| RAM > 75% sustained (5 min) | Upgrade RAM (512MB → 2GB) | Alta |
| Erro 502/503 rate > 1% | Verificar timeout config, adicionar instancia | Critica |
| Request p99 > Railway timeout (100s) | Otimizar pipeline ou fracionar busca | Critica |

### 5.6 Matriz Resumo de Triggers

| Quando X atinge Y% | Escalar Z | Prioridade |
|--------------------|-----------|------------|
| `active_searches` > 15 | WEB_CONCURRENCY 3-4 | Alta |
| `process_cpu_usage` > 80% | + instancia web | Alta |
| `process_memory_rss` > 75% | + RAM Railway | Media |
| Redis memory > 80% free (200MB) | Upstash paid tier | Media |
| Redis commands > 80% free (400K/mes) | Redis pay-as-you-go | Alta |
| Supabase connections > 20 | PgBouncer | Alta |
| DB storage > 75% Pro (6GB) | Cleanup ou +storage | Media |
| Erro 502/503 > 1% das requests | Instancia extra | Critica |
| Request p99 > 100s | Otimizar pipeline | Critica |

---

## 6. Recomendacoes e Roadmap de Escala

### 6.1 Proximo Passo Imediato (0-30 dias)

Trigger esperado: **50-100 usuarios ativos** (pre-revenue / trials pagos).

- [ ] Aumentar `WEB_CONCURRENCY` para 2 (suporta ~60 usuarios)
- [ ] Configurar alerta Prometheus para `active_searches` > 8
- [ ] Validar Redis SSE progress em staging (ja implementado STORY-294)
- [ ] Executar k6 load test com 2 workers para confirmar throughput

### 6.2 Proximo Salto (30-90 dias)

Trigger esperado: **100-500 usuarios ativos** (pos-lancamento).

- [ ] WEB_CONCURRENCY=4 com 2GB RAM Railway
- [ ] Supabase Free → Pro ($25/mo)
- [ ] Monitorar `smartlic_redis_pool_connections_used` (pode precisar aumentar pool)
- [ ] Implementar LLM batch queue se p95 de busca > 20s

### 6.3 Escala Media (90-180 dias)

Trigger esperado: **500-1.000 usuarios ativos**.

- [ ] Segunda instancia web Railway (load-balanced)
- [ ] Redis Pub/Sub obrigatorio para SSE cross-instance
- [ ] Redis pay-as-you-go (Upstash) se commands > 400K/mes
- [ ] Supabase PgBouncer se conexoes > 20 ativas
- [ ] Rate limiting mais granular por usuario

### 6.4 Escala Grande (180+ dias)

Trigger esperado: **1.000-5.000 usuarios ativos**.

- [ ] 3+ instancias web com auto-scaling
- [ ] Redis cluster ou Upstash Pro
- [ ] Supabase read replicas
- [ ] LLM batch processing queue dedicada
- [ ] CDN para frontend (Vercel/Railway)
- [ ] Full observability (Grafana Cloud)

### 6.5 Custo Acumulado Projetado

| Mes | Usuarios | Custo/mes | Custo acumulado (12m) |
|-----|----------|-----------|----------------------|
| 1-3 | 100 | ~$58/mo | ~$174 |
| 4-6 | 500 | ~$119/mo | ~$357 |
| 7-9 | 1.000 | ~$144/mo | ~$432 |
| 10-12 | 2.000 | ~$200/mo | ~$600 |
| **12 meses** | | | **~$1.563** |

---

## 7. Ferramentas de Calculo

### 7.1 Script de Estimativa

```bash
# Projecoes para 100, 500, 1000, 5000 usuarios
python scripts/estimate-capacity.py

# Projecao para numero especifico
python scripts/estimate-capacity.py --users 250

# Saida JSON (para pipe em dashboards)
python scripts/estimate-capacity.py --json

# Apenas bottleneck
python scripts/estimate-capacity.py --bottleneck
```

### 7.2 Load Testing (k6)

```bash
# Stress test completo (7 fases, 10→500 VUs)
k6 run tests/load/k6-stress-test.js

# Load test de busca
k6 run tests/load/buscar.k6.js --env BACKEND_URL=https://staging.smartlic.tech

# Smoke test (rapido, verifica baseline)
k6 run tests/load/buscar.k6.js --env SMOKE=1 --vus 1 --duration 10s
```

---

## 8. Documentos Relacionados

| Documento | Conteudo | 
|-----------|----------|
| `docs/operations/capacity-limits.md` | Limites de capacidade, gargalos conhecidos e plano de escala (DEBT-129) |
| `docs/operations/cost-analysis.md` | Analise de custos operacionais detalhada (GTM-GO-004) |
| `docs/operations/monitoring.md` | Monitores de uptime, alert rules e metricas Prometheus |
| `docs/operations/alerting-runbook.md` | Runbooks de resposta para cada alerta |
| `scripts/estimate-capacity.py` | Script de calculo de projecoes (#1879) |
| `tests/load/k6-stress-test.js` | Stress test k6 com 7 fases (#1796) |
| `tests/load/buscar.k6.js` | Load test para endpoint /buscar (#1796) |

---

## 9. Historico de Alteracoes

| Data | Alteracao | Autor |
|------|-----------|-------|
| 2026-06-15 | Documento criado com projecoes 100-5K usuarios, triggers de escala e custos | #1879 |

---

*Projecoes baseadas em load testing (k6 #1796), metricas de producao e modelo de
custos validado em docs/operations/cost-analysis.md. Atualizar quando houver dados
reais de billing ou resultados de novo load test.*
