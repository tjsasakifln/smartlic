# ADR-026: Endpoint Admin para Estado de Circuit Breakers

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @devops
**Issue:** #1919

## Context

Operadores SRE precisavam de acesso ao Redis para visualizar o estado de circuit breakers das APIs externas (PNCP, PCP, ComprasGov, BrasilAPI, IBGE). Isso exigia acesso direto ao Redis e conhecimento dos keyspaces — inseguro e não escalável. Precisávamos de um endpoint admin que expusesse o estado real-time de todos os CBs.

## Decision

Criar `GET /v1/admin/circuit-breakers` como endpoint dedicado, protegido por role `admin:ops`, que agrega estado de todos os circuit breakers via `get_all_circuit_breaker_states()`.

## Alternatives Considered

1. **Dashboard Grafana:** Métricas Prometheus já expõem estado de CB — mas são agregadas e não têm resolução por request.
2. **Redis CLI via bastion:** Exigiria acesso SSH + Redis auth — risco de segurança e complexidade operacional.
3. **Endpoint sem cache:** Optamos por sem cache pois é endpoint de diagnóstico operacional (chamada esporádica).

## Consequences

- **Positivo:** SRE visualiza estado sem acesso Redis; role `admin:ops` alinhada com RBAC granular.
- **Negativo:** Sem cache — cada chamada consulta Redis para todos os CBs; sem histórico/timeline de transições.
- **Mitigação:** Métricas Prometheus já cobrem histórico agregado.

## References

- `backend/routes/admin_circuit_breakers.py` (36 LOC)
- `clients/pncp/circuit_breaker.py` (CB implementations)
