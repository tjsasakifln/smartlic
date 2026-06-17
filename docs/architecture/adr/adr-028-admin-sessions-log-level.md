# ADR-028: Admin Session Revocation e Runtime Log Level

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @devops
**Issues:** #1923, #1924

## Context

Duas operações SRE que antes exigiam ações manuais fora do sistema: (1) revogar sessões de um usuário específico exigia acesso ao Supabase + Redis; (2) alterar nível de log para debugging exigia redeploy da aplicação. Ambas são operações frequentes em cenários de incidente que não deveriam depender de acesso à infraestrutura.

## Decision

Criar dois endpoints admin: `POST /v1/admin/sessions/revoke` (role `admin:users`) que limpa sessões no Redis + Supabase, e `POST /v1/admin/log-level` (role `admin:ops`) que altera nível de log em runtime via manipulador do logger raiz.

## Alternatives Considered

1. **Supabase dashboard (SQL direto):** Rápido, mas sem audit trail e sem integração com RBAC granular.
2. **Feature flags (LaunchDarkly):** Overkill para log level toggle — uma simples chave runtime resolve.

## Consequences

- **Positivo:** Operação SRE self-service sem acesso à infraestrutura; testes unitários (217 LOC sessions, 437 LOC log-level) garantem confiabilidade.
- **Negativo:** Session revocation precisa validar consistência Redis/Supabase em cenários de partição; log level não persiste entre deploys.
- **Mitigação:** Log level volta ao default do `logging.yaml` após redeploy — comportamento documentado.

## References

- `backend/routes/admin_sessions.py` (session revocation + list)
- `backend/routes/admin_log_level.py` (runtime log level toggle)
- `test_admin_sessions.py` (217 LOC)
- `test_admin_log_level.py` (437 LOC)
