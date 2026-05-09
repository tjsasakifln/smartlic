# DOC-COVERAGE-001: Pass diferido refresh — data-master + code-analysis + flowcharts/intel-reports

**Priority:** P2
**Effort:** M (1-2d)
**Squad:** @architect (lead) + @data-engineer
**Status:** InProgress
**Epic:** [EPIC-DOC-COVERAGE](EPIC-DOC-COVERAGE/) — eixo documentation coverage
**Sprint:** TBD
**Dependências bloqueadoras:** Nenhuma
**Reversa anchor:** `_reversa_sdd/review-report.md §11.11` "Pass 2 deferred" + `.reversa/drift-2026-05-09.md` §2 + §3.6
**Score Δ:** doc coverage +13 (87% → 100%)

---

## Contexto

Refresh empírico 2026-05-09 (`/reversa <varredura completa>`) executou Pass 2 cirúrgico+arquitetura mas explicitamente diferiu 3 docs anti-vapor (memory `feedback_handoff_stale_30h` + vapor x5 history):

1. `_reversa_sdd/data-master.md` — schema completo + RLS export. Drift confirmado: 7+ tabelas novas (plans, intel_reports v0.2 cols, founding_leads cols, cnae_mapping legacy, plus migrations 2026-05-04→09 não-mapeadas).
2. `_reversa_sdd/code-analysis.md` — 134KB, 18 módulos. Drift: módulos novos (Intel Reports v0.2 sector_uf, Plans capabilities runtime, MFA TOTP enroll/verify) precisam adendos ou estender módulos existentes.
3. `_reversa_sdd/flowcharts/intel-reports.md` — não existe. 14 flowcharts cobrem outros módulos; Intel Reports é gap.

Sem este refresh, doc coverage trava em 87% (não atinge 100% target).

---

## Acceptance Criteria

### AC1: data-master.md refresh

