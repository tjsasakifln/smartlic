# Runbook: Stripe Webhook Failure

**Versao:** 1.0
**Criado:** 2026-06-17
**Owner:** @devops
**Severidade tipica:** SEV2 (impacto direto em receita)
**Diferenca:** `stripe-outage.md` cobre Stripe indisponivel; este runbook cobre **webhooks que falham** mesmo com Stripe online.

---

## 1. Sintomas

### Alertas
- Sentry: `stripe_webhook_errors`, `stripe_webhook_signature_invalid`
- Usuario reporta: "paguei mas nao ativou", "assinatura nao aparece"
- Admin reporta: "usuario preso em trial expirado"
- Stripe Dashboard mostra `Failed deliveries` > 0

### Comportamento Observado
```
Log: "Stripe webhook signature verification failed"
Log: "Unhandled Stripe event type: ..."
Log: "Error processing Stripe webhook: ..."
Health: stripe health check pode mostrar "ok" (Stripe online, mas webhooks falhando)
```

### Impacto no Negocio
| Evento Falho | Consequencia | Urgencia |
|-------------|-------------|----------|
| `checkout.session.completed` | Assinatura nao ativada | CRITICA — receita perdida |
| `invoice.payment_succeeded` | Plano nao estendido | ALTA — churn acidental |
| `invoice.payment_failed` | Nao notificado (grace period) | MEDIA |
| `customer.subscription.updated` | Mudanca de plano nao refletida | ALTA |
| `customer.subscription.deleted` | Cancelamento nao processado | MEDIA |

---

## 2. Diagnostico

### 2.1 Verificar Eventos Falhos no Stripe

```bash
# Listar entregas falhas recentes
curl -s https://api.stripe.com/v1/events?limit=10&delivery_success=false \
  -u "$STRIPE_SECRET_KEY:" | jq '.data[] | {id: .id, type: .type, created: (.created | todate), pending_webhooks: .pending_webhooks, request: .request}'
```

### 2.2 Verificar Endpoint Webhook Configurado

```bash
# Listar webhook endpoints
curl -s https://api.stripe.com/v1/webhook_endpoints \
  -u "$STRIPE_SECRET_KEY:" | jq '.data[] | select(.url | contains("smartlic")) | {url: .url, status: .status, enabled_events: .enabled_events}'

# Verificar se a URL esta correta (aponta para Railway?)
# Esperado: https://api.smartlic.tech/v1/webhooks/stripe
```

### 2.3 Verificar Webhook Secret no Railway

```bash
# Secret esta configurado?
railway variables --service bidiq-backend | grep STRIPE_WEBHOOK_SECRET

# Se vazio ou incorreto: obter do Stripe Dashboard
# Stripe > Developers > Webhooks > (seu endpoint) > Signing secret
```

### 2.4 Verificar Eventos Processados no Supabase

```bash
# Verificar eventos recentes processados
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT event_id, event_type, created_at, status, error_message FROM events_processed ORDER BY created_at DESC LIMIT 20"}' | jq .
```

### 2.5 Verificar Logs do Backend

```bash
# Logs especificos de webhook
railway logs --service bidiq-backend --tail | grep -i "webhook\|stripe"

# Verificar erros de assinatura
railway logs --service bidiq-backend --tail | grep -i "signature\|hmac\|secret"
```

### 2.6 Validar Assinatura Manualmente

```bash
# Se voce tem o payload bruto e o header stripe-signature, validar:
railway run --service bidiq-backend python3 -c "
import os, hashlib, hmac
secret = os.environ['STRIPE_WEBHOOK_SECRET']
# Comparar com o header recebido
print(f'Secret length: {len(secret)}')
"
```

---

## 3. Causas Comuns

| Causa | Indicador | Probabilidade |
|-------|-----------|---------------|
| Webhook secret rotacionado ou incorreto | `signature verification failed` nos logs | Alta |
| URL do endpoint mudou (redeploy mudou URL) | Stripe mostra `webhook_endpoint` com URL errada | Media |
| Handler quebrou (exception em webhook handler) | Logs mostram `Error processing` + stack trace | Media |
| Event type nao registrado no endpoint | Stripe mostra evento nao listado em `enabled_events` | Baixa |
| Event type nao implementado no handler | Logs mostram `Unhandled event type` | Baixa |
| Rate limit Stripe (webhooks concorrentes) | `429 Too Many Requests` nos logs | Baixa |

---

## 4. Mitigacao

