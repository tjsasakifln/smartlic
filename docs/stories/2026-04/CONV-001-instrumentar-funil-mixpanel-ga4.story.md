# CONV-001: Instrumentar funil completo Mixpanel + GA4

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Growth: Dunford/Suellentrop) — habilitador de toda análise A/B
**Prioridade:** P0 — sem isso, A/B testing é cego
**Complexidade:** M (1-2 dias)
**Owner:** @dev + @data-engineer
**Tipo:** Observability / Analytics
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

Funil de conversão SmartLic não tem instrumentação ponta-a-ponta. Memory `reference_mixpanel_backend_token_gap_2026_04_24` documentou que Mixpanel backend ficou silenciado 7d até PR #536 — sinal de que events críticos podem não estar conectados.

Gap atual: 2 signups/30d sem visibilidade de **onde** o funil quebra (visitor→signup? signup→onboarding? onboarding→1ª busca?). Sem dados de funil, todo o restante do EPIC-CONV-FUNNEL é especulativo.

Userpilot — "PQL converte 5-6x mais que MQL" (Cluster Growth, Hiten Shah). Mas só conseguimos definir PQL com eventos limpos.

---

## Decisão

1. Mapear 15 eventos críticos do funil com schema padronizado
2. Implementar tracking duplo: Mixpanel (product analytics) + GA4 (acquisition attribution)
3. Cohort dimensions: ICP (empresa vs consultoria) × source (organic/direct/paid) × awareness level estimado
4. Dashboard Mixpanel com funil visual + CVR por step + drop-off
5. Validar: 7d de events coletados sem gaps antes de declarar AC done

---

## Critérios de Aceite

### Eventos Frontend (Next.js)

- [ ] **AC1:** Eventos `landing_view`, `hero_cta_click`, `signup_view`, `signup_complete`, `onboarding_step_view`, `onboarding_complete`, `first_search`, `first_pipeline_save`, `paywall_hit`, `pricing_view`, `checkout_view`, `cancel_view`, `cancel_complete` instrumentados em frontend via Mixpanel SDK
- [ ] **AC2:** Cada evento envia properties: `user_id` (se autenticado), `session_id`, `account_type` (empresa/consultoria), `utm_source`, `utm_medium`, `utm_campaign`, `awareness_estimate` (entry surface heurística)
- [ ] **AC3:** GA4 também recebe os eventos críticos via gtag (`signup_complete`, `trial_started`, `trial_paid_conversion`) para attribution

### Eventos Backend (FastAPI)

- [ ] **AC4:** Confirmar `mixpanel-python` em `backend/requirements.txt` (PR #536) e `MIXPANEL_TOKEN` setado em `bidiq-backend` Railway service
- [ ] **AC5:** Backend emite eventos: `trial_started` (auth callback), `trial_email_sent_{n}`, `trial_email_open_{n}` (webhook Resend), `trial_paid_conversion` (Stripe webhook `customer.subscription.created`), `subscription_cancelled` (Stripe `customer.subscription.deleted`)
- [ ] **AC6:** Idempotência: cada evento backend tem `event_id` UUID determinístico para prevenir duplicação em retry de webhooks

### Cohort Dimensions

- [ ] **AC7:** Mixpanel `people.set` no momento de signup popula: `account_type`, `cnae_principal` (após onboarding), `created_at`, `source_first_touch`, `awareness_estimate`
- [ ] **AC8:** Awareness estimate heurístico:
  - `unaware` se entry = `/`
  - `problem_aware` se entry contém `/observatorio/*`, `/licitacoes/*`, `/contratos/*`
  - `solution_aware` se entry = `/pricing` ou `/features`
  - `product_aware` se entry = `/signup` direto

### Dashboard

- [ ] **AC9:** Dashboard Mixpanel `Funnel — SmartLic Conversion` com 6 steps: visitor → signup_complete → onboarding_complete → first_search → first_pipeline_save → trial_paid_conversion
- [ ] **AC10:** Breakdown por `account_type` × `source_first_touch` × `awareness_estimate`
- [ ] **AC11:** Dashboard GA4 com attribution multi-touch para `trial_paid_conversion`

### Validação

- [ ] **AC12:** 7 dias de eventos coletados sem gaps (todas as 15 events recebem ≥1 event count)
- [ ] **AC13:** Cross-check Mixpanel vs Stripe: `trial_paid_conversion` count = `customer.subscription.created` count (±5% tolerância de webhook delay)
- [ ] **AC14:** Documentação `docs/observability/conversion-funnel-events.md` lista cada evento, properties, trigger, e exemplo de payload

---

## Arquivos Impactados

**Novos:**
- `frontend/lib/analytics/funnel-events.ts` — schema centralizado + tracker functions
- `backend/observability/funnel_events.py` — backend event emission + idempotency
- `docs/observability/conversion-funnel-events.md` — documentação

**Modificados:**
- `frontend/app/page.tsx` — `landing_view` + `hero_cta_click`
- `frontend/app/signup/page.tsx`, `frontend/app/signup/components/SignupForm.tsx` — `signup_view`, `signup_complete`
- `frontend/app/onboarding/page.tsx`, `frontend/app/onboarding/components/*` — `onboarding_step_view`, `onboarding_complete`
- `frontend/app/buscar/page.tsx` — `first_search`, `paywall_hit`
- `frontend/app/pipeline/page.tsx` — `first_pipeline_save`
- `frontend/app/planos/page.tsx` — `pricing_view`, `checkout_view`
- `frontend/components/account/CancelSubscriptionModal.tsx` — `cancel_view`, `cancel_complete`
- `backend/webhooks/stripe.py` — `trial_paid_conversion`, `subscription_cancelled`
- `backend/services/billing.py` — `trial_started`
- `backend/jobs/cron/trial_emails.py` — `trial_email_sent_{n}`
- `backend/routes/trial_emails.py` (webhook) — `trial_email_open_{n}` via Resend events

---

## Riscos

- **R1 (Alto):** Mixpanel backend ainda em validação pós-PR #536. Se events não fluírem, AC4 trava todo restante. **Mitigação:** verificar `railway variables --service bidiq-backend --kv | grep MIXPANEL_TOKEN` + smoke test antes de iniciar implementação.
- **R2 (Médio):** Duplicação de events em retry de webhooks Stripe/Resend gera CVR inflado. **Mitigação:** AC6 idempotência via `event_id` determinístico (hash de `provider_event_id`).
- **R3 (Médio):** GDPR/LGPD — `user_id` em events pode ser PII. **Mitigação:** usar Mixpanel `distinct_id` (UUID), não email; revisar `log_sanitizer.py` patterns.
- **R4 (Baixo):** Custom dimensions GA4 limit 50 — só usar para top-level events. **Mitigação:** restringir GA4 a 5 conversion events; resto fica em Mixpanel.

---

## Dependências

- PR #536 confirmado em produção (memory `project_mixpanel_lib_silent_2026_04_27`)
- Acesso admin Mixpanel project
- GA4 property + measurement ID em `frontend/app/layout.tsx` (verificar se já existe)

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. Habilitador P0 do EPIC-CONV-FUNNEL-2026-Q2. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO**. Habilitador crítico de todo epic. Pré-condição smoke test Mixpanel backend (PR #536) ANTES de @dev iniciar. Status Draft → Ready. |
