# Procedimento de Rotacao de Secrets/Credenciais — SmartLic

**Status:** Draft v1.0
**Responsavel:** @devops
**Data:** 2026-06-15
**Issue:** #1810
**Periodicidade:** Trimestral (Q1/Q2/Q3/Q4)
**Emergencia:** Imediata mediante confirmacao de comprometimento

---

## 1. Inventario de Credenciais

Ver `docs/security/credentials-inventory.md` para o inventario completo com
proprietario, ultima rotacao, metodo e impacto.

### Resumo Rapido

| # | Servico | Tipo | Qtde Secrets | Rotacao | Impacto Comprometimento |
|---|---------|------|-------------|---------|------------------------|
| 1 | Stripe | API Key + Webhook Secret | 3 | Trimestral | Faturamento, dados de pagamento |
| 2 | Supabase | Service Role Key + Anon Key | 3 | Trimestral | Acesso total ao banco, RLS bypass |
| 3 | OpenAI | API Key | 2 | Trimestral | Uso indevido de quota, custos |
| 4 | Resend | API Key | 1 | Trimestral | Envio de emails fraudulentos |
| 5 | Sentry | DSN + Auth Token | 3 | Trimestral | Vazamento de error traces |
| 6 | Mixpanel | API Key + Token | 2 | Trimestral | Dados de analytics |
| 7 | Redis | Connection String + Password | 2 | Trimestral | Cache, filas, locks, SSE state |

---

## 2. Procedimentos de Rotacao por Servico

### 2.1 Stripe

**Secrets envolvidos:**
- `STRIPE_SECRET_KEY` — Chave de API (modo live)
- `STRIPE_WEBHOOK_SECRET` — Segredo para validacao de webhooks
- `STRIPE_PRICE_*` — IDs de precos (nao sao secrets mas requerem sync)

**Passo a passo:**

```bash
# 1. Acessar Stripe Dashboard
#    https://dashboard.stripe.com/apikeys

# 2. Gerar nova Secret Key (live)
#    Developers > API Keys > Roll secret key
#    Copiar novo valor temporariamente

# 3. Atualizar no Railway
railway variables set STRIPE_SECRET_KEY="sk_live_..." --service bidiq-backend

# 4. Atualizar no .env.example se aplicavel
#    (manter placeholder: sk_live_...)

# 5. Validar que a chave antiga ainda funciona (Stripe permite overlap de 24h)
#    Executar smoke test
curl -s https://api.smartlic.tech/health/ready | jq .

# 6. Apos 24h, revogar chave antiga no Stripe Dashboard
#    Developers > API Keys > Revoke old key

# 7. Repetir para webhook secret (se aplicavel):
#    Developers > Webhooks > Endpoint > Reveal/Reset signing secret
railway variables set STRIPE_WEBHOOK_SECRET="whsec_..." --service bidiq-backend
```

**Rollback:** Manter chave antiga em local seguro por 48h. Se algo quebrar,
restaurar via `railway variables set STRIPE_SECRET_KEY="sk_live_OLD..."`.

**Tempo estimado:** 15min

---

### 2.2 Supabase

**Secrets envolvidos:**
- `SUPABASE_URL` — URL do projeto (muda apenas se recriar projeto)
- `SUPABASE_SERVICE_ROLE_KEY` — Chave service_role (acesso total)
- `SUPABASE_ANON_KEY` — Chave anonima (cliente-side)
- `SUPABASE_ACCESS_TOKEN` — Token de acesso a API de gerenciamento

**Passo a passo:**

```bash
# 1. Acessar Supabase Dashboard
#    https://supabase.com/dashboard/project/fqqyovlzdzimiwfofdjk

# 2. Gerar nova Service Role Key
#    Project Settings > API > Service Role Key > Regenerate

# 3. Atualizar no Railway
railway variables set SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOiJIUzI1NiIs..." --service bidiq-backend

# 4. Gerar nova Anon Key
#    Project Settings > API > Anon Key > Regenerate
railway variables set SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIs..." --service bidiq-backend

# 5. Redeploy
railway redeploy --service bidiq-backend -y

# 6. Validar conectividade
curl -s "https://fqqyovlzdzimiwfofdjk.supabase.co/rest/v1/profiles?select=id&limit=1" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" | head -50
```

