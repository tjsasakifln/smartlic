# Inventario de Credenciais — SmartLic

**Status:** Draft v1.0
**Responsavel:** @devops
**Data:** 2026-06-15
**Issue:** #1810

---

## Tabela de Inventario

| # | Servico | Credencial | Variavel de Ambiente | Proprietario | Ultima Rotacao | Metodo de Rotacao | Impacto se Comprometido |
|---|---------|-----------|---------------------|-------------|---------------|-------------------|------------------------|
| 1 | Stripe | Secret Key (live) | `STRIPE_SECRET_KEY` | @devops | — | Stripe Dashboard > Roll key | **CRITICO**: Acesso total a faturamento, subscriptions, refunds, dados de cartao (via tokens). Pode gerar cobrancas fraudulentas e comprometer receita. |
| 2 | Stripe | Webhook Secret | `STRIPE_WEBHOOK_SECRET` | @devops | — | Stripe Dashboard > Webhook > Reset | **ALTO**: Permite forjar eventos de webhook (iniciar subscriptions, cancelar assinaturas). Stripe SDK valida assinatura HMAC — sem bypass via header. |
| 3 | Stripe | API Key (test) | `STRIPE_TEST_SECRET_KEY` | @devops | — | Stripe Dashboard > Roll key | **BAIXO**: Ambiente de teste apenas. Sem impacto em dados reais. |
| 4 | Supabase | Service Role Key | `SUPABASE_SERVICE_ROLE_KEY` | @devops | — | Supabase Dashboard > Settings > API > Regenerate | **CRITICO**: Acesso irrestrito a todas as tabelas, bypass de RLS. Pode ler/alterar qualquer registro, executar queries arbitrarias. Equivalente a acesso root ao banco. |
| 5 | Supabase | Anon Key | `SUPABASE_ANON_KEY` | @devops | — | Supabase Dashboard > Settings > API > Regenerate | **BAIXO**: Chave publica, usada no frontend. Por design, e exposta ao cliente. RLS controla o que pode ser acessado com ela. |
| 6 | Supabase | Access Token (CLI) | `SUPABASE_ACCESS_TOKEN` | @devops | — | Supabase Dashboard > Settings > Access Tokens | **ALTO**: Acesso a API de gerenciamento do projeto. Permite alterar configuracoes, ler migracoes. |
| 7 | OpenAI | API Key | `OPENAI_API_KEY` | @devops | — | OpenAI Dashboard > API Keys | **ALTO**: Permite consumo de quota GPT-4.1-nano em nome da conta. Risco financeiro (cobranca por uso indevido). Sem acesso a dados do SmartLic. |
| 8 | Resend | API Key | `RESEND_API_KEY` | @devops | — | Resend Dashboard > API Keys | **MEDIO**: Permite envio de emails do dominio smartlic.tech. Risco de phishing usando dominio confiavel. |
| 9 | Sentry | DSN (backend) | `SENTRY_DSN` | @devops | — | Sentry Dashboard > Settings > Projects | **BAIXO**: DSN e semi-publico. Permite apenas envio de eventos. Sem acesso a leitura de dados. |
| 10 | Sentry | DSN (frontend) | `SENTRY_DSN_FRONTEND` | @devops | — | Sentry Dashboard > Settings > Projects | **BAIXO**: DSN publico (exposto no frontend). Permite apenas envio de eventos. |
| 11 | Sentry | Auth Token | `SENTRY_AUTH_TOKEN` | @devops | — | Sentry Dashboard > Auth Tokens | **MEDIO**: Permite upload de source maps e gerenciamento de releases. Sem acesso a dados de erro. |
| 12 | Mixpanel | Project Token | `NEXT_PUBLIC_MIXPANEL_TOKEN` | @devops | — | Mixpanel Dashboard > Project Settings | **BAIXO**: Token publico (exposto no frontend). Permite apenas envio de eventos. |
| 13 | Mixpanel | API Key | `MIXPANEL_API_KEY` | @devops | — | Mixpanel Dashboard > Project Settings | **MEDIO**: Permite importar/exportar dados de analytics via API. |
| 14 | Redis | Connection URL | `REDIS_URL` | @devops | — | Upstash Console > Reset Password / Railway > Re-add plugin | **ALTO**: Acesso a cache, filas ARQ, locks distribuidos, SSE state. Pode corromper estado de workers, causar crash, ou roubar dados de sessao. |
| 15 | Redis | Password | `REDIS_PASSWORD` | @devops | — | (incluida na REDIS_URL) | **ALTO**: Mesmo impacto de REDIS_URL comprometida. |
| 16 | GitHub | Deploy Token | `gh auth` | @devops | — | GitHub > Settings > Developer Settings | **MEDIO**: Acesso a repositorios. Pode ler codigo fonte. |
| 17 | Railway | Auth Token | `RAILWAY_TOKEN` | @devops | — | Railway Dashboard > Settings > Tokens | **ALTO**: Acesso a infraestrutura. Permite alterar variaveis de ambiente, redeploy, rollback. |
| 18 | Docker Hub | Registry Token | (Docker config.json) | @devops | — | Docker Hub > Security | **BAIXO**: Apenas pull de imagens publicas. |

---

## Armazenamento

| Onde esta | O que contem | Protecao |
|-----------|-------------|----------|
| Railway Variables (env) | Todas as credenciais de producao | Criptografadas em repouso, acessiveis via CLI com autenticacao |
| `.env` (local dev) | Variaveis de desenvolvimento | .gitignore, nunca commitado |
| `.env.example` | Placeholders (valores falsos) | Versionado, sem secrets reais |
| Supabase Dashboard | Service Role Key, Anon Key | Autenticacao MFA obrigatoria |
| Stripe Dashboard | Secret Key, Webhook Secret | Autenticacao MFA obrigatoria |
| OpenAI Dashboard | API Key | Autenticacao MFA obrigatoria |
| Resend Dashboard | API Key | Autenticacao com senha |
| Sentry Dashboard | Auth Token | Autenticacao com senha |
| Mixpanel Dashboard | Token, API Key | Autenticacao com senha |
| Upstash Console | Redis Password | Autenticacao com senha |

---

## Requisitos de Segregacao

| Ambiente | Conjunto de Credenciais | Pode compartilhar? |
|----------|------------------------|-------------------|
| Producao | Todas as secrets reais | NAO — estritamente isolado |
| Staging | Chaves de teste/trial | Pode compartilhar parcialmente com dev |
| Desenvolvimento Local | `.env` local com chaves dev | Cada dev tem seu proprio conjunto |
| CI/CD | Secrets injetadas via GitHub Actions | NAO — isoladas por ambiente |
| Code Review | Nenhuma secret | NUNCA aparece em diffs |

---

## Procedimentos Relacionados

- `docs/runbooks/secret-rotation.md` — Passo a passo de rotacao
- `docs/runbooks/incident-response.md` — Resposta a incidentes de seguranca
- `.gitleaks.toml` — Regras de deteccao de secrets pre-commit
- `.github/workflows/sast.yml` — SAST scanning (gitleaks em CI)

---

## Status da Ultima Auditoria

| Item | Status | Data |
|------|--------|------|
| Inventario revisado | Pendente | — |
| Todas as credenciais rotacionadas nos ultimos 90 dias | Pendente | — |
| Gitleaks configurado e ativo | Ativo | Pre-existente |
| MFA ativado em todos os provedores critico | Pendente | — |
| Acesso de terceiros auditado | Pendente | — |

---

*Ultima revisao: 2026-06-15. Proxima revisao: 2026-09-15.*
