# Runbook de Incidentes — SmartLic

**Versao:** 2.0
**Criado:** 2026-06-15
**Owner:** @devops
**Issues:** #1799, #640

---

## Sumario

1. [Matriz de Severidade (SEV1-SEV4)](#1-matriz-de-severidade-sev1-sev4)
2. [Fluxo de Resposta a Incidentes](#2-fluxo-de-resposta-a-incidentes)
3. [Playbooks por Cenário](#3-playbooks-por-cenario)
   - [3.1 Backend DOWN (502)](#31-backend-down-502)
   - [3.2 Supabase Pool Exhaustion (CRIT-046)](#32-supabase-pool-exhaustion-crit-046)
   - [3.3 Redis Offline](#33-redis-offline)
   - [3.4 PNCP API Breaking Change](#34-pncp-api-breaking-change)
   - [3.5 Stripe Webhook Failure](#35-stripe-webhook-failure)
4. [Comandos de Diagnostico Rapido](#4-comandos-de-diagnostico-rapido)
5. [Contatos e Escalacao](#5-contatos-e-escalacao)
6. [Referencias](#6-referencias)

---

## 1. Matriz de Severidade (SEV1-SEV4)

| Severidade | Definicao | Tempo de Resposta | MTTR Alvo | Exemplos |
|------------|-----------|-------------------|-----------|----------|
| **SEV1** (Critico) | Sistema totalmente indisponivel ou funcionalidade critica (busca, login, pipeline) quebrada para todos os usuarios. Impacto direto em receita. | **< 5 min** para responder | **< 30 min** | Backend 100% down (502), Supabase outage total, perda de dados, Stripe webhook parando de processar assinaturas |
| **SEV2** (Alto) | Funcionalidade principal degradada para alguns usuarios ou parcialmente indisponivel. Sem workaround aceitavel. | **< 15 min** para responder | **< 60 min** | Redis offline, busca lenta (p95 > 10s), PNCP circuit breaker aberto, zero-match LLM falhando |
| **SEV3** (Medio) | Funcionalidade secundaria afetada. Workaround existe ou impacto limitado a um subconjunto pequeno de usuarios. | **< 60 min** para responder | **< 4 h** | PNCP canary detectou shape drift, cache L1 cheio mas Redis funcionando, erro em pagina SEO programatica |
| **SEV4** (Baixo) | Problema cosmetico, bug sem impacto funcional, alerta de baixa urgencia. | **< 24 h** para responder | Proximo ciclo | Typo em pagina de marketing, gauge de metrica com label errada, warning em log sem consequencia |

### Gatilhos de Escalacao Automatica

- SEV1 nao mitigado em 15 min -> escalar para @architect + @pm
- SEV2 nao mitigado em 60 min -> escalar para @devops + @architect
- Qualquer SEV com causa desconhecida apos 30 min de investigacao -> escalar automaticamente

---

## 2. Fluxo de Resposta a Incidentes

```
DETECTAR -> TRIAR -> MITIGAR -> RESOLVER -> POST-MORTEM
```

### 2.1 Detectar

O incidente pode ser detectado por:

- **Alerta de uptime** (UptimeRobot / BetterStack): health check falhou
- **Alerta Sentry**: error rate spike, pipeline wedge, pool saturation
- **Usuario reportando**: email, suporte in-app (InMail)
- **Canary**: PNCP breaking change detectado
- **Metrica**: `smartlic_pipeline_budget_exceeded_total` > 2/5min, `wedge_risk=high`

**Acao imediata ao receber alerta:**
1. Abra esta runbook
2. Classifique a severidade (SEV1-SEV4) usando a matriz acima — nao perca mais de 30s nisso
3. Inicie o timer de resposta

### 2.2 Triar (5 min)

```bash
# 1. Health check completo
curl -s https://api.smartlic.tech/health/ready | jq .

# 2. Health liveness (sempre 200 se o processo estiver vivo)
curl -s https://api.smartlic.tech/health/live | jq .

# 3. Metrics: circuit breakers, redis, supabase
curl -s https://api.smartlic.tech/metrics | grep -E 'smartlic_circuit_breaker|smartlic_redis_available|smartlic_supabase_cb_state'

# 4. Railway logs
railway logs --tail --service bidiq-backend | head -50

# 5. Deploy recente?
gh api /repos/confenge/smartlic/actions/runs --jq '.workflow_runs[:3] | .[] | {status, conclusion, name, created_at}'

# 6. Status pages
# Supabase: https://status.supabase.com
# OpenAI: https://status.openai.com
# Stripe: https://status.stripe.com
# Railway: https://status.railway.app
```

**Perguntas-chave durante triagem:**
- E problema no nosso codigo ou em dependencia externa?
- Houve deploy recente? (rollback e a acao mais rapida)
- E generalizado ou afeta apenas alguns usuarios?
- `wedge_risk` esta `low`, `medium` ou `high`?

### 2.3 Mitigar

Siga o playbook especifico na Secao 3. O objetivo e restaurar o servico o mais rapido possivel.

**Principios de mitigacao:**
- **Rollback** e sempre mais rapido que fix forward para incidentes de codigo
- **Feature flag**: desabilitar funcionalidade problematica via Railway env var (nao requer deploy)
- **Degradacao graciosa**: melhor que downtime total (ex: servir resultados parciais de fontes saudaveis)
- **Nao investigar debug flags em prod** — o gate `audit-prod-env.yml` detecta isso

### 2.4 Resolver

Apos mitigacao, verificar:
- `curl -s https://api.smartlic.tech/health/ready | jq '.ready'` retorna `true`
- Funcionalidade critica testada manualmente (busca, pipeline, login)
- Alertas estabilizaram (sem novos disparos nos ultimos 5 min)
- `wedge_risk` voltou para `low`

### 2.5 Post-Mortem

Para SEV1 e SEV2, crie documento de post-mortem em `docs/incidents/YYYY-MM-DD-titulo.md`:

```markdown
# Post-Mortem: [Titulo]

**Data:** YYYY-MM-DD
**Duracao:** Xh Ym
**Severidade:** SEV1/SEV2
**Impacto:** [Descricao — usuarios afetados, metricas, receita]

## Timeline
- HH:MM - Alerta disparado
- HH:MM - Triagem iniciada
- HH:MM - Causa identificada
- HH:MM - Mitigacao aplicada
- HH:MM - Servico restaurado

## Causa Raiz
[Descricao]

## Acao Imediata
[O que foi feito]

## Acoes Corretivas
- [ ] [Descricao] — Owner: @ — Prazo: YYYY-MM-DD

## Licoes
[O que funcionou, o que melhorar]

## Metricas
- MTTR: Xm | Downtime: Xm | Usuarios afetados: X
```

---

## 3. Playbooks por Cenário

### 3.1 Backend DOWN (502)

**Sintomas:** Frontend carrega mas buscas retornam erro / health check timeout / Railway mostra CRASHED.

**Severidade tipica:** SEV1

#### Diagnostico

```bash
# Logs do Railway
railway logs --tail --service bidiq-backend

# Liveness check
curl -s -o /dev/null -w "%{http_code}" https://api.smartlic.tech/health/live

# Readiness
curl -s https://api.smartlic.tech/health/ready | jq .

# GitHub Actions billing gate (CRIT-080)
gh api /repos/confenge/smartlic/actions/runs --jq '.workflow_runs[:5] | .[] | {status, conclusion, name, created_at}'
```

#### Causas e Mitigacao

| Causa | Verificacao | Mitigacao |
|-------|-------------|-----------|
| SIGSEGV (CRIT-080/083) | Logs mostram segfault | Verificar `RUNNER=uvicorn` (nao gunicorn); redeploy |
| OOM | Railway mostra memoria > 90% | Reduzir `WEB_CONCURRENCY=2` ou rollback |
| Erro de sintaxe/import | Logs mostram `SyntaxError` / `ModuleNotFoundError` | Rollback imediato |
| Railway proxy timeout | Logs mostram 503 apos 120s | Verificar `ROUTE_TIMEOUT_S` (< 120) |
| GitHub Actions sem billing | Actions runs "queued" / `conclusion=null` | Resolver pagamento em GitHub Settings > Billing |

#### Acao

```bash
# Rollback imediato
railway rollback --service bidiq-backend

# Se rollback falhar, redeploy forcado
railway redeploy --service bidiq-backend -y

# Verificar env vars criticas
railway variables --service bidiq-backend | grep -E 'RUNNER|WEB_CONCURRENCY|ROUTE_TIMEOUT'
```

#### Verificacao pos-mitigacao

```bash
curl -s https://api.smartlic.tech/health/ready | jq '.ready'
# Testar busca simples
curl -s -X POST https://api.smartlic.tech/v1/buscar \
  -H "Content-Type: application/json" \
  -d '{"ufs": ["SC"], "dataInicial": "2026-06-01", "dataFinal": "2026-06-10"}' | jq '.status'
```

---

### 3.2 Supabase Pool Exhaustion (CRIT-046)

**Sintomas:** `wedge_risk=high`, buscas falham com timeout, Sentry alerta `smartlic_supabase_pool_timeouts_total > 0`. Logs mostram `PoolTimeout` ou `ConnectionError`.

**Severidade tipica:** SEV2 (pode escalar para SEV1)

#### Diagnostico

```bash
# 1. Pool utilization via Prometheus
curl -s https://api.smartlic.tech/metrics | grep -E 'smartlic_supabase_pool_(active|idle|max|timeouts|retry)'

# 2. Wedge risk
curl -s https://api.smartlic.tech/health/ready | jq '{wedge_risk, checks}'

# 3. Conexoes ativas (Supabase Management API)
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT count(*) as active_conns FROM pg_stat_activity WHERE state = '\''active'\''"}' | jq .

# 4. Queries lentas (>10s)
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT pid, now() - query_start AS duration, query, state FROM pg_stat_activity WHERE state != '\''idle'\'' AND now() - query_start > interval '\''10 seconds'\'' ORDER BY duration DESC"}' | jq .
```

#### Causas e Mitigacao

| Causa | Mitigacao |
|-------|-----------|
| `statement_timeout` alto (queries rodam > 15s) | `railway variables set SUPABASE_STATEMENT_TIMEOUT=15000` + redeploy |
| Pico de requests simultaneos | Aumentar `SUPABASE_POOL_MAX_CONNECTIONS` ou reduzir `WEB_CONCURRENCY` |
| SSG build hammering backend | Adicionar `AbortSignal.timeout` nos fetches SSG |
| Conexoes vazando (sem cleanup) | Verificar `get_supabase()` com `try/finally` |

```bash
# Emergency: reduzir statement_timeout
railway variables set SUPABASE_STATEMENT_TIMEOUT=15000 --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

#### Referencia

**CRIT-046 (2026-04):** Pool saturation durante pico de uso. `statement_timeout` estava em 30s (default). Fix: reduzir para 15s. Criados gauges de pool para monitoramento continuo.

---

### 3.3 Redis Offline

**Sintomas:** `smartlic_redis_available=0`, rate limit para de funcionar, circuit breaker state perdido, ARQ queue nao processa.

**Severidade tipica:** SEV2

#### Diagnostico

```bash
# Gauge de disponibilidade
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_redis_available'

# Tempo em fallback
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_redis_fallback_duration_seconds'

# PING direto
railway run --service bidiq-backend python3 -c "
import asyncio, os
from redis import asyncio as aioredis
async def main():
    r = aioredis.from_url(os.environ['REDIS_URL'])
    print(await r.ping())
asyncio.run(main())
"
```

#### Impacto

| Componente | Com Redis | Sem Redis |
|------------|-----------|-----------|
| Cache L1 | Redis-backed (multi-worker) | InMemoryCache (per-process, sem shared) |
| Rate Limiter | Token bucket funcional | Fail-open (todas requests passam) |
| Circuit Breaker | Estado persistente | Reseta para CLOSED |
| ARQ Jobs | Processamento assincrono | Inline (mais lento) |

#### Acao

O sistema tem **degradacao graciosa** para Redis offline. Nao requer acao imediata.

```bash
# Se Railway addon: restartar servico Redis
railway redeploy --service redis -y

# Se Upstash: verificar quota no dashboard

# Se prolongado (> 30 min): aumentar InMemoryCache
railway variables set INMEMORY_CACHE_MAX_ENTRIES=20000 --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

**Gatilho SEV1:** Redis offline > 30 min COM pico de uso (InMemoryCache nao aguenta).

---

### 3.4 PNCP API Breaking Change

**Sintomas:** Sentry alerta com tag `pncp_breaking_change`, canary detectou `max_page_size_changed` ou `shape_drift`. Buscas retornam 0 resultados.

**Severidade tipica:** SEV2 (SEV1 se todas as buscas falharem)

#### Diagnostico

```bash
# Canary metrics
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_pncp_canary'

# Circuit breaker PNCP
curl -s https://api.smartlic.tech/health/ready | jq '.checks'

# Testar PNCP direto
curl -s "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20260610&dataFinal=20260615&pagina=1&tamanhoPagina=5" | head -c 500
```

#### Cenarios e Mitigacao

| Cenario | Acao |
|---------|------|
| `tamanhoPagina` aumentou (ex: 50 -> 100) | Nao urgente. Atualizar `PNCP_PAGE_SIZE` no proximo deploy |
| `tamanhoPagina` diminuiu (ex: 50 -> 20) | **URGENTE**: `railway variables set PNCP_PAGE_SIZE=20` + redeploy |
| Response shape mudou (campo renomeado) | **CRITICO**: Ajustar schema + `pncp_client.py` |
| API retornando 500 | Verificar status PNCP. Se prolongado, desabilitar PNCP |

```bash
# Emergency: desabilitar PNCP (buscas usarao PCP + ComprasGov)
railway variables set PNCP_ENABLED=false --service bidiq-backend
railway redeploy --service bidiq-backend -y

# Reabilitar apos fix
railway variables set PNCP_ENABLED=true --service bidiq-backend
```

#### Referencia

Canary roda a cada 10 min (`PNCP_CANARY_INTERVAL_S=600`) no worker. Fingerprint Sentry `["pncp_canary", reason]`, dedup 6h via Redis. Veja `backend/jobs/cron/pncp_canary.py`.

---

### 3.5 Stripe Webhook Failure

**Sintomas:** Assinaturas nao ativadas apos checkout, usuarios presos em trial expirado, `stripe_webhook_errors` no Sentry.

**Severidade tipica:** SEV2 (impacto direto em receita)

#### Diagnostico

```bash
# Eventos falhos no Stripe
curl -s https://api.stripe.com/v1/events?limit=5&delivery_success=false \
  -u "$STRIPE_SECRET_KEY:" | jq '.data[] | {id, type, created, pending_webhooks}'

# Verificar endpoint webhook
curl -s https://api.stripe.com/v1/webhook_endpoints \
  -u "$STRIPE_SECRET_KEY:" | jq '.data[] | select(.url | contains("smartlic")) | {url, status, enabled_events}'

# Verificar env var do webhook secret
railway variables --service bidiq-backend | grep STRIPE_WEBHOOK_SECRET
```

#### Causas e Mitigacao

| Causa | Mitigacao |
|-------|-----------|
| Webhook URL mudou | Atualizar endpoint no Stripe Dashboard |
| Assinatura invalida | Verificar/regenerar `STRIPE_WEBHOOK_SECRET` |
| Backend retornou 5xx | Rollback se handler quebrou; verificar logs |
| Evento nao tratado | Adicionar handler em `webhooks/handlers/` |

```bash
# Verificar eventos processados (Supabase)
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT event_id, event_type, created_at, status FROM events_processed ORDER BY created_at DESC LIMIT 10"}' | jq .

# Reprocessar webhooks falhos manualmente no Stripe Dashboard
# Stripe > Developers > Webhooks > Failed deliveries > Retry

# Se handler quebrado: rollback
railway rollback --service bidiq-backend
```

---

## 4. Comandos de Diagnostico Rapido

### Railway

```bash
railway logs --tail --service bidiq-backend       # Logs backend
railway logs --tail --service bidiq-worker         # Logs worker
railway deployments --service bidiq-backend         # Listar deployments
railway variables --service bidiq-backend           # Env vars
railway rollback --service bidiq-backend             # Rollback
railway redeploy --service bidiq-backend -y          # Redeploy forcado
```

### Redis

```bash
# PING
railway run --service bidiq-backend python3 -c "
import asyncio, os; from redis import asyncio as aioredis
async def main():
    r = aioredis.from_url(os.environ['REDIS_URL'])
    print(await r.ping())
asyncio.run(main())
"
# Metrics
curl -s https://api.smartlic.tech/metrics | grep -E 'redis_pool|redis_available|redis_fallback'
```

### Supabase

```bash
# Supabase Management API health
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/health" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" | jq .
# Conexoes ativas
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT count(*) FROM pg_stat_activity"}' | jq .
# Pool metrics
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_supabase_pool'
```

### Application Health

```bash
curl -s -o /dev/null -w "%{http_code}" https://api.smartlic.tech/health/live
curl -s https://api.smartlic.tech/health/ready | jq .
curl -s https://api.smartlic.tech/health/ready | jq '.wedge_risk'
curl -s https://api.smartlic.tech/metrics | grep -E 'smartlic_(uptime|incidents|health_canary|http_responses|circuit_breaker|pipeline_budget_exceeded)'
```

### GitHub / CI

```bash
gh api /repos/confenge/smartlic/actions/runs --jq '.workflow_runs[:3] | .[] | {name, status, conclusion, created_at}'
gh api /repos/confenge/smartlic/actions/billing --jq '{minutes_used, included_minutes}'
gh pr list --state merged --limit 5
```

---

## 5. Contatos e Escalacao

### Equipe de Resposta

| Funcao | Nome | Contato | Disponibilidade |
|--------|------|---------|-----------------|
| **DevOps (Primary On-Call)** | Tiago Sasaki | tiago.sasaki@gmail.com | 24/7 |

### Canais de Alerta

| Canal | Uso | Destino |
|-------|-----|---------|
| Email | Sentry, UptimeRobot, BetterStack | tiago.sasaki@gmail.com |
| Sentry | Error tracking, metric alerts | confenge org |

### Contatos Externos

| Servico | Suporte | Status Page |
|---------|---------|-------------|
| Railway | https://railway.app/help | https://status.railway.app |
| Supabase | https://supabase.com/support | https://status.supabase.com |
| Stripe | https://support.stripe.com | https://status.stripe.com |
| OpenAI | https://help.openai.com | https://status.openai.com |
| Sentry | https://sentry.io/support | - |

---

## 6. Referencias

### Runbooks Relacionados

| Documento | Caminho |
|-----------|---------|
| Rollback Procedure | `docs/runbooks/rollback-procedure.md` |
| General Outage | `docs/runbooks/general-outage.md` |
| PNCP Timeout | `docs/runbooks/PNCP-TIMEOUT-RUNBOOK.md` |
| Stripe Outage | `docs/runbooks/stripe-outage.md` |
| Monitoring Setup | `docs/runbooks/monitoring-alerting-setup.md` |
| Audit Prod Env | `docs/runbooks/audit-prod-env.md` |
| Redis Failure Modes | `docs/architecture/redis-failure-modes.md` |
| Error Budget & SLO | `docs/architecture/error-budget-slo.md` |

### Arquitetura

| Documento | Caminho |
|-----------|---------|
| System Architecture | `docs/architecture/system-architecture.md` |
| Architecture Patterns | `.claude/rules/architecture-patterns.md` |
| Critical Implementation Notes | `.claude/rules/critical-impl-notes.md` |

### Metricas Prometheus Relevantes

| Metrica | Proposito |
|---------|-----------|
| `smartlic_http_responses_total` | Respostas HTTP por status class |
| `smartlic_uptime_pct_30d` | Uptime percentual (30 dias) |
| `smartlic_route_timeout_total` | Route-level timeouts |
| `smartlic_pipeline_budget_exceeded_total` | Pipeline phases que excederam budget |
| `smartlic_redis_available` | Disponibilidade Redis |
| `smartlic_incidents_total` | Incidentes (labels: source, severity) |
| `smartlic_health_canary_status` | Status health canary |
| `smartlic_circuit_breaker_trips_total` | Trip events em circuit breakers |
| `smartlic_pncp_canary_consecutive_failures` | Falhas consecutivas PNCP canary |
| `smartlic_supabase_pool_timeouts_total` | Pool timeouts Supabase |

---

**Versao:** 2.0
**Criado:** 2026-06-15
**Substitui:** v1.0 (Issue #640)
**Proxima revisao:** Apos primeira SEV1 usando esta runbook
