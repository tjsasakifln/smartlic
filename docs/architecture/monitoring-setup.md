# Monitoramento e Alerting de Downtime (#1786)

## 1. Stack Atual de Observabilidade

O SmartLic utiliza tres camadas de observabilidade, cada uma com proposito distinto:

| Camada | Tecnologia | Proposito |
|--------|-----------|-----------|
| **Metricas** | Prometheus (`prometheus_client`) | Contadores, histogramas, gauges para performance e saturacao |
| **Tracing** | OpenTelemetry | Rastreamento distribuido de requisicoes entre componentes |
| **Erros** | Sentry | Captura de excecoes, erros de aplicacao, performance de transacoes |

### 1.1 Prometheus — Metricas

**Implementacao:** `backend/metrics.py` define ~200+ metricas entre counters, histograms e gauges.

**Exposicao:** Endpoint `/metrics` montado como ASGI app (via `make_asgi_app()`). Protegido por `METRICS_TOKEN` via query parameter ou header. Desligavel via `METRICS_ENABLED=false`.

**Principais categorias de metricas:**

| Categoria | Exemplos | Labels |
|-----------|----------|--------|
| Performance de busca | `smartlic_search_duration_seconds`, `smartlic_fetch_duration_seconds`, `smartlic_llm_call_duration_seconds` | sector, source, cache_status |
| Cache | `smartlic_cache_hits_total`, `smartlic_cache_misses_total`, `smartlic_l1_cache_hits_total` | level, freshness, backend |
| LLM | `smartlic_llm_calls_total`, `smartlic_llm_tokens_total`, `smartlic_llm_cost_brl_total` | model, decision, zone, call_type |
| Erros de API | `smartlic_api_errors_total` | source, error_type |
| Circuit breaker | `smartlic_circuit_breaker_degraded`, `smartlic_circuit_breaker_trips_total` | source, cb_type |
| Pipeline | `smartlic_pipeline_budget_exceeded_total`, `smartlic_pipeline_duration_seconds` | phase, source |
| Rate limit | `smartlic_rate_limit_exceeded_total`, `smartlic_rate_limit_hits_total` | endpoint, limit_type |
| Pool de conexoes | `smartlic_supabase_pool_active_connections`, `smartlic_redis_pool_connections_used`, `smartlic_redis_pool_connections_max` | — |
| Saturacao | `smartlic_redis_fallback_duration_seconds`, `smartlic_process_memory_rss_bytes` | — |
| Health canary | `smartlic_health_canary_status`, `smartlic_health_canary_duration_seconds`, `smartlic_uptime_pct_30d` | — |

**Feature flag:** `METRICS_ENABLED=true` (default). Quando desligado ou sem `prometheus_client` instalado, todas as operacoes se tornam no-ops silenciosos.

### 1.2 Sentry — Erros

**Configuracao:** SDK `sentry_sdk` configurado no startup com `SentryStarletteIntegration`. Integracoes com `LoggingIntegration` e `AioHttpIntegration`.

**Eventos capturados:**
- Excecoes nao tratadas em rotas (automatico)
- `capture_message` manual para incidentes de saude (ex: `cron_monitoring_job`, `detect_incident`)
- Performance tracing (transactions)
- PNCP breaking-change canary alertas via Sentry (fingerprint `["pncp_canary", reason]`)
- Timeout budget exceeded (`smartlic_route_timeout_total > 10/hr`)

### 1.3 OpenTelemetry — Tracing

**Status:** `is_tracing_enabled()` retorna true/false conforme configuracao de ambiente. Tracing habilitado em producao.

**Escopo:** Rastreamento de requisicoes HTTP entre backend, Supabase e APIs externas.

## 2. Health Check Endpoints

O sistema possui dois endpoints de health check montados em nivel raiz (fora do `/v1/`) para compatibilidade com probes de container e balanceadores.

### 2.1 `/health/live` — Liveness Probe

**Localizacao:** `backend/routes/health_core.py::health_live()`

**Comportamento:** Sempre retorna HTTP 200 em <10ms. Nao verifica dependencias externas. Resposta minima:

```json
{
  "live": true,
  "ready": false,
  "uptime_seconds": 0.0,
  "process_uptime_seconds": 0.0
}
```

**Uso:** Indicador de que o processo esta vivo (nao travado / OOM-killed). Nao reflete capacidade de servir requisicoes.

### 2.2 `/health/ready` — Readiness Probe

**Localizacao:** `backend/routes/health_core.py::health_ready()`

