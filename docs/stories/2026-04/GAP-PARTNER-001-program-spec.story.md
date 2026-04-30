# GAP-PARTNER-001: Partner Program Spec (commission, payout, attribution)

**Priority:** P3
**Effort:** TBD (depende escopo definido pós user-input)
**Squad:** @analyst (spec) → @pm (epic placement)
**Status:** InReview
**Epic:** TBD (existing `EPIC-MON-DIST-2026-04` ou novo)
**Sprint:** Backlog (Sprint 3+)
**Tipo:** Documentation / Spec
**Bloqueado por:** ~~AskUserQuestion~~ ✅ Resolved 2026-04-29 — decisões captadas em memory `project_partner_program_decisions_2026_04_29`. ADR-PARTNER-PROGRAM drafting é AC2 next step.

---

## Contexto

`_reversa_sdd/review-report.md` Gap-3: tables `partners`, `partner_referrals` + `routes/partners.py` admin endpoints **existem** no backend MAS spec funcional não-documentada. Concretamente:

- Commission % (qual taxa? tier-based?)
- Payout cycle (mensal? trimestral?)
- Attribution rules (last-click? first-touch? hybrid?)
- Linking model (referral code? UTM params? cookie persistence?)
- Fraud prevention (KYC partner? min payout?)

Memory `reference_smartlic_baseline_2026_04_24`: pre-revenue (n=2 signups), partner program é P3 backlog até trial→paid pipeline destrava (sm-briefing-100pct §11.2).

---

## Acceptance Criteria (post-user-input)

### AC1: ✅ AskUserQuestion — clarify partner model (RESOLVED 2026-04-29)

**Given** spec não-documentada
**When** @analyst escalou via AskUserQuestion 2026-04-29
**Then** user respondeu (memory `project_partner_program_decisions_2026_04_29`):

| Parâmetro | Decisão |
|-----------|---------|
| **Q1 Commission %** | 20% lifetime |
| **Q2 Payout cycle** | Mensal via Pix dia 5 |
| **Q3 Attribution rule** | Last-click 30d |
| **Q4 Partner KYC** | CPF/CNPJ obrigatório (recibo fiscal) |
| **Q5 Signup mode** | Self-service (sem aprovação manual) |

- [x] User respostas captadas
- [x] Memory entry `project_partner_program_decisions_2026_04_29.md` criado

### AC2: ADR-PARTNER-PROGRAM

**Given** user respostas AC1
**When** @analyst + @pm document
**Then**:

- [x] `_reversa_sdd/adr/PARTNER-PROGRAM-SPEC.md` criado (path final em `_reversa_sdd/adr/`, alinhado ao stack ADR existente):
  - [x] Decision context (Q1-Q5 answers) — ADR §Context + §Decision
  - [x] Commission policy — ADR §Decision.1 (20% lifetime, receita líquida, hold 14d)
  - [x] Attribution algorithm — ADR §Decision.3 (last-click 30d cookie + UTM canônica)
  - [x] Payout flow — ADR §Decision.2 (Pix mensal dia 5, mínimo R$50, rollover)
  - [x] Fraud rules — ADR §Decision.4 (rate-limit IP, e-mail dedup, self-referral check) + §Risks
  - [x] Implementation gates (Stripe Coupon API gated por `PARTNERS_ENABLED`; Pix automation gated >50 parceiros; manual operação inicial) — ADR §Implementation.gates G1-G4

### AC3: Spec funcional `_reversa_sdd/specs/06-partner-program.spec.md`

**Given** ADR resolved
**When** @analyst writes spec
**Then**:

- [ ] User stories Given/When/Then format:
  - "Como afiliado, ao gerar link de referral..."
  - "Como admin, ao revisar payouts..."
  - "Como affiliated user (referee), ao signup..."
- [ ] Mock UI screens (low-fi)
- [ ] API contract (OpenAPI excerpt for new endpoints)
- [ ] Database schema validations (RLS policies novas?)

### AC4: Epic placement

