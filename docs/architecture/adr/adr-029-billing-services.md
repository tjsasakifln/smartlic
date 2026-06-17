# ADR-029: Extração de Serviços de Billing

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @dev

## Context

O módulo `routes/billing.py` (383 LOC) continha toda a lógica de billing misturada com definições de rotas FastAPI — checkout, subscription, cancelamento, portal. Isso dificultava testes unitários (dependentes de mocking de request/response FastAPI) e reuso entre rotas. Precisávamos separar a lógica de negócio da camada de apresentação HTTP.

## Decision

Extrair `create_checkout_session()` para `services/billing/checkout.py` e `get_subscription_status()` para `services/billing/subscription.py`, mantendo o router `routes/billing.py` apenas como camada de apresentação (parse request, call service, format response).

## Alternatives Considered

1. **Monólito mantido:** Mais simples, mas viola Single Responsibility e dificulta testes.
2. **Serviço externo de billing:** Stripe já gerencia subscriptions — serviço interno é thin wrapper.
3. **Repository pattern:** Overengineering para apenas 2 funções extraídas — service layer simples é suficiente.

## Consequences

- **Positivo:** Separação de concerns clara; serviços testáveis isoladamente; caminho pavimentado para extrair cancel/update/portal.
- **Negativo:** Apenas checkout + subscription extraídos — billing.py original ainda tem cancel, update, portal; sem injeção de dependência formal (import direto).
- **Mitigação:** Iteração contínua — próximas extrações seguem mesmo padrão.

## References

- `backend/services/billing/checkout.py` (77 LOC)
- `backend/services/billing/subscription.py` (74 LOC)
- `backend/routes/billing.py` (383 LOC — router mantido)
