# ADR Lifecycle Review — 2026-05-09

One-shot vigência assessment for every ADR under `docs/adr/`. This document is **not** a permanent process — it is a snapshot at the time `ADR-INDEX-001` (issue [#972](https://github.com/tjsasakifln/PNCP-poc/issues/972)) was implemented.

The goal is to flag **candidates** for status change. No ADR is marked `Superseded` or `Deprecated` in this PR — those decisions require a separate per-ADR review. The follow-up should be:

1. For each candidate listed below, open a tracking issue.
2. Confirm or reject the candidate status with the original owners.
3. Update the ADR's `**Status:**` line (and add `**Superseded By:**` if applicable).
4. Re-run `python scripts/build_adr_index.py` to regenerate `docs/adr/README.md`.

## Assessment

| ADR | Current Status | Vigência Assessment | Notes |
|-----|----------------|---------------------|-------|
| `ADR-ARCH-001-godmodule-split-strategy.md` | Accepted (2026-05-08) | **STILL VIGENT** | Recent (last week). Active execution under EPIC-TD-2026Q2. No superseding decision. |
| `ADR-BILL-SYNC-001-bidirectional-strategy.md` | Accepted (2026-04-28) | **STILL VIGENT** | Bidirectional sync is the canonical Stripe ↔ DB strategy. Implementation tracked under BILL-SYNC-001. |
| `ADR-BIZ-FOUND-002-founding-policy.md` | Accepted (2026-04-28) | **STILL VIGENT (canonical)** | This ADR is the canonical founding-plan policy. **Note:** `founding-plan-canonical.md` covers a related earlier decision and should be reviewed for potential supersede relationship — see candidate below. |
| `ADR-MFA-EXT-001-mandatory-policy.md` | Accepted (2026-04-28) | **STILL VIGENT (canonical)** | Canonical MFA policy. **Candidate:** `mfa-policy.md` (predecessor) may be **superseded by** this ADR. |
| `ADR-PARITY-BE-FE-001-response-model-mandatory.md` | Accepted (2026-05-09) | **STILL VIGENT** | Issued today. Enforces `response_model=` on every FastAPI route. No supersede relationships. |
| `ADR-SEN-BE-001b-service-role-timeout.md` | Accepted (2026-04-28) | **STILL VIGENT** | `service_role` `statement_timeout = 60s` — verified in prod. Companion of SEN-BE-001 (per-query budgets). No supersede relationship. |
| `cron-consolidation.md` | Accepted (2026-04-28) | **VERIFY-IMPLEMENTATION** — likely vigent | `backend/cron/` legacy → `backend/jobs/cron/` ARQ canonical migration tracked under REF-SCALE-002. If migration is fully complete, ADR remains vigent (the decision still binds future cron work). If still in progress, no change. **Action:** confirm ARQ canonical adoption. |
| `founding-plan-canonical.md` | Accepted (2026-04-28) | **SUPERSEDED-CANDIDATE** | Predecessor of `ADR-BIZ-FOUND-002-founding-policy.md`. Both dated 2026-04-28; the formally-IDed `BIZ-FOUND-002` appears to be the canonical replacement. **Candidate for `Superseded by: ADR-BIZ-FOUND-002`** — confirm with @architect. |
| `mfa-policy.md` | Accepted (2026-04-28) | **SUPERSEDED-CANDIDATE** | Predecessor of `ADR-MFA-EXT-001-mandatory-policy.md`. Same date. **Candidate for `Superseded by: ADR-MFA-EXT-001`** — confirm with @architect. |
| `org-rbac.md` | Accepted (2026-04-28) | **STILL VIGENT** | Canonical RBAC enforcement (owner > member > viewer). Implementation tracked under RBAC-ORG-001. No supersede candidate. **Format candidate:** rename to `ADR-RBAC-ORG-001-enforcement.md` for naming consistency (cosmetic, optional). |
| `partner-program.md` | Accepted (2026-05-06) | **STILL VIGENT** | Canonical partner program policy (20% lifetime, last-click 30d, Pix monthly). Recent. **Format candidate:** rename to `ADR-PARTNER-001-program-policy.md` for naming consistency (cosmetic, optional). |

## Summary

| Bucket | Count | ADRs |
|--------|-------|------|
| Still vigent (no action) | 8 | ARCH-001, BILL-SYNC-001, BIZ-FOUND-002, MFA-EXT-001, PARITY-BE-FE-001, SEN-BE-001b, org-rbac, partner-program |
| Superseded-candidate | 2 | `founding-plan-canonical.md`, `mfa-policy.md` |
| Verify-implementation | 1 | `cron-consolidation.md` |
| Deprecated-candidate | 0 | (none) |

## Format Cleanup (Separate Concern)

Independent of vigência: the validator (`scripts/validate_adr_format.py`) currently reports 17 format violations across the 11 ADRs (mostly missing `**Authors:**` / `**Owners:**` lines and missing `## Alternatives Considered` sections). The CI gate runs in **warn-only** mode pending a follow-up PR that brings legacy ADRs into compliance.

This document does **not** propose format edits — only lifecycle assessments. Format cleanup is tracked separately.
