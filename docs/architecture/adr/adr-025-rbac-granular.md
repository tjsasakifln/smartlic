# ADR-025: RBAC Granular para Endpoints Admin

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @dev
**Issue:** #1912

## Context

O sistema de autorização admin era binário — `is_admin: bool` em `profiles` concedia acesso total a todos os endpoints administrativos. Com o crescimento de responsabilidades admin (cache, billing, users, SEO, compliance, ops), o modelo binário tornou-se um risco de segurança: um admin de billing tinha acesso irrestrito a operações de cache ou compliance. Precisávamos de roles granulares com princípio de least privilege.

## Decision Drivers

1. Least privilege: cada admin deve ter apenas as roles necessárias para sua função
2. Backward compatibility: endpoints legados não podem quebrar durante a migração
3. Simplicidade: não introduzir framework externo de autorização

## Decision

Adotar role-based access control (RBAC) com coluna `admin_roles TEXT[]` em `profiles`, validada por factory `require_admin_role(role)` no backend. Oito roles definidas: `admin:users`, `admin:billing`, `admin:cache`, `admin:partners`, `admin:seo`, `admin:ops`, `admin:compliance`, `admin:super`. A role `admin:super` funciona como bypass total.

## Alternatives Considered

1. **Policy-based (Casbin/OpenFGA):** Overengineering para ~8 roles — complexidade desnecessária.
2. **Atributos no JWT:** Roles em claims JWT forçariam re-login após mudança de role — inviável.
3. **Tabela separada de roles:** Mais normalizado, mas adiciona JOIN em todo request admin — optamos por array column.

## Consequences

- **Positivo:** Granularidade sem quebrar endpoints existentes; factory pattern torna a adição de novas roles trivial.
- **Negativo:** Sem UI admin para gerenciamento de roles (apenas SQL direto); audit log de atribuição/remoção não implementado.
- **Mitigação:** Fase 2 planejada para UI admin + audit trail.

## References

- `backend/rbac_granular.py` (36 LOC, factory)
- `backend/admin.py` (reexporta `require_admin_*`)
- Migration: `20260616120000_add_admin_roles_to_profiles.sql`
