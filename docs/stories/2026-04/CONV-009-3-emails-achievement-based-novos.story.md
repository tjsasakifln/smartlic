# CONV-009: 3 emails achievement-based novos

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Email & Retenção/Chaperon Soap Opera + Belgray + Sethi)
**Prioridade:** P1 — trial→paid é gargalo crítico
**Complexidade:** M (3-5 dias)
**Owner:** @dev + @copywriter (interno)
**Tipo:** Backend / Email / Copy
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

Encharge: achievement-based emails +258% vs calendar-based. CONV-008 audit revelará gaps na sequence atual; esta story adiciona 3 emails event-triggered que cobrem momentos de alta intenção:

1. **Pós-10 buscas:** usuário engajou, mostrar caso de pipeline ainda não convertido
2. **Pós-1ª pipeline_save:** validação positiva, mostrar pattern + sugerir mais
3. **Pós-5d inativo:** re-engajamento com novidade do CNAE

Combinado com Chaperon Soap Opera narrative (open loops) + Belgray personality (não corporate).

**Lift esperado:** +15-25% trial→paid (Encharge bem-desenhado).

---

## Decisão

1. 3 templates Resend novos com voz personalística (Belgray + Settle daily seinfeld lite)
2. Triggers event-driven via Mixpanel events (CONV-001) + ARQ cron escutando
3. Idempotência: cada email só envia 1x por user via `trial_email_log`
4. A/B test contra control (sem email) para validar lift
5. Templates em pt-BR com tom pessoal do Tiago (memory `reference_resend_personal_tone_send`)

---

## Critérios de Aceite

### Email 1 — Pós-10 buscas

- [ ] **AC1:** Trigger: ARQ cron poll Mixpanel events `first_search` count + outros searches; envia quando user atinge 10 searches AND último envio foi >24h
- [ ] **AC2:** Template `trial_achievement_10_searches.html`:
  ```
  Subject: Você analisou 10 editais — viu o de R$ [X] em [UF]?
  Body (personality):
  "Oi [nome], reparei que você já analisou 10 editais hoje. 👀
  
  Olhei aqui sua busca e o de R$ [valor] em [UF] tem [X]% de viabilidade
  pelo seu perfil. Esse é exatamente o tipo que vale salvar no pipeline.
  
  [CTA: Ver detalhes do edital]
  
  PS: trial expira em [N] dias. No plano Pro, você analisa 1.500/mês
  (vs. limite trial). [CTA secundário: Ver planos]
  
  Tiago — fundador SmartLic"
  ```
- [ ] **AC3:** Body dinâmico: `[X]`, `[UF]`, `[valor]`, `[viabilidade %]` populados via query Supabase (top edital com viability score do user)

### Email 2 — Pós-1ª pipeline_save

- [ ] **AC4:** Trigger: webhook backend (`backend/routes/pipeline.py:POST /v1/pipeline`) detecta primeiro pipeline_save do user, dispatcha email
- [ ] **AC5:** Template `trial_achievement_first_pipeline.html`:
  ```
  Subject: Salvou seu 1º edital 🎯 — quer ver mais como esse?
  Body:
  "[nome], você acabou de salvar [edital_título] no pipeline.
  
  Esse padrão (CNAE [X], UF [Y], valor R$ [Z]) tem [N] outros editais
  abertos com perfil similar. Quer ver?
  
  [CTA: Ver editais similares]
  
  Quem usa o pipeline desde o trial fecha plano Pro 3x mais
  (dado interno SmartLic — n cresce, validar empiricamente).
  
  Tiago"
  ```
- [ ] **AC6:** Backend computa "editais similares" via query similar to último pipeline_save

### Email 3 — Pós-5d inativo

