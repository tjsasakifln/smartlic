# Router Registration Design

> Documentacao da ordem de registro dos routers em `backend/startup/routes.py`.
> GAP-017: Verificacao de ordem e duplicidade de paths.

## Ordem de Registro

A funcao `register_routes()` registra routers em tres blocos:

1. **health_core_router** — prefixo raiz `/` (health checks para Railway probes)
2. **74 routers** em `_v1_routers` — prefixo `/v1`
3. **Routers com prefixo proprio** — registrados sem prefixo, cada um define seu proprio prefixo internamente (`APIRouter(prefix="/...")`)

### Nota sobre resolucao de rotas

Ordem nao afeta resolucao de rotas no FastAPI (diferente de Express). No FastAPI,
cada rota e registrada com seu metodo HTTP + path completo; o roteador usa um
radix tree (trie) para matching, nao busca linear. A ordem no arquivo e apenas
convencao de legibilidade.

### Verificacao de duplicidade

Nao ha paths duplicados entre routers. Cada router define prefixos distintos,
e nenhum path completo (method + path) aparece em mais de um router. Verificado
contra conflitos de prefixo e sobreposicao de paths.

---

## Auth & Identity (prefixo `/v1`)

| # | Router | Fonte | Prefixo |
|---|--------|-------|---------|
| 17 | `auth_email_router` | `routes/auth_email.py` | `/v1/auth` |
| 18 | `auth_signup_router` | `routes/auth_signup.py` | `/v1/auth` |
| 6 | `oauth_router` | `routes/auth_oauth.py` | `/v1/auth/oauth` |
| 21 | `auth_check_router` | `routes/auth_check.py` | `/v1/auth` |
| 25 | `mfa_router` | `routes/mfa.py` | `/v1/mfa` |
| 10 | `user_router` | `routes/user.py` | `/v1/user` |
| 26 | `org_router` | `routes/organizations.py` | `/v1/organizations` |

## Search & Pipeline (prefixo `/v1`)

| # | Router | Fonte | Prefixo |
|---|--------|-------|---------|
| 9 | `search_router` | `routes/search.py` | `/v1/search` |
| 15 | `pipeline_router` | `routes/pipeline.py` | `/v1/pipeline` |
| 22 | `bid_analysis_router` | `routes/bid_analysis.py` | `/v1/bid-analysis` |
| 12 | `sessions_router` | `routes/sessions.py` | `/v1/sessions` |

## Billing & Checkout (prefixo `/v1`)

| # | Router | Fonte | Prefixo |
|---|--------|-------|---------|
| 2 | `subscriptions_router` | `routes/subscriptions.py` | `/v1/subscriptions` |
| 11 | `billing_router` | `routes/billing.py` | `/v1/billing` |
| 13 | `plans_router` | `routes/plans.py` | `/v1/plans` |
| 3 | `upgrade_to_lifetime_router` | `routes/upgrade_to_lifetime.py` | `/v1/upgrade-to-lifetime` |
| 62 | `founding_router` | `routes/founding.py` | `/v1/founding` |
| 63 | `conta_router` | `routes/conta.py` | `/v1/conta` |
| 39 | `trial_extension_router` | `routes/trial_extension.py` | `/v1/trial` |
| 4 | `features_router` | `routes/features.py` | `/v1/features` |
| 68 | `products_router` | `routes/products.py` | `/v1/products` |

## Export & Reports (prefixo `/v1`)

| # | Router | Fonte | Prefixo |
|---|--------|-------|---------|
| 8 | `export_sheets_router` | `routes/export_sheets.py` | `/v1/export` |
| 61 | `edital_export_router` | `routes/export.py` | `/v1/edital-export` |
| 29 | `reports_router` | `routes/reports.py` | `/v1/reports` |
| 38 | `relatorio_router` | `routes/relatorio.py` | `/v1/relatorio` |
| 65 | `intel_reports_router` | `routes/intel_reports.py` | `/v1/intel-reports` |

## Admin (prefixo `/v1` + prefixo proprio)

### Em `_v1_routers` (prefixo `/v1`)

| # | Router | Fonte |
|---|--------|-------|
| 1 | `admin_router` | `admin.py` |
| 47 | `seo_admin_router` | `routes/seo_admin.py` |
| 32 | `feature_flags_router` | `routes/feature_flags.py` |
| 33 | `feature_flags_public_router` | `routes/feature_flags.py` (public_router) |
| 73 | `segment_router` | `routes/segment.py` |

### Prefixedos proprios (fora de `_v1_routers`, dentro de `register_routes()`)

