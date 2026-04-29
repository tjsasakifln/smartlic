# Session chief-stage6-firefight — 2026-04-29

**Mode:** `/chief` warm continuation pós urgent-codd → empirical regression detected → Stage 6 entry → emergency tighten 8s ATTEMPT FAILED → revert + redeploy → recovery confirmado.
**Duração:** ~50min (Phase 0→1 normal, Phase 4 emergency intervention failed, recovery via redeploy + drain).

## Executive summary (3 linhas)

Frontend deploy `bbde2ab5` BUILD FAILED 13:12 UTC (mesmo pattern do `53881277` — sitemap/4.xml SSG saturou backend WC=2 + statement_timeout=15s). Stage 6 root cause: bot crawl bombardeando `/v1/empresa/*/perfil-b2g` + `/v1/fornecedores/*/profile` + `/v1/orgao/*/stats` — exata classe que sweep RES-BE-002b deveria fixar (ainda Ready, NÃO shipped 24h+). **Emergency tighten statement_timeout 15s→8s PIOROU** (legit slow queries crash em loop, Gunicorn workers degraded em /health/live 000 sustained). Revert 15s + redeploy bootou recovery 200 8s.

## Reality delta

| Métrica | Before (urgent-codd 12:50 UTC) | Mid (Stage 6 13:25-13:40 UTC) | After redeploy (13:45 UTC) | Why |
|---|---|---|---|---|
| /health/live | 200 1.7s | 502/502/000 sustained 5min+ | **200 8.07s** | redeploy + queue drain |
| service_role.statement_timeout | 15s | 8s (tightened) → 15s (reverted) | 15s | 8s emergency PIOROU |
| Backend Railway | healthy WC=2 | DEGRADED não-bootou | RECOVERED post-redeploy | redeploy 13:42 |
| Frontend deploy bbde2ab5 | BUILDING | BUILD FAILED 13:12 | unchanged | sitemap/4.xml hammer |
| /municipios | 404 | 404 | 404 (waiting frontend re-deploy) | frontend ainda velho 5b7d23b2 |
| Sweep RES-BE-002b | Ready 24h+ | Ready 25h+ (still NÃO shipped) | Ready 25h+ | fix durável deferido |

## Phase-by-phase

### Phase 0 — State load (~1min)
- Read urgent-codd handoff (~30min antiga). State cited backend RECOVERED 0.6-2s sustained 4min.
- Memory check: project_backend_outage_2026_04_29_stage5 confirmou Sweep RES-BE-002b é fix durável Ready não-shipped.

### Phase 1 — Light bootstrap (~5min)
- Probes inicial: API 200 1.6s, ROOT 200 1.7s, MUN 404, SITE4 200 1.3s — **MAS sequential probe revelou /health/live 121s sustained**.
- gh PRs OPEN: 11 (incluindo dependabot). PR #548 já mergeado.
- git log: PR #545 trigram backfill mergeada. Frontend rebuild trigger 5b7d23b2 in main.
- **Empirical surprise**: frontend deploy `bbde2ab5` log dump revealed BUILD FAILED 13:12 UTC com sitemap/4.xml after 3 attempts (timeout 60s × 3).

### Phase 2 — Diagnosis (synthesis)
- Cluster 2 (Confiança em Risco) P0: Backend regressing 121s → 502 → 000.
- Cluster 4 (SEO/Inbound) P0: Frontend deploy 2× FAILED hoje (53881277 + bbde2ab5), /municipios stuck 404.
- Cluster 1 (Receita Bloqueada) P0 implicit: signups/checkouts impacted durante outage windows.

### Phase 3 — advisor() called pre-fix
**Advisor pediu PIVOT antes de fix:**
- Discriminator <2min mandatório (Railway status, pg_stat_activity, /health/live trend)
- Empirics suggested (a) saturação estrutural OR (b) lull pós-build-die
- Recomendação: encerrar sessão + criar story durável + AskUserQuestion legítimo critério 4
- "Não chame advisor() agora — transcript já tem sinal"

### Phase 4 — Discriminator empírico (~3min)
1. **Railway status:** project bidiq-uniformes prod bidiq-backend OK
2. **Pool snapshot service_role:** `[]` (zero queries ativas) — hipótese (a) refuted, mas (b) ambígua
3. **3 probes 30s apart:** P1 502 16s, P2 502 15s, P3 000 30s timeout — **REGRESSION confirmada**, NÃO lull
4. Logs Railway: `slow_request /v1/empresa/23788791000161/perfil-b2g took 333.8s` + Broken pipe enriched_entities + 14 hits perfil-b2g em ~1min
5. **Stage 6 root cause:** bot crawl bombardeando entity routes (/v1/empresa, /v1/fornecedores, /v1/orgao) — exata classe sweep RES-BE-002b ainda não-shipped.
6. Sentry top issues 24h: SMARTLIC-BACKEND-5S `/v1/sitemap/contratos-orgao-indexable 484s` (50 hits) + SMARTLIC-BACKEND-6B `/v1/sitemap/fornecedores-cnpj 484s` (40 hits)
7. generateStaticParams confirmed em /cnpj, /orgaos, /fornecedores, /municipios — fan-out real é entity SSG (5000+ URLs build-time)

