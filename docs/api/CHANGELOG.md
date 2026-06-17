# API Changelog — SmartLic

**Repository:** [github.com/tjsasakifln/SmartLic](https://github.com/tjsasakifln/SmartLic)
**Format:** [Keep a Changelog](https://keepachangelog.com/)
**Versioning:** Semantic versioning via URI prefix (`/v{N}/*`)

## [v1] — Current (2026-06-16)

### Added

- Initial API version. All endpoints live under `/v1/*` prefix.
- Middleware adds `X-API-Version: v1` and `X-API-Deprecated: false` to all responses.
- API versioning policy documented in `docs/architecture/api-versioning.md`.

### Endpoints (stable)

#### Search
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/search` | Execute a new search (async, returns search_id) |
| GET | `/v1/search/{id}/status` | Poll search status |
| GET | `/v1/search/{id}/timeline` | Search execution timeline |
| GET | `/v1/search/{id}/results` | Get search results |
| GET | `/v1/search/{id}/zero-match` | Zero-match classification results |
| POST | `/v1/search/{id}/regenerate-excel` | Regenerate Excel export |
| POST | `/v1/search/{id}/retry` | Retry a failed search |
| POST | `/v1/search/{id}/cancel` | Cancel an in-progress search |
| POST | `/buscar` | Legacy search endpoint (deprecated route) |
| GET | `/buscar-progress/{id}` | SSE progress stream (deprecated route) |

#### Pipeline (Kanban)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/pipeline` | List pipeline items |
| POST | `/v1/pipeline` | Create pipeline item |
| PATCH | `/v1/pipeline` | Update pipeline item (optimistic locking) |
| DELETE | `/v1/pipeline` | Delete pipeline item |
| GET | `/v1/pipeline/alerts` | Pipeline alerts |

#### Billing / Plans
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/plans` | List available plans |
| POST | `/v1/checkout` | Create checkout session |
| POST | `/v1/billing-portal` | Billing portal session |
| GET | `/v1/subscription/status` | Current subscription status |
| POST | `/v1/billing/setup-intent` | Setup intent for payment method |
| POST | `/v1/api/subscriptions/cancel` | Cancel subscription |
| POST | `/v1/api/subscriptions/update-billing-period` | Update billing period |
| POST | `/v1/api/subscriptions/cancel-feedback` | Cancel feedback |
| POST | `/v1/founding/checkout` | Founding member checkout |
| POST | `/v1/conta/cancelar-trial` | Cancel trial |
| POST | `/v1/trial/extend` | Extend trial period |

#### User / Account
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/me` | Current user profile |
| POST | `/v1/change-password` | Change password |
| GET | `/v1/trial-status` | Trial status |
| GET | `/v1/profile/context` | Profile context |
| GET | `/v1/profile/completeness` | Profile completion |
| GET | `/v1/profile/alert-preferences` | Alert preferences |
| GET | `/v1/me/export` | Export user data (LGPD) |
| POST | `/v1/trial/exit-survey` | Trial exit survey |
| POST | `/v1/auth/signup` | Sign up |
| POST | `/v1/auth/check-email` | Check email availability |
| POST | `/v1/auth/validate-signup-email` | Validate signup email |
| POST | `/v1/auth/resend-confirmation` | Resend confirmation |
| GET | `/v1/auth/status` | Auth status |
| POST | `/v1/auth/mfa/recovery` | MFA recovery |
| POST | `/v1/auth/oauth/google` | Google OAuth |

#### Analytics / Dashboard
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/analytics/summary` | Dashboard summary |
| GET | `/v1/analytics/searches-over-time` | Search volume over time |
| GET | `/v1/analytics/top-dimensions` | Top dimensions |
| GET | `/v1/analytics/trial-value` | Trial value metrics |
| GET | `/v1/analytics/new-opportunities` | New opportunities |
| POST | `/v1/analytics/track-cta` | Track CTA |

#### Alerts
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/alerts` | List user alerts |
| POST | `/v1/alerts` | Create alert |
| DELETE | `/v1/alerts/{id}` | Delete alert |

#### Messages (Support)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/messages` | List conversations |
| POST | `/v1/messages` | Create conversation |
| GET | `/v1/messages/{id}/replies` | Get replies |
| POST | `/v1/messages/{id}/replies` | Send reply |
| PATCH | `/v1/messages/{id}/status` | Update conversation status |
| GET | `/v1/messages/unread-count` | Unread count |

#### Feedback
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/feedback` | Submit feedback (rate limited) |
| DELETE | `/v1/feedback/{id}` | Delete feedback (LGPD) |

#### Onboarding
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/first-analysis` | Auto-dispatch first search |
| POST | `/v1/onboarding/tour-event` | Tour telemetry event |

#### Sessions
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/sessions` | List user sessions |
| DELETE | `/v1/sessions/{id}` | Revoke session |

#### Organizations
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/organizations` | List organizations |
| POST | `/v1/organizations` | Create organization |

#### Partners / Referral
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/partners` | List partners |
| POST | `/v1/referral` | Create referral |

#### Share
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/share/{id}` | Get shared item |

#### Health / Status
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health/live` | Liveness probe |
| GET | `/health/ready` | Readiness probe |
| GET | `/health` | General health |
| GET | `/v1/health` | General health (versioned) |
| GET | `/v1/health/cache` | Cache health |
| GET | `/v1/health/sources` | Data source health |
| GET | `/v1/health/status` | Status incidents |
| GET | `/v1/health/uptime-history` | Uptime history |
| GET | `/sources/health` | Sources health (deprecated route) |

#### SEO Programmatic (Public, No Auth)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/observatorio/{slug}` | Observatory page |
| GET | `/v1/observatorio/raio-x-setor/{id}` | Sector deep-dive |
| GET | `/v1/observatorio/raio-x-municipio/{id}` | Municipality deep-dive |
| GET | `/v1/observatorio/raio-x-orgao/{id}` | Agency deep-dive |
| GET | `/v1/observatorio/raio-x-alerta/{id}` | Alert deep-dive |
| GET | `/v1/setores` | List all sectors |
| GET | `/v1/empresa/{cnpj}` | Company profile |
| GET | `/v1/orgao/{slug}` | Agency profile |
| GET | `/v1/municipios/{slug}` | Municipality profile |
| GET | `/v1/contratos/{setor}/{uf}` | Contracts by sector/UF |
| GET | `/v1/contratos/orgao/{cnpj}` | Contracts by agency |
| GET | `/v1/dados-publicos` | Public data |
| GET | `/v1/alertas-publicos/{setor}/{uf}` | Public alerts |
| GET | `/v1/itens/{id}` | Item details |
| GET | `/v1/compliance/{cnpj}` | Compliance report |
| GET | `/v1/indice-municipal/{municipio-uf}` | Municipal index |
| GET | `/v1/blog/stats` | Blog stats |
| GET | `/v1/stats/public` | Public stats |
| GET | `/v1/calculadora` | Bid calculator |
| GET | `/v1/comparador` | Bid comparison |
| GET | `/v1/lead-capture` | Lead capture form |
| GET | `/v1/lead-magnet` | Lead magnet download |

#### Sitemaps
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/sitemap/cnpjs` | CNPJ sitemap |
| GET | `/v1/sitemap/orgaos` | Agencies sitemap |
| GET | `/v1/sitemap/licitacoes` | Bids sitemap |
| GET | `/v1/sitemap/licitacoes-do-dia` | Daily bids sitemap |

#### Reports / Exports
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/reports` | List reports |
| POST | `/v1/reports` | Generate report |
| GET | `/v1/relatorio/{id}` | Get report |
| POST | `/v1/export/edital` | Export bid to PDF |
| GET | `/v1/export/sheets` | Export to Google Sheets |
| GET | `/v1/daily-digest` | Daily digest |
| GET | `/v1/weekly-digest` | Weekly digest |

#### Trial Emails / Notifications
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/trial-emails/webhook` | Trial email webhook |
| GET | `/v1/notifications` | List notifications |
| PATCH | `/v1/notifications` | Mark read |
| GET | `/v1/emails/unsubscribe` | Email unsubscribe |

#### Admin
| Method | Path | Description |
|--------|------|-------------|
| GET/POST/DELETE | `/v1/admin/*` | Admin CRUD operations |
| GET | `/v1/admin/trace` | Trace requests |
| GET | `/v1/admin/cron-status` | Cron job status |
| GET | `/v1/admin/cnae-mapping` | CNAE mapping |
| GET | `/v1/admin/llm-cost` | LLM cost tracking |
| GET | `/v1/admin/calibration` | LLM calibration |
| POST | `/v1/admin/billing-sync` | Billing sync |
| POST | `/v1/admin/founding` | Founding admin |
| GET | `/v1/admin/metrics` | Admin metrics |
| GET | `/v1/admin/sessions` | All sessions |
| GET | `/v1/admin/slo` | SLO metrics |
| GET | `/v1/admin/seo` | SEO admin |
| GET | `/v1/admin/feature-flags` | Feature flags |
| GET | `/v1/admin/digest-metrics` | Digest metrics |
| POST | `/v1/admin/subscriptions/*` | Subscription admin |
| GET | `/v1/admin/log-level` | Runtime log level |
| GET | `/v1/admin/synthetic/last-run` | Synthetic monitor |
| POST | `/v1/admin/test-alert` | Test alert routing |
| GET | `/v1/admin/dlq` | Dead letter queue |

#### Webhooks
| Method | Path | Description |
|--------|------|-------------|
| POST | `/webhooks/stripe` | Stripe webhooks (root only) |
| POST | `/v1/webhooks/stripe` | Stripe webhooks (versioned) |

#### Surveys
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/survey` | Submit survey response |

#### Feature Flags
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/feature-flags` | List feature flags (public) |
| POST | `/v1/feature-flags` | Toggle feature flag (admin) |

#### DataLake API
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/datalake` | DataLake query |
| GET | `/v1/api-keys` | API key management |
| GET | `/v1/api/search` | Public API search |

#### Intelligence Reports
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/intel/reports` | List reports |
| POST | `/v1/intel/tasting` | Intel tasting |
| GET | `/v1/intel/vitrine` | Intel showcase |
| GET | `/v1/pseo/data` | PSEO data |
| GET | `/v1/pseo/intel-feed` | PSEO intel feed |
| GET | `/v1/seo-coverage-manifest` | SEO coverage |
| GET | `/v1/intel-tasting` | Quick intel tasting |
| GET | `/v1/predint` | Predictive intelligence |
| GET | `/v1/monthly-report` | Monthly report |
| GET | `/v1/widget/compint` | Competitive intel widget |
| GET | `/v1/competitive-intel` | Competitive intelligence |
| GET | `/v1/score` | Opportunity scoring |
| GET | `/v1/consultoria` | Consulting services |
| GET | `/v1/subcontract` | Subcontracting |
| GET | `/v1/subcontract-intel` | Subcontract intel |

#### Products / Network
| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/products` | Product catalog |
| GET | `/v1/seasonal-calendar` | Seasonal calendar |
| GET | `/v1/network-events` | Network events |
| POST | `/v1/segment` | Segment tracking |
| GET | `/v1/segment` | Get segment data |

#### Data Deletion (LGPD)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/data-deletion` | Request data deletion |
| GET | `/v1/data-deletion/status` | Deletion status |

### Deprecation Notices

- Legacy routes (without `/v1/` prefix) return `Deprecation: true` header.
- Legacy routes sunset date: 2026-06-01.
- All legacy routes have a `Link: </v1{path}>; rel="successor-version"` header.

### Versioning History

| Version | Release Date | Status |
|---------|-------------|--------|
| v1 | 2026-06-16 | Active |

---

## Template — Future Version Entries

When adding a new version, copy below and fill:

```markdown
## [v2] — YYYY-MM-DD

### Added
- New endpoints...

### Changed
- Breaking changes (list each with before/after)...

### Deprecated
- v1 endpoints entering deprecation window...

### Removed
- Endpoints removed from v1 for v2...

### Migration Guide: v1 → v2
- Step-by-step migration instructions...
- `Scripts/check-api-breaking.sh` output for reference...
```

---

*Policy document: `docs/architecture/api-versioning.md`*
*Breaking change detection: `scripts/check-api-breaking.sh`*
*CI gate: `.github/workflows/api-schema-check.yml`*