| Router | Fonte | Prefixo |
|--------|-------|---------|
| `admin_trace_router` | `routes/admin_trace.py` | `/v1/admin/trace` |
| `admin_cron_router` | `routes/admin_cron.py` | `/v1/admin/cron` |
| `admin_cnae_mapping_router` | `routes/admin_cnae_mapping.py` | `/v1/admin/cnae` |
| `admin_llm_cost_router` | `routes/admin_llm_cost.py` | `/v1/admin/llm-cost` |
| `admin_calibration_router` | `routes/admin_calibration.py` | `/v1/admin/calibration` |
| `admin_billing_sync_router` | `routes/admin_billing_sync.py` | `/v1/admin/billing-sync` |
| `admin_founding_router` | `routes/admin_founding.py` | `/v1/admin/founding` |
| `admin_metrics_router` | `routes/admin_metrics.py` | `/v1/admin/metrics` |
| `slo_router` | `routes/slo.py` | `/v1/admin/slo` |
| `admin_digest_metrics_router` | `routes/admin_digest_metrics.py` | `/v1/admin/digest-metrics` |

## SEO / Public (prefixo `/v1`, sem auth)

| # | Router | Fonte |
|---|--------|-------|
| 56 | `observatorio_router` | `routes/observatorio.py` |
| 35 | `empresa_publica_router` | `routes/empresa_publica.py` |
| 50 | `orgao_publico_router` | `routes/orgao_publico.py` |
| 51 | `contratos_publicos_router` | `routes/contratos_publicos.py` |
| 42 | `dados_publicos_router` | `routes/dados_publicos.py` |
| 53 | `municipios_publicos_router` | `routes/municipios_publicos.py` |
| 55 | `itens_publicos_router` | `routes/itens_publicos.py` |
| 54 | `compliance_publicos_router` | `routes/compliance_publicos.py` |
| 43 | `alertas_publicos_router` | `routes/alertas_publicos.py` |
| 28 | `sectors_public_router` | `routes/sectors_public.py` |
| 41 | `stats_public_router` | `routes/stats_public.py` |
| 34 | `calculadora_router` | `routes/calculadora.py` |
| 46 | `comparador_router` | `routes/comparador.py` |
| 59 | `indice_municipal_router` | `routes/indice_municipal.py` |
| 30 | `blog_stats_router` | `routes/blog_stats.py` |
| 52 | `daily_digest_router` | `routes/daily_digest.py` |
| 40 | `weekly_digest_router` | `routes/weekly_digest.py` |
| 44 | `lead_capture_router` | `routes/lead_capture.py` |
| 45 | `lead_magnet_router` | `routes/lead_magnet.py` |
| 66 | `pseo_data_router` | `routes/pseo_data.py` |
| 67 | `seo_coverage_manifest_router` | `routes/seo_coverage_manifest.py` |
| 71 | `seasonal_calendar_router` | `routes/seasonal_calendar.py` |
| 72 | `network_events_router` | `routes/network_events.py` |
| 48 | `sitemap_cnpjs_router` | `routes/sitemap_cnpjs.py` |
| 49 | `sitemap_orgaos_router` | `routes/sitemap_orgaos.py` |
| 57 | `sitemap_licitacoes_router` | `routes/sitemap_licitacoes.py` |
| 58 | `sitemap_licitacoes_do_dia_router` | `routes/sitemap_licitacoes_do_dia.py` |

## Infrastructure (prefixo `/v1`)

| # | Router | Fonte | Prefixo |
|---|--------|-------|---------|
| 19 | `cache_health_router` | `routes/health.py` | `/v1/health` |
| 31 | `metrics_api_router` | `routes/metrics_api.py` | `/v1/metrics` |

## Email & Notifications (prefixo `/v1`)

| # | Router | Fonte |
|---|--------|-------|
| 14 | `emails_router` | `routes/emails.py` |
| 24 | `trial_emails_router` | `routes/trial_emails.py` |
| 60 | `notifications_router` | `routes/notifications.py` |
| 23 | `alerts_router` | `routes/alerts.py` |

## Other (prefixo `/v1`)

| # | Router | Fonte |
|---|--------|-------|
| 5 | `messages_router` | `routes/messages.py` |
| 7 | `analytics_router` | `routes/analytics.py` |
| 16 | `onboarding_router` | `routes/onboarding.py` |
| 20 | `feedback_router` | `routes/feedback.py` |
| 36 | `share_router` | `routes/share.py` |
| 37 | `referral_router` | `routes/referral.py` |
| 27 | `partners_router` | `routes/partners.py` |
| 64 | `survey_router` | `routes/survey.py` |
| 69 | `datalake_api_router` | `routes/datalake_api.py` |
| 70 | `api_keys_router` | `routes/api_keys.py` |
| 74 | `api_search_router` | `routes/api_search.py` |

