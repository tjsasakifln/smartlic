# CONV-010: Trial expiry email loss-frame com lista nominal

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Psicologia/Kahneman loss aversion + Cluster Direct Response/Schwartz)
**Prioridade:** P2
**Complexidade:** M (2-3 dias)
**Owner:** @dev + @copywriter
**Tipo:** Backend / Email / Copy
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

McKinsey/JMR: loss aversion em retention/renewal = +21-32% conversion. SmartLic trial atual (memory CONV-008 audit pendente) provavelmente tem email "trial expirando" calendar-based genérico. Substituir por **loss-frame específico com lista nominal** (Kahneman: perda concreta > perda abstrata) maximiza urgência psicológica sem manipulação.

`frontend/app/components/TrialExpiringBanner.tsx:26-31` já usa loss frame, mas só no banner UI. Email é momento de maior atenção (open rate alto em pré-expiração).

**Princípio:** Schwartz "specificity sells" + Kahneman loss aversion. Lista de 5-10 editais REAIS que o user salvou no pipeline OR analisou com viability >70% torna a perda tangível.

---

## Decisão

1. Email único disparado D-2 antes de expiração (dia 12 do trial)
2. Subject loss-frame: "Você está prestes a perder acesso a [N] editais relevantes"
3. Body lista 5-10 editais nominais (do pipeline OR top viability)
4. CTA único: "Manter acesso por R$ 297/mês (1 cafezinho/dia)" — Sutherland reframe
5. Body fallback se user tem 0 pipeline_saves AND 0 high-viability searches: emails generic com top 3 do CNAE
6. A/B test contra control (sem email D-2)

---

## Critérios de Aceite

### Trigger + Lógica

- [ ] **AC1:** ARQ cron diário (10 UTC) verifica users com `trial_expires_at` em 48h±2h AND não recebeu este email AND `trial_status = 'active'`
- [ ] **AC2:** Template `trial_expiry_d2_loss_frame.html`:
  ```
  Subject: Você está prestes a perder acesso a [N] editais relevantes
  Body:
  "[nome], em 2 dias seu trial expira.
  
  Aqui está o que você vai perder acesso:
  
  [Se user tem ≥1 pipeline_save:]
  📌 Editais que você salvou no pipeline:
  1. [edital_título_1] — R$ [valor] — [UF]
  2. ...
  
  [Se user tem 0 pipeline_save mas viability >70%:]
  ⭐ Editais com alta viabilidade pra você:
  1. [edital_título_1] — R$ [valor] — viabilidade [%]
  2. ...
  
  [Sempre:]
  💾 Mais [N] editais analisados nos últimos 14 dias
  📊 Seu histórico de buscas e filtros
  
  Manter acesso por R$ 297/mês (1 cafezinho/dia):
  [CTA: Ativar plano Pro]
  
  Cancelar em 2 cliques quando quiser. Sem letras miúdas.
  
  Tiago — fundador"
  ```
- [ ] **AC3:** Body dinâmico via query Supabase:
  - Pipeline saves do user: `SELECT * FROM pipeline_items WHERE user_id = ? ORDER BY created_at DESC LIMIT 5`
  - Top viability searches: `SELECT * FROM ... WHERE user_id = ? AND viability_score > 70 LIMIT 5`
  - Total editais analisados: `COUNT` queries
- [ ] **AC4:** Fallback para users sem dados: lista top 3 editais do CNAE com publicação recente

### Idempotência

- [ ] **AC5:** Registro em `trial_email_log` com `email_type = 'expiry_d2_loss_frame'`; re-envio bloqueado
- [ ] **AC6:** Se user converter para paid antes de D-2, email NÃO dispara (verificação `trial_status = 'active'`)

### Tracking + A/B

- [ ] **AC7:** Mixpanel events: `trial_expiry_email_sent`, `trial_expiry_email_open`, `trial_expiry_email_click_cta`
- [ ] **AC8:** Feature flag `expiry_d2_email_enabled: bool` per-user (50/50)
- [ ] **AC9:** Test runs ≥30d OU n≥30 trial expirations per arm
- [ ] **AC10:** Métrica primária: trial→paid CVR conversão D-2 a D+0; secundária: open rate, click rate
- [ ] **AC11:** Documentado em `docs/experiments/conv-010-expiry-loss-frame.md`

### Tom + Compliance

- [ ] **AC12:** Tom não manipulativo — loss frame factual ("vai perder acesso a X que você salvou"), não FUD ("se não pagar nunca mais verá editais")
- [ ] **AC13:** LGPD compliant — body usa só dados do próprio user, não dados de terceiros
- [ ] **AC14:** Unsubscribe link funcional (já obrigatório por Resend)

---

## Arquivos Impactados

**Novos:**
- `backend/templates/emails/trial_expiry_d2_loss_frame.html`
- `backend/jobs/cron/trial_expiry_emails.py` — cron diário
- `backend/services/expiry_email_service.py` — body builder
- `backend/tests/test_expiry_emails.py`
- `docs/experiments/conv-010-expiry-loss-frame.md`

**Modificados:**
- `backend/jobs/cron/scheduler.py` — registrar cron
- `backend/services/email_service.py` — método `send_trial_expiry_email`
- Tabela `trial_email_log` — entry para `expiry_d2_loss_frame` type

---

## Riscos

- **R1 (Médio):** Loss frame pode ser percebido como pressuring se mal-calibrado. **Mitigação:** AC12 tom factual, A/B test com sentiment monitoring.
- **R2 (Médio):** User com 0 pipeline_saves AND 0 high-viability fica com fallback fraco. **Mitigação:** AC4 fallback genérico OK; alternativa = não enviar (avoid spam).
- **R3 (Baixo):** Email pode coincidir com `TrialExpiringBanner` no UI. **Mitigação:** complementar não conflita; verificar coordenação visual.
- **R4 (Baixo):** Conversão D-2→D+0 pode ser baixa por timing (fim de semana, feriado). **Mitigação:** A/B test detecta efeito; ajustar timing futuramente.

---

## Dependências

- CONV-001 (instrumentação) Done
- CONV-008 (audit) Done — confirma que email D-2 não conflita com sequence existente
- Tabela `trial_email_log` operacional
- @copywriter validação pt-BR antes de produção

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P2 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Kahneman loss aversion +21-32%. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO**. Loss frame factual (não FUD) + AC4 fallback graceful + LGPD compliant. R1 sentiment monitoring via cancel rate proxy. Status Draft → Ready. |
