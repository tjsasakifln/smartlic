# Execute Sweep Priority List (RES-BE-002c AC2)

**Generated:** 2026-04-29
**Source:** `docs/audit/execute-callsites-2026-04-29.md` (57 unprotected callsites)
**Story:** [RES-BE-002c](../stories/2026-04/RES-BE-002c-execute-audit-sweep-remaining.story.md)

---

## Tier classification

Ranked by Sentry impressions 7d + Stage 4-7 wedge cycle evidence (memory `project_backend_outage_2026_04_29_stage5` — 10 routes mapped P0).

### Top tier — sweep this PR (Wave 5)

Routes Sentry-priorized P0 / P1 com bot fan-out crítico (Googlebot/Bingbot crawl wave saturou Stage 5 sob WC=1).

| File:line | Function | Tier | Sweep status (this PR) |
|-----------|----------|------|------------------------|
| `contratos_publicos.py:184` | `_fetch_sector_contracts` | **P0** | ✅ wrapped `_run_with_budget` 10s + 503 graceful + Stage 5 evidence |
| `contratos_publicos.py:236` | `orgao_contratos_stats` | **P0** | ✅ wrapped + negative cache 5min on timeout |
| `orgao_publico.py:225` | `_build_orgao_stats` | **P0** | ✅ wrapped + 503 graceful |
| `orgao_publico.py:376` | `_fetch_contracts_data` | **P0** | ✅ wrapped 8s + graceful return zero on timeout |
| `municipios_publicos.py:378` | `municipio_profile` enrich | **P1** | ✅ wrapped 5s + continue without enrichment on timeout |

### Mid tier — defer next session

Auth path / low bot impact / single-user flows. Não justificam single-PR sweep agora.

| File:line | Function | Tier | Notes |
|-----------|----------|------|-------|
| `mfa.py:107,128,157,193,205,235,246,273,304,310` | MFA setup/verify (10 callsites) | P3 | Auth path — usuário-driven; baixo bot impact. Story future |
| `conta.py:101,113,257,265` | Account update | P3 | Self-service; raro |
| `auth_signup.py:94` | Signup profile update | P3 | One-time per signup |
| `referral.py:79,92,107,163,205,255,280` | Referral tracking | P3 | Funcionalidade rara |
| `plans.py:87` | Plan assignment | P3 | Admin operation |
| `founding.py:100,162,182,230` | Founding leads | P3 | Marketing funnel; baixo volume |
| `features.py:70,95,135` | Feature flags read | P2 | Cached upstream |
| `lead_capture.py:48` | Lead capture | P3 | Form submission |
| `comparador.py:165` | Comparador | P3 | User feature |

### Low tier — defer indefinite

Internal/admin/observability rotas com tráfego mínimo. Sweep sem ROI.

| File | Notes |
|------|-------|
| `observatorio.py:324` `_query_historical_sync` | Sync function — caller responsibility wrap |
| `sitemap_cnpjs.py:178,216,321` | Sync function — caller wraps via PR #549 / #535 |
| `sitemap_orgaos.py:112,145,262` | Same — sync helpers |
| `sitemap_licitacoes.py:272` | Same |
| `sitemap_licitacoes_do_dia.py:133` | Same |
| `indice_municipal.py:266` | Internal cron-driven |
| `compliance_publicos.py:177` | Low-traffic public route |
| `blog_stats.py:39,924` | Blog stats — internal admin |
| `itens_publicos.py:443` | Item profile — defer |
| `empresa_publica.py:450` | **Already protected** (`sb_execute` em circuit breaker) — false positive grep |

---

## Sweep pattern (this PR)

Pattern aplicado no top-tier:

```python
# Antes
resp = (
    sb.table("...").select("...").eq(...).limit(N).execute()
)
# Depois
from pipeline.budget import _run_with_budget

def _query():
    return sb.table("...").select("...").eq(...).limit(N).execute()

try:
    resp = await _run_with_budget(
        asyncio.to_thread(_query),
        budget=10.0,
        phase="public_route",
        source="<route>.<endpoint>",
    )
except asyncio.TimeoutError:
    # Graceful degradation: 503 ou negative cache 5min ou empty result
    raise HTTPException(status_code=503, ...)  # ou continue degraded
```

## Negative cache (where applicable)

`contratos_publicos.py:236` (orgao_contratos_stats) adiciona negative cache 5min em TimeoutError — previne Googlebot retry storm (memory `feedback_build_hammers_backend_cascade`). Cache pattern reused from `_set_cached(_orgao_contratos_cache, ...)` existing.

## Soak protocol (24h post-merge — AC6)

Monitor Sentry 24h:

```bash
SENTRY_TOKEN=$(grep SENTRY_AUTH_TOKEN .env | cut -d= -f2)
# Pre-merge baseline:
curl -s -H "Authorization: Bearer $SENTRY_TOKEN" \
  "https://sentry.io/api/0/organizations/confenge/issues/?project=smartlic-backend&statsPeriod=24h&query=culprit:public_route" \
  | jq '[.[] | .count | tonumber] | add'

# Post-merge (24h):
# - Zero new "after 3 attempts" Sentry events em /v1/contratos/*publicos
# - Zero new wedge events (slow_request >60s)
# - p95 latency /v1/contratos/orgao/*/stats <2s sustained
# - smartlic_pipeline_budget_exceeded_total{phase="public_route"} not zero (budget enforcement working)
```

Critério ROLLBACK: ≥3 wedge events em 6h pós-deploy → revert + re-investigate.

## Mid tier sweep (next session)

Após 24h soak top-tier verde, próxima sessão pode sweep mid tier (mfa.py 10 callsites + conta.py 4 + referral.py 7 + auth_signup.py + plans.py = ~25 callsites). Pattern idêntico; menor risco já que rotas auth-driven não têm bot fan-out.

## Refs

- Memory: `feedback_pool_leak_caller_timeout_vs_sql_timeout` (caller wait_for vs SQL pool)
- Memory: `feedback_sweep_single_pr_required` (Stages 4+5 confirmed 2×)
- Memory: `feedback_cluster_sweep_pattern` (BTS-style hypothesis-first)
- Memory: `project_backend_outage_2026_04_29_stage5` (10 routes mapped P0 — empresa, contratos, orgao publicos)
- Memory: `feedback_build_hammers_backend_cascade` (Googlebot retry storm pattern)
- Code: `backend/pipeline/budget.py:28-73` `_run_with_budget` signature
- Code: `backend/routes/contratos_publicos.py:31-33` negative cache pattern (replicated)
