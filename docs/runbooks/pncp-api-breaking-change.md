# Runbook: PNCP API Breaking Change

**Versao:** 1.0
**Criado:** 2026-06-17
**Owner:** @devops
**Severidade tipica:** SEV2 (SEV1 se todas as buscas falharem)
**Referencia:** `incident-response.md` secao 3.4

---

## 1. Sintomas

### Alertas
- Sentry: `pncp_breaking_change` com fingerprint `["pncp_canary", reason]`
- Canary detectou: `max_page_size_changed`, `shape_drift`, `required_field_missing`
- Buscas retornam 0 resultados
- Log: `PNCP API response shape mismatch`
- Circuit breaker PNCP abriu (`smartlic_circuit_breaker_trips_total{source="pncp"} > 0`)

### Comportamento Observado
```bash
# Canary metrics
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_pncp_canary'

# Provavel output:
# smartlic_pncp_canary_consecutive_failures 3
# smartlic_pncp_canary_last_status{reason="shape_drift"} 0

# Circuit breaker PNCP
curl -s https://api.smartlic.tech/health/ready | jq '.checks.pncp_circuit_breaker'
# Provavel: "OPEN" (se ja tripou)
```

### Matriz de Impacto

| Dados de Busca | Com PNCP Quebrado | Acoes |
|----------------|-------------------|-------|
| Resultados PNCP | 0 | PCP + ComprasGov continuam |
| Cobertura total | ~60% dos editais do pais | Cobertura cai para ~40% |
| UFs pequenas | Perdem cobertura completa | PCP cobre ~15 UFs |
| UFs grandes (SP, RJ, MG) | Ainda cobertos por PCP | Cobertura parcial |

---

## 2. Diagnostico

### 2.1 Identificar o Tipo de Breaking Change

```bash
# 1. Testar PNCP direto
curl -s "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20260610&dataFinal=20260615&pagina=1&tamanhoPagina=5" | head -c 1000

# 2. Verificar status code
curl -s -o /dev/null -w "%{http_code}" "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20260610&dataFinal=20260615&pagina=1&tamanhoPagina=5"
# 200 = API online, 500 = API com problema, 400 = nossa request esta errada

# 3. Verificar response time
curl -s -o /dev/null -w "time_total=%{time_total}\nhttp_code=%{http_code}\n" "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20260610&dataFinal=20260615&pagina=1&tamanhoPagina=5"
```

### 2.2 Verificar Canary Log

```bash
railway logs --service bidiq-worker --tail | grep -A5 "pncp_canary"
```

O canary roda a cada 10 min (`PNCP_CANARY_INTERVAL_S=600`) no worker. Log output mostra exatamente o que falhou:

- `shape_drift` — Campos diferentes do esperado
- `max_page_size_changed` — `tamanhoPagina` maximo mudou
- `required_field_missing` — Campo obrigatorio ausente
- `status_code_unexpected` — API retornando erro

### 2.3 Verificar Versao do Schema

```bash
# Nosso schema esperado (arquivo local)
grep -A20 "CONTRATACAO_SCHEMA" backend/pncp_canary.py

# Response real
curl -s "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20260610&dataFinal=20260615&pagina=1&tamanhoPagina=1" | python3 -m json.tool | head -30
```

---

## 3. Causas

| Tipo | Exemplo | Urgencia |
|------|---------|----------|
| `max_page_size_changed` | `tamanhoPagina` maximo mudou de 50 para 20 | ALTA — reduz cobertura |
| `shape_drift` | Campo `dataPublicacao` renomeado para `dataPublicacaoPNCP` | CRITICA — quebra parser |
| `required_field_missing` | `modalidade` nao e mais retornado | CRITICA — quebra parser |
| `status_code_unexpected` | API retornando 500 para requests validas | MEDIA — pode ser instabilidade |
| `response_time_degraded` | P95 > 30s | BAIXA — PNCP pode estar lento |

---

## 4. Mitigacao

### 4.1 Imediata: Desabilitar PNCP (se critico)

Se o parser quebrou e buscas estao retornando 0 resultados:

