# CONV-013: Cancel flow com retention dinâmico por motivo

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster SaaS Conversion/Klettke BDA + Wiebe VOC)
**Prioridade:** P2 — depende de n≥10 cancellations para validar
**Complexidade:** M (2-3 dias)
**Owner:** @dev + @copywriter
**Tipo:** Frontend / Backend / Copy
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

`frontend/components/account/CancelSubscriptionModal.tsx:23-36` atual:
- 5 reasons (caro, não usa, falta funcionalidade, outra solução, outro motivo)
- Lista benefits genérica (1000 análises mensais, histórico completo, etc.)
- **Falha:** benefits não vinculados ao motivo do user — se "está caro", mostrar "1000 análises" não responde

**Princípio Klettke BDA (Before-During-After):** retention copy efetivo responde à objeção específica. Wiebe VOC (Voice of Customer): usar a linguagem do user que está saindo.

**Lift documentado:** retention dinâmico por motivo = +10-30% save rate em SaaS B2B.

---

## Decisão

1. Manter 5 reasons existentes
2. Para cada reason, mostrar retention copy específico:
   - "Está caro" → ROI calc com últimos editais + oferta de 1 mês desconto
   - "Não estou usando" → editais novos do CNAE últimos 7d + onboarding revisão
   - "Falta funcionalidade" → form para PM + roadmap atual
   - "Outra solução" → form aberto + 30d acesso para comparar (oferta retenção)
   - "Outro motivo" → form aberto + Tiago contact direto
3. Tracking save rate por reason → priorizar copy que mais retém
4. Métrica final: cancel rate vs save rate por reason

---

## Critérios de Aceite

### Modal Refactor

- [ ] **AC1:** Modal tem 3 steps:
  - Step 1: razão (5 opções)
  - Step 2: retention dinâmico por razão
  - Step 3: confirmação final OR retention saved (sucesso)
- [ ] **AC2:** Cada step pode voltar (back button) sem perder seleção

### Retention Copy por Razão

- [ ] **AC3:** "Está caro" — Step 2:
  ```
  H: "Vamos rever o ROI?"
  Body:
  "Nos últimos 30 dias você analisou [N] editais.
  Top 3 com maior viabilidade pra você:
  
  1. [edital] — R$ [X] — viabilidade [%]
  2. ...
  3. ...
  
  ROI estimado: 1 edital ganho = 12 meses Pro Anual.
  
  Posso te oferecer:
  [CTA primário: 1 mês de desconto 50%] (uso único, link gera Stripe coupon)
  [CTA secundário: Cancelar mesmo assim]
  "
  ```

- [ ] **AC4:** "Não estou usando" — Step 2:
  ```
  H: "Talvez você não esteja vendo o que precisa?"
  Body:
  "Nos últimos 7 dias, [N] novos editais do CNAE [X] foram publicados.
  Top 3 com alta viabilidade pra você (que você ainda não viu):
  
  1. ...
  2. ...
  3. ...
  
  [CTA primário: Ver esses editais agora]
  [CTA secundário: Quero ajuda no onboarding (Tiago)]
  [CTA terciário: Cancelar mesmo assim]
  "
  ```

- [ ] **AC5:** "Falta funcionalidade que preciso" — Step 2:
  ```
  H: "O que tá faltando?"
  Body:
  Form livre (textarea max 500 chars) — "Conte qual feature mudaria sua decisão"
  
  [CTA primário: Enviar para Tiago] (envia email pro PM/founder)
  [CTA secundário: Ver roadmap público] (link para /roadmap se existir)
  [CTA terciário: Cancelar agora]
  
  "Vou ler pessoalmente. Se for algo no nosso roadmap próximo, entro em contato."
  ```

- [ ] **AC6:** "Encontrei outra solução" — Step 2:
  ```
  H: "Curioso pra saber qual e por quê"
  Body:
  Form: "Qual ferramenta?" + "O que ela faz melhor?" (textareas)
  
  [CTA primário: 30 dias de acesso grátis para comparar] (extende trial-like)
  [CTA secundário: Cancelar agora]
  
  "Sem letras miúdas — te dou 30 dias para comparar lado-a-lado.
  Se decidir pela outra, sem hard feelings."
  ```