### 4.1 Imediata: Reprocessar Webhooks Falhos

```bash
# Opcao 1: Stripe Dashboard (recomendado para poucos eventos)
# Stripe > Developers > Webhooks > Failed deliveries > Retry

# Opcao 2: Stripe CLI (para muitos eventos)
# stripe trigger checkout.session.completed
# Nota: precisa de Stripe CLI instalado localmente
```

### 4.2 Se Webhook Secret incorreto

```bash
# 1. Obter novo secret do Stripe Dashboard
# Stripse > Developers > Webhooks > Seu Endpoint > Reveal signing secret

# 2. Atualizar no Railway
railway variables set STRIPE_WEBHOOK_SECRET=whsec_... --service bidiq-backend

# 3. Redeploy
railway redeploy --service bidiq-backend -y

# 4. Testar
# Stripe Dashboard > Send test webhook
```

### 4.3 Se URL do Endpoint Incorreta

```bash
# 1. Stripe Dashboard > Developers > Webhooks
# 2. Atualizar Webhook URL para: https://api.smartlic.tech/v1/webhooks/stripe
# 3. Receber novo signing secret
# 4. Atualizar no Railway (passo 4.2 acima)
```

### 4.4 Se Handler Quebrou (Exception)

```bash
# Rollback e mais rapido que fix forward
railway rollback --service bidiq-backend

# Se rollback nao for possivel:
# 1. Verificar exception nos logs
# 2. Criar hotfix
# 3. Deploy
```

### 4.5 Emergency: Reconciliacao Manual

Para usuarios que pagaram mas nao tiveram plano ativado:

```bash
# 1. Identificar usuarios afetados
# Stripe Dashboard > Payments > Recent transactions > Verificar usuarios sem plano ativo

# 2. Ativar manualmente via Supabase
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"UPDATE profiles SET plan_type = 'pro', updated_at = NOW() WHERE id = '<user_id>'\"}" | jq .
```

---

## 5. Resolucao

### 5.1 Apos aplicar correcao

```bash
# 1. Testar webhook com evento de teste no Stripe Dashboard
# Stripe > Developers > Webhooks > Send test webhook

# 2. Verificar logs
railway logs --service bidiq-backend --tail | grep -i webhook

# 3. Verificar events_processed no Supabase
curl -s "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT event_id, event_type, created_at, status FROM events_processed ORDER BY created_at DESC LIMIT 5"}' | jq .
```

### 5.2 Reprocessar eventos na fila do Stripe

Stripe reenvia webhooks automaticamente por ate 3 dias com backoff exponencial:

- Primeira tentativa: 5s
- Segunda: 30s
- Terceira: 5 min
- ... ate 3 dias

Apos corrigir o handler, os webhooks falhos serao reprocessados automaticamente. Nao e necessario acao manual a menos que o atraso seja critico.

### 5.3 Se urgente: Reprocessar manualmente

Stripe CLI (recomendado):
```bash
stripe trigger checkout.session.completed
```

Ou via Stripe Dashboard > Developers > Webhooks > Failed deliveries > Retry all.

---

## 6. Prevencao

### Monitoramento
- Alerta Sentry para `stripe_webhook_errors` com dedup de 15 min
- Stripe Dashboard: configurar alerta de `failed webhook deliveries`
- Verificar `events_processed` status `error` diariamente

### Testes
- Teste de integracao que envia webhook de teste e verifica `events_processed`
- Teste de assinatura invalida (secret errado)
- Teste de evento desconhecido (graceful handling)

### Codigo
- Todos os webhook handlers devem ser idempotentes (`event_id` unico)
- Log estruturado: `event_id`, `event_type`, `status` em cada webhook
- Graceful handling para eventos desconhecidos (log + ack, nunca 500)
- Timeout de 30s por webhook (Railway proxy: 120s)

### Stripe Dashboard
- Manter `STRIPE_WEBHOOK_SECRET` em cofre de senhas (1Password)
- Auditar endpoints webhook mensalmente
- Rotacionar secret a cada 90 dias

---

## 7. Referencias

- `stripe-outage.md` — Stripe outage (quando Stripe esta offline)
- `incident-response.md` secao 3.5 — Playbook resumido Stripe Webhook
- `backend/webhooks/handlers/` — Implementacao dos handlers
- Stripe Webhooks Docs: https://stripe.com/docs/webhooks
- Stripe Dashboard: https://dashboard.stripe.com
- Stripe Status: https://status.stripe.com
