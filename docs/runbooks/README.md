# Runbooks — SmartLic SRE

**Ultima atualizacao:** 2026-06-17
**Owner:** @devops
**Issue:** #1960

## Objetivo

Runbooks operacionais para incidentes comuns de producao. Cada documento descreve sintomas, diagnostico, mitigacao, resolucao e prevencao para um incidente especifico.

On-call SRE deve comecar pelo **Runbook de Resposta a Incidentes** (`incident-response.md`) para triagem e severidade, depois navegar para o runbook especifico.

## Runbooks Individuais

| # | Incidente | Severidade Tipica | Arquivo |
|---|-----------|-------------------|---------|
| 1 | Supabase Pool Exhaustion (CRIT-046) | SEV2 (pode escalar SEV1) | `supabase-pool-exhaustion.md` |
| 2 | Redis Connection Failure | SEV2 (pode escalar SEV1) | `redis-connection-failure.md` |
| 3 | PNCP API Breaking Change | SEV2 | `pncp-api-breaking-change.md` |
| 4 | Stripe Webhook Failure | SEV2 | `stripe-webhook-failure.md` |
| 5 | Railway Deploy Stuck | SEV2 | `railway-deploy-stuck.md` |
| 6 | OpenAI Rate Limit / Outage | SEV3 (pode escalar SEV2) | `openai-rate-limit-outage.md` |
| 7 | High Error Rate on /buscar | SEV1 | `high-error-rate-buscar.md` |

## Runbooks Relacionados

| Documento | Descricao |
|-----------|-----------|
| `incident-response.md` | Matriz de severidade, fluxo de resposta, triagem, playbooks resumidos |
| `general-outage.md` | Outage generico — checklist dos primeiros 5 minutos |
| `rollback-procedure.md` | Procedimento completo de rollback backend + frontend |
| `stripe-outage.md` | Stripe outage (diferente de webhook failure) |
| `PNCP-TIMEOUT-RUNBOOK.md` | Timeout especifico PNCP por UF |
| `monitoring-alerting-setup.md` | Setup de monitoramento e alertas |
| `audit-prod-env.md` | Auditoria de ambiente de producao |

## Como Usar

1. Recebeu um alerta? Abra `incident-response.md` primeiro
2. Identificou o cenario especifico? Navegue para o runbook correspondente
3. Siga os passos de diagnostico e mitigacao na ordem
4. Apos resolucao, crie post-mortem em `docs/incidents/` (SEV1/SEV2)
5. Atualize este README se adicionar novo runbook