**Cuidados:**
- Rotacao de service_role key interrompe servicos em execucao (require redeploy)
- Anon key pode ser atualizada com menos urgencia (usada em RLS anon)
- **Nunca** commitar service_role key no frontend ou em repositorios

**Rollback:** Supabase mantem a chave anterior valida por 1h. Se algo quebrar,
regenere novamente com o mesmo valor anterior (copiado do backup).

**Tempo estimado:** 10min

---

### 2.3 OpenAI

**Secrets envolvidos:**
- `OPENAI_API_KEY` — Chave de API (GPT-4.1-nano)

**Passo a passo:**

```bash
# 1. Acessar OpenAI Dashboard
#    https://platform.openai.com/api-keys

# 2. Criar nova API Key
#    API Keys > + Create new secret key
#    Permissao: apenas o modelo GPT-4.1-nano (ou modelo definido em config.py)

# 3. Adicionar nova chave no Railway (MANTENDO a antiga ainda ativa)
railway variables set OPENAI_API_KEY="sk-proj-..." --service bidiq-backend
railway redeploy --service bidiq-backend -y

# 4. Validar classificacao IA
curl -s https://api.smartlic.tech/health/ready | jq .

# 5. Apos confirmacao, revogar chave antiga no OpenAI Dashboard
```

**Rollback:** OpenAI permite multiplas chaves ativas simultaneamente. Manter
chave antiga como fallback por 24h.

**Tempo estimado:** 10min

---

### 2.4 Resend

**Secrets envolvidos:**
- `RESEND_API_KEY` — Chave de API para envio de emails

**Passo a passo:**

```bash
# 1. Acessar Resend Dashboard
#    https://resend.com/api-keys

# 2. Criar nova API Key
#    API Keys > Create API Key
#    Domain: smartlic.tech (verificado)

# 3. Atualizar no Railway
railway variables set RESEND_API_KEY="re_..." --service bidiq-backend
railway redeploy --service bidiq-backend -y

# 4. Testar envio de email
#    Usar script de teste ou trigger manual de email transacional
#    Verificar delivery no Resend Dashboard > Logs
```

**Rollback:** Resend permite chaves multiplas. Revogar antiga apos 24h.

**Tempo estimado:** 10min

---

### 2.5 Sentry

**Secrets envolvidos:**
- `SENTRY_DSN` — DSN do backend (nao e estritamente secreto)
- `SENTRY_DSN_FRONTEND` — DSN do frontend
- `SENTRY_AUTH_TOKEN` — Token de autenticacao (releases + source maps)

**Passo a passo:**

```bash
# 1. Gerar novo SENTRY_AUTH_TOKEN
#    Settings > Auth Tokens > Create New Token
#    Escopos: project:releases, event:read, org:read

# 2. Atualizar no Railway (backend)
railway variables set SENTRY_AUTH_TOKEN="sntrys_..." --service bidiq-backend

# 3. Atualizar no Railway (frontend)
railway variables set SENTRY_DSN_FRONTEND="https://..." --service bidiq-frontend

# 4. Validar
#    Backend: forcar um erro e verificar no Sentry Dashboard
#    Frontend: npm run build (source maps devem upload com novo token)

# 5. Revogar token antigo no Sentry Dashboard
```

**Rollback:** Criar novo token antes de revogar o antigo. Manter ambos ativos
por 24h.

**Tempo estimado:** 10min

---

### 2.6 Mixpanel

**Secrets envolvidos:**
- `MIXPANEL_TOKEN` — Token do projeto (frontend)
- `MIXPANEL_API_KEY` — Chave de API (importacao de dados)

**Passo a passo:**

