# Paridade de Ambientes — Staging ≡ Produção

**Issue:** [#1812](https://github.com/tjsasakifln/SmartLic/issues/1812)
**Prioridade:** P1
**Status:** Plano documentado — provisionamento pendente
**Data:** 2026-06-15

## 1. Objetivo

Garantir que o ambiente de staging seja estruturalmente idêntico ao de produção, eliminando a classe de bugs "funciona no meu ambiente / staging" que só se manifestam em produção.

## 2. Arquitetura de Ambientes

### 2.1 Ambientes Atuais (Railway)

| Ambiente | Railway Environment | Branch | Uso |
|----------|-------------------|--------|-----|
| **Produção** | `production` | `main` | Tráfego real de usuários |
| **Staging** | `staging` (a criar) | `main` (pre-deploy) | Validação pré-produção |
| **PR Preview** | N/A | Feature branches | Review de PR |

### 2.2 Serviços por Ambiente

| Serviço | Produção | Staging |
|---------|----------|---------|
| **Backend (FastAPI)** | Railway `bidiq-backend` | Railway `bidiq-backend-staging` |
| **Worker (ARQ)** | Railway `bidiq-worker` | Railway `bidiq-worker-staging` |
| **Frontend (Next.js)** | Railway `bidiq-frontend` | Railway `bidiq-frontend-staging` |
| **PostgreSQL** | Supabase Cloud (`fqqyovlzdzimiwfofdjk`) | Supabase Cloud (projeto separado ou branch) |
| **Redis** | Upstash/Railway Redis | Upstash/Railway Redis (instância separada) |

## 3. Infrastructure as Code

### 3.1 railway.toml (Staging)

```toml
# railway.toml — Staging
[build]
builder = "nixpacks"
watch_patterns = ["backend/**"]

[deploy]
num_replicas = 1
sleep_application = false

[service]
healthcheck_path = "/api/v1/health"

[variables]
ENVIRONMENT = "staging"
LOG_LEVEL = "debug"
ENABLE_SENTRY = "false"
```

### 3.2 railway.toml (Produção)

```toml
# railway.toml — Produção
[build]
builder = "nixpacks"
watch_patterns = ["backend/**"]

[deploy]
num_replicas = 2
sleep_application = false

[service]
healthcheck_path = "/api/v1/health"

[variables]
ENVIRONMENT = "production"
LOG_LEVEL = "warning"
ENABLE_SENTRY = "true"
```

## 4. Matriz de Paridade

### 4.1 Versões de Serviços

| Componente | Produção | Staging | Paridade |
|-----------|----------|---------|:---:|
| Python | 3.12.x | 3.12.x | ✅ Deve ser igual |
| FastAPI | 0.136.x | 0.136.x | ✅ Deve ser igual |
| PostgreSQL | 17.x (Supabase) | 17.x (Supabase) | ✅ Deve ser igual |
| Redis | 7.x | 7.x | ✅ Deve ser igual |
| Node.js | 18+ | 18+ | ✅ Deve ser igual |
| Next.js | 16.1.x | 16.1.x | ✅ Deve ser igual |

### 4.2 Variáveis de Ambiente

| Variável | Produção | Staging | Notas |
|----------|----------|---------|-------|
| `DATABASE_URL` | Supabase prod | Supabase staging | Diferente (esperado) |
| `REDIS_URL` | Redis prod | Redis staging | Diferente (esperado) |
| `OPENAI_API_KEY` | Chave prod | Chave staging/test | Diferente (esperado) |
| `STRIPE_SECRET_KEY` | Chave live | Chave test (`sk_test_`) | Diferente (obrigatório) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_` prod | `whsec_` test | Diferente (obrigatório) |
| `SUPABASE_URL` | URL prod | URL staging | Diferente (esperado) |
| `SUPABASE_SERVICE_KEY` | Key prod | Key staging | Diferente (esperado) |
| `SENTRY_DSN` | DSN prod | DSN staging ou vazio | Diferente (esperado) |
| `MIXPANEL_TOKEN` | Token prod | Token test ou vazio | Diferente (esperado) |
| `RESEND_API_KEY` | Key prod | Key test | Diferente (esperado) |
| `LOG_LEVEL` | `warning` | `debug` | Diferente intencional |
| `ENVIRONMENT` | `production` | `staging` | Diferente intencional |
| `CORS_ORIGINS` | `https://smartlic.tech` | `https://staging.smartlic.tech` | Diferente (esperado) |

## 5. Estratégia de Sanitização de Dados

### 5.1 Regras para Staging

Staging **NUNCA** usa cópia do banco de produção. Em vez disso:

1. **Seed data:** Script `supabase/seed.sql` com dados de teste realistas mas anônimos
2. **Usuários de teste:** Emails `@example.com` ou `@test.smartlic.tech`
3. **Stripe:** Modo teste sempre (`sk_test_`), sem cartões reais
4. **Emails (Resend):** Modo sandbox ou email domain de teste
5. **Mixpanel:** Token de test project ou desabilitado
6. **OpenAI:** Usar chave com limite de gastos baixo para staging

### 5.2 Script de Seed

```bash
# Popular staging com dados de teste
npx supabase db reset --linked --db-url "$STAGING_DB_URL"
```

## 6. Pipeline de Promoção CI

### 6.1 Fluxo

```
Feature Branch → PR → Staging Deploy → Smoke Tests → Merge → Produção Deploy
```

### 6.2 GitHub Actions Workflow

```yaml
name: Deploy Pipeline
on:
  push:
    branches: [main]
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  staging-deploy:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Staging
        run: railway up --environment staging --service bidiq-backend
      - name: Smoke Tests
        run: npm --prefix frontend run test:e2e
        env:
          BASE_URL: https://staging.smartlic.tech

  production-deploy:
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    needs: []  # Não depende de staging (deploy direto com rollback disponível)
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Production
        run: railway up --environment production --service bidiq-backend
```

## 7. Verificação de Paridade

### 7.1 Script Automatizado

Executar `scripts/check-parity.sh` (ou `.ps1` no Windows) periodicamente (semanal) para detectar drift:

```bash
./scripts/check-parity.sh
```

O script compara:
- Versão do PostgreSQL (produção vs staging)
- Versão do Redis
- Plano Railway (recursos alocados)
- Variáveis de ambiente (nomes, não valores)
- Extensões PostgreSQL instaladas

### 7.2 CI Gate

Incluir no workflow semanal (Sunday 03:00 UTC):
- Executa `check-parity.sh`
- Alerta se diferenças encontradas (Slack/email)
- Bloqueia deploy se diferenças críticas

## 8. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|:---:|:---:|-----------|
| Custo extra do staging | Média | Baixo | Railway fatura por uso; staging com 1 replica |
| Staging ficar desatualizado | Alta | Médio | Script `check-parity.sh` semanal |
| Vazamento de dados produção no staging | Baixa | Crítico | Staging NUNCA toca banco de produção |
| Testes de carga no staging afetarem produção | Baixa | Alto | Recursos isolados; Redis/DB separados |

## 9. Referências

- [Railway Environments](https://docs.railway.com/reference/environments)
- [12-Factor App — Dev/Prod Parity](https://12factor.net/dev-prod-parity)
- [Supabase Database Branching](https://supabase.com/docs/guides/platform/branching)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
