# CONV-CTA-002 — Audit and Add CTAs to All Programmatic SEO Templates

**Epic:** EPIC-CONV-DIAG-2026-04-30
**Status:** Draft
**Priority:** T1
**Created:** 2026-04-30
**Depends on:** CONV-CTA-001 (TrackingLink component + pattern validated)

---

## Context

CONV-CTA-001 validated the CTA insertion pattern on `/contratos/orgao/[cnpj]` (4 of top-10 GSC URLs, ~12 clicks/month). This story extends the same `TrackingLink` + hero/footer CTA pattern to the remaining programmatic SEO templates that have organic traffic but zero conversion touchpoints.

---

## Goal

Add hero CTA + footer CTA (using `TrackingLink`) to all high-traffic programmatic SEO page templates. Reuse the visual pattern and UTM structure established in CONV-CTA-001.

---

## Programmatic Templates to Audit

| Template | Route Pattern | Priority |
|----------|--------------|----------|
| Fornecedor | `/cnpj/[cnpj]` and `/fornecedores/[cnpj]` | High |
| Orgao publico | `/orgaos/[slug]` | High |
| Municipio | `/municipios/[slug]` | High |
| Observatorio item | `/observatorio/[slug]` | Medium |
| Observatorio raio-x | `/observatorio/raio-x-*/[id]` | Medium |
| Contratos por setor | `/contratos/[setor]` | Medium |
| Contratos setor × UF | `/contratos/[setor]/[uf]` | Medium |
| Blog contratos | `/blog/contratos/[setor]` | Low |
| Blog licitacoes | `/blog/licitacoes/[setor]` | Low |

---

## Acceptance Criteria

- [ ] AC1 — Each template receives a hero CTA block (below H1/subtitle, above main content)
- [ ] AC2 — Each template receives a footer CTA block (above or replacing LeadCapture secondary)
- [ ] AC3 — All CTAs use `TrackingLink` from `@/components/TrackingLink`
- [ ] AC4 — UTM params follow pattern: `utm_source=programmatic&utm_medium=cta&utm_campaign=conv-cta-002&utm_content={template-slug}&page_{id_type}={id_value}`
- [ ] AC5 — `eventProps` includes `{ cta_name: '{template}_{hero|footer}', placement: 'hero'|'footer', page_{id_type}: id }`
- [ ] AC6 — Page files remain server components (no `'use client'` added to page.tsx)
- [ ] AC7 — Tests added: one test file per template verifying 2 CTAs present + UTM correctness
- [ ] AC8 — `revalidate` values unchanged across all modified templates
- [ ] AC9 — Existing tests pass (0 regressions)

---

## Implementation Notes

- Reuse `TrackingLink` created in CONV-CTA-001 (`frontend/components/TrackingLink.tsx`)
- Visual template: `bg-blue-50 rounded-lg p-6 text-center` (from `/contratos/orgao/[cnpj]`)
- Button: `px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors`
- WCAG: `<section aria-labelledby="{placement}-cta-heading">` + matching `id` on h2
- Mobile touch target: `min-h-[44px]` on the anchor

---

## File List

_(to be filled during implementation)_

- `frontend/app/cnpj/[cnpj]/page.tsx`
- `frontend/app/fornecedores/[cnpj]/page.tsx`
- `frontend/app/orgaos/[slug]/page.tsx`
- `frontend/app/municipios/[slug]/page.tsx`
- `frontend/app/observatorio/[slug]/page.tsx`
- `frontend/app/contratos/[setor]/page.tsx` _(if exists)_
- `frontend/app/contratos/[setor]/[uf]/page.tsx` _(if exists)_
- `frontend/__tests__/contratos/cta-*.test.tsx` _(per template)_
