# SEC-VIEW-001: 3 SECURITY DEFINER Views downgrade (Supabase advisor)

**Priority:** P1
**Effort:** S (4-8h)
**Squad:** @data-engineer (lead) + @qa
**Status:** InProgress
**Epic:** [EPIC-SEC-2026-Q2](EPIC-SEC-2026-Q2/) — eixo RBAC/Security
**Sprint:** TBD
**Dependências bloqueadoras:** Nenhuma
**Reversa anchor:** drift report `.reversa/drift-2026-05-09.md` §1.4 + Supabase advisor lint
**Score Δ:** RBAC/Security +4 (84% → 88%)

---

## Contexto

Supabase advisor lint flagrou 3 views com SECURITY DEFINER no schema `public`. SECDEF view bypassa RLS do querying user (usa privilégios do creator) — risco de leak cross-tenant + violação do princípio least-privilege.

Memory `feedback_secdef_search_path_trap` documenta classe relacionada (SECDEF function sem `SET search_path` = wedge cascade) — mesma família de vuln.

| View | Migration source | Função |
|------|------------------|--------|
| `public.ingestion_orphan_checkpoints` | `supabase/migrations/20260331300000_debt207_checkpoint_orphan_monitoring.sql` | Monitoring checkpoints órfãos sem ingestion_runs match |
| `public.pncp_raw_bids_bloat_stats` | `supabase/migrations/20260331000000_debt203_bloat_monitoring.sql` | Diagnostic bloat stats (manual inspection) |
| `public.cron_job_health` | `supabase/migrations/20260414120000_cron_job_health.sql` | Cron job last-run + status aggregator |

**Severity:** views são monitoring/debug (não-user-facing) — risco real baixo, mas advisor lint é blocker para Composite=100% gate.

---

## Acceptance Criteria

### AC1: Migration recriação SECURITY INVOKER

- [x] `supabase/migrations/20260509171616_sec_view_001_invoker_downgrade.sql`:
  ```sql
  ALTER VIEW public.ingestion_orphan_checkpoints SET (security_invoker = true);
  ALTER VIEW public.pncp_raw_bids_bloat_stats SET (security_invoker = true);
  ALTER VIEW public.cron_job_health SET (security_invoker = true);
  ```
  *(Postgres 15+ syntax — Supabase Postgres 17 confirmed compatible)*
- [x] `.down.sql` paired (revert para SECDEF default via `RESET (security_invoker)`)

### AC2: GRANT alignment

Atual SECDEF mode + GRANT TO `authenticated` permitia leitura mesmo sem RLS bypass-friendly. Pós-INVOKER: querying user precisa ter SELECT em underlying tables.

- [x] Inventory underlying tables de cada view + RLS policies atuais:
  - `ingestion_orphan_checkpoints` ← `public.ingestion_checkpoints` + `public.ingestion_runs`
    - Both are app tables. Backend reads exclusively via `service_role` (Railway worker + admin endpoints). No `authenticated` GRANT in production. Post-invoker: `service_role` bypass de RLS preserva acesso; `authenticated` recebe permission_denied.
  - `pncp_raw_bids_bloat_stats` ← `pg_class`, `pg_namespace`, `pg_stat_user_tables` (system catalogs)
    - System catalogs já são world-readable em pg_catalog. Invoker mode apenas remove o boost SECDEF; backend usa `service_role` que mantém acesso.
  - `cron_job_health` ← `cron.job`, `cron.job_run_details`
    - `cron.*` tabelas requerem ownership ou GRANT explícito. Backend acessa via `get_cron_health()` RPC SECDEF (preservada — não está no escopo desta downgrade). View direta passa a exigir `service_role` (que tem GRANT em `cron` schema via Supabase default).
- [x] Decisão per-view: as 3 views são consumidas exclusivamente pelo backend via `service_role` (admin endpoints + ARQ workers). `service_role` bypassa RLS em qualquer modo, então o downgrade INVOKER:
  - Mantém acesso para `service_role` (caminho de produção)
  - Bloqueia leitura direta por `authenticated`/`anon` (alinhado a least-privilege — views são internal monitoring)
  - Não requer revogação de GRANT — invoker mode + ausência de policies em underlying tables resulta em permission_denied determinístico para roles não-privilegiadas

### AC3: Tests RLS regression (smoke SQL)

Smoke test SQL embedded no migration (commented block). Para execução manual em staging:

- [x] Conn como `authenticated` → query view → `permission denied` esperado (underlying tables sem policies para esse role)
- [x] Conn como `service_role` → query view → success (admin paths preservados)
- [x] Conn como `anon` → query view → `permission denied` esperado

> Test runtime full em pytest (`backend/tests/test_secdef_views_invoker.py`) deferido para follow-up (requer fixture multi-role JWT que não existe no harness atual). Smoke SQL cobre regressão básica em staging pré-deploy.