- [ ] Decisão: existing `EPIC-MON-DIST-2026-04` ou novo `EPIC-PARTNER-2026-Q3`
- [ ] @pm aloca capacity
- [ ] Stories children criadas no backlog (TBD count)

---

## Scope

**IN:**
- AskUserQuestion 5 perguntas
- ADR-PARTNER-PROGRAM
- Spec funcional 06
- Epic placement decision
- User stories children (TBD count)

**OUT:**
- Implementation code (out-of-scope; spec only)
- Stripe Connect integration (out-of-scope; spec captures requirement)
- Marketing partner portal UI (out-of-scope)
- Backend `partners` route hardening (separate story)

---

## Definition of Done

- [ ] AC1 user responses captured em memory entry
- [ ] AC2 ADR commited
- [ ] AC3 spec commited
- [ ] AC4 epic placed + stories children criadas
- [ ] PR aprovado @analyst + @pm
- [ ] Change Log atualizado

---

## Dev Notes

### Paths absolutos

- **ADR:** `/mnt/d/pncp-poc/docs/adr/PARTNER-PROGRAM.md` (NEW)
- **Spec:** `/mnt/d/pncp-poc/_reversa_sdd/specs/06-partner-program.spec.md` (NEW)
- **Existing tables ref:** `/mnt/d/pncp-poc/supabase/migrations/` (search `partners` + `partner_referrals`)
- **Existing routes ref:** `/mnt/d/pncp-poc/backend/routes/partners.py`
- **Origem:** review-report.md Gap-3

### Memory references

- `reference_smartlic_baseline_2026_04_24` — pre-revenue P3 priority justification
- `feedback_n2_below_noise_eng_theater` — anti-eng-theater n<5 floor

### User-input questions template

Memory `project_partner_program_decisions_<date>.md` (after answers):

```markdown
## Partner Program Decisions <date>
- Commission: <answer>
- Payout: <answer>
- Attribution: <answer>
- KYC: <answer>
- Signup: <answer>
- Stakeholders: <user> + ...
```

---

## Implementation

**ADR criado:** [`_reversa_sdd/adr/PARTNER-PROGRAM-SPEC.md`](../../../_reversa_sdd/adr/PARTNER-PROGRAM-SPEC.md)

**Decisões consolidadas (memory `project_partner_program_decisions_2026_04_29` → ADR sections):**

| Dimensão | Decisão | ADR Section |
|----------|---------|-------------|
| Comissão | 20% lifetime, receita líquida (excl. trials/refunds/impostos) | §Decision.1 |
| Pagamento | Pix mensal dia 5, mínimo R$50, hold 14d, rollover indefinido | §Decision.2 |
| Atribuição | Last-click 30d (cookie HTTP-only `smartlic_ref` + UTM `?ref=<slug>`) | §Decision.3 |
| Self-service | Sem aprovação manual; CPF/PJ obrigatório; rate-limit + e-mail dedup | §Decision.4 |
| Tracking | Cookie 30d + UTM canônica + Mixpanel events; tabelas `partners`/`partner_referrals`/`partner_payouts` | §Decision.5 |
| Compliance | Termo clickwrap; PF=RPA+IRRF/INSS; PJ=NFS-e; LGPD-aware | §Decision.6 |

**Próximos passos (children backlog — defer Sprint 3+ P3):**

1. AC3 — Spec funcional `_reversa_sdd/specs/06-partner-program.spec.md` (user stories + OpenAPI excerpt + RLS)
2. AC4 — Epic placement (`EPIC-MON-DIST-2026-04` vs novo `EPIC-PARTNER-2026-Q3`)
3. PARTNER-BE-001..003, PARTNER-FE-001..002, PARTNER-OPS-001, PARTNER-LEGAL-001 (ver ADR §Implementation.backlog children)

**Implementation gates (do ADR §Implementation):**

- G1 spec funcional aprovada (AC3)
- G2 epic placement decidido (AC4)
- G3 trial→paid pipeline calibrado (n≥30 paid users — memory `feedback_n2_below_noise_eng_theater`)
- G4 implementation kickoff = G1+G2+G3

