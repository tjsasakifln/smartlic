# Incident Playbook — SmartLic

> AC6: Procedimentos de resposta por tipo de alerta, contatos, e rollback.
> Combinado com `on-call.md` para escalation e `alerting-runbook.md` para detalhes de alertas.
> Ultima atualizacao: 2026-06-15 | Issue: #1865

---

## 1. Overview do Sistema de Alertas

```
Severity    Routing             SLA First Response     Escalation
───────     ──────────           ──────────────────     ──────────
SEV1        PagerDuty + Slack    5 min                 5min → Secondary, 15min → Escalation
SEV2        Slack #alerts       15 min                 N/A (not escalated automatically)
SEV3        Sentry + daily      24 h (batch)           N/A (daily digest review)
```

---

## 2. Playbook por Tipo de Alerta

### 2.1 SEV1 — Backend DOWN (/health/ready fails)

**Trigger:** `/health/ready` retorna != 200 por > 60s.

**Diagnostico (2 min):**
1. Verificar Railway logs:
   ```bash
   railway logs --tail | tail -50
   ```
2. Verificar health endpoint:
   ```bash
   curl -s https://bidiq-backend-production.up.railway.app/health/ready | python -m json.tool
   ```
3. Verificar Railway dashboard: CPU/Memory/Restarts.

**Acao:**
1. **Se restart loop:** Railway CLI restart forcado:
   ```bash
   railway redeploy --service bidiq-backend -y
   ```
2. **Se deploy quebrado:** Rollback para versao anterior:
   ```bash
   railway rollback --service bidiq-backend
   ```
3. **Se dependencia externa (Supabase/Redis DOWN):** Verificar status pages, aguardar recovery.
   - Supabase: https://status.supabase.com/
   - Redis (Upstash): https://status.upstash.com/

**Contato:** Tiago Sasaki (PagerDuty ou telefone).

**Rollback procedure:**
```bash
# Railway rollback to last known good version
railway rollback --service bidiq-backend -y
# Verify health
sleep 30 && curl -s https://smartlic.tech/health/ready
```

---

### 2.2 SEV1 — 5xx Error Rate > 5%

**Trigger:** Erro 5xx excede 5% das requisicoes em janela de 5 min.

**Diagnostico (3 min):**
1. Sentry dashboard: https://confenge.sentry.io/issues/?project=smartlic-backend
2. Identificar endpoint com maior taxa de erro.
3. Verificar se e erro novo ou regressao.

**Acao:**
1. **Erro novo:** Corrigir com hotfix:
   ```bash
   git checkout -b fix/issue-description
   # fix → test → commit
   git push origin fix/issue-description
   # Criar PR e mergear
   ```
2. **Regressao:** Rollback Railway para versao anterior.
3. **Transiente:** Se for timeout/RateLimit, monitorar por 5 min.

**Contato:** Dev responsavel pelo modulo afetado.

---

### 2.3 SEV1 — Stripe Webhook Failure

**Trigger:** Stripe webhook retorna erro ou timeout.

**Diagnostico (2 min):**
1. Verificar ultimos webhooks no Stripe Dashboard:
   ```bash
   stripe logs --webhook_endpoint=smartlic
   ```
2. Verificar Railway logs para `stripe_webhook`:
   ```bash
   railway logs --tail | grep -i "stripe\|webhook"
   ```

**Acao:**
1. Verificar se Stripe esta operacional: https://status.stripe.com/
2. Se Stripe OK: verificar assinatura do webhook (endpoint secret expirado?)
3. Se erro de assinatura: reconfigurar `STRIPE_WEBHOOK_SECRET`:
   ```bash
   railway variables set STRIPE_WEBHOOK_SECRET=whsec_...
   ```
4. Reprocessar webhooks falhos no Stripe Dashboard.

**Contato:** Tiago Sasaki (billing critical).

---

### 2.4 SEV2 — Latencia p95 > 2s

**Trigger:** Latencia p95 das requisicoes excede 2s.

**Diagnostico (5 min):**
1. Verificar Prometheus metrics:
   ```bash
   curl -s https://bidiq-backend-production.up.railway.app/metrics | grep duration_seconds
   ```
2. Verificar qual endpoint esta lento.
3. Verificar datalake query performance:
   ```bash
   railway run python -c "from supabase_client import get_supabase; print(get_supabase().rpc('search_datalake', {...}).execute())"
   ```

**Acao:**
1. **Datalake lento:** Verificar Supabase slow queries dashboard.
2. **API externa lenta:** Circuit breaker deve auto-recuperar.
3. **Cache frio:** Aguardar warming, verificar cache hit rate.
4. **Se persistente (> 15 min):** Reduzir concurrency:
   ```bash
   railway variables set PNCP_BATCH_SIZE=3 PNCP_BATCH_DELAY_S=3.0
   ```

---

### 2.5 SEV2 — Redis DOWN > 5min

**Trigger:** Redis indisponivel por mais de 5 minutos.

**Diagnostico (2 min):**
1. Verificar Redis status: Railway dashboard → Redis service.
2. Testar conexao:
   ```bash
   railway run python -c "import redis; r=redis.from_url('REDIS_URL'); r.ping()"
   ```

