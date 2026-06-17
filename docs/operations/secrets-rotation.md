# Secrets Rotation — Procedimento e Automacao

**Issue:** #1915
**Responsavel:** @devops
**Periodicidade:** Trimestral (90 dias)
**Ultima revisao:** 2026-06-16

---

## 1. Visao Geral

Este documento consolida o inventario, procedimentos e automacao para rotacao de
secrets/credenciais da plataforma SmartLic. Substitui e expande:

- `docs/runbooks/secret-rotation.md` (runbook operacional — manter como referencia rapida)
- `docs/security/secret-rotation.md` (documento de seguranca — manter como referencia)
- `docs/security/credentials-inventory.md` (inventario completo)

### 1.1 Arquitetura da Automacao

```
scripts/rotate-secrets.sh          ← Script principal (dry-run + rollback + audit)
.secrets-backup/last-rotation.json ← Tracker versionado (apenas datas)
.secrets-backup/*.env               ← Backups de valores (gitignorados — NAO commitar)
.secrets-backup/rotation-audit.log  ← Audit trail de todas as rotacoes
.github/workflows/secret-age-check.yml ← CI gate mensal
```

### 1.2 Pre-requisitos

```bash
# CLI tools necessarias
curl --version         # >= 7.68
jq --version           # >= 1.6
openssl version        # >= 1.1
railway --version      # Autenticado como tiago.sasaki@gmail.com

# Smoke test endpoint (padrao: https://api.smartlic.tech/health/ready)
export SMOKE_TEST_URL="https://api.smartlic.tech/health/ready"
```

---

## 2. Inventario de Secrets

Secrets sao classificados por metodo de rotacao, criticidade e servico Railway.

### 2.1 Auto-Generated (gerados localmente via script)

| Secret | Railway Service | Rotacao | Geracao |
|--------|----------------|---------|---------|
| `REVALIDATE_SECRET` | backend + frontend | `openssl rand -hex 32` | Automatica |
| `LGPD_DELETION_SECRET` | backend | `openssl rand -hex 32` | Automatica |

### 2.2 Manual (criados via provider dashboard)

| Secret | Railway Service | Criticidade | Provider URL |
|--------|----------------|-------------|-------------|
| `OPENAI_API_KEY` | backend | ALTO | https://platform.openai.com/api-keys |
| `STRIPE_SECRET_KEY` | backend | CRITICO | https://dashboard.stripe.com/apikeys |
| `STRIPE_WEBHOOK_SECRET` | backend | MEDIO | Stripe Dashboard > Webhooks |
| `SUPABASE_SERVICE_ROLE_KEY` | backend | CRITICO | Supabase Dashboard > API > service_role |
| `SUPABASE_ANON_KEY` | backend + frontend | BAIXO | Supabase Dashboard > API > anon key |
| `SUPABASE_ACCESS_TOKEN` | backend | ALTO | Supabase Dashboard > Access Tokens |
| `SUPABASE_DB_URL` | backend | CRITICO | Supabase Dashboard > Database |
| `RESEND_API_KEY` | backend | MEDIO | https://resend.com/api-keys |
| `TRIAL_EMAILS_WEBHOOK_SECRET` | backend | MEDIO | Resend Dashboard > Webhooks |
| `SENTRY_DSN` | backend (+ frontend) | BAIXO | Sentry Dashboard > Projects |
| `SENTRY_AUTH_TOKEN` | backend | MEDIO | Sentry Dashboard > Auth Tokens |
| `MIXPANEL_SERVICE_ACCOUNT_USERNAME` | backend | BAIXO | Mixpanel Dashboard > Settings |
| `MIXPANEL_SERVICE_ACCOUNT_PASSWORD` | backend | BAIXO | Mixpanel Dashboard > Settings |
| `MIXPANEL_PROJECT_ID` | backend | BAIXO | Mixpanel Dashboard > Settings |
| `RAILWAY_TOKEN` | GitHub Actions | ALTO | Railway Dashboard > Settings > Tokens |
| `REDIS_URL` | backend | ALTO | Railway Redis / Upstash Console |
| `FOUNDING_ONE_TIME_PRICE_ID` | backend | BAIXO | Stripe Dashboard > Products |
| `GITHUB_TOKEN` | GitHub Actions / dev | ALTO | https://github.com/settings/tokens |
| `DEEPSEEK_API_KEY` | backend | MEDIO | https://platform.deepseek.com |
| `OPENROUTER_API_KEY` | backend | BAIXO | https://openrouter.ai/keys |
| `EXA_API_KEY` | backend | BAIXO | https://exa.ai/dashboard |
| `N8N_API_KEY` | backend | BAIXO | N8N Dashboard > Settings |

