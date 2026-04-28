# CONV-014: Selo LGPD + 3 cases nominais com número

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Brasileira/Olivetto + Cluster Brand/Miller SB7 social proof)
**Prioridade:** P3 — bloqueada por n≥3 paid customers
**Complexidade:** S (1 dia + permissões)
**Owner:** @copywriter + @pm + @dev
**Tipo:** Frontend / Trust
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

Trust signals B2B Brasil: CNPJ no footer, depoimentos com cargo+empresa+número (1 case nominal > 10 genéricos), selo LGPD (+30% growth case fintech, fonte Privacidade Garantida).

SmartLic atual: 0 cases nominais. Trust signals atuais ("Fontes oficiais verificadas") são anti-claims (defensivos), não autoridade.

**Princípio Cialdini Social Proof + Olivetto emoção invisível:** 1 case real com cargo+empresa+número humaniza e prova mais que 10 testimoniais genéricos.

**Bloqueador empírico:** memory `feedback_n2_below_noise_eng_theater` — n=2 reais. Story só executa quando n≥3 paid customers AND ≥1 disposto a dar permissão de uso de nome.

---

## Decisão

1. Aguardar n≥3 paid customers
2. Outreach manual: pedir permissão para usar nome+cargo+empresa+resultado
3. Estruturar 3 cases formato Cargo + Empresa + Número R$ encontrado + Tempo
4. Posicionar 1 case por surface crítica: landing hero + pricing + signup
5. Adicionar selo LGPD via certificadora (Privacidade Garantida ou similar) no footer + checkout

---

## Critérios de Aceite

### Pré-condição

- [ ] **AC0:** n≥3 paid customers identificados E ≥3 disposto a dar permissão de uso (waiver assinado por email/DocuSign)

### Cases Nominais

- [ ] **AC1:** 3 cases estruturados em `frontend/lib/cases/featured-cases.ts`:
  ```ts
  type Case = {
    name: string;       // "João Silva"
    role: string;       // "Diretor Comercial"
    company: string;    // "Limp&Co Materiais de Limpeza"
    sector: string;     // "Limpeza B2G"
    photoUrl: string;   // foto real, autorizada
    quote: string;      // 1-2 frases, autêntico
    metric: {
      value: string;    // "R$ 240.000"
      label: string;    // "em editais identificados"
      timeframe: string;// "em 30 dias"
    };
    timestamp: string;  // ISO date case foi coletado
  };
  ```
- [ ] **AC2:** 3 cases populados com dados reais (não fictícios) — 1 empresa de cada perfil distinct (idealmente: 1 PME, 1 média, 1 consultoria)
- [ ] **AC3:** Cada case tem permissão documentada em `docs/legal/case-waivers/{case_id}.pdf` (waiver assinado autorizando uso de nome+empresa+foto)

### Posicionamento

- [ ] **AC4:** Landing hero: bloco social proof abaixo do hero CTA com Case 1
  ```
  [Foto] "frase de 1-2 linhas." — Nome, Cargo, Empresa
  R$ 240.000 em editais identificados em 30 dias
  ```
- [ ] **AC5:** Pricing page (`/planos`): Case 2 abaixo do bloco ROI
- [ ] **AC6:** Signup page: Case 3 lateral ou abaixo do form (não competir com CTA)

### Selo LGPD

- [ ] **AC7:** Contratar certificação LGPD (Privacidade Garantida, OneTrust ou similar) — orçamento ~R$ 2-5k/ano (validar com @pm)
- [ ] **AC8:** Selo visual no footer global + checkout page
- [ ] **AC9:** Página `/lgpd-compliance` documentando práticas (DPO, dados coletados, retenção, direitos do titular)
- [ ] **AC10:** Link selo aponta para certificado público da certificadora

### Tracking

- [ ] **AC11:** Mixpanel event `case_view` (impression) e `case_interaction` (click no nome/empresa) por surface
- [ ] **AC12:** Mixpanel event `lgpd_seal_click` (interesse em compliance)

### Component

- [ ] **AC13:** Componente `<FeaturedCase />` em `frontend/components/social-proof/FeaturedCase.tsx` reutilizável
- [ ] **AC14:** Componente `<LGPDSeal />` em `frontend/components/trust/LGPDSeal.tsx`
- [ ] **AC15:** Tests `frontend/__tests__/components/social-proof/FeaturedCase.test.tsx`

---

## Arquivos Impactados

**Novos:**
- `frontend/lib/cases/featured-cases.ts`
- `frontend/components/social-proof/FeaturedCase.tsx`
- `frontend/components/trust/LGPDSeal.tsx`
- `frontend/app/lgpd-compliance/page.tsx`
- `frontend/__tests__/components/social-proof/FeaturedCase.test.tsx`
- `docs/legal/case-waivers/` — waivers PDF
- `public/cases/` — fotos autorizadas

**Modificados:**
- `frontend/app/page.tsx` — landing inserir Case 1
- `frontend/app/planos/page.tsx` — pricing inserir Case 2
- `frontend/app/signup/page.tsx` — signup inserir Case 3
- `frontend/components/layout/Footer.tsx` — LGPD seal global

---

## Riscos

- **R1 (Alto):** Customers podem recusar permissão de uso (B2G é mercado conservador, expor cliente pode não ser bem visto). **Mitigação:** AC0 bloqueador rígido; alternative offer "anonimizado por setor" se nome bloquear.
- **R2 (Médio):** Custo certificação LGPD recorrente (~R$ 2-5k/ano). **Mitigação:** AC7 validar com @pm orçamento; alternativa free = página /lgpd-compliance autodeclarativa (memory: SmartLic já tem `/privacidade`).
- **R3 (Médio):** Cases envelhecem — número R$ 240k de Q2 não é tão impressionante em Q4. **Mitigação:** AC1 `timestamp` permite rotação trimestral.
- **R4 (Baixo):** Foto real expõe pessoa em mercado B2G fechado. **Mitigação:** AC3 waiver explícito + opção "iniciais + cargo" se foto bloquear.

---

## Dependências

- n≥3 paid customers (memory `feedback_n2_below_noise_eng_theater`)
- @pm valida orçamento certificação LGPD
- Permissões legais (waivers) coletadas
- CONV-001 (instrumentação) Done

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P3 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Cialdini social proof + Olivetto emoção invisível. Bloqueada por n≥3 paid. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 10/10 → **GO**. Gate AC0 (n≥3 paid + waivers) explícito. R1 fallback "anonimizado por setor" pré-pensado. R2 alternativa free página /lgpd-compliance autodeclarativa válida se orçamento bloquear. Status Draft → Ready. |
