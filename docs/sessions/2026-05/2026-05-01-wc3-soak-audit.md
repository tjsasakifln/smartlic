# Audit wc3-soak — 2026-05-01

**Gerado em:** 2026-05-02 02:10 UTC  
**Propósito:** Sonda de saúde +24h pós Railway Hobby→Pro + WEB_CONCURRENCY 2→3 (~2026-04-30 23:00 UTC).  
**Soak target:** zero HTTP 5xx + p95 latência estável vs baseline.

---

## Contexto do upgrade

| Item | Valor |
|------|-------|
| Data do upgrade | ~2026-04-30 23:00 UTC |
| Plano Railway | Hobby → Pro |
| `WEB_CONCURRENCY` antes | 2 |
| `WEB_CONCURRENCY` depois | 3 |
| Referência session | `docs/sessions/2026-04/2026-04-30-stage8-frontend-build-recovery.md` (não encontrado no repo no momento da sonda — pode estar em branch não-mergeado) |

**Baseline declarado (2026-04-30 ~02:03 UTC, pré+pós bump):**
- `/health/live`: HTTP 200, 0.6–2s (probe 1 era 1.9s durante fila de redeploy; probes 2-3 sub-1s)
- `/health/ready`: HTTP 200
- Stage 8 routes post-PR #535/#555: sub-2s vs pré-fix 583s

---

## Resultado das probes

### Método

```bash
for endpoint in '/health/live' '/health/ready' \
  '/v1/empresa/76205699000198/perfil-b2g' \
  '/v1/orgao/87366159000102/stats' \
  '/v1/fornecedores/35068104000112/profile'; do
  for i in $(seq 1 10); do
    curl -sS -o /dev/null -w '%{http_code} %{time_total}\n' "https://api.smartlic.tech$endpoint"
  done
done
```

**Total planejado:** 50 probes (10 × 5 endpoints).

### Resultado bruto

| Endpoint | Probes | HTTP 403 | HTTP 5xx | HTTP 2xx | Latência observada |
|----------|--------|----------|----------|----------|--------------------|
| `/health/live` | 10 | 10 | 0 | 0 | min 0.048s / max 0.391s |
| `/health/ready` | 10 | 10 | 0 | 0 | min 0.050s / max 0.134s |
| `/v1/empresa/76205699000198/perfil-b2g` | 10 | 10 | 0 | 0 | min 0.042s / max 0.071s |
| `/v1/orgao/87366159000102/stats` | 10 | 10 | 0 | 0 | min 0.040s / max 0.113s |
| `/v1/fornecedores/35068104000112/profile` | 10 | 10 | 0 | 0 | min 0.041s / max 0.154s |
| **TOTAL** | **50** | **50** | **0** | **0** | — |

### Diagnóstico do 403

```
HTTP/2 403
x-deny-reason: host_not_allowed
```

**Causa:** O ambiente de execução desta sonda (cloud sandbox / Claude Code) está listado como não-autorizado pelo Railway Edge / Cloudflare WAF da Railway. O 403 é bloqueio de rede **antes** de chegar ao processo uvicorn — **não é erro de aplicação**. A latência ultra-baixa (40–390ms sem body) confirma que a resposta vem do edge, não do backend.

**Implicação:** Zero HTTP 5xx observados — mas por bloqueio de rede, não por saúde do servidor. **As probes NÃO puderam alcançar o backend de produção.** Sstat de latência de aplicação não está disponível.

---

## Comparação com baseline

