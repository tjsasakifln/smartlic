# Procedimento de Rotacao de Secrets

Este documento lista todos os secrets e tokens utilizados no projeto SmartLic,
com procedimentos de rotacao, prazos recomendados e plano de resposta a vazamento.

---

## Indice

- [Visao Geral dos Secrets](#visao-geral-dos-secrets)
- [Matriz de Rotacao](#matriz-de-rotacao)
- [Procedimentos por Servico](#procedimentos-por-servico)
- [Testes Pos-Rotacao](#testes-pos-rotacao)
- [Resposta a Vazamento (Incident Response)](#resposta-a-vazamento-incident-response)

---

## Visao Geral dos Secrets

### Producao (Railway)

| Secret | Servico | Onde esta definido | Acesso |
|--------|---------|--------------------|--------|
| `OPENAI_API_KEY` | OpenAI | Railway backend env | Dashboard |
| `SUPABASE_URL` | Supabase | Railway backend env | Dashboard |
| `SUPABASE_ANON_KEY` | Supabase | Railway backend + frontend env | Dashboard |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase | Railway backend env (NUNCA no frontend) | Dashboard |
| `STRIPE_SECRET_KEY` | Stripe | Railway backend env | Dashboard |
| `STRIPE_WEBHOOK_SECRET` | Stripe | Railway backend env | Dashboard |
| `RESEND_API_KEY` | Resend | Railway backend env | Dashboard |
| `TRIAL_EMAILS_WEBHOOK_SECRET` | Resend | Railway backend env | Dashboard |
| `SENTRY_DSN` | Sentry | Railway backend + frontend env | Dashboard |
| `SENTRY_AUTH_TOKEN` | Sentry | Railway backend env (management Excel) | Dashboard |
| `MIXPANEL_SERVICE_ACCOUNT_USERNAME` | Mixpanel | Railway backend env | Dashboard |
| `MIXPANEL_SERVICE_ACCOUNT_PASSWORD` | Mixpanel | Railway backend env | Dashboard |
| `MIXPANEL_PROJECT_ID` | Mixpanel | Railway backend env | Dashboard |
| `RAILWAY_TOKEN` | Railway | GitHub Actions secrets | GitHub |
| `GITHUB_TOKEN` | GitHub | GitHub Actions + local dev | GitHub |
| `REVALIDATE_SECRET` | Next.js | Railway backend + frontend env | Dashboard |
| `OPENROUTER_API_KEY` | OpenRouter | Railway backend env | Dashboard |
| `DEEPSEEK_API_KEY` | DeepSeek | .env (dev apenas) | Local |
| `EXA_API_KEY` | Exa | .env (dev apenas) | Local |
| `LGPD_DELETION_SECRET` | SmartLic | Railway backend env | Dashboard |
| `SUPABASE_ACCESS_TOKEN` | Supabase CLI | GitHub Actions | GitHub |
| `SUPABASE_DB_URL` | Supabase | GitHub Actions | GitHub |
| `SEED_ADMIN_PASSWORD` | SmartLic | Railway backend env | Dashboard |
| `SEED_MASTER_PASSWORD` | SmartLic | Railway backend env | Dashboard |
| `FOUNDING_ONE_TIME_PRICE_ID` | Stripe | Railway backend env | Dashboard |

### Desenvolvimento Local

| Secret | Onde esta | Fonte |
|--------|-----------|-------|
| `OPENAI_API_KEY` | `.env` local | OpenAI platform |
| `SUPABASE_URL/ANON_KEY/SERVICE_ROLE_KEY` | `.env` local | Supabase project settings |
| Todas as demais | `.env` local | Respectivos providers |
| `CLICKUP_API_KEY` | `.env` local | Clickup settings (opcional) |
| `N8N_API_KEY` + `N8N_WEBHOOK_URL` | `.env` local | N8N instance (opcional) |
| `VERCEL_TOKEN` | `.env` local | Vercel account (opcional) |

---

## Matriz de Rotacao

| Secret | Prazo Recomendado | Impacto se Vazar | Rotacao Emergencial |
|--------|-------------------|-------------------|---------------------|
| `OPENAI_API_KEY` | 90 dias | Alto (custo LLM) | Imediata |
| `SUPABASE_SERVICE_ROLE_KEY` | 90 dias | Critico (acesso total DB) | Imediata |
| `SUPABASE_ANON_KEY` | 180 dias | Baixo (anon, RLS protege) | Agendada |
| `STRIPE_SECRET_KEY` | 90 dias | Critico (faturamento) | Imediata |
| `STRIPE_WEBHOOK_SECRET` | 90 dias | Medio (webhooks falsos) | Imediata |
| `RESEND_API_KEY` | 90 dias | Medio (email spoofing) | Imediata |
| `TRIAL_EMAILS_WEBHOOK_SECRET` | 90 dias | Medio (webhooks falsos) | Imediata |
| `SENTRY_DSN` | 180 dias | Baixo (apenas ingestao) | Agendada |
| `SENTRY_AUTH_TOKEN` | 90 dias | Medio (acesso admin Sentry) | Imediata |
| `MIXPANEL_*` | 180 dias | Medio (dados analiticos) | Agendada |
| `RAILWAY_TOKEN` | 90 dias | Alto (deploy nao autorizado) | Imediata |
| `GITHUB_TOKEN` | 90 dias | Alto (acesso ao repositorio) | Imediata |
| `REVALIDATE_SECRET` | 90 dias | Medio (cache flush) | Imediata |
| `LGPD_DELETION_SECRET` | 180 dias | Alto (LGPD compliance) | Imediata |
| `SUPABASE_DB_URL` | 90 dias | Critico (acesso direto DB) | Imediata |
| `SUPABASE_ACCESS_TOKEN` | 90 dias | Alto (admin Supabase) | Imediata |

---

## Procedimentos por Servico

### OpenAI

```bash
# 1. Gerar nova chave no dashboard da OpenAI
#    https://platform.openai.com/api-keys
# 2. Atualizar Railway
railway variables set OPENAI_API_KEY=sk-<nova-chave>
# 3. Verificar health
railway run curl -s https://api.smartlic.tech/health/live
# 4. Revogar chave antiga no dashboard da OpenAI
```

### Supabase (Service Role Key)

```bash
# 1. Gerar nova chave no Supabase Dashboard
#    Project Settings > API > service_role key > Reveal > Regenerate
# 2. Atualizar Railway
railway variables set SUPABASE_SERVICE_ROLE_KEY=<nova-chave>
# 3. Reiniciar servico
railway redeploy --service bidiq-backend -y
# 4. Verificar
railway run curl -s https://api.smartlic.tech/v1/admin/cron-status
# 5. Atualizar SUPABASE_DB_URL se necessario
#    (connection string inclui a service role key)
```

### Supabase (Anon Key)

```bash
# 1. Gerar nova chave no Supabase Dashboard
#    Project Settings > API > anon public key > Regenerate
# 2. Atualizar Railway backend
railway variables set SUPABASE_ANON_KEY=<nova-chave>
# 3. Atualizar Railway frontend
railway variables set SUPABASE_ANON_KEY=<nova-chave>  # no servico frontend
# 4. Atualizar .env.local de desenvolvimento
# 5. Verificar auth flows
```

### Stripe

```bash
# 1. Gerar nova chave secreta no Stripe Dashboard
#    Developers > API Keys > Roll key
# 2. Atualizar Railway
railway variables set STRIPE_SECRET_KEY=sk_live_<nova-chave>
# 3. Atualizar webhook secret se necessario
#    Stripe Dashboard > Developers > Webhooks > endpoint > Reveal > Signing secret
# 4. Reiniciar servico
railway redeploy --service bidiq-backend -y
# 5. Testar criacao de checkout em modo test
```

### Resend

```bash
# 1. Gerar nova chave no Resend Dashboard
#    https://resend.com/api-keys
# 2. Atualizar Railway
railway variables set RESEND_API_KEY=re_<nova-chave>
# 3. Se o webhook secret tambem mudar:
railway variables set TRIAL_EMAILS_WEBHOOK_SECRET=<novo-secret>
# 4. Reiniciar servico
railway redeploy --service bidiq-backend -y
# 5. Verificar envio de email (ex: /v1/trial-emails/webhook)
```

### GitHub Token

```bash
# 1. Ir em https://github.com/settings/tokens
# 2. Gerar novo token (classic ou fine-grained)
# 3. Atualizar GitHub Actions secrets
#    Settings > Secrets and variables > Actions > GITHUB_TOKEN
# 4. Atualizar .env.local
# 5. Revogar token antigo
```

### Revalidate Secret

```bash
# 1. Gerar novo secret
openssl rand -hex 32
# 2. Atualizar Railway backend
railway variables set REVALIDATE_SECRET=<novo-secret>
# 3. Atualizar Railway frontend
railway variables set REVALIDATE_SECRET=<novo-secret>
# 4. Atualizar .env.local
# 5. Verificar ISR revalidation
```

### LGPD Deletion Secret

```bash
# 1. Gerar novo pepper
openssl rand -hex 32
# 2. Atualizar Railway
railway variables set LGPD_DELETION_SECRET=<novo-secret>
# 3. ATENCAO: Secrets antigos usados para hashes existentes
#    Devem ser mantidos em LGPD_DELETION_SECRET_OLD para verificacao
#    ate o periodo de retencao expirar
railway variables set LGPD_DELETION_SECRET_OLD=<secret-anterior>
# 4. Atualizar codigo para tentar ambos: novo primeiro, old como fallback
```

---

## Testes Pos-Rotacao

Apos cada rotacao, execute os seguintes testes:

### Checklist Universal

- [ ] Railway health endpoints retornam 200:
  ```bash
  curl -f https://api.smartlic.tech/health/live
  curl -f https://api.smartlic.tech/health/ready
  ```
- [ ] Sentry nao mostra novos erros de autenticacao
- [ ] Railway logs nao mostram `401`, `403`, ou `authentication failed`

### Por Servico

| Secret Rotacionado | Teste Especifico |
|--------------------|------------------|
| OpenAI | Executar busca com `?setor=8` e verificar classificacao LLM |
| Supabase Service Role | Verificar `GET /v1/admin/cron-status` retorna dados |
| Supabase Anon | Fazer login no frontend, verificar search funciona |
| Stripe | Criar checkout session em modo test, verificar webhook |
| Resend | Enviar email de teste, verificar entrega |
| Revalidate | `curl -X POST https://smartlic.tech/api/revalidate` |
| GitHub Token | `gh auth status` |
| Railway Token | `railway status` |

---

## Resposta a Vazamento (Incident Response)

### Severidade por Tipo de Secret

| Severidade | Criterio | Exemplos |
|------------|----------|----------|
| **CRITICO** | Acesso a dados financeiros, admin DB, ou deploy | `STRIPE_SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`, `RAILWAY_TOKEN` |
| **ALTO** | Acesso a dados de clientes ou operacao paga | `OPENAI_API_KEY`, `GITHUB_TOKEN`, `LGPD_DELETION_SECRET` |
| **MEDIO** | Spoofing ou acesso a dados analiticos | `RESEND_API_KEY`, `SENTRY_AUTH_TOKEN`, `MIXPANEL_*` |
| **BAIXO** | Dados publicos ou baixo risco | `SUPABASE_ANON_KEY`, `SENTRY_DSN` |

### Procedimento Imediato (S0 -- Critico/Alto)

1. **Identificar o alcance:**
   - Verificar GitHub Secrets para execucoes de Actions nao autorizadas
   - Verificar Railway logs para活动 suspeita
   - Verificar Stripe Dashboard para transacoes nao autorizadas
   - Verificar OpenAI usage para consumo anomalo

2. **Rotacao emergencial:**
   ```bash
   # Sequencia recomendada (orcamento por risco)
   railway variables set STRIPE_SECRET_KEY=<nova-chave>
   railway variables set SUPABASE_SERVICE_ROLE_KEY=<nova-chave>
   railway variables set RAILWAY_TOKEN=<novo-token>
   railway redeploy --service bidiq-backend -y
   ```

3. **Revogar credential comprometida:**
   - Stripe: Dashboard > Developers > API Keys > Revoke
   - OpenAI: Platform > API Keys > Revoke
   - GitHub: Settings > Tokens > Delete
   - Supabase: Project Settings > API > Regenerate

4. **Verificacao de danos:**
   - Revisar logs de acesso das ultimas 24h
   - Verificar billing de todos os servicos afetados
   - Auditar GitHub Actions runs

5. **Notificacao:**
   - Criar incident report em Sentry
   - Notificar equipe via canal de comunicacao designado
   - Registrar em `docs/security/incidents/`

### Procedimento Agendado (S1 -- Medio/Baixo)

1. Rotacao dentro de 24h uteis seguindo procedimento por servico
2. Atualizar `.env.example` se necessario
3. Verificar se o secret antigo foi removido de todos os locais
4. Registrar rotacao em `CHANGELOG.md`

### Prevencao

- **gitleaks**: Scan pre-commit (configurado em `.gitleaks.toml`)
- **GitHub secret scanning**: Ativado no repositorio
- **`.env` no `.gitignore`**: Confirmar que `.env` nunca e commitado
- **Auditoria periodica**: Checklist trimestral em `docs/security/quarterly-checklist.md`
