# Runbook: Railway Deploy Stuck

**Versao:** 1.0
**Criado:** 2026-06-17
**Owner:** @devops
**Severidade tipica:** SEV2 (SEV1 se bloquear hotfix critico)
**Referencia:** CLAUDE.md — Railway Deploy Rules, CRIT-080

---

## 1. Sintomas

### Alertas
- GitHub Actions: runs ficam `queued` (nunca comecam)
- Railway Dashboard: deploy mostra `BUILDING` ou `DEPLOYING` por > 10 min
- Railway Dashboard: deploy mostra `CRASHED` logo apos iniciar
- Usuario reporta: "mudou algo? site esta quebrado" (deploy quebrado no ar)
- Railway CLI: `railway status` mostra servico `DEGRADED` ou `CRASHED`

### Comportamento Observado
```
GitHub Actions: workflow_runs[0] = {status: "queued", conclusion: null}  # CRIT-080
Railway: "Deploy stuck in BUILDING for 15+ minutes"
Railway: "Application crashed after 3 seconds"
Railway: "Could not find root directory"  # Deploy de subdiretorio errado
```

### Classificacao de Stuck

| Tipo | Sintoma | Causa Provavel |
|------|---------|----------------|
| **Build Stuck** | BUILDING > 10 min | Build falho, recurso insuficiente, monorepo structure errada |
| **Deploy Stuck** | DEPLOYING > 10 min | Health check falhando, crash loop |
| **Queued** | workflow run "queued" sem comecar | GitHub Actions billing issue (CRIT-080) |
| **Skipped** | Railway mostra SKIPPED | Commit nao tocou backend/ ou frontend/ |
| **Crash Loop** | CRASHED, reinicia, crash de novo | Erro de runtime, env var faltando, SIGSEGV |

---

## 2. Diagnostico

### 2.1 Verificar GitHub Actions Billing (PRIMEIRO PASSO)

```bash
# CRIT-080: billing issue e a causa mais comum de deploy stuck silencioso
gh api /repos/confenge/smartlic/actions/runs --jq '.workflow_runs[:5] | .[] | {status, conclusion, name, created_at}'

# Se MULTIPLOS runs mostram "queued" + null → billing issue confirmado
gh api /repos/confenge/smartlic/actions/billing --jq '{minutes_used, included_minutes, minutes_remaining}'
```

**Se billing excedido:** GitHub Settings > Billing & plans > Actions Spending limit > Add budget.

### 2.2 Verificar Railway Deploy Status

```bash
# Listar deployments recentes
railway deployments --service bidiq-backend

# Ver status detalhado
railway status

# Ver logs do deploy atual
railway logs --service bidiq-backend --tail | tail -50
```

### 2.3 Verificar Build Logs

```bash
# Logs de build (se o deploy chegou a comecar)
railway logs --service bidiq-backend --build | tail -50

# Erros comuns:
# - "Could not find root directory" → deploy de subdiretorio errado
# - "npm ERR!" ou "Module not found" → dependencia quebrada
# - "Python build failed" → requirements.txt com erro
```

### 2.4 Verificar Monorepo Path

```bash
# Confirmar que RAILWAY_SERVICE_ROOT_DIRECTORY esta correto
railway variables --service bidiq-backend | grep RAILWAY_SERVICE_ROOT_DIRECTORY
# Backend esperado: "backend"
# Frontend esperado: "frontend"

# Se vazio ou errado: deploy pega a raiz do repo (monorepo = build quebrado)
```

### 2.5 Verificar Cache Bust

```bash
# Se o codigo nao mudou mas precisa de redeploy forcado
# Railway watch patterns ignoram commits que nao tocam os paths monitorados
grep -r "LABEL build.timestamp" backend/Dockerfile
grep -r "ARG CACHEBUST" backend/Dockerfile
```

---

## 3. Causas e Mitigacao

### 3.1 GitHub Actions Sem Billing

**Causa:** Spending limit excedido ou pagamento pendente.
**Mitigacao:**

```bash
# Emergency: bypass GitHub Actions, deploy direto no Railway
railway redeploy --service bidiq-backend -y

# Fix permanente: GitHub > Settings > Billing > aumentar spending limit
```

### 3.2 Deploy de Subdiretorio Errado

**Causa:** `railway up` executado de dentro de `backend/` ou `frontend/`.

**Mitigacao:**

```bash
# Sempre executar de raiz do projeto
cd /mnt/d/pncp-poc
railway up

# Verificar .railwayignore (excluir docs/, data/, scripts/)
cat .railwayignore
```

### 3.3 Deploy SKIPPED (arquivos nao monitorados)

**Causa:** Commit que nao toca `backend/` ou `frontend/`.

