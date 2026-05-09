# Dependency Security Scanning

Runbook for the dependency CVE gates. Closes [#193](https://github.com/tjsasakifln/SmartLic/issues/193) (TD-GTM-004).

## Overview

Two complementary CI workflows protect production from vulnerable dependencies:

| Workflow | File | Vuln source | Schedule | Scope |
|----------|------|-------------|----------|-------|
| **Dep Scan** (DEBT-08) | `.github/workflows/dep-scan.yml` | PyPI advisories + npm registry | Weekly (Mon 08:00 UTC) + on dep PRs + push to `main` | HIGH/CRITICAL gate |
| **Dependency Audit (OSV)** | `.github/workflows/dependency-audit.yml` | OSV.dev + npm registry | **Daily (07:00 UTC)** + on dep PRs | Strict (any severity for backend, HIGH+ for frontend) |

The OSV workflow runs daily so a CVE disclosed against an already-merged dependency surfaces within 24 hours instead of waiting for the next dep-changing PR.

Dependabot (`.github/dependabot.yml`) opens grouped weekly PRs (minor + patch combined) for `pip` (`/backend`), `npm` (`/frontend`), and `github-actions` (`/`).

## How the OSV workflow runs

1. **Backend (`pip-audit`):** installs `pip-audit==2.9.0`, runs `pip-audit -r backend/requirements.txt --strict --vulnerability-service osv --format json`. JSON report uploaded as artifact `pip-audit-osv-report` (30d retention).
2. **Frontend (`npm-audit`):** `npm ci --ignore-scripts` then `npm audit --audit-level=high --omit=dev`. JSON uploaded as `npm-audit-report`.
3. **Gate (`dependency-audit-gate`):** fails if either job fails. Required for PR merge once the workflow has run on the PR.

## Triage: pip-audit failure

When `pip-audit` blocks a PR:

1. **Read the JSON artifact** from the failed run (`Actions → Dependency Audit (OSV) → run → artifacts → pip-audit-osv-report`). Each entry has `id` (e.g. `GHSA-xxxx-xxxx-xxxx` or `PYSEC-2024-NN`), `description`, `fix_versions`, and the affected package.
2. **Check fix availability:**
   - **Fix available:** bump the pinned version in `backend/requirements.txt`. If it's a transitive dependency, bump the parent or pin the transitive dep directly.
   - **No fix yet:** confirm exploitability against our actual usage. If non-applicable (CVE in a code path we don't call), proceed to whitelist.
3. **Whitelist (temporary):** add `--ignore-vuln <ID>` to the `pip-audit` step in `.github/workflows/dependency-audit.yml`, with an inline comment containing the rationale, link to upstream advisory, and a follow-up issue number. **Cap at 3 simultaneous ignores** — if more accumulate, open a security debt epic.
4. **Track:** open a follow-up issue tagged `security` + `dependencies` listing the ignored CVE, expected fix ETA, and review date.

Example ignore syntax:

```yaml
- name: Run pip-audit (OSV, strict)
  run: |
    pip-audit \
      -r backend/requirements.txt \
      --strict \
      --vulnerability-service osv \
      --ignore-vuln GHSA-xxxx-xxxx-xxxx \  # Issue #NNN — non-exploitable, awaiting upstream fix (review YYYY-MM)
      --desc on \
      --format json \
      --output audit-reports/pip-audit.json
```

## Triage: npm audit failure

1. **Read the JSON artifact** (`npm-audit-report`). For each `vulnerabilities` entry check `severity`, `via`, `fixAvailable`.
2. **`fixAvailable: true` and non-breaking:** run `cd frontend && npm audit fix`, commit `package-lock.json`.
3. **`fixAvailable` requires major bump:** evaluate breaking changes; if blocked, file an issue and add a per-package allow-list via `npm audit --audit-level=critical` (raise the gate temporarily) **only with code-owner approval**. Document in `CHANGELOG.md`.
4. **Dev-only deps:** the gate already excludes them via `--omit=dev`. The legacy `dep-scan.yml` runs an advisory dev-deps pass.

## How to update the workflow

- **Bump pip-audit:** edit `pip install 'pip-audit==X.Y.Z'` in `dependency-audit.yml`. Pin to specific patch — pip-audit's CLI/JSON shape changed between minor versions historically.
- **Bump Node:** edit `node-version: '20'`. Keep aligned with `dep-scan.yml` and `frontend-tests.yml` to avoid version skew across audits.
- **Change cron:** the `0 7 * * *` daily UTC schedule was chosen to land before the team's working hours (BRT). Adjust in the `on.schedule.cron` field if disclosure→fix latency becomes a problem.
- **Disable temporarily:** comment the `paths:` and `schedule:` triggers (do **not** delete the workflow) and open a tracking issue. Never bypass via branch protection without code-owner sign-off.

## Where things live

- Workflow: `.github/workflows/dependency-audit.yml`
- Legacy / sibling workflow: `.github/workflows/dep-scan.yml`
- Dependabot config: `.github/dependabot.yml`
- Auto-merge config (Dependabot): `.github/workflows/dependabot-auto-merge.yml`
- This runbook: `docs/security/dependency-scanning.md`
