# Inventario do Projeto — SmartLic

**Ultima atualizacao:** 2026-06-17

Estrutura real de diretorios e arquivos do projeto.

---

## Backend (FastAPI 0.137 / Python 3.12)

```
backend/
├── main.py                     # FastAPI app entrypoint (<30 LOC — SYS-020)
├── config.py                   # Env vars, feature flags, constants
├── feature_flags.py            # Runtime feature flag helpers
│
├── # --- Schemas (Pydantic v2, 88 classes) ---
├── schemas/                    # Package: common, search, user, billing, admin, pipeline
│
├── # --- Startup / Bootstrap ---
├── startup/                    # app_factory, routes, lifespan, middleware_setup
│   └── routes.py               # Registers 65 routers, 187 endpoints
│
├── # --- Search Pipeline (7-stage state machine) ---
├── search_pipeline.py          # Orchestrator: multi-source search + consolidation
├── search_state_manager.py     # State machine workflow
├── search_context.py           # SearchContext dataclass
├── search_cache.py             # Two-level cache (InMemory + Supabase), SWR
├── pipeline/                   # Budget, cache_manager, helpers, tracing, worker, stages/
├── consolidation/              # Source aggregation, dedup (5-layer), timeout
│   └── dedup/                  # Dedup strategy implementations
│
├── # --- Cache (3-layer, passive) ---
├── cache/                      # Manager, cascade, SWR, ops, admin, enums
├── redis_client.py             # Redis client
├── redis_pool.py               # Connection pool + InMemoryCache fallback
├── cache_module.py             # Generic cache utilities
│
├── # --- Filtering & Classification ---
├── filter/                     # Package: pipeline, keywords, density, stats, stages/
├── llm_arbiter/                # Package: classification, zero_match, async_runtime,
│   └── strategies/             #   batch_api, prompt_builder
├── llm.py                      # GPT-4.1-nano executive summaries
├── relevance.py                # Relevance scoring
├── viability.py                # 4-factor viability assessment
├── sectors.py                  # Sector definitions
├── synonyms.py                 # Keyword synonym expansion
├── status_inference.py         # Bid status inference from dates
├── sectors_data.yaml           # 20 sector definitions with keywords
│
├── # --- Auth & Authorization ---
├── auth.py                     # JWT 3-strategy auth (JWKS ES256 > PEM > HS256)
├── authorization.py            # Role-based access (admin/master)
├── oauth.py                    # Google OAuth (Sheets + Login)
│
├── # --- Billing / Quota / Plans ---
├── billing/                    # Billing service package
├── quota/                      # quota_core, quota_atomic, plan_enforcement
├── services/billing/           # Billing service layer
├── stripe/                     # Stripe integration helpers
│
├── # --- Webhooks ---
├── webhooks/                   # Webhook receivers
│   └── handlers/               # checkout, subscription, invoice, founding
│
├── # --- Jobs / Cron ---
├── jobs/
│   ├── queue/                  # ARQ worker: config, jobs, search, pool, definitions
│   └── cron/                   # Cron jobs: canary, billing, notifications, scheduler
├── job_queue.py                # ARQ job queue facade
├── cron_jobs.py                # Legacy cron facade
├── cron/                       # Legacy cron (cache, billing, health, notifications, loop)
│
├── # --- Routes (71 router files, 65 registered, 187 endpoints) ---
├── routes/
│   ├── search/                 # Subpackage: search endpoints + SSE
│   ├── admin_*.py              # admin, admin_trace, admin_cron, admin_llm_cost
│   ├── *publicos.py            # 18 SEO programmatic routers
│   ├── sitemap_*.py            # 5 sitemap routers
│   ├── analytics.py, billing.py, pipeline.py, messages.py
│   ├── feedback.py, user.py, health.py, health_core.py
│   ├── auth_email.py, auth_oauth.py, mfa.py
│   ├── onboarding.py, plans.py, subscriptions.py
│   ├── observatorio.py, blog_stats.py
│   ├── calculadora.py, comparador.py
│   ├── founding.py, conta.py, trial_extension.py
│   └── feature_flags.py, slo.py, share.py
│
├── # --- Ingestion / DataLake ---
├── ingestion/                  # config, scheduler, crawler, transformer, loader,
│                               #   checkpoint, enricher
├── datalake_query.py           # DataLake query RPC
│
├── # --- Output / Exports ---
├── excel.py                    # Excel export (openpyxl)
├── pdf_generator_edital.py     # PDF generation (ReportLab)
├── google_sheets.py            # Google Sheets export
├── report_generator.py         # Report orchestration
├── digest_sender.py            # Email digest sender
│
├── # --- Email ---
├── email_service.py            # Resend transactional email
├── templates/emails/           # 15 email templates (base, trial, billing, dunning)
│
├── # --- Lead Prospecting ---
├── lead_prospecting.py         # Lead discovery engine
├── lead_scorer.py              # Lead scoring model
├── lead_deduplicator.py        # Lead deduplication
├── contact_searcher.py         # Contact info lookup
├── schemas_lead_prospecting.py # Lead schemas
├── bid_analyzer.py             # Bid analysis engine
│
├── # --- ML / Data Science ---
├── ml/                         # ML models (SCORE-001 win probability)
│
├── # --- Monitoring & Observability ---
├── metrics.py                  # Prometheus metrics
├── telemetry.py                # OpenTelemetry tracing
├── audit.py                    # Audit logging
├── log_sanitizer.py            # PII removal from logs
├── analytics_events.py         # Mixpanel event tracking
├── health.py                   # Health check logic
├── progress.py                 # SSE progress (asyncio.Queue)
│
├── # --- Rate Limiting & Middleware ---
├── middleware.py                # CORS, rate limiting, error handling
├── rate_limiter.py             # Redis token bucket
├── api_key_rate_limit.py       # API key rate limiting
├── bulkhead.py                 # Bulkhead isolation
├── bot_detection.py            # Bot detection
├── command_feature_gate.py     # Feature gate commands
├── business_hours.py           # Business hours helpers
│
├── # --- Clients ---
├── clients/                    # External API clients
│   └── pncp/                   # PNCP client package
├── pncp_client.py              # PNCP legacy client
├── pncp_client_resilient.py    # Enhanced PNCP client with degradation
├── pncp_resilience.py          # Circuit breaker + degradation state
├── pncp_homologados_client.py  # PNCP homologated items
├── receita_federal_client.py   # Receita Federal CNPJ lookup
│
├── # --- Utilities ---
├── utils/                      # cnae_mapping, date_parser, error_reporting, ordenacao
├── exceptions.py               # Custom exception classes
├── error_response.py           # Standardized error responses
├── item_inspector.py           # Bid item inspection
├── message_generator.py        # Message templates
├── feedback_analyzer.py        # Bi-gram analysis from user feedback
├── feedback_affinity.py        # Feedback affinity analysis
├── llm_budget.py               # LLM budget tracking
├── degradation.py              # Degradation state management
├── storage.py                  # File storage abstraction
├── database.py                 # Supabase connection helpers
├── supabase_client.py          # Supabase client singleton (CB + sb_execute)
│
├── # --- Unified Schemas (multi-source) ---
├── unified_schemas/            # Unified schemas for multi-source consolidation
├── source_config/              # Source configurations
│
├── # --- Contract Tests ---
├── contracts/schemas/          # JSON schema files for canary + contract tests
│
├── # --- Config & Scripts ---
├── config/                     # Config packages (pncp, etc.)
├── models/                     # Domain models (search_state, etc.)
├── data/                       # Static data files
├── examples/                   # Example scripts
├── monitoring/                 # Monitoring helpers
├── scripts/                    # Utility scripts
├── docs/                       # Audits and doc artifacts
├── start.sh                    # Launcher (PROCESS_TYPE=web|worker)
├── gunicorn_conf.py            # Gunicorn config (not active — RUNNER=uvicorn)
├── requirements.txt            # Python dependencies (pinned)
├── pyproject.toml              # Pytest + coverage config
├── Procfile                    # Railway process definition
├── seed_users.py               # Database seeding
│
└── tests/                      # ~5131+ tests
    ├── test_*.py               # Unit and integration tests
    ├── contract/               # Contract tests
    ├── contracts/              # Additional contract tests
    ├── fixtures/               # Test fixtures
    ├── fuzz/                   # Fuzz testing
    ├── helpers/                # Test helpers
    ├── integration/            # Integration tests
    ├── load/                   # Load/performance tests
    ├── property/               # Property-based tests
    ├── recovery/               # Recovery tests
    ├── resilience/             # Resilience tests
    ├── scripts/                # Test scripts
    ├── security/               # Security tests
    ├── snapshots/              # API schema snapshots
    ├── startup/                # Startup tests
    └── webhooks/               # Webhook tests
```

