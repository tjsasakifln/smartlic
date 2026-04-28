# ADR — RBAC-ORG-001: Enterprise-standard organization role enforcement

**Status:** Accepted
**Date:** 2026-04-28
**Authors:** @architect, @dev
**Story:** [docs/stories/2026-04/RBAC-ORG-001-enforce-org-role-dependency.story.md](../stories/2026-04/RBAC-ORG-001-enforce-org-role-dependency.story.md)
**Reversa Audit:** Gap-1 (`_reversa_sdd/review-report.md`)

---

## Context

`backend/routes/organizations.py` exposed eight endpoints that mutated
organization state (invite, remove, update logo, dashboard, etc.) but
only verified that the caller was *authenticated* — never that they
held the required role. Combined with multi-tenant data via
`organization_members`, this allowed any accepted member to:

- Invite arbitrary external email addresses (multi-tenant leak).
- Remove other members (denial-of-service against teammates).
- Read dashboard / billing data the matrix said should be owner-only.

The existing `organization_members.role` column accepted three values
(`owner | admin | member`) but no application code actually compared
role hierarchy. SOC 2 / LGPD compliance reviewers flagged this as a
P1 audit blocker.

We needed an enterprise-grade RBAC layer that:

1. is enforceable in **one place** (a FastAPI dependency) so future
   endpoints can't accidentally skip the check;
2. fails **closed** (insufficient role → 403; unknown user → 404);
3. is **least-privilege by default** (most operations owner-only);
4. preserves **at least one owner per org** (no "orphaned organization"
   state via demotion);
5. produces an **append-only audit trail** for every privileged
   mutation (invite / remove / role-change / transfer-ownership /
   logo-update / etc.);
6. is **forward-compatible** with a future granular permissions table.

---

## Decision

### 1. Canonical role enum

```
owner > member > viewer
```

We **dropped** the legacy `admin` role (privilege-down to `member`).
Rationale: `admin` was never wired to anything meaningful; it duplicated
"owner" in 90% of the codebase and confused auditors. A single
"owner" tier gives unambiguous "who can mutate this org" semantics.

`viewer` is **new**: read-only access for stakeholders who should see
the org dashboard but not the member list (privacy) or perform any
mutations.

### 2. Single FastAPI dependency factory

`backend/dependencies/org_auth.py::require_org_role(min_role: OrgRole)`
returns a fresh dependency callable per call:

```python
@router.delete("/organizations/{org_id}")
async def delete_org(
    org_id: str,
    member = Depends(require_org_role(OrgRole.OWNER)),
):
    ...
```

The callable resolves the user via `require_auth`, looks up
`organization_members.role` (only `accepted_at IS NOT NULL` rows count
— pending invites grant nothing), and compares ordinal roles.

### 3. Enterprise matrix (least-privilege defaults)

| Endpoint                                                    | Min role            |
|-------------------------------------------------------------|---------------------|
| `GET    /v1/organizations/me`                               | (auth)              |
| `POST   /v1/organizations`                                  | (auth)              |
| `GET    /v1/organizations/{id}`                             | viewer              |
| `POST   /v1/organizations/{id}/invite`                      | owner               |
| `POST   /v1/organizations/{id}/accept`                      | (invitee — token)   |
| `DELETE /v1/organizations/{id}/members/{target_id}`         | owner OR self-leave |
| `GET    /v1/organizations/{id}/dashboard`                   | member              |
| `PUT    /v1/organizations/{id}/logo`                        | owner               |
| `PATCH  /v1/organizations/{id}/members/{user_id}/role`      | owner               |
| `POST   /v1/organizations/{id}/transfer-ownership`          | owner               |
| `GET    /v1/organizations/{id}/audit-log`                   | owner               |

**Defaults follow principle of least privilege**: anything that mutates
state or reveals member identities is owner-only. Dashboard requires
`member+` (not `viewer+`) because it includes search-volume telemetry
that isn't appropriate for read-only stakeholders.

### 4. Last-owner invariant

`update_member_role` and the demotion path of `transfer_ownership`
**reject** any change that would drop the org's owner count below 1.
The check is implemented in `services/organization_service.py` rather
than as a SQL CHECK constraint because:

- a CHECK across rows requires a trigger or DEFERRABLE constraint —
  significant Postgres complexity for a single rule;