**Acao:**
1. **Se Railway Redis:** Reiniciar servico Redis no Railway.
2. **Se Upstash:** Verificar https://status.upstash.com/
3. **Fallback:** App funciona em degradado sem Redis (cache L1 InMemory apenas).

---

### 2.6 SEV2 — API Quota Exhaustion

**Trigger:** OpenAI ou PNCP API quota esgotada.

**Diagnostico (1 min):**
1. Verificar error log: `railway logs --tail | grep -i "quota\|rate_limit\|429"`
2. Verificar OpenAI billing: https://platform.openai.com/account/usage

**Acao:**
1. **OpenAI quota:** Aumentar limite no OpenAI dashboard ou reduzir consumo.
2. **PNCP quota:** Rate limiting e normal, circuit breaker gerencia.
3. **Temporario:** Desabilitar LLM zero-match:
   ```bash
   railway variables set LLM_ZERO_MATCH_ENABLED=false
   ```

---

### 2.7 SEV3 — Cache Hit Rate < 50%

**Trigger:** Cache hit rate abaixo de 50% na ultima hora.

**Diagnostico:**
1. Verificar metricas de cache:
   ```bash
   curl -s https://bidiq-backend-production.up.railway.app/metrics | grep cache_hit
   ```

**Acao:**
1. Verificar se warming jobs estao rodando.
2. Verificar se TTLs estao configurados corretamente.
3. Geralmente auto-corrige apos periodo de carga normal.

---

### 2.8 SEV3 — DB Pool > 85%

**Trigger:** Pool de conexoes do Supabase acima de 85%.

**Diagnostico:**
1. Supabase Dashboard → Database → Connection pool.
2. Verificar se ha queries lentas ocupando conexoes.

**Acao:**
1. Identificar e matar queries lentas no Supabase:
   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%'
   ORDER BY duration DESC;
   ```
2. Se necessario: aumentar pool size no Supabase.

---

### 2.9 SEV3 — Cron Job Atrasado > 1h

**Trigger:** Cron job nao executou no horario esperado (> 1h de atraso).

**Diagnostico:**
1. Verificar cron status: `GET /v1/admin/cron-status`
2. Verificar worker logs: `railway logs --tail | grep "cron\|arq"`

**Acao:**
1. **Worker offline:** Reiniciar worker service no Railway.
2. **Job travado:** Verificar se ha lock stuck no Redis:
   ```bash
   railway run python -c "import redis; r=redis.from_url('REDIS_URL'); print(r.keys('*lock*'))"
   ```
3. **Se lock stuck:** Remover chave do Redis:
   ```bash
   railway run python -c "import redis; r=redis.from_url('REDIS_URL'); r.delete('lock:<jobname>')"
   ```

---

## 3. Matriz de Contatos

| Tipo de Alerta | Contato Primario | Contato Secundario | Canal Preferido |
|----------------|-----------------|--------------------|---------------|
| Backend DOWN | On-call primary | Tiago Sasaki | PagerDuty |
| 5xx Rate | On-call primary | Dev responsavel | Slack #incident-response |
| Stripe Failure | Tiago Sasaki | - | Sentry → Email |
| Latencia | On-call primary | Dev responsavel | Slack #alerts |
| Redis DOWN | On-call primary | - | Slack #alerts |
| Quota Exhaustion | Tiago Sasaki | - | Slack #alerts |
| Performance Geral | On-call primary | Dev responsavel | Slack #alerts |

---

## 4. Procedimentos de Rollback

### Railway Rollback
```bash
# Listar versoes disponiveis
railway service list-deployments
# Rollback para versao especifica
railway rollback --deployment <id>
# Verificar health
curl -s https://smartlic.tech/health/ready
```

### Feature Flag Rollback
Se o incidente foi causado por feature flag:
```bash
# Desabilitar feature flag via Railway env
railway variables set FEATURE_FLAG_NAME=false
# Ou via API
curl -X POST https://smartlic.tech/v1/admin/feature-flags \
  -H "Authorization: Bearer <token>" \
  -d '{"flag": "feature_name", "enabled": false}'
```

### Database Rollback (emergencia)
```bash
# Verificar migrations aplicadas
npx supabase migration list
# Rollback da ultima migration
npx supabase db push --dry-run  # Preview
# Se necessario, reverter manualmente via .down.sql
```

---

## 5. Pos-Incidente

### Post-Mortem
Template: `docs/operations/post-mortem-template.md`
Prazo: 48h apos resolucao.

### Checklist de Fechamento
- [ ] Incidente resolvido e confirmado via health check.
- [ ] Post-mortem registrado.
- [ ] Acoes corretivas documentadas como issues.
- [ ] Runbook atualizado se procedimento mudou.
- [ ] On-call handoff atualizado se necessario.
- [ ] Comunicacao enviada aos stakeholders (se aplicavel).

---

## 6. Historico

| Data | Alteracao |
|------|-----------|
| 2026-06-15 | Documento criado com alert routing e playbooks por tipo (Issue #1865) |
