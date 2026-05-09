# INTEL-REPORT-002-V02-SPEC-001: Spec SDD para Intel Reports v0.2 (RPC sector_uf_intel + PDF generator)

**Priority:** P2
**Effort:** XS (2-4h)
**Squad:** @architect (lead) + @dev
**Status:** InProgress
**Epic:** [INTEL-001](../2026-04/EPIC-RES-BE-2026-Q2.md) (epic Intel Reports one-time products)
**Sprint:** TBD
**Dependências bloqueadoras:** Nenhuma — INTEL-REPORT-002 RPC + PDF shipped (#826, #825 smoke tests)
**Reversa anchor:** `_reversa_sdd/review-report.md §10.1` Intel Reports v0.1 + `state.json refresh_2026_05_08` `INTEL-REPORT-002 RPC sector_uf_intel`

---

## Contexto

INTEL-REPORT-002 (Mapa Setorial UF — produto one-time R$497 Stripe) shipped:
- RPC Postgres `sector_uf_intel` (#826) — agrega contratos por setor × UF × período
- PDF generator (`backend/services/pdf_generator_sector_uf_report.py` + 34 unit tests)
- Smoke tests + 403 ownership fix (#825)

Spec SDD ainda não criada em `_reversa_sdd/specs/`. Doc coverage gap (89% atual). Esta story formaliza contrato RPC + PDF generator output schema.

Memory `project_pmf_blind_spots_2026_05_04`: Intel Reports T0 — DataLake 2M contratos não monetizado historicamente; v0.1 Raio-X Concorrente já shipped, v0.2 é Mapa Setorial.

---

## Acceptance Criteria

### AC1: Spec SDD RPC sector_uf_intel

- [x] `_reversa_sdd/specs/07-intel-report-sector-uf.md` seguindo template specs/01-05
- [x] Seções: Inputs (setor_id, uf, periodo_inicio, periodo_fim) · Output schema (JSONB array agregado) · SQL definition referência (link migration `supabase/migrations/...sector_uf_intel.sql`) · Performance characteristics (p95 latency target, índices used) · Permission boundary (autenticado + ownership check)

### AC2: PDF generator contract

- [x] `_reversa_sdd/specs/07b-intel-pdf-generator.md` (sub-spec) — input dict schema, output PDF byte stream, error modes (RPC empty / ReportLab failure)
- [x] Cross-ref test coverage (`test_pdf_generator_sector_uf_report.py` 34 tests)

### AC3: User flow doc

- [x] `_reversa_sdd/user-stories.md` — adicionar fluxo "Compra Intel Report v0.2" (Stripe checkout → webhook payment → RPC trigger → PDF gen → email delivery → presigned download URL)

### AC4: Code-Spec matrix update

- [x] `_reversa_sdd/code-spec-matrix.md` entry confirmação spec criada

---

## Files

| Arquivo | Ação |
|---------|------|
| `_reversa_sdd/specs/07-intel-report-sector-uf.md` | Create |
| `_reversa_sdd/specs/07b-intel-pdf-generator.md` | Create |
| `_reversa_sdd/user-stories.md` | Edit (1 fluxo novo) |
| `_reversa_sdd/code-spec-matrix.md` | Edit (1 linha) |

---

## Definition of Done

- [x] 2 specs criadas sem invenção (fonte: código + migration + tests)
- [x] Confiança 🟢 CONFIRMADO em todas seções (código existe e shipped)
- [x] User-stories.md novo fluxo cross-ref Stripe + RPC + PDF
- [x] Validate `wc -l` post-write (anti-vapor) — `07-intel-report-sector-uf.md`=141 LOC, `07b-intel-pdf-generator.md`=163 LOC

---

## File List

- **Created:** `_reversa_sdd/specs/07-intel-report-sector-uf.md` (RPC spec, 141 LOC, 🟢 CONFIRMADO)
- **Created:** `_reversa_sdd/specs/07b-intel-pdf-generator.md` (PDF generator sub-spec, 163 LOC, 🟢 CONFIRMADO)
- **Edited:** `_reversa_sdd/user-stories.md` (+US-027 Compra Intel Report v0.2 fluxo end-to-end Stripe→Webhook→ARQ→Storage→Resend)
- **Edited:** `_reversa_sdd/code-spec-matrix.md` (+row spec→code intel-report-sector-uf)
- **Edited:** `docs/stories/2026-05/INTEL-REPORT-002-V02-SPEC-001-spec-sdd.story.md` (Status Ready→InProgress, ACs/DoD checkboxes, File List)

## Dev Notes

- Pricing real do código: **R$147,00** (`backend/schemas/intel_report.py:INTEL_REPORT_PRICES["sector_uf"]=14700` centavos). Story original mencionou R$497 — corrigido nas specs para fonte de verdade (No Invention).
- RPC assinatura real: `sector_uf_intel(p_sector TEXT, p_keywords TEXT[], p_uf TEXT, p_window_months INTEGER DEFAULT 24) RETURNS JSONB` — não `(setor_id, uf, periodo_inicio, periodo_fim)` como hipotetizado na AC1; alinhado ao SQL real.
- PDF generator localização real: `backend/pdf_generator_sector_uf_report.py` (top-level, não `backend/services/`). Tests: `backend/tests/test_sector_uf_intel_pdf.py` (366 LOC, 34 tests confirmados).

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
| 1 | Clear and objective title | ✓ | Spec SDD para Intel Reports v0.2 — produto + escopo doc |
| 2 | Complete description | ✓ | Cita RPC #826 + PDF #825 + 34 unit tests; doc gap identificada |
| 3 | Testable acceptance criteria | ✓ | 4 ACs file-deliverable based |
| 4 | Well-defined scope | ✓ | Doc-only; código shipped |
| 5 | Dependencies mapped | ✓ | Nenhuma (#826, #825 merged) |
| 6 | Complexity estimate | ✓ | XS (2-4h) realista |
| 7 | Business value | ✓ | Doc coverage +2 (gap composite 100%) + monetização one-time documentada |
| 8 | Risks documented | ✓ | Anti-vapor `wc -l` validate; sem invenção (fonte código) |
| 9 | Criteria of Done | ✓ | 3 itens explícitos |
| 10 | Alignment with PRD/Epic | ✓ | Epic #634 intel-reports + Reversa anchor §10.1 |

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-05-08 | 1.0 | Story criada (SM) | @sm |
| 2026-05-09 | 1.1 | PO validation GO 10/10 — Draft → Ready | @po |
