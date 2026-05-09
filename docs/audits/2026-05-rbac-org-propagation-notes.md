# RBAC Org-ID Propagation — Manual Review Notes

**Companion to:** [2026-05-rbac-org-propagation.md](./2026-05-rbac-org-propagation.md) (auto-generated)
**Story:** [RBAC-ORG-002](../stories/2026-05/RBAC-ORG-002-org-role-propagation-completion.story.md)
**Author:** @architect (Aria) + @dev (Dex) + @qa (Quinn) — autonomous YOLO
**Date:** 2026-05-08

---

## TL;DR

**Audit empirical finding:** Of 213 routes audited, the only org-scoped surface
in the codebase is `backend/routes/organizations.py` (8 endpoints, all already
enforced by RBAC-ORG-001). **Zero P0 multi-tenant leaks exist outside that
file.** One P1 finding (`POST /v1/organizations/{org_id}/accept`) is
**by design** — the invitee accepts an invite, so by definition is not yet a
member; ADR `docs/adr/org-rbac.md` mandates `auth-only` here.

The audit script is now a **forward-looking** CI gate (AC3): when a future
story (e.g. shared pipeline-items, org-scoped intel reports) adds `org_id` to
new tables, the gate will block PRs that fail to call `require_org_role`.

---

## AC1 — Audit findings (in detail)

| Severity | Count | Status |
|----------|------:|--------|
| P0 multi-tenant leak | **0** | ✓ no remediation needed |
| P1 escalation risk | 1 | by-design (ADR §accept) |
| P2 read-only org touch | 0 | ✓ |
| OK | 212 | — |

### P1 — `POST /v1/organizations/{org_id}/accept` (by-design)

**Finding:** route accepts `{org_id}` path param without `require_org_role`.

**Why this is correct:**

- `docs/adr/org-rbac.md` line 32 (table row): `POST /v1/organizations/{id}/accept`
  → `Mín role: invitee (auth-only)`. The invitee is, by definition, **not yet
  an accepted member** — applying `require_org_role(MEMBER)` would create a
  catch-22: you can't accept the invite that grants you membership without
  already being a member.
- `services/organization_service.py::accept_invite` performs the cross-check
  internally: it verifies the caller has a `pending` (`accepted_at IS NULL`)
  row in `organization_members` for `(org_id, user_id)` before flipping to
  `accepted_at = NOW()`. A user with no invite row gets a 400 from the
  service layer.
- **Cross-tenant injection test:** `test_rbac_org_cross_tenant.py` does NOT
  cover this endpoint specifically because the audit acceptance is mediated
  by service-layer logic (verified separately in `test_organizations.py`),
  not the role dependency.

**Action:** add to `EXEMPT_FINDINGS` allow-list of the audit script (TBD if
this becomes a CI false-positive in practice). For now, the CI gate ignores
P1 (only P0 blocks merge), so no action needed.

---

## AC2 — P0 fixes applied

**Vacuously satisfied: empirical zero P0 in current codebase.**

The story's hypothesis ("member acessa data de outra org via id-injection
em pipeline/intel_reports/etc.") presumed `org_id` propagation that does not
exist in the current schema:

- `pipeline_items` table: user-scoped only (`user_id`, no `org_id` column)
- `intel_reports`: user-scoped only
- `messages`, `notifications`, `sessions`, `feedback`: all user-scoped
- `observatorio.py`, `*_publicos.py`: public, no auth
- `buscar*`: user-scoped via `current_user.id`

Cross-org data access via path-injection is impossible because the data
is not partitioned by `org_id`. The defence-in-depth here is the **explicit
`.eq("user_id", current_user.id)`** filter pattern (ISSUE-021), already
applied repo-wide.

**Out-of-scope flagged for follow-up (not this PR):** if/when `org_id`
columns are added to user-data tables (e.g. shared pipelines for
consultoria), a sibling story should audit `user_id` propagation under
the same gate.

---

## AC3 — CI gate

**Workflow:** `.github/workflows/audit-org-rbac.yml`

**Behaviour:**

1. Triggers on PRs modifying `backend/routes/**`, `dependencies/org_auth.py`,
   the audit script, or the allow-list.
2. Runs `audit_org_id_propagation.py --ci`.
3. Posts a sticky PR comment with the full markdown report.
4. **Fails the build (exit 1) if any P0 finding exists** outside the
   `EXEMPT_MODULES` allow-list.
5. Allow-list is `backend/scripts/exempt_routes.py::EXEMPT_MODULES`.
   Mutations require @architect + @devops sign-off (analogous to
   `prod-env-blocklist.txt`).

---

## AC4 — Test coverage

**File:** `backend/tests/test_rbac_org_cross_tenant.py` (16 tests, 100% pass).

| Test class | Scenarios | Assertion |
|-----------|----------|-----------|
| `TestCrossTenantNotMember` | 5 (one per role-gated endpoint × Alice→OrgB) | 403 + body contains "membro" |
| `TestCrossTenantPendingInvite` | 3 (caller has pending row, not accepted) | 403 |
| `TestCrossTenantStatusIs403NotLeak` | 5 parametrized (LGPD 403-vs-404 contract) | 403 always |
| `TestCrossTenantOrgIdInjection` | 3 (path-param injection) | 403 (uses path id, not cached) |

**Threat model covered:** Alice OWNER of org A attempts to read/mutate org B
via id-injection in the URL — every role-gated endpoint returns 403.

**Threat model NOT covered (not applicable):** cross-org access via downstream
user-data tables — those are user-scoped, not org-scoped (see AC2 notes).

---

## Score impact (`_reversa_sdd/review-report.md §10.4`)

| Surface | Pre RBAC-ORG-002 | Post RBAC-ORG-002 |
|---------|:---------------:|:-----------------:|
| RBAC-ORG-001 enforcement | 100% (8/8 organizations.py) | 100% |
| Cross-tenant leak audit | absent | **complete** (213 routes) |
| CI gate (forward-looking) | absent | **active** |
| Cross-tenant test coverage | absent | **16 tests** |
| **§10.4 RBAC/Security score** | 80/100 | **85/100** (+5) |

---

## Methodology limits / known false-positives

- **Service-layer enforcement:** The audit looks for `Depends(require_org_role)`
  at the route signature only. If a route enforces via service-layer
  (`organization_service.py::_assert_org_role(...)`) without the dependency,
  it is reported as P1/P0. None observed in current code.
- **Dynamic table names:** `.table(table_var)` where `table_var` is not a
  string literal is not detected. Manual review of `routes/*.py` confirmed
  no such pattern targets `organizations` / `organization_members`.
- **Webhook routers:** `webhooks/stripe.py` is registered separately (not in
  `routes/`); not part of audit scope. Stripe events do carry `org_id` as
  metadata when a customer is org-scoped, but the webhook is signature-gated
  (see DEBT-324) and operates as service-role; no per-user RBAC applies.
