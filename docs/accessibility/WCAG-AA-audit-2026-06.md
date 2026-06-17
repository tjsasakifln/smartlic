# WCAG AA Audit Report — June 2026

> Issue #1926 — WCAG AA Full Audit (P2 accessibility/compliance)

## Methodology

The audit combines automated and manual inspection techniques:

| Method | Tool / Technique | Scope |
|--------|-----------------|-------|
| **Automated** | axe-core Playwright (WCAG 2.1 AA tags) | 10 critical pages, blocking on critical/serious violations |
| **Keyboard** | Tab navigation through all interactive elements | All main flows |
| **Screen reader** | NVDA/VoiceOver patterns in code review | ARIA labels, live regions, roles |
| **Contrast** | CSS variable review against WCAG 2.1 SC 1.4.3/1.4.11 | All text/background combinations |
| **Code review** | Manual inspection of JSX for a11y patterns | All shared components |

## Current Status

**CI gate: PASSING** — The existing axe-core CI gate (`npm run test:a11y`) enforces zero critical/serious violations across 10 critical pages. Color-contrast violations are tracked separately in issue #1901 (requires design-system-level CSS variable changes).

### Known Disabled Rules

Per `e2e-tests/a11y/axe-config.ts`, two axe-core rules are deliberately disabled in the CI gate pending a design-system fix:

| Rule | Severity | Reason | Tracking |
|------|----------|--------|----------|
| `color-contrast` | serious | `text-ink-muted` (#808f9f, ratio 3.11) and `text-brand-blue` (#116dff, ratio 4.24) on `bg-surface-1` (#f7f8fa) both fail 4.5:1. These are Tailwind theme tokens used app-wide. | #1901 |
| `link-in-text-block` | serious | Consequence of color-contrast issue. Links in text blocks inherit insufficient contrast ratios. | #1901 |

## Results by Page

| # | Page | Critical | Serious | Moderate | Notes |
|---|------|----------|---------|----------|-------|
| 1 | `/` (Landing) | 0 | 0 | 2 | Decorative animations, skip-link present |
| 2 | `/login` | 0 | 0 | 1 | Form labels present, error messages linked |
| 3 | `/signup` | 0 | 0 | 2 | Form validation accessible, password strength visible |
| 4 | `/planos` | 0 | 0 | 1 | Pricing cards accessible, tab order logical |
| 5 | `/observatorio` | 0 | 0 | 1 | ISR content, headings hierarchy verified |
| 6 | `/buscar` | 0 | 0 | 3 | Search form labels OK, results aria-live, SSE progress announced |
| 7 | `/pipeline` | 0 | 0 | 2 | Drag-and-drop has screen reader announcements (Portuguese), focus management OK |
| 8 | `/conta` | 0 | 0 | 1 | Account settings accessible, form labels OK |
| 9 | `/onboarding` | 0 | 0 | 2 | Wizard steps accessible, focus moves between steps |
| 10 | `/checkout` | 0 | 0 | 1 | Stripe iframe excluded from analysis |

> Moderate findings are logged for triage but do not block CI. See `docs/testing/a11y-e2e.md` for triage process.

## What Was Fixed

### Skip-to-main-content Links (WCAG 2.4.1)

The root layout (`app/layout.tsx`) has a skip link pointing to `#main-content`. Six pages were missing the `#main-content` target element on their `<main>` wrapper, making the skip link non-functional. This audit fixed:

- `/login` — `app/login/page.tsx`: changed `<div>` to `<main id="main-content">`
- `/signup` — `app/signup/page.tsx`: changed `<div>` to `<main id="main-content">`
- `/planos` — `app/planos/page.tsx`: changed `<div>` to `<main id="main-content">`
- `/onboarding` — `app/onboarding/page.tsx`: changed `<div>` to `<main id="main-content">`
- `/dashboard` — `app/dashboard/page.tsx`: changed `<div>` to `<main id="main-content">`
- `/observatorio` — `app/observatorio/page.tsx`: added `id="main-content"` to `<main>`

### PR Template

Added WCAG AA accessibility checklist to `.github/pull_request_template.md`:

- Keyboard navigation
- ARIA labels for screen readers
- Color contrast (4.5:1 text, 3:1 large)
- Form labels and error messages
- Focus management for modals/drawers
- axe-core CI gate
- Information not conveyed by color alone

## Existing Accessibility Features (Verified)

### Focus Management
- `:focus-visible` with 3px outline + 2px offset (meets WCAG 2.2 AAA 2.4.13)
- All modals use `focus-trap-react` with focus return on close
- BottomNav drawer: focus trap + Escape close + return focus to trigger
- MobileDrawer: focus trap + Escape close
- Programmatic focus on search results heading after search completes

### Keyboard Navigation
- All interactive elements reachable via Tab
- No keyboard traps detected
- Button min-height: 44px (WCAG 2.5.5)
- Form input min-height: 44px
- `prefers-reduced-motion` respected — all animations disabled

### Screen Reader
- `aria-live="polite"` on search results header (`ResultsHeader.tsx`)
- `aria-live="assertive"` on errors (`SearchErrorBanner`, `ErrorDetail`)
- `aria-live="polite"` on UF progress grid
- `aria-live="polite"` on tour step announcements
- Pipeline drag-and-drop: Portuguese `Announcements` for dnd-kit
- `sr-only` utility class for screen reader-only text (setor-hint, loading states)
- `aria-hidden="true"` on all decorative icons

### Forms
- All inputs have associated `<label>` with `htmlFor`
- Error messages linked via `aria-describedby`
- Required fields marked with `required` attribute
- `aria-invalid` on fields with validation errors
- `role="alert"` on error banners

### Color & Visual
- Semantic colors documented with contrast ratios in CSS variables
- Error/success/warning tokens all pass WCAG AA 4.5:1 on all surfaces
- Disabled state tokens pass WCAG AA 4.5:1
- Focus ring 4.51:1 (meets 3:1 UI component requirement)
- Information not conveyed by color alone (icons + text accompany color signals)

### ARIA Landmarks
- `role="search"` on search form
- `role="navigation"` on nav elements with `aria-label`
- `role="dialog"` / `role="alertdialog"` on modals with `aria-modal`
- `role="progressbar"` with `aria-valuenow/min/max`
- `role="tablist"`, `role="tab"` on login method tabs
- `role="menu"`, `role="menuitem"` on dropdown menus
- `role="group"` on pipeline columns with `aria-labelledby`
- `aria-current="page"` on active nav items

### Heading Hierarchy
- Single `<h1>` per page (verified on main routes)
- Logical progression h1 -> h2 -> h3 (no skipping)
- Page titles set via Next.js metadata

## How to Verify

```bash
# Run automated a11y scan on all 10 critical pages
cd frontend && npm run test:a11y

# Specific page scan
cd frontend && npx playwright test e2e-tests/a11y/critical-pages.spec.ts --project=chromium

# View axe-core results (JSON attachments)
# Open playwright-report/index.html in browser
```

## Future Improvements

| Priority | Improvement | Tracking |
|----------|------------|----------|
| P1 | Fix color-contrast tokens (design-system CSS variables) | #1901 |
| P2 | Add automated keyboard navigation e2e tests | Future |
| P2 | Add screen reader e2e tests using `page.evaluate` with aria snapshots | Future |
| P3 | Consider WCAG 2.2 compliance audit (new SCs: 2.4.11-2.4.13 focus, 2.5.7-2.5.8 dragging) | Future |
