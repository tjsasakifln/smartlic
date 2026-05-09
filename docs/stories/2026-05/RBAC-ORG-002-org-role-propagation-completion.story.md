# RBAC-ORG-002: Org Role Propagation Completion (post RBAC-ORG-001)

**Priority:** P1
**Effort:** M (1-2 dias)
**Squad:** @architect (lead) + @dev + @qa
**Status:** InProgress
**Epic:** [EPIC-TD-2026Q2](EPIC-TD-2026Q2/) — eixo RBAC/security
**Sprint:** TBD
**Dependências bloqueadoras:** [RBAC-ORG-001](../2026-04/RBAC-ORG-001-enforce-org-role-dependency.story.md) Done (8 endpoints `routes/organizations.py` enforced)
**ADR:** [docs/adr/org-rbac.md](../../adr/org-rbac.md)
**Reversa anchor:** `_reversa_sdd/review-report.md §10.4` RBAC/Security 80% (+20 gap to 100%)

---

## Contexto

RBAC-ORG-001 implementou `require_org_role` em 8 endpoints `routes/organizations.py`. **Mas org_id propagation não foi auditada** em endpoints downstream que consomem dados org-scoped:

- `routes/buscar*.py` (search results org-scoped)
- `routes/pipeline*.py` (kanban org-scoped — multi-user dentro de org)
- `routes/exports.py` (Excel/PDF — quem pode exportar?)
- `routes/admin/*.py` (já gated por `is_admin` mas org context?)
- `routes/observatorio.py` + `routes/intel_reports.py` (org-scoped data)

Memory `reference_admin_bypass_paywall`: admin bypass paywall — análogo possível em org-context (member acessa data de outra org via id-injection).

---

## Acceptance Criteria

### AC1: Audit org_id usage

