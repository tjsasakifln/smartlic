# Tech Stack — SmartLic v0.5

## Backend (Python 3.12)

### Core Framework

| Componente | Tecnologia | Versao | Justificativa |
|------------|------------|--------|---------------|
| Framework | FastAPI | 0.137.0 | Performance, async, validacao automatica |
| Runtime | Python | 3.12 | Ecosystem rico, type hints avanados |
| Server (dev) | Uvicorn | 0.49.0 | ASGI server, hot-reload |
| Server (prod) | Uvicorn | 0.49.0 | workers via multiprocessing (Gunicorn inativo — CRIT-084) |
| Validacao | Pydantic | 2.13.4 | Type safety, structured outputs |
| Config | pydantic-settings | 2.14.1 | .env loading com validacao |
| ASGI Base | Starlette | 0.52.1 | Base ASGI framework |
| Multipart | python-multipart | >=0.0.32 | Upload parsing (CVE-2026-24486) |
| Date parsing | python-dateutil | >=2.9.0.post0 | Parsing de datas |

### HTTP & Data Sources

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| HTTP Client | httpx | 0.28.1 | Resilient HTTP, async support |
| YAML Parser | PyYAML | >=6.0 | Sector config (sectors_data.yaml) |
| Excel | openpyxl | 3.1.5 | Planilhas formatadas |
| PDF | reportlab | 4.5.1 | PDF (Diagnostico de Oportunidades) |
| JSON Schema | jsonschema | 4.26.0 | Validacao de contratos + canary |

### AI / LLM

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| OpenAI SDK | openai | 1.109.1 | GPT-4.1-nano classificacao + resumos |

### Database & Cache

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Database | Supabase | 2.31.0 | PostgreSQL + Auth + RLS + Storage |
| Cache/Queue | Redis | 5.3.1 | Cache L1, circuit breaker, job queue |
| Auth tokens | PyJWT | >=2.13.0 | JWT validation (ES256/JWKS) |
| Hash (MFA) | bcrypt | >=5.0.0 | Recovery code hashing (STORY-317) |

### Billing & Payments

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Payments | Stripe | 11.6.0 | Subscriptions, webhooks, billing portal |

### Background Jobs

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Job Queue | ARQ | >=0.26 | LLM + Excel async processing |

### Monitoring & Observability

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Error tracking | Sentry | 2.62.0 (pinned) | FastAPI integration (STORY-413) |
| Metrics | prometheus_client | >=0.25.0 | /metrics endpoint |
| Tracing (API) | opentelemetry-api | >=1.41.1 | Distributed tracing |
| Tracing (SDK) | opentelemetry-sdk | >=1.41.1 | Spans, exporters |
| Tracing (OTLP) | opentelemetry-exporter-otlp-proto-http | >=1.41.1 | OTLP export (HTTP, nao gRPC) |
| Tracing (FastAPI) | opentelemetry-instrumentation-fastapi | >=0.62b1 | Auto-instrumentation |
| Tracing (httpx) | opentelemetry-instrumentation-httpx | >=0.62b1 | HTTP client tracing |
| Logging | python-json-logger | >=4.1.0 | Structured JSON logs |
| Memory | psutil | >=5.9.8 | Process memory introspection (health) |
| Analytics | mixpanel | >=4.11.1 | Product analytics backend events |

### Google Integration

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Google API | google-api-python-client | 2.197.0 | Sheets export |
| Google Auth | google-auth | 2.54.0 | OAuth 2.0 |
| Google Auth OAuth | google-auth-oauthlib | 1.4.0 | OAuth flow helpers |
| Google Auth HTTP | google-auth-httplib2 | 0.4.0 | HTTP transport |
| Crypto | cryptography | >=46.0.6 | Token encryption (CVE fixes) |

### Email

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Transactional | Resend | >=2.30.1 | Welcome, quota, billing emails |

### ML Win Probability (SCORE-001, adicionado 2026-Q2)

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| ML Framework | scikit-learn | >=1.9.0 | Win probability model |
| Numerical | numpy | >=2.4.6 | Operacoes numericas |
| Data | pandas | >=3.0.3 | Data manipulation |
| Serialization | joblib | >=1.5.3 | Model serialization |

---

## Frontend (Node.js 18+)

### Core Framework

| Componente | Tecnologia | Versao | Justificativa |
|------------|------------|--------|---------------|
| Framework | Next.js | ^16.2.9 | App Router, SSR, API routes |
| Runtime | React | ^18.3.1 | Component model, hooks |
| Language | TypeScript | ^5.9.3 | Type safety |
| Styling | Tailwind CSS | ^3.4.19 | Utility-first, responsive |

### UI Libraries

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Icons | lucide-react | ^0.577.0 | Icon system |
| Animation | framer-motion | ^12.40.0 | Transitions, motion |
| Toast | sonner | ^2.0.7 | Notifications |
| Onboarding | shepherd.js | ^14.5.1 | Product tours |
| Progress bar | nprogress | ^0.2.0 | Navigation indicator |
| Charts | recharts | ^3.8.1 | Analytics dashboards |
| Markdown | react-markdown + remark-gfm | ^10.1.0 / ^4.0.1 | Markdown rendering |
| Data Fetching | swr | ^2.4.1 | Cache + revalidation |
| Pull-to-refresh | react-simple-pull-to-refresh | ^1.3.4 | Mobile gesture |
| Web Vitals | web-vitals | ^5.3.0 | Core Web Vitals |

