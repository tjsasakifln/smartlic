# ADR-034: Estratégia de Versionamento de API

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @pm
**Issue:** #1918

## Context

A API do SmartLic cresceu organicamente sem versionamento formal. Rotas não seguiam prefixo consistente — algumas em `/v1/`, outras em `/`. Isso gerava atrito ao fazer breaking changes: não havia como comunicar depreciação a clientes nem período de transição. Precisávamos de uma estratégia que permitisse evolução sem quebrar clientes existentes.

## Decision

Implementar 3 headers HTTP padrão RFC 8594 nas respostas, gerenciados por middleware em `backend/middleware.py`: `X-API-Version: v1` (versão atual), `Deprecation: true` (endpoints depreciados), `Sunset: YYYY-MM-DD` (data de descontinuação). Política: 90 dias de aviso entre depreciação e remoção; v1 e v2 coexistindo durante transição; breaking changes apenas em major version bump.

## Alternatives Considered

1. **URI-based versioning (`/v1/`, `/v2/`):** Simples, mas polui as URLs e duplica código de roteamento.
2. **Accept header (`application/vnd.smartlic.v1+json`):** Elegante, mas pouco óbvio para clientes REST comuns.
3. **Query parameter (`?version=1`):** Fácil de implementar, mas não segue padrão RFC e não funciona para métodos POST.

## Consequences

- **Positivo:** Headers seguem RFC 8594 (padrão da indústria); middleware único sem modificar rotas existentes; política clara de 90 dias para clientes se adaptarem.
- **Negativo:** Middleware aplicado em poucos endpoints — rollout progressivo; sem changelog automatizado; sem métricas de uso por versão.
- **Mitigação:** Rollout incremental; métricas de adoção por versão planejadas.

## References

- `backend/middleware.py` (DeprecationMiddleware, `X-API-Version` header)
- `docs/architecture/api-versioning.md` (política completa)
- RFC 8594: Deprecation HTTP Header Field