### 2.3 Matriz de Criticidade

| Nivel | Exemplos | Janela de Rotacao Emergencial |
|-------|----------|------------------------------|
| **CRITICO** | `STRIPE_SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`, `RAILWAY_TOKEN` | Imediata (minutos) |
| **ALTO** | `OPENAI_API_KEY`, `SUPABASE_ACCESS_TOKEN`, `GITHUB_TOKEN`, `REDIS_URL` | 1 hora |
| **MEDIO** | `RESEND_API_KEY`, `SENTRY_AUTH_TOKEN`, `STRIPE_WEBHOOK_SECRET` | 4 horas |
| **BAIXO** | `SUPABASE_ANON_KEY`, `SENTRY_DSN`, `MIXPANEL_*` | 24 horas |

---

## 3. Script de Automacao

### 3.1 Uso Basico

```bash
# Listar todos os secrets rastreados
./scripts/rotate-secrets.sh --list

# Verificar idade de todos os secrets
./scripts/rotate-secrets.sh --check

# Dry-run: mostrar o que seria feito (nao altera nada)
./scripts/rotate-secrets.sh REVALIDATE_SECRET --dry-run

# Rotacionar um secret auto-gerado
./scripts/rotate-secrets.sh REVALIDATE_SECRET

# Rotacionar um secret manual (fornecer o valor antecipadamente)
./scripts/rotate-secrets.sh OPENAI_API_KEY --value="sk-proj-..."

# Rotacionar com valor via env var (non-interactive)
ROTATE_OPENAI_API_KEY="sk-proj-..." ./scripts/rotate-secrets.sh OPENAI_API_KEY

# Rollback para o valor anterior
./scripts/rotate-secrets.sh REVALIDATE_SECRET --rollback

# Especificar servico Railway diferente
./scripts/rotate-secrets.sh SUPABASE_ANON_KEY --service bidiq-frontend
```

### 3.2 Fluxo de Execucao

O script executa 6 passos para cada rotacao:

```
Step 1: Backup current value  → .secrets-backup/<SECRET>.env (chmod 600)
Step 2: Obtain new value       → Auto-generate ou leitura de --value / env var / prompt
Step 3: Update Railway         → railway variables set SECRET=VALUE --service <name>
Step 4: Wait for deploy        → Poll railway status ate running
Step 5: Smoke test             → GET /health/ready (HTTP 200)
Step 6: Update tracker         → Atualiza .secrets-backup/last-rotation.json
```

### 3.3 Dry-Run Mode

Usar `--dry-run` para validar o fluxo sem fazer alteracoes:

```bash
./scripts/rotate-secrets.sh REVALIDATE_SECRET --dry-run
```

Saida de exemplo:
```
[DRY-RUN] Would backup current value of REVALIDATE_SECRET to ...
[DRY-RUN] railway variables set REVALIDATE_SECRET=*** --service bidiq-backend
[DRY-RUN] Would wait for deploy of 'bidiq-backend' (timeout: 180s)
[DRY-RUN] Would run smoke test against https://api.smartlic.tech/health/ready
[DRY-RUN] Would update tracker: REVALIDATE_SECRET = 2026-06-16T...
```

