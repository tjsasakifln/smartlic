# CONV-008: Auditoria trial 6-step (calendar vs achievement triggers)

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Email & Retenção/Settle, Chaperon, Belgray)
**Prioridade:** P1 — habilitador de CONV-009/010
**Complexidade:** S (1 dia)
**Owner:** @analyst + @dev
**Tipo:** Audit / Documentation
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

Encharge benchmark documenta: emails achievement-based (event-triggered) convertem **+258% vs calendar-based** (cron-triggered fixos). STORY-321 (memory: `frontend/templates/emails/trial_*.html`) implementou 6-step trial sequence, mas é desconhecido se triggers são calendar (dia 1, dia 3, dia 7...) ou achievement (após 1ª busca, após 1ª pipeline_save, após 5d inativo).

Memory `reference_mixpanel_backend_token_gap_2026_04_24` aponta que Mixpanel backend ficou silenciado 7d até PR #536 — sinal de que achievement triggers podem nem estar conectados aos events.

Sem audit, CONV-009 (3 emails achievement novos) e CONV-010 (loss-frame expiry) podem duplicar ou conflitar com sequence existente.

---

## Decisão

1. Mapear cada email da sequence trial 6-step: subject, trigger, condições
2. Classificar cada email: calendar OU achievement OU mixed
3. Identificar gaps: achievement triggers ausentes que deveriam existir
4. Identificar overlap: emails que podem ser consolidados
5. Documentar em relatório com recomendações para CONV-009/010

---

## Critérios de Aceite

### Mapeamento

- [ ] **AC1:** Inventário completo em `docs/reports/conv-008-trial-emails-audit-{YYYY-MM-DD}.md`:
  | Email # | Subject | Template file | Trigger type | Trigger condition | Send timing | Status |
  | 1 | "..." | trial_welcome.html | calendar | T+0h after signup | immediate | active |
  | 2 | "..." | trial_day3.html | calendar | T+72h after signup | day 3 | active |
  | ... | | | | | | |

- [ ] **AC2:** Para cada email, snippet do código que dispara:
  - Se cron: link para `backend/jobs/cron/trial_emails.py:LXX`
  - Se webhook: link para `backend/webhooks/X.py:LYY`
  - Se manual: link para route que envia

### Análise

- [ ] **AC3:** Categorização:
  - 🟢 Achievement-based (event-triggered)
  - 🟡 Calendar-based (cron-triggered)
  - 🔴 Não dispara (broken trigger ou condição inalcançável)

- [ ] **AC4:** Identificação de gaps documentada:
  - Achievement triggers ausentes que deveriam existir (ex: pós-1ª busca, pós-1ª pipeline_save, pós-5d inativo, pós-paywall_hit)
  - Calendar emails que poderiam ser convertidos para achievement (ex: "dia 7 lembrete" → "5 dias sem voltar lembrete")

### Validação Operacional

- [ ] **AC5:** Verificar `trial_email_log` tabela (memory `reference_trial_email_log_delivery_status_null`): cada email tem entries em produção nos últimos 7d?
- [ ] **AC6:** Cross-check Resend dashboard: open rate por email, delivery rate, bounce rate
- [ ] **AC7:** Identificar emails com open rate <15% (industry benchmark transactional ≥25%) — candidatos a redesign

### Recomendações

- [ ] **AC8:** Relatório recomenda concretamente:
  - Quais emails MANTER (high open + achievement-based)
  - Quais emails CONVERTER de calendar→achievement
  - Quais emails ADICIONAR (gaps de CONV-009)
  - Quais emails REMOVER (low open + redundantes)
  - Como CONV-009/010 se integram sem conflitar

### Saída

- [ ] **AC9:** Documento aprovado por @pm antes de @sm criar stories CONV-009 e CONV-010 ajustadas
- [ ] **AC10:** Tabela atualizada em `docs/observability/trial-email-sequence.md` (single source of truth para futuras mudanças)

---

## Arquivos Impactados

**Apenas leitura (audit):**
- `backend/templates/emails/trial_*.html`
- `backend/jobs/cron/trial_emails.py`
- `backend/services/email_service.py`
- `backend/webhooks/*.py`
- Tabela `trial_email_log` (Supabase)

**Novos:**
- `docs/reports/conv-008-trial-emails-audit-{YYYY-MM-DD}.md`
- `docs/observability/trial-email-sequence.md` — fonte da verdade ongoing

---

## Riscos

- **R1 (Médio):** Acesso Resend dashboard pode requerer credenciais (memory `reference_resend_personal_tone_send`). **Mitigação:** @devops fornece acesso ou stats via API.
- **R2 (Baixo):** Trial sequence pode ter sido modificada recentemente sem documentação. **Mitigação:** AC10 cria SSOT — futuras mudanças exigem update.
- **R3 (Baixo):** Análise de open rate pode ter dados limitados (n=2 trials reais). **Mitigação:** documentar limitação; usar benchmarks Resend para comparação.

---

## Dependências

- CONV-001 (instrumentação) Done — events `trial_email_sent_{n}`, `trial_email_open_{n}` ativos
- Tabela `trial_email_log` operacional (memory: live desde 2026-04-24)
- Acesso Resend dashboard ou API

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P1 habilitador para CONV-009/010. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 10/10 → **GO**. Audit-only, scope cristalino, AC10 SSOT documento ongoing. Bloqueia CONV-009/010 até completar. Status Draft → Ready. |
