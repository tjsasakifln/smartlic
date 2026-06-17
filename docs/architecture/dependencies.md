# Dependencias do Projeto — SmartLic

**Ultima atualizacao:** 2026-06-17

Este documento e a fonte unificada de verdade para as dependencias do projeto,
extraida diretamente de `backend/requirements.txt` e `frontend/package.json`.

---

## Backend (Python 3.12)

### Core Framework

| Componente | Versao no requirements.txt | Uso |
|------------|---------------------------|-----|
| FastAPI | 0.137.0 | API REST + SSE |
| Uvicorn | 0.49.0 | ASGI server (sem extras `[standard]` — CRIT-SIGSEGV-v2) |
| Gunicorn | 23.0.0 | Process management (inativo — RUNNER=uvicorn ativo) |
| Pydantic | 2.13.4 | Validacao e schemas (com suporte email) |
| pydantic-settings | 2.14.1 | .env loading com validacao |
| Starlette | 0.52.1 | Base ASGI framework |
| python-multipart | >=0.0.32 | Upload parsing (CVE-2026-24486 fix) |
| python-dateutil | >=2.9.0.post0 | Parsing de datas (era transitiva, tornada explicita em 2026-06-08) |

### HTTP & Integracoes

| Componente | Versao | Uso |
|------------|--------|-----|
| httpx | 0.28.1 | HTTP client async (PNCP, PCP, ComprasGov) |
| PyYAML | >=6.0.3 | Configuracao de setores (sectors_data.yaml) |
| jsonschema | 4.26.0 | Validacao de schema (contratos + canary) |

### LLM & AI

| Componente | Versao | Uso |
|------------|--------|-----|
| openai | 1.109.1 | GPT-4.1-nano para classificacao + resumos executivos |

### Database & Cache

| Componente | Versao | Uso |
|------------|--------|-----|
| supabase | 2.31.0 | PostgreSQL + Auth + RLS + Storage |
| PyJWT | >=2.13.0 | Validacao JWT (ES256 + JWKS — STORY-227) |
| redis | 5.3.1 | Cache L1, SSE state, rate limiter, locks |

### Billing & Payments

| Componente | Versao | Uso |
|------------|--------|-----|
| stripe | 11.6.0 | Subscriptions, webhooks, billing portal |

### Background Jobs

| Componente | Versao | Uso |
|------------|--------|-----|
| arq | >=0.28.0 | Job queue async (LLM, Excel, notificacoes) |

### Output Generation

| Componente | Versao | Uso |
|------------|--------|-----|
| openpyxl | 3.1.5 | Excel estilizado com openpyxl |
| reportlab | 4.5.1 | PDF (Diagnostico de Oportunidades — STORY-325) |

### Auth & Security

| Componente | Versao | Uso |
|------------|--------|-----|
| bcrypt | >=5.0.0 | Hashing de recovery codes (MFA TOTP — STORY-317) |
| cryptography | >=46.0.6,<47.0.0 | Token encryption Google OAuth, CVE fixes |

### Google Integration

| Componente | Versao | Uso |
|------------|--------|-----|
| google-api-python-client | 2.197.0 | Google Sheets API |
| google-auth | 2.54.0 | OAuth 2.0 |
| google-auth-oauthlib | 1.4.0 | OAuth flow |
| google-auth-httplib2 | 0.4.0 | HTTP transport |

### Email

| Componente | Versao | Uso |
|------------|--------|-----|
| resend | >=2.30.1 | Email transacional (dominio smartlic.tech) |

### ML & Data Science (adicionado 2026-Q2 — SCORE-001)

| Componente | Versao | Uso |
|------------|--------|-----|
| numpy | >=2.4.6 | Operacoes numericas |
| scikit-learn | >=1.9.0 | ML win probability model |
| joblib | >=1.5.3 | Model serialization |
| pandas | >=3.0.3 | Data manipulation |

### Observabilidade

| Componente | Versao | Uso |
|------------|--------|-----|
| sentry-sdk[fastapi] | 2.62.0 | Error tracking (pinned — STORY-413) |
| prometheus_client | >=0.25.0 | Metricas /metrics endpoint |
| python-json-logger | >=4.1.0 | Structured JSON logging |
| opentelemetry-api | >=1.41.1 | Distributed tracing API |
| opentelemetry-sdk | >=1.41.1 | Tracing SDK |
| opentelemetry-exporter-otlp-proto-http | >=1.41.1 | OTLP HTTP export |
| opentelemetry-instrumentation-fastapi | >=0.62b1 | FastAPI auto-instrumentation |
| opentelemetry-instrumentation-httpx | >=0.62b1 | HTTP client tracing |
| mixpanel | >=4.11.1 | Product analytics (backend events) |
| psutil | >=5.9.8 | Process memory introspection (health checks) |

---

## Frontend (Node.js >=18)

### Core Framework

