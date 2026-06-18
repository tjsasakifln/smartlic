# Plano de Disaster Recovery (DR) — SmartLic

**Issue:** #1957
**Versao:** 1.0
**Data:** 2026-06-17
**Autor:** Dex (Builder)
**Aprovacao:** Pendente

---

## Sumario

1. [Dependencias e RPO/RTO](#1-dependencias-e-rpoto)
2. [Criterios de Ativacao do DR](#2-criterios-de-ativacao-do-dr)
3. [Checklist de Ativacao (Quem, Quando, Como)](#3-checklist-de-ativacao)
4. [Procedimentos de Recuperacao por Dependencia](#4-procedimentos-de-recuperacao)
   - [4.1 Supabase — Point-in-Time Recovery (PITR)](#41-supabase--point-in-time-recovery-pitr)
   - [4.2 Supabase — Recriacao Completa a Partir de Migrations](#42-supabase--recriacao-completa-a-partir-de-migrations)
   - [4.3 Redis / Upstash — Failover](#43-redis--upstash--failover)
   - [4.4 Railway — Emergency Rollback e Redeploy](#44-railway--emergency-rollback-e-redeploy)
   - [4.5 Recriacao de Secrets (Stripe, OpenAI, Resend, Supabase)](#45-recriacao-de-secrets)
5. [Verificacao Pos-Recuperacao](#5-verificacao-pos-recuperacao)
6. [Teste de DR — Simulacao de Perda Total](#6-teste-de-dr)
7. [Cenario: Perda do Proprio Plano de DR](#7-cenario-perda-do-proprio-plano-de-dr)
8. [Gotchas Conhecidas](#8-gotchas-conhecidas)
9. [Custos](#9-custos)
10. [Melhorias Futuras](#10-melhorias-futuras)

---

## 1. Dependencias e RPO/RTO

A tabela abaixo define o **RPO (Recovery Point Objective)** — perda maxima de dados aceitavel — e o **RTO (Recovery Time Objective)** — tempo maximo para restauracao — para cada dependencia critica do sistema.

Diferente da abordagem de RPO/RTO global (4h/1h), cada dependencia tem metricas proprias baseadas em sua arquitetura e criticidade.

### Tabela de RPO/RTO por Dependencia

| Dependencia | Tipo | RPO | RTO | Metodo de Recuperacao Primario | Metodo Secundario |
|-------------|------|-----|-----|-------------------------------|-------------------|
| **Supabase (PostgreSQL)** | Banco de dados + Auth | 1h (PITR) / 24h (snapshot) | 2h | PITR para novo projeto | Snapshot + migrations |
| **Redis / Upstash** | Cache + Queue + SSE + Rate Limiter | Perda total aceitavel (efemero) | 30min | Troca de endpoint no Railway | Criar nova instancia Redis |
| **Railway (Backend)** | Web server (FastAPI) | N/A (stateless) | 15min | Rollback para deploy anterior | `railway redeploy` |
| **Railway (Frontend)** | Web server (Next.js) | N/A (stateless) | 15min | Rollback para deploy anterior | `railway redeploy` |
| **Railway (Worker)** | ARQ job processor | Perda de jobs em fila (idempotentes) | 15min | Reinicio do worker | Redeploy do worker |
| **Stripe** | Pagamentos + assinaturas | Perda maxima: transacoes no ultimo webhook | 1h | Regenerar secrets via Dashboard | Stripe suporte |
| **OpenAI** | LLM (classificacao + resumos) | N/A (stateless) | 30min | Regenerar API key via Dashboard | Fallback PENDING_REVIEW |
| **Resend** | Email transacional | Perda maxima: emails na fila | 30min | Regenerar API key via Dashboard | Resend suporte |
| **GitHub** | Codigo fonte + CI/CD | Perda maxima: ultimo commit | 2h | Push de clone local | GitHub Support |
| **Cloudflare** | DNS (smartlic.tech) | N/A | 1h | Atualizar DNS records | Cloudflare Dashboard |
| **Sentry** | Error tracking | N/A (stateless) | 1h | Regenerar DSN via Dashboard | — |
| **Mixpanel** | Analytics | Perda de eventos nao enviados | 2h | Regenerar token via Dashboard | — |

### RPO/RTO Globais do Sistema

| Metrica | Valor | Definicao |
|---------|-------|-----------|
| **RPO Global** | 1 hora | Perda maxima de dados aceitavel em caso de desastre |
| **RTO Global** | 4 horas | Tempo maximo para restauracao completa do sistema |

Estes valores foram definidos considerando o estagio atual do produto (pre-revenue beta, trials pagos) e o perfil de uso B2G. A medida que o produto amadurecer e a base de usuarios crescer, RPO e RTO devem ser revistos para prazos mais agressivos (ex: RTO <1h).

---

## 2. Criterios de Ativacao do DR

O plano de Disaster Recovery e ativado quando um ou mais dos seguintes criterios sao atendidos:

### 2.1 Criterios de Ativacao Automatica

| Criterio | Descricao | Gatilho |
|----------|-----------|---------|
| **Supabase indisponivel >10min** | Health check `/health/ready` retorna `unhealthy` por >10 minutos consecutivos | Monitoramento (health canary 5min) |
| **Perda de dados confirmada** | Exclusao acidental, corrupcao, ou ataque identificado via logs | Notificacao manual |
| **Projeto Supabase deletado** | Projeto inteiro perdido (raro, mas ja ocorrido em outros projetos) | Notificacao manual |
| **Redis irrecuperavel** | Instancia Upstash deletada ou corrompida, sem possibilidade de restore | Notificacao manual |
| **Comprometimento de credenciais** | Secrets expostos (vazamento em log, repositorio publico, etc.) | Notificacao manual |

### 2.2 Criterios de Ativacao Manual

| Criterio | Decisor |
|----------|---------|
| Falha em mais de 50% dos health checks por >30min | Admin (Tiago Sasaki) |
| Incidente de seguranca com impacto em dados de usuarios (LGPD) | Admin (Tiago Sasaki) |
| Desastre regional (regiao `sa-east-1` da AWS indisponivel afetando Supabase) | Admin (Tiago Sasaki) |
| Instrucao direta do Founder/CEO | Founder |

### 2.3 Quando NAO Ativar o DR

- Redis caiu, mas sistema opera em modo degradado (todos os fallbacks funcionam)
- Erro de deploy que pode ser corrigido com rollback simples (Section 4.4)
- Instabilidade temporaria de API externa (PNCP, PCP, ComprasGov) — circuit breakers gerenciam
- Pico de trafego com degradacao parcial — escalar primeiro (restart worker, aumentar recursos)

---

## 3. Checklist de Ativacao

### 3.1 Quem Ativa

| Funcao | Responsavel | Contato |
|--------|-------------|---------|
| **DR Lead (on-call)** | Tiago Sasaki | tiago.sasaki@gmail.com |
| **Backup DR Lead** | Marinalva Baron | marinalvabaron@gmail.com |
| **Supabase Support** | — | support@supabase.io (Pro plan) |
| **Railway Support** | — | support@railway.app, Discord |
| **Stripe Support** | — | dashboard.stripe.com/support |
| **Resend Support** | — | support@resend.com |

### 3.2 Quando Ativar

| Sintoma | Acao | Prazo |
|---------|------|-------|
| Supabase /health/ready unhealthy >10min | Iniciar diagnostico | Imediato |
| Perda de dados confirmada | ATIVAR DR (Section 4.1 PITR) | Imediato |
| Projeto Supabase deletado | ATIVAR DR (Section 4.2 Full Recreation) | Imediato |
| Secrets expostos | ATIVAR DR (Section 4.5 Secrets) + rotacionar | Imediato |
| Indisponibilidade >30min sem causa identificada | ATIVAR DR | 30min apos inicio |
| Instrucao do Founder | ATIVAR DR | Imediato |

### 3.3 Checklist de Ativacao (Passo a Passo)

```markdown
## DR ACTIVATION CHECKLIST

### Passo 1 — Diagnostico (5 min)
- [ ] Verificar /health/ready: curl -f https://smartlic.tech/health/ready
- [ ] Verificar Railway logs: railway logs --tail --service bidiq-backend
- [ ] Verificar Railway status: railway status
- [ ] Verificar Supabase status: https://status.supabase.com
- [ ] Verificar log de erros no Sentry
- [ ] Confirmar qual dependencia falhou e qual o impacto
- [ ] DECISAO: Ativar DR ou aguardar recuperacao automatica?

### Passo 2 — Notificacao (2 min)
- [ ] Notificar admin (Tiago Sasaki): email + telefone
- [ ] Notificar time de engenharia se impacto >30min estimado
- [ ] Se dados de usuario afetados: documentar para notificacao LGPD posterior
- [ ] Criar incidente em docs/runbooks/incidentes/ com timestamp

### Passo 3 — Executar Recovery (RTO varia por dependencia — ver Section 4)
- [ ] Executar procedimento especifico da dependencia afetada
- [ ] Documentar cada comando executado (para post-mortem)
- [ ] Registrar timestamps de inicio e fim de cada etapa

### Passo 4 — Verificar (15 min)
- [ ] Executar Post-Recovery Verification Checklist (Section 5)
- [ ] Confirmar que health endpoints retornam healthy
- [ ] Testar login com usuario admin
- [ ] Testar fluxo de busca basico
- [ ] Verificar Stripe webhooks recebendo eventos
- [ ] Verificar fila ARQ processando jobs

### Passo 5 — Comunicar Encerramento
- [ ] Notificar admin que DR foi concluido
- [ ] Se downtime >30min: enviar email para usuarios afetados via Resend
- [ ] Agendar post-mortem em ate 48h
- [ ] Atualizar este documento com licoes aprendidas
```

---

## 4. Procedimentos de Recuperacao

### 4.1 Supabase — Point-in-Time Recovery (PITR)

**Metodo preferido** para: exclusao acidental de dados, corrupcao, bad migration aplicada.

**NAO usar para:** projeto deletado, outage regional do Supabase.

**Pre-requisito:** Plano Pro com PITR ativado.

**RPO:** ~2 minutos (WAL archiving continuo)
**RTO estimado:** 15-30 minutos

#### Procedimento

```bash
# 1. Acessar Supabase Dashboard
#    https://supabase.com/dashboard/project/fqqyovlzdzimiwfofdjk

# 2. Navegar: Database > Backups > Point in Time

# 3. Selecionar timestamp alvo (anterior ao incidente)
#    - Se exclusao de dados: timestamp 5 minutos antes do comando destrutivo
#    - Se bad migration: timestamp antes da migracao ser aplicada

# 4. Clicar "Start recovery"
#    - Supabase CRIA UM NOVO PROJETO com os dados restaurados
#    - O projeto original permanece intocado (seguranca)
#    - Anotar o novo project ref (ex: abcdefghijklmnopqrst)

# 5. Atualizar environment variables no Railway (ver Section 4.5)
#    railway variables set SUPABASE_URL=https://<NEW_REF>.supabase.co --service bidiq-backend
#    railway variables set SUPABASE_KEY=<new_anon_key> --service bidiq-backend
#    railway variables set SUPABASE_SERVICE_ROLE_KEY=<new_service_role_key> --service bidiq-backend
#    railway variables set NEXT_PUBLIC_SUPABASE_URL=https://<NEW_REF>.supabase.co --service bidiq-frontend
#    railway variables set NEXT_PUBLIC_SUPABASE_ANON_KEY=<new_anon_key> --service bidiq-frontend

# 6. Redeploy ambos os servicos
#    railway redeploy --service bidiq-backend -y
#    railway redeploy --service bidiq-frontend -y

# 7. Verificar (Section 5)
```

#### Apos o PITR

1. Verificar integridade dos dados: `SELECT count(*)` nas tabelas principais (`profiles`, `subscriptions`, `search_history`)
2. Verificar autenticacao: tentar login com usuario admin
3. Verificar RLS policies: consultar como usuario nao-admin
4. Reaplicar migrations pendentes se o restore for de data anterior ao deploy mais recente:
   ```bash
   npx supabase db push --include-all
   ```
5. Reconfigurar items nao cobertos pelo PITR:
   - Auth email templates
   - Auth redirect URLs
   - Google OAuth client ID/secret
   - pg_cron extension (se o restore criou projeto sem)
   - Ver `DISASTER-RECOVERY.md` Section 4 para lista completa

---

### 4.2 Supabase — Recriacao Completa a Partir de Migrations

**Metodo nuclear** para: projeto completamente perdido, migracao para nova organizacao Supabase, restore quando PITR nao esta disponivel.

**RPO:** 24h (ultimo snapshot diario) + dados desde entao (perdidos se sem pg_dump manual)
**RTO estimado:** 1-2 horas

**ATENCAO:** Este procedimento recria apenas o SCHEMA. Dados de usuario NAO sao recuperados a menos que voce tenha um pg_dump recente.

#### Pre-requisitos

```bash
# Verificar que o Supabase CLI esta disponivel
npx supabase --version

# Verificar que o diretorio de migrations existe
ls supabase/migrations/ | wc -l   # Deve mostrar ~183+ arquivos

# Exportar SUPABASE_ACCESS_TOKEN do .env
export SUPABASE_ACCESS_TOKEN=$(grep SUPABASE_ACCESS_TOKEN .env | cut -d '=' -f2)
```

#### Step 1: Criar Novo Projeto Supabase

1. Acessar **supabase.com/dashboard** > New Project
2. **Regiao:** South America (Sao Paulo) — `sa-east-1`
3. **Nome:** `smartlic-prod` (ou `smartlic-dr-YYYYMMDD`)
4. **Database password:** Gerar e salvar em cofre seguro (Bitwarden, 1Password)
5. Anotar o novo **project ref** (substitui `fqqyovlzdzimiwfofdjk`)

#### Step 2: Habilitar pg_cron Extension

**CRITICO** — as migrations 022, 023, 20260225150000, 20260304110000, 20260308310000 VAO FALHAR sem pg_cron.

1. Dashboard > Database > Extensions
2. Buscar `pg_cron`
3. Clicar **Enable**
4. Confirmar que aparece na lista de extensoes habilitadas

#### Step 3: Link e Aplicar Migrations

```bash
npx supabase link --project-ref <NOVO_PROJECT_REF>
npx supabase db push --include-all
```

Se alguma migration falhar:
- Verificar se pg_cron esta habilitado (Step 2)
- Migrations iniciais (001-033) usam nomenclatura legada e podem falhar em re-run — isto e normal no tracking sequencial do Supabase
- Migrations com `CREATE OR REPLACE` ou `IF NOT EXISTS` sao seguras para re-run

#### Step 4: Verificar pg_cron Jobs

Executar no SQL Editor:

```sql
SELECT jobname, schedule, command
FROM cron.job
ORDER BY jobname;
```

**Esperado: 11 jobs** (cleanup-monthly-quota, cleanup-webhook-events, cleanup-audit-events, cleanup-cold-cache-entries, cleanup-expired-search-results, cleanup-search-state-transitions, cleanup-alert-sent-items, cleanup-health-checks, cleanup-incidents, cleanup-mfa-recovery-attempts, cleanup-alert-runs).

Se algum job estiver faltando, re-executar o `cron.schedule()` da migration correspondente manualmente no SQL Editor.

#### Step 5: Seed Admin User

1. Auth > Users > Create user: `tiago.sasaki@gmail.com`
2. Executar no SQL Editor:

```sql
UPDATE public.profiles
SET is_admin = true, is_master = true
WHERE email = 'tiago.sasaki@gmail.com';
```

3. Repetir para `marinalvabaron@gmail.com` (is_master = true)

#### Step 6: Restaurar Dados (se pg_dump disponivel)

```bash
# Se voce tem um dump recente (ver Section 6.2 para criacao manual):
pg_restore --dbname="postgresql://postgres:<password>@db.<NEW_REF>.supabase.co:5432/postgres" \
  smartlic_backup_YYYYMMDD_HHMMSS.dump
```

**AVISO:** pg_restore pode sobrescrever dados seed (plans, billing periods) — verificar apos restore.

#### Step 7: Atualizar Environment Variables

Ver Section 4.5 para lista completa de variaveis.

---

### 4.3 Redis / Upstash — Failover

**Arquitetura Atual:** Redis utilizado como cache L1 (4h TTL), SSE state tracking, rate limiter, ARQ job queue, distributed locks, circuit breaker state, e feature flag overrides. Todos os dados no Redis SAO EFEMEROS e podem ser reconstruidos das fontes primarias.

**Impacto de Perda do Redis:**
- Todos os fallbacks documentados em `docs/architecture/redis-failure-modes.md`
- Sistema opera em modo degradado (fail-open para rate limiter, InMemoryCache como fallback)
- ARQ job queue fica indisponivel — jobs nao processados ate Redis voltar
- Rate limiting desativado temporariamente (fail-open)
- Circuit breaker state perdido (fallback para memoria local)
- SSE state tracking perdido (novas conexoes comecam do zero)

#### Procedimento de Failover

##### Caso A: Upstash Instancia Ativa mas Degradada

```bash
# 1. Verificar conectividade
railway run redis-cli -u $REDIS_URL ping

# 2. Verificar client count (pool saturado?)
railway run redis-cli -u $REDIS_URL CLIENT LIST | wc -l

# 3. Verificar memory usage
railway run redis-cli -u $REDIS_URL INFO memory | grep used_memory_human

# 4. Verificar keyspace
railway run redis-cli -u $REDIS_URL INFO keyspace

# 5. Se saturacao: limpar caches antigos
railway run redis-cli -u $REDIS_URL FLUSHDB ASYNC  # Cuidado: limpa TUDO
```

##### Caso B: Upstash Instancia Perdida / Deletada

```bash
# 1. Criar nova instancia Redis no Upstash Console:
#    - Acessar https://console.upstash.com
#    - Redis > Create Database
#    - Regiao: sa-east-1 (ou a mesma regiao do Railway/Supabase)
#    - Max memory: 100MB-256MB (suficiente para cache + queue + SSE)
#    - TLS habilitado (rediss://)
#    - Eviction policy: allkeys-lru

# 2. Copiar o REDIS_URL (formato: rediss://default:<token>@<endpoint>.upstash.io:6379)

# 3. Atualizar no Railway
railway variables set REDIS_URL="rediss://default:<novo_token>@<novo_endpoint>.upstash.io:6379" --service bidiq-backend

# 4. Redeploy
railway redeploy --service bidiq-backend -y
```

##### Caso C: Migrar para Railway Redis (se Upstash estiver completamente indisponivel)

```bash
# Railway tambem oferece Redis como plugin. Se Upstash estiver fora:
# 1. No Railway Dashboard > bidiq-backend > Variables
# 2. Clicar "Add Plugin" > Redis
# 3. Railway cria automaticamente a variavel REDIS_URL
# 4. Confirmar com:
railway variables list | grep REDIS_URL
# 5. Se a variavel ja foi injetada automaticamente, redeploy e suficiente:
railway redeploy --service bidiq-backend -y
```

#### Apos Recovery do Redis

```bash
# Verificar que o Redis esta operacional
railway run redis-cli -u $REDIS_URL ping
# Deve retornar: PONG

# Verificar metricas de fallback no Prometheus
# smartlic_redis_available deve voltar para 1
# smartlic_redis_fallback_duration_seconds deve parar de incrementar
```

Apos recovery automatico:
- Auth cache repopula na proxima requisicao
- Rate limiter retorna para Redis mode
- ARQ jobs retomam (pode ser necessario `railway redeploy --service bidiq-worker`)
- Circuit breaker state recomeca fresh (historico de falhas perdido)

---

### 4.4 Railway — Emergency Rollback e Redeploy

#### 4.4.1 Rollback para Deploy Anterior

**Cenario:** Deploy recente introduziu bug critico em producao. Rollback e mais rapido que hotfix.

**Metodo 1: Railway Dashboard (recomendado para emergencia)**

```bash
# 1. Listar deploys recentes para identificar o ultimo estavel
railway deploy list --service bidiq-backend

# 2. Rollback para um deploy especifico pelo ID
railway deploy rollback <DEPLOY_ID> --service bidiq-backend -y
#    (substituir bidiq-backend por bidiq-frontend ou bidiq-worker conforme necessario)

# 3. Verificar status apos rollback
railway status --service bidiq-backend
```

**Metodo 2: Git Revert + Push (quando rollback via CLI nao funciona)**

```bash
# 1. Identificar o commit estavel (ultimo commit em main antes do problematico)
git log --oneline -10 main

# 2. Reverter o(s) commit(s) problematico(s) em uma nova branch
git checkout main
git pull origin main
git revert <COMMIT_HASH_PROBLEMATICO> --no-edit
#    Ou para multiplos commits:
git revert <OLDEST_GOOD_COMMIT>..<LATEST_BAD_COMMIT> --no-edit

# 3. Fazer push para main (gatilho CI/CD automatico)
git push origin main

# 4. Acompanhar deploy: https://railway.app/project/<project>/deploys
#    Ou via CLI:
railway status
```

#### 4.4.2 Redeploy Forcado (quando GitHub auto-deploy nao trigger)

```bash
# CASO: Commit foi para main mas Railway nao iniciou deploy
# (comum quando Railway watch patterns nao detectam mudanca)

# Solucao 1: redeploy forcado
railway redeploy --service bidiq-backend -y

# Solucao 2: usar CACHEBUST para forcar rebuild
# Editar backend/Dockerfile e modificar o LABEL build.timestamp:
# LABEL build.timestamp="2026-06-17T12:00:00Z"
# Commit e push triggeram novo build

# Solucao 3: toque manual nos watch patterns
# touch backend/main.py && git add . && git commit -m "chore: force redeploy"
```

#### 4.4.3 Reinicio de Servico (para problemas de memoria/worker travado)

```bash
# Reiniciar servico (mais rapido que redeploy — mantem o mesmo build)
railway service restart --service bidiq-backend

# Verificar logs apos restart
railway logs --tail --service bidiq-backend

# Se worker travado:
railway service restart --service bidiq-worker
```

#### 4.4.4 Emergency Procedure: Railway Proxy Timeout (CRIT-RES)

O Railway tem hard timeout de ~120s. Se o backend esta respondendo mas o proxy Railway esta matando requisicoes antes:

```bash
# 1. Verificar se o route-level timeout middleware esta ativo (deve estar)
#    ROUTE_TIMEOUT_S deve ser < 120 (default 60s)

# 2. Se middleware causando problemas, desabilitar sem redeploy:
railway variables set ROUTE_TIMEOUT_S=0 --service bidiq-backend

# 3. O servico reinicia automaticamente quando variaveis sao alteradas via CLI
#    (fire-and-forget: Railway aplica variaveis e reinicia)

# 4. Apos resolucao, reativar:
railway variables set ROUTE_TIMEOUT_S=60 --service bidiq-backend
```

#### 4.4.5 Recuperacao de Worker Travado (ARQ)

```bash
# 1. Verificar se worker esta processando
railway logs --tail --service bidiq-worker | grep "arq"

# 2. Se worker parou mas processo ainda esta vivo:
railway service restart --service bidiq-worker

# 3. Se worker nao reinicia:
railway redeploy --service bidiq-worker -y

# 4. Se colocated worker (WORKER_COLOCATED=true no backend):
#    O worker roda como subprocesso do backend. Reiniciar o backend:
railway service restart --service bidiq-backend
```

---

### 4.5 Recriacao de Secrets

#### 4.5.1 Mapa Completo de Secrets

| Secret | Onde Obter | Servicos Afetados | Rotacao Emergencial |
|--------|-----------|-------------------|---------------------|
| `SUPABASE_URL` | Supabase Dashboard > Project Settings > API | backend, frontend | Imediata |
| `SUPABASE_ANON_KEY` | Supabase Dashboard > Project Settings > API | backend, frontend | Imediata |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase Dashboard > Project Settings > API | backend (service_role) | Imediata |
| `DATABASE_URL` | Supabase Dashboard > Project Settings > Database | backend (conexao direta) | Imediata |
| `STRIPE_SECRET_KEY` | Stripe Dashboard > Developers > API Keys | backend | Imediata |
| `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard > Webhooks > Endpoint > Signing secret | backend | Imediata (se webhook endpoint mudar) |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys | backend | Imediata |
| `RESEND_API_KEY` | https://resend.com/api-keys | backend | Imediata |
| `TRIAL_EMAILS_WEBHOOK_SECRET` | Resend > Webhooks > Endpoint > Signing Secret | backend | Imediata (se webhook endpoint mudar) |
| `SENTRY_DSN` | Sentry > Settings > Projects > smartlic-backend > DSN | backend, frontend | Media |
| `GITHUB_TOKEN` | GitHub > Settings > Developer settings > Personal access tokens | CI/CD | Se exposto |
| `SUPABASE_ACCESS_TOKEN` | Supabase Dashboard > Account > Access Tokens | CLI, CI/CD | Se exposto |
| `REVALIDATE_SECRET` | Gerado com `openssl rand -hex 32` | backend, frontend | Se exposto |
| `LGPD_DELETION_SECRET` | Gerado com `openssl rand -hex 32` | backend | Se exposto |

#### 4.5.2 Procedimento de Recriacao de Secrets

**Regra de ouro:** NUNCA commitar secrets no repositorio. Usar Railway Dashboard ou CLI exclusivamente.

##### Stripe

```bash
# 1. Acessar Stripe Dashboard > Developers > API Keys
# 2. Criar nova secret key (ou revelar existente)
# 3. Se webhook endpoint precisar ser recriado:
#    - Stripe Dashboard > Developers > Webhooks > Add endpoint
#    - URL: https://smartlic.tech/webhooks/stripe (NOTA: raiz, NAO /v1/webhooks/stripe)
#    - Eventos: customer.subscription.created, .updated, .deleted,
#               invoice.paid, .payment_failed, .upcoming,
#               checkout.session.completed, .async_payment_succeeded,
#               .async_payment_failed, customer.created, .deleted
#    - Copiar o signing secret
# 4. Atualizar no Railway:
railway variables set STRIPE_SECRET_KEY="sk_live_..." --service bidiq-backend
railway variables set STRIPE_WEBHOOK_SECRET="whsec_..." --service bidiq-backend
```

##### OpenAI

```bash
# 1. Acessar https://platform.openai.com/api-keys
# 2. Criar nova API key (ou revelar existente)
# 3. Atualizar no Railway:
railway variables set OPENAI_API_KEY="sk-..." --service bidiq-backend

# NOTA: Se a key for rotacionada, o LLM arbiter pode retornar PENDING_REVIEW
# temporariamente ate o proximo request. Verificar Sentry para erros 401.
```

##### Resend

```bash
# 1. Acessar https://resend.com/api-keys
# 2. Criar nova API key
# 3. Se webhook endpoint precisar ser recriado:
#    - Resend > Webhooks > Add endpoint
#    - URL: https://smartlic.tech/v1/trial-emails/webhook
#    - Copiar signing secret
# 4. Atualizar no Railway:
railway variables set RESEND_API_KEY="re_..." --service bidiq-backend
railway variables set TRIAL_EMAILS_WEBHOOK_SECRET="whsec_..." --service bidiq-backend
```

##### Supabase (apos PITR ou Full Recreation)

```bash
# Obter novas chaves no Supabase Dashboard > Project Settings > API
railway variables set \
  SUPABASE_URL="https://<NEW_REF>.supabase.co" \
  SUPABASE_ANON_KEY="<new_anon_key>" \
  SUPABASE_SERVICE_ROLE_KEY="<new_service_role_key>" \
  --service bidiq-backend

railway variables set \
  NEXT_PUBLIC_SUPABASE_URL="https://<NEW_REF>.supabase.co" \
  NEXT_PUBLIC_SUPABASE_ANON_KEY="<new_anon_key>" \
  --service bidiq-frontend

# Atualizar DATABASE_URL para conexao direta (pg_dump, CLI):
# Acessar Supabase Dashboard > Project Settings > Database > Connection string (URI)
railway variables set \
  DATABASE_URL="postgresql://postgres:<password>@db.<NEW_REF>.supabase.co:5432/postgres" \
  --service bidiq-backend
```

##### GitHub Actions Secrets (se project ref mudou)

```bash
gh secret set SUPABASE_PROJECT_REF --body "<NEW_REF>"
gh secret set SUPABASE_ACCESS_TOKEN --body "<token>"
gh secret set SUPABASE_DB_URL --body "postgresql://postgres:<password>@db.<NEW_REF>.supabase.co:5432/postgres"
```

#### 4.5.3 Script de Verificacao de Secrets

Apos atualizar secrets, verificar que todas as variaveis necessarias estao presentes:

```bash
# Listar variaveis do backend
railway variables list --service bidiq-backend

# Verificar variaveis criticas
REQUIRED_VARS=(
  "SUPABASE_URL"
  "SUPABASE_ANON_KEY"
  "SUPABASE_SERVICE_ROLE_KEY"
  "OPENAI_API_KEY"
  "STRIPE_SECRET_KEY"
  "RESEND_API_KEY"
  "REDIS_URL"
)

for var in "${REQUIRED_VARS[@]}"; do
  value=$(railway variables get "$var" --service bidiq-backend 2>/dev/null)
  if [ -z "$value" ]; then
    echo "MISSING: $var"
  else
    echo "OK: $var (${#value} chars)"
  fi
done
```

---

## 5. Verificacao Pos-Recuperacao

### 5.1 Database

- [ ] Todas as migrations aplicadas sem erros (`npx supabase db push --include-all`)
- [ ] pg_cron extension habilitada e 11 jobs agendados (`SELECT * FROM cron.job`)
- [ ] pg_trgm extension habilitada (`SELECT * FROM pg_extension`)
- [ ] `handle_new_user` trigger existe em `auth.users` (CRITICO)
- [ ] `check_and_increment_quota` RPC function existe
- [ ] `increment_quota_atomic` RPC function existe
- [ ] `set_updated_at` function existe
- [ ] Todas as RLS policies ativas (`SELECT tablename, COUNT(*) FROM pg_policies GROUP BY tablename`)
- [ ] Plans table com entradas corretas (`SELECT * FROM plans`)
- [ ] Billing periods com Stripe price IDs (`SELECT * FROM plan_billing_periods`)
- [ ] Admin users tem is_admin = true (`SELECT email, is_admin, is_master FROM profiles WHERE is_admin = true`)

### 5.2 Backend

- [ ] Environment variables atualizadas (ver Section 4.5)
- [ ] `uvicorn main:app` inicia sem erros
- [ ] `GET /health/live` retorna 200
- [ ] `GET /health/ready` retorna `healthy`
- [ ] `GET /setores` retorna 20 setores
- [ ] `GET /plans` retorna dados dos planos
- [ ] Login funciona (testar com admin `tiago.sasaki@gmail.com`)
- [ ] Search pipeline produz resultados (rodar busca de teste)
- [ ] Redis ping retorna PONG (`railway run redis-cli -u $REDIS_URL ping`)
- [ ] Fila ARQ processando jobs (`railway logs --tail --service bidiq-worker | grep "Job"`)

### 5.3 Frontend

- [ ] Environment variables atualizadas
- [ ] `npm run build` succeeds
- [ ] Login page carrega em `/login`
- [ ] Login com admin credentials funciona
- [ ] Search page carrega em `/buscar`
- [ ] Dashboard carrega em `/dashboard`
- [ ] Pagina de planos carrega em `/planos`

### 5.4 Integracoes Externas

- [ ] Stripe webhooks recebendo eventos (Stripe Dashboard > Webhooks > Recent events)
- [ ] Railway services healthy (ambos backend e frontend)
- [ ] GitHub Actions secrets atualizados (se project ref mudou)
- [ ] Dominio `smartlic.tech` resolvendo corretamente (`curl -I https://smartlic.tech | head -1` retorna 200)
- [ ] Sentry capturando erros (forcar um erro de teste)

---

## 6. Teste de DR

### 6.1 Cronograma

| Tipo | Frequencia | Responsavel | Proximo |
|------|-----------|-------------|---------|
| **Full loss simulation** | Trimestral (meses 3, 6, 9, 12) | DR Lead | 2026-09-17 |
| **PITR dry run** | Semestral (meses 1, 7) | DR Lead | 2026-07-17 |
| **Secrets rotation drill** | Semestral (meses 4, 10) | DR Lead | 2026-10-17 |
| **Railway rollback drill** | Semestral (meses 4, 10) | DR Lead | 2026-10-17 |
| **Backup verification** | Mensal (dia 1) | DR Lead | 2026-07-01 |

### 6.2 Full Loss Simulation (Trimestral)

**Objetivo:** Simular perda completa do projeto Supabase + Redis e validar recuperacao dentro do RTO de 4 horas.

**Ambiente:** Projeto Supabase temporario + servico Railway temporario (opcional, pode ser so validacao de procedimento).

#### Procedimento

```bash
# FASE 1: Criar ambiente de teste (15 min)

# 1. Criar projeto Supabase temporario
npx supabase projects create --name "smartlic-dr-test-$(date +%Y%m%d)"

# 2. Habilitar pg_cron (Dashboard > Database > Extensions)

# 3. Link e aplicar migrations
npx supabase link --project-ref <TEST_REF>
npx supabase db push --include-all

# 4. Criar instancia Redis temporaria (Railway plugin ou Upstash)
#    Para Railway: adicionar plugin Redis no servico de teste

# FASE 2: Verificar schema e funcionalidades (20 min)

# 5. Executar verification checklist (Section 5)

# 6. Verificar pg_cron jobs
psql <CONNECTION_STRING> -c "SELECT jobname FROM cron.job"

# 7. Simular restauracao de dados (se pg_dump disponivel)
pg_restore --dbname="<TEST_CONNECTION>" latest_backup.dump

# FASE 3: Destruir ambiente (5 min)
npx supabase projects delete <TEST_REF>
```

#### Criterios de Sucesso

1. Todas as migrations aplicadas sem erros
2. pg_cron extension habilitada e 11 jobs agendados
3. RPC functions criticas existem (`check_and_increment_quota`, `increment_quota_atomic`, `set_updated_at`)
4. `handle_new_user` trigger existe em `auth.users`
5. RLS policies ativas em todas as tabelas
6. Plans + billing periods com dados seed corretos
7. Duracao total do procedimento < 4h (RTO global)

#### Documentacao do Teste

Apos cada execucao, gerar relatorio sucinto em `docs/architecture/dr-test-logs/`:

```markdown
# DR Test Report — YYYY-MM-DD

**Tipo:** Full loss simulation
**DR Lead:** Nome
**Duracao:** XX minutos

## Resultados

| Etapa | Status | Duracao | Notas |
|-------|--------|---------|-------|
| Criacao projeto Supabase | PASS/FAIL | Xmin | - |
| pg_cron habilitado | PASS/FAIL | Xmin | - |
| Migrations aplicadas | PASS/FAIL | Xmin | - |
| RPC functions verificadas | PASS/FAIL | Xmin | - |
| RLS policies verificadas | PASS/FAIL | Xmin | - |
| pg_cron jobs verificados | PASS/FAIL | Xmin | - |
| Seed data verificada | PASS/FAIL | Xmin | - |
| Redis failover | PASS/FAIL | Xmin | - |

## Problemas Encontrados
1. ...
2. ...

## Licoes Aprendidas
1. ...
2. ...

## Aprovacao
- [ ] PASS — procedimento valido dentro do RTO
- [ ] FAIL — gap identificado, revisar plano antes do proximo teste
```

---

### 6.3 Backup Manual (pg_dump) — Antes de Operacoes de Risco

Sempre executar antes de:
- Aplicar migrations em producao
- Modificar dados sensiveis via SQL Editor
- Reestruturar tabelas

```bash
# Obter connection string do Dashboard > Settings > Database > URI
pg_dump "postgresql://postgres:<password>@db.fqqyovlzdzimiwfofdjk.supabase.co:5432/postgres" \
  --format=custom \
  --no-owner \
  --file=smartlic_backup_$(date +%Y%m%d_%H%M%S).dump

# Verificar integridade do dump
pg_restore --list smartlic_backup_20260617_120000.dump | head -20
```

---

## 7. Cenario: Perda do Proprio Plano de DR

**Cenario:** O repositorio GitHub esta indisponivel e o documento `docs/architecture/disaster-recovery-plan.md` nao pode ser acessado.

**Mitigacao:** Este plano existe em tres locais:
1. **GitHub** — source of truth (repositorio remoto)
2. **Clone local** — cada desenvolvedor tem copia do repositorio
3. **Backup designado** — copia exportada em `DISASTER-RECOVERY.md` na raiz do projeto (arquivo legado mantido como fallback de leitura rapida)

**Procedimento se todos os acessos falharem:**
1. Recuperar clone local de qualquer desenvolvedor
2. Recriar repositorio GitHub (ver `backup-dr-strategy.md` Section 4.4)
3. Fazer push do clone local
4. Proceder com DR normalmente a partir do documento recuperado

---

## 8. Gotchas Conhecidas

### Supabase

| Gotcha | Descricao | Mitigacao |
|--------|-----------|-----------|
| **pg_cron manual** | pg_cron precisa ser habilitado manualmente no Dashboard. `CREATE EXTENSION IF NOT EXISTS pg_cron` na migration falha porque requer superuser. | Habilitar antes de `db push` |
| **Migrations 001-033 sem IF NOT EXISTS** | Migrations legadas falham em re-run. | Esperado no tracking sequencial do Supabase; ignorar erro e continuar |
| **handle_new_user trigger** | Se faltar, novos signups criam auth user mas SEM profile -> 401/403 em toda requisicao | Verificar na POS-RECOVERY checklist |
| **Stripe price IDs hardcoded** | Price IDs estao nas migrations 029 e 20260301300000 | Se Stripe products forem recriados, atualizar `plan_billing_periods.stripe_price_id` manualmente |
| **PITR cria novo projeto** | PITR NAO restaura no projeto original — cria um novo. URL e chaves mudam. | Atualizar env vars e redeploy |
| **Auth settings nao entram no PITR** | Email templates, OAuth config, redirect URLs precisam ser reconfigurados manualmente | Checklist Section 5 captura isso |

### Redis

| Gotcha | Descricao | Mitigacao |
|--------|-----------|-----------|
| **ARQ jobs perdidos** | Jobs enfileirados no Redis sao perdidos se Redis for deletado. | Todos os jobs sao idempotentes (upsert semantics) |
| **Circuit breaker state resetado** | Historico de falhas dos CBs e perdido. | CBs comecam fresh — aceitavel, estado e temporario |
| **Rate limiter fail-open** | Sem Redis, rate limiter permite todas as requisicoes. | Degradacao aceitavel. Monitorar `smartlic_rate_limit_exceeded_total` |
| **SSE tracking perdido** | Conexoes SSE ativas perdem estado. | Cliente frontend reinicia conexao automaticamente |

### Railway

| Gotcha | Descricao | Mitigacao |
|--------|-----------|-----------|
| **`railway up` de subdiretorio falha** | Executar `railway up` de dentro de `backend/` ou `frontend/` envia estrutura errada. | Sempre executar da raiz do repositorio |
| **Env vars via CLI nao reiniciam servico** | Railway NAO reinicia automaticamente quando env vars mudam via CLI. | Executar `railway redeploy` apos alterar env vars |
| **GitHub auto-deploy pode pular commits** | Commits que nao tocam `backend/**` ou `frontend/**` sao ignorados pelos watch patterns. | Usar `railway redeploy` se auto-deploy nao trigger |
| **413 Payload Too Large** | `railway up` da raiz pode falhar se repositorio >~300MB. | Usar `.railwayignore` ou GitHub auto-deploy |

### Secrets

| Gotcha | Descricao | Mitigacao |
|--------|-----------|-----------|
| **DSN do Sentry muda por projeto** | Cada projeto Sentry tem DSN unico. Se recriar projeto Sentry, DSN muda. | Atualizar `SENTRY_DSN` no Railway |
| **Stripe webhook secret muda se endpoint for recriado** | Recriar webhook endpoint no Stripe gera novo signing secret. | Atualizar `STRIPE_WEBHOOK_SECRET` |
| **Resend webhook signing secret** | Mesmo principio do Stripe — recriar endpoint = novo secret | Atualizar `TRIAL_EMAILS_WEBHOOK_SECRET` |

---

## 9. Custos

| Componente | Custo | Detalhes |
|------------|-------|----------|
| Supabase daily snapshots | Incluso no plano Pro | Retencao de 7 dias |
| Supabase PITR | Custo adicional (WAL storage) | Ja ativo no plano Pro |
| Ambiente de teste DR | Custo marginal | Projeto Supabase temporario + potencial Redis extra |
| Railway rebuild | Sem custo adicional | Infra-as-code: deploy recria do zero |
| GitHub | Incluso | Backup distribuido do repositorio |
| Upstash Redis | Incluso no free tier | 100MB, suficiente para producao atual |

---

## 10. Melhorias Futuras

| Item | Prioridade | Esforco | Beneficio |
|------|-----------|---------|-----------|
| Automatizar DR test trimestral via script CI | Media | Medio | Validacao regular sem esforco manual |
| Configurar replicacao cross-region Supabase | Baixa | Alto | Alta disponibilidade geografica |
| Backup automatizado de env vars Railway para cofre | Baixa | Baixo (script) | Evitar configuracao manual apos rebuild |
| On-call rotation (PagerDuty ou similar gratuito) | Alta | Medio | Alertas nao dependem de email pessoal |
| Dashboard Grafana publico de status | Baixa | Medio | Transparencia para usuarios |
| Script unificado de DR (`scripts/dr-recovery.sh`) | Media | Alto | Executar procedimento completo com um comando |
| Criptografia de backups em repouso | Ja implementado | — | Supabase gerencia nativamente |

---

## Referencias

- `DISASTER-RECOVERY.md` — Documento legado com PITR detalhado e Full Recreation (raiz do projeto)
- `docs/architecture/backup-dr-strategy.md` — Estrategia de backup original (issue #1787)
- `docs/architecture/redis-failure-modes.md` — Comportamento degradado do Redis
- `docs/architecture/monitoring-setup.md` — Stack de monitoramento e alertas
- `docs/architecture/graceful-degradation-matrix.md` — FMEA de todas as dependencias
- `docs/runbooks/incident-response.md` — Runbook de resposta a incidentes
- `backend/railway.toml` — Configuracao Railway do backend
- `.env.example` — Template de environment variables