- [X] Script `backend/scripts/audit_org_id_propagation.py` — AST-based, walks routes/*.py recursive
- [X] Output: tabela rota → enforces? (sim/não) → severity (P0 multi-tenant leak / P1 escalation / P2 read-only). Salvo em `docs/audits/2026-05-rbac-org-propagation.md`
- [X] Manual review top-20 endpoints high-traffic — completo. Findings: 0 P0, 1 P1 (by-design accept invitee), 0 P2, 212 OK em 213 rotas auditadas

### AC2: Fix critical leaks

- [X] Para cada route P0 do AC1: zero P0 detectado — schema atual mantém pipeline_items/intel_reports/messages/etc user-scoped (sem `org_id` column). AC2 vacuamente satisfeita; finding documentado em `docs/audits/2026-05-rbac-org-propagation-notes.md`
- [X] Test: cross-org access tentativa retorna 403 (não 404 — leak via timing) — coberto em `TestCrossTenantStatusIs403NotLeak`

### AC3: CI gate audit

- [X] `.github/workflows/audit-org-rbac.yml` — fail PR se nova route org-scoped sem enforcement; sticky PR comment + step summary
- [X] Allow-list arquivo: `backend/scripts/exempt_routes.py::EXEMPT_MODULES` (rotas SEO programmatic, sitemap, health, auth flows, share GET, trial-emails webhook)

### AC4: Test coverage

- [X] `backend/tests/test_rbac_org_cross_tenant.py` — 16 tests cobrindo 4 cenários por endpoint role-gated cross-org
- [X] Coverage: Alice OWNER de orgA tenta GET/POST/PUT/DELETE /v1/organizations/{orgB}/* → 403 (nunca 404, nunca 200)

---

## Files

| Arquivo | Ação | Status |
|---------|------|--------|
| `backend/scripts/audit_org_id_propagation.py` | Create | ✅ Done |
| `backend/scripts/exempt_routes.py` | Create (allow-list) | ✅ Done |
| `.github/workflows/audit-org-rbac.yml` | Create | ✅ Done |
| `backend/tests/test_rbac_org_cross_tenant.py` | Create — 16 tests, 100% pass | ✅ Done |
| `docs/audits/2026-05-rbac-org-propagation.md` | Create (auto-generated audit report) | ✅ Done |
| `docs/audits/2026-05-rbac-org-propagation-notes.md` | Create (manual review notes) | ✅ Done |
| `_reversa_sdd/review-report.md` | Edit §10 — score +5 RBAC/Security | ✅ Done |
| `backend/routes/{multiple}.py` | Edit per AC2 findings | N/A (zero P0) |

## File List

- backend/scripts/audit_org_id_propagation.py (new)
- backend/scripts/exempt_routes.py (new)
- backend/tests/test_rbac_org_cross_tenant.py (new)
- .github/workflows/audit-org-rbac.yml (new)
- docs/audits/2026-05-rbac-org-propagation.md (new — auto-generated)
- docs/audits/2026-05-rbac-org-propagation-notes.md (new — manual notes)
- _reversa_sdd/review-report.md (edit — §10 added)
- docs/stories/2026-05/RBAC-ORG-002-org-role-propagation-completion.story.md (edit — checkboxes + status)

## Dev Notes

**Premise validation (advisor-gated):** Before substantive work, confirmed via grep + schema reading that `org_id` exists ONLY in `organizations` and `organization_members` tables. Pipeline items, intel reports, messages, sessions, feedback are all user-scoped (`user_id`, no `org_id` column). The story's hypothesis ("member acessa data de outra org via id-injection em pipeline/intel_reports/etc.") presumed schema that wasn't built. AC2 therefore vacuously satisfied — empirical zero P0.

**Pivot to forward-looking gate:** The CI gate (AC3) is the highest-leverage deliverable. When `org_id` eventually propagates to user-data tables (e.g. shared org pipelines, multi-tenant intel reports), the gate blocks any PR that fails to call `require_org_role`.

**Test pattern reused:** `dependency_overrides[require_auth]` + `patch(_ORG_AUTH_GET_SUPABASE)` from `tests/test_rbac_org.py` — same fixture style, no new framework code.

**Key contract asserted:** 403 (not 404) on non-member access. 404 would leak org existence; 403 is LGPD-aligned.

---

## Definition of Done

- [ ] Audit completo top-20 routes
- [ ] Zero P0 leaks unfixed
- [ ] CI gate ativo, zero allow-list creep
- [ ] Test suite green 100%
- [ ] `review-report.md §10.4 RBAC/Security` score atualizado (+5pts target)

---

## PO Validation

**Validated by:** @po (Sarah)
**Date:** 2026-05-09
**Verdict:** GO
**Score:** 10/10
**Status transition:** Draft → Ready

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Org Role Propagation Completion (post RBAC-ORG-001) — escopo explícito |
| 2 | Complete description | ✓ | Lista routes downstream específicas; cita risco multi-tenant LGPD |
| 3 | Testable acceptance criteria | ✓ | AC1 audit script, AC2 fix P0, AC3 CI gate, AC4 test cross-tenant |
| 4 | Well-defined scope | ✓ | Top-20 endpoints high-traffic (cap claro); allow-list pattern para exceções |
| 5 | Dependencies mapped | ✓ | RBAC-ORG-001 Done (precedente) + ADR org-rbac.md |
| 6 | Complexity estimate | ✓ | M (1-2d) realista — audit + fix + tests + CI gate |
| 7 | Business value | ✓ | Sec +5 (gap composite 100%) + LGPD compliance multi-tenant |
| 8 | Risks documented | ✓ | Memory `reference_admin_bypass_paywall` cross-ref (analog risk pattern) |
| 9 | Criteria of Done | ✓ | 5 itens DoD claros (audit + zero P0 + CI + tests + score) |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-TD-2026Q2 RBAC/security + Reversa anchor §10.4 |

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-05-08 | 1.0 | Story criada (SM) | @sm |
| 2026-05-09 | 1.1 | PO validation GO 10/10 — Draft → Ready | @po |
| 2026-05-08 | 1.2 | YOLO autonomous execution: AC1-4 done; advisor-validated pivot — empirical zero P0 outside organizations.py; AC2 vacuamente satisfeita; AC3 forward-looking gate é deliverable principal | @architect+@dev+@qa |
