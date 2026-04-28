# CONV-003: Reescrita hero homepage com awareness ladder + ABT + número

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Clusters Direct Response/Schwartz/Halbert + SaaS Conversion/Wiebe/Dry + Brand/Howell)
**Prioridade:** P1 — visitor→signup é gargalo #1
**Complexidade:** S (1d implementação + 14d A/B test)
**Owner:** @dev + @ux-design-expert
**Tipo:** Frontend / Copy
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

`frontend/app/components/landing/HeroSection.tsx:78-145` — copy atual:

```
H1: "Pare de perder dinheiro"
    "com licitações erradas."
Sub: "O SmartLic analisa cada edital contra o perfil da sua empresa.
      Elimina o que não faz sentido. Entrega só o que tem chance real
      de retorno — com justificativa objetiva."
CTAs: "Ver oportunidades para meu setor" / "Ver como funciona"
Trust: "Fontes oficiais verificadas" / "Critérios objetivos, não opinião" / "Sem dados fabricados"
```

**Falhas detectadas:**
- 0 números (Wiebe Rule of One falha — não específico)
- 0 inimigos nomeados (PNCP.gov manual? consultor R$8k? planilha?)
- Trust signals defensivos (anti-claims)
- Awareness mismatch: assume product-aware, mas 60% do tráfego é problem-aware (entry via SEO programmatic)
- Falha 5-second test (Harry Dry: concrete > abstract, falsifiable > vague)

**Lift documentado:** specificity + number + tribo no hero = +10-30% signup CVR (Wiebe Copyhackers VOC + Dry Marketing Examples).

---

## Decisão

1. Reescrita hero seguindo padrão ABT (Park Howell): "AND/BUT/THEREFORE"
2. Inserir número grande verificável ("R$ 4,2 trilhões em editais" — Lei 14.133 transparência pública)
3. CTA primário com remoção explícita de fricção: "(2 min, sem cartão)"
4. CTA secundário problem-aware: "Ver editais do meu CNAE" (preserva visitor problem-aware)
5. Trust signals reescritos com números falsificáveis
6. A/B test variant atual vs nova mínimo 14d, n≥1000 visitors, decisão p<0.05

---

## Critérios de Aceite

### Copy Nova (Variant B)

- [ ] **AC1:** Hero novo implementado com texto exato:
  ```
  H1: "R$ 4,2 trilhões em editais públicos abertos no Brasil em 2025."
  H2: "Sua empresa precisa ver os 50 que importam — não os 1.500 que não."
  Sub: "SmartLic usa IA para filtrar editais por CNAE, porte e geografia.
        Em 2 minutos você vê as oportunidades reais para sua empresa."
  CTA primário: "Começar análise grátis (2 min, sem cartão)"
  CTA secundário: "Ver editais do meu CNAE"
  ```
- [ ] **AC2:** Trust signals reescritos:
  ```
  ✓ 1.500.000 editais indexados (PNCP, Compras.gov, PCP)
  ✓ 27 estados cobertos
  ✓ 400 dias de histórico
  ```
- [ ] **AC3:** Números trust signals refletem dados reais do DataLake (`pncp_raw_bids` count + `pncp_supplier_contracts` count via API ou static fallback semanal)

### A/B Test

- [ ] **AC4:** Sistema A/B test funcional (50/50 split). Reutilizar GV-001 framework se existente, OU implementar via Mixpanel feature flag (`hero_variant: A | B`).
- [ ] **AC5:** Eventos `hero_view` + `hero_cta_click` taggeam variant
- [ ] **AC6:** Variant atual (A) preservada como fallback; nova (B) ativável via feature flag
- [ ] **AC7:** Test runs ≥14d OU n≥1000 visitors (whichever later)
- [ ] **AC8:** Análise estatística: chi-squared test, decisão por p<0.05
- [ ] **AC9:** Vencedor promovido para 100% via toggle de feature flag (zero deploy)

### Acessibilidade + Performance

- [ ] **AC10:** WCAG AA preservado: contrast ratio H1/H2 ≥4.5:1
- [ ] **AC11:** Lighthouse score landing não degrada (Performance/SEO/A11y vs baseline)
- [ ] **AC12:** Mobile responsive — H1 ≤2 linhas em viewport ≥360px

### Documentação

- [ ] **AC13:** `docs/experiments/conv-003-hero-rewrite.md` documenta:
  - Hipótese
  - Variantes A vs B
  - Resultados (winner, lift, p-value)
  - Decisão final + data de promoção

---

## Arquivos Impactados

**Modificados:**
- `frontend/app/components/landing/HeroSection.tsx` — variant B + integration A/B
- `frontend/lib/feature-flags/hero-variant.ts` (novo) — toggle logic
- `frontend/lib/analytics/funnel-events.ts` — adicionar `variant` property em `hero_view` + `hero_cta_click`

**Novos:**
- `docs/experiments/conv-003-hero-rewrite.md`

---

## Riscos

- **R1 (Alto):** Promessa "2 min" no CTA cria expectativa que TTV deve cumprir. Memory `feedback_supabase_disk_io_root_cause_pattern` aponta backend lento. **Mitigação:** validar TTV mediano <5min via CONV-007 ANTES de promover variant B para 100%. Se >5min, ajustar copy para "5 min" ou esperar fix.
- **R2 (Médio):** A/B test com baixo tráfego (126 clicks GSC 28d) pode ter potência estatística insuficiente. **Mitigação:** AC7 condição mínima n≥1000 visitors OR 14d, accept underpowered se necessário e documentar limitation.
- **R3 (Baixo):** "R$ 4,2 trilhões" é claim verificável mas pode ser questionado. **Mitigação:** linkar fonte (Lei 14.133 transparência) em footnote tooltip ou /sobre.

---

## Dependências

- CONV-001 (instrumentação) Done — `hero_view` + `hero_cta_click` events tracking variant
- Framework A/B test (GV-001 OU implementação ad-hoc via feature flag)
- DataLake counts atualizados (`pncp_raw_bids`, `pncp_supplier_contracts`) para AC3

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P1 do EPIC-CONV-FUNNEL-2026-Q2. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO**. Copy variante B com texto exato + ACs falsificáveis (p<0.05). R1 dependência CONV-007 (TTV) bem-mitigado. Status Draft → Ready. |
