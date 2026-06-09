# Runbook: Stripe Outage

**Documento:** DEC-BIL-GAP-02
**Versao:** 1.0
**Ultima atualizacao:** 2026-06-08

## Sumario

Procedimento para detectar e responder a uma indisponibilidade do Stripe.

## Deteccao Automatica

O health check `GET /v1/health/stripe` detecta automaticamente:

- **Stripe online:** `{"stripe": "ok"}`
- **Stripe unreachable (grace period):** `{"stripe": "unreachable", "since": "<ts>", "grace_remaining_hours": <n>}`
- **Stripe unreachable (>4h):** `{"stripe": "unreachable", "since": "<ts>", "notified": true}`

### Mecanismo

1. `check_stripe_connection()` chama `stripe.Account.retrieve()` com cache de 60s
2. Primeira falha: registra timestamp, log CRITICAL, Sentry `capture_message`
3. Grace period de 4h: acesso mantido (plan_type nao e alterado)
4. Apos 4h offline: notifica founder via email (`tiago.sasaki@gmail.com`)
5. Cooldown de 2h entre notificacoes para evitar spam
6. Estado cross-worker via Redis (fallback InMemoryCache)

## Verificacao Manual

### 1. Verificar status do Stripe

```bash
# Painel de status oficial
https://status.stripe.com

# Dashboard Stripe
https://dashboard.stripe.com
```

### 2. Verificar logs do backend

```bash
# Railway logs
railway logs --service bidiq-backend --tail | grep -i stripe

# Verificar health check
curl -s https://api.smartlic.tech/v1/health/stripe | jq .
```

### 3. Verificar Sentry

- Acessar Sentry > Issues
- Buscar por "Stripe connection lost"
- Verificar fingerprint e timeline

## Passos de Restauracao

### Se Stripe esta com outage confirmado (status.stripe.com)

1. **NAO tome acao imediata** — Stripe e SaaS gerenciado, outages sao resolvidos pelo time deles
2. Monitore o status em https://status.stripe.com
3. O sistema mantem acesso normal durante grace period de 4h
4. Usuarios continuam com `plan_type` atual (nao sao rebaixados)

### Se Stripe esta online mas o health check aponta offline

1. Verificar chave de API:

```bash
# Verificar se STRIPE_SECRET_KEY esta configurada corretamente
railway variables --service bidiq-backend | grep STRIPE_SECRET_KEY
```

2. Verificar conectividade de rede:

```bash
# Testar connectivity
curl -v https://api.stripe.com/v1/account -H "Authorization: Bearer sk_test_..."
```

3. Verificar se a chave expirou ou foi rotacionada no dashboard do Stripe

### Se STRIPE_SECRET_KEY foi rotacionada

1. Gerar nova chave em Stripe Dashboard > Developers > API keys
2. Atualizar no Railway:

```bash
railway variables set STRIPE_SECRET_KEY=sk_live_... --service bidiq-backend
```

3. Redeploy:

```bash
railway redeploy --service bidiq-backend -y
```

4. Verificar health check apos deploy:

```bash
curl -s https://api.smartlic.tech/v1/health/stripe | jq .
```

## Impacto no Sistema

| Funcionalidade | Impacto | Mitigacao |
|---------------|---------|-----------|
| Checkout | Bloqueado | Gateway nao processa pagamentos |
| Assinaturas | Sem alteracao | Stripe gerencia ciclos de cobranca |
| Webhooks | Nao recebidos | Eventos ficam na fila do Stripe ate 3 dias |
| Plan_type | Mantido | "Fail to last known plan" |
| Trial | Normal | Sem dependencia de Stripe |
| Pipeline | Normal | Sem dependencia de Stripe |

## Contatos

- **Founder:** Tiago Sasaki — tiago.sasaki@gmail.com
- **Stripe Support:** https://support.stripe.com
- **Stripe Status:** https://status.stripe.com

## Historico de Incidentes

| Data | Duracao | Causa | Resolucao |
|------|---------|-------|-----------|
| — | — | — | — |