### 3.4 Rollback

```bash
# Rollback do ultimo valor de REVALIDATE_SECRET
./scripts/rotate-secrets.sh REVALIDATE_SECRET --rollback
```

O rollback:
1. Le o arquivo `.secrets-backup/<SECRET>.env`
2. Restaura o valor via `railway variables set`
3. Aguarda deploy
4. Executa smoke test
5. Atualiza o tracker

### 3.5 Audit Log

Todas as operacoes sao registradas em `.secrets-backup/rotation-audit.log`:

```
2026-06-16T10:30:00Z | REVALIDATE_SECRET | ROTATE | SUCCESS | Service: bidiq-backend
2026-06-16T10:35:00Z | REVALIDATE_SECRET | ROLLBACK | SUCCESS | Restored from backup
```

---

## 4. Procedimentos por Secret

### 4.1 Auto-Generated: REVALIDATE_SECRET e LGPD_DELETION_SECRET

Estes sao os unicos secrets que podem ser rotacionados 100% via script, sem
intervencao manual em dashboard de terceiros.

```bash
# Rotacao completa (backup + gerar + atualizar + smoke test)
./scripts/rotate-secrets.sh REVALIDATE_SECRET

# Verificar o novo valor no Railway (opcional)
railway variables get REVALIDATE_SECRET --service bidiq-backend
```

### 4.2 Manual: Todos os demais secrets

Para secrets que exigem criacao no dashboard do provedor:

```bash
# 1. (Opcional) Verificar idade atual
./scripts/rotate-secrets.sh --check

# 2. Gerar novo valor no provider dashboard
#    Exemplo: https://platform.openai.com/api-keys

# 3. Rotacionar com o novo valor
./scripts/rotate-secrets.sh OPENAI_API_KEY --value="sk-proj-..."

#    OU via env var (uteis para CI/automacao):
ROTATE_OPENAI_API_KEY="sk-proj-..." ./scripts/rotate-secrets.sh OPENAI_API_KEY
```

**Provedores e seus dashboards:**

| Secret | Acao no Dashboard |
|--------|-------------------|
| `OPENAI_API_KEY` | API Keys > + Create new secret key (modelo: GPT-4.1-nano) |
| `STRIPE_SECRET_KEY` | Developers > API Keys > Roll secret key |
| `STRIPE_WEBHOOK_SECRET` | Developers > Webhooks > Endpoint > Reset signing secret |
| `SUPABASE_SERVICE_ROLE_KEY` | Project Settings > API > service_role key > Regenerate |
| `SUPABASE_ANON_KEY` | Project Settings > API > anon public key > Regenerate |
| `RESEND_API_KEY` | API Keys > Create API Key (domain: smartlic.tech) |
| `SENTRY_AUTH_TOKEN` | Settings > Auth Tokens > Create New (scopes: project:releases, event:read) |

### 4.3 Emergencia: Credencial Comprometida

```bash
# 1. Rotacionar IMEDIATAMENTE (sem dry-run, sem overlap)
./scripts/rotate-secrets.sh STRIPE_SECRET_KEY --value="sk_live_NOVO"

# 2. Verificar uso indevido no dashboard do provedor

# 3. Notificar equipe (criar issue ou alerta)
```

---

## 5. CI Gate: Secret Age Check

### 5.1 Workflow

`.github/workflows/secret-age-check.yml` executa no 1o dia de cada mes (07:00 UTC)
e verifica se todos os secrets foram rotacionados nos ultimos 90 dias.

**Disparo:**
- Schedule: `0 7 1 * *` (1o dia do mes, 07:00 UTC)
- `workflow_dispatch`: manual

**Comportamento:**
- Le `.secrets-backup/last-rotation.json`
- Calcula idade de cada secret
- Se algum > 90 dias: cria GitHub Issue com alerta
- Se aprovacao manual (workflow_dispatch): pode criar issue mesmo com aprovacao

