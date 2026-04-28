# EPIC-CONV-FUNNEL-2026-Q2: Funnel Conversion Sprint (Persuasion + Psychology)

**Priority:** P0
**Owner:** @sm + @po
**Status:** Ready
**Sprint:** Conversion Funnel Sprint Q2 2026
**Predecessor:** EPIC-CONVERSION-2026-04 (Done — visual valor visível, scope on-page valor)

---

## Contexto

Conselho de Copymasters (55 especialistas, 8 clusters) deliberou em 2026-04-28 sobre por que tráfego SmartLic existe (126 cliques GSC / 9.9k impressões 28d) mas não converte (~2 signups/30d, baseline `reference_smartlic_baseline_2026_04_24`).

**Diagnóstico unânime — 5 falhas convergentes:**

1. **Awareness mismatch (Schwartz):** SEO programmatic atrai problem-aware; landing trata como product-aware
2. **Hero genérico:** 0 números, 0 inimigos nomeados, anti-claims defensivos (falha 5-second test de Wiebe/Dry)
3. **Friction de signup:** sem Google OAuth, CTA "Criar conta" genérico (caso Eleken: 4 campos = +117% completion)
4. **Trial sem achievement loop:** calendar emails -258% vs event-based (Encharge benchmark)
5. **Pricing sem decoy + ROI defensivo:** 3 planos lineares, disclaimer antes do número (Ariely +163% premium com decoy)

**Gap atual estimado:** 2/9.900 = 0.02% visitor→signup CVR. Benchmark daydream: 3.8% mediana SaaS. Gap = ~190x.

**Plano de munição completa:** `/home/tjsasakifln/.claude/plans/levantamentos-recentes-apontam-que-snappy-stardust.md`

---

## Stories deste Epic

| Story | Título | Phase Funnel | Priority | Effort | Lift Esperado | Status |
|-------|--------|--------------|----------|--------|---------------|--------|
| CONV-001 | Instrumentar funil completo Mixpanel + GA4 | mensuração | P0 | M | habilitador | Draft |
| CONV-002 | Definir PQL (Product-Qualified Lead) | mensuração | P2 | S | habilitador | Draft |
| CONV-003 | Reescrita hero homepage (awareness ladder + ABT + número) | visitor→signup | P1 | S+A/B | +10-30% | Draft |
| CONV-004 | Friction reduction signup form (Google OAuth + ≤4 campos + CTA) | visitor→signup | P1 | M | +20-40% | Draft |
| CONV-005 | Pre-Suasion above-the-fold (âncora estatística) | visitor→signup | P2 | S | +5-10% | Draft |
| CONV-006 | Onboarding step copy + motivation microcopy | signup→trial | P1 | S | +5-15% | Draft |
| CONV-007 | TTV tracking + first-analysis dispatch otimizado | signup→trial | P1 | S | +15-25% | Draft |
| CONV-008 | Auditoria trial 6-step (calendar vs achievement triggers) | trial→paid | P1 | S | habilitador | Draft |
| CONV-009 | 3 emails achievement-based novos | trial→paid | P1 | M | +15-25% | Draft |
| CONV-010 | Trial expiry email loss-frame com lista nominal | trial→paid | P2 | M | +10-20% | Draft |
| CONV-011 | Pricing page com decoy effect + anchor visual | decisão | P1 | S+A/B | +20-40% mid-tier | Draft |
| CONV-012 | FAQ pricing com objeção-driven answers | decisão | P2 | S | +5-15% | Draft |
| CONV-013 | Cancel flow com retention dinâmico por motivo | retenção | P2 | M | +10-30% retention | Draft |
| CONV-014 | Selo LGPD + 3 cases nominais com número | trust | P3 | S | +10-30% B2B | Draft |
| CONV-015 | Carta do fundador em /sobre + Liking activation | trust | P3 | S | +5-10% | Draft |

---

## Sprints de Execução

### Sprint 1 — Habilitadores + Quick Wins (~5 dias)
**Meta:** Visibilidade de funil + reduzir fricção #1. Sem CONV-001, A/B testing é cego.

