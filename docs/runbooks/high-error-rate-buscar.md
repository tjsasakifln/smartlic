# Runbook: High Error Rate on /buscar

**Versao:** 1.0
**Criado:** 2026-06-17
**Owner:** @devops
**Severidade tipica:** SEV1 (funcionalidade principal)
**Endpoint:** `POST /v1/buscar`

---

## 1. Sintomas

### Alertas
- Sentry: error rate > 5% em `POST /v1/buscar` nos ultimos 5 min
- Metrica: `smartlic_http_responses_total{route="/v1/buscar",status="5xx"}` spike
- Usuario reporta: "busca nao funciona", "erro ao buscar", "carregando eternamente"
- Railway: 503/502 rate > 10%
- Frontend: usuarios veem tela de erro ou loading infinito

### Comportamento Observado
```
Sentry: "POST /v1/buscar" 500 errors
Log: "Pipeline budget exceeded"  (time budget waterfall)
Log: "PNCP client error: ..."
Log: "Cache miss cascade"  (L1+L2 miss, chamada direta a fontes)
Log: "TimeoutError: UF=XX timed out"
Health: wedge_risk pode estar "high"
```

### Pipeline de Busca (diagnostico rapido)

A busca passa por 4 estagios. Cada um pode falhar independentemente:

```
Frontend → SSE Stream → /v1/buscar → Cache Check (L1/L2)
  → PNCP Client → PCP Client → ComprasGov Client
  → Merge → Classificacao → Cache Store → Response Stream
```

O erro pode estar em QUALQUER um desses estagios.

---

## 2. Diagnostico (ordem: datalake → cache → live → frontend)

### 2.1 Verificar Health do Backend

```bash
# Health check completo
curl -s https://api.smartlic.tech/health/ready | jq '.'

# Wedge risk (indicador de stress do sistema)
curl -s https://api.smartlic.tech/health/ready | jq '.wedge_risk'
# "low" = normal, "medium" = stress, "high" = critico
```

### 2.2 Verificar Metrics de Erro por Componente

```bash
# Erros HTTP por rota
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_http_responses_total'

# Erros por fonte de dados
curl -s https://api.smartlic.tech/metrics | grep -E 'smartlic_pncp_error|smartlic_pcp_error|smartlic_comprasgov_error'

# Time budget exceeded (pipeline interrompido)
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_pipeline_budget_exceeded_total'

# Timeouts
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_route_timeout_total'

# Circuit breakers
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_circuit_breaker_trips_total'
```

### 2.3 Testar Busca Direta (sem frontend)

```bash
# Busca simples (1 UF, periodo curto)
curl -s -X POST https://api.smartlic.tech/v1/buscar \
  -H "Content-Type: application/json" \
  -d '{"ufs": ["SC"], "dataInicial": "2026-06-10", "dataFinal": "2026-06-15"}' | jq '.status'

# Se falhar: testar cada fonte separadamente
# PNCP direto
curl -s "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20260610&dataFinal=20260615&pagina=1&tamanhoPagina=5" | head -c 500

# PCP direto (se disponivel)
# curl -s "https://compras.api.portal..." | head -c 500
```

### 2.4 Verificar Cache Health

```bash
# Cache hit rates
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_cache_hit'

# L1 (InMemory) + L2 (Supabase/Redis)
# Se miss rate > 80%, cache pode estar vazio (apos restart) ou com TTL muito curto
```

### 2.5 Verificar Frontend (se busca funciona mas frontend quebra)

```bash
# Verificar se o problema e no frontend
curl -s https://smartlic.tech | head -c 500
# Se 200: frontend esta no ar

# Verificar console errors (via Playwright se disponivel)
# Verificar se o frontend esta fazendo a request correta
```

### 2.6 Verificar Railway Logs Recentes

```bash
# Logs de erro da busca
railway logs --service bidiq-backend --tail | grep -E "buscar|error|exception|timeout" | head -30
```

### 2.7 Verificar Deploy Recente

```bash
gh api /repos/confenge/smartlic/actions/runs --jq '.workflow_runs[:3] | .[] | {name, status, conclusion, created_at}'
```

---

## 3. Arvore de Decisao

```
Alta error rate em /buscar
│
├── wedge_risk = "high"?
│   ├── SIM → Pool exhaustion ou memoria baixa
│   │   └── Ir para runbook supabase-pool-exhaustion.md
│   └── NAO → Problema especifico da busca
│
├── Circuit breaker PNCP aberto?
│   ├── SIM → PNCP API pode estar fora
│   │   └── Ir para runbook pncp-api-breaking-change.md
│   └── NAO
│
├── Pipeline budget exceeded?
│   ├── SIM → Time budget insuficiente
│   │   └── Aumentar budget ou reduzir paralelismo
│   └── NAO
│
├── Source-specific error?
│   ├── PNCP → Ir para pncp-api-breaking-change.md
│   ├── Redis → Ir para redis-connection-failure.md
│   ├── Supabase → Ir para supabase-pool-exhaustion.md
│   └── Todas → Problema geral (deploy quebrou algo)
│
├── Deploy recente?
│   ├── SIM → Rollback IMEDIATO
│   └── NAO → Investigar causa raiz
│
└── Todas as fontes estao saudaveis mas busca falha?
    └── Problema no merge/classificacao → Investigar codigo
```

