# SDD Specs — Modules 25-36

> Gerado em 2026-06-17 a partir do codigo fonte
> Cobre 12 modulos: rbac-granular, circuit-breaker-admin, data-retention-admin, sessions-log-level, billing-services, dedup-engine-v2, filter-llm-zero-match, webhook-integrations, cicd-security-ops, api-versioning, property-based-testing, accessibility-wcag-aa

---

## M25 — RBAC Granular

**Proposito:** Controle de acesso baseado em funcoes administrativas granulares, substituindo o booleano binario `is_admin` por 8 roles especificas.

**Entradas:**
- `user_id` (UUID) extraido do JWT por `require_auth`
- `profiles.admin_roles` (jsonb) armazenado na tabela `profiles`

**Saidas:**
- `403 Forbidden` se o usuario nao possui a role requerida
- `user` dict se autorizado

**Dependencias:**
- `backend/auth.py::require_auth` (autenticacao JWT)
- `backend/supabase_client` (consulta profiles.admin_roles)
- `backend/authorization.py` (compatibilidade com `is_admin` legado)

**Definicao de roles:**
- `admin:users` — gestao de usuarios
- `admin:billing` — gestao de faturamento
- `admin:cache` — gestao de cache
- `admin:partners` — gestao de parceiros
- `admin:seo` — gestao de SEO
- `admin:ops` — operacoes (circuit-breakers, log-level, etc.)
- `admin:compliance` — compliance e auditoria
- `admin:super` — super-admin (herda todas as anteriores)

**Mecanismo:** `require_admin_role(role)` retorna um `Depends` que consulta `get_profile_admin_roles(user_id)` e valida se a role esta presente. Se `admin:super` esta presente, todas as roles sao implicitamente concedidas.

**Arquivos:** `backend/rbac_granular.py` (37 LOC)

---

## M26 — Circuit Breaker Admin

**Proposito:** Endpoint de observabilidade para monitorar estado de todos os circuit breakers do sistema em tempo real.

**Entradas:**
- `user` autenticado com role `admin:ops`

**Saidas:**
- `GET /v1/admin/circuit-breakers` -> `{circuit_breakers: {source: {state, failure_count, open_duration, ...}}}`
- Fallback: `{circuit_breakers: {}, error: str}` em caso de falha

**Dependencias:**
- `backend/admin.py::require_admin_ops`
- `backend/clients/pncp/circuit_breaker.py::get_all_circuit_breaker_states`

**Fontes monitoradas:** PNCP, PCP, ComprasGov, BrasilAPI, IBGE

**Arquivos:** `backend/routes/admin_circuit_breakers.py` (37 LOC)

---

## M27 — Data Retention Admin

**Proposito:** Endpoint de observabilidade para inspecionar o ultimo ciclo de purge de dados por tabela.

**Entradas:**
- `user` autenticado com role admin

**Saidas:**
- `GET /v1/admin/data-retention/status` -> `{status, queried_at, tables: [{name, last_purge_at, rows_purged_last, status}], total_rows_purged_last, last_cycle_duration_seconds}`
- Fallback graceful quando Redis indisponivel

**Dependencias:**
- `backend/admin.py::require_admin`
- `backend/redis_pool.py::get_redis_pool`
- `backend/jobs/cron/data_retention.py` (cron que popula Redis com estatisticas de purge)

**Tabelas monitoradas:** `trial_email_log`, `messages`, `ingestion_checkpoints`

**Arquivos:** `backend/routes/admin_data_retention.py` (~80 LOC), `backend/jobs/cron/data_retention.py`

---

## M28 — Sessions Log Level

**Proposito:** Alteracao de nivel de log em runtime sem restart do servidor, com TTL configuravel para auto-reversao.

**Entradas:**
- `POST /v1/admin/log-level` -> `{level: "DEBUG"|"INFO"|"WARNING"|"ERROR", logger: "ingestion"|"*", ttl_seconds: 300}`
- `GET /v1/admin/log-level` -> lista de loggers modificados

**Saidas:**
- Sucesso: `{message, logger, previous_level, current_level, ttl_until}`
- Estado atual: `{modified_loggers: [{logger, original_level, current_level, set_by, set_at, ttl_remaining}]}`

**Mecanismo:**
- Armazenamento in-memory (`_log_level_overrides: dict[str, dict]`)
- Background task (asyncio) verifica expiracao a cada 30s e reverte loggers expirados
- Suporta root logger (`*`) e loggers especificos (ex: `ingestion`)
- Requer role `admin:ops`

