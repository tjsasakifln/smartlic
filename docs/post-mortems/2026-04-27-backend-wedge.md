# Post-Mortem: Backend Wedge Multi-Estagio (2026-04-27)

**Data do Incidente:** 2026-04-26 a 2026-04-30
**Data do Post-Mortem:** 2026-04-30 (backfill documentado em 2026-06-15 conforme #1878)
**Severidade:** SEV1
**Duracao:** 2026-04-26 23:58 UTC ate 2026-04-30 23:59 UTC (~96h com janelas de recuperacao parcial)
**Impacto:** Backend wedged intermitente por 4 dias. Usuarios recebendo 502/504, crawlers bloqueados, deploys falhando.
**Responsavel pelo Post-Mortem:** Tiago Sasaki (@tjsasakifln)
**Revisores:** N/A (unico desenvolvedor)

---

## 1. Timeline (UTC)

### Stage 1 — Crawler Retry Storm (2026-04-26)

| Horario | Evento |
|---------|--------|
| 23:58 | PR #513 merged. Railway frontend rebuild disparado com 4146 paginas SSG. |
| 2026-04-27 00:08 | /health comeca a retornar timeout (5-15s). Backend hobby plan com WEB_CONCURRENCY=1. |
| 00:09 | Frontend build falha: /api/badge/stats exit 1 apos 3 retries. |
| 00:14 | Cache 502 + AbortSignal timeouts — crawlers retry loop sobrecarrega unico worker. |
| 00:14-22:42 | Backend wedged. Statement timeout (8s) no _compute_contratos_stats sobre 2M+ rows. |
| 22:42 | Hotfix #515: blog_stats retorna empty dict em vez de 502 + AbortSignal.timeout(8000) no frontend. Backend recupera. |

### Stage 2 — Googlebot Crawl Saturation (2026-04-27)

| Horario | Evento |
|---------|--------|
| ~13:00 | Railway upgrade para Pro (WEB_CONCURRENCY=4) apos Stage 1. |
| 13:53 | Googlebot crawl sostenido de /cnpj/* e /fornecedores/*. Workers bloqueados em queries lentas. |
| 13:55 | Railway logs: perfil-b2g levou 457.8s, fornecedor profile levou 359.2s. |
| 14:00 | Backend wedged novamente. Todos 4 workers bloqueados. |
| 14:00 | railway redeploy --service bidiq-backend. Container recicla. |
| 14:04 | Backend retorna /health/live 200 < 0.7s. |
| 19:25 | Hotfix #529: hard budget + negative cache em perfil-b2g e fornecedor profile. |

### Stage 3 — Healthcheck Path Bug (2026-04-27)

| Horario | Evento |
|---------|--------|
| ~14:10 | Deploy 71e27195 falha: "1/1 replicas never became healthy!" — /health probe timeout. |
| ~14:15 | Deploy 71e27195 apos 11 tentativas exaure retry budget (5min). Railway nao promove novo container. |
| 11:40 | Hotfix fc31ce2f (parte do PR #529): healthcheckPath /health → /health/live. |
| 11:40 | /health/live e puramente async, sem IO, sempre retorna 200. Deploys voltam a funcionar. |

### Stage 4 — Sitemap/SEO Routes (2026-04-28)

| Horario | Evento |
|---------|--------|
| ~10:00 | Sitemap-4.xml retorna 0 entradas em producao. Pipeline de SEO interrompido. |
| ~14:00 | Hotfix #535/#539: hard budget + asyncio.to_thread + negative cache no sitemap. Backend recupera. |

### Stage 5-8 — Bissection e Correcoes Estruturais (2026-04-29 a 2026-04-30)

| Horario | Evento |
|---------|--------|
| 2026-04-28 | PYTHONASYNCIODEBUG=0 setado em Railway (estava 1 em producao, degradando event-loop). |
| 2026-04-29 | RES-BE-002b sweep: 9 callsites sync .execute() convertidos para _run_with_budget. |
| 2026-04-29 | RES-BE-002c sweep: auditoria completa de .execute() com budget + negative cache. |
| 2026-04-30 | query_datalake convertido de blocking para sb_execute + asyncio.to_thread. |
| 2026-04-30 | Sitemap build-time pre-flight probe adicionado. |
| 2026-05-01 | RES-BE-015 sweep: auditoria CI gate + 19 bare .execute() convertidos. |
| 2026-05-02 | RES-BE-013 CI gate para audit env vars Railway pos-incidente. |
| 2026-05-04 | Billing webhook .execute() convertidos para _run_with_budget. |

---

## 2. 5-Whys — Analise de Causa Raiz

**Problema:** Backend wedged intermitente por 96h, com 3 ondas de recorrencia apos mitigacoes parciais.

1. **Por que o backend wedged na Stage 1?**
   - Frontend rebuild com 4146 SSG pages hammerou o unico worker do hobby plan com requests de crawler que travavam em query lenta no Supabase.
   - **Evidencia:** log railway: `_compute_contratos_stats(uf, municipio_pattern ilike)` em 2M+ rows.

2. **Por que a query era lenta?**
   - Faltava indice composto em `pncp_supplier_contracts(is_active, uf, lower(municipio))`. A query fazia full scan.
   - **Evidencia:** query plan ausente de index scan; `statement_timeout=8s` disparando.

3. **Por que o worker ficava wedged em vez de falhar rapido?**
   - A rota blog_stats levantava HTTPException(502) em vez de retornar resposta vazia. Crawlers retentavam → DDoS no unico worker.
   - Nao havia negative cache para absorver falhas transientes.
   - **Evidencia:** PR #515 diff: `raise HTTPException(502)` → `return empty_stats_dict`.

4. **Por que o mesmo padrao se repetiu nas Stages 2, 3 e 4?**
   - As mitigacoes de cada stage eram parciais (apenas 1 rota de cada vez). Googlebot encontrou outras rotas sem budget/negative cache.
   - sync .execute() bloqueava event loop em varias rotas, impedindo /health/live de responder.
   - Nao havia CI gate para detectar .execute() sem _run_with_budget.
   - **Evidencia:** PR #529 e #535 diffs: 3+ rotas diferentes precisaram do mesmo padrao de fix.

5. **Por que as correcoes foram parciais a cada stage?**
   - Nao existia processo de post-mortem para analisar causa raiz sistemica apos o primeiro incidente.
   - Cada hotfix tratava o sintoma imediato sem auditoria do sistema completo.
   - Faltavam runbooks para respostas coordenadas.
   - **Evidencia:** Nao havia post-mortem apos Stage 1; o proximo stage so foi descoberto quando o Googlebot atingiu a proxima rota.

**Causa Raiz:** Ausencia de budget de tempo, negative cache, e envoltorio async (_run_with_budget) em rotas de SEO long-tail, combinada com sync .execute() bloqueando event loop e ausencia de processo de post-mortem apos o primeiro incidente, permitindo recorrencia por 4 dias.

---

## 3. Impacto

| Metrica | Valor |
|---------|-------|
| Usuarios afetados | Todos os usuarios ativos (trials pagos) — backend indisponivel ou degradado |
| Duracao da indisponibilidade | ~96h com janelas de recuperacao parcial entre stages |
| Requests com erro (5xx) | Centenas a milhares (502/504 de crawlers + usuarios) |
| Erros no Sentry | Multiplos eventos por stage |
| Receita afetada | Risco de churn de trials pagos (pre-revenue) |
| Componentes afetados | backend (web + worker), frontend (build), Supabase (pool) |
| Commits de hotfix | 053eb785, 22ca3d06, fc31ce2f, 82bad614, 4cc8d0d0, bd2c2bb1, 3d7e7e4a, ff6c287f, 910ac17e |

---

## 4. Resposta ao Incidente

### Stage 1

| Fase | Duracao | Observacao |
|------|---------|------------|
| Deteccao ate diagnostico | ~11min (00:08-00:19) | /health timeout detectado por UptimeRobot |
| Diagnostico ate mitigacao | ~22h23min (00:19-22:42) | Causa raiz complexa — crawler + query lenta + cache ausente |
| Mitigacao ate resolucao total | Imediata apos deploy | Hotfix #515 resolveu Stage 1 |
| **MTTR Stage 1** | **~22h34min** | |

### Stage 2

| Fase | Duracao | Observacao |
|------|---------|------------|
| Deteccao ate diagnostico | ~2min | Railway logs diretos |
| Diagnostico ate mitigacao | ~5h31min (13:55-19:25) | Hotfix + healthcheck path fix |
| Mitigacao ate resolucao total | Imediata apos redeploy | Redeploy + hotfix #529 |
| **MTTR Stage 2** | **~5h30min** | |

### Stage 3 (causado pelo fix do Stage 2)

| Fase | Duracao | Observacao |
|------|---------|------------|
| Deteccao ate diagnostico | ~30min | Railway deploy falhando silenciosamente |
| Diagnostico ate mitigacao | ~2h | Identificado que /health timeout causava falso-negativo no healthcheck |
| **MTTR Stage 3** | **~2h30min** | |

### Stages 4-8

| Fase | Duracao | Observacao |
|------|---------|------------|
| Sweep estrutural | 2026-04-28 a 2026-05-04 | Correcoes preventivas em todas as rotas |
| CI gates implementados | 2026-05-01 a 2026-05-02 | Auditorias automatizadas |

### O Que Funcionou Bem

- Circuit breakers existentes impediram cascata para todas as fontes ao mesmo tempo.
- Railway redeploy forcado (`railway redeploy -y`) foi efetivo para recovery imediato.
- Feature flags (LLM_ARBITER_ENABLED, ITEM_INSPECTION_ENABLED) reduziram carga durante stages.
- Uso de negative cache (5min TTL) absorveu retry storms.
- Migracao de RUNNER=gunicorn para RUNNER=uvicorn (CRIT-084) eliminou SIGSEGV.

### O Que Poderia Ser Melhor

- Post-mortem deveria ter sido feito apos Stage 1, antes do Stage 2 ocorrer.
- Nao havia CI gate para detectar sync .execute() fora de _run_with_budget.
- /health endpoint fazia IO (probes externos), tornando-o inadequado como liveness probe.
- PYTHONASYNCIODEBUG=1 estava ativo em producao, degradando event-loop perf.
- Faltava indice composto critical em pncp_supplier_contracts.
- Statement timeout nao estava configurado (ALTER ROLE service_role statement_timeout=15s so foi aplicado durante incidente).

---

## 5. Action Items

Cada item gerou uma **GitHub Issue** com label `post-mortem`.

| # | Acao | Tipo | Responsavel | Prazo | Issue |
|---|------|------|-------------|-------|-------|
| 1 | RES-BE-001: CI gate para detectar .execute() sem _run_with_budget | preventiva | @tjsasakifln | 2026-05-02 | #600 |
| 2 | RES-BE-002b: Converter .execute() em _run_with_budget em 9 rotas | corretiva | @tjsasakifln | 2026-04-29 | #598 |
| 3 | RES-BE-002c: Auditoria completa + top-tier sweep .execute() | corretiva | @tjsasakifln | 2026-04-29 | #599 |
| 4 | RES-BE-013: CI gate para audit env vars Railway | preventiva | @tjsasakifln | 2026-05-02 | #601 |
| 5 | RES-BE-015: Sweep de 15 rotas SEO long-tail + audit gate | corretiva | @tjsasakifln | 2026-05-01 | #602 |
| 6 | RES-BE-015b: _run_with_budget para blog_stats setor/* routes | corretiva | @tjsasakifln | 2026-05-01 | #603 |
| 7 | Adicionar indice composto em pncp_supplier_contracts(is_active, uf, lower(municipio)) | preventiva | @tjsasakifln | 2026-04-29 | #604 |
| 8 | Fix healthcheckPath /health → /health/live | corretiva | @tjsasakifln | 2026-04-27 | #529 |
| 9 | Setar PYTHONASYNCIODEBUG=0 em Railway | corretiva | @tjsasakifln | 2026-04-28 | — |
| 10 | Converter query_datalake para nao-blocking (sb_execute + asyncio.to_thread) | corretiva | @tjsasakifln | 2026-04-30 | #605 |
| 11 | Billing webhook .execute() wrap em _run_with_budget (Stage 2-8 regression) | corretiva | @tjsasakifln | 2026-05-04 | #717 |
| 12 | Processo de post-mortem obrigatorio em ate 48h para SEV1/SEV2 | preventiva | @tjsasakifln | 2026-06-15 | #1878 |

---

## 6. Licoes Aprendidas

1. **Mitigacao parcial e perigosa.** Corrigir apenas o sintoma imediato sem auditar o sistema completo leva a recorrencia em cascata. Apos o primeiro incidente, deveriamos ter auditado TODAS as rotas de SEO em vez de apenas a que quebrou primeiro.

2. **Sync .execute() e um anti-padrao silencioso.** Sem CI gate, novas chamadas sync .execute() entram no codigo sem deteccao. O CI gate de auditoria (RES-BE-001) e agora obrigatorio em todo PR.

3. **Liveness probe nunca deve fazer IO.** /health com probes externos (PNCP, Portal, etc) e inadequado como liveness probe do Railway. /health/live (puramente async, sem IO) e o padrao correto.

4. **Debug mode em producao degrada performance.** PYTHONASYNCIODEBUG=1 em producao adiciona overhead ao event loop. Toda env var de producao deve ser auditada.

5. **Statement timeout e baseline de seguranca de banco.** ALTER ROLE service_role statement_timeout deve ser configurado no setup inicial, nao descoberto durante incidente.

6. **Post-mortem previne recorrencia.** Se o post-mortem tivesse sido feito apos Stage 1, as Stages 2-4 poderiam ter sido evitadas. O processo de post-mortem em 48h e agora obrigatorio.

---

## Referencias

- `docs/operations/post-mortem-template.md` — Template usado para este documento
- `docs/operations/incident-response.md` — Processo de resposta a incidentes
- `docs/operations/alerting-runbook.md` — Runbooks por tipo de alerta
- `docs/runbook/incident-response.md` — Runbook tatico de resposta
- `CLAUDE.md` — Secao Troubleshooting CRIT-080/083/084 + Railway Deploy Rules
- `.claude/rules/critical-impl-notes.md` — Runner History e Time Budget Waterfall
- `docs/architecture/CRIT-080-investigation.md` — Investigacao SIGSEGV