### Date & DnD

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Dates | date-fns | ^4.4.0 | Date formatting |
| Date picker | react-day-picker | ^9.14.0 | Calendar UI |
| Drag & Drop | @dnd-kit/core + sortable + utilities | ^6.3.1 / ^10.0.0 | Pipeline kanban |

### Forms & Validation

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Forms | react-hook-form | ^7.79.0 | Form state management |
| Validation | zod | ^4.4.3 | Schema validation |
| Resolvers | @hookform/resolvers | ^5.4.0 | Zod resolver |
| Utils | clsx, tailwind-merge, class-variance-authority | ^2.1.1 / ^3.6.0 / ^0.7.1 | Class management |

### Auth & Data

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Auth (SSR) | @supabase/ssr | ^0.12.0 | Server-side auth |
| Auth helpers | @supabase/auth-helpers-nextjs | ^0.15.0 | Legacy auth helpers |
| Supabase JS | @supabase/supabase-js | ^2.108.2 | Database client |
| UUID | uuid | ^13.0.2 | ID generation |
| Debounce | use-debounce | ^10.1.1 | Input debouncing |
| Slot | @radix-ui/react-slot | ^1.2.4 | Slot pattern |
| Typography | @tailwindcss/typography | ^0.5.20 | Prose styling |
| Focus trap | focus-trap-react | ^12.0.2 | Modal accessibility |

### Stripe (Frontend)

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| React Elements | @stripe/react-stripe-js | ^6.5.0 | Stripe UI components |
| Stripe.js | @stripe/stripe-js | ^9.8.0 | Stripe SDK |

### Monitoring

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Error tracking | @sentry/nextjs | ^10.57.0 | Frontend errors |
| Analytics | mixpanel-browser | ^2.80.0 | User analytics |

### Testing

| Componente | Tecnologia | Versao | Uso |
|------------|------------|--------|-----|
| Unit tests | Jest | ^29.7.0 | Component + hook tests |
| DOM testing | @testing-library/react | ^14.1.2 | React component testing |
| DOM matchers | @testing-library/jest-dom | ^6.1.5 | Custom DOM matchers |
| User events | @testing-library/user-event | ^14.5.1 | User event simulation |
| E2E tests | @playwright/test | ^1.60.0 | Browser automation |
| Accessibility | @axe-core/playwright | ^4.11.3 | a11y testing |
| Visual regression | @chromatic-com/playwright | ^0.14.8 | Chromatic integration |
| Transpiler | @swc/core + @swc/jest | ^1.15.41 / ^0.2.29 | Fast TypeScript compilation |
| Lighthouse | @lhci/cli | ^0.15.0 | Performance auditing |
| Bundle size | size-limit + @size-limit/file | ^11.2.0 | Bundle size control |
| Codegen | openapi-typescript | ^7.13.0 | OpenAPI -> TS types |
| Sitemap | next-sitemap | ^4.2.3 | Sitemap generation |
| Storybook | storybook + addons | ^8.6.14 | Component documentation |

---

## Infrastructure

| Componente | Servico | Uso |
|------------|---------|-----|
| Backend (web) | Railway | FastAPI server (PROCESS_TYPE=web) |
| Backend (worker) | Railway | ARQ job processor (PROCESS_TYPE=worker) |
| Frontend | Railway | Next.js SSR |
| Database | Supabase Cloud | PostgreSQL + Auth + RLS + Storage |
| Cache / Queue | Redis (Upstash/Railway) | InMemory L1, circuit breaker, ARQ |
| CI/CD | GitHub Actions | Tests + E2E + deploy |
| DNS | Cloudflare (or similar) | smartlic.tech domain |
| Payments | Stripe | Subscriptions, invoices, webhooks |
| Email | Resend | Transactional email delivery |
| Error tracking | Sentry | Backend + Frontend error monitoring |
| Metrics | Prometheus + Grafana | /metrics endpoint, dashboards |
| Tracing | OpenTelemetry (OTLP) | Distributed tracing |

## External APIs

| Servico | Endpoint | Prioridade | Auth |
|---------|----------|------------|------|
| PNCP | `pncp.gov.br/api/consulta/v1/contratacoes/publicacao` | 1 (primary) | None |
| PCP v2 | `compras.api.portaldecompraspublicas.com.br/v2/licitacao/processos` | 2 | None (public) |
| ComprasGov v3 | `dadosabertos.compras.gov.br` | 3 | None |
| OpenAI | `api.openai.com` | N/A | API Key |
| Stripe | `api.stripe.com` | N/A | Secret Key |
| Resend | `api.resend.com` | N/A | API Key |
| Google OAuth | `accounts.google.com` | N/A | Client ID/Secret |