```bash
# Desabilitar fonte PNCP
railway variables set PNCP_ENABLED=false --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

**Impacto:** Buscas usarao PCP + ComprasGov. Cobertura cai, mas funcionalidade principal continua.

**Tempo de deploy:** ~90s (Railway redeploy)

### 4.2 Se page_size mudou (nao quebrou parser)

Apenas ajustar o tamanho da pagina:

```bash
# Descobrir novo tamanho maximo
curl -s "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20260610&dataFinal=20260615&pagina=1&tamanhoPagina=100" | head -c 200

# Testar com tamanhos diferentes ate encontrar o maximo aceito
for size in 10 20 30 50 100; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao?dataInicial=20260610&dataFinal=20260615&pagina=1&tamanhoPagina=$size")
  echo "tamanhoPagina=$size → $code"
done

# Atualizar no Railway
railway variables set PNCP_PAGE_SIZE=<novo_valor> --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

### 4.3 Se shape_drift (parser quebrou)

**Emergency:** Desabilitar PNCP `PNCP_ENABLED=false` e criar hotfix:

```bash
# 1. Desabilitar PNCP
railway variables set PNCP_ENABLED=false --service bidiq-backend
railway redeploy --service bidiq-backend -y

# 2. Criar branch de hotfix
git checkout -b hotfix/pncp-schema-$(date +%Y%m%d)

# 3. Atualizar schema em backend/pncp_client.py
#    - Mapear novos campos
#    - Atualizar validacao
#    - Adicionar log para detectar futuras mudancas

# 4. Testar localmente com response real da PNCP

# 5. Commit, push, PR, deploy
```

### 4.4 Se status_code_unexpected (PNCP instavel)

Se a API esta com instabilidade temporaria (500 intermitentes):

```bash
# Apenas monitorar — nao desabilitar imediatamente
# O circuit breaker ja protege contra hammering

# Verificar circuit breaker state
curl -s https://api.smartlic.tech/health/ready | jq '.checks.pncp_circuit_breaker'

# Se HALF_OPEN ou OPEN: aguardar circuit breaker fechar sozinho
# Se CLOSED mas erros continuam: considerar desabilitar
```

---

## 5. Resolucao

### 5.1 Apos aplicar hotfix

```bash
# Reabilitar PNCP
railway variables set PNCP_ENABLED=true --service bidiq-backend
railway variables set PNCP_PAGE_SIZE=<novo_valor> --service bidiq-backend  # Se mudou
railway redeploy --service bidiq-backend -y
```

### 5.2 Verificar canary pos-fix

```bash
# Aguardar 10 min (ciclo do canary)
# Verificar metrics
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_pncp_canary'
# Esperado: smartlic_pncp_canary_consecutive_failures 0

# Testar busca real
curl -s -X POST https://api.smartlic.tech/v1/buscar \
  -H "Content-Type: application/json" \
  -d '{"ufs": ["SC"], "dataInicial": "2026-06-10", "dataFinal": "2026-06-15"}' | jq '.total | length'
# Esperado: > 0 resultados
```

---

## 6. Prevencao

### Canary Proativo
- `pncp_canary.py` roda a cada 10 min no worker
- Fingerprint Sentry `["pncp_canary", reason]` com dedup de 6h via Redis
- Se falhar 3x consecutivas: alerta Sentry + metric gauge

### Testes de Integracao
- Teste semanal que consome PNCP real (fora do horario comercial)
- Valida schema response contra `CONTRATACAO_SCHEMA`
- Se schema do PNCP mudou: teste quebra, alerta antes de chegar em prod

### Contrato PNCP
- PNCP nao tem SLA formal nem changelog de API
- Toda request deve ser resiliente a shape desconhecido
- Usar `response.get("campo", DEFAULT)` em vez de `response["campo"]`

---

## 7. Referencias

- `backend/jobs/cron/pncp_canary.py` — Implementacao do canary
- `backend/pncp_client.py` — Cliente PNCP
- `backend/pncp_resilience.py` — Adaptive timeout, retry, circuit breaker
- `incident-response.md` secao 3.4 — Playbook resumido PNCP Breaking Change
- `docs/runbooks/PNCP-TIMEOUT-RUNBOOK.md` — Timeout especifico PNCP por UF
- API PNCP: https://pncp.gov.br/api/consulta/v1/swagger-ui.html