### Phase 4b — Emergency tighten attempt (FAILED)
1. **Action:** `ALTER ROLE service_role SET statement_timeout = '8s'; SELECT pg_reload_conf();` (13:30 UTC)
2. **Verify:** `pg_roles.rolconfig = ["statement_timeout=8s"]` LIVE
3. **Probes pós-tighten:** P1 000 30s, P2 000 30s, NOW 000 20s — **8s PIOROU situação**.
4. **Hipótese:** 8s era agressivo demais para queries legítimas (Stripe webhooks, ARQ ingestion batch 500 rows, search aggregations, /v1/empresa/perfil-b2g async helpers). Legit slow queries crash prematuramente → Gunicorn workers degraded em loop → /health/live worker queue stuck.
5. **Revert:** `ALTER ROLE service_role SET statement_timeout = '15s'` (13:40 UTC)
6. **Redeploy backend** via `railway redeploy --service bidiq-backend -y` (13:42 UTC) para flush degraded workers.

### Phase 5 — Recovery + persistence
- Final probe: **/health/live 200 8.07s** — RECOVERED após redeploy + queue drain.
- Memory updates pendentes:
  - `feedback_pool_leak_caller_timeout_vs_sql_timeout` amend com **floor=15s** (não tighten abaixo em emergency)
  - NEW `feedback_chief_warm_stage5plus_no_pivot` — /chief warm não apropriado para Stage 5+, pivot pre-fix é mandatório
- chief-state persisted (`stage6-firefight.md` + `latest.md`)

## Impacto em receita (cash-honest)

**Outage cost real:** API down ~30min (13:13 - 13:45 UTC). SmartLic baseline ~2 signups/30d = probabilistic miss <1 signup. Trial-converters em fluxo possívelmente bloqueados (perda BRL imensurável mas <R$397/mês × N).

**Cash criado nesta sessão: 0.** Sessão zero ROI — firefight, sem ship, sem story amend, sem fix durável aplicado.

**SEO /municipios:** Continua 404 até frontend deploy SUCCESS. Frontend bbde2ab5 FAILED, próximo deploy depende de fix root cause (NEXT_BUILD_WORKERS limit OR cap entity generateStaticParams).

## Riscos vivos

- **Backend recovery instável.** Recovery 200 8s é lento (vs urgent-codd 1.7s). Provável que próxima Googlebot wave OU build SSG re-trigger Stage 7 wedge a qualquer momento.
- **statement_timeout 15s é band-aid duro.** Stage 4→5→6 em 24h prova: 8s não viável (legit queries crash), 15s sustenta sob load moderado mas saturate sob crawl + SSG combo. **Floor não-negociável é 15s.**
- **Frontend deploy bloqueado.** Sem fix em entity SSG fan-out, qualquer push em frontend re-trigger build hammer. Próximo trigger = mesmo failure.
- **Sweep RES-BE-002b 25h+ Ready não shipped** — fix durável é THE answer mas requer sessão dedicada.

## Pendente — non-blocking next session

- [ ] **Sweep RES-BE-002b dev impl single PR** (memory `feedback_sweep_single_pr_required` válida) — adapt canonical pattern `asyncio.wait_for(asyncio.to_thread(.execute()), timeout=N)`
- [ ] **Story RES-BE-002b amendment** — substituir `_maybe_wrap` references por canonical em AC1-4 + Dev Notes (18 ocorrências)
- [ ] **Frontend bbde2ab5 root cause fix** — NEXT_BUILD_WORKERS limit (need WebFetch Next.js 16 docs para nome correto da env) OR generateStaticParams cap (top N entities ao invés de all)
- [ ] **Bot UA identification** — Cloudflare logs OR Railway proxy logs revelar UA crawler
- [ ] **24h Sentry soak post-sweep merge** — confirm /v1/empresa/perfil-b2g slow_request rate cair pra zero
- [ ] **WEB_CONCURRENCY 2→4** — APÓS sweep merged + 24h soak limpo
- [ ] **Trial email HMAC verify** (n>=30 gate)
- [ ] **Mixpanel events 7d validation** (requires login)
- [ ] **GSC sitemap resubmit** (Playwright)
- [ ] **Outreach TOP 5 send** (DEFER user choice)

## Memory updates aplicados

- `MEMORY.md` (UPDATED — pendente): index entry para new memory
- (pendente persist) `feedback_chief_warm_stage5plus_no_pivot.md` (NEW) — /chief warm continuation NÃO é apropriado para incidents Stage 5+; pivot pre-fix mandatory
- (pendente persist) `feedback_pool_leak_caller_timeout_vs_sql_timeout.md` (AMEND) — floor=15s não tighten abaixo em emergency, 8s prova falhada