| Componente | Versao no package.json | Uso |
|------------|-----------------------|-----|
| next | ^16.2.9 | Framework SSR + ISR + API routes |
| react | ^18.3.1 | Component model |
| react-dom | ^18.3.1 | DOM rendering |
| typescript | ^5.9.3 (dev) | Type safety |
| tailwindcss | ^3.4.19 (dev) | Utility-first CSS |
| autoprefixer | ^10.5.0 (dev) | CSS vendor prefixes |
| postcss | ^8.5.15 (dev) | CSS processor |

### UI & Icons

| Componente | Versao | Uso |
|------------|--------|-----|
| lucide-react | ^0.577.0 | Icon system |
| framer-motion | ^12.40.0 | Animacoes e transicoes |
| sonner | ^2.0.7 | Toast notifications |
| nprogress | ^0.2.0 | Progress bar |
| recharts | ^3.8.1 | Charts interativos |
| react-markdown | ^10.1.0 | Markdown rendering |
| remark-gfm | ^4.0.1 | GFM markdown support |
| swr | ^2.4.1 | Data fetching com cache e revalidation |
| react-simple-pull-to-refresh | ^1.3.4 | Pull-to-refresh mobile |
| web-vitals | ^5.3.0 | Core Web Vitals reporting |

### Forms & Validation

| Componente | Versao | Uso |
|------------|--------|-----|
| react-hook-form | ^7.79.0 | Form state management |
| @hookform/resolvers | ^5.4.0 | Schema resolvers |
| zod | ^4.4.3 | Schema validation |
| class-variance-authority | ^0.7.1 | Variant-based class management |
| clsx | ^2.1.1 | Conditional class names |
| tailwind-merge | ^3.6.0 | Tailwind class merging |

### Drag & Drop

| Componente | Versao | Uso |
|------------|--------|-----|
| @dnd-kit/core | ^6.3.1 | Pipeline kanban drag-and-drop |
| @dnd-kit/sortable | ^10.0.0 | Sortable items |
| @dnd-kit/utilities | ^3.2.2 | DnD utilities |

### Date Handling

| Componente | Versao | Uso |
|------------|--------|-----|
| date-fns | ^4.4.0 | Date formatting |
| react-day-picker | ^9.14.0 | Calendar/date picker |

### Auth & Database

| Componente | Versao | Uso |
|------------|--------|-----|
| @supabase/ssr | ^0.12.0 | Server-side auth |
| @supabase/supabase-js | ^2.108.2 | Supabase client |
| @supabase/auth-helpers-nextjs | ^0.15.0 | Legacy auth helpers |
| uuid | ^13.0.2 | ID generation |
| use-debounce | ^10.1.1 | Input debouncing |

### UI Components (Radix + Tailwind)

| Componente | Versao | Uso |
|------------|--------|-----|
| @radix-ui/react-slot | ^1.2.4 | Slot pattern |
| @tailwindcss/typography | ^0.5.20 | Typography plugin |
| focus-trap-react | ^12.0.2 | Focus trap (modal acessibilidade) |

### Stripe (Frontend)

| Componente | Versao | Uso |
|------------|--------|-----|
| @stripe/react-stripe-js | ^6.5.0 | Stripe Elements React |
| @stripe/stripe-js | ^9.8.0 | Stripe.js |

### Monitoring & Analytics

| Componente | Versao | Uso |
|------------|--------|-----|
| @sentry/nextjs | ^10.57.0 | Error tracking frontend |
| mixpanel-browser | ^2.80.0 | User analytics |

### Dev Dependencies — Testing

| Componente | Versao | Uso |
|------------|--------|-----|
| jest | ^29.7.0 | Test runner |
| @testing-library/react | ^14.1.2 | Component testing |
| @testing-library/jest-dom | ^6.1.5 | DOM matchers |
| @testing-library/user-event | ^14.5.1 | User event simulation |
| jest-environment-jsdom | ^29.7.0 | JSDOM environment |
| @swc/core | ^1.15.41 | TypeScript transpiler |
| @swc/jest | ^0.2.29 | Jest SWC integration |
| jest-axe | ^10.0.0 | Accessibility assertions |
| @types/jest-axe | ^3.5.9 | Type definitions |

### Dev Dependencies — E2E

| Componente | Versao | Uso |
|------------|--------|-----|
| @playwright/test | ^1.60.0 | E2E browser tests |
| @axe-core/playwright | ^4.11.3 | Accessibility E2E |
| @chromatic-com/playwright | ^0.14.8 | Visual regression |

### Dev Dependencies — Performance & Build

| Componente | Versao | Uso |
|------------|--------|-----|
| @lhci/cli | ^0.15.0 | Lighthouse CI |
| @next/bundle-analyzer | ^16.2.9 | Bundle analysis |
| size-limit | ^11.2.0 | Bundle size control |
| @size-limit/file | ^11.2.0 | File size plugin |
| next-sitemap | ^4.2.3 | Sitemap generation |
| openapi-typescript | ^7.13.0 | OpenAPI -> TypeScript codegen |

### Dev Dependencies — Storybook