```bash
# 1. Acessar Mixpanel Dashboard
#    https://mixpanel.com/settings/project

# 2. Gerar novo token de projeto (regenerar)
#    Project Settings > Token

# 3. Atualizar variaveis no Railway
railway variables set MIXPANEL_TOKEN="new-token..." --service bidiq-frontend
railway variables set MIXPANEL_API_KEY="new-apikey..." --service bidiq-backend

# 4. Redeploy ambos servicos
railway redeploy --service bidiq-frontend -y
railway redeploy --service bidiq-backend -y

# 5. Validar: verificar Mixpanel Live View para eventos recebidos
```

**Tempo estimado:** 10min

---

### 2.7 Redis

**Secrets envolvidos:**
- `REDIS_URL` — URL de conexao (contem password)
- `REDIS_PASSWORD` — Senha do Redis (quando separada da URL)

**Passo a passo:**

```bash
# 1. Acessar painel do provedor Redis (Upstash / Railway)
#    Se Railway: Dashboard > Redis plugin
#    Se Upstash: console.upstash.com > Database > Settings

# 2. Regenerar password
#    Railway: Remove and re-add Redis plugin (gera nova URL automaticamente)
#    Upstash: Settings > Reset Password

# 3. Atualizar no Railway
railway variables set REDIS_URL="redis://:newpassword@host:port" --service bidiq-backend
railway redeploy --service bidiq-backend -y

# 4. Validar conexao
railway run --service bidiq-backend python -c "
import asyncio
from redis_pool import get_redis_pool
async def main():
    r = await get_redis_pool()
    await r.set('healthcheck', 'ok')
    val = await r.get('healthcheck')
    print(f'Redis OK: {val}')
asyncio.run(main())
"
```

**Cuidados:**
- Rotacao de Redis **derruba** todas as sessoes ativas (cache, filas, locks, SSE)
- Preferencia por janela de manutencao de baixo trafego
- Filas ARQ podem perder jobs em andamento — verificar antes

**Rollback:** Manter senha antiga por 30min. Provedores de Redis geralmente
nao suportam overlap de senhas — rollback requer restore da senha anterior.

**Tempo estimado:** 15min

---

## 3. Procedimento de Emergencia — Credencial Comprometida

**Disparador:** Confirmacao de que uma credencial foi exposta (vazamento em log,
commit accident, terceiro nao autorizado, breach de provedor).

### 3.1 Triage (5 min)

```bash
# 1. Identificar qual credencial foi comprometida
#    Procurar em:
#    - Logs do Railway (railway logs --tail --service bidiq-backend)
#    - GitHub (git log --all -p | grep -i "sk_live\|sk-proj\|eyJhbGci\|re_\|sntrys_")
#    - Gitleaks (gitleaks detect -v)
#    - Sentry (error traces que possam conter secrets)

# 2. Avaliar impacto
#    Consultar docs/security/credentials-inventory.md tabela de impacto

# 3. Decidir se e emergencia ou pode esperar rotacao agendada
```

### 3.2 Contencao Imediata (15 min)

Para **qualquer** credencial confirmada como comprometida:

```bash
# Passo 1: Rotacionar IMEDIATAMENTE (seguir procedimento da secao 2)
# Nao esperar overlap — revogar antiga e gerar nova.

# Passo 2: Revogar acesso no provedor (via dashboard ou CLI)
#    Stripe:     Revoke key no Dashboard
#    OpenAI:     Revoke key no Dashboard
#    Supabase:   Regenerate no Dashboard
#    Resend:     Delete key no Dashboard
#    Sentry:     Revoke token no Dashboard

# Passo 3: Verificar uso indevido
#    Stripe:     Dashboard > Payments > Verificar transacoes nao autorizadas
#    OpenAI:     Dashboard > Usage > Verificar pico de uso anomalo
#    Supabase:   Logs > Verificar queries suspeitas

# Passo 4: Notificar equipe
#    #devops-canal (Slack/Discord): "CREDENCIAL COMPROMETIDA: {servico}
#     Rotacao realizada em $(date). Impacto avaliado: {baixo/medio/alto}"
```

### 3.3 Pos-Contencao (30 min)

