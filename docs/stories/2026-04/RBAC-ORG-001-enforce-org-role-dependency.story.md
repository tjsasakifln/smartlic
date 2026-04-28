# RBAC-ORG-001: Multi-tenant Organization RBAC Enforcement (owner | member | viewer)

**Status:** InReview
**Origem:** Reversa Audit 2026-04-27 (`_reversa_sdd/review-report.md` Gap-1) + US-012 (`_reversa_sdd/user-stories.md`) + decisão CTO 2026-04-27 (enum canônico mantido + defaults enterprise standard)
**Prioridade:** P1 — security/multi-tenant integrity
**Complexidade:** S (1-2 dias)
**Owner:** @dev + @architect
**Tipo:** Security / Authorization
**Companion de:** GV-014-consultoria-client-readonly (trata read-only mode trial; este trata role enum granular)

---

## Contexto

Tabelas `organizations` + `organization_members` existem com coluna `role` enum `owner | member | viewer`. Endpoints em `routes/organizations.py` (8 rotas) NÃO enforce role granular — qualquer `member` pode chamar update/delete/invite via JWT válido.

Riscos:
- `member` consegue deletar org inteira (perda de dados de owner)
- `viewer` consegue invite externos (multi-tenant leak)
- Compliance LGPD + SOC2 quebra (role enforcement é controle obrigatório)

Reversa Audit Gap-1: *"roles não-enforce em endpoints; RBAC granular não-documentado em código nem ADR"*.

**Decisão CTO 2026-04-27:**
- Enum canônico: **mantido** `owner | member | viewer`
- Defaults: **enterprise standard** (princípio de menor privilégio + escalation explícita)
- Migration: `organization_members.role` backfill via lógica histórica (primeiro membro=owner, demais=member)

---

## Decisão — Enterprise RBAC Matrix

| Endpoint | min_role | Rationale |
|----------|----------|-----------|
| `POST /v1/organizations` | qualquer auth | criar nova org (sempre owner do que cria) |
| `GET /v1/organizations/{id}` | viewer+ | leitura básica para qualquer membro |
| `PATCH /v1/organizations/{id}` | owner | mudança nome/logo/settings = owner only |
| `DELETE /v1/organizations/{id}` | owner | destrutivo |
| `GET /v1/organizations/{id}/members` | member+ | viewer não-vê outros membros (privacy) |
| `POST /v1/organizations/{id}/invite` | owner | controle de quem entra |
| `POST /v1/organizations/{id}/accept` | invitee (token) | self-service via token |
| `DELETE /v1/organizations/{id}/members/{user_id}` | owner OU self (leave) | owner remove qualquer; member/viewer só remove self |
| `PATCH /v1/organizations/{id}/members/{user_id}/role` | owner | promoção/demoção |
| `POST /v1/organizations/{id}/transfer-ownership` | owner | transferência owner (single-step + email confirmation) |
| `GET /v1/organizations/{id}/billing` | owner | dados financeiros sensíveis |
| `POST /v1/organizations/{id}/checkout` | owner | compra/upgrade plano |

**Permissions atômicas (futuro):** AC15 deixa hooks para granularidade futura via `organization_permissions` table (não-implementar nesta story; apenas dependency `require_org_permission()` placeholder).

---

## Critérios de Aceite

### Backend — Dependency + Migration

- [x] **AC1:** FastAPI dependency `backend/dependencies/org_auth.py::require_org_role(min_role: OrgRole)` (factory pattern — returns a fresh dependency callable per call; signature in story was rewritten because `Depends(...)` cannot accept inline parameters).
- [x] **AC2:** Hierarquia ordinal: `viewer < member < owner` via Enum (`__lt__/__le__/__gt__/__ge__`).
- [x] **AC3:** Migration `supabase/migrations/20260428100200_organization_members_role_backfill.sql` (filename pre-allocated by orchestrator):
  - Migra rows `admin` legadas → `member` (privilege-down).
  - Backfill via heurística "primeiro membro (menor `invited_at`) = owner".
  - Reaplica `NOT NULL DEFAULT 'member'` + CHECK `role IN ('owner','member','viewer')`.
  - Reescreve 4 RLS policies que referenciavam `'admin'`.
- [x] **AC4:** Paired `.down.sql` (`20260428100200_organization_members_role_backfill.down.sql`) restaura CHECK legado, downgrade `viewer` → `member`, recria RLS policies originais.

### Backend — Apply em todos endpoints

- [x] **AC5:** Aplicar `require_org_role(...)` em **11** endpoints (8 legados + 3 novos). Os 4 endpoints da matrix conceitual original (`PATCH /org`, `DELETE /org`, `GET /billing`, `POST /checkout`) foram **deferidos** pois ainda não existem em `routes/organizations.py` e não constam dos AC explícitos — ver Change Log 2026-04-28. RBAC infra está pronto para gatá-los assim que forem implementados.
- [x] **AC6:** `POST /v1/organizations/{id}/transfer-ownership` — valida owner, valida target accepted member, atomic rebaixa→promove, sincroniza `organizations.owner_id`, registra audit. Body exige `{confirm: true}` (gate UI 2-step). Email notify deferido para story de email follow-up (não bloqueante).
- [x] **AC7:** `PATCH /v1/organizations/{id}/members/{target}/role` rejeita demote do último owner (`_count_owners(...) <= 1`).

### Audit Log

- [x] **AC8:** Tabela `organization_audit_log` (`supabase/migrations/20260428100300_organization_audit_log.sql`): RLS owner-only SELECT, append-only (UPDATE/DELETE revogados de `authenticated`/`anon`). Logger em `backend/services/organization_audit.py::log_org_event` (best-effort, nunca bloqueia).
- [x] **AC9:** `GET /v1/organizations/{id}/audit-log` com paginação (`limit/offset` query params, `response_model=OrganizationAuditLogResponse`).