- CONV-001 instrumentação (M — 2d)
- CONV-004 friction signup (M — 1-2d)
- CONV-007 TTV measurement (S — <1d)
- CONV-008 trial email audit (S — 1d)

### Sprint 2 — Comunicação de Valor (~5 dias)
**Meta:** Realinhar copy hero, onboarding, pricing.

- CONV-003 hero rewrite (S — 1d + 14d A/B)
- CONV-006 onboarding microcopy (S — 1d)
- CONV-011 pricing decoy (S — 1d + 21d A/B)
- CONV-005 pre-suasion stats (S — 1d)
- CONV-012 FAQ rewrite (S — 1d)

### Sprint 3 — Trial Nurture + Trust (~7 dias)
**Meta:** Achievement triggers + retention + trust.

- CONV-009 achievement emails (M — 3-5d)
- CONV-010 trial expiry loss-frame (M — 2-3d)
- CONV-013 cancel retention (M — 2-3d)
- CONV-015 carta fundador (S — 1d)

### Sprint 4 — Validação Empírica (post n≥30)
**Meta:** Stories que requerem dados reais.

- CONV-002 PQL definition (S — <1d, requer n≥30)
- CONV-014 LGPD + cases nominais (S — 1d, requer n≥3 paid)

---

## KPIs de Sucesso

| Métrica | Baseline 2026-04 | Meta Sprint 2 | Meta Sprint 3 | Meta Final |
|---------|------------------|---------------|---------------|------------|
| Visitor→signup CVR | 0.02% (2/9.9k) | 0.5% | 1.5% | 3-4% |
| Signup→trial completion | desconhecido | instrumentar | 60% | 75% |
| TTV mediano (signup→1º edital viável) | desconhecido | <5min | <5min | <3min |
| Trial→paid CVR | desconhecido | instrumentar | 8% | 18% (benchmark) |
| Email open rate (trial nurture) | desconhecido | instrumentar | 25% | 35% |
| PQL count semanal | n/a | n/a | definir | crescimento WoW |

---

## Caveats Críticos

1. **n=2 abaixo do noise floor** (memory `feedback_n2_below_noise_eng_theater`). Sprint 1+2 vão por evidência literatura. Sprint 4 espera n≥30.
2. **Mixpanel backend recém-restaurado** (PR #536, memory `reference_mixpanel_backend_token_gap_2026_04_24`). Confirmar events fluindo antes de CONV-001 declarar habilitação.
3. **Loss frame em aquisição = backfire.** Aplicar APENAS em trial→paid e cancel.
4. **Decoy precisa ser crível.** Plano "Consultoria R$997/mês" só ancora se features reais.
5. **TTV é problema de produto.** Backend lento (memory `feedback_supabase_disk_io_root_cause_pattern`) trava CONV-007.
6. **Prometeu "2min" no hero exige delivery.** Validar TTV antes de CONV-003.

---

## Dependências do Epic

- Mixpanel backend funcional (PR #536) — confirmar events em produção antes de CONV-001
- Supabase Auth com Google OAuth provider habilitado (CONV-004)
- ARQ cron + Resend SDK (CONV-008/009/010)
- Stripe webhooks operacionais para conversion tracking (CONV-001)
- Acesso GA4 + Mixpanel admin (CONV-001)

---

## Change Log

| Data | Agente | Mudança |
|------|--------|---------|
| 2026-04-28 | @sm | Epic criado a partir do consenso /copymasters (55 Copymasters, 8 clusters). 15 stories propostas em ordem lift × esforço. Status=Draft → @po validation |
| 2026-04-28 | @po | Epic validation: 15/15 stories aprovadas (min 8/10, mediana 9/10). Sprint sequenciamento sólido (habilitadores Sprint 1 → comunicação Sprint 2 → trial nurture Sprint 3 → validação empírica Sprint 4). Caveats explícitos sobre n=2 baseline. Status Draft → Ready. |