## Frontend (Next.js 16.2 / React 18.3)

```
frontend/
├── app/                        # Next.js App Router
│   ├── page.tsx                # Landing page
│   ├── layout.tsx              # Root layout (providers, metadata)
│   ├── types.ts                # Shared TypeScript types
│   ├── api-types.generated.ts  # Auto-generated OpenAPI -> TypeScript
│   │
│   ├── # --- Core Authenticated Pages ---
│   ├── buscar/                 # Main search page (SSE, filters, results)
│   │   ├── components/         # 33 search-specific components
│   │   ├── hooks/              # useSearch, useSearchFilters, useUfProgress
│   │   ├── constants/          # Search constants
│   │   ├── types/              # Search-specific types
│   │   └── utils/              # dates, reliability
│   ├── pipeline/               # Opportunity kanban (drag-and-drop)
│   ├── dashboard/              # Personal analytics dashboard
│   ├── historico/              # Search history
│   ├── mensagens/              # InMail support inbox
│   ├── analise/[hash]/         # Search analysis page
│   │
│   ├── # --- Auth Pages ---
│   ├── login/                  # Login
│   ├── signup/                 # Cadastro
│   ├── auth/callback/          # OAuth callback
│   ├── recuperar-senha/        # Password recovery
│   ├── redefinir-senha/        # Password reset
│   │
│   ├── # --- Account / Settings ---
│   ├── conta/                  # Account (dados, plano, seguranca, equipe, preferencias)
│   │   ├── cancelar-trial/
│   │   └── api/                # Account API handlers
│   ├── configuracoes/          # Settings
│   │
│   ├── # --- Onboarding ---
│   ├── onboarding/             # 3-step wizard (CNAE -> UFs -> first-analysis)
│   │
│   ├── # --- Marketing / Landing Pages ---
│   ├── planos/                 # Pricing plans
│   │   ├── obrigado/           # Post-checkout thank you
│   │   └── command/            # Plan command
│   ├── pricing/                # Pricing marketing page
│   ├── features/               # Features page
│   ├── planos/                 # Plans comparison
│   ├── landing/                # Landing sections (11 components)
│   ├── consultoria/            # Consulting services
│   ├── consultoria-b2g/        # B2G consulting
│   ├── consultorias/           # Consulting listing
│   ├── para-empresas/          # For companies
│   ├── para-advogados/         # For lawyers
│   ├── para-consultorias/      # For consultancies
│   ├── para-construtoras/      # For construction companies
│   ├── para-fornecedores/      # For suppliers
│   ├── para-empresas-de-ti/    # For IT companies
│   ├── para-quem-quer-subcontratar/  # For subcontractors
│   ├── sobre/                  # About us
│   ├── demo/                   # Demo
│   ├── casos/                  # Case studies
│   │
│   ├── # --- SEO Programmatic Pages (10k+, ISR) ---
│   ├── observatorio/[slug]/    # Observatory dynamic pages
│   │   └── embed/              # Embedded widgets
│   ├── cnpj/[cnpj]/            # Per-CNPJ pages
│   ├── fornecedores/[cnpj]/    # Supplier pages
│   ├── orgaos/[slug]/          # Public agency pages
│   ├── orgaos-publicos/        # Public agencies listing
│   ├── municipios/[slug]/      # Municipality pages
│   ├── licitacoes/[setor]/     # Sector bidding pages
│   ├── contratos/[setor]/      # Contract pages
│   │   └── orgao/              # By agency
│   ├── alertas-publicos/[setor]/  # Public alerts
│   ├── alertas/                # Alerts main
│   ├── itens/[catmat]/         # Item (CATMAT) pages
│   ├── compliance/[cnpj]/      # Compliance pages
│   ├── indice-municipal/[municipio-uf]/  # Municipal index
│   ├── dados/                  # Open data
│   ├── estatisticas/           # Statistics
│   │   └── embed/              # Embedded stats
│   ├── calculadora/            # Bid calculator
│   │   └── embed/              # Embedded calculator
│   ├── comparador/             # Bid comparison tool
│   ├── inteligencia/[cnpj]/    # Intelligence pages
│   ├── intel-concorrente/      # Competitor intelligence
│   ├── intel-reports/          # Intel reports
│   ├── segmentar/              # Segmentation
│   │
│   ├── # --- Content Pages ---
│   ├── blog/                   # Blog (contratos, licitacoes, panorama, programmatic)
│   │   ├── [slug]/             # Blog posts
│   │   ├── author/             # Author pages
│   │   ├── content/            # Blog content data
│   │   ├── componentes/        # Blog components
│   │   ├── rss.xml/            # RSS feed
│   │   └── weekly/             # Weekly digests
│   ├── guia/                   # Guides
│   │   ├── [slug]/             # Guide pages
│   │   ├── _components/        # Guide components
│   │   ├── _content/           # Guide content
│   │   └── guia-pratico-b2g/   # Practical B2G guide
│   ├── ajuda/                  # Help center
│   ├── glossario/[termo]/      # Glossary terms
│   ├── perguntas/[slug]/       # FAQ pages
│   ├── masterclass/[tema]/     # Masterclass
│   ├── ferramentas/            # Tools
│   ├── como-avaliar-licitacao/ # SEO content: how to evaluate bids
│   ├── como-evitar-prejuizo-licitacao/  # SEO content
│   ├── como-filtrar-editais/   # SEO content
│   ├── como-priorizar-oportunidades/    # SEO content
│   ├── relatorios/             # Reports
│   │   └── mensal/             # Monthly reports
│   ├── relatorio-2026-t1/      # Q1 2026 report
│   ├── licitacoes-publicas-2026/  # Public bids 2026
│   ├── licitacoes-do-dia/      # Today's bids (blog)
│   │
│   ├── # --- B2B Intelligence ---
│   ├── intencao/               # Intent pages (comercial, investigativa, juridica,
│   │                           #   subcontratacao)
│   ├── radar/                  # Radar monitoring
│   ├── radar-recorrencia/      # Recurrence radar
│   ├── marketplace/            # Marketplace
│   ├── subcontratacao/         # Subcontracting
│   ├── widgets/                # Embeddable widgets
│   │   └── competitive-intel/  # Competitive intelligence widget
│   │
│   ├── # --- Legal Pages ---
│   ├── privacidade/            # Privacy policy
│   ├── termos/                 # Terms of service
│   │   └── fundadores/         # Founders terms
│   │
│   ├── # --- Admin Pages ---
│   ├── admin/                  # Admin panel
│   │   ├── billing/            # Billing admin
│   │   ├── cache/              # Cache dashboard
│   │   ├── calibration/        # LLM calibration
│   │   ├── components/         # Admin components
│   │   ├── emails/             # Email admin
│   │   ├── feature-flags/      # Feature flags
│   │   ├── founding/           # Founding admin
│   │   ├── metrics/            # Metrics
│   │   ├── partners/           # Partners
│   │   ├── seo/                # SEO admin
│   │   └── slo/                # SLO dashboard
│   │
│   ├── # --- Static / Other ---
│   ├── status/                 # Status page
│   ├── stack/                  # Tech stack page
│   ├── founding/               # Founding program
│   ├── fundadores/             # Founders
│   ├── obrigado/               # Generic thank you
│   ├── indicar/                # Referral
│   ├── (protected)/            # Protected route layout
│   └── _dev/                   # Dev tools
│       └── sentry-test/        # Sentry test page
│
│   ├── # --- API Route Handlers (proxy to backend) ---
│   ├── api/
│   │   ├── buscar/route.ts     # POST -> /buscar
│   │   ├── buscar-progress/    # GET -> SSE stream
│   │   ├── buscar-results/     # GET -> search results
│   │   ├── search-status/      # Search status polling
│   │   ├── search-cancel/      # Cancel search
│   │   ├── search-zero-match/  # Zero-match results
│   │   ├── download/route.ts   # Excel download
│   │   ├── feedback/route.ts   # POST/DELETE /v1/feedback
│   │   ├── admin/[...path]/    # Dynamic admin proxy
│   │   ├── analytics/route.ts  # Analytics endpoints
│   │   ├── billing-portal/     # Stripe billing portal
│   │   ├── trial-status/       # Trial status
│   │   ├── subscription-status/ # Subscription status
│   │   ├── checkout/           # Stripe checkout
│   │   ├── billing/            # Billing API
│   │   ├── plans/              # Plans API
│   │   ├── me/                 # User profile
│   │   ├── user/               # User data
│   │   ├── auth/               # Auth endpoints
│   │   ├── change-password/    # Password change
│   │   ├── mfa/                # MFA management
│   │   ├── messages/           # Messages API
│   │   ├── sessions/           # Sessions API
│   │   ├── pipeline/           # Pipeline API
│   │   ├── alerts/             # Alerts API
│   │   ├── alert-preferences/  # Alert preferences
│   │   ├── onboarding/         # Onboarding API
│   │   ├── first-analysis/     # First analysis dispatch
│   │   ├── conta/              # Account API
│   │   ├── dados/              # Data API
│   │   ├── export/             # Export API
│   │   ├── relatorio/          # Report API
│   │   ├── regenerate-excel/   # Excel regeneration
│   │   ├── sectors/            # Sectors API
│   │   ├── setores/            # Setores (PT-BR)
│   │   ├── empresa/            # Company API
│   │   ├── feature-flags/      # Feature flags API
│   │   ├── calculadora/        # Calculator API
│   │   ├── comparador/         # Comparator API
│   │   ├── blog/               # Blog API
│   │   ├── health/             # Health check
│   │   ├── metrics/            # Metrics endpoint
│   │   ├── stats/              # Stats
│   │   ├── status/             # Status
│   │   ├── og/                 # Open Graph generation
│   │   ├── badge/              # Badge generation
│   │   ├── docs/               # API docs proxy
│   │   ├── csp-report/         # CSP violation report
│   │   ├── bid-analysis/       # Bid analysis
│   │   ├── b2b-intel/          # B2B intelligence
│   │   ├── intel-reports/      # Intel reports
│   │   ├── lead-capture/       # Lead capture
│   │   ├── new-bids-count/     # New bids counter
│   │   ├── organizations/      # Organizations
│   │   ├── profile-completeness/ # Profile completeness
│   │   ├── profile-context/    # Profile context
│   │   ├── pseo/               # Programmatic SEO
│   │   ├── referral/           # Referral tracking
│   │   ├── revalidate/         # ISR revalidation
│   │   ├── reports/            # Reports API
│   │   ├── segment/            # Segment API
│   │   ├── share/              # Share API
│   │   ├── subcontract/        # Subcontracting API
│   │   ├── survey/             # Survey API
│   │   ├── trial/              # Trial API
│   │   ├── founding/           # Founding API
│   │   ├── founders-hall/      # Founders hall
│   │   ├── products/           # Products API
│   │   ├── experiments/        # A/B experiments
│   │   └── v1/                 # Legacy API proxy
│   │
│   ├── # --- Shared Components ---
│   ├── components/
│   │   ├── ui/                 # Design system (Button, Input, Modal, Pagination...)
│   │   ├── landing/            # Landing page sections
│   │   ├── navigation/         # NavigationShell, Sidebar, BottomNav, MobileDrawer
│   │   ├── seo/                # SEO components (JSON-LD, metadata)
│   │   ├── programmatic/       # Programmatic page components
│   │   ├── checkout/           # Checkout components
│   │   ├── conversion/         # Conversion optimization
│   │   ├── whatsapp/           # WhatsApp integration
│   │   ├── __tests__/          # Component tests
│   │   ├── AuthProvider.tsx
│   │   ├── AppHeader.tsx
│   │   ├── LoadingProgress.tsx
│   │   ├── TrialConversionScreen.tsx
│   │   └── ... (72+ total components)
│   │
│   ├── # --- Hooks ---
│   ├── hooks/                  # Shared custom hooks
│   ├── contexts/               # React contexts (auth, theme, etc.)
│   ├── lib/                    # Library code (api client, supabase, stripe)
│   ├── types/                  # Global TypeScript types
│   ├── data/                   # Static data
│   └── content/                # Content data (blog posts, guides, FAQ, glossary)
│
├── # --- Tests ---
├── __tests__/                  # Jest tests (~2681+ tests, 50+ categories)
│   ├── api/                    # API handler tests
│   ├── buscar/                 # Search page tests
│   ├── components/             # Component tests
│   ├── hooks/                  # Hook tests
│   ├── auth/                   # Auth flow tests
│   ├── billing/                # Billing tests
│   ├── pipeline/               # Pipeline tests
│   ├── onboarding/             # Onboarding tests
│   ├── admin/                  # Admin tests
│   ├── alerts/                 # Alert tests
│   ├── blog/                   # Blog tests
│   ├── pseo/                   # Programmatic SEO tests
│   ├── seo/                    # SEO tests
│   ├── landing/                # Landing page tests
│   ├── layout/                 # Layout tests
│   ├── billing/                # Billing tests
│   ├── checkout/               # Checkout tests
│   ├── planos/                 # Plan page tests
│   ├── pricing/                # Pricing tests
│   ├── signup/                 # Signup tests
│   ├── onboarding/             # Onboarding tests
│   ├── conta/                  # Account tests
│   ├── configuracoes/          # Settings tests
│   ├── dashboard/              # Dashboard tests
│   ├── relatorios/             # Reports tests
│   ├── intel-reports/          # Intel reports tests
│   ├── intel-concorrente/      # Competitor intel tests
│   ├── licitacoes/             # Bid page tests
│   ├── contratos/              # Contract page tests
│   ├── fornecedores/           # Supplier page tests
│   ├── org/                    # Org page tests
│   ├── pages/                  # General page tests
│   ├── app/                    # App-level tests
│   ├── data/                   # Data tests
│   ├── lib/                    # Library tests
│   ├── schemas/                # Schema tests
│   ├── search-results/         # Search result tests
│   ├── fundadores/             # Founders tests
│   ├── founding/               # Founding tests
│   ├── consultoria/            # Consulting tests
│   ├── intencao/               # Intent tests
│   ├── radar/                  # Radar tests
│   ├── radar-recorrencia/      # Recurrence radar tests
│   ├── polich/                 # Polish tests
│   ├── privacidade/            # Privacy tests
│   ├── story-257b/             # Story-specific tests
│   ├── recovery/               # Recovery tests
│   ├── a11y/                   # Accessibility tests
│   ├── banners/                # Banner tests
│   └── ... (additional categories)
│
├── e2e-tests/                  # Playwright E2E (~60 tests)
├── tests/
│   └── chromatic/              # Chromatic visual regression
│
├── # --- Config ---
├── .storybook/                 # Storybook config
├── .interface-design/          # Interface design docs
├── hooks/                      # Shared hooks
├── components/                 # Server components
├── contexts/                   # React contexts
├── lib/                        # Utility libraries
├── types/                      # Shared types
├── data/                       # Static data
├── content/                    # Content
├── public/                     # Static assets
├── scripts/                    # Build and utility scripts
│   └── eslint-rules/           # Custom ESLint rules
├── __mocks__/                  # Jest mocks
│
├── jest.config.js
├── jest.setup.js
├── tailwind.config.js
├── tsconfig.json
├── next.config.js
├── playwright.config.ts
└── package.json
```

