# ADR-033: Automação de Segurança e Operações CI/CD

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @devops
**Issues:** #1915, #1917, #1922, #1925

## Context

Quatro lacunas operacionais de segurança identificadas: (1) rotação de secrets era manual e sem periodicidade; (2) ambiente de produção podia divergir de staging sem alerta; (3) resiliência a falhas de Redis e banco nunca era testada; (4) não havia plano formal de penetration test. Precisávamos de automação independente do código da aplicação — scripts e workflows CI/CD.

## Decision

Implementar 4 artefatos: `scripts/rotate-secrets.sh` para rotação automatizada de secrets (Supabase, Stripe, OpenAI, Resend); `.github/workflows/audit-prod-env.yml` para detectar drift staging/produção diariamente; `scripts/chaos/redis_failure.sh` + `db_failover.sh` para experimentos de chaos engineering; `docs/security/penetration-test-plan.md` + `scripts/security/scan.sh` para segurança ofensiva.

## Alternatives Considered

1. **Vault (HashiCorp):** Ideal para secrets, mas infraestrutura adicional em Railway — sem budget.
2. **Terraform drift detection:** Overengineering para 2 ambientes — workflow YAML é suficiente.
3. **Gremlin (chaos engineering):** SaaS pago — scripts bash locais atendem.

## Consequences

- **Positivo:** Automação independente do código da aplicação; audit-prod-env roda como CI gate diário; chaos experiments documentam comportamento esperado sob falha.
- **Negativo:** Secrets rotation sem smoke test pós-rotação; chaos experiments manuais (sem schedule); penetration test plan ainda não executado.
- **Mitigação:** Smoke test pós-rotação e schedule automatizado de chaos planejados.

## References

- `scripts/rotate-secrets.sh` (rotação de secrets)
- `.github/workflows/audit-prod-env.yml` (drift detection)
- `scripts/chaos/redis_failure.sh`, `db_failover.sh`
- `docs/security/penetration-test-plan.md`