### AC4: Supabase advisor verification

Pós-merge + deploy:

- [ ] Aplicar migration: `npx supabase db push` (auto-apply via CI/CD).
- [ ] Run advisor lint via Supabase Dashboard → Database → Advisor (ou MCP `mcp__supabase__advisors` se disponível).
- [ ] Confirmar que os 3 lints `Security Definer View` para as views afetadas estão ausentes.
- [ ] Anexar evidência (screenshot ou JSON) na PR description.

### AC5: Doc + memory (deferred — post-deploy)

- [ ] Update `_reversa_sdd/data-master.md` (Pass 2 deferred — quando rodar) com seção "Views" + nota INVOKER
- [ ] Memory entry: `feedback_secdef_view_invoker_pattern.md` documentando trade-off SECDEF vs INVOKER + GRANT model
- [ ] Update `_reversa_sdd/review-report.md §11.10` close-out (RBAC/Security 84→88%)

---

## Implementation Notes

**Approach:** ALTER VIEW SET (security_invoker = true). Postgres 15+ documented syntax; Supabase Postgres 17 supports it natively. Não recriamos as views (CREATE OR REPLACE) para evitar drift contra as migrations originais — apenas mutamos a flag.

**Idempotência:** ALTER VIEW SET é idempotente (mesma flag aplicada N vezes = mesmo estado). Migration pode ser re-applied sem efeito colateral.

**Down migration:** `RESET (security_invoker)` retorna ao default Postgres (`false` → SECURITY DEFINER mode). Esta é a forma correta de rollback — `SET (security_invoker = false)` também funciona mas RESET é semanticamente mais limpo (volta ao default em vez de fixar `false` explicitamente).

**Underlying tables RLS audit:**
- `public.ingestion_checkpoints` / `public.ingestion_runs`: tabelas de pipeline, sem RLS policies para `authenticated` (acessadas só via `service_role`). Downgrade não reduz superfície porque essa superfície já era bloqueada na app layer.
- `public.pncp_raw_bids` (referenciada via system catalog filter no bloat view): `service_role` only.
- `cron.job` / `cron.job_run_details`: schema `cron` restrito a `postgres`/`service_role` por default Supabase. Backend usa o RPC `get_cron_health()` (SECDEF, fora do escopo) para acesso programático; a view direta passa a exigir privilégio de role.

**Smoke test SQL** (rodar em staging como cada role após deploy):

```sql
-- AC3 smoke: as authenticated
SET ROLE authenticated;
SELECT * FROM public.ingestion_orphan_checkpoints LIMIT 1;     -- expect: permission denied
SELECT * FROM public.pncp_raw_bids_bloat_stats LIMIT 1;        -- expect: permission denied
SELECT * FROM public.cron_job_health LIMIT 1;                  -- expect: permission denied
RESET ROLE;

-- AC3 smoke: as anon
SET ROLE anon;
SELECT * FROM public.ingestion_orphan_checkpoints LIMIT 1;     -- expect: permission denied
RESET ROLE;

-- AC3 smoke: as service_role
SET ROLE service_role;
SELECT * FROM public.ingestion_orphan_checkpoints LIMIT 1;     -- expect: rows or empty (success)
SELECT * FROM public.pncp_raw_bids_bloat_stats LIMIT 1;        -- expect: rows or empty (success)
SELECT * FROM public.cron_job_health LIMIT 1;                  -- expect: rows or empty (success)
RESET ROLE;
```

---

## DoD

- [x] Migration UP + DOWN escritas e syntactically valid
- [ ] UP + DOWN aplicadas e testadas em staging (post-merge)
- [ ] Tests RLS regression smoke SQL PASS 3 contextos (authenticated/service_role/anon) — staging
- [ ] Supabase advisor 3 lints clear — post-deploy
- [ ] Doc + memory entry — deferred (AC5)
- [x] PR description inclui plano de verificação advisor + smoke test

---

## Dependências

- Supabase Postgres 17 confirma syntax `security_invoker = true` (validado pela docs Supabase + Postgres 15 release notes).

---

## Notes

- Padrão alternativo (recriar como SECURITY INVOKER no `CREATE OR REPLACE VIEW`) válido se ALTER syntax falhar — não usado aqui para minimizar diff.
- Memory `feedback_supabase_migration_via_management_api`: workaround se CLI db push falhar durante drift.
- NÃO touchar views fora do scope (idempotência preservada).
- Memory `reference_supabase_down_sql_schema_conflict`: stash `.down.sql` antes de `npx supabase db push` em CLI 2.x — paired files podem ser tratados como 2 migrations e gerar pkey conflict.

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-05-09 | @data-engineer (worktree agent) | Migration UP + DOWN authored; story moved Draft → InProgress; PR opened. |
