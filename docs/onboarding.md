# Onboarding para Desenvolvedores -- SmartLic

Guia de inicio rapido para desenvolvedores que ingressam no projeto SmartLic.
Plataforma de inteligencia em licitacoes publicas que automatiza a descoberta,
analise e qualificacao de oportunidades para empresas B2G.

> **Producao:** v0.5 -- beta com trials pagos, pre-revenue (runway-critical)
> **Live:** https://smartlic.tech

---

## Indice

- [Pre-requisitos](#pre-requisitos)
- [Setup Inicial](#setup-inicial)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Comandos Essenciais](#comandos-essenciais)
- [Fluxo de Desenvolvimento](#fluxo-de-desenvolvimento)
- [Onde Encontrar Docs Adicionais](#onde-encontrar-docs-adicionais)

---

## Pre-requisitos

| Ferramenta | Versao Minima | Por que |
|------------|---------------|---------|
| Python | 3.12 | Backend (FastAPI, Pydantic, httpx, OpenAI SDK) |
| Node.js | 18+ | Frontend (Next.js 16, React 18) |
| npm | 9+ | Gerenciamento de pacotes do frontend |
| Git | 2.40+ | Controle de versao |
| Supabase CLI | latest | Migracoes e gerenciamento do banco |
| Railway CLI | latest | Deploy (ja autenticado como tiago.sasaki@gmail.com) |
| Docker | 24+ | Opcional -- ambientes isolados para workers |

### Variaveis de Ambiente Requeridas

As seguintes chaves sao obrigatorias para rodar o projeto localmente:

- `OPENAI_API_KEY` -- classificacao LLM + sumarios executivos
- `SUPABASE_URL` + `SUPABASE_ANON_KEY` + `SUPABASE_SERVICE_ROLE_KEY` -- banco e auth
- `RESEND_API_KEY` -- email transacional
- `SENTRY_DSN` -- error tracking (opcional em dev)

Copie `.env.example` para `.env` e preencha os valores.

---

## Setup Inicial

### 1. Clone

```bash
git clone https://github.com/tjsasakifln/SmartLic.git
cd SmartLic
```

### 2. Configuracao de Ambiente

```bash
cp .env.example .env
# Edite .env com suas chaves reais
```

### 3. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Frontend

```bash
cd frontend
npm install
```

### 5. Rodar Localmente

**Terminal 1 -- Backend:**

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

O backend sera iniciado em http://localhost:8000. A documentacao interativa
OpenAPI estara em http://localhost:8000/docs.

**Terminal 2 -- Frontend:**

```bash
cd frontend
npm run dev
```

O frontend sera iniciado em http://localhost:3000.

### 6. Verificar Saudacao

- Health check: `curl http://localhost:8000/health/live`
- OpenAPI schema: `curl http://localhost:8000/openapi.json`

---

## Estrutura do Projeto

```
SmartLic/
├── backend/                    # FastAPI (Python 3.12)
│   ├── main.py                 # App factory (< 30 LOC)
│   ├── config.py               # Config via env vars
│   ├── startup/                # Bootstrap (routes, lifespan, middleware)
│   ├── schemas/                # Pydantic models (88 classes)
│   ├── routes/                 # 71 routers, 187 endpoints
│   ├── filter/                 # Classificacao por keywords + LLM
│   ├── llm_arbiter/            # Classificador GPT-4.1-nano
│   ├── pipeline/               # Pipeline de busca (7-stage state machine)
│   ├── ingestion/              # ETL: PNCP, PCP, ComprasGov
│   ├── cache/                  # L1 InMemory + L2 Redis + L3 Supabase
│   ├── jobs/                   # ARQ queue + cron jobs
│   ├── webhooks/               # Stripe + Resend webhooks
│   ├── routes/search.py        # POST /buscar (SSE async)
│   ├── datalake_query.py       # Full-text search no PostgreSQL
│   └── tests/                  # 454 arquivos, 5131+ testes
│
├── frontend/                   # Next.js 16 (React 18, TypeScript)
│   ├── app/                    # Pages (25 core + 10k+ SEO programmatic)
│   │   ├── buscar/             # Pagina principal de busca
│   │   ├── pipeline/           # Kanban de oportunidades
│   │   ├── dashboard/          # Painel pessoal
│   │   ├── historico/          # Historico de buscas
│   │   ├── conta/              # Configuracoes da conta
│   │   └── observatorio/       # Paginas SEO programmatic
│   ├── components/             # ~72 componentes compartilhados
│   ├── app/api/                # Next.js route handlers (proxies)
│   ├── app/api-types.generated.ts  # Tipos auto-gerados do OpenAPI
│   └── tests/                  # 376 arquivos, 2681+ testes
│
├── supabase/
│   └── migrations/             # 183+ migracoes (source of truth)
│
├── docs/                       # Documentacao do projeto
│   ├── architecture/           # ADRs, arquitetura, decisoes tecnicas
│   ├── security/               # Politicas de seguranca, rotacao
│   └── stories/                # Historias de desenvolvimento
│
├── .claude/
│   └── rules/                  # Regras contextuais para IA
│
├── CLAUDE.md                   # Instrucoes do projeto para Claude Code
├── PRD.md                      # Product Requirements Document
├── ROADMAP.md                  # Roadmap e backlog
└── CHANGELOG.md                # Historico de versoes
```

### Modulos do Backend (18 funcionais)

| Categoria | Modulos | Proposito |
|-----------|---------|-----------|
| Entry | `main.py`, `startup/`, `config.py` | Bootstrap, rotas, lifespan |
| Schemas | `schemas/` | Contratos Pydantic -> OpenAPI -> TypeScript |
| Search Pipeline | `search_pipeline.py`, `pipeline/`, `consolidation/` | State machine 7-stage, time budget waterfall |
| Ingestion | `ingestion/`, `datalake_query.py` | ETL diario (~10k tendencias/dia) |
| Filter/LLM | `filter/`, `llm_arbiter/`, `llm.py` | Classificacao 20 setores, precisao >= 85% |
| Cache | `cache/`, `redis_pool.py`, `search_cache.py` | SWR reativo, L1/L2/L3 |
| Auth | `auth.py`, `authorization.py` | JWT 3-estrategias, RLS |
| Billing | `services/billing.py`, `quota/`, `webhooks/stripe.py` | Stripe, 9 planos, quota atomica |
| Pipeline Kanban | `routes/pipeline.py` | CRUD 5-estagios com optimistic locking |
| Jobs/Cron | `jobs/queue/`, `jobs/cron/` | ARQ worker + 9 schedules cron |
| Routes | `routes/` (71 arquivos) | 187 endpoints |
| Exports | `excel.py`, `google_sheets.py`, `pdf_generator_edital.py` | Excel, PDF, Google Sheets |
| SEO | `routes/*_publicos.py`, `routes/observatorio.py` | 18 routers publicos, 10k+ paginas |
| Observability | `metrics.py`, `telemetry.py`, `health.py` | Prometheus, Sentry, OpenTelemetry |

---

## Comandos Essenciais

### Backend

```bash
# Desenvolvimento
cd backend && uvicorn main:app --reload --port 8000

# Testes (especifico -- rapido, preferencial)
pytest -k "test_name"

# Testes (arquivo unico -- seguro)
pytest tests/test_foo.py

# Suite completa (Linux CI)
pytest --timeout=30

# Suite completa (Windows -- isolamento por subprocess)
python scripts/run_tests_safe.py
python scripts/run_tests_safe.py --parallel 4

# Cobertura
pytest --cov

# Lint
ruff check . && mypy .

# Testes de integracao
pytest tests/integration/
```

### Frontend

```bash
# Desenvolvimento
cd frontend && npm run dev

# Testes
npm test                        # Todos (devem passar 100%)
npm run test:coverage           # Cobertura (threshold: 60%)
npm run test:ci                 # Modo CI
npm run lint

# Build producao
npm run build && npm start

# E2E (Playwright)
npm run test:e2e                # Headless
npm run test:e2e:headed         # Modo debug

# Sincronizar tipos do OpenAPI
npm run generate:api-types
```

### Banco de Dados (Supabase)

```bash
# Listar projetos
npx supabase projects list

# Aplicar migracoes
npx supabase db push

# Pull do schema remoto
npx supabase db pull

# Ver diff
npx supabase db diff

# Criar nova migracao
npx supabase migration new <nome>
```

### Deploy (Railway)

```bash
# Status
railway status

# Logs
railway logs --tail

# Deploy (SEMPRE da raiz do projeto, nunca de backend/ ou frontend/)
railway up

# Redeploy de emergencia
railway redeploy --service bidiq-backend -y
```

---

## Fluxo de Desenvolvimento

### Branch Strategy

- **`main`** -- producao (deploy automatico via GitHub Actions + Railway)
- **`feature/*`** -- novas funcionalidades
- **`fix/*`** -- correcoes de bugs

### Ciclo de Tarefa

1. **Criar branch:** `git checkout -b feature/meu-issue`
2. **Desenvolver:** Seguir story-driven development (stories em `docs/stories/`)
3. **Validar localmente:** Rodar pre-push gates
4. **Commit:** Usar conventional commits (`feat:`, `fix:`, `docs:`, `chore:`)
5. **Push:** `git push origin minha-branch`
6. **PR:** Criar Pull Request via `gh pr create`
7. **CI:** GitHub Actions valida lint + testes + build
8. **Merge para `main`:** Deploy automatico

### Pre-Push Gates (OBRIGATORIO)

Antes de qualquer commit/push, execute a validacao correspondente ao tipo de
alteracao. O hook `.claude/hooks/pre-push-gate.cjs` bloqueia commits sem
validacao recente.

| Alteracao | Comando |
|-----------|---------|
| `backend/**` | `cd backend && ruff check . && pytest tests/ -m "not benchmark and not external" --ignore=tests/fuzz --ignore=tests/integration --cov=. --cov-fail-under=71 -v && python scripts/check_module_coverage.py` |
| `frontend/**` | `cd frontend && npx tsc --noEmit --pretty && npm test -- --coverage --ci --no-cache && npm run build` |
| `supabase/migrations/**` | `cd backend && pytest tests/ -k "migration" -v` |
| Ambos | Ambos os comandos acima |
| Apenas docs | Toque `.claude/.pre-push-passed` |

### CI/CD

- **GitHub Actions:** Testes backend + frontend + CodeQL + validacao API types
- **Railway:** Deploy automatico ao fazer merge em `main`
- **Monitoramento:** Sentry (erros), Prometheus (metricas), Mixpanel (analytics)

---

## Onde Encontrar Docs Adicionais

### Referencias Tecnicas

| Documento | Localizacao | Conteudo |
|-----------|-------------|----------|
| Architecture Patterns | `.claude/rules/architecture-patterns.md` | 3-layer data architecture, LLM classification, SSE, cache |
| Architecture Detail | `.claude/rules/architecture-detail.md` | Module map, 187 endpoints, frontend pages |
| Critical Impl Notes | `.claude/rules/critical-impl-notes.md` | Ingestion, PNCP quirks, Railway history, time budgets |
| Dev Recipes | `.claude/rules/dev-recipes.md` | Step-by-step para tarefas recorrentes |
| Testing Strategy | `.claude/rules/testing-strategy.md` | Padroes de teste, mocks, anti-hang rules |
| AIOS Framework | `.claude/rules/aios-framework.md` | AI-orchestrated development framework |

### Documentacao do Projeto

| Documento | Localizacao | Conteudo |
|-----------|-------------|----------|
| README | `README.md` | Visao geral, metricas, stack, status |
| CASE STUDY | `CASE_STUDY.md` | Narrativa de engenharia completa |
| PRD | `PRD.md` | Product Requirements Document |
| Roadmap | `ROADMAP.md` | Backlog e status |
| CHANGELOG | `CHANGELOG.md` | Historico de versoes |
| Deployment | `docs/DEPLOYMENT.md` | Railway, Supabase, CI/CD |
| System Architecture | `docs/architecture/system-architecture.md` | C4 diagrams, ADRs, ERD |
| AI Pipeline | `docs/ai-pipeline.md` | Pipeline de classificacao IA |
| API Versioning | `docs/architecture/api-versioning.md` | Politica de versionamento |
| Secret Rotation | `docs/security/secret-rotation.md` | Procedimentos de rotacao de secrets |
| Founders Policy | `docs/founders-policy.md` | Politicas do produto |
| GTM Playbook | `docs/summaries/gtm-resilience-summary.md` | Estrategia Go-to-Market |

### Codigo Fonte

- `CLAUDE.md` -- Instrucoes para Claude Code (tech stack, dev commands, architecture)
- `.claude/rules/` -- Regras contextuais carregadas automaticamente
- `backend/startup/routes.py` -- Registro de todas as rotas da API
- `backend/sectors_data.yaml` -- Definicao dos 20 setores
- `backend/config.py` -- Todas as configuracoes via env vars

### Ferramentas Externas

| Ferramenta | URL | Uso |
|------------|-----|-----|
| Sentry | https://confenge.sentry.io/ | Error tracking |
| Railway | https://railway.app/ | Infraestrutura |
| Supabase | https://supabase.com/ | Banco + Auth |
| Stripe | https://dashboard.stripe.com/ | Billing |
| Mixpanel | https://mixpanel.com/ | Analytics |
| Resend | https://resend.com/ | Email |