- [ ] **AC7:** Trigger: ARQ cron diário (06 UTC) verifica users com `last_login` >5d ago AND `trial_status = 'active'` AND não-recebido este email
- [ ] **AC8:** Template `trial_reengagement_5d.html`:
  ```
  Subject: 23 novos editais do seu CNAE foram publicados
  Body:
  "[nome], faz 5 dias que você não volta no SmartLic.
  
  Enquanto isso, [N] novos editais do CNAE [X] foram publicados.
  Top 3 com maior viabilidade pra você:
  
  1. [Edital título] — R$ [X] — [UF] — viabilidade [%]
  2. ...
  3. ...
  
  [CTA: Ver todos]
  
  Trial expira em [N] dias. Não deixa passar.
  
  Tiago"
  ```
- [ ] **AC9:** Body popula 3 editais reais via query Supabase (CNAE do user, viability >70%, publicação >5d ago, não vistos pelo user)

### Idempotência + Tracking

- [ ] **AC10:** Cada envio registra em `trial_email_log` com `email_type` (e.g., `achievement_10_searches`) — re-envio bloqueado por unique constraint `(user_id, email_type)`
- [ ] **AC11:** Mixpanel events: `trial_email_achievement_sent`, `trial_email_achievement_open`, `trial_email_achievement_click` com `email_type` property
- [ ] **AC12:** Resend webhook (memory: implementado em 2026-04-24) atualiza `trial_email_log.delivery_status`

### A/B Test

- [ ] **AC13:** Feature flag `achievement_emails_enabled: bool` per-user (50/50 split por hash de user_id)
- [ ] **AC14:** Test runs ≥21d OU n≥30 trial completions per arm (whichever later)
- [ ] **AC15:** Métrica primária: trial→paid CVR; secundária: trial active days, total engagement events
- [ ] **AC16:** Documentado em `docs/experiments/conv-009-achievement-emails.md`

---

## Arquivos Impactados

**Novos:**
- `backend/templates/emails/trial_achievement_10_searches.html`
- `backend/templates/emails/trial_achievement_first_pipeline.html`
- `backend/templates/emails/trial_reengagement_5d.html`
- `backend/jobs/cron/trial_achievement_emails.py` — ARQ cron + dispatch logic
- `backend/services/achievement_email_service.py` — query helpers (top edital, similar, novos do CNAE)
- `backend/tests/test_achievement_emails.py`
- `docs/experiments/conv-009-achievement-emails.md`

**Modificados:**
- `backend/routes/pipeline.py` — webhook após primeiro pipeline_save
- `backend/jobs/cron/scheduler.py` — registrar novo cron `trial_achievement_emails`
- `backend/services/email_service.py` — método `send_achievement_email`
- Tabela `trial_email_log` — adicionar unique constraint `(user_id, email_type)` se não existir

---

## Riscos

- **R1 (Alto):** Mixpanel backend events fluindo é pré-condição (CONV-001 done). Sem isso, triggers não disparam. **Mitigação:** verificar events em produção ANTES de iniciar implementação.
- **R2 (Médio):** Email achievement frequente (3 novos) pode causar fatigue se mal-timing. **Mitigação:** AC1 condição "último envio >24h" + max 1 achievement email por dia globalmente.
- **R3 (Médio):** Body dinâmico (top edital, similar, etc.) pode falhar silenciosamente se queries retornam 0. **Mitigação:** fallback para template genérico se conteúdo dinâmico vazio.
- **R4 (Baixo):** Resend rate limit. **Mitigação:** Resend permite 100 emails/s — suficiente para volume atual.

---

## Dependências

- CONV-001 (instrumentação) Done — Mixpanel events ativos
- CONV-008 (audit) Done — recomendações para evitar conflito com sequence existente
- Tabela `trial_email_log` operacional + delivery webhook (memory: live)
- Memory `reference_mixpanel_backend_token_gap_2026_04_24` resolvido (PR #536)
- @copywriter ou @analyst para validação tom pt-BR antes de produção

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P1 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Encharge achievement +258%. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO**. 3 templates exatos pt-BR + idempotência via trial_email_log unique constraint. R1 pré-condição Mixpanel events validar antes de @dev iniciar. Status Draft → Ready. |