## Documentacao

```
docs/
├── framework/                  # Guias de referencia do framework
│   ├── source-tree.md          # Estrutura do projeto
│   ├── tech-stack.md           # Pilha tecnologica
│   └── coding-standards.md     # Padroes de codigo
├── architecture/               # ADRs e documentacao arquitetural
│   ├── dependencies.md         # Dependencias do projeto (este arquivo)
│   ├── inventory.md            # Inventario de estrutura (este arquivo)
│   ├── overview.md             # Visao geral da arquitetura (C4)
│   ├── adr-*.md                # Architecture Decision Records
│   ├── system-architecture.md  # Arquitetura detalhada do sistema
│   ├── multi-source-*.md       # Documentacao multi-fonte
│   ├── frontend-code-analysis.md
│   ├── api-versioning.md       # Politica de versionamento de API
│   ├── webhook-handlers.md     # Documentacao de webhooks
│   ├── rate-limiting.md        # Rate limiting strategy
│   ├── circuit-breaker-audit.md
│   ├── llm-arbiter.md          # Arquitetura do LLM arbiter
│   ├── dedup-algorithm.md      # Algoritmo de deduplicacao
│   └── ... (30+ arquivos)
├── stories/                    # Historias de desenvolvimento
├── api/                        # Documentacao de API
├── guides/                     # Guias de desenvolvimento
├── prd/                        # PRD sharded (epics)
├── adr/                        # ADRs (alternate location)
├── deployment/                 # Documentacao de deploy
├── infraestrutura/             # Documentacao de infraestrutura
├── security/                   # Documentacao de seguranca
├── testing/                    # Documentacao de testes
├── qa/                         # QA reports
├── runs/                       # Runbooks
├── incidents/                  # Relatorios de incidentes
├── performance/                # Documentacao de performance
├── observability/              # Observabilidade
├── analytics/                  # Analytics docs
├── features/                   # Feature documentation
├── implementacao/              # Implementation notes
├── evidence/                   # Evidencia de teste/QA
├── summaries/                  # Sumarios executivos
├── decisions/                  # Decisoes de produto/tecnologia
├── intel/                      # Business intelligence
├── intel-b2g/                  # B2G intelligence
├── commercial/                 # Documentacao comercial
├── sales/                      # Sales collateral
├── research/                   # Pesquisas
├── ux/                         # UX design docs
├── ux-analysis/                # UX analysis
├── accessibility/              # Acessibilidade
├── audit/                      # Auditorias
└── ... (additional directories)
```

## Infraestrutura

```
supabase/
├── migrations/                 # ~183 migrations (source of truth)
│   ├── YYYYMMDDHHMMSS_description.sql
│   └── YYYYMMDDHHMMSS_description.down.sql  # Rollback obrigatorio (STORY-6.2)
└── ...

infra/                          # Infraestrutura como codigo
data/                           # Dados estaticos
scripts/                        # Scripts de automation
squads/                         # Squad definitions
tests/                          # Testes de integracao/infra
```

---

## Notas

- **Backend tests:** ~5131+ tests (454 test files), excluindo fuzz e benchmark
- **Frontend tests:** ~2681+ tests (376 test files), 50+ categorias de teste
- **E2E tests:** ~60 testes Playwright
- **Rotas API:** 187 endpoints em 65 routers registrados
- **Paginas frontend:** ~25 paginas core + 10k+ paginas programmaticas (ISR)
- **Componentes frontend:** 72+ componentes compartilhados
- **Migrations:** ~183 migrations no diretorio `supabase/migrations/`