### 5.2 Interpretacao de Falhas

| Resultado | Significado | Acao |
|-----------|-------------|------|
| Todos < 90d | Verde | Nenhuma |
| 1-3 secrets > 90d | Warning | Rotacionar nos proximos 7 dias |
| 4+ secrets > 90d | Issue criada | Rotacao urgente necessaria |
| Tracker nao encontrado | Erro | Executar `--dry-run` para inicializar |

---

## 6. Calendario de Rotacao

### 6.1 Rotacao Trimestral (90 dias)

| Janela | Secrets | Responsavel |
|--------|---------|-------------|
| Q1: 15-31 Jan | Stripe + Supabase + OpenAI + REVALIDATE | @devops |
| Q2: 15-30 Abr | Resend + Sentry + Mixpanel + LGPD | @devops |
| Q3: 15-31 Jul | REDIS + Supabase (re-rotate) + GitHub | @devops |
| Q4: 15-31 Out | Stripe + OpenAI + revisao geral | @devops |

### 6.2 Gatilhos Adicionais

| Evento | Acao |
|--------|------|
| Membro da equipe sai | Rotacionar TODAS as credenciais |
| Breach de terceiro | Rotacionar a credencial afetada IMEDIATAMENTE |
| Commit acidental de secret | Rotacionar IMEDIATAMENTE + investigar janela |
| Pre-lancamento major | Rotacionar tudo 7 dias antes |
| CI gate dispara issue | Rotacionar nos proximos 7 dias |

---

## 7. Smoke Tests Pos-Rotacao

Apos cada rotacao, o script executa automaticamente:

```bash
# 1. Health endpoint
curl -f https://api.smartlic.tech/health/ready

# 2. Teste especifico por servico
#    OpenAI:  Executar busca com ?setor=X e verificar classificacao
#    Stripe:  Verificar webhook de teste
#    Resend:  Enviar email de teste
#    Supabase: Verificar GET /v1/admin/cron-status
```

Testes manuais recomendados apos rotacao:
- [ ] Health check (ready + live) retornam 200
- [ ] Login no frontend funciona
- [ ] Busca basica retorna resultados
- [ ] Sentry sem novos erros de auth
- [ ] Railway logs sem 401/403

---

## 8. Rollback Procedure

### 8.1 Via Script (recomendado)

```bash
./scripts/rotate-secrets.sh <SECRET> --rollback
```

### 8.2 Manual (se backup corrompido ou inexistente)

```bash
# 1. Gerar novo valor no provider dashboard (mesmo procedimento da rotacao)
# 2. Atualizar Railway manualmente
railway variables set SECRET="<valor>" --service bidiq-backend
# 3. Redeploy
railway redeploy --service bidiq-backend -y
# 4. Verificar saude
curl -f https://api.smartlic.tech/health/ready
# 5. Atualizar tracker manualmente
jq '.SECRET = "'$(date -u '+%Y-%m-%dT%H:%M:%SZ')'" | ._last_updated = "'$(date -u '+%Y-%m-%dT%H:%M:%SZ')'"' \
  .secrets-backup/last-rotation.json > /tmp/tmp.json && mv /tmp/tmp.json .secrets-backup/last-rotation.json
```

---

## 9. Documentos Relacionados

| Documento | Conteudo |
|-----------|----------|
| `docs/runbooks/secret-rotation.md` | Runbook operacional rapido |
| `docs/security/secret-rotation.md` | Documento de seguranca detalhado |
| `docs/security/credentials-inventory.md` | Inventario completo com proprietario |
| `scripts/rotate-secrets.sh` | Script de automacao |
| `.secrets-backup/last-rotation.json` | Tracker de rotacao |
| `.github/workflows/secret-age-check.yml` | CI gate mensal |
| `docs/runbooks/incident-response.md` | Resposta a incidentes |
| `.gitleaks.toml` | Config de deteccao de secrets no git |

---

*Proxima revisao: 2026-09-16*
