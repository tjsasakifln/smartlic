# Guia de Setup — SmartLic

**Objetivo:** Novo desenvolvedor roda o sistema localmente em menos de 30 minutos.

## 1. Pré-requisitos

| Ferramenta | Versão Mínima | Verificar |
|-----------|:---:|---|
| **Python** | 3.12+ | `python --version` |
| **Node.js** | 18+ | `node --version` |
| **Git** | 2.40+ | `git --version` |
| **Supabase CLI** | 1.150+ | `npx supabase --version` |
| **Redis** | 7.x | `redis-cli ping` (ou usar Upstash free tier) |

### 1.1 Instalar Supabase CLI

```bash
npm install -g supabase
```

### 1.2 Instalar Railway CLI (opcional, para deploy)

```bash
npm install -g @railway/cli
```

## 2. Clone e Configuração

### 2.1 Clonar Repositório

```bash
git clone https://github.com/tjsasakifln/SmartLic.git
cd SmartLic
```

### 2.2 Criar .env

```bash
cp .env.example .env
```

Editar `.env` e preencher as variáveis obrigatórias:

```ini
# Obrigatórias
OPENAI_API_KEY=sk-...          # https://platform.openai.com/api-keys
SUPABASE_URL=https://...       # Criar projeto gratuito em https://supabase.com
SUPABASE_ANON_KEY=eyJhbG...   # Supabase Dashboard → Settings → API
SUPABASE_SERVICE_KEY=eyJh...  # Supabase Dashboard → Settings → API

# Recomendadas
REDIS_URL=redis://...          # Upstash free tier ou Redis local
STRIPE_SECRET_KEY=sk_test_...  # https://dashboard.stripe.com/test/apikeys
STRIPE_WEBHOOK_SECRET=whsec_...# Stripe Dashboard → Developers → Webhooks
RESEND_API_KEY=re_...          # https://resend.com/api-keys
```

## 3. Backend (FastAPI)

### 3.1 Instalar Dependências

```bash
cd backend
python -m venv venv
source venv/bin/activate    # Linux/macOS
# venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### 3.2 Rodar Migrations Supabase

```bash
# Linkar projeto Supabase (apenas na primeira vez)
npx supabase link --project-ref <SEU_PROJECT_REF>

# Aplicar migrations
npx supabase db push
```

### 3.3 Iniciar Servidor

```bash
uvicorn main:app --reload --port 8000
```

Verificar: `http://localhost:8000/api/v1/health` deve retornar `{"status": "ok"}`

### 3.4 Rodar Worker (ARQ)

Em outro terminal:

```bash
cd backend
source venv/bin/activate
arq worker.WorkerSettings
```

## 4. Frontend (Next.js)

### 4.1 Instalar Dependências

```bash
cd frontend
npm install
```

### 4.2 Iniciar Servidor

```bash
npm run dev
```

Verificar: `http://localhost:3000` deve mostrar a página de login.

### 4.3 Compilar para Produção (teste local)

```bash
npm run build && npm start
```

## 5. Verificação Final

Com backend (porta 8000) e frontend (porta 3000) rodando:

| Teste | URL Esperada | Resultado |
|-------|-------------|-----------|
| Health Check | `http://localhost:8000/api/v1/health` | `{"status": "ok"}` |
| API Docs | `http://localhost:8000/api/v1/docs` | Swagger UI |
| Frontend | `http://localhost:3000` | Tela de login |
| Login | Login com email/senha | Redireciona para /buscar |
| Busca | Buscar "construção" | Resultados em tela |
| Pipeline | `/pipeline` | Kanban com colunas |

## 6. Problemas Comuns

### 6.1 `ModuleNotFoundError: No module named 'xxx'`

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### 6.2 Supabase connection refused

- Verificar se `SUPABASE_URL` está correto no `.env`
- Verificar se o projeto Supabase está ativo (free tier pausa após inatividade)
- Verificar IP allowlist no Supabase Dashboard

### 6.3 Redis connection refused

- Redis local: `redis-server` para iniciar
- Upstash: verificar `REDIS_URL` no `.env`
- Alternativa: desabilitar Redis para dev local (funcionalidade degradada)

### 6.4 OpenAI rate limit

- Free tier tem limite baixo; usar chave paga para desenvolvimento ativo
- Ajustar `LLM_RATE_LIMIT` no `.env`

### 6.5 Port already in use

```bash
# Linux/macOS
lsof -i :8000
kill -9 <PID>

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## 7. Setup Opcional

### 7.1 Stripe Webhook Local

```bash
stripe listen --forward-to localhost:8000/api/v1/stripe/webhook
stripe trigger payment_intent.succeeded
```

### 7.2 Sentry Local (debug)

Configurar `SENTRY_DSN` no `.env` para ver erros no dashboard do Sentry.

### 7.3 Mixpanel Local (debug)

Configurar `MIXPANEL_TOKEN` para tracking de eventos em desenvolvimento.

## 8. Referências

- [CLAUDE.md](../../CLAUDE.md) — Guia completo do projeto e regras de desenvolvimento
- [Documentação de Arquitetura](../architecture/overview.md)
- [Convenções de Código](./conventions.md)
- [API Versioning](../architecture/api-versioning.md)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
