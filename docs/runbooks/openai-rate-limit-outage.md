# Runbook: OpenAI Rate Limit / Outage

**Versao:** 1.0
**Criado:** 2026-06-17
**Owner:** @devops
**Severidade tipica:** SEV3 (pode escalar SEV2 se prolongado)
**Modelo:** GPT-4.1-nano (classificacao setorial + resumos executivos)

---

## 1. Sintomas

### Alertas
- Sentry: `openai_rate_limit` ou `openai_api_error`
- Log: `429 Too Many Requests` (rate limit) ou `timeout` (outage)
- Metrica: `smartlic_openai_rate_limit_hits_total > 0`
- Usuario reporta: "resumo nao aparece", "classificacao parece diferente"

### Comportamento Observado
```
Log: "openai.RateLimitError: 429 Too Many Requests"
Log: "openai.APITimeoutError: Request timed out"
Log: "openai.APIConnectionError: Connection error"
Log: "LLM classification fallback: REJECT (zero-match)"
```

### Impacto por Funcionalidade

| Funcionalidade | Com OpenAI OK | Com Erro | Severidade |
|---------------|---------------|----------|------------|
| Classificacao keyword | Normal | Normal | Nenhum |
| Classificacao zero-match LLM | Classifica bids novos | Todos REJECT (fallback) | ALTO recall |
| Resumo executivo IA | Resumo detalhado | `gerar_resumo_fallback()` generico | BAIXO |
| Enriquecimento setorial | Keywords + contexto | Pula enriquecimento | BAIXO |

---

## 2. Diagnostico

### 2.1 Verificar Status OpenAI

```bash
# Status page oficial
curl -s https://status.openai.com | grep -oP 'All Systems Operational|Degraded Performance|Partial Outage|Major Outage'
# Ou acessar: https://status.openai.com

# Health endpoint
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -c 200
# Se retorna lista de modelos: OpenAI esta respondendo
# Se timeout ou 401: problema de rede ou chave
```

### 2.2 Verificar Rate Limit Status

```bash
# Verificar headers de rate limit
curl -s -D - https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4.1-nano", "messages": [{"role": "user", "content": "test"}], "max_tokens": 5}' 2>&1 | grep -iE 'x-ratelimit|x-request-id'

# Headers importantes:
# x-ratelimit-remaining-requests: quantas requests restam no periodo
# x-ratelimit-remaining-tokens: quantos tokens restam
# x-ratelimit-reset-requests: quando o limite reseta
```

### 2.3 Verificar Key Usage no OpenAI Dashboard

```bash
# OpenAI Dashboard > API Keys > Usage
# https://platform.openai.com/usage

# Verificar:
# - Usage no mes atual vs limite da conta
# - Tokens consumidos por modelo (GPT-4.1-nano)
# - Cost incurred
```

### 2.4 Verificar Logs do Backend

```bash
# Classificacao LLM logs
railway logs --service bidiq-worker --tail | grep -i "llm\|openai\|classific"

# Pipeline logs
railway logs --service bidiq-backend --tail | grep -i "llm\|openai\|classific"
```

### 2.5 Verificar Cache de Classificacao

```bash
# Classificacoes em cache ainda sao servidas
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_llm_cache'
# Se hit rate > 50%, impacto e menor (classificacoes em cache nao chamam OpenAI)
```

---

## 3. Causas

| Causa | Indicador | Probabilidade |
|-------|-----------|---------------|
| Rate limit excedido (RPM ou TPM) | HTTP 429 + headers de rate limit | Alta |
| Key expirou ou foi revogada | HTTP 401 `Invalid API Key` | Media |
| OpenAI outage | Status page mostra incidente | Baixa |
| Budget mensal excedido | HTTP 429 `insufficient_quota` | Media |
| Network issue (Railway -> OpenAI) | `APIConnectionError` sem 429/401 | Baixa |

---

## 4. Mitigacao

### 4.1 Imediata: Nenhuma (fallback automatico)

O sistema tem fallback automatico para OpenAI indisponivel:

- **Zero-match LLM:** Fallback para REJECT (zero noise philosophy). Bids que seriam aprovadas apenas por LLM sao rejeitadas. Perda de recall, mas sem falso positivo.
- **Resumos executivos:** `gerar_resumo_fallback()` gera resumo baseado em template (sem LLM).
- **Classificacao keyword:** Funciona normalmente.