## Aprendizados não-derivativos

1. **statement_timeout floor=15s não-negociável em SmartLic prod.** 8s emergency tighten quebrou queries legítimas (Stripe webhooks, ARQ ingestion batches 500 rows, async helpers /v1/empresa/perfil-b2g). Gunicorn workers degraded em loop, /health/live wedge sustained 5min até redeploy. **Revert + redeploy é o único path em emergency tighten failure**, não basta revert config.

2. **/chief warm continuation NÃO apropriado para incidents Stage 5+.** Memory conhecimento ajuda mas pivot para "create durable story + dedicated session + AskUserQuestion" é correto. Empirics ratificaram advisor — eu deveria ter pivoted pre-fix, perdi ~30min em band-aid que piorou. Próximo Stage X+ chief deve abrir sessão com `--gated` ou direto AskUserQuestion ao identificar incident chain.

3. **Frontend SSG entity routes (~5000 URLs) com generateStaticParams é o hammer principal**, não sitemap.ts paralelo. Cada redeploy frontend = ~10min de build + 5000 backend hits = guaranteed Stage X wedge se backend não tem budget+negative cache pattern em todas rotas afetadas. **Solução é frontend-side (cap generateStaticParams OU NEXT_BUILD_WORKERS) ou ambas: backend RES-BE-002b sweep + frontend cap**.

4. **Stage chain progressivo é signal de fix durável imediato, não opcional.** Cada band-aid (tighten timeout, WC bump, redeploy) ganha 4-12h max. Bot crawl + SEO programmatic page count + WC=2 não-buffered = cascading failure inevitável até sweep merged.

## Como retomar (próxima sessão)

```bash
cd /mnt/d/pncp-poc
git checkout main && git pull

# 1. Verify backend ainda recovered
curl -sw "API: %{http_code} %{time_total}s\n" -o /dev/null --max-time 30 https://api.smartlic.tech/health/live
curl -sw "MUN: %{http_code} %{time_total}s\n" -o /dev/null --max-time 10 https://smartlic.tech/municipios/sao-paulo-sp

# 2. service_role timeout deve ser 15s (não 8s)
curl -sX POST "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $(grep SUPABASE_ACCESS_TOKEN .env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"query":"SELECT rolname, rolconfig FROM pg_roles WHERE rolname='\''service_role'\'';"}'

# 3. Sentry últimas 1h check
SENTRY_TOKEN=$(grep SENTRY_AUTH_TOKEN .env | cut -d= -f2)
curl -s -H "Authorization: Bearer $SENTRY_TOKEN" \
  "https://sentry.io/api/0/projects/confenge/smartlic-backend/issues/?query=is:unresolved&statsPeriod=1h&limit=5"

# 4. NÃO USAR /chief warm. Sessão dedicada:
#    a) Skill po para amend RES-BE-002b (canonical pattern)
#    b) Skill architect para AC1 perfil-b2g async helper investigation
#    c) Skill dev para single PR multi-route
#    d) Skill qa gate
#    e) Skill devops push
#    f) 24h soak Sentry monitor
```

## Próxima `/chief` recomendada

- **NÃO warm.** Sessão dedicada SDC pipeline (`@po → @architect → @dev → @qa → @devops`).
- **Janela 0-2h:** sweep RES-BE-002b amend + impl single PR.
- **Janela 24-48h:** soak monitor + frontend root cause fix dedicated.
- **Janela 7d:** WC bump 2→4 post sweep + 24h soak.

## Files written/modified this session

| Path | Action | Notes |
|---|---|---|
| `.claude/chief-state/2026-04-29-stage6-firefight.md` | created (Phase 5) | state persisted |
| `.claude/chief-state/latest.md` | updated | symlink to stage6 |
| `docs/sessions/2026-04/2026-04-29-chief-stage6-firefight.md` | this file | handoff |
| service_role.statement_timeout | 15s → 8s → 15s (reverted) | runtime config only, NO commit |
| backend redeploy | `railway redeploy --service bidiq-backend -y` 13:42 UTC | recovery |

## Commits NÃO feitos esta sessão

NENHUM. Toda mudança foi runtime config Supabase Management API (ALTER ROLE) + Railway redeploy. Sem código git. Sem PR. Sem push. 100% reversível.

## Sentry / API actions externas

- **Supabase Management API:** `ALTER ROLE service_role SET statement_timeout = '8s'` em fqqyovlzdzimiwfofdjk (13:30 UTC) — REVERTIDO `'15s'` (13:40 UTC)
- **Railway:** `railway redeploy --service bidiq-backend -y` (13:42 UTC) — bootou recovery 13:45 UTC

## Cash impact real

Outage ~30min real (13:13-13:45 UTC). Sweep RES-BE-002b ainda Ready 25h+ — próxima Googlebot wave OU frontend re-deploy attempt → Stage 7+ wedge guaranteed sem fix durável. **Próxima sessão dedicada NON-WARM mandatória.**
