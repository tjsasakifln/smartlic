# CONV-007: Time-to-Value tracking + first-analysis dispatch otimizado

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Growth/Bush, Shah — Bowling Alley + Aha moment) + GTM-004 existente
**Prioridade:** P1 — TTV é multiplicador de retention/conversion
**Complexidade:** S (<1 dia mensuração; M se gargalos exigem fix)
**Owner:** @dev + @data-engineer + @architect
**Tipo:** Observability / Performance
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

GTM-004 já estabelece meta TTV <5min via auto-dispatch first-analysis pós-onboarding. Cerebral Ops benchmark: TTV <5min → +40% retention 30d, +15-25% trial→paid; cada 10min delay → -8% conversion.

**Status atual:** TTV não mensurado empiricamente. Memory `feedback_supabase_disk_io_root_cause_pattern` aponta gargalos no backend. Memory `project_backend_outage_2026_04_27` documenta sync .execute() bloqueando event loop em algumas rotas.

**Risco:** CONV-003 promete "2 min" no hero. Sem mensuração + fix de gargalos, promessa não é cumprida.

---

## Decisão

1. Mensurar TTV empiricamente (signup → primeiro edital viável visualizado)
2. Identificar gargalos via tracing (search latency? UF batching? LLM classify? frontend hydration?)
3. Aplicar fixes priorizados (≥10s reduction)
4. Definir SLA: TTV mediano <5min, p95 <8min
5. Alerta automático se TTV degrada >20% WoW

---

## Critérios de Aceite

### Mensuração

- [ ] **AC1:** Evento `ttv_measured` (Mixpanel) com properties:
  - `user_id`
  - `ttv_seconds` (de signup_complete a first_search_results_viewed)
  - `funnel_steps_count` (signup → onboarding_step_1 → ... → first_search)
  - `step_durations_ms` (JSON com tempo gasto em cada step)
- [ ] **AC2:** Backend tracing (OpenTelemetry) cobre first-analysis dispatch:
  - Trace span `first_analysis.dispatch` envolvendo todo pipeline
  - Sub-spans: `cnae_lookup`, `uf_batching`, `llm_classify`, `viability_score`, `cache_check`
- [ ] **AC3:** Dashboard Mixpanel `TTV Distribution` com p50/p75/p95/p99
- [ ] **AC4:** Dashboard Sentry/Tempo `First Analysis Latency` com breakdown por sub-span

### Análise + Otimização

- [ ] **AC5:** Análise inicial (mínimo n=10 trials) identifica top 3 gargalos por contribuição ao TTV total
- [ ] **AC6:** Para cada gargalo identificado, criar sub-issue com fix priorizado:
  - Se gargalo é DB query: optimize query OR add cache OR use materialized view
  - Se gargalo é LLM classify: paralelizar OR usar batch API OR pre-compute para CNAEs comuns
  - Se gargalo é frontend hydration: code-split OR pre-render OR optimistic UI
- [ ] **AC7:** Aplicar fixes que reduzem TTV em ≥10s cada (medido via tracing)

### SLA

- [ ] **AC8:** SLA TTV documentado em `docs/observability/ttv-sla.md`:
  - Target mediano: <5min
  - p95: <8min
  - p99: <15min
- [ ] **AC9:** Alerta Sentry se TTV mediano semanal >5min OU degrada >20% WoW
- [ ] **AC10:** Alerta Sentry se p95 >8min em janela 24h

### Coordenação com CONV-003

- [ ] **AC11:** Antes de promover CONV-003 variant B (hero "2 min") para 100%, validar TTV mediano <5min em 7d consecutivos. Se >5min, pausar CONV-003 promotion ou ajustar copy hero para "5 min".

---

## Arquivos Impactados

**Modificados:**
- `frontend/app/auth/callback/page.tsx` — emit `ttv_start` event
- `frontend/app/buscar/page.tsx` (ou first-search component) — emit `ttv_end` event quando first_search_results renderizam
- `backend/routes/onboarding.py` — adicionar OTel spans em first-analysis dispatch
- `backend/search_pipeline.py` — sub-spans em stages críticos
- `backend/llm_arbiter/classification.py` — span em LLM classify

**Novos:**
- `docs/observability/ttv-sla.md`
- `docs/reports/ttv-baseline-{YYYY-MM-DD}.md` — análise inicial
- `frontend/lib/analytics/ttv-tracker.ts` — utilitário para emit start/end + computa duration

---

## Riscos

- **R1 (Alto):** Backend gargalos (memory `feedback_supabase_disk_io_root_cause_pattern`) podem requerer compute upgrade Railway. **Mitigação:** AC5 análise antes de assumir compute upgrade; otimizações de código primeiro.
- **R2 (Médio):** TTV inclui tempo de leitura do usuário (não apenas backend). User pode demorar 2min lendo onboarding. **Mitigação:** AC1 step_durations_ms permite distinguir backend latency vs user dwell time.
- **R3 (Médio):** OpenTelemetry overhead em produção pode adicionar 5-10ms por span. **Mitigação:** sampling rate ajustável, default 10% trials.
- **R4 (Baixo):** SLA definido pode ser ambicioso para n atual baixo. **Mitigação:** AC8 SLA é direcional; ajustar após n≥30 baseline.

---

## Dependências

- CONV-001 (instrumentação) Done — events Mixpanel
- OpenTelemetry já configurado em `backend/telemetry.py`
- Sentry alerting funcional
- CONV-003 coordenação — pausa de promoção se TTV >5min

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P1 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Bowling Alley (Bush). Habilitador para CONV-003 promotion. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 8/10 → **GO com nota**. AC7 "fixes que reduzem ≥10s" pode escalar escopo. @dev deve time-box otimização (recommendation: split em CONV-007a mensuração + CONV-007b otimizações pós-baseline em sprint subsequente). Complexidade S→M se gargalos exigem fix. Status Draft → Ready. |