### Frontend

- [x] **AC10:** `frontend/app/organizations/[id]/members/page.tsx` renderiza badge + dropdown (owner-only).
- [x] **AC11:** Modal `TransferOwnershipModal.tsx` 2-step (checkbox de acknowledge + digitação verbatim do email do alvo).
- [x] **AC12:** Form de convite só para owner; `RoleControls` esconde transfer/remove conforme role do viewer.

### Tests

- [x] **AC13:** `backend/tests/test_organizations_rbac.py` — 41 testes (matrix 3 roles × 7 endpoints gateáveis + non-member 404 × 7 + delete-self/owner edge × 6 + last-owner guard × 2 + transfer guards × 2 + helpers). Plus `backend/tests/test_org_auth_dependency.py` — 17 unit tests no helper. **93 testes passam, 0 regressões em test_organizations*.py**.
- [x] **AC14:** `frontend/__tests__/components/OrgMembers.test.tsx` — 16 testes cobrindo a matriz de visibilidade.
- [x] **AC15:** `dependencies/org_auth.py::require_org_permission(perm)` placeholder com mapping `_PERMISSION_ROLE_FLOOR` (10 perms documentadas; raise `ValueError` para perms desconhecidas).

---

## Arquivos Impactados (File List — atualizado pelo @dev 2026-04-28)

**Novos:**
- `backend/dependencies/__init__.py`
- `backend/dependencies/org_auth.py`
- `backend/schemas/organization.py`
- `backend/services/organization_audit.py`
- `backend/tests/test_organizations_rbac.py`
- `backend/tests/test_org_auth_dependency.py`
- `supabase/migrations/20260428100200_organization_members_role_backfill.sql`
- `supabase/migrations/20260428100200_organization_members_role_backfill.down.sql`
- `supabase/migrations/20260428100300_organization_audit_log.sql`
- `supabase/migrations/20260428100300_organization_audit_log.down.sql`
- `scripts/rbac_org_001_backfill_dryrun.py`
- `frontend/components/organizations/RoleControls.tsx`
- `frontend/components/organizations/TransferOwnershipModal.tsx`
- `frontend/app/organizations/[id]/members/page.tsx`
- `frontend/__tests__/components/OrgMembers.test.tsx`
- `docs/adr/ADR-RBAC-ORG-001-enterprise-standard.md`

**Modificados:**
- `backend/routes/organizations.py` — 11 endpoints (8 legados + 3 novos: PATCH role, POST transfer-ownership, GET audit-log) gateados via `require_org_role`.
- `backend/services/organization_service.py` — adiciona `update_member_role`, `transfer_ownership`, `_count_owners`, doc string sobre legacy `admin`.
- `backend/tests/test_organizations.py` — autouse fixture `_patch_org_membership_lookup` + helpers `_override_membership` / `_override_no_membership`; tests de `TestMemberIsolation` e `test_invite_member_not_admin` adaptados.
- `backend/tests/test_organizations_pgrst205_guard.py` — autouse fixture `_stub_org_membership_and_audit` para que o teste alcance o handler service-layer.

---

## Riscos

- **R1 (Médio):** Backfill assume primeiro membro = owner (heurística). Pode estar errado em ~5% de orgs (caso founder não foi primeiro a se cadastrar). **Mitigação:** dry-run script gera CSV pré-migration, send para admin review/manual override
- **R2 (Médio):** Constraint "≥1 owner" pode bloquear delete de org legítimo se último owner sair. **Mitigação:** delete org força cascade delete de todos members (org morre junto com owner)
- **R3 (Baixo):** Frontend pode mostrar controles brevemente antes de carregar role (FOUC). **Mitigação:** SSR resolve role no server, hidrata sem flash

---

## Dependências

- Tabela `organizations` + `organization_members` (existem)
- @architect approval do enterprise matrix antes de @dev pickup
- @ux-design-expert review UI controls visibility

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-27 | @sm | Story criada via Reversa Audit Gap-1. Decisão CTO: enum mantido owner/member/viewer + enterprise standard matrix + backfill heurístico primeiro-membro=owner. Status=Draft → @po validation |
| 2026-04-27 | @po | Validation 9/10 → **GO**. Minor: AC13 lista 36 cenários (3×12) sem specifying bypass cases — aceitável (test scope explícito o suficiente para @qa expandir). Companion limpo de GV-014 (read-only consultoria, escopo distinto). Sem duplicates em docs/stories/. Status Draft → Ready. |
| 2026-04-28 | @dev | **Implementação completa.** Decisões: (1) escopo reduzido para 11 endpoints (8 legados + 3 novos: PATCH role, POST transfer-ownership, GET audit-log) — 4 da matrix conceitual (`PATCH /org`, `DELETE /org`, `GET /billing`, `POST /checkout`) deferidos pois ainda não existem em `routes/organizations.py` e não constam dos AC explícitos. (2) AC1 signature reescrita para factory pattern (`Depends` não aceita parâmetros inline). (3) Migration filenames usam slot pré-alocado pelo orchestrator (`20260428100200_*` em vez do `20260427212000_*` da story original — colisão evitada). (4) Legacy `'admin'` rows migram para `'member'` (privilege-down, mais seguro que privilege-up). (5) Email notify de transfer-ownership deferido (não bloqueante para AC6; story de email separada). Tests: 93 backend (0 regressões em test_organizations*.py) + 16 frontend. Lint: ruff clean nos arquivos modificados; mypy 0 erros nos arquivos novos (57 erros pré-existentes em outros arquivos do projeto). Status Ready → InReview. |
