# Postmortem — Backend Wedge Stages 4-7 (2026-04-27 a 2026-04-29)

## Status

Final — 2026-04-29 23:59 UTC. Recovery orgânico confirmado (sitemap-4 = 8.630 URLs, /health/live 200 1.8s sustained). Tripwire ativa até 2026-05-06.

Story: `docs/stories/2026-04/OPS-POSTMORTEM-001-stage-4-7-audit-consolidado.story.md`. Runbook reativo paralelo: PR #551 (OPS-RECOVERY-001).

---

## Resumo Executivo

Entre 2026-04-27 e 2026-04-29 o backend SmartLic entrou em ciclo recurrent de **wedge HTTP** (workers stuck simultâneos, http=000 sustained, build/SSG cascade fail) atravessando 4 stages (4 → 5 → 6/6.5 → 7) que somaram **~50 minutos de outage real ao usuário** (12:14 → 13:00 UTC em 2026-04-29) + **~14h de SEO programmatic regression** (/municipios + 219 entity URLs servindo 404, sitemap-4 stuck empty), em cima dos Stages 1-3 prévios documentados em `project_backend_outage_2026_04_27`. **9 sessões `/chief` documentadas + 12 PRs (#533-#549) + 22 stories criadas + 4 ADRs**. Frontend deploy falhou 9× consecutivos durante a janela.

**Root cause confirmado:** classe arquitetural única — **bot/cron load + sync `.execute()` em rotas DB-bound em handler async, sem `_run_with_budget`/`asyncio.wait_for + asyncio.to_thread` + sem negative cache + service_role sem `statement_timeout`** = pool exhaustion → workers stuck → wedge total. Hipótese de capacity (Hobby Plan 48 vCPU/48 GB) **REFUTADA empíricamente** em 2026-04-29 Stage 6.5 (WC=1, WC=2 e WC=4 produziram outcome idêntico). Caller-side `asyncio.wait_for` **NÃO libera pool Supabase** até server-side `statement_timeout` matar a query — fix definitivo é server-side `ALTER ROLE service_role SET statement_timeout = '15s'` (memory `feedback_pool_leak_caller_timeout_vs_sql_timeout`).

**Status atual:** API estável (probes 1.8s), sitemap-4 valid, schema drift `20260427015000` reconciliado (PR `394ae9a8` + repair --status applied), service_role timeout=15s LIVE em prod, sweep RES-BE-002b shipped (PR #549). **Memory leak hypothesis (5.5GB RSS sustained) ainda não-confirmada** — diagnóstico defer 24-48h pós-soak via SEN-BE-010 Phase 0 (PR #554, tracemalloc + memory-snapshot endpoint). Tripwire Sentry `slow_request >60s sustained 5min` ativa até 2026-05-06; se disparar, dropar trabalho e reabrir Stage-8 audit.

**Cash-honest:** Impacto direto **<1 signup probabilístico** (baseline n=2 reais 30d, GSC 126 clicks/28d). Imunização real é prevenir Stage-8 sob primeira aquisição orgânica via SEO programmatic — janela 7-30d. Postmortem atende necessidade de knowledge-persistence para onboarding e regra arquitetural (não-defensive readout founder + advisor).

---

## Timeline Consolidada

```
2026-04-27 ~01-04 UTC    Stage 1+2+3   Mixpanel/Clarity silenced (7d) + warm-stonebraker wedge
                  |                     + sitemap/blog_stats wedges (PRs #533-#537/#544)
                  |                     Pattern: sync .execute() + WEB_CONCURRENCY=1 + no budget
                  |
2026-04-29 ~01-02 UTC    Stage 4       keen-neumann — API /health/live http=000 sustained
                  |                     Recovery via GraphQL deploymentRedeploy(76f8d6fa) workaround
                  |                     (latest b89c717b silent twin FAILED Railway rootDir bug recidiva)
                  |                     bfa3eb8e: alertas-publicos ISR 1h → 24h (-24× fan-out)
                  |
2026-04-29 ~12-13 UTC    Stage 5       chief-savvy-jasmine (continuação espírito) — saturation
                  |                     not crashed: 200 em 54s sob WC=1 + bot fan-out
                  |                     10 routes mapped Sentry-priorized P0=3
                  |                       (empresa.perfil_b2g 482×2248s, contratos.fornecedor 224×3027s,
                  |                        orgao.stats 478×130s)
                  |                     Migration 20260427213410 unapplied = CRIT-050 silent broken
                  |                     PR #545 SEN-BE-001b service_role statement_timeout=60s shipped
                  |
2026-04-29 12:13-12:42   Stage 6 (P0)  chief-urgent-codd — frontend deploy crashed
                  |                     SSG burst (31 workers × 4148 pages × 6 sub-sitemap) +
                  |                       Googlebot + cron = pool 35/25 sustained (CRIT-046)
                  |                     Detection 12:13 UTC, recovery 12:42 UTC
                  |                     Fix1: ALTER ROLE service_role SET statement_timeout='15s'
                  |                       (Management API curl) — pool turnover 4× faster
                  |                     Fix2: WEB_CONCURRENCY 1 → 2 (Railway env var)
                  |
2026-04-29 13:46-14:30   Stage 6.5     chief-stage65-firefight — frontend 6× FAIL consecutive
                  |                     WC=2→4 bump TENTATIVA — outcome IDÊNTICO (capacity refuted)
                  |                     6 redeploys, todos /sitemap/4.xml after 3 attempts
                  |                     7 band-aids speculative queimadas
                  |                     Memory feedback_chief_warm_stage5plus_no_pivot reforçada
                  |
2026-04-29 ~14:50-15:10  Stage 7       chief-stage7-wedge-discriminator — pivot mandatório
                  |                     Discriminadores frontend (BACKEND_URL internal/cap MAX_STATIC/
                  |                       compile mode) avaliados:
                  |                       Disc 1 INVIABLE at build (Railway private network runtime-only)
                  |                       Disc 2 user-cancelled (founder moat SEO)
                  |                       Disc 3 RISKY (compat × output:'standalone' unverified)
                  |                     Cloudflare INNOCENT (Railway direct domain timeout idêntico)
                  |                     docs/analysis/chief-stage7-definitive-solution.md output
                  |
2026-04-29 ~16-22 UTC    Recovery      chief-swift-mendel — migration drift fix completo
                  |                     394ae9a8 backfill 20260427015000 trigram index
                  |                     repair --status applied + stash 17 .down.sql (CLI 2.x bug)
                  |                     PR #547 STORY-431 observatorio merged (4c8648bb)
                  |                     PR #548 SEN-BE-007 sitemap merged (c23fa182)
                  |                     CRIT-050 unblocked (validated empíricamente)
                  |
2026-04-29 22:42-23:00   Recovery      chief-drift-paulo — backend organic recovery confirmed
                                        /health/live 200 1.8s sustained, sitemap-4 = 8.630 URLs
                                        Schema drift Paulo investigation (NÃO bypass paywall —
                                          dual source-of-truth bounded 2 users)
                                        Tripwire established (Sentry slow_request >60s → 2026-05-06)
```

### Stage 4 — 2026-04-29 ~01-02 UTC

**Sintoma:** API `/health/live` http=000 sustained. Caminho de pagamento bloqueado (signups + checkouts + Stripe webhooks down). Frontend deploys 4× FAILED por backend wedge cascade. Padrão idêntico a Stages 2-3 prévios (`project_backend_outage_2026_04_27`).

**Discriminador-chave:** Latest deploy `b89c717b` era **silent twin FAILED** por bug de path Railway rootDirectory recidiva (memory `reference_railway_rootdir_prod_incident_2026_04_23`). Deploy bom era `76f8d6fa` anterior.

**Fix:** Recovery via Railway GraphQL `deploymentRedeploy(id="76f8d6fa")` mutation em vez de redeploy comum. Commit `bfa3eb8e` reduziu fan-out: `alertas-publicos` ISR 1h → 24h (405 pages, 24× redução fan-out).

**Memory:** `project_backend_outage_2026_04_29_stage4`, `reference_railway_404_triage`.

### Stage 5 — 2026-04-29 ~12-13 UTC (continuação espírito)

**Sintoma:** API NÃO crashed = **saturated**. 200s respondidos em 54s sob WC=1 + bot fan-out. Discriminator empírico crítico — distinguir wedge (workers stuck 100%) de saturated (workers atendendo lentamente). `/v1/empresa/{cnpj}` + `/v1/contratos/*` + `/v1/orgaos/*` Sentry P0 priorized.

**Mapeamento sweep RES-BE-002b** (10 routes Sentry-driven, P0=3, P1=2, P2=5):

| # | Route | Endpoint | Sentry 24h | Status |
|---|-------|----------|------------|--------|
| 1 | `empresa_publica.py` | `/v1/empresa/{cnpj}/perfil-b2g` | 482×2248s | budget=0, NOT FIXED |
| 2 | `contratos_publicos.py` | `/v1/fornecedores/{cnpj}/profile` | 224×3027s + ConnectionTerminated | budget=0 |
| 3 | `orgao_publico.py` | `/v1/orgao/{cnpj}/stats` | 478×130s | budget=0 |
| 4 | `itens_publicos.py` | `/v1/itens/{id}/profile` | 49×2248s | budget=0 |
| 5 | `blog_stats.py` | `/v1/blog/stats/...` | 1 recente×965s | partial |
| 6-10 | comparador/compliance/indice_municipal/sitemap_cnpjs/sitemap_orgaos | low Sentry | partial / NOT FIXED |

**Discoveries adicionais:** Migration `20260427213410` (PR #545) unapplied silently em prod = **CRIT-050 silent broken** (drift `20260427015000` bloqueava ALL `supabase db push`). Memory `feedback_crit_050_silent_broken_during_drift` criada.

**Fix:** PR #545 SEN-BE-001b — service_role statement_timeout=60s formalizado (handler 57014 mapped); Migration backfill via PR #544.

**Memory:** `project_backend_outage_2026_04_29_stage5`, `feedback_sweep_single_pr_required`.

### Stage 6 + 6.5 — 2026-04-29 12:13-14:30 UTC

**Stage 6 (P0 outage real, ~50min wall):** PR #548 frontend deploy crashed 12:13:54 UTC. SSG burst (31 workers × 4148 pages × 6 sub-sitemap fetches = ~25k requests num burst de minutos) saturou pool 35/25 sustained. CRIT-046 + blog_stats 10s budget firing + fornecedor 30s + sitemap 25s — pool kept growing. Backend probes 5/5 timeout 15s.

**Discriminator empírico:** Bot 503 hotfix (advisor primeira proposta) **NÃO se aplica** — Node.js SSG fetcher não usa bot User-Agent. Pivot: tighten server-side `statement_timeout`.

**Fix Stage 6:**
1. `ALTER ROLE service_role SET statement_timeout = '15s'; SELECT pg_reload_conf();` via Supabase Management API (12:42 UTC) — pool turnover 4× faster.
2. `WEB_CONCURRENCY=1→2` Railway env var (12:55 UTC) — 2 workers + 15s safety net.
3. Verification: `/health/live = 200 1.7s`, `/v1/sitemap/cnpjs = 200 2.24s`. Recovered.

**Stage 6.5 (capacity hypothesis refuted):** Backend recovered MAS frontend deploy 6× FAIL consecutivos (mesmo padrão `/sitemap/4.xml after 3 attempts`). Tentativas band-aid:

1. WC=1→2 bump (Stage 6 — incluído)
2. WC=2→4 bump (Stage 6.5)
3. statement_timeout 60s→15s tighten (Stage 6 — efetivo, mas não-resolveu Stage 6.5)
4. 6 redeploys frontend
5. PR #549 RES-BE-002b sweep — 9 callsites wrappados em `_run_with_budget`

**Conclusão Stage 6.5:** WC=4 outcome IDÊNTICO a WC=2 e WC=1. **Hipótese capacity Gunicorn worker count REFUTADA empíricamente** (memory `reference_railway_hobby_plan_actual` — Hobby tem 48 vCPU / 48 GB, não 1 GB).

**Memory:** `feedback_pool_leak_caller_timeout_vs_sql_timeout`, `feedback_chief_warm_stage5plus_no_pivot`, `feedback_web_concurrency_4_amplifier`.

### Stage 7 — 2026-04-29 ~14:50-15:10 UTC

**Sintoma:** State file Stage 6.5 claim "200 sub-3s sustained" foi OUTDATED — backend wedged again post-handoff. Frontend cron health proxy 100+ failures since 12:29 UTC. Local curl 5/5 timeouts a `https://api.smartlic.tech/health/live` AND `https://bidiq-uniformes-production.up.railway.app/health/live` (Railway direct domain) — **Cloudflare innocent**. TCP connects, TTFB never arrives. Backend Python process alive (logs flowing) but ALL workers stuck.

**Discriminadores user-suggested (avaliados):**

| # | Disc | Verdict |
|---|------|---------|
| 1 | `BACKEND_URL=internal:8000` Dockerfile build | INVIABLE at build (Railway docs: private network only at runtime) |
| 2 | Cap `_MAX_STATIC_*` 1000→50 | DESCARTADO user (founder moat — "cap não é interesse para SEO massivo") |
| 3 | `--experimental-build-mode=compile` | RISKY (Next.js 16 compat × `output: 'standalone'` unverified) |

**Conclusão Stage 7:** Frontend discriminators são **secundários**. Real active root cause = backend HTTP layer wedged at runtime, NOT SSG burst. Pivot: deep root-cause backend wedge cycle audit + sweep universal (RES-BE-002c + SEN-BE-010 Phase 0 mem leak hypothesis).

**Output:** `docs/analysis/chief-stage7-definitive-solution.md` — solução multi-camada documentada (4 camadas: Recovery / Backend Sweep / Frontend Resilience / Preventivo).

### Recovery — 2026-04-29 ~16-23 UTC

**chief-swift-mendel:** Migration drift full fix (commit `394ae9a8` backfill 20260427015000 + `repair --status applied` + stash 17 `.down.sql` para CLI 2.x bug). PR #547 STORY-431 observatorio merged (`4c8648bb`). PR #548 SEN-BE-007 sitemap merged (`c23fa182`). CRIT-050 unblocked (deploy.yml auto-applied 20260427213410 → `pg_roles.rolconfig` BEFORE `null` → AFTER `["statement_timeout=60s"]`).

**chief-drift-paulo (22:42-23:00 UTC):** Backend organic recovery confirmed (200 OK 1.8s sustained 9/9 health probes). Sitemap recovered (8.630 URLs). PR #549 sweep stuck UNSTABLE 11h por body metadata gap (gh api PATCH fix aplicado, memory `reference_pr_body_edit_persistence`). Schema drift Paulo (`paywall bypass` aparente) discriminado: **NÃO é bypass sistemático** — dual source-of-truth `user_subscriptions.expires_at` vs `profiles.trial_expires_at` bounded a 2 users (memory `project_paulo_paywall_bypass_root_cause_2026_04_29`). Tripwire estabelecida.

---

## Impact Assessment

| Métrica | Pre-incident (2026-04-26) | Stage 4 (~01h) | Stage 5 (~12-13h) | Stage 6/6.5 (~12-15h) | Stage 7 (~15h) | Recovery (23h) |
|---------|--------------------------|----------------|-------------------|-----------------------|----------------|----------------|
| `/health/live` latency | 200 <500ms | http=000 timeout | 200 em 54s (saturated) | 502/15s timeout | http=000 (5/5) | 200 1.8s |
| sitemap-4.xml URLs | 7368 | 0 (404) | stuck | stuck | 0 | 8630 |
| Frontend deploy state | OK | 4× FAILED | OK pré-12:13 | 9× FAILED consecutive | wedge cascade | recovered |
| /municipios entity URLs | 219 indexed | 404 | 404 | 404 (14h) | 404 | recovery pendente |
| Sentry P0 events/h | 0 | N (cron 100+ since 12:29) | high (482 empresa, 478 orgao) | sustained | sustained | 0 |
| service_role statement_timeout | NULL (CRIT-080 hotfix) | NULL | 60s (PR #545 LIVE 16:00) | 15s (12:42 emergency) | 15s | 15s |
| WEB_CONCURRENCY | 1 | 1 | 1 | 1→2→4 (refuted)→2 stable | 2 | 2 |
| Pool utilization (Supabase 25) | <30% | unknown | unknown | 35/25 (CRIT-046) | unknown | drained |
| Real users impacted (n) | n=2 (1 ativo Paulo) | n=2 | n=2 | n=2 | n=2 | n=2 |
| Outage real (signup blocked) | 0 | janela ALB timeout | 0 (saturated não-down) | ~50min (12:14-13:00) | wedge re-entry | 0 |

**Cash impact direto:** <1 signup probabilístico perdido (baseline 2 signups/30d × ~50min outage / 30d × 24h = ~0.001). Cash impact indireto SEO: 219 entity URLs 404 ~14h pode degradar Googlebot indexing janela 7-30d (perda probabilística <1 trial/mês a CTR 1.3% × 126 GSC clicks/28d).

---

## Root Cause Analysis

### Hipóteses descartadas (refutadas empíricamente)

1. **Capacity Gunicorn worker count.** Stage 6.5 testou WC=1, WC=2, WC=4 — **outcome IDÊNTICO** (`/sitemap/4.xml after 3 attempts` em todas). Hobby Plan = 48 vCPU / 48 GB por serviço (memory `reference_railway_hobby_plan_actual`), não saturável por workers. **Refuted**.

2. **Cloudflare egress / DNS rate limit.** Stage 7 curl direto a `bidiq-uniformes-production.up.railway.app/health/live` (bypassa Cloudflare) timeout idêntico a `api.smartlic.tech`. **Refuted**.

3. **WEB_CONCURRENCY=4 amplifier de Supabase saturation.** Memory `feedback_web_concurrency_4_amplifier` previa 4×18 cron tasks = 72 paralelas startup. Stage 6.5 confirmou: WC=4 piora startup boot mas NÃO é root cause do steady-state wedge.

4. **Bot 503 hotfix (User-Agent rate limit).** Stage 6 advisor primeira proposta. Refutada — Node.js SSG fetcher não usa bot User-Agent identificável; build hammer é independente de bot detection.

5. **ISR-cached-404-durante-wedge.** Stage 4 hipótese inicial. Refutada via discriminator: runtime servia build PRÉ-wedge `2c0b2dac` FAILED durante wedge. Real: build artifact stale + `notFound()` cached.

### Hipóteses ativas (confirmadas — fix arquitetural shipped/em progresso)

1. **Sync `.execute()` em handler async sem `_run_with_budget`/`asyncio.wait_for + asyncio.to_thread`.** 🟢 CONFIRMADO Stages 2-3-4-5. Sweep RES-BE-002b (PR #549 merged) cobre 9 callsites. RES-BE-002c (PR #555 OPEN) cobre top-tier audit remaining.

2. **Caller-side `asyncio.wait_for` NÃO libera pool Supabase.** 🟢 CONFIRMADO Stage 6 (memory `feedback_pool_leak_caller_timeout_vs_sql_timeout`). Caller cancela await mas thread continua bloqueada em Postgres response → conexão HELD até server-side `statement_timeout`. **Fix definitivo:** `ALTER ROLE service_role SET statement_timeout = '15s'` (LIVE em prod). Floor 15s não-negociável (8s testado e PIOROU).

3. **Service_role sem `statement_timeout` default.** 🟢 CONFIRMADO Stage 2 (memory `reference_supabase_service_role_no_timeout_default`). Anon=3s, authenticated=8s, service_role=NULL. Backend que usa SERVICE_ROLE_KEY rodava queries ilimitadas. Histórico timeline: NULL → 60s (PR #545, 2026-04-27) → 15s (Stage 6 emergency, 2026-04-29).

4. **Build SSG hammers backend cascade.** 🟡 INFERIDO (memory `feedback_build_hammers_backend_cascade`). 31 workers × 4148 pages × 6 sub-sitemap fetches = burst load profile diferente de steady-state Googlebot. Mitigação: SEN-FE-002 + SEN-FE-003 (resilience + decouple).

5. **Memory leak 5.5GB RSS sustained.** 🔴 LACUNA — diagnóstico defer 24-48h pós-soak. Suspeitos não-discriminados: cron loops? OAuth refresh pool? LLM client warm context? httpx connection pool? **Mitigação:** SEN-BE-010 Phase 0 PR #554 instrumenta `tracemalloc` + `/v1/admin/memory-snapshot` endpoint + gunicorn worker rotation. Phase 1 (root cause investigation) gated em primeira ocorrência tripwire OU 2026-05-06 calendar trigger.

### Hipóteses ativas paralelas (não-relacionadas direto, mas surfaced no ciclo)

6. **Schema drift dual source-of-truth (Paulo "paywall bypass").** 🟢 CONFIRMADO bounded 2 users (`check_quota` lê `user_subscriptions`, `extend_trial_atomic` grava `profiles`). Story DATA-DRIFT-001 P1 fix 3h (memory `project_paulo_paywall_bypass_root_cause_2026_04_29`).

7. **CRIT-050 silent broken durante drift.** 🟢 CONFIRMADO 2+ dias unapplied. Migration drift `20260427015000` bloqueia ALL `supabase db push`; subsequentes ficam committed mas not-applied silenciosamente. Discriminator: `pg_roles.rolconfig` query Management API antes NOTIFY pgrst.

---

## 5 Lições Aprendidas

### L1 — Sweep universal single PR > granular per-route

**Memory:** `feedback_sweep_single_pr_required`.

Fix-per-route insufficient confirmado **2× consecutivos** (Stage 4 e Stage 5+6). Granular per-route mantém pattern em rotas vizinhas que voltam a saturar pool. Padrão correto:

- **Single PR multi-arquivo Sentry-priorized** (P0 first: empresa.perfil_b2g, orgao.stats, contratos.fornecedor)
- **WEB_CONCURRENCY bump SEPARADO** + 24h soak post-merge
- Ship `_run_with_budget` + `asyncio.to_thread` + negative cache em todos os callsites simultaneamente

**Aplicação:** Sempre ALWAYS aplicar pattern sweep em sweeps futuros (RES-BE-002c, próximas stories de wedge). Anti-pattern: PR único cobrindo 1 rota com promessa de "follow-up cobrirá demais" — confirmado degenerar em recidiva 2x.

### L2 — Caller `asyncio.wait_for` NÃO libera Supabase pool

**Memory:** `feedback_pool_leak_caller_timeout_vs_sql_timeout`.

Pattern aparente:
```python
await asyncio.wait_for(
    asyncio.to_thread(lambda: sb.table('x').select('*').execute()),
    timeout=25.0,
)
```
parece protegido. **NÃO É.** Caller catch TimeoutError e retorna negative cache, MAS thread continua bloqueada em Postgres response — conexão HELD até server-side `statement_timeout`. Sob 31 burst SSG concurrent, pool 25 satura sem turnover.

**Fix definitivo único:** server-side `ALTER ROLE service_role SET statement_timeout = '15s'`. Floor 15s não-negociável (Stage 6.5 testou 8s e PIOROU — legit ingestion + Stripe webhooks queries quebraram). Reversível via mesmo Management API curl.

**Aplicação:** Toda role usada por backend que executa queries DEVE ter `statement_timeout` configurado. Discriminator: `SELECT rolname, rolconfig FROM pg_roles WHERE rolname='service_role';` — `null` rolconfig = bomba relógio.

### L3 — Capacity hypothesis refutation + Warm continuation pivot

**Memory:** `feedback_chief_warm_stage5plus_no_pivot`.

Stage 5+6.5 testou **7 band-aids speculative** (8s tighten + WC=2 bump + WC=4 bump + 6 redeploys frontend) — TODAS falharam mesmo padrão `/sitemap/4.xml after 3 attempts`. Hipótese capacity Gunicorn refutada empíricamente.

**Aplicação — pivot mandatório quando >2 fix attempts produzem mesmo failure pattern:**
- Cold session dedicated em vez de warm continuation
- Discriminador empírico <5min ANTES de mais ação speculative (memory `feedback_advisor_critical_discernment`)
- Dropar a hipótese e abrir nova investigation lane

Anti-pattern: 7 band-aids consecutive na mesma sessão warm queimando recursos sem produzir cash + sem isolar root cause real. /chief Stage 5+ pivota para sessão dedicated SDC pipeline OR plain investigation, NÃO continua warm.

### L4 — Discovery > speculation (Phase 0 antes de Phase 1)

**Memory:** `project_p0_zany_kurzweil_2026_04_29` (handoff pattern), `feedback_advisor_critical_discernment`.

Memory leak 5.5GB RSS sustained foi suspeita Stage 4-7, MAS **não-confirmada**. Antes de gastar dias em "fix memory leak", instrumentar primeiro:

**SEN-BE-010 Phase 0 (PR #554):** tracemalloc enabled + `/v1/admin/memory-snapshot` admin endpoint retornando top-25 allocations + gunicorn worker rotation `--max-requests 1000 --max-requests-jitter 100`. Roda 24-48h em prod sob carga real. **Phase 1 (fix)** só inicia após snapshot revelar smoking gun OR tripwire fired.

**Aplicação:** Em fix complexo, sempre Phase 0 = instrumentation antes de Phase 1 = root-cause action. Discriminator empírico barato (<5min) ANTES de ação custosa (>1d) é mandatório.

### L5 — Tripwire post-recovery + AT RUNTIME variant Disc 1

**Memory:** existing tripwire em `feedback_chief_warm_stage5plus_no_pivot` ampliada via OPS-RECOVERY-001.

**Tripwire ativa até 2026-05-06:** Sentry alert rule — `slow_request >60s` events sustained 5min OR ≥25 events em 24h → page on-call → **drop other work** até root cause identificado OR 2026-05-06 calendar release.

**Disc 1 user-suggested salvado AT RUNTIME** (não-build):
- Stage 7 confirmou Railway private network only at runtime, não build phase
- AT RUNTIME variant em **OPS-DEVOPS-001** (`docs/stories/2026-04/OPS-DEVOPS-001-runtime-internal-hostname.story.md`) — frontend container curl `bidiq-backend.railway.internal:8000/health/live` <100ms; build mantém public URL via separate ARG `BACKEND_URL_BUILD`
- Bypassa Cloudflare 5s+ DNS overhead para 30k+ runtime ISR fetches/dia

**Aplicação:** Quando user surface multi-discriminator, evaluar cada um por context (build-time vs runtime) — não-rejeitar all-or-nothing. AT RUNTIME pode ser válido mesmo quando AT BUILD inviável.

---

## Action Items

| ID | Título | Owner | Status | Story / PR | ETA |
|----|--------|-------|--------|------------|-----|
| AI-1 | Memory leak Phase 1 root cause investigation | @architect | DEFER 24-48h post-soak | SEN-BE-010 | gated em tripwire OR 2026-05-06 |
| AI-2 | MV/ETL sitemap-licitacoes-indexable (decouple SSG fetch) | @data-engineer | DEFER post-soak | SEN-BE-009 | Sprint 2 (2026-05-06) |
| AI-3 | CI build budget guard (block deploy if SSG fetch >X) | @devops | Wave A esta sessão | OPS-CI-001 | Sprint 2 |
| AI-4 | Weekly load test reproducer Stage 4-7 pattern | @qa | Wave A esta sessão | OPS-CI-002 | Sprint 2 |
| AI-5 | Bot rate-limit tier por User-Agent (Googlebot/Bingbot/crawler) | @architect | Wave B esta sessão | OBS-001 | Sprint 2 |
| AI-6 | Frontend runtime internal hostname (Disc 1 AT RUNTIME) | @devops | Wave B esta sessão | OPS-DEVOPS-001 | Sprint 2 |
| AI-7 | Frontend resilience combo (SSG fetch defensive + decouple) | @dev | Wave C esta sessão | SEN-FE-002 + SEN-FE-003 | Sprint 2 |
| AI-8 | Backend wedge recovery runbook executável | @architect | OPEN PR #551 | OPS-RECOVERY-001 | imediato |
| AI-9 | Memory snapshot endpoint + tracemalloc + gunicorn rotation | @architect | OPEN PR #554 | SEN-BE-010 Phase 0 | imediato |
| AI-10 | Schema drift Paulo dual source-of-truth fix | @data-engineer | Sprint atual | DATA-DRIFT-001 | 3h estimate |
| AI-11 | RES-BE-002c top-tier sweep audit + remaining .execute() | @dev | OPEN PR #555 | RES-BE-002c | imediato |
| AI-12 | SEO PROG-008 frontend getBackendUrl helper + CI gate | @dev | OPEN PR #552 | SEO-PROG-008 | imediato |
| AI-13 | FOUND-SCALE-002 frontend safeFetch + fetchWithBudget Sentry | @dev | OPEN PR #553 | FOUND-SCALE-002 | imediato |
| AI-14 | SEO-PROG-006 defer integral + @architect decision | @architect | OPEN PR #556 | SEO-PROG-006 | imediato |

**Open PRs já em fluxo (cobertos pelos action items acima):** #551 (OPS-RECOVERY-001), #552 (SEO-PROG-008), #553 (FOUND-SCALE-002), #554 (SEN-BE-010 Phase 0), #555 (RES-BE-002c), #556 (SEO-PROG-006 defer).

**Closed/merged durante o ciclo:** #533 (blog_stats), #534 (Resend HMAC + service_role 60s), #535/#539 (sitemap budget), #536 (mixpanel-python), #537 (Clarity ARG), #540 (new_bids_notifier rename), #544 (sitemap module cache + trigram backfill), #545 (SEN-BE-001b service_role 60s formal), #547 (observatorio budget), #548 (sitemap Sentry breadcrumb + retry), #549 (RES-BE-002b sweep 9 callsites).

---

## Tripwire Protocol (Active until 2026-05-06)

**Threshold disparo:**
- Sentry rule: `slow_request` event level=error/fatal com `latency_ms >= 60000` sustained 5min (rolling window)
- OR: `slow_request` events count ≥ 25 em 24h sliding window
- OR: backend p95 `/health/ready` latency >5s sustained 5min (Sentry custom metric)

**Resposta automática on-page:**
1. Sentry alert → page on-call (Tiago direto, single-founder)
2. Validar tripwire não é noise via curl matrix (memory `reference_railway_404_triage`):
   ```bash
   curl -sw "API: %{http_code} %{time_total}s\n" -o /dev/null --max-time 15 https://api.smartlic.tech/health/live
   curl -sw "DIRECT: %{http_code} %{time_total}s\n" -o /dev/null --max-time 15 https://bidiq-uniformes-production.up.railway.app/health/live
   curl -sX POST "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" -d '{"query":"SELECT rolname, rolconfig FROM pg_roles WHERE rolname='\''service_role'\'';"}'
   ```
3. Se confirmed wedge → seguir runbook OPS-RECOVERY-001 (PR #551):
   - Stage 1: Railway redeploy backend (3min)
   - Stage 2: Se band-aid não resolve, GraphQL `deploymentRedeploy(last-known-good-id)` workaround
   - Stage 3: Se memory leak suspeitado, capturar `/v1/admin/memory-snapshot` ANTES de redeploy (preserva forensics)
4. **Drop other work** — Stage-8 audit prioridade absoluta até root cause identificado
5. Postmortem update com Stage 8 timeline + lições novas

**Calendar release 2026-05-06:**
- Se tripwire não-disparou em janela 7d: tripwire desativada, mas Sentry alert rule mantida em `level=warning` para visibility contínua
- Se disparou: prorrogar tripwire +14d e reabrir SEN-BE-010 Phase 1 acelerado

---

## Cross-References

### Sessions chief 2026-04-28/29 (9 sessões consolidadas)

- `docs/sessions/2026-04/2026-04-28-chief-savvy-jasmine.md` — Stage 5 saturation mapping (10 routes)
- `docs/sessions/2026-04/2026-04-29-chief-stage65-firefight.md` — Stage 6/6.5 capacity refutation
- `docs/sessions/2026-04/2026-04-29-chief-stage7-wedge-discriminator.md` — Stage 7 pivot mandatório
- `docs/sessions/2026-04/2026-04-29-chief-swift-mendel.md` — migration drift recovery + PRs #547/#548 merge
- `docs/sessions/2026-04/2026-04-29-chief-trusty-pasteur.md` — outreach prep + smoking gun migration
- `docs/sessions/2026-04/2026-04-29-chief-urgent-codd.md` — Stage 6 emergency 12:14-12:42 statement_timeout=15s
- `docs/sessions/2026-04/2026-04-29-chief-drift-paulo.md` — recovery confirmed + tripwire established
- `docs/sessions/2026-04/2026-04-29-keen-neumann.md` — Stage 4 GraphQL deployment redeploy workaround
- `docs/analysis/chief-stage7-definitive-solution.md` — solução multi-camada referência

### Memory entries (7 críticas + 6 contextuais)

**Críticas (cited em lessons):**
- `project_backend_outage_2026_04_27` — Stage 1+2+3 pattern original
- `project_backend_outage_2026_04_29_stage4` — Stage 4 keen-neumann
- `project_backend_outage_2026_04_29_stage5` — Stage 5 saturation mapping
- `feedback_chief_warm_stage5plus_no_pivot` — pivot mandatório (L3)
- `feedback_pool_leak_caller_timeout_vs_sql_timeout` — root cause hypothesis L2
- `feedback_supabase_disk_io_root_cause_pattern` — Disk IO discriminator
- `feedback_sweep_single_pr_required` — L1 padrão sweep

**Contextuais (cited inline):**
- `reference_supabase_service_role_no_timeout_default` — timeline NULL→60s→15s
- `reference_railway_hobby_plan_actual` — capacity refutation evidence
- `feedback_web_concurrency_4_amplifier` — WC=4 amplifier
- `feedback_build_hammers_backend_cascade` — SSG burst hypothesis
- `feedback_crit_050_silent_broken_during_drift` — drift discovery technique
- `project_paulo_paywall_bypass_root_cause_2026_04_29` — schema drift Paulo

### Stories follow-up

- `SEN-BE-009` — MV/ETL sitemap-licitacoes-indexable (decouple SSG fetch)
- `SEN-BE-010` — memory leak RSS guard + profiling (Phase 0 PR #554)
- `OPS-CI-001` — build budget guard CI
- `OPS-CI-002` — weekly load test stage pattern
- `OBS-001` — bot rate-limit tier por User-Agent
- `OPS-DEVOPS-001` — runtime internal hostname Railway
- `SEN-FE-002` — frontend fetch timeout errors (`docs/stories/SEN-FE-002-fetch-timeout-errors.story.md`)
- `SEN-FE-003` — SSG fanout decouple Next phase
- `OPS-RECOVERY-001` — backend wedge recovery runbook (PR #551)
- `RES-BE-002c` — audit + top-tier sweep .execute() (PR #555)
- `DATA-DRIFT-001` — paywall consolidation Paulo (`docs/stories/2026-04/DATA-DRIFT-001-paywall-consolidation-paulo.story.md`)

### PRs shipped/em fluxo (12 merged + 6 OPEN)

**Merged (12):** #533, #534, #535/#539, #536, #537, #540, #544, #545, #547, #548, #549, plus commits direct main `bfa3eb8e`, `5b7d23b2`, `394ae9a8`.

**Open (6):** #551 (OPS-RECOVERY-001), #552 (SEO-PROG-008), #553 (FOUND-SCALE-002), #554 (SEN-BE-010 Phase 0), #555 (RES-BE-002c), #556 (SEO-PROG-006 defer).

---

## Apêndice — Discriminator Playbook (curl + GraphQL + tripwire)

Padrões empíricos validados durante o ciclo, prontos para reuse em Stage 8 hipotético.

### Curl matrix bypass Cloudflare (Stage 7)

```bash
# Cloudflare path
curl -sw "%{http_code} %{time_total}s\n" -o /dev/null --max-time 15 https://api.smartlic.tech/health/live

# Railway direct domain (bypassa Cloudflare)
curl -sw "%{http_code} %{time_total}s\n" -o /dev/null --max-time 15 https://bidiq-uniformes-production.up.railway.app/health/live

# Frontend runtime
curl -sw "%{http_code} %{time_total}s\n" -o /dev/null --max-time 15 https://smartlic.tech/sitemap/4.xml
```

Se ambos timeout idêntico → backend wedge real, NÃO Cloudflare. Se direct OK e cloudflare timeout → DNS/edge issue (raríssimo).

### GraphQL `deploymentRedeploy` workaround (Stage 4)

Quando Railway watcher SKIPPED (commits que não tocam `frontend/`/`backend/`) ou quando latest deploy é silent twin FAILED:

```graphql
mutation {
  deploymentRedeploy(id: "76f8d6fa-...") {  # last-known-good deploy ID
    id
    status
  }
}
```

Bypassa watch patterns + força rebuild a partir de deploy específico. Reference: `project_backend_outage_2026_04_29_stage4`.

### Pool/timeout discriminator (Stage 6)

```bash
# pg_roles statement_timeout check
curl -sX POST "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"SELECT rolname, rolconfig FROM pg_roles WHERE rolname='\''service_role'\'';"}'

# Output esperado: rolconfig = ["statement_timeout=15s"]
# Se null → CRIT-080 hotfix recidiva, fix imediato:
curl -sX POST "https://api.supabase.com/v1/projects/fqqyovlzdzimiwfofdjk/database/query" \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -d '{"query":"ALTER ROLE service_role SET statement_timeout = '\''15s'\''; SELECT pg_reload_conf();"}'
```

### Memory snapshot capture (Stage 8 prep)

Pós-deploy SEN-BE-010 Phase 0 (PR #554):

```bash
# Capturar ANTES de redeploy (preserva forensics)
curl -H "Authorization: Bearer $ADMIN_JWT" https://api.smartlic.tech/v1/admin/memory-snapshot \
  | jq '.top_allocations[:25]' > snapshot-stage-8-$(date +%s).json
```

Reference: `_reversa_sdd/incidents-2026-04-27-29.md` para histórico granular cronológico.

---

## Apêndice B — Anti-patterns reforçados (architecture.md §8)

Padrões já documentados em `_reversa_sdd/architecture.md §8`, **reforçados e cross-referenced** após Stage 4-7:

1. **Sync `.execute()` em handler async sem `_run_with_budget`** — Stages 2-3-4-5 confirmaram. Pattern correto: `_run_with_budget(asyncio.to_thread(lambda: sb...execute()), timeout=N, phase="route_X")` + negative cache 300s.

2. **WEB_CONCURRENCY bump como fix capacity** — Stage 6.5 refutado. WC bump SEPARADO de sweep, post-soak 24h.

3. **Caller-side `asyncio.wait_for` como timeout reliable** — Stage 6 refutado. Sempre combinar com server-side `statement_timeout` no role usado.

4. **Build-time SSG fetch sem fallback** — `revalidate=N` + `cache:'no-store'` quebra SSG (memory `feedback_isr_fetch_cache_alignment_next16`). Use `next:{revalidate:N}` com mesmo N + try/catch return `null`/`[]` fallback.

5. **Migration drift → CRIT-050 silent broken** — discriminator: `pg_roles.rolconfig` query Management API antes NOTIFY pgrst. Backfill committed file ANTES de novas migrations.

6. **Deploy Railway sem watcher path-include** — empty commits e commits fora de `frontend/`/`backend/` são SKIPPED. Bump `LABEL build.timestamp` Dockerfile para forçar.

---

**Postmortem closed 2026-04-29 23:59 UTC.** Próximo update gated em (a) tripwire fired Stage 8, (b) calendar release 2026-05-06 com soak validation, ou (c) SEN-BE-010 Phase 1 root cause memory leak.
