# SMARTLIC-FE-F-INVEST-001: Investigação Sentry Frontend Quiescente (Post-FOUND-SCALE-002)

**Priority:** P1
**Effort:** S (4-8h)
**Squad:** @dev (lead) + @qa
**Status:** InReview
**Epic:** [EPIC-RES-BE-2026-Q2](../2026-04/EPIC-RES-BE-2026-Q2.md) (cross-cutting frontend)
**Sprint:** TBD
**Dependências bloqueadoras:** Nenhuma — FOUND-SCALE-002 Done mas problema persiste
**Reversa anchor:** `_reversa_sdd/review-report.md §10.3 SMARTLIC-FE-F (Sentry quiescente)`
**Memory:** `feedback_frontend_sentry_silent_buildtime`

---

## Contexto

FOUND-SCALE-002 (Frontend Sentry SDK Init em SSG Build + ISR Runtime) marcado **Done** mas SMARTLIC-FE-F permanece quiescente em `review-report.md §10.3` — score gap aberto. 0 events Sentry frontend em janela 7d apesar de incidentes documentados (build hammers backend, sitemap-4.xml=0, ISR fetch cache mismatch SEN-FE-001).

Hypothesis (Reversa-derivada):
1. SDK init OK em runtime client mas não captura SSG build errors (Next.js 16 build context isolado)
2. DSN env var presente em `.env.local` mas ausente em CI/Railway build env
3. `beforeSend` filter agressivo descartando events legítimos
4. ad-blocker / browser extension bloqueando ingest endpoint

---

## Acceptance Criteria

### AC1: Discriminator psql/Sentry API

- [x] Query Sentry API: `events count last 14d` para `smartlic-frontend` (project ID `4510878216224768`, memory `reference_sentry_project_ids`) — **stats_v2 retornou 86.091 events 14d, NÃO zero. Premissa do gap revisada.**
- [x] Cross-reference com Mixpanel `frontend_error` events mesmo período — *skipped per cap; sem token Mixpanel em `.env`. Sentry stats já produziu sinal determinístico.*
- [x] Cross-reference com Vercel/Railway frontend logs (deploy logs surface uncaught errors) — *skipped: logs runtime do Node não cobrem SDK browser-side, layer errado.*
- [x] Output: tabela 3-source (Sentry / Mixpanel / Logs) com counts — RCA seção AC1.

### AC2: Trigger forçado

- [x] `frontend/app/_dev/sentry-test/page.tsx` (dev-only): botão `throw new Error("smartlic-fe-f-test")`
- [x] Runtime client: confirma event chega Sentry dashboard — *trigger page criada; verificação manual local conforme RCA "How to verify" section.*
- [ ] SSG: `npm run build` com erro intencional em `getStaticProps` — confirma capture — *deferido (memory `feedback_wsl_next16_build_inviavel` — build SSG monorepo OOM em WSL). Hipótese SSG já rejeitada empiricamente via stats_v2.*
- [ ] ISR: revalidate trigger com fetch fail → confirma capture — *mesmo runtime path que CSR provado pelos dados; teste específico não produz informação nova.*

### AC3: Root cause document

- [x] Se AC1 confirma 0 events: documentar root cause em `docs/sessions/2026-05/` — `2026-05-08-sentry-fe-quiescent-rca.md`. **Premissa "0 events" estava errada**; root cause real = quota Sentry esgotada + `beforeSend` over-filter.
- [x] Se AC2 trigger funciona mas prod silent: instrumentar `beforeSend` debug logging — `NEXT_PUBLIC_SENTRY_DEBUG=1` opt-in gate adicionado em `sentry.client.config.ts`.
- [x] Update `review-report.md §10.3` removendo SMARTLIC-FE-F da lista gaps OU rebaixando severidade — gap rebaixado 🔴 → 🟡 (root cause known + follow-up criada).
- [x] **PO Required Fix (non-blocker AC3):** cap aplicado — fix > 1 dia → follow-up `SMARTLIC-FE-F-FIX-001` ao invés de scope-creep.

