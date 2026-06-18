# ADR-032: Sistema de Webhooks Outgoing — Notificações Multicanal

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @devops, @pm
**Issues:** #1522, #1950

## Context

Admins precisavam ser notificados sobre eventos do sistema (falhas de ingestão, alertas de quota, anomalias) mas não havia canal unificado de notificação. Cada evento usava seu próprio mecanismo (Sentry, email direto, sem notificação). Precisávamos de um sistema multicanal configurável por admins, com formatos específicos para cada plataforma.

## Decision

Implementar sistema de webhooks outgoing com 3 canais iniciais: Slack (Block Kit mrkdwn), Teams (Adaptive Cards), Email (HTML via Resend). Configuração via `routes/admin_alerts.py` com proteção RBAC. Disparo via `services/webhook_dispatcher.py`.

## Alternatives Considered

1. **Apenas email (Resend):** Canal universal, mas sem integração real-time com ferramentas de equipe.
2. **Sentry apenas:** Bom para erros técnicos, mas não cobre notificações de negócio (quota, trial expiring).
3. **Serviço terceiro (PagerDuty/Opsgenie):** Custo adicional mensal — inviável no estágio atual.

## Consequences

- **Positivo:** Cada canal com formato nativo (Slack blocks, Teams cards, Email HTML); configuração self-service via endpoint admin; proteção RBAC.
- **Negativo:** Sem retry com backoff para falhas de entrega; sem fila (entrega síncrona no request); sem idempotency key.
- **Mitigação:** Retry + fila planejados para fase 2 após observação de padrões de falha.

## References

- `backend/services/webhook_dispatcher.py` (dispatcher multicanal)
- `backend/routes/admin_alerts.py` (configuração)
- Slack: Block Kit (mrkdwn), Teams: Adaptive Cards, Email: Resend