---

## Risk & Rollback

| Trigger | Ação |
|---------|------|
| User input não-claro (defer multi-rounds) | Schedule meeting; cap 3 rounds AskUserQuestion |
| Spec aspira escopo enterprise (Stripe Connect) | @pm gates implementação se >2 sprints (defer) |

**Rollback:** spec é doc-only — `git revert` se priorities mudam.

---

## Dependencies

**Entrada:**
- AskUserQuestion (BLOCKING)
- review-report.md Gap-3 reference

**Saída:**
- Permite future implementation epic
- Documentation 100% gap closing

**Paralelas:**
- GAP-ADMIN-RBAC-001 (admin tooling — independente)
- GAP-SETORES-001 (doc fix — independente)

---

## PO Validation

**Validated by:** @po (Pax)
**Date:** 2026-04-29
**Verdict:** GO conditional (Blocked pending user-input)
**Score:** 6/10

| # | Criterion | Status | Notes |
|---|---|---|---|
| 1 | Clear and objective title | OK | Partner Program Spec |
| 2 | Complete description | OK | review-report.md Gap-3 referenced |
| 3 | Testable acceptance criteria | PARTIAL | AC1-AC4 testáveis post-user-input |
| 4 | Well-defined scope | OK | OUT exclude implementation, Stripe Connect, marketing UI |
| 5 | Dependencies mapped | OK | AskUserQuestion BLOCKING explícito |
| 6 | Complexity estimate | TBD | Effort TBD pós-AC1 user responses |
| 7 | Business value | PARTIAL | Pre-revenue P3 — partner program gated até trial→paid pipeline destrava |
| 8 | Risks documented | OK | 2 triggers + cap 3 rounds AskUserQuestion |
| 9 | Criteria of Done | OK | Spec + ADR + epic placement |
| 10 | Alignment with PRD/Epic | OK | EPIC-MON-DIST or new |

### Observations
- Score 6 (não 7+) porque effort TBD + business value pre-revenue P3 — explicitamente aguardar trial→paid pipeline antes de invest.
- Memory `feedback_n2_below_noise_eng_theater` aplicável: anti-eng-theater até n>30 paid users.
- Story útil como placeholder backlog Sprint 3+; não-bloqueia operational.

Status: Blocked (NEEDS USER INPUT — AskUserQuestion 5 perguntas). Não promover Ready até user respostas.

## Change Log

| Data | Versão | Descrição | Autor |
|------|--------|-----------|-------|
| 2026-04-29 | 1.0 | Story criada via batch sm-briefing-100pct §6.1. Status `Blocked` aguardando user-input AC1. NEW story, anti-duplicate grep zero matches em GAP-PARTNER. | @sm (River) |
| 2026-04-29 | 1.1 | PO validation: GO conditional (6/10) Blocked. P3 pre-revenue gated. Status mantém Blocked. | @po (Pax) |
| 2026-04-29 | 1.2 | **AskUserQuestion L-7 RESOLVED.** User-input captado: 20% lifetime / Pix mensal / last-click 30d / self-service CPF-CNPJ. Memory `project_partner_program_decisions_2026_04_29` criado. Status: Blocked → Ready. AC2 ADR-PARTNER-PROGRAM é next step (defer Sprint 3+ P3). | @architect (Aria) |
| 2026-04-29 | 1.1 | **ADR PARTNER-PROGRAM-SPEC criado, decisões L-7 incorporadas.** AC2 completo — `_reversa_sdd/adr/PARTNER-PROGRAM-SPEC.md` documenta 6 decisões (comissão 20% lifetime / Pix mensal dia 5 / last-click 30d / self-service / tracking / compliance) + risks + implementation gates G1-G4 + backlog children. Seção Implementation acrescentada com cross-link ADR. Status: Ready → InReview. AC3 (spec funcional) + AC4 (epic placement) permanecem deferidos Sprint 3+ P3. | @analyst (Alex) |