**Arquivos:** `backend/routes/admin_log_level.py` (~150 LOC)

---

## M29 — Billing Services

**Proposito:** Gestao completa de assinaturas e faturamento via Stripe, incluindo planos, quotas, webhooks e portal de autoatendimento.

**Entradas:**
- Eventos Stripe (12 webhook types: checkout, subscription, invoice)
- Requisicoes dos usuarios (checkout, portal, status)
- Admin roles para gestao de planos

**Saidas:**
- `GET /v1/plans` — lista de planos disponiveis
- `POST /v1/checkout` — cria Stripe Checkout Session
- `POST /v1/billing-portal` — link para Stripe Customer Portal
- `GET /v1/subscription/status` — status atual
- `POST /webhooks/stripe` — dispatcher com signature validation
- Atualizacao de `profiles.plan_type` apos cada evento

**Componentes:**
- `backend/services/billing.py` — `update_stripe_subscription_billing_period`, `get_next_billing_date`
- `backend/quota/` — `quota_core.py`, `quota_atomic.py`, `plan_enforcement.py`, `plan_auth.py`, `session_tracker.py`
- `backend/webhooks/stripe.py` — dispatcher router (thin)
- `backend/webhooks/handlers/` — checkout, subscription, invoice, api_checkout, founding, stripe_product_price
- `backend/routes/billing.py` — endpoints de faturamento
- `backend/routes/subscriptions.py` — endpoints de subscription

**Planos:** free_trial, smartlic_pro, founding_member, consultoria, consultor_agil (legacy), maquina (legacy), sala_guerra (legacy), master, free (legacy prod)

**Dependencias:** `stripe`, `supabase_client`, `cache.redis_cache`, `auth`, `services/email_service`

**Arquivos:** `backend/services/billing.py`, `backend/quota/*.py`, `backend/webhooks/stripe.py`, `backend/webhooks/handlers/*.py`, `backend/routes/billing.py`

---

## M30 — Dedup Engine v2

**Proposito:** Motor de deduplicacao multi-camada para registros de compras publicas de 3 fontes (PNCP, PCP, ComprasGov), com merge-enrichment entre duplicatas.

**Entradas:**
- `List[UnifiedProcurement]` — registros consolidados das 3 fontes
- `adapters: Dict` — mapping source -> SourceAdapter (para prioridade)
- Feature flags: `DEDUP_FUZZY_ENABLED`, `DEDUP_FUZZY_THRESHOLD`

**Saidas:**
- `List[UnifiedProcurement]` — registros deduplicados com merge-enrichment

**Algoritmo (5 layers em sequencia):**
1. **source_id exact** — mesmo PNCP ID (datalake + live API)
2. **dedup_key exact** — mesmo edital cross-source, vence por prioridade de fonte
3. **Fuzzy Jaccard** — mesmo conteudo, numeros de edital diferentes (toggle via `DEDUP_FUZZY_ENABLED`)
4. **Process-number** — sequenciais adjacentes do mesmo orgao (regex `r"-(\d{4,6})/(\d{4})$"`)
5. **Title-prefix** — duplicatas cross-org

**Merge-enrichment:** Campos `valor_estimado`, `modalidade`, `orgao`, `objeto` do duplicado sao copiados se ausentes no winner.

**Metricas:** `DEDUP_FIELDS_MERGED`, `DEDUP_FUZZY_HITS` (Prometheus counters)

**Stopwords:** Importadas de `filter/stopwords.py` (230 palavras PT-BR + procurement terms)

**Arquivos:** `backend/consolidation/dedup.py` (566 LOC)

---

## M31 — Filter LLM Zero-Match

**Proposito:** Classificacao batch via GPT-4.1-nano para licitacoes com 0% de keyword match, permitindo recuperacao de candidatos que a filtragem keyword-only perderia.

**Entradas:**
- Items com keyword density = 0%
- Contexto do setor (nome, id, termos de busca)
- `search_id` para correlacao

**Saidas:**
- Decisoes YES/NO para cada item no batch
- Items YES reintroduzidos no pipeline como `source: llm_zero_match`

**Algoritmo:**
- Batch de ate 20 itens por chamada LLM
- Prompt: `_build_zero_match_prompt()` em `zero_match.py`
- Parsing: regex `^\d+[\.\):\s]*\s*(YES|NO|SIM|NAO|NÃO)$`
- **Zero-noise rule:** se count mismatch -> `None` -> rejeita TODOS (nao classifica nenhum)
- Cache 2-tier: L1 LRU 5000 + L2 Redis