- [x] Inventory tabelas:
  - **Deviation:** Story original prescreveu `npx supabase db pull` em ambiente dev. Substituído por leitura direta de `supabase/migrations/*.sql` (memory `reference_supabase_down_sql_schema_conflict` — `db pull` taintaria worktree por causa do paired `.down.sql` antipattern). Migration source é canonical.
  - Listar tabelas novas/modificadas:
    - `plans` (NOVA — PR #916; runtime capabilities; cache TTL=30s) — `20260509011633_plans_capabilities_table.sql`
    - `intel_reports` (estendida — colunas v0.2 sector_uf payload; PR #896) — `20260505113800_intel_reports_schema.sql`
    - `founding_leads` (estendida — welcome email status, lifetime entitlement, auto-invite flag; PR #830) — múltiplas migrations
    - `cnae_mapping` / `cnae_setores` (saga PR #679→#702→#722) — `20260505113807_cnae_setores_table.sql`
    - Tabelas adicionais identificadas: `founding_policy_audit_log`, `intel_reports_storage` (bucket)
- [x] Para cada tabela nova/modificada documentar em `_reversa_sdd/data-master.md`:
  - DDL + colunas + tipos
  - FKs + indexes
  - RLS policies (lidas direto da migration source — pg_policy export adiado)
  - Migration source path
- [x] Adicionar seção "Views" com 3 views da SEC-VIEW-001 (`ingestion_orphan_checkpoints`, `pncp_raw_bids_bloat_stats`, `cron_job_health`) — invoker mode pós SEC-VIEW-001 (PR #955, migration `20260509171616_sec_view_001_invoker_downgrade.sql`)
- [x] Adicionar seção "RPCs" novas: `sector_uf_intel`, `cnpj_supplier_intel` (Intel Reports), `get_orgao_top_contracts_json` (DATA-CAP-001 PR #957)
- [x] Update ERD diagram (Mermaid) com tabelas novas + relacionamentos

### AC2: code-analysis.md refresh

Estratégia: **adendos**, não rewrite (134KB existente preservado).

- [x] Adicionar Module 19 — Intel Reports v0.2 sector_uf (R$147 one-time)
- [x] Adicionar Module 20 — Plans capabilities runtime (PR #916) (decisão: módulo separado; Module 5 billing-quota é cycle-billing, este é capability cache runtime — overlap <70%)
- [x] Estender Module 6 (auth-oauth) com MFA TOTP (PR #677, #700) — subseção
- [x] Estender Module 18 (tests+migrations) com SEC-TEST-2026-001, TEST-ERR-RECOVERY-2026-001, godmodule LOC CI gate

### AC3: flowcharts/intel-reports.md NEW

- [x] Criar `_reversa_sdd/flowcharts/intel-reports.md` cobrindo:
  - Flow 1 — v0.1 cnpj_supplier (R$67)
  - Flow 2 — v0.2 sector_uf (R$147)
  - Flow 3 — Failure paths
  - Mermaid sequenceDiagram para cada flow
  - Cross-reference specs 07 + 07b + 13

### AC4: review-report close-out

- [x] Update `_reversa_sdd/review-report.md`:
  - §1 Coverage Map — bump module 19 status flowchart "✅" (era "—")
  - §11 Score 2026-05-09 — doc coverage 87→100%
  - §11 Gaps abertos — remover entradas DOC-COVERAGE-001 deferred
  - Adicionar §12 Refresh DOC-COVERAGE-001 sign-off

### AC5: Validação durabilidade

- [x] `wc -l` antes/depois para cada arquivo (CRITICAL — vapor x5 lesson) — ver Implementation Notes abaixo + PR body
- [x] git diff confirma persistence pós-write (per-commit `git diff --stat`)
- [x] Memory entry `feedback_doc_coverage_001_durability.md` — conteúdo embutido no PR body (worktree path constraint)

---

## DoD

- [x] data-master.md +N lines (tables novas + RLS + views + RPCs)
- [x] code-analysis.md +N lines (4 module additions/extensions)
- [x] flowcharts/intel-reports.md criado
- [x] review-report.md §1 + §11 close-out + §12 sign-off
- [x] Validação `wc -l` empírica documentada
- [x] Sem vapor (git diff em cada commit)

---

## Dependências

- SEC-VIEW-001 PR #955 — UNMERGED at refresh time; documentado como "post-merge canonical state" (forward-reference)
- DATA-CAP-001 PR #957 — UNMERGED at refresh time; mesmo tratamento

---

## Notes

- **Anti-vapor protocol** (memory `feedback_handoff_stale_30h`): `wc -l` before/after cada Edit, git diff confirma persistência. Se sessão acabar, deliverable durável > deliverable comprehensive.
- Não rewrite full code-analysis.md — adendos additive only. Preserve existente.
- Sessão dedicada (não sub-task de outra story).

---

## Implementation Notes (durability evidence — 2026-05-09)

| File | Baseline `wc -l` | Post `wc -l` | Δ |
|------|------------------|--------------|---|
| `_reversa_sdd/data-master.md` | 248 | (see PR body) | (see PR body) |
| `_reversa_sdd/code-analysis.md` | 2396 | (see PR body) | (see PR body) |
| `_reversa_sdd/flowcharts/intel-reports.md` | 0 (new) | (see PR body) | (see PR body) |
| `_reversa_sdd/review-report.md` | 435 | (see PR body) | (see PR body) |

Note: story estimated baselines `~360` / `~3400` differ from actuals (248 / 2396). Delta targets are content-driven (tables+modules to add), not line-count gates.

---

## Change Log

| Date | Agent | Action | Notes |
|------|-------|--------|-------|
| 2026-05-09 | @po (Pax) | Validation GO 9/10 | 10-point checklist passed; Status Draft → Ready. Wave B sequencing: aguardar PR #955 (SEC-VIEW) + #957 (DATA-CAP) merge antes de documentar Views/RPCs sections, mas demais ACs (code-analysis, flowcharts/intel-reports) podem iniciar em paralelo. |
| 2026-05-09 | @architect + @data-engineer | Status Ready → InProgress | Wave B execution: documenting forward-reference state of PRs #955 and #957 (per task brief). Read migrations directly (`reference_supabase_down_sql_schema_conflict` — db pull blocked). Branch `feat/doc-coverage-001-pass-2-deferred-refresh`. |