- [ ] **AC7:** "Outro motivo" — Step 2:
  ```
  H: "Conta o que aconteceu?"
  Body: textarea livre
  [CTA primário: Falar com Tiago direto] (abre wa.me OU email pessoal)
  [CTA secundário: Cancelar]
  ```

### Backend Logic

- [ ] **AC8:** Endpoint `POST /v1/account/cancel-feedback` recebe `{reason, free_text?, retention_offer_accepted?}` e registra em tabela `cancel_feedback`
- [ ] **AC9:** Cupom Stripe 50% off 1 mês gerado dinamicamente no AC3 caso user aceite (link único, 24h validade)
- [ ] **AC10:** AC6 30-day extension implementado via `trial_expires_at` ou flag custom (sem cobrar)
- [ ] **AC11:** AC5/AC7 envia email para `tiago@smartlic.tech` com transcript

### Tracking

- [ ] **AC12:** Mixpanel events:
  - `cancel_view` (modal open)
  - `cancel_reason_selected` (com `reason` property)
  - `cancel_retention_offer_shown` (com `reason`)
  - `cancel_retention_offer_accepted` (com `reason`, `offer_type`)
  - `cancel_complete` (com `reason`, `retention_attempted`, `retention_saved`)

### Métricas

- [ ] **AC13:** Dashboard Mixpanel `Cancel Funnel` com:
  - Volume por reason
  - Save rate por reason (retention_offer_accepted / total per reason)
  - Reasons com save rate >20% — priorizar copy improvement
  - Reasons com save rate <5% — investigar copy ou aceitar como churn natural

### Bloqueador Empírico

- [ ] **AC14:** Story implementada AGORA mas validação empírica espera n≥10 cancellations por reason. Documentar em `docs/experiments/conv-013-cancel-retention.md` que após 60d de produção, revisar copy por reason.

---

## Arquivos Impactados

**Novos:**
- `supabase/migrations/YYYYMMDDHHMMSS_create_cancel_feedback.sql` + `.down.sql`
- `frontend/components/account/CancelRetentionStep.tsx` — step 2 retention dinâmico
- `frontend/components/account/CancelOfferCard.tsx` — sub-componente reusable
- `backend/routes/cancel_feedback.py` (ou route extension em billing.py)
- `backend/services/retention_offer_service.py` — Stripe coupon gen + 30d extension
- `backend/tests/test_cancel_retention.py`
- `docs/experiments/conv-013-cancel-retention.md`

**Modificados:**
- `frontend/components/account/CancelSubscriptionModal.tsx` — refactor 3-step
- `backend/services/billing.py` — coordenação Stripe coupon + extension
- Tabela `cancel_feedback` (nova): `id, user_id, reason, free_text, retention_offer_shown, retention_offer_accepted, offer_type, created_at`

---

## Riscos

- **R1 (Médio):** Cupom Stripe 50% off pode ser abusado (cancel→aceita→cancel→aceita). **Mitigação:** AC9 validade 24h + flag user `cancel_retention_used: bool` impede uso múltiplo.
- **R2 (Médio):** "30 dias grátis para comparar" pode atrair users que ja decidiram sair, custo operacional. **Mitigação:** AC10 só oferecer se user pagou ≥3 meses (signal de fit prévio).
- **R3 (Baixo):** Form livre AC5/AC7 pode receber spam ou conteúdo abusivo. **Mitigação:** rate limit + sanitização + email para Tiago revisar.
- **R4 (Baixo):** N=2 atual, retention dinâmico não tem dados para validar. **Mitigação:** AC14 — implementar agora, validar empírico em 60d.

---

## Dependências

- CONV-001 (instrumentação) Done
- Stripe API funcional (cupons + subscription updates)
- Tabela `cancel_feedback` criada
- @pm valida política 30d extension (AC10)

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P2 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Klettke BDA + Wiebe VOC. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO**. 3-step modal + retention copy por reason. AC14 reconhece n=2 atual e plana validação 60d post-prod. R1 cupom abuse mitigado via flag user. Status Draft → Ready. |