**Nao requer acao imediata para SEV3.**

### 4.2 Se rate limit (429): Aumentar Backoff / Reduzir Concorrencia

```bash
# Reduzir concorrencia de chamadas OpenAI
railway variables set LLM_MAX_CONCURRENCY=3 --service bidiq-backend
railway variables set LLM_RATE_LIMIT_RPM=50 --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

### 4.3 Se rate limit persistente: Desabilitar LLM Classification

```bash
# Desabilitar classificacao LLM
railway variables set LLM_ARBITER_ENABLED=false --service bidiq-backend
railway variables set LLM_ZERO_MATCH_ENABLED=false --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

**Impacto:** Apenas classificacao keyword funciona. Resultados serao menos precisos para setores sem keyword match. Risco de perder bids relevantes (falso negativo), mas ZERO falso positivo.

### 4.4 Se outage OpenAI confirmado (status.openai.com)

```bash
# 1. Desabilitar recursos LLM
railway variables set LLM_ARBITER_ENABLED=false --service bidiq-backend
railway variables set SUMMARY_WITH_LLM=false --service bidiq-backend
railway redeploy --service bidiq-backend -y

# 2. Monitorar status page
# https://status.openai.com

# 3. Ao恢复正常: Reabilitar
railway variables set LLM_ARBITER_ENABLED=true --service bidiq-backend
railway variables set SUMMARY_WITH_LLM=true --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

### 4.5 Se chave expirou ou foi revogada

```bash
# 1. Gerar nova chave em OpenAI Dashboard
# https://platform.openai.com/api-keys

# 2. Atualizar no Railway
railway variables set OPENAI_API_KEY=sk-... --service bidiq-backend
railway redeploy --service bidiq-backend -y

# 3. Verificar
railway run --service bidiq-backend python3 -c "
import os, openai
client = openai.OpenAI(api_key=os.environ['OPENAI_API_KEY'])
models = client.models.list()
print(f'API Key valida: {len(models.data)} models disponiveis')
"
```

---

## 5. Resolucao

### 5.1 Verificar OpenAI Online Novamente

```bash
# Testar API
curl -s https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | head -c 100

# Verificar rate limit voltou ao normal
curl -s -D - https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4.1-nano", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5}' 2>&1 | grep -i 'x-ratelimit-remaining'
```

### 5.2 Reabilitar Recursos LLM

```bash
railway variables set LLM_ARBITER_ENABLED=true --service bidiq-backend
railway variables set LLM_ZERO_MATCH_ENABLED=true --service bidiq-backend
railway variables set SUMMARY_WITH_LLM=true --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

### 5.3 Verificar Classificacao Pos-Fix

```bash
# Verificar health
curl -s https://api.smartlic.tech/health/ready | jq '.ready'

# Verificar metrics de LLM
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_llm'
```

---

## 6. Prevencao

### Rate Limiting
- Configurar `LLM_RATE_LIMIT_RPM` para 80% do limite contratado (buffer de 20%)
- Monitorar `x-ratelimit-remaining-requests` e alertar se < 20%
- Implementar jitter exponencial entre retries

### Cache
- Classificacoes LLM cacheadas por 24h (mesmo setor + mesmo texto = mesma classificacao)
- Cache hit rate > 50% reduz chamadas OpenAI em 50%
- `smartlic_llm_cache_hits_total` deve ser monitorado

### Budget
- Configurar limite de gastos no OpenAI Dashboard (hard limit mensal)
- Verificar usage semanalmente
- Alertar se usage > 70% do budget mensal

### Fallback
- Testar periodicamente `gerar_resumo_fallback()` em staging
- Garantir que o fallback gera saida aceitavel (nao quebra UI)
- Documentar qualidade do fallback vs LLM

---

## 7. Referencias

- `backend/services/llm_classifier.py` — Classificador LLM com fallback
- `backend/services/resumo_fallback.py` — `gerar_resumo_fallback()`
- OpenAI Status: https://status.openai.com
- OpenAI Rate Limits: https://platform.openai.com/account/limits
- OpenAI Dashboard: https://platform.openai.com/usage
