# CONV-012: FAQ pricing com objeção-driven answers

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Direct Response/Bencivenga reason-why + Cluster Psicologia/Sutherland reframe)
**Prioridade:** P2
**Complexidade:** S (1 dia)
**Owner:** @copywriter + @dev
**Tipo:** Frontend / Copy
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

`frontend/app/planos/page.tsx:67-73` FAQ atual:
- "Posso cancelar a qualquer momento?" → "Sim. Sem contrato..."
- "O que acontece se eu cancelar?" → "Você mantém acesso..."
- "Existe contrato de fidelidade?" → "Não."

**Falhas (Bencivenga reason-why):**
- Respostas defensivas, não vendedoras
- Não usam reframe Sutherland para mudar percepção
- Não respondem à objeção real (medo da decisão), só à pergunta literal

**Princípio Bencivenga:** toda resposta a objeção deve dar reason-why crível + evidência + reframe que muda framing mental.

---

## Decisão

1. Reescrever 5 FAQs prioritárias com format "Objeção real → Reframe Sutherland → Comprovação"
2. Adicionar 3 FAQs novas que respondem objeções de alto impacto (caro, já uso planilha, "vou pensar")
3. Cada FAQ tem CTA contextual quando aplicável (link para case, comparativo, calc)
4. Tracking de open por FAQ (qual objeção é mais clicada → priorizar futuras stories)

---

## Critérios de Aceite

### FAQs Reescritas (5 prioritárias)

- [ ] **AC1:** "Posso cancelar a qualquer momento?"
  ```
  Sim — 2 cliques em Conta > Plano > Cancelar.
  Ninguém da SmartLic vai te ligar pedindo para reconsiderar.
  Acesso mantido até o fim do período já pago.
  ```

- [ ] **AC2:** "Está caro? R$ 297/mês é muito?"
  ```
  R$ 13/dia. Menos que 1 cafezinho.
  1 contrato público médio = R$ 150.000.
  ROI: 1 edital ganho paga 12 meses Pro Anual.
  Ver casos: [link para /sobre/casos quando CONV-014 done]
  ```

- [ ] **AC3:** "Já uso planilha — por que mudar?"
  ```
  Quanto tempo você gasta filtrando por semana?
  Empresas B2G médias gastam 8h/sem (32h/mês).
  Em 2 minutos no SmartLic você vê o equivalente a 8h de filtro manual.
  Trial 14 dias grátis: testa e compara.
  ```

- [ ] **AC4:** "O que acontece se eu cancelar no meio do anual?"
  ```
  Sem reembolso de meses já pagos (Stripe padrão).
  Acesso mantido até o fim do período pago.
  Seus dados (pipeline, histórico) ficam disponíveis 30d para export.
  Sem contrato de fidelidade — você pode voltar quando quiser.
  ```

- [ ] **AC5:** "Por que vocês cobram menos no Anual?"
  ```
  Anual reduz custo operacional pra gente (menos churn = menos suporte).
  Repassamos 25% pra você (R$ 100/mês de economia).
  É a forma de você se comprometer e nós retribuirmos.
  ```

### FAQs Novas

- [ ] **AC6:** "E se eu não achar nenhum edital relevante no trial?"
  ```
  Acontece em ~10% dos casos quando CNAE é muito nichado.
  Nesse caso: trial estendido por +14 dias OU reembolso integral
  no primeiro pagamento (sem perguntas).
  Mande email pra [tiago@smartlic.tech].
  ```

- [ ] **AC7:** "Posso usar para minha consultoria atender múltiplos clientes?"
  ```
  Sim — plano Consultoria R$ 997/mês:
  - Multi-CNAE (10+ perfis)
  - Multi-CNPJ (atender vários clientes)
  - Relatórios white-label
  Ver detalhes: [link para card Consultoria]
  ```

- [ ] **AC8:** "Vocês têm dados de quais editais? PNCP só?"
  ```
  Hoje: PNCP (federal/estadual/municipal) + Compras.gov + PCP v2.
  1.500.000 editais indexados, 27 estados, 400 dias de histórico.
  Cobertura: 95%+ dos editais públicos federais e estaduais.
  ```

### Implementação

- [ ] **AC9:** Componente `<PricingFAQ />` em `frontend/components/billing/PricingFAQ.tsx` (ou similar) com 8 FAQs (5 reescritas + 3 novas)
- [ ] **AC10:** Cada FAQ é collapsible (default fechado), accordion pattern
- [ ] **AC11:** Schema markup JSON-LD `FAQPage` para SEO benefit
- [ ] **AC12:** Tracking event `pricing_faq_open` com `faq_id` property — Mixpanel

### A11y + Performance

- [ ] **AC13:** WCAG AA: keyboard nav (Enter/Space para expandir), aria-expanded states
- [ ] **AC14:** Lighthouse score `/planos` não degrada

---

## Arquivos Impactados

**Modificados:**
- `frontend/app/planos/page.tsx` — substitui FAQ atual por componente novo
- `frontend/components/billing/PricingFAQ.tsx` (novo OU modificado se existe)
- `frontend/lib/analytics/funnel-events.ts` — `pricing_faq_open` event

**Novos:**
- `frontend/__tests__/components/billing/PricingFAQ.test.tsx`

---

## Riscos

- **R1 (Médio):** AC6 promessa "trial estendido +14d OU reembolso" cria SLA com user. Precisa ser cumprível. **Mitigação:** validar com @pm que política de retention permite isso (memory: STORY-277/360 valida pricing flexibility).
- **R2 (Baixo):** AC2 e AC3 referenciam casos/comparativos que podem não existir ainda. **Mitigação:** AC2 graceful — se CONV-014 não Done, link para `/sobre` genérico.
- **R3 (Baixo):** Schema markup FAQPage pode causar Google rich snippet conflict se já existir em outra página. **Mitigação:** verificar antes de deploy.

---

## Dependências

- CONV-001 (instrumentação) Done
- CONV-014 (cases nominais) — soft dependency para AC2 link
- @pm valida AC6 política trial extension

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P2 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Bencivenga reason-why. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO com nota**. AC6 promessa "trial estendido +14d ou reembolso" requer validação @pm da política ANTES de @dev iniciar. Sub-task: política operacional documentada antes de implementação. Status Draft → Ready. |