**Config:**
- Feature flag: `LLM_ZERO_MATCH_ENABLED` (default true)
- Modelo: `gpt-4.1-nano`, temperature=0, max_tokens=1
- Fallback `PENDING_REVIEW` quando `LLM_FALLBACK_PENDING_ENABLED=true`

**Metricas:** `smartlic_filter_decisions_by_setor_total{source="llm_zero_match"}`, `LLM_CALLS`, `ARBITER_CACHE_*`

**Arquivos:** `backend/llm_arbiter/zero_match.py` (289 LOC), `backend/llm_arbiter/classification.py` (648 LOC), `backend/llm_arbiter/prompt_builder.py` (378 LOC)

---

## M32 — Webhook Integrations

**Proposito:** Sistema extensivel de webhooks com validacao de assinatura, idempotencia, timeout e roteamento para handlers especializados.

**Entradas:**
- Requisicoes HTTP POST de fontes externas (Stripe, Resend)
- Signature headers para validacao

**Saidas:**
- `200 OK` processamento bem-sucedido
- `400 Bad Request` signature invalida
- `504 Gateway Timeout` timeout de processamento (>30s)
- Eventos registrados em `stripe_webhook_events` para audit trail

**Componentes:**
- **Dispatcher:** `backend/webhooks/stripe.py` — thin router com signature validation + idempotency
- **Handlers organizados por recurso:**
  - `checkout.py` — checkout.session.completed, async_payment_succeeded/failed, intel_report_payment_failed, digital_product_checkout_completed
  - `subscription.py` — customer.subscription.created/updated/deleted/trial_will_end
  - `invoice.py` — invoice.payment_succeeded/failed/payment_action_required
  - `api_checkout.py` — checkout.session.completed (API subscription)
  - `founding.py` — founding member abandonment (checkout.session.expired)
  - `stripe_product_price.py` — product.price.updated
- **Base:** `_base.py`, `_shared.py` (resolve_user_id)
- **Registry:** `_registry.py`

**Mecanismos:**
- Stripe signature validation via `stripe.Webhook.construct_event`
- Idempotencia via `INSERT ... ON CONFLICT DO NOTHING` em `stripe_webhook_events`
- Timeout: `asyncio.wait_for(handler, timeout=30s)` (SYS-024)
- Stuck recovery: eventos `processing` >5min -> log WARN + retoma
- Cache invalidation: `invalidate_plan_status_cache(user_id)` + `clear_plan_capabilities_cache()` apos cada evento de subscription

**Arquivos:** `backend/webhooks/stripe.py`, `backend/webhooks/handlers/*.py`

---

## M33 — CI/CD Security Ops

**Proposito:** Gates de seguranca automatizados no pipeline CI/CD para prevenir vazamento de secrets, vulnerabilidades e violacoes de conformidade.

**Entradas:**
- Codigo do repositorio (backend, frontend, infra)
- Workflow triggers: PR, push, schedule

**Saidas:**
- Report SARIF (CodeQL, Semgrep)
- Secret scan alerts (Gitleaks)
- Dependency vulnerability reports (pip-audit + npm audit)
- Block/no-block decision por workflow

**Gates implementados:**

| Workflow | Ferramenta | Frequencia | Bloqueia? |
|----------|-----------|------------|-----------|
| `sast.yml` | Semgrep (`p/default`) | PR + weekly | Advisory |
| `codeql.yml` | CodeQL (Python + JS) | PR + weekly | Advisory |
| `secret-scan.yml` | Gitleaks | PR + push main | Bloqueia |
| `dep-scan.yml` | pip-audit + npm audit | PR + weekly | Bloqueia HIGH/CRITICAL |
| `secdef-search-path-guard.yml` | Grep SECURITY DEFINER | PR | Bloqueia |
| `security-tests.yml` | OWASP ZAP | Schedule | Advisory |
| `secret-age-check.yml` | Age-check | PR | Advisory |
| `a11y-gate.yml` | axe-core | PR | Advisory |
| `mutation-testing.yml` | mutmut | Weekly | Non-blocking |

**Arquivos:** `.github/workflows/sast.yml`, `.github/workflows/codeql.yml`, `.github/workflows/secret-scan.yml`, `.github/workflows/dep-scan.yml`, `.github/workflows/security-tests.yml`, `.github/workflows/secdef-search-path-guard.yml`, `.github/workflows/mutation-testing.yml`, `.github/workflows/a11y-gate.yml`, `.github/workflows/secret-age-check.yml`

---

## M34 — API Versioning

**Proposito:** Estrategia de versionamento de API via prefixo URL, garantindo compatibilidade retroativa e convivencia de versoes.

