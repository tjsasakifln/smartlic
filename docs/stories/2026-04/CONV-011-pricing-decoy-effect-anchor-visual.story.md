# CONV-011: Pricing page com decoy effect + anchor visual

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Psicologia/Ariely + Cluster Direct Response/Kennedy + Cluster Brasileira/Ladeira)
**Prioridade:** P1 — pricing decisão é gargalo final
**Complexidade:** S (1d implementação + 21d A/B)
**Owner:** @dev + @ux-design-expert
**Tipo:** Frontend / Copy
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

`frontend/app/planos/page.tsx:344-416` atual:
- 3 planos lineares (Mensal/Semestral/Anual) sem destaque visual de "MAIS POPULAR"
- ROI messaging com disclaimer ANTES do número (enfraquece âncora)
- "Comece a Vencer Licitações" + "O SmartLic é um só. Você decide com que frequência..." — paralisia de escolha (Ariely)

**Lift documentado:**
- Get Monetizely: decoy effect com tier ancor → 32% → 84% premium adoption (+163%)
- Ariely *Predictably Irrational*: asymmetric dominance effect → +20-40% mid-tier conversion

**Estratégia consensual:**
- **Mensal R$397** (high-tier, flexível, sem destaque)
- **Anual R$297/mês "MAIS POPULAR"** (decoy âncora — 25% off agressivo, destaque visual)
- **Consultoria R$997/mês** (ultra-premium ancora R$397 como acessível)

---

## Decisão

1. Reordenar visualmente: Mensal | **Anual (DESTAQUE)** | Consultoria
2. Anual com badge "MAIS POPULAR" + destaque colorido + economia em R$ + reframe Sutherland ("R$ 13/dia")
3. ROI messaging reordenado: número PRIMEIRO, disclaimer pequeno DEPOIS
4. Comparativo lado-a-lado com alternativas (planilha/consultor) — anchor concorrência
5. A/B test variant atual (A) vs novo (B) mínimo 21d

---

## Critérios de Aceite

### Layout + Decoy

- [ ] **AC1:** Pricing card Anual com destaque visual:
  - Badge "🔥 MAIS POPULAR" no topo do card
  - Border colorido (primary color)
  - Background sutilmente diferente (tint primary)
  - Tamanho ligeiramente maior (scale 1.05) em desktop
- [ ] **AC2:** Card Anual contém:
  - Preço grande: "R$ 297/mês"
  - Sub-preço: "ou R$ 13/dia (1 cafezinho)" (Sutherland reframe temporal)
  - Economia: "Economize R$ 1.200/ano (3 meses grátis)"
- [ ] **AC3:** Card Consultoria mantido como ultra-premium (R$ 997/mês) — anchor para Pro parecer barato
- [ ] **AC4:** Card Mensal sem destaque, posicionado primeiro à esquerda (ordem importa — anchor primeiro)

### Hero da pricing page

- [ ] **AC5:** Headline reescrita:
  ```
  H1: "Quanto vale 1 edital ganho?"
  Sub: "1 contrato público médio = R$ 150.000.
        Com SmartLic Pro Anual, você paga R$ 13/dia para ver os melhores."
  ```
- [ ] **AC6:** Trial badge mais agressivo:
  ```
  "🔥 14 dias grátis · Sem cartão de crédito · Cancele em 2 cliques"
  ```

### ROI Messaging

- [ ] **AC7:** Bloco ROI reordenado (número PRIMEIRO):
  ```
  R$ 150.000 — valor médio de oportunidade B2G
  R$ 3.564/ano — SmartLic Pro Anual
  ROI = 42x em 1 contrato vencido
  
  *Estimativa baseada em editais típicos do setor.
  ```
  Disclaimer fica em font menor, abaixo, em `<small>` ou rodapé.

### Comparativo de Alternativas

- [ ] **AC8:** Tabela comparativa abaixo dos cards:
  | | Planilha manual | Consultor | SmartLic Pro Anual |
  |---|---|---|---|
  | Tempo gasto/mês | 32h (8h/sem) | 0h | 30min |
  | Custo mensal | R$ 0* | R$ 5.000-15.000 | R$ 297 |
  | Cobertura | Limitada | Variável | Nacional |
  | IA viabilidade | Não | Não | Sim |
  | Histórico | Manual | Variável | 400 dias |
  
  `*custo de oportunidade do tempo`

### A/B Test

- [ ] **AC9:** Variant A (atual) preservada via feature flag `pricing_variant: A | B`
- [ ] **AC10:** Variant B = AC1+AC2+AC5+AC7+AC8 combinados
- [ ] **AC11:** Test runs ≥21d OU n≥200 pricing_view events per arm
- [ ] **AC12:** Métrica primária: pricing_view → checkout_complete CVR; secundária: distribuição entre tiers (target +30-40% Anual)
- [ ] **AC13:** Documentado em `docs/experiments/conv-011-pricing-decoy.md`

### Mobile + A11y

- [ ] **AC14:** Mobile: cards stackam verticalmente com Anual no topo (não no meio — em mobile, primeiro = mais visível)
- [ ] **AC15:** WCAG AA contrast preservado nos badges/destaques
- [ ] **AC16:** Lighthouse score `/planos` não degrada

---

## Arquivos Impactados

**Modificados:**
- `frontend/app/planos/page.tsx` — layout + ROI + comparativo
- `frontend/components/billing/PlanCard.tsx` — badge + destaque + sub-preço
- `frontend/components/billing/PlanToggle.tsx` (se existir) — reordenar
- `frontend/lib/feature-flags/pricing-variant.ts` (novo) — A/B toggle
- `frontend/lib/analytics/funnel-events.ts` — adicionar `tier_selected` property em `checkout_view`

**Novos:**
- `docs/experiments/conv-011-pricing-decoy.md`

---

## Riscos

- **R1 (Médio):** Decoy "Consultoria R$997/mês" precisa ter features reais. Memory `feedback_n2_below_noise_eng_theater` aponta defer automação até n≥30. **Mitigação:** confirmar com @pm que Consultoria tier é real (memory: STORY-277/360 documenta R$997/mês). Se não, AC3 substituir por anchor diferente.
- **R2 (Médio):** Reframe "R$ 13/dia (1 cafezinho)" pode soar trivializante para B2G corporate. **Mitigação:** A/B test detecta sentiment via metric proxy (cancel rate); ajustar copy se conversão Anual cresce mas churn pós-checkout cresce também.
- **R3 (Baixo):** Comparativo com "consultor R$ 5.000-15.000" pode ofender consultores (parte do ICP). **Mitigação:** memory: ICP é empresas + consultorias; revisar copy para "consultor terceiro" não ofender consultorias-clientes.
- **R4 (Baixo):** ROI 42x é claim forte. **Mitigação:** AC7 disclaimer presente, AC8 tabela traz contexto.

---

## Dependências

- CONV-001 (instrumentação) Done — `pricing_view`, `checkout_view`, `tier_selected` events
- Stripe webhook funcional para conversion attribution
- Plano Consultoria R$997/mês ativo em produção (verificar `plan_billing_periods` table)

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P1 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Ariely decoy effect +163%. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO com nota**. R3 copy "consultor R$5-15k/mês" pode ofender ICP consultorias-clientes. @ux-design-expert revisar AC8 tabela ANTES de produção (substituir por "consultor terceiro" ou "alternativa manual"). Validar Consultoria tier R$997 ativo em produção (plan_billing_periods). Status Draft → Ready. |
