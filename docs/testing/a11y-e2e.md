# A11y E2E — axe-core Triage Runbook

**Owner:** Frontend / QA
**Issue:** [#276 — TD-FE-027 Missing Accessibility Tests](https://github.com/tjsasakifln/SmartLic/issues/276)
**Last updated:** 2026-05-08

This runbook explains how SmartLic enforces WCAG 2.1 AA at the E2E layer via
[`@axe-core/playwright`](https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright)
and how to triage violations the automated audit reports.

---

## What runs

| Spec | What it covers |
|------|----------------|
| `frontend/e2e-tests/accessibility-audit.spec.ts` | 10 high-traffic pages: `/`, `/login`, `/signup`, `/buscar`, `/dashboard`, `/pipeline`, `/planos`, `/historico`, `/conta`, `/ajuda` |
| `frontend/e2e-tests/dialog-accessibility.spec.ts` | Modal / dialog focus management |
| `frontend/e2e-tests/tour-a11y.spec.ts` | Shepherd.js onboarding tour |
| `frontend/e2e-tests/pipeline-keyboard.spec.ts` (AC6) | Pipeline keyboard nav + axe |

All four import the shared fixture at
`frontend/e2e-tests/fixtures/axe.ts` (or use `AxeBuilder` directly with the
same WCAG 2.1 AA tag set).

CI runs them in `.github/workflows/e2e.yml` and `.github/workflows/tests.yml`
on every PR touching `frontend/**`.

## Severity policy

axe-core ranks each violation with an `impact` field. SmartLic policy:

| Impact | CI behaviour | Action |
|--------|--------------|--------|
| `critical` | **Fail PR** | Must be fixed before merge. No exceptions outside `disableRules`. |
| `serious` | **Fail PR** | Must be fixed before merge. Use `disableRules` only with a tracking issue. |
| `moderate` | Logged | Triaged async into a backlog issue. Does not block merge. |
| `minor` | Logged | Tracked but not actionable unless clustered. |

The fixture `assertNoSeriousViolations` enforces this gate. Raw axe output is
attached to the Playwright HTML report as `axe-<context>.json` so reviewers
can inspect violation details without re-running the test.

## Reading axe output

A violation entry in the JSON attachment looks like:

```json
{
  "id": "color-contrast",
  "impact": "serious",
  "description": "Ensures the contrast between foreground and background colors meets WCAG 2 AA",
  "helpUrl": "https://dequeuniversity.com/rules/axe/4.11/color-contrast",
  "nodes": [
    {
      "html": "<button class=\"btn-primary\">...</button>",
      "target": ["#submit"],
      "failureSummary": "Element has insufficient color contrast of 3.2 (foreground color: #6c757d, background color: #f8f9fa, font size: 14.0pt, font weight: normal). Expected contrast ratio of 4.5:1"
    }
  ]
}
```

Key fields:

- **`id`** — axe rule name. Look it up at the `helpUrl` for fix guidance.
- **`impact`** — drives the gate (see policy above).
- **`nodes[].target`** — CSS selector for the offending element.
- **`nodes[].failureSummary`** — human-readable explanation.

## Fixing vs disabling

**Default: fix it.** Most a11y violations have low-effort fixes:

| axe rule | Typical fix |
|----------|-------------|
| `color-contrast` | Adjust token in `frontend/styles/tokens.css` (validated WCAG AA) |
| `label` | Add `<label htmlFor=...>` or `aria-label` |
| `button-name` | Add visible text or `aria-label` |
| `landmark-one-main` | Wrap page content in `<main>` |
| `region` | Wrap top-level sections in `<section aria-label=...>` |
| `image-alt` | Add `alt=""` (decorative) or `alt="..."` (meaningful) |

**Disable only when:**
1. The violation is in third-party code we don't control (Stripe iframe, Google widgets).
2. There's a tracking issue committed alongside the disable.
3. We've capped at **5 disabled rules total per spec**. More than 5 = stop and ask.

To disable a rule:

```ts
const results = await makeAxeBuilder()
  .disableRules(['color-contrast']) // tracked in #NNNN — Stripe iframe contrast
  .analyze();
```

Always include a comment with the issue number on the same line.

## Excluding selectors

The fixture excludes by default:

```ts
.exclude('iframe[src*="stripe.com"]')
.exclude('iframe[src*="google.com"]')
.exclude('[data-clarity-mask]')
```

Add to `frontend/e2e-tests/fixtures/axe.ts` (not per-spec) when a third-party
embed produces unactionable noise across multiple pages.

## Running locally

```bash
# All a11y specs
cd frontend
npx playwright test accessibility-audit dialog-accessibility tour-a11y

# Single page
npx playwright test accessibility-audit -g "Login"

# Headed (see what axe is auditing)
npx playwright test accessibility-audit --headed
```

The Playwright HTML report (`playwright-report/index.html`) shows attached
axe JSON per failing test for offline triage.

## When the audit fails on a PR

1. Open the Playwright report artifact uploaded by CI.
2. Find the failing page test, expand the attachment `axe-<context>.json`.
3. Filter to `impact: "critical"` or `"serious"` — those are blockers.
4. For each:
   - Match `id` against the table above for typical fixes.
   - Inspect `nodes[].target` to find the component.
   - Fix in `frontend/components/...` or `frontend/app/...`.
5. Re-run locally: `npx playwright test accessibility-audit`.
6. If you cannot fix in this PR (e.g., third-party regression):
   - File a tracking issue with the axe JSON snippet.
   - `disableRules([...])` with comment referencing the issue.
   - Note the disable in the PR body under "Disabled rules".

## Adding new pages to the audit

1. Pick a high-traffic public or authenticated page (top 20 by analytics).
2. Add a new test block to `accessibility-audit.spec.ts` following the
   existing template (mock auth/data → goto → wait for hydration → audit).
3. Set up any required mocks via `helpers/test-utils.ts`.
4. Run locally to confirm zero serious violations before opening a PR.

## References

- axe-core rules: <https://dequeuniversity.com/rules/axe/4.11>
- WCAG 2.1 AA quick reference: <https://www.w3.org/WAI/WCAG21/quickref/>
- axe-core/playwright README: <https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright>
- Existing component a11y units: `frontend/__tests__/a11y/`,
  `frontend/__tests__/viability-badge-a11y.test.tsx`