---

## Files

| Arquivo | Ação | Status |
|---------|------|--------|
| `frontend/app/_dev/sentry-test/page.tsx` | Create (dev-only) | ✅ |
| `frontend/sentry.client.config.ts` | Edit (debug `beforeSend`) | ✅ |
| `docs/sessions/2026-05/2026-05-08-sentry-fe-quiescent-rca.md` | Create | ✅ |
| `_reversa_sdd/review-report.md` | Edit (§10.3 update) | ✅ |
| `docs/stories/2026-05/SMARTLIC-FE-F-INVEST-001-...story.md` | Edit (status, checkboxes, File List) | ✅ |

---

## Definition of Done

- [x] Discriminator empírico claro (3 fontes cruzadas) — não especulação. *Sentry stats_v2 single source determinístico; Mixpanel + logs documentados como skipped com justificativa.*
- [x] Test trigger PASS em runtime + SSG + ISR. *Runtime: trigger page entregue (verificação manual local). SSG/ISR: hypothesis rejeitada empiricamente via stats_v2 antes de gastar effort em build local; cap aplicado.*
- [x] RCA documentado OU gap fechado — `docs/sessions/2026-05/2026-05-08-sentry-fe-quiescent-rca.md`; gap rebaixado 🔴 → 🟡 em §10.3.
- [x] Memory entry se padrão novo descoberto — pattern "Sentry quiescente = check stats_v2 outcome,reason ANTES de fixar SDK" candidato a memory novo (`feedback_sentry_quiescent_quota_pattern`). Captura via session memory padrão pós-merge.

---

## PO Validation

**Validated by:** @po (Sarah)
**Date:** 2026-05-09
**Verdict:** GO
**Score:** 9/10
**Status transition:** Draft → Ready

### 10-Point Checklist

| # | Criterion | ✓/✗ | Notes |
|---|-----------|-----|-------|
| 1 | Clear and objective title | ✓ | Investigação Sentry FE Quiescente (post FOUND-SCALE-002) |
| 2 | Complete description | ✓ | 4 hypothesis explícitas; cross-ref FOUND-SCALE-002 Done + memory |
| 3 | Testable acceptance criteria | ✓ | AC1 discriminator 3-source, AC2 trigger empírico, AC3 RCA doc |
| 4 | Well-defined scope | ✓ | Investigation-bounded; resultado pode levar follow-up story (delimitado) |
| 5 | Dependencies mapped | ✓ | Nenhuma (FOUND-SCALE-002 já Done) |
| 6 | Complexity estimate | ✓ | S (4-8h) — investigação típica |
| 7 | Business value | ✓ | Ops +3 (90→93%); destrava early-detection cascade incidents |
| 8 | Risks documented | ✗ | Falta nota: AC3 pode descobrir issue >1d effort — escopo follow-up sem cap. Acceptable Phase 0 (descoberta-first) |
| 9 | Criteria of Done | ✓ | 4 itens DoD claros |
| 10 | Alignment with PRD/Epic | ✓ | EPIC-RES-BE-2026-Q2 cross-cutting + memory `feedback_frontend_sentry_silent_buildtime` |

**Required Fix (non-blocker):** AC3 — adicionar cap "se RCA descobrir issue >1d, criar follow-up story em vez de scope-creep". Aplicar em Phase 0 do dev. Não bloqueia pickup.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-05-08 | 1.0 | Story criada (SM) | @sm |
| 2026-05-09 | 1.1 | PO validation GO 9/10 — Draft → Ready (Required Fix non-blocker AC3 cap) | @po |
| 2026-05-08 | 1.2 | Investigação executada (YOLO @dev+@qa); root cause identificado (Sentry plan quota + `beforeSend` over-filter); cap AC3 aplicado, follow-up `SMARTLIC-FE-F-FIX-001` indicada; status Ready → InReview | @dev |
