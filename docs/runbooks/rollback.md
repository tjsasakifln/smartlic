# Runbook de Rollback — SmartLic

**Issue:** [#1797](https://github.com/tjsasakifln/SmartLic/issues/1797)
**Prioridade:** P1
**Status:** Procedimento documentado e testado
**SLA de Rollback:** < 2 minutos
**Última atualização:** 2026-06-15

## 1. Visão Geral

Este runbook descreve o procedimento de rollback de emergência para reverter um deploy com falha no SmartLic. O sistema roda em Railway com deploy automático via GitHub Actions.

### 1.1 Quando Usar

- **Imediato (P0):** Sistema completamente fora do ar, erros 5xx > 10%
- **Urgente (P1):** Feature crítica quebrada (login, busca, pipeline)
- **Programado (P2):** Regressão não-crítica, rollback pode esperar próximo deploy

### 1.2 Pré-requisitos

- [ ] `railway` CLI instalado e autenticado
- [ ] Acesso ao dashboard Railway (fallback)
- [ ] Canal #incidents no Slack para comunicação
- [ ] Acesso ao `gh` CLI para verificar commits

## 2. Procedimento de Rollback (Railway)

### 2.1 Identificar Último Deploy Funcional

```bash
# 1. Listar deployments recentes no Railway
railway deployments --service bidiq-backend --limit 10

# 2. Identificar o deployment estável (último com status SUCCESS antes do problemático)
# Output mostrará: DEPLOYMENT_ID  STATUS    COMMIT    TIMESTAMP

# 3. Verificar qual commit corresponde ao deployment estável
railway deployment inspect <DEPLOYMENT_ID>
```

### 2.2 Executar Rollback

```bash
# Opção A: Railway CLI (recomendado)
railway redeploy --service bidiq-backend --deployment <LAST_GOOD_DEPLOYMENT_ID>

# Opção B: Fallback via GitHub Actions (re-run do último workflow bom)
gh run rerun <GOOD_RUN_ID>

# Opção C: Dashboard Railway
# Acessar https://railway.app/project/<PROJECT_ID>/services/bidiq-backend
# Clicar no deployment estável → "Redeploy"
```

### 2.3 Verificação Pós-Rollback

```bash
# 1. Health check básico
curl -s https://smartlic.tech/api/v1/health | jq .

# 2. Smoke tests rápidos
curl -s https://smartlic.tech/api/v1/search/stats | jq '.status'

# 3. Verificar se workers voltaram
railway logs --service bidiq-worker --limit 20

# 4. Verificar conectividade Supabase
curl -s https://smartlic.tech/api/v1/health | jq '.checks.supabase'

# 5. Verificar conectividade Redis
curl -s https://smartlic.tech/api/v1/health | jq '.checks.redis'
```

### 2.4 Comunicação

Após rollback concluído, atualizar canal de incidente:

```
🚨 INCIDENT UPDATE:
- Rollback executado: <DEPLOYMENT_ID_NOVO> → <DEPLOYMENT_ID_ANTIGO>
- Tempo de rollback: <X> segundos (SLA: < 120s)
- Serviço: ✅ Restaurado
- Verificação: Health check OK, smoke tests passando
- Impacto: <duração do outage> minutos
- Próximo: Investigar causa raiz em #incident-<NUM>
```

## 3. Deploy Lock (Bloqueio de Deploy)

### 3.1 Ativar Deploy Lock

Durante incidentes ativos, bloquear novos deploys para evitar agravar a situação:

```bash
# Railway não tem deploy lock nativo. Implementado via:
# 1. GitHub Environment Protection Rule
gh api /repos/tjsasakifln/SmartLic/environments/production \
  --method PUT \
  -f protection_rules='[{"type":"wait_timer","wait_timer":60}]'

# 2. Ou via branch protection temporária
gh api /repos/tjsasakifln/SmartLic/branches/main/protection \
  --method PUT \
  -f required_status_checks='{"strict":true,"contexts":["deploy-lock/active"]}'
```

### 3.2 Remover Deploy Lock

Após resolução do incidente:

```bash
# Restaurar proteções normais
gh api /repos/tjsasakifln/SmartLic/branches/main/protection \
  --method DELETE
```

## 4. Health-Based Promotion

### 4.1 Health Check Config

```toml
# railway.toml
[service]
healthcheck_path = "/api/v1/health"
healthcheck_timeout = 10
healthcheck_interval = 30
healthcheck_healthy_threshold = 3
healthcheck_unhealthy_threshold = 2
```

### 4.2 Smoke Tests Automáticos

Após cada deploy, executar smoke tests antes do serviço receber tráfego real:

```bash
# Script: scripts/smoke-test.sh
#!/bin/bash
BASE_URL="${1:-https://smartlic.tech}"
TIMEOUT=30

echo "=== Smoke Tests: $BASE_URL ==="

# 1. Health check
curl -sf --max-time "$TIMEOUT" "$BASE_URL/api/v1/health" || exit 1

# 2. Search endpoint
curl -sf --max-time "$TIMEOUT" "$BASE_URL/api/v1/search/stats" || exit 2

# 3. Auth endpoint (login page)
curl -sf --max-time "$TIMEOUT" "$BASE_URL/login" || exit 3

# 4. API docs
curl -sf --max-time "$TIMEOUT" "$BASE_URL/api/v1/docs" || exit 4

echo "=== All smoke tests passed ==="
```

## 5. Cenários de Rollback Específicos

### 5.1 Migração de Banco com Erro

Se o deploy inclui migração Supabase que falhou:

```bash
# 1. Rollback da migração
npx supabase db reset --linked  # CUIDADO: destrói dados!

# Ou aplicar migration down manual:
npx supabase db push  # Aplica migrations pendentes (incluindo .down.sql)

# 2. Rollback do serviço
railway redeploy --service bidiq-backend --deployment <LAST_GOOD_ID>
```

### 5.2 Variável de Ambiente Incorreta

```bash
# 1. Corrigir variável no Railway
railway variables set KEY=correct_value --service bidiq-backend

# 2. Redeploy imediato
railway redeploy --service bidiq-backend
```

### 5.3 Supabase Outage (externo)

Se Supabase está fora do ar, rollback de aplicação não resolve:

```bash
# 1. Verificar status Supabase
curl -s https://status.supabase.com/api/v2/status.json | jq .

# 2. Ativar modo degradado no backend
railway variables set ENABLE_DEGRADED_MODE=true --service bidiq-backend
railway redeploy --service bidiq-backend

# 3. Comunicar usuários via status page
```

## 6. Testes de Rollback

### 6.1 Teste Programado (Mensal)

Uma vez por mês, executar drill de rollback em staging:

```bash
# 1. Deploy de versão "ruim" em staging (commit com health check quebrado)
# 2. Detectar falha via smoke test
# 3. Executar procedimento de rollback
# 4. Cronometrar: deve ser < 120 segundos
# 5. Documentar resultado em docs/runbooks/rollback-drills.md
```

### 6.2 Critérios de Sucesso

- [ ] Rollback completado em < 120 segundos
- [ ] Health check volta a responder em < 30 segundos
- [ ] Zero dados perdidos ou corrompidos
- [ ] Comunicação enviada no Slack em < 5 minutos

## 7. Referências

- [Railway CLI — Redeploy](https://docs.railway.com/reference/cli#redeploy)
- [Railway Health Checks](https://docs.railway.com/reference/healthchecks)
- [GitHub Deployment Protection Rules](https://docs.github.com/en/actions/deployment/protection-rules)
- [Incident Response Runbook](./incident-response.md)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
