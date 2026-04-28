# CONV-002: Definir PQL (Product-Qualified Lead)

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Growth: Shah, Suellentrop) — Userpilot benchmark "PQL converte 5-6x mais que MQL"
**Prioridade:** P2 — depende de n≥30 trials concluídos
**Complexidade:** S (<1 dia, mas bloqueado por dados)
**Owner:** @analyst + @data-engineer
**Tipo:** Analytics / Strategy
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

Sem definição empírica de PQL, marketing/sales investem igualmente em todos os signups. Userpilot/Hiten Shah benchmark: PQLs convertem 5-6x mais — segmentar permite focar nurture nos leads quentes e identificar friction nos frios.

Hipótese inicial (a validar): PQL = trial user com `≥3 buscas em 7d` OU `≥1 pipeline_save em 7d` OU `TTV alcançado <5min`.

**Bloqueador empírico:** memory `feedback_n2_below_noise_eng_theater` — n=2 reais em 30d. Validação requer n≥30 trials concluídos. Story preparada para execução pós-Sprint 3 do epic.

---

## Decisão

1. Aguardar n≥30 trials concluídos (estimativa: pós-Sprint 3 do EPIC-CONV-FUNNEL)
2. Análise quantitativa: cohort de trial→paid vs trial→churn por feature usage
3. Definição empírica de threshold PQL (fórmula com 2-3 sinais)
4. Dashboard PQL count semanal + alertas para drop-off
5. Documento `docs/strategy/pql-definition.md`

---

## Critérios de Aceite

### Pré-condição

- [ ] **AC0:** n≥30 trial users com outcome conhecido (paid OU churned). Bloquear story até atingir threshold.

### Análise

- [ ] **AC1:** Query Mixpanel/Supabase extrai por trial user: total searches em 7d, total pipeline_saves em 7d, TTV em min, total downloads, total feedback events
- [ ] **AC2:** Comparação cohort `paid` vs `churned` por feature usage — identificar top 3 features com maior delta
- [ ] **AC3:** Threshold PQL definido com 2-3 sinais combinados (e.g., `searches≥3 AND pipeline_saves≥1` OR `TTV<5min AND searches≥2`)
- [ ] **AC4:** Validação cruzada: PQL definition aplicada retroativamente prevê paid com precision≥75%, recall≥60%

### Implementação

- [ ] **AC5:** View materializada `public.pql_users` no Supabase com refresh diário (pg_cron):
  ```sql
  CREATE MATERIALIZED VIEW pql_users AS
  SELECT user_id, computed_at, signals_jsonb, is_pql
  FROM ...
  ```
- [ ] **AC6:** Dashboard Mixpanel `PQL Tracking` com count semanal, conversion rate PQL→paid, PQL→churn
- [ ] **AC7:** Alerta automático (Sentry breadcrumb) se PQL count semanal cai >30% WoW

### Documentação

- [ ] **AC8:** `docs/strategy/pql-definition.md` documenta:
  - Definição empírica + threshold
  - Sinais usados + razão
  - Métricas de validação (precision/recall)
  - Quando re-validar (trimestral OU n≥100 incremental)
- [ ] **AC9:** Tabela `cohort_definitions` ou similar registra versão da PQL definition (audit trail para mudanças futuras)

---

## Arquivos Impactados

**Novos:**
- `supabase/migrations/YYYYMMDDHHMMSS_pql_users_view.sql` + `.down.sql`
- `scripts/pql_threshold_analysis.py` — análise reproduzível
- `docs/strategy/pql-definition.md` — documento estratégico
- `docs/reports/pql-baseline-{YYYY-MM-DD}.md` — análise inicial

**Modificados:**
- `backend/jobs/cron/scheduler.py` — refresh diário da view (se não usar pg_cron)

---

## Riscos

- **R1 (Alto):** n insuficiente leva a definição com baixa precision. **Mitigação:** AC0 bloqueador rígido, não relaxar threshold.
- **R2 (Médio):** Sinais escolhidos podem ser proxies fracos do verdadeiro comportamento de compra. **Mitigação:** AC4 validação retroativa obrigatória.
- **R3 (Baixo):** PQL definition pode mudar com novas features. **Mitigação:** AC9 audit trail + AC8 política de re-validação.

---

## Dependências

- CONV-001 (instrumentação) Done
- n≥30 trial users com outcome conhecido (Sprint 3+ do epic)
- Acesso Mixpanel + Supabase dados de produção

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P2 (bloqueada por dados). Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 10/10 → **GO**. Gate AC0 (n≥30) explícito e bem-defendido. Story Ready mas execução bloqueada até dados. Status Draft → Ready. |