---

## 4. Mitigacao

### 4.1 Imediata: Rollback (se deploy recente)

```bash
# Rollback e SEMPRE a acao mais rapida se houve deploy recente
railway rollback --service bidiq-backend

# Verificar se rollback resolveu
curl -s https://api.smartlic.tech/health/ready | jq '.ready'
curl -s -X POST https://api.smartlic.tech/v1/buscar \
  -H "Content-Type: application/json" \
  -d '{"ufs": ["SC"], "dataInicial": "2026-06-10", "dataFinal": "2026-06-15"}' | jq '.status'
```

### 4.2 Se rollback nao e possivel: Mitigacoes Especificas

| Problema | Mitigacao |
|----------|-----------|
| Circuit breaker PNCP aberto | `railway variables set PNCP_ENABLED=false` + redeploy |
| Redis offline | Aguardar (degradacao graciosa) ou `railway redeploy` |
| Supabase pool exhaustion | `railway variables set SUPABASE_STATEMENT_TIMEOUT=15000` + redeploy |
| Pipeline budget exceeded | `railway variables set PIPELINE_TOTAL_BUDGET_S=120` + redeploy |
| Timeout especifico de UF | Reduzir `MAX_CONCURRENT_UFS` ou aumentar timeout |

### 4.3 Se erro no frontend (nao backend)

```bash
# Verificar se NEXT_PUBLIC_BACKEND_URL esta correto
railway variables --service bidiq-frontend | grep NEXT_PUBLIC_BACKEND_URL

# Verificar build do frontend
railway logs --service bidiq-frontend --tail | grep -i error

# Se necessario: rollback do frontend
railway rollback --service bidiq-frontend
```

### 4.4 Emergency: Desabilitar Fontes Problematicas

Se apenas uma fonte esta causando erro, desabilita-la:

```bash
railway variables set PNCP_ENABLED=false --service bidiq-backend
# ou
railway variables set PCP_ENABLED=false --service bidiq-backend
# ou
railway variables set COMPRASGOV_ENABLED=false --service bidiq-backend

railway redeploy --service bidiq-backend -y
```

---

## 5. Resolucao

### 5.1 Verificar Busca Apos Mitigacao

```bash
# 1. Health check
curl -s https://api.smartlic.tech/health/ready | jq '.ready'

# 2. Busca de teste
curl -s -X POST https://api.smartlic.tech/v1/buscar \
  -H "Content-Type: application/json" \
  -d '{"ufs": ["SC"], "dataInicial": "2026-06-10", "dataFinal": "2026-06-15"}' | jq '{status: .status, total: (.resultados | length)}'

# 3. Verificar metrics
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_http_responses_total' | grep '/v1/buscar'
```

### 5.2 Monitorar por 15 Minutos

Apos a mitigacao, monitorar:
- Error rate no Sentry (deve cair para < 1%)
- `wedge_risk` (deve voltar para "low")
- Logs de erro (sem novos erros de busca)

### 5.3 Apos Estabilizar: Post-Mortem

Criar post-mortem em `docs/incidents/` com:
- Timeline completa (deteccao -> triagem -> mitigacao -> resolucao)
- Causa raiz
- Acoes corretivas
- Metricas de impacto

---

## 6. Prevencao

### Monitoramento
- Alerta Sentry: error rate > 5% em `/v1/buscar` nos ultimos 5 min
- Metrica: `smartlic_http_responses_total{route="/v1/buscar"}` com label de status
- Dashboard Railway: error rate + response time + throughput

### Testes
- Smoke test automatizado para `/v1/buscar` (roda a cada 5 min)
- Teste de integracao que mocka cada fonte e verifica fallback
- Chaos engineering: derrubar uma fonte de cada vez para testar degradacao

### Arquitetura
- Cada fonte de dados deve ser independente (falha de uma nao quebra as outras)
- Cache (L1 + L2) protege contra instabilidade de fontes
- Circuit breakers protegem contra hammering de fontes instaveis
- Time budget waterfall: 100s total, distribuido entre fontes

---

## 7. Referencias

- `incident-response.md` — Triagem inicial, matriz de severidade
- `supabase-pool-exhaustion.md` — Pool exhaustion Supabase
- `pncp-api-breaking-change.md` — Breaking change PNCP
- `redis-connection-failure.md` — Redis offline
- `docs/runbooks/rollback-procedure.md` — Rollback backend/frontend
- `backend/pipeline/buscar_service.py` — Implementacao da busca
- `backend/services/cache/` — Cache L1 (InMemory) e L2 (Redis/Supabase)
- CLAUDE.md secao "Time Budget Waterfall" — Pipeline 100s > per_source 70s > per_uf 25s