**Mitigacao:**

```bash
# Forcar rebuild com cache bust
# Opcao 1: Atualizar LABEL build.timestamp no Dockerfile
sed -i 's/build.timestamp=.*/build.timestamp='$(date +%s)'/' backend/Dockerfile
git add backend/Dockerfile && git commit -m "chore: bump build timestamp [skip ci]"

# Opcao 2: Deploy manual forcado
railway redeploy --service bidiq-backend -y
```

### 3.4 Build Falhou (Dependencia)

**Causa:** `requirements.txt` ou `package.json` com versao quebrada.

**Mitigacao:**

```bash
# Rollback para deployment anterior
railway rollback --service bidiq-backend

# Corrigir dependencia localmente
# Testar build
cd backend && pip install -r requirements.txt

# Commit e deploy
git add backend/requirements.txt && git commit -m "fix: corrigir dependencia quebrada"
```

### 3.5 Crash Loop (Runtime Error)

**Causa:** Erro de runtime, env var faltando, SIGSEGV (CRIT-080/083).

**Mitigacao:**

```bash
# 1. Verificar logs de crash
railway logs --service bidiq-backend --tail

# 2. Se SIGSEGV: verificar RUNNER env var
railway variables --service bidiq-backend | grep RUNNER
# Deve ser "uvicorn", nao "gunicorn" (gunicorn causa SIGSEGV)

# 3. Se ModuleNotFoundError ou SyntaxError: rollback
railway rollback --service bidiq-backend

# 4. Rollback for emergency
railway redeploy --service bidiq-backend -y
```

### 3.6 413 Payload Too Large (railway up)

**Causa:** Repositorio > ~300MB, `railway up` falha.

**Mitigacao:**

```bash
# 1. Usar .railwayignore para excluir diretorios grandes
echo "docs/" >> .railwayignore
echo "data/" >> .railwayignore
echo "scripts/" >> .railwayignore

# 2. Preferir GitHub auto-deploy (push to main) em vez de railway up
```

---

## 4. Resolucao

### 4.1 Rollback Imediato (se deploy quebrou producao)

```bash
# Railway CLI
railway rollback --service bidiq-backend

# Verificar se rollback funcionou
railway status
curl -s https://api.smartlic.tech/health/ready | jq '.ready'
```

### 4.2 Redeploy Forcado (se deploy esta stuck em BUILD)

```bash
# Cancelar deploy atual e redeploy
railway redeploy --service bidiq-backend -y

# Se ainda falhar: verificar build logs
railway logs --service bidiq-backend --build | tail -30
```

### 4.3 Cache Bust (se precisa forçar rebuild mesmo sem mudancas)

```bash
# Atualizar timestamp no Dockerfile
echo "LABEL build.timestamp=$(date +%s)" >> backend/Dockerfile
# ou
railway variables set CACHEBUST=$(date +%s) --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

### 4.4 Verificacao Pos-Resolucao

```bash
# Health check
curl -s https://api.smartlic.tech/health/ready | jq '.'

# Deploy recente bem sucedido?
railway deployments --service bidiq-backend | head -5

# Testar busca
curl -s -X POST https://api.smartlic.tech/v1/buscar \
  -H "Content-Type: application/json" \
  -d '{"ufs": ["SC"], "dataInicial": "2026-06-10", "dataFinal": "2026-06-15"}' | jq '.status'
```

---

## 5. Prevencao

### Git Workflow
- **NUNCA** executar `railway up` de dentro de `backend/` ou `frontend/`
- **NUNCA** executar `railway up` se o repo exceder ~300MB (usar GitHub auto-deploy)
- Preferir GitHub auto-deploy (push to main trigga deploy com estrutura correta)
- Manter `.railwayignore` atualizado

### CI Gates
- `audit-prod-env.yml` — detecta debug flags em prod (diario)
- `migration-check.yml` — verifica migrations pendentes
- Validar billing do GitHub Actions semanalmente

### Dockerfile
```dockerfile
# Sempre incluir cache bust
ARG CACHEBUST=1
LABEL build.timestamp=${CACHEBUST}
```

### Railway Config
- `RAILWAY_SERVICE_ROOT_DIRECTORY` configurado corretamente para cada servico
- `railway.toml` presente em cada servico com health check configurado

---

## 6. Referencias

- `incident-response.md` secao 3.1 — Backend DOWN (502)
- `docs/runbooks/rollback-procedure.md` — Procedimento completo de rollback
- CLAUDE.md secao "Railway Deploy Rules" — Regras de deploy Railway
- CRIT-080: SIGSEGV + GHA billing fix
- Railway Status: https://status.railway.app
- Railway Docs: https://docs.railway.app