## Routers com Prefixo Proprio (fora de `/v1/`)

Estes routers definem seu proprio prefixo via `APIRouter(prefix="/...")` e sao registrados em `register_routes()` sem prefixo adicional.

| Router | Fonte | Prefixo | Proposito |
|--------|-------|---------|-----------|
| `health_core_router` | `routes/health_core.py` | raiz `/health/*`, `/sources/*` | Railway probes (liveness, readiness) |
| `stripe_webhook_router` | `webhooks/stripe.py` | raiz `/webhooks/stripe` | Stripe webhook (DEBT-324) |
| `founders_router` | `routes/founders.py` | `/api/founders` | Founders availability (Issue #1002) |
| `founders_hall_router` | `routes/founders_hall.py` | `/api/founders/hall` | Hall of Founders (Issue #1008) |
| `checkout_router` | `routes/checkout.py` | `/api/checkout` | Checkout (CONV-005b-2) |
| `email_tracking_router` | `routes/email_tracking.py` | `/api/email` | Email tracking (Issue #1421) |

## Lista Completa — Ordem em `_v1_routers`

A ordem exata dos 74 routers na lista `_v1_routers` (linhas 100-153 de `startup/routes.py`):

```
 1. admin_router
 2. subscriptions_router
 3. upgrade_to_lifetime_router
 4. features_router
 5. messages_router
 6. analytics_router
 7. oauth_router
 8. export_sheets_router
 9. search_router
10. user_router
11. billing_router
12. sessions_router
13. plans_router
14. emails_router
15. pipeline_router
16. onboarding_router
17. auth_email_router
18. auth_signup_router
19. cache_health_router
20. feedback_router
21. auth_check_router
22. bid_analysis_router
23. alerts_router
24. trial_emails_router
25. mfa_router
26. org_router
27. partners_router
28. sectors_public_router
29. reports_router
30. blog_stats_router
31. metrics_api_router
32. feature_flags_router
33. feature_flags_public_router
34. calculadora_router
35. empresa_publica_router
36. share_router
37. referral_router
38. relatorio_router
39. trial_extension_router
40. weekly_digest_router
41. stats_public_router
42. dados_publicos_router
43. alertas_publicos_router
44. lead_capture_router
45. lead_magnet_router
46. comparador_router
47. seo_admin_router
48. sitemap_cnpjs_router
49. sitemap_orgaos_router
50. orgao_publico_router
51. contratos_publicos_router
52. daily_digest_router
53. municipios_publicos_router
54. compliance_publicos_router
55. itens_publicos_router
56. observatorio_router
57. sitemap_licitacoes_router
58. sitemap_licitacoes_do_dia_router
59. indice_municipal_router
60. notifications_router
61. edital_export_router
62. founding_router
63. conta_router
64. survey_router
65. intel_reports_router
66. pseo_data_router
67. seo_coverage_manifest_router
68. products_router
69. datalake_api_router
70. api_keys_router
71. seasonal_calendar_router
72. network_events_router
73. segment_router
74. api_search_router
```

## Lista Completa — Ordem em `register_routes()` (self-prefixed)

A ordem exata de registro dos routers com prefixo proprio em `register_routes()`:

```
 1. health_core_router          (raiz)
 2. admin_trace_router          (self-prefixed)
 3. admin_cron_router           (self-prefixed)
 4. admin_cnae_mapping_router   (self-prefixed)
 5. admin_llm_cost_router       (self-prefixed)
 6. admin_calibration_router    (self-prefixed)
 7. admin_billing_sync_router   (self-prefixed)
 8. admin_founding_router       (self-prefixed)
 9. admin_metrics_router        (self-prefixed)
10. slo_router                  (self-prefixed)
11. founders_router             (/api/founders)
12. founders_hall_router        (/api/founders/hall)
13. checkout_router             (/api/checkout)
14. email_tracking_router       (/api/email)
15. admin_digest_metrics_router (self-prefixed)
16. stripe_webhook_router       (raiz /webhooks/stripe)
```

## Total

- **74 routers** registrados com prefixo `/v1` (via `_v1_routers`)
- **16 routers** com prefixo proprio (fora de `/v1/`)
- **Total: 90 importacoes de router** (alguns compartilham o mesmo arquivo fonte, e.g., `feature_flags.py` exporta ambos `router` + `public_router`)