**Entradas:**
- Requisicoes HTTP com prefixo `/v1/`
- Feature flags para rotas experimentais

**Saidas:**
- Rotas registradas com prefixo automatico `/v1`
- Admin routes auto-prefixed `/v1/admin/*`
- Root routes (health, webhooks) sem versionamento

**Mecanismo:**
- 71 router files registrados em `startup/routes.py::register_routes`
- `app.include_router(r, prefix="/v1")` para todos os `_v1_routers`
- Admin routers tem `prefix="/v1/admin"` explicito no APIRouter
- Rotas publicas (observatorio, sitemaps) tambem prefixadas `/v1`
- Health endpoints (`/health/live`, `/health/ready`) e webhooks (`/webhooks/stripe`) sem prefixo

**Excecoes:** Webhook Stripe registrado em `/webhooks/stripe` (nao `/v1/webhooks/stripe`) — configurado no Stripe Dashboard. `CorrelationIDMiddleware` opera antes do roteamento.

**Arquivos:** `backend/startup/routes.py`, `backend/startup/endpoints.py`

---

## M35 — Property-Based Testing

**Proposito:** Testes baseados em propriedades (Hypothesis) para deteccao de edge cases e comportamento inesperado em parsers e componentes criticos.

**Entradas:**
- Estrategias Hypothesis: `st.text(max_size=500)`, operadores, smart quotes, unicode
- Input do modulo sob teste (ex: `parse_search_terms`)

**Saidas:**
- `List[str]` (unico outcome esperado — qualquer excecao e considerada bug)
- Relatorio de mutantes sobreviventes (mutmut, semanal)

**Propriedades testadas:**
1. Texto arbitrario nunca causa excecao nao-capturada
2. Input vazio / whitespace-only -> lista vazia
3. Input com virgulas (leading/trailing, sequenciais)
4. Smart quotes (U+201C/201D/2018/2019) — sanitizados antes do parsing
5. Unicode combining marks / caracteres extremos
6. Input longo > MAX_INPUT_LENGTH=256 -> truncamento

**Mutacao (STORY-6.6):**
- `mutation-testing.yml` semanal (domingo 6am UTC)
- Modulos: filter/, llm_arbiter/, consolidation/, quota/
- Non-blocking (`|| true`) — relatorio como artifact

**Arquivos:** `backend/tests/fuzz/test_term_parser_fuzz.py`, `.github/workflows/mutation-testing.yml`, `backend/tests/fuzz/`

---

## M36 — Accessibility WCAG AA

**Proposito:** Testes automatizados de acessibilidade para conformidade WCAG 2.2 AA, cobrindo componentes criticos da interface.

**Entradas:**
- Componentes React renderizados (modal, drawer, icon buttons, search results)
- Paginas do frontend (login, buscar, pipeline, admin)

**Saidas:**
- Testes pass/fail por criterio WCAG
- Lighthouse report (CI)
- axe-core audit results

**Cobertura de criterios:**

| Criterio WCAG | Cobertura | Arquivo de teste |
|--------------|-----------|-----------------|
| 1.1.1 Non-text Content | SVG alt text, aria-labels | `accessibility.test.tsx` |
| 1.4.3 Contrast (Minimum) | CSS variable contrast docs | `accessibility.test.tsx` |
| 1.4.11 Non-text Contrast | Decorative vs meaningful | `accessibility.test.tsx` |
| 2.1.1 Keyboard | Focus trapping modals | `debt-004-accessibility-wcag.test.tsx` |
| 2.4.3 Focus Order | Navigation order | `debt-004-accessibility-wcag.test.tsx` |
| 2.4.7 Focus Visible | Visible focus indicators | `debt-004-accessibility-wcag.test.tsx` |
| 4.1.2 Name, Role, Value | Icon button aria-labels | `debt-004-accessibility-wcag.test.tsx` |
| 4.1.3 Status Messages | aria-live search results | `debt-004-accessibility-wcag.test.tsx` |

**CI Gate:** `.github/workflows/a11y-gate.yml` — Lighthouse + axe-core em PRs

**Arquivos:** `frontend/__tests__/accessibility.test.tsx`, `frontend/__tests__/debt-004-accessibility-wcag.test.tsx`, `frontend/__tests__/landing-accessibility.test.tsx`, `frontend/__tests__/viability-badge-a11y.test.tsx`, `frontend/e2e-tests/a11y/`, `frontend/e2e-tests/accessibility-audit.spec.ts`, `.github/workflows/a11y-gate.yml`