**Comportamento:** Verifica dependencias em paralelo com timeouts individuais (HARDEN-016, #1790):

| Check | Timeout | Impacto |
|-------|---------|---------|
| Supabase (SELECT 1) | 2s | **unhealthy** se falhar — dependencia critica |
| Redis (PING) | 500ms | **degraded** se falhar — fail-open |
| Pool Supabase (>85% uso) | 500ms | **degraded** se >85% |
| Cache hit rate | 500ms | **degraded** se <50% |

**Logica de status:**
- `healthy` — todas as dependencias ok
- `degraded` — Redis down, pool >85%, ou hit rate <50%
- `unhealthy` — Supabase down (retorna HTTP 503)

**Aposreat shutdown (DEBT-124 AC6):** Retorna 503 com `shutting_down: true` durante drenagem.

**Wedge risk (#640):** O endpoint inclui campo `wedge_risk` (low/medium/high/unknown) calculado a partir de saturacao do pool Redis e timeouts recentes.

### 2.3 `/health` — Comprehensive Health

**Localizacao:** `backend/routes/health_core.py::health()`

**Retorna:** Status detalhado de todas as dependencias, circuit breakers, bulkheads, ARQ queue, Redis metrics, e tracing status.

### 2.4 `/sources/health` — Data Sources Health

**Localizacao:** `backend/routes/health_core.py::sources_health()`

**Retorna:** Status individual de cada fonte de dados configurada (PNCP, Portal, ComprasGov) com latencia e disponibilidade.

## 3. O Que Esta Sendo Monitorado

### 3.1 Monitoramento Ativo

| O que | Como | Frequencia | Resposta |
|-------|------|-----------|----------|
| Health canary | ARQ cron (`health_canary_job`) executa `get_system_health()` | 5 min | Salva em `health_checks`, detecta incidentes, email admin |
| PNCP breaking-change canary | ARQ cron (`pncp_canary_job`) | 10 min | Sentry alert + metricas Prometheus |
| pg_cron monitor | ARQ cron (`cron_monitoring_job`) | 1h | Sentry alerta se job falhou ou >25h parado |
| Health checks historico | `save_health_check()` apos cada canary run | 5 min | Tabela `health_checks` para calculo de uptime |
| Deteccao de incidentes | `detect_incident()` em cada canary run | 5 min | Cria/resolve automaticamente na tabela `incidents` |

### 3.2 Metricas de Saude (SLIs)

As seguintes metricas Prometheus servem como SLIs para monitoramento continuo:

| SLI | Metrica | Alerta Sugerido |
|-----|---------|-----------------|
| Uptime 30d | `smartlic_uptime_pct_30d` | <99.5% |
| Pipeline timeouts | `smartlic_pipeline_budget_exceeded_total` | >0/hr |
| Route timeouts | `smartlic_route_timeout_total` | >10/hr |
| Redis disponibilidade | `smartlic_redis_available` | =0 (degradado) |
| Erros de API externa | `smartlic_api_errors_total` | >100/hr por source |
| Filter discard rate | `smartlic_filter_discard_rate` | Monitorar desvios por setor |
| CB estado | `smartlic_circuit_breaker_degraded` | =1 (aberto) por >15min |
| Memoria RSS | `smartlic_process_memory_rss_bytes` | >500MB |

## 4. O Que FALTA — Lacunas Identificadas

### 4.1 Lacunas de Monitoramento

| Lacuna | Impacto | Prioridade |
|--------|---------|-----------|
| **Alertas de downtime externo (UptimeRobot)** | Nao ha monitoramento de saude externo ao Railway. Se o proxy Railway falhar, nao sabemos. | Alta |
| **Pager duty / on-call rotation** | Alertas vao para email de admin (tiago.sasaki@gmail.com). Sem escalation se email nao for visto. | Alta |
| **Alertas de threshold no Prometheus** | Metricas existem, mas nao ha AlertManager configurado para disparar alerts baseados em threshold. | Media |
| **Monitoramento de frontend (RUM)** | Nao ha Real User Monitoring. Erros de JS no frontend sao capturados por Sentry, mas performance de carregamento nao e monitorada. | Media |
| **Alertas de SSL expiracao** | Sem monitoramento de expiracao de certificado SSL do dominio. | Baixa |
| **Dashboard Grafana publico** | Nao ha dashboard publico de status alem do endpoint `/health` JSON. | Baixa |

### 4.2 Lacunas de Processo

| Lacuna | Impacto | Prioridade |
|--------|---------|-----------|
| **Runbook de resposta a incidentes** | Criado recentemente em `docs/runbooks/incident-response.md`.  Documenta arvore de decisao e procedimentos. | Feito |
| **Post-mortem apos incidentes** | Nao ha processo formal de post-mortem apos incidentes significativos. | Media |
| **Teste de restore trimestral** | Nao ha schedule formal de teste de restore. | Media |

## 5. Proposta de Setup Adicional

### 5.1 UptimeRobot — Health Check Externo

**Custo:** Gratuito (ate 50 monitors, 5min interval).

**Configuracao:**

```text
Monitor Type: HTTP(s)
URL: https://smartlic.tech/health/live
Interval: 5 minutes
Alert when: Down for 1 minute
Notification Contacts: Email (tiago.sasaki@gmail.com)
```

**Monitors sugeridos:**

| Monitor | URL | Justificativa |
|---------|-----|---------------|
| Liveness | `https://smartlic.tech/health/live` | Deteccao de processo morto |
| Readiness | `https://smartlic.tech/health/ready` | Deteccao de dependencia critica offline |
| API Root | `https://smartlic.tech/` | API root response |
| Frontend | `https://smartlic.tech/login` | Frontend SSR disponivel |
| SSL | `https://smartlic.tech` (SSL check) | Expiracao de certificado |

**Nota:** UptimeRobot monitora de fora da infraestrutura Railway, detectando problemas que monitors internos nao veem (ex: proxy Railway offline, DNS failure, roteamento de rede).

### 5.2 Railway Built-in Health Check

**Status:** Ja configurado. Railway utiliza o endpoint `/health/ready` como health check interno.

- Intervalo: Configuravel no painel Railway (default ~15s)
- Acao em falha: Railway reinicia o container apos N falhas consecutivas
- Porta de health check: 8000 (mesma do servico)

### 5.3 Prometheus AlertManager

**Proposta de configuracao:**

```yaml
# Prometheus AlertManager rules (aplicar no servidor Prometheus)
groups:
  - name: smartlic
    rules:
      - alert: SupabaseDown
        expr: smartlic_supabase_pool_active_connections == 0
        for: 2m
        annotations:
          summary: "Supabase esta inacessivel"
          runbook: "docs/runbooks/incident-response.md"

      - alert: RedisDegraded
        expr: smartlic_redis_available == 0
        for: 5m
        annotations:
          summary: "Redis em fallback ha mais de 5 minutos"

      - alert: HighRouteTimeoutRate
        expr: rate(smartlic_route_timeout_total[5m]) > 0.003
        for: 5m
        annotations:
          summary: "Mais de 10 route timeouts por hora"
          runbook: "docs/runbooks/incident-response.md"

      - alert: HighMemoryUsage
        expr: smartlic_process_memory_rss_bytes > 500000000
        for: 5m
        annotations:
          summary: "Processo usando mais de 500MB RSS"

      - alert: CircuitBreakerOpen
        expr: smartlic_circuit_breaker_degraded{source="pncp"} == 1
        for: 15m
        annotations:
          summary: "Circuit breaker do PNCP aberto ha mais de 15 min"

      - alert: LowUptime
        expr: smartlic_uptime_pct_30d < 99.5
        annotations:
          summary: "Uptime 30d abaixo de 99.5%"
```

## 6. Procedimento Quando Alerta Disparar

### 6.1 Arvore de Decisao

```
Alerta dispara
├── Verificar status: railway logs --tail (backend + worker)
├── Verificar health: curl https://smartlic.tech/health/ready
│   ├── healthy → falso positivo (verificar configuracao do alerta)
│   └── unhealthy/degraded →
│       ├── Supabase down →
│       │   ├── Verificar https://status.supabase.com
│       │   ├── Verificar Railway dashboard (conexao com Supabase)
│       │   └── Se prolongado → contatar suporte Supabase
│       ├── Redis degraded →
│       │   ├── Verificar redis-cli ping
│       │   ├── Verificar smartlic_redis_fallback_duration_seconds
│       │   └── Se prolongado → reiniciar Redis via Railway
│       ├── Circuit breaker aberto →
│       │   ├── Verificar log PCP/PNCP para erros 5xx
│       │   ├── Verificar rate limiting (smartlic_rate_limit_exceeded_total)
│       │   └── Se recuperacao automatica falhar → restart do worker
│       └── Route timeouts elevados →
│           ├── Verificar Supabase pool utilization (#1817)
│           ├── Verificar CPU/memoria do processo
│           └── Se persistente → escalar (mais workers, timeout maior)
│
└── Registrar no runbook de incidentes:
    1. Timestamp do alerta
    2. Sintomas observados
    3. Acao tomada
    4. Resolucao
    5. Post-mortem (se aplicavel)
```

### 6.2 Escalation Path

| Nivel | Quem | Canais | SLA |
|-------|------|--------|-----|
| 1 (triagem) | Admin (tiago.sasaki@gmail.com) | Email, Sentry | <30min |
| 2 (engenharia) | Time de desenvolvimento | Email, Sentry, Railway logs | <2h |
| 3 (infra) | Suporte Railway / Supabase | Ticket no provedor | <4h |

### 6.3 Runbook de Referencia

Consultar `docs/runbooks/incident-response.md` para:
- Procedimento detalhado de resposta a incidentes
- Arvore de decisao completa
- Template de post-mortem
- Lista de contatos de emergencia

## 7. Evolucao do Setup

| O que | Quando | Responsavel |
|-------|--------|-------------|
| Configurar UptimeRobot (5 monitors gratuitos) | Imediato | DevOps |
| Adicionar AlertManager ao servidor Prometheus | Proximo ciclo | DevOps |
| Configurar on-call rotation (PagerDuty ou similar gratuito) | Proximo trimestre | Product |
| Implementar dashboard Grafana publico | Proximo trimestre | DevOps |
| Automatizar post-mortem apos incidentes | Continuo | Team |
| Realizar primeiro teste de restore trimestral | Proximo trimestre | DevOps |
