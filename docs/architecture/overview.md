# Visão Geral da Arquitetura — SmartLic

**Última atualização:** 2026-06-15

## 1. Diagrama C4 — Nível 1 (System Context)

```
┌──────────────────────────────────────────────────────────────────┐
│                        Usuário B2G                                │
│              (Empresa que vende para governo)                     │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTPS (navegador)
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     SmartLic Platform                              │
│                 https://smartlic.tech                              │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │  Frontend     │  │  Backend      │  │  Worker (ARQ)        │   │
│  │  Next.js 16.1 │  │  FastAPI 0.136│  │  Jobs + Sumários     │   │
│  │  Railway      │──│  Railway      │──│  Railway             │   │
│  └──────────────┘  └──────┬───────┘  └──────────┬───────────┘   │
│                            │                      │               │
└────────────────────────────┼──────────────────────┼───────────────┘
                             │                      │
              ┌──────────────┼──────────────────────┼───────────────┐
              │              ▼                      ▼               │
              │  ┌──────────────┐  ┌──────────────┐                │
              │  │  Supabase     │  │  Redis        │                │
              │  │  PostgreSQL 17│  │  Upstash/Rail │                │
              │  │  + Auth + RLS │  │  Cache+Queue  │                │
              │  └──────────────┘  └──────────────┘                │
              │         Cloud Services                              │
              └─────────────────────────────────────────────────────┘

┌──────────────────────────┐    ┌──────────────────────────┐
│  Fontes de Dados          │    │  Serviços Externos        │
│                           │    │                           │
│  • PNCP API (gov.br)      │    │  • OpenAI (GPT-4.1-nano)  │
│  • PCP v2 API             │    │  • Stripe (billing)       │
│  • ComprasGov v3           │    │  • Resend (email)         │
│                           │    │  • Sentry (errors)         │
│                           │    │  • Mixpanel (analytics)    │
└──────────────────────────┘    └──────────────────────────┘
```

## 2. Stack Tecnológica

### 2.1 Backend

| Componente | Tecnologia | Versão | Função |
|-----------|-----------|:---:|--------|
| Framework | FastAPI | 0.137 | API REST + SSE |
| Runtime | Python | 3.12 | Linguagem |
| Validação | Pydantic | 2.13 | Schemas e tipos |
| HTTP Client | httpx | — | Chamadas externas |
| IA | OpenAI SDK | 1.109 | GPT-4.1-nano |
| Database | Supabase | — | PostgreSQL 17 + Auth + RLS |
| Cache | Redis | — | L1 cache, SSE state, rate limiter |
| Queue | ARQ | 0.26+ | Jobs assíncronos |
| Billing | Stripe | 11.6 | Pagamentos (12 webhook events) |
| Email | Resend | — | Email transacional |
| PDF | ReportLab | — | Geração de PDF |
| Excel | openpyxl | — | Geração de Excel |
| YAML | PyYAML | — | Configuração de setores |
| Logging | Sentry | — | Error tracking |
| Métricas | Prometheus + OT | — | Observabilidade |

### 2.2 Frontend

| Componente | Tecnologia | Versão | Função |
|-----------|-----------|:---:|--------|
| Framework | Next.js | 16.1 | SSR + ISR + API routes |
| UI | React | 18.3 | Componentes |
| Linguagem | TypeScript | 5.9 | Tipagem |
| Estilo | Tailwind CSS | 3.4 | Utility-first CSS |
| Animação | Framer Motion | — | Animações |
| Gráficos | Recharts | — | Charts interativos |
| Drag-drop | @dnd-kit | — | Pipeline kanban |
| Tour | Shepherd.js | — | Onboarding |
| Auth | Supabase SSR | — | Autenticação |
| Analytics | Mixpanel | — | Event tracking |
| Error | Sentry | — | Error tracking |

### 2.3 Infraestrutura

| Componente | Provedor | Função |
|-----------|----------|--------|
| Hospedagem | Railway | Web + Worker + Frontend |
| Database | Supabase Cloud | PostgreSQL 17 |
| Cache/Queue | Upstash / Railway Redis | Redis |
| CI/CD | GitHub Actions | Build + Deploy |
| Monitoramento | Sentry + Prometheus | Errors + Métricas |

## 3. Fluxo de Dados Principal

### 3.1 Pipeline de Busca