- the application-layer check produces a friendly error message
  ("transfer ownership first") instead of a low-level constraint
  violation;
- the fail-safe is RLS plus the dependency; even if the application
  check is bypassed, the next handler reading the org as `member` can
  still operate (no broken state, just rare 403s for legit owner
  operations).

### 5. Audit log table

`organization_audit_log` is **append-only** with RLS allowing **only
org owners to SELECT**. `UPDATE` and `DELETE` are revoked from
`authenticated`/`anon` at the GRANT level so even a malicious owner
cannot edit history. The log captures `actor_user_id`,
`target_user_id`, `action`, `old_value`, `new_value`, plus a JSONB
`metadata` column for future fields (IP, user-agent).

Writes happen from the route handlers via
`services.organization_audit.log_org_event(...)`, which **never raises**
(audit is best-effort — never blocks user-facing operations).

### 6. Backfill heuristic + dry-run gate (Risk R1 mitigation)

The migration backfills missing roles via:

```sql
-- For each org_id, the lowest-`invited_at` member becomes owner;
-- everyone else becomes member.
```

This heuristic may misclassify ~5% of orgs whose actual founder was
*not* the first row inserted. Mitigation:
`scripts/rbac_org_001_backfill_dryrun.py --dry-run` queries Supabase
read-only, generates a CSV of every (org_id, user_id, current_role,
proposed_role, reason), and writes it to `artifacts/`. Operators run
this before applying the migration in production, review, and apply
manual `UPDATE` overrides via psql AFTER the migration if necessary.

### 7. Forward-compatibility: `require_org_permission(perm: str)`

A placeholder dependency that takes a string permission name and today
proxies to `require_org_role` via a hard-coded `_PERMISSION_ROLE_FLOOR`
dict. Routes can adopt it now without churn — when the
`organization_permissions` table lands in a future story, the function
body is the only thing that changes.

---

## Consequences

### Positive

- **Audit-ready**: SOC 2 / LGPD reviewers see a single chokepoint
  (`require_org_role`) and an append-only log.
- **Enforce-by-default**: future endpoints get RBAC by adding one
  `Depends(...)` line; forgetting it is visible at code review.
- **Test-friendly**: every test patches one helper
  (`dependencies.org_auth._fetch_membership`); no more chained Supabase
  mocks per test for role checks.
- **Type-safe enum**: `OrgRole` is a `str, Enum` with ordinal `__lt__`
  — no string comparison footguns.

### Negative / Trade-offs

- **Existing tests required updates** — but the change is mechanical
  (add the autouse fixture; existing service-layer mocks still work).
- **Backfill heuristic is a guess** for ~5% of orgs — mitigated by
  dry-run review.
- **Two new migrations** add slight complexity to the deploy pipeline,
  but both are paired with `.down.sql` rollbacks.

### Deferred (NOT in this story)

The story matrix listed 12 endpoints. Four of them (`PATCH org`,
`DELETE org`, `GET billing`, `POST checkout`) are **not yet in
`routes/organizations.py`**. They're deferred to a follow-up story:
adding three new endpoints (transfer-ownership, role PATCH, audit-log)
plus gating the existing eight already meets every explicit AC in the
story (AC1–AC15) without bloating the PR. The RBAC infrastructure is
ready for those endpoints when they ship.

---

## Implementation summary

| Concern | File |
|---------|------|
| Enum + Pydantic models | `backend/schemas/organization.py` |
| FastAPI dependency factory | `backend/dependencies/org_auth.py` |
| Audit logger | `backend/services/organization_audit.py` |
| New service ops (transfer, role update) | `backend/services/organization_service.py` |
| Routes (11 endpoints gated) | `backend/routes/organizations.py` |
| Migration: role backfill + RLS rewrite | `supabase/migrations/20260428100200_*` |
| Migration: audit log table | `supabase/migrations/20260428100300_*` |
| Backfill dry-run | `scripts/rbac_org_001_backfill_dryrun.py` |
| Backend tests (matrix + dep) | `backend/tests/test_organizations_rbac.py`, `backend/tests/test_org_auth_dependency.py` |
| Frontend role badge + 2-step modal | `frontend/components/organizations/{RoleControls,TransferOwnershipModal}.tsx` |
| Frontend members page | `frontend/app/organizations/[id]/members/page.tsx` |
| Frontend tests | `frontend/__tests__/components/OrgMembers.test.tsx` |