| Métrica | Baseline (2026-04-30) | Esta sonda (2026-05-02) | Delta |
|---------|-----------------------|-------------------------|-------|
| `/health/live` HTTP 200 rate | 100% | **N/A** (bloqueado) | — |
| `/health/live` p95 latência | ~1.0s | **N/A** | — |
| Stage 8 routes HTTP 200 rate | 100% (pós-PR #535/#555) | **N/A** | — |
| Stage 8 p95 latência | <2s (pós-fix, baseline 583s) | **N/A** | — |
| HTTP 5xx observados | 0 | 0 (edge block) | ✅ 0 |

---

## Contexto do repo (cross-check)

### Commits relevantes desde o upgrade (~2026-04-30)

| Commit | Título | Impacto Stage 8 |
|--------|--------|-----------------|
| PR #603 (`545db38`) | `fix(backend): RES-BE-015 sweep — wrap remaining 19 bare .execute() in _run_with_budget` | ALTO — corrige a classe exata de bug (sync `.execute()` bloqueando event loop) que causou os outages Stage 2-3 em 2026-04-27 |
| PR #600 (`910ac17`) | `fix(backend): RES-BE-015 sweep (anterior)` | ALTO — mesmo padrão |
| PR #592 (`59eeba4`) | `fix(backend): PNCPRateLimitError carries retry_after; raised on 429 exhaustion` | MÉDIO — resilência PNCP |
| PR #595 (`c1b5752`) | `fix(seo): SEO-026 — Allow /alertas-publicos in robots.txt` | BAIXO |

**PR #603 é especialmente relevante:** a sessão `2026-04-27-sorted-bumblebee` documentou que `/contratos/orgao/{cnpj}/stats` tinha o "mesmo padrão" de sync `.execute()` bloqueando event loop, mas ficou como "Stage 4 latente — baixa prio". PR #603 (19 bare `.execute()` restantes) provavelmente fecha esse gap.

### Estado do runtime declarado (memória de sessão)

- **RUNNER=uvicorn** ativo (não Gunicorn prefork — CRIT-084 resolve SIGSEGV)
- **WEB_CONCURRENCY=3** (bump de 2)
- **statement_timeout service_role = 60s** (ALTER ROLE em 2026-04-27)
- **ROUTE_TIMEOUT_S** ativo (60s middleware, SSE/health exempts)
- **Time budget waterfall** ativo: pipeline(100s) > per_source(70s) > per_uf(25s)
- **Negative cache 5min** em `/v1/empresa/{cnpj}/perfil-b2g` e `/v1/fornecedores/{cnpj}/profile` (PR #529)

### Riscos vivos documentados (de sessões anteriores)

| Risco | Origem | Status estimado |
|-------|--------|-----------------|
| `/contratos/orgao/{cnpj}/stats` sem budget/cache (Stage 4 latente) | `2026-04-27-sorted-bumblebee` | Provavelmente mitigado por PR #603 (RES-BE-015 sweep) |
| Recidiva wedge por Googlebot wave (24-48h janela) | `2026-04-27-sorted-bumblebee` | Mitigado por WC=3 + RES-BE-015 |
| WEB_CONCURRENCY > 1 + in-memory progress tracker = SSE bug | `GTM-RELIABILITY-VERDICT.md` | Persiste — `_active_trackers` dict in-memory incompatível com multi-worker |

---

## Verdict

### **⚠️ INCONCLUSIVE — probes bloqueadas pelo edge Railway/Cloudflare**

O ambiente de execução desta sonda não tem permissão de acesso ao host `api.smartlic.tech` (Railway WAF retorna `x-deny-reason: host_not_allowed`). Nenhuma das 50 probes alcançou o processo uvicorn. Não é possível emitir veredito GREEN/YELLOW/RED baseado nestas probes.

**O que se pode afirmar com dados de repositório:**
- Zero commits de revert/hotfix/incident pós-2026-04-30 no `main`
- PR #603 (RES-BE-015) reforça a resiliência dos endpoints Stage 8 que eram o alvo da sonda
- Runtime configurado com múltiplas camadas de defesa (timeout waterfall, statement_timeout, negative cache, RUNNER=uvicorn)

---

## Recomendação

### Para o usuário executar manualmente (das suas máquinas/Railway shell)

```bash
# Probe rápida — 10 por endpoint, output: http_code + latência
PROD=https://api.smartlic.tech
for ep in '/health/live' '/health/ready' \
           '/v1/empresa/76205699000198/perfil-b2g' \
           '/v1/orgao/87366159000102/stats' \
           '/v1/fornecedores/35068104000112/profile'; do
  echo "=== $ep ==="
  for i in $(seq 1 10); do
    curl -sS -o /dev/null -w '%{http_code} %{time_total}\n' "$PROD$ep"
  done
done
```

**Critérios de veredito:**

| Resultado | Veredito | Ação |
|-----------|---------|------|
| Zero 5xx + p95 `/health/live` <3s + p95 Stage 8 <5s | **GREEN** | Continuar WC=3; considerar WC=4 no próximo ciclo de soak |
| Zero 5xx + p95 `/health/live` 3–10s OU p95 Stage 8 5–30s | **YELLOW** | Continuar WC=3; deferir WC=4 |
| 1+ 5xx OU p95 `/health/live` >10s OU p95 Stage 8 >30s | **RED** | Reverter: `railway variables --service bidiq-backend --set WEB_CONCURRENCY=2` |

### Verificações manuais adicionais recomendadas (não cobertas aqui)

1. **Sentry `slow_request`** — verificar se `rate(slow_request[1h])` decaiu vs baseline pré-WC=3
2. **CRIT-046 recidiva** — `grep "pool exhaustion\|connection timeout" <(railway logs --service bidiq-backend --tail 1000)` 
3. **Prometheus histogram** — `histogram_quantile(0.95, rate(smartlic_pipeline_duration_seconds_bucket[5m]))` para p95 real
4. **In-memory SSE tracker** — validar que `/buscar` + `/buscar-progress/{id}` funcionam end-to-end com WC=3 (risco documentado em `GTM-RELIABILITY-VERDICT.md`: `_active_trackers` dict in-memory + multi-worker = cross-worker miss)
5. **ARQ worker** — `railway logs --service bidiq-worker --tail 200` confirmar sem SIGSEGV / statement_timeout kills em ingestion

---

## Caveats

- **Esta sonda NÃO é um full audit.** Sentry `slow_request` count, CRIT-046 grep em logs Railway, Prometheus histogram `smartlic_pipeline_duration_seconds` e Mixpanel funnel conversion NÃO estão cobertos. O usuário deve executar essas verificações manualmente.
- **403 `host_not_allowed`** significa que o ambiente Claude Code (sandbox cloud) está bloqueado pelo Railway Edge. Este é o comportamento esperado de um WAF bem configurado. **Não indica problema na aplicação.**
- **Sessão de referência `2026-04-30-stage8-frontend-build-recovery.md`** não encontrada no repo no momento desta sonda. Se estiver em branch não-mergeado, o baseline declarado na task pode ter contexto adicional não refletido aqui.
- **WC=3 + `_active_trackers` in-memory** é um risco conhecido (documentado em `GTM-RELIABILITY-VERDICT.md`). Testar o fluxo `/buscar` → SSE progress manualmente antes de elevar para WC=4.

---

## Como retomar

```bash
# Verificar se sonda manual GREEN:
railway variables --service bidiq-backend  # confirmar WEB_CONCURRENCY=3

# Se GREEN e quiser elevar para WC=4:
railway variables --service bidiq-backend --set WEB_CONCURRENCY=4
# Aguardar redeploy + soak 4h antes de confirmar

# Se RED — reverter:
railway variables --service bidiq-backend --set WEB_CONCURRENCY=2
```