```
Usuário faz busca
       │
       ▼
┌──────────────────┐
│  POST /buscar     │  ← Frontend envia termo + filtros
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Search Pipeline  │  ← Pipeline de 5 estágios
│                   │
│  1. Parse params  │  ← Validar termo, UF, modalidade
│  2. DataLake query│  ← Consultar pncp_raw_bids (1.5M rows)
│  3. Dedup 5 camadas│ ← Remover duplicatas entre fontes
│  4. LLM classify  │  ← GPT-4.1-nano classifica relevância
│  5. Viability     │  ← Calcular score de viabilidade
│  6. Cache & return│  ← Cache L1 (Redis 4h) + L2 (Supabase 24h)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  SSE Stream       │  ← Resultados chegam via Server-Sent Events
│  (Frontend)       │     atualização progressiva no frontend
└──────────────────┘
```

### 3.2 Pipeline de Ingestão (Background)

```
┌──────────────────┐
│  ARQ Scheduler    │  ← Agenda jobs recorrentes (pg_cron)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Ingestion Job    │  ← 27 UFs × 6 modalidades = 162 consultas
│                   │
│  1. Fetch PNCP    │  ← API pública, tamanhoPagina=50
│  2. Fetch PCP v2  │  ← API pública, sem auth
│  3. Fetch Gov v3  │  ← Dados abertos, dual-endpoint
│  4. Transform     │  ← Normalizar schema comum
│  5. Dedup         │  ← Remover sobreposição entre fontes
│  6. Load datalake │  ← Inserir no pncp_raw_bids
│  7. Checkpoint    │  ← Salvar progresso (retry em falha)
└──────────────────┘
       │
       ▼
┌──────────────────┐
│  Retention        │  ← 400 dias de histórico
│  (pg_cron)        │     limpeza automática diária
└──────────────────┘
```

## 4. Serviços e Integrações

### 4.1 APIs Externas

| Serviço | Endpoint | Auth | Rate Limit |
|---------|----------|------|-----------|
| **PNCP** | `https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao` | Pública | ~30 req/min |
| **PCP v2** | `https://compras.api.portaldecompraspublicas.com.br/v2/licitacao/processos` | Pública | ~60 req/min |
| **ComprasGov v3** | `https://dadosabertos.compras.gov.br` | Pública | ~60 req/min |
| **OpenAI** | `https://api.openai.com/v1/chat/completions` | API Key | Tier-based |
| **Stripe** | `https://api.stripe.com/v1/` | Secret Key | N/A |
| **Resend** | `https://api.resend.com/emails` | API Key | 100/dia (free) |

### 4.2 Webhooks Recebidos

| Fonte | Endpoint | Eventos |
|-------|----------|---------|
| **Stripe** | `POST /api/v1/stripe/webhook` | 12 eventos (checkout, subscription, invoice, payment) |

## 5. Modelo de Dados (Simplificado)

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  users            │     │  searches         │     │  opportunities   │
│  (Supabase Auth)  │────▶│  (buscas salvas)  │────▶│  (pipeline)      │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                                                                │
┌──────────────────┐     ┌──────────────────┐                  │
│  subscriptions    │     │  pncp_raw_bids    │                  │
│  (Stripe)         │     │  (datalake)       │◀─────────────────┘
└──────────────────┘     └──────────────────┘
```

## 6. Segurança

- **Autenticação:** Supabase Auth (JWT)
- **Autorização:** Row Level Security (RLS) em todas as tabelas
- **Rate Limiting:** Redis token bucket por IP + user
- **Validação:** Pydantic schemas em todas as entradas
- **Log:** Sanitização de dados sensíveis (log_sanitizer.py)
- **CORS:** Configurável via `CORS_ORIGINS`
- **Admin:** Rotas admin requerem `is_admin` ou `is_master`
- **Content-Security-Policy (Issue #1913):**
  - Backend: `default-src 'none'` com `report-uri /v1/csp-report` para todas as respostas
  - Frontend: CSP completa com `default-src 'self'`, whitelists para Stripe/Sentry/Supabase/Mixpanel/Cloudflare
  - Controle: `CSP_ENFORCE_MODE` env var — `true` envia `Content-Security-Policy` (enforce), `false` envia `Content-Security-Policy-Report-Only`
  - Violações coletadas via `POST /v1/csp-report` (backend) e `/api/csp-report` (frontend proxy)
  - Report-To header configurado para Reporting API v1 com grupo `csp-endpoint`
  - Rate limit: 30 reports/min/IP (backend), 100 reports/min/IP (frontend)

## 7. Referências

- [CLAUDE.md](../../CLAUDE.md) — Guia completo de desenvolvimento
- [Documentação de Setup](../development/setup.md)
- [Convenções de Código](../development/conventions.md)
- [API Versioning](./api-versioning.md)
- [Runbook de Incidentes](../runbooks/incident-response.md)
- [_reversa_sdd/architecture.md](../../_reversa_sdd/architecture.md) — C4 L1/L2/L3 (Reversa)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