```bash
# 1. Atualizar inventory
#    - docs/security/credentials-inventory.md
#    - Coluna "Ultima Rotacao" = hoje

# 2. Investigar causa raiz
#    - Como a credencial vazou?
#    - Precisa de mitigation adicional? (ex: gitleaks pre-commit hook, env var audit)

# 3. Documentar incidente
#    - docs/incidents/YYYY-MM-DD-credential-compromise.md
#    - Incluir: cronologia, causa raiz, impacto, acoes corretivas

# 4. Se vazamento foi publico (GitHub, pastebin):
#    - Verificar se credencial foi rotacionada (passo 1)
#    - Considerar notificacao legal se dados de clientes expostos
```

---

## 4. Checklist de Verificacao Pos-Rotacao

Apos cada rotacao (agendada ou emergencial), executar:

### 4.1 Backend Health

```bash
# 1. Health check basico
curl -s https://api.smartlic.tech/health/live | jq .
curl -s https://api.smartlic.tech/health/ready | jq .

# 2. Testar endpoint que usa o servico rotacionado
#    Stripe:     Criar subscription de teste (modo test)
#    OpenAI:     Buscar que usa classificacao IA
#    Supabase:   GET /bids?limit=1
#    Resend:     Enviar email de teste
#    Redis:      Verificar health check wedge_risk
```

### 4.2 Testes Automatizados

```bash
# Rodar suite de seguranca (cobre auth, webhook, rate-limit)
cd backend && python -m pytest tests/security/ -v --timeout=30
```

### 4.3 Validacao Manual

```bash
# 1. Fazer login no frontend (testa Supabase Auth + JWT)
# 2. Executar uma busca (testa pipeline completo)
# 3. Gerar relatorio Excel (testa export)
# 4. Verificar Sentry para novos erros apos redeploy
# 5. Verificar Mixpanel Live View para eventos
```

### 4.4 Verificacao de Vazamento

```bash
# Garantir que a credencial antiga NAO aparece em:
# - git log (gitleaks detect)
# - Railway logs (railway logs --tail)
# - Sentry traces
# - Pastas docs/ ou frontend (commits anteriores)
```

---

## 5. Calendario de Rotacao Periodica

| Trimestre | Janela | Servicos | Responsavel |
|-----------|--------|----------|-------------|
| Q1 | 15-31 Janeiro | Stripe + Supabase + OpenAI | @devops |
| Q2 | 15-30 Abril | Resend + Sentry + Mixpanel | @devops |
| Q3 | 15-31 Julho | Redis + Supabase (re-rotate) | @devops |
| Q4 | 15-31 Outubro | Stripe + OpenAI + revisao geral | @devops |

**Regras:**
- Nao rotacionar mais de 2 servicos no mesmo dia (minimizar risco)
- Preferencia por janela de baixo trafego (fins de semana, 22h-06h)
- Manter janela de 2 semanas para acomodar imprevistos
- Agendar no calendario da equipe com 7 dias de antecedencia

### Gatilhos Adicionais (fora do calendario)

| Evento | Acao |
|--------|------|
| Rotacao de membro da equipe | Rotacionar todas as credenciais que o membro tinha acesso |
| Breach de terceiro (Supabase, OpenAI, Stripe) | Rotacionar imediatamente a credencial afetada |
| Commit acidental de secret | Rotacionar imediatamente + investigar janela de exposicao |
| Auditoria externa | Rotacionar todas as credenciais antes da auditoria |
| Pre-v1.0 launch | Rotacionar todas as credenciais 7 dias antes do launch |

---

## 6. Documentos Relacionados

- `docs/security/credentials-inventory.md` — Inventario completo de credenciais
- `docs/security/pentest-plan.md` — Plano de teste de penetracao
- `docs/security/test-baseline.md` — Testes de seguranca automatizados
- `docs/runbooks/incident-response.md` — Runbook de resposta a incidentes
- `docs/security/dependency-scanning.md` — Auditoria de dependencias
- `.gitleaks.toml` — Configuracao de deteccao de secrets no git

---

*Ultima revisao: 2026-06-15. Proxima revisao: 2026-09-15.*
