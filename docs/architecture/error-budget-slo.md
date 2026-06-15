# Error Budget e SLO — SmartLic

**Versao:** 1.0
**Criado:** 2026-06-15
**Owner:** @devops
**Issue:** #1802

---

## Sumario

1. [Service Level Objectives (SLOs)](#1-service-level-objectives-slos)
2. [Service Level Indicators (SLIs)](#2-service-level-indicators-slis)
3. [Error Budget Mensal](#3-error-budget-mensal)
4. [Como Medir](#4-como-medir)
5. [Politica de Esgotamento do Error Budget](#5-politica-de-esgotamento-do-error-budget)
6. [Grafana Dashboard Recomendado](#6-grafana-dashboard-recomendado)
7. [Referencias](#7-referencias)

---

## 1. Service Level Objectives (SLOs)

### SLOs Atuais

| SLO | Alvo | Meta | Janela de Medicao | Prioridade |
|-----|------|------|--------------------|------------|
| **Uptime da API** | 99.5% | Max 3.6h de downtime/mes | Rolling 30 dias | P0 |
| **Latencia de Busca (p95)** | < 500 ms | 95% das buscas completam em < 500 ms | Rolling 7 dias | P0 |
| **Latencia DataLake (p95)** | < 100 ms | 95% das queries DataLake em < 100 ms | Rolling 7 dias | P0 |
| **Error Rate (HTTP 5xx)** | < 1% | Menos de 1% das requests retornam 5xx | Rolling 7 dias | P0 |
| **Latencia de Fetch por Fonte (p95)** | < 10 s | 95% das chamadas a fontes externas em < 10 s | Rolling 7 dias | P1 |
| **Disponibilidade LLM** | > 98% | Mais de 98% das chamadas LLM bem-sucedidas | Rolling 30 dias | P1 |
| **Cache Hit Ratio (L1)** | > 60% | 60%+ das buscas servidas de cache L1 | Rolling 7 dias | P2 |

### SLOs As-Pirated (futuros)

| SLO | Alvo | Notas |
|-----|------|-------|
| **MTTR (Mean Time to Resolve)** | < 30 min para SEV1 | Acompanhar apos cada incidente SEV1 |
| **Stripe Webhook Success Rate** | > 99.9% | Atualmente nao medido como SLI separado |
| **Frontend LCP (p75)** | < 2.5 s | Medido via GA4 Web Vitals, nao vinculado a error budget |

---

## 2. Service Level Indicators (SLIs)

Cada SLO e medido por um ou mais SLIs. Abaixo a definicao de cada SLI e a metrica Prometheus correspondente.

### 2.1 SLI: Uptime da API

**Definicao:** Percentual de tempo em que o endpoint `/health/live` retorna HTTP 200.

**Formula:**
```
uptime_30d = 100 * (1 - (minutos_de_downtime_30d / 43200))
```

**Metrica Prometheus:**
```
smartlic_uptime_pct_30d
```
Gauge atualizado periodicamente pelo health canary.

**Fonte alternativa:** UptimeRobot / BetterStack external probes com check a cada 1 min.

### 2.2 SLI: Latencia de Busca (p95)

**Definicao:** Percentil 95 da duracao total do pipeline de busca, do recebimento da request ate o retorno dos resultados.

**Metrica Prometheus:**
```
smartlic_search_duration_seconds
```
Histograma com buckets [1, 2, 5, 10, 20, 30, 60, 120, 300].

**Labels:** `sector`, `uf_count`, `cache_status`.

**Origem:** `backend/metrics.py::SEARCH_DURATION`.

### 2.3 SLI: Latencia DataLake (p95)

**Definicao:** Percentil 95 das queries RPC ao DataLake (`search_datalake`).

**Metrica Prometheus:**
```
smartlic_supabase_execute_duration_seconds
```
Histograma com buckets [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5].

### 2.4 SLI: Error Rate (HTTP 5xx)

**Definicao:** Proporcao de respostas HTTP com status 5xx em relacao ao total de respostas.

**Formula:**
```
error_rate = rate(smartlic_http_responses_total{status_class="5xx"}[5m]) / rate(smartlic_http_responses_total[5m])
```

**Metrica Prometheus:**
```
smartlic_http_responses_total
```
Counter com labels `status_class` (2xx, 4xx, 5xx, redirect) e `method`.

### 2.5 SLI: Latencia de Fetch por Fonte

**Definicao:** Percentil 95 do tempo de busca em cada fonte externa (PNCP, PCP v2, ComprasGov v3).

**Metrica Prometheus:**
```
smartlic_fetch_duration_seconds
```
Histograma com labels `source`.

### 2.6 SLI: Disponibilidade LLM

**Definicao:** Proporcao de chamadas LLM (classificacao + resumos) que retornaram sucesso vs. erro.

**Metricas Prometheus:**
```
smartlic_llm_calls_total{decision!="error"}
smartlic_llm_calls_total{decision="error"}
```

### 2.7 SLI: Cache Hit Ratio (L1)

**Definicao:** Proporcao de buscas servidas pelo cache L1 (Redis ou InMemory) sem necessidade de fetched ao DataLake ou fontes externas.

**Metrica Prometheus:**
```
rate(smartlic_cache_hits_total{level="l1"}[7d]) / (rate(smartlic_cache_hits_total{level="l1"}[7d]) + rate(smartlic_cache_misses_total{level="l1"}[7d]))
```

---

## 3. Error Budget Mensal

### Calculo

Error budget = (1 - SLO) * total_de_minutos_no_mes

| SLO | Alvo | Downtime Permitido / mes | Error Budget (min) |
|-----|------|--------------------------|--------------------|
| Uptime API | 99.5% | 3.6 h / mes | 216 min |
| Error Rate | < 1% | 1% das requests | Proporcional ao volume |
| Latencia Busca (p95) | < 500 ms | 5% podem exceder 500 ms | 5% das buscas |
| Latencia DataLake (p95) | < 100 ms | 5% podem exceder 100 ms | 5% das queries |
| Disponibilidade LLM | > 98% | 2% das chamadas LLM | 2% do total |

### Tabela de Error Budget (Uptime)

| Periodo | Downtime Max (99.5%) | Error Budget Total |
|---------|----------------------|--------------------|
| Dia | ~7.2 min | 7.2 min |
| Semana | ~50.4 min | 50.4 min |
| Mes (30d) | 3.6 h | 216 min |
| Trimestre | 10.8 h | 648 min |

### Consumo Tipico de Error Budget (historico)

| Mes | Downtime Estimado | Error Budget Consumido | Observacao |
|-----|-------------------|------------------------|------------|
| 2026-04 | ~120 min | 55% do mes | CRIT-080/083/084, outage de 3 dias |
| 2026-05 | ~30 min | 14% do mes | Estabilizacao pos-RES-BE |
| 2026-06 (YTD) | ~15 min | 7% do mes | Operacao normal |

---

## 4. Como Medir

### 4.1 Prometheus Metrics (automatico)

O backend exporta todas as metricas em `/metrics` no formato Prometheus text exposition format.

```bash
# Verificar metricas raw
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_'

# Verificar metricas de interesse para SLO
curl -s https://api.smartlic.tech/metrics | grep -E 'smartlic_(http_responses|search_duration|uptime|llm_calls|cache_hits|supabase_execute)'
```

### 4.2 Health Endpoint (para uptime)

```bash
# Liveness
curl -s -o /dev/null -w "%{http_code}" https://api.smartlic.tech/health/live

# Readiness (com wedge_risk e checks de dependencias)
curl -s https://api.smartlic.tech/health/ready | jq .
```

### 4.3 Grafana (via Prometheus scraping)

Se Grafana estiver configurado para scrapar o `/metrics` endpoint do backend, use as seguintes queries PromQL para cada SLO:

**Uptime:**
```promql
# Gauge direto
smartlic_uptime_pct_30d
```

**Error Rate:**
```promql
# Error rate (%) nos ultimos 5 min
sum(rate(smartlic_http_responses_total{status_class="5xx"}[5m])) / sum(rate(smartlic_http_responses_total[5m])) * 100
```

**Latencia Busca p95:**
```promql
# p95 da duracao do pipeline
histogram_quantile(0.95, sum(rate(smartlic_search_duration_seconds_bucket[7d])) by (le))
```

**Latencia DataLake p95:**
```promql
histogram_quantile(0.95, sum(rate(smartlic_supabase_execute_duration_seconds_bucket[7d])) by (le))
```

**Cache Hit Ratio (L1):**
```promql
# Cache hit ratio
sum(rate(smartlic_cache_hits_total{level="l1"}[7d])) / (sum(rate(smartlic_cache_hits_total{level="l1"}[7d])) + sum(rate(smartlic_cache_misses_total{level="l1"}[7d]))) * 100
```

**LLM Error Rate:**
```promql
# LLM error rate (%)
sum(rate(smartlic_llm_calls_total{decision="error"}[7d])) / sum(rate(smartlic_llm_calls_total[7d])) * 100
```

### 4.4 Sentry Alerts (complementar)

Os SLIs de error rate e pipeline wedge sao monitorados via Sentry Metric Alerts:

| Alerta Sentry | Condicao | SLI Relacionado |
|---------------|----------|-----------------|
| Pipeline Wedge | `smartlic_pipeline_budget_exceeded_total` > 2/5min | Error rate (indireto) |
| High Error Rate | HTTP 5xx > 10/min | Error rate |
| DB Pool Saturation | Redis pool > 80% | Uptime (risco de wedge) |
| Route Timeout | `smartlic_route_timeout_total` > 10/h | Error rate + Latencia |

### 4.5 External Probes

UptimeRobot e BetterStack monitoram `/health/live` de fora da rede Railway, garantindo que o SLI de uptime reflita a experiencia real do usuario (nao apenas health checks internos).

---

## 5. Politica de Esgotamento do Error Budget

### 5.1 Zonas do Error Budget

| Zona | Consumo | Acao |
|------|---------|------|
| **Verde** | 0-70% do budget | Operacao normal. Deploys liberados. |
| **Amarelo** | 70-90% do budget | Warning. Reforcar revisao de PRs. Feature flags para mudancas arriscadas. |
| **Vermelho** | 90-100% do budget | **Freeze de deploys**. Apenas hotfixes de SEV1/SEV2 permitidos. |
| **Excedido** | > 100% | **Freeze total.** Rollback de mudancas recentes se necessario. Post-mortem obrigatorio. |

### 5.2 Acoes por Zona

#### Verde (0-70%)

- Deploys normais liberados
- Features podem ser enviadas
- Monitoring continua normal

#### Amarelo (70-90%)

- Todas as PRs devem passar por code review adicional (`@architect` obrigatorio)
- Mudancas de alto risco (mudanca de infra, alteracao de pipeline, release de nova feature) feature-flag gateadas
- Investigar causa raiz do consumo acelerado
- Aumentar frequencia de verificacao de metricas (cada 30 min)

#### Vermelho (90-100%)

- **Freeze de deploys** — apenas hotfixes para incidentes SEV1/SEV2
- Toda mudanca precisa ser aprovada por `@devops` + `@architect`
- Time dedicado a resolver a causa do consumo
- Reuniao diaria de status do error budget
- Se aplicavel: ativar modo de degradacao (desabilitar funcionalidades nao-criticas)

#### Excedido (> 100%)

- **Freeze total** — nenhum deploy, nem hotfix, sem aprovacao do time completo
- Rollback de mudancas recentes que possam ter contribuido
- Post-mortem obrigatorio com analise de causa raiz
- Plano de acao para recuperar confiabilidade antes de novos deploys
- Notificar stakeholders (PM, founding team)

### 5.3 Recuperacao

Para sair da zona vermelha ou excedida:

1. Identificar e corrigir a causa raiz do consumo de error budget
2. Implementar medidas preventivas (testes, CI gates, monitoring)
3. Validar que as correcoes estao funcionando (observar error budget estabilizar)
4. Apresentar post-mortem e plano de acao para @pm + @architect
5. Retornar gradualmente a deploys normais (primeiro mudancas de baixo risco)

### 5.4 Excecoes

- **Hotfixes de seguranca** (vulnerabilidade critica) — permitidos em qualquer zona, mediante aprovacao de @devops
- **Rollback** — sempre permitido (restaura estabilidade)
- **Mudancas em monitoring/docs/CI** — nao consomem error budget, liberadas sempre

---

## 6. Grafana Dashboard Recomendado

### Painel: "SmartLic SLO Dashboard"

Este painel consolidaria todos os SLIs e o estado do error budget em uma unica visualizacao. Abaixo a configuracao recomendada para criacao no Grafana.

### Linha 1: Visao Geral (4 singlestat panels)

| Painel | Metrica | Thresholds |
|--------|---------|------------|
| **Uptime 30d** | `smartlic_uptime_pct_30d` | Verde: >= 99.5, Amarelo: >= 99.0, Vermelho: < 99.0 |
| **Error Budget Restante** | Calculado: `216 - minutos_de_downtime_no_mes` | Verde: > 151 (70%), Amarelo: > 22 (90%), Vermelho: <= 22 |
| **Error Rate (5m)** | `sum(rate(...5xx...))/sum(rate(...total...))` | Verde: < 1%, Amarelo: < 5%, Vermelho: >= 5% |
| **Cache Hit Ratio (L1)** | `rate(cache_hits_l1)/rate(cache_hits_l1+misses_l1)` | Verde: > 60%, Amarelo: > 40%, Vermelho: <= 40% |

### Linha 2: Latencia (2 time series panels)

**Busca p95:**
```promql
histogram_quantile(0.95, sum(rate(smartlic_search_duration_seconds_bucket[7d])) by (le))
```
- Linha horizontal de referencia (threshold): 0.5s (500 ms)

**DataLake p95:**
```promql
histogram_quantile(0.95, sum(rate(smartlic_supabase_execute_duration_seconds_bucket[7d])) by (le))
```
- Linha horizontal de referencia: 0.1s (100 ms)

### Linha 3: Distribuicao de Erros (1 stacked bar chart)

```promql
# 5xx por endpoint (top 10)
sum by (route) (rate(smartlic_route_timeout_total[1d]))
```

### Linha 4: Detalhamento do Error Budget (1 time series panel)

**Consumo Acumulado no Mes:**
```promql
# Minutos de downtime acumulados no mes (requer recording rule ou gauge externo)
smartlic_error_budget_consumed_minutes
```

### Como criar (passo a passo)

1. Adicionar datasource Prometheus apontando para o `/metrics` endpoint do backend
2. Criar nova dashboard: "SmartLic SLO Dashboard"
3. Adicionar panels conforme as queries acima
4. Configurar alertas no Grafana para:
   - `Uptime < 99.5%` -> Warning
   - `Error Budget < 30%` -> Warning
   - `Error Budget = 0` -> Critical

### Recording Rules Recomendadas (Prometheus)

Para simplificar as queries e reduzir custo de computacao, configure estas recording rules no Prometheus server:

```yaml
groups:
  - name: smartlic_slo_recording_rules
    interval: 5m
    rules:
      - record: smartlic:error_rate_5m
        expr: |
          sum(rate(smartlic_http_responses_total{status_class="5xx"}[5m]))
          / sum(rate(smartlic_http_responses_total[5m]))
      - record: smartlic:search_p95_latency_7d
        expr: |
          histogram_quantile(0.95,
            sum(rate(smartlic_search_duration_seconds_bucket[7d])) by (le))
      - record: smartlic:datalake_p95_latency_7d
        expr: |
          histogram_quantile(0.95,
            sum(rate(smartlic_supabase_execute_duration_seconds_bucket[7d])) by (le))
      - record: smartlic:cache_hit_ratio_7d
        expr: |
          sum(rate(smartlic_cache_hits_total{level="l1"}[7d]))
          / (sum(rate(smartlic_cache_hits_total{level="l1"}[7d]))
          + sum(rate(smartlic_cache_misses_total{level="l1"}[7d])))
```

---

## 7. Referencias

| Documento | Caminho |
|-----------|---------|
| Incident Response Runbook | `docs/runbooks/incident-response.md` |
| Monitoring & Alerting Setup | `docs/runbooks/monitoring-alerting-setup.md` |
| Backend Metrics Definitions | `backend/metrics.py` |
| Health Endpoints | `backend/health.py`, `backend/health_core.py` |
| SLO Admin Endpoint | `backend/routes/slo.py`, `GET /v1/admin/slo/dashboard` |
| Web Vitals (Frontend) | `docs/observability/web-vitals.md` |
| Critical Implementation Notes | `.claude/rules/critical-impl-notes.md` |
| Architecture Patterns | `.claude/rules/architecture-patterns.md` |

---

**Versao:** 1.0
**Criado:** 2026-06-15
**Owner:** @devops
**Proxima revisao:** 2026-07-15 ou apos primeiro esgotamento de error budget