| Componente | Versao | Uso |
|------------|--------|-----|
| storybook | ^8.6.18 | Component documentation |
| @storybook/nextjs | ^8.6.18 | Next.js integration |
| @storybook/react | ^8.6.18 | React integration |
| @storybook/react-webpack5 | ^8.6.18 | Webpack 5 build |
| @storybook/addon-essentials | ^8.6.14 | Essential addons |
| @storybook/blocks | ^8.6.14 | Doc blocks |
| @storybook/test | ^8.6.18 | Testing addon |

### Dev Dependencies — Linting & Types

| Componente | Versao | Uso |
|------------|--------|-----|
| eslint-plugin-local-rules | ^3.0.2 | Project-specific ESLint rules |
| js-yaml | ^4.2.0 | YAML parsing (tests) |
| robots-parser | ^3.0.1 | Robots.txt parsing (tests) |

### Type Definitions

| Componente | Versao |
|------------|--------|
| @types/node | ^25.9.3 |
| @types/react | ^19.2.9 |
| @types/react-dom | ^19.2.3 |
| @types/nprogress | ^0.2.3 |
| @types/uuid | ^10.0.0 |
| @types/js-yaml | ^4.0.9 |

---

## Infraestrutura

| Componente | Provedor | Uso |
|------------|----------|-----|
| Backend (web) | Railway | FastAPI server (PROCESS_TYPE=web) |
| Backend (worker) | Railway | ARQ job processor (PROCESS_TYPE=worker) |
| Frontend | Railway | Next.js SSR standalone |
| Database | Supabase Cloud | PostgreSQL 17 + Auth + RLS + Storage |
| Cache / Queue | Upstash / Railway Redis | L1 cache, SSE state, rate limiter, ARQ queue |
| CI/CD | GitHub Actions | Build, test, deploy |
| DNS | Cloudflare | smartlic.tech |
| Payments | Stripe | Subscriptions, invoices, webhooks |
| Email | Resend | Transactional email |
| Error tracking | Sentry | Backend + Frontend |
| Metrics | Prometheus + Grafana | /metrics + dashboards |
| Tracing | OpenTelemetry (OTLP) | Tracing distribuido |

---

## APIs Externas

| Servico | Endpoint | Prioridade | Auth |
|---------|----------|------------|------|
| PNCP | `pncp.gov.br/api/consulta/v1/contratacoes/publicacao` | 1 (primary) | None |
| PCP v2 | `compras.api.portaldecompraspublicas.com.br/v2/licitacao/processos` | 2 | None (public) |
| ComprasGov v3 | `dadosabertos.compras.gov.br` | 3 | None |
| OpenAI | `api.openai.com` | N/A | API Key |
| Stripe | `api.stripe.com` | N/A | Secret Key |
| Resend | `api.resend.com` | N/A | API Key |
| Google OAuth | `accounts.google.com` | N/A | Client ID/Secret |

---

## Notas sobre Dependencias Recentes (3 meses)

Dependencias adicionadas ou significativamente atualizadas nos ultimos 3 meses (desde ~2026-03):

| Dependencia | Mudanca | Referencia |
|-------------|---------|------------|
| reportlab 4.5.1 | **Nova** — geracao de PDF | STORY-325 |
| numpy >=2.4.6 | **Nova** — ML pipeline | SCORE-001 (#1614) |
| scikit-learn >=1.9.0 | **Nova** — ML win probability | SCORE-001 (#1614) |
| joblib >=1.5.3 | **Nova** — model serialization | SCORE-001 (#1614) |
| pandas >=3.0.3 | **Nova** — data manipulation | SCORE-001 (#1614) |
| prometheus_client >=0.25.0 | **Promovida** — required (era opcional) | GTM-RESILIENCE-E03 |
| psutil >=5.9.8 | **Nova** — memory introspection | SEN-BE-010 |
| mixpanel >=4.11.1 | **Nova** — estava ausente (bug fix) | PR #530 |
| bcrypt >=5.0.0 | **Nova** — recovery codes | STORY-317 |
| python-dateutil >=2.9.0.post0 | **Tornada explicita** — era transitiva | PR #1555 |
| cryptography >=46.0.6 | **Atualizada** — CVE fixes + pin | DEBT-018 |
| supabase 2.31.0 | **Atualizada** — breaking changes | 2.13.0 -> 2.31.0 |
| pydantic 2.13.4 | **Atualizada** | 2.12.x -> 2.13.4 |
| fastapi 0.137.0 | **Atualizada** | 0.129.x -> 0.137.0 |
| sentry-sdk 2.62.0 | **Atualizada** — pin exact | STORY-413 |
| next ^16.2.9 | **Atualizada** — major | 14.x -> 16.x |

---

## Referencias

- `backend/requirements.txt` — Fonte de verdade para dependencias Python
- `frontend/package.json` — Fonte de verdade para dependencias Node.js
- `docs/framework/tech-stack.md` — Visao geral da pilha tecnologica
