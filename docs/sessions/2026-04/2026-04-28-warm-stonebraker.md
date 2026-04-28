# Session warm-stonebraker — 2026-04-28

## Objetivo

Mover defesa permanente para prod (PR #534 + #535) + soak + schema drift discriminator.

## Resultado

**Incident vivo no encerramento.** Backend prod DOWN 35+ min. Tratativa em sessão paralela.

## Entregue

- **PR #534 MERGED** `170b368c` (security: Resend webhook HMAC verify + service_role statement_timeout=60s) — deploy SUCCESS `71932168` 11:14 UTC, migration aplicada
- **PR #535 MERGED** `1ab05e25` (sitemap budget + asyncio.to_thread + negative cache, 6 routes) — depois **REVERTIDO** `e17252c9` durante incident, código de fix continua válido para próxima merge
- **Down.sql do PR #534 aplicada** via Supabase Management API: `ALTER ROLE service_role RESET statement_timeout` + `NOTIFY pgrst, 'reload config'` — `pg_roles.rolconfig=null` confirmado
- **WEB_CONCURRENCY: 4 → 1** em `bidiq-backend` Railway service (root cause amplifier descoberto durante incident)
- **Railway scale**: 0 (pause loop) → 1 (resume)

## Impacto em receita

**Negativo:** 35+ min outage api.smartlic.tech.

Defense-in-depth do PR #534 (HMAC verify) permanece — único ganho persistente.

## Causa raiz (advisor-confirmed)

Supabase Disk IO Budget depleted → todas queries timeout → schema_contract + ensure_bucket startup falham → Application startup nunca completa → healthcheck nunca green → Railway kill container → ON_FAILURE retry → loop.

**Amplifier descoberto durante incident:** `WEB_CONCURRENCY=4` em prod (memory `reference_railway_hobby_plan_actual` mencionava possibility 2-4 mas não real production value). 4 workers × 18 cron tasks = 72 tasks paralelas hitting Supabase ao startup. Reduzido p/ 1.

**Não-causa:** PR #535 código (revert deploy hit identical failure — código não é variável).

**Sessão paralela diagnosticou:** worker `bidiq-worker` continua UP agravando carga.

## Pendente (dono + prazo)

- [ ] **Supabase Disk IO Budget recovery** — manual via dashboard fqqyovlzdzimiwfofdjk OR Supabase support — sem ETA
- [ ] **Pausar `bidiq-worker` enquanto Disk IO drena** — @devops — imediato
- [ ] **Re-merge PR #535** após recovery — branch já deletada, recriar a partir de `1ab05e25` ou cherry-pick
- [ ] **STORY blog/stats wedge classe** — `/v1/blog/stats/contratos/cidade/{c}/setor/{s}` 14044s slow_requests (9 issues Sentry) — mesma classe sitemap fix
- [ ] **STORY sectors/stats wedge classe** — `/v1/sectors/{N}/stats` 5498s (8 issues Sentry) — mesma classe
- [ ] **STORY orgao/stats** — count 467 — não coberto PR #529
- [ ] **GH Actions deploy.yml + Railway repo watcher dual-trigger** — desabilitar uma das paths (deploy.yml é redundante; Railway repo watcher já cobre)
- [ ] **Schema drift `20260427015000`** — adiada (mesma sessão anterior)
- [ ] **SEN-FE-001 frontend recidiva** — adiada

## Riscos vivos

- **Backend prod offline** — receita parando enquanto durar incident
- **PR #534 statement_timeout=60s migration aplicada em DB MAS rolconfig=null pós-down.sql** — repo migration vs DB realidade desincronizado; próxima migration `supabase db push --include-all` pode reaplicar (Migration Check workflow agora vai falhar)
- **PR #535 reverted commit em main** — código de fix bom existe local em `_reversa_sdd/` ou requer cherry-pick. Branch `fix/sitemap-endpoints-async-budget` já deletada via `--delete-branch`

## Memory updates

- **NEW** `feedback_dual_deploy_railway_gh_actions.md` — push to main triggers 2 simultaneous DEPLOYING (Railway repo watcher + GH Actions deploy.yml). Both have `rootDirectory:"backend"`. Sob Disk IO pressure 4 workers competem startup queries. Memory anterior `reference_railway_rootdir_prod_incident_2026_04_23` só cobria FAILED rootdir noise; este é race **DEPLOYING**.
- **NEW** `feedback_web_concurrency_4_amplifier.md` — `WEB_CONCURRENCY=4` em prod era amplificador de saturation Supabase (72 cron tasks paralelas startup vs 18 com 1 worker). Memory `reference_railway_hobby_plan_actual` mencionava 2-4 possible mas real production gap não estava documentado.
- **UPDATE** `reference_supabase_service_role_no_timeout_default.md` — adicionar: `statement_timeout=60s` aplicado via PR #534 reverteu via Management API (Down.sql). Cuidado: futura `supabase db push --include-all` reaplica migration sem revert no .down.
- **NEW** `feedback_supabase_diskio_root_cause_pattern_amplification.md` — atualizar memory existente: PR #534 statement_timeout=60s **piora** behavior sob Disk IO depleted (queries killed antes de completar fallback paths). Não aplicar timeout=60s service_role enquanto Disk IO Budget <50% disponível.
- **NEW** `reference_supabase_management_api_query.md` — quando CLI db push rejeita ou backend offline, aplicar SQL via `POST https://api.supabase.com/v1/projects/{ref}/database/query` com `Authorization: Bearer $SUPABASE_ACCESS_TOKEN`. Funciona mesmo sob Disk IO degradado (retry 2-5x). Memory `feedback_supabase_migration_via_management_api` cobre full migration via API; este é single-query.

## KPI sessão

| Métrica | Alvo charter | Resultado |
|---|---|---|
| Shipped to prod | ≥1 | 1 (PR #534) |
| Incidentes novos | 0 | **1** (P0 backend outage 35+min) |
| Tempo em docs | <15% | ✅ |
| Tempo em fix não-prod | <25% | ❌ (~70% incident response) |
| Instrumentação adicionada | ≥1 evento | 0 (deploy não estabilizou) |

**2 métricas vermelho** → próxima sessão começa com retrospective 10min.

## Como retomar próxima sessão

```bash
# 1. Verificar Supabase Disk IO recovery
SBT=$(grep SUPABASE_ACCESS_TOKEN .env | cut -d= -f2)
curl -s -X POST "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SBT" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT 1;"}'
# Se responde rápido (<2s): Disk IO recuperou

# 2. Verificar backend
curl -s --max-time 5 -w "%{http_code}/%{time_total}s\n" https://api.smartlic.tech/health/live

# 3. Se UP: validar PR #534 statement_timeout state
SBT=$(grep SUPABASE_ACCESS_TOKEN .env | cut -d= -f2)
curl -s -X POST "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SBT" -H "Content-Type: application/json" \
  -d '{"query": "SELECT rolname, rolconfig FROM pg_roles WHERE rolname='\''service_role'\'';"}'
# rolconfig=null significa down.sql aplicada (statement_timeout removido)

# 4. Re-merge PR #535 (cherry-pick 1ab05e25 em nova branch)
git fetch origin
git checkout main && git pull
git checkout -b fix/sitemap-endpoints-async-budget-v2
git cherry-pick 1ab05e25  # commit original PR #535
# Resolver conflito api-types/openapi snapshot se houver
git push -u origin fix/sitemap-endpoints-async-budget-v2
gh pr create ...
```

## Decisões deliberadamente fora-de-escopo

- Fix proativo blog/stats + sectors/stats classe — só após recovery
- Schema drift `20260427015000` discriminator — só após recovery
- SEN-FE-001 frontend recidiva — só após recovery
- 6 stories drafts triagem @po — sessão dedicada
- Compute upgrade Supabase — defer até confirmar drain não basta
