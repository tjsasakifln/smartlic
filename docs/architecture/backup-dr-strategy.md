# Estrategia de Backup e Disaster Recovery (#1787)

## 1. Objetivos de Recuperacao (RPO e RTO)

| Metrica | Valor | Definicao |
|---------|-------|-----------|
| **RPO (Recovery Point Objective)** | 1 hora | Perda maxima de dados aceitavel em caso de desastre |
| **RTO (Recovery Time Objective)** | 4 horas | Tempo maximo para restauracao completa do sistema |

Estes valores foram definidos considerando o estagio atual do produto (pre-revenue beta) e a criticidade do servico para usuarios B2G. A medida que o produto amadurecer, RPO e RTO devem ser revistos para prazos mais agressivos.

## 2. Stack Atual e Status de Backup

### 2.1 Supabase (PostgreSQL)

**Backup atual:** Gerenciado pelo provedor Supabase Cloud.

| Recurso | Status | Detalhes |
|---------|--------|----------|
| Daily snapshots | Habilitado | Snapshots diarios automaticos com 7 dias de retencao |
| Point-in-Time Recovery (PITR) | Disponivel, nao ativado | Exige plano Pro ou superior. Permite restore para qualquer ponto nos ultimos 2 dias. |
| Wal-G / WAL archiving | Gerido pela Supabase | Arquivos WAL retidos conforme politica do plano contratado. |

**Schema versionado:** `supabase/migrations/` contem o schema completo (source of truth). ~183 migrations com `.down.sql` emparelhadas (STORY-6.2). Qualquer restore de dados requer reaplicacao do schema a partir das migrations.

**Dados criticos armazenados no Supabase:**

| Categoria | Tabelas | Volatilidade |
|-----------|---------|-------------|
| Autenticacao | `auth.users`, `auth.identities`, `auth.sessions`, `auth.mfa_factors` | Alta (login/logout constante) |
| Perfis | `profiles` | Baixa (alteracao rara) |
| Buscas | `search_history`, `search_results_cache`, `search_store` | Media |
| Pipeline | `pipeline_items`, `pipeline_movements` | Media |
| InMail | `messages`, `message_conversations` | Baixa |
| Ingestao | `pncp_raw_bids` (~1.5M rows), `pncp_supplier_contracts` (~2M+ rows) | Alta (ingestao diaria) |
| Checkpoints ingestao | `ingestion_checkpoints`, `ingestion_runs` | Alta |
| Assinaturas | `subscriptions`, `user_subscriptions`, `plan_billing_periods` | Baixa |
| Feedback | `feedback_classification` | Baixa |
| Health monitoring | `health_checks`, `incidents` | Alta |
| Onboarding | `onboarding_progress` | Baixa |
| Sessao | `user_sessions` | Media |

### 2.2 Redis (Cache)

**Status:** Efemero — sem backup necessario.

Redis armazena exclusivamente dados temporarios e cache. Todos os dados no Redis podem ser reconstruidos a partir das fontes primarias (Supabase / APIs externas):

| Funcao | Reconstrucao apos perda |
|--------|------------------------|
| Cache de resultados de busca (L2) | Reconstruido via SWR na proxima requisicao |
| Rate limiter (token bucket) | Resetado — todos os limites reiniciam |
| SSE state tracking | Perdido — novas conexoes comecam do zero |
| ARQ job queue | Jobs enfileirados sao perdidos (jobs sao idempotentes) |
| Distributed locks | Liberados — proxima execucao do cron adquire novo lock |
| Circuit breaker state | Fallback para estado local em memoria |
| Auth cache (L2) | Reconstruido via L1 + Supabase na proxima requisicao |
| LLM budget tracking | Budget enforcement desativado temporariamente |

Cenario de degradacao completo documentado em `docs/architecture/redis-failure-modes.md`.

### 2.3 Railway (Infraestrutura)

**Status:** Infra-as-code — reconstruivel.

Toda a configuracao de infraestrutura esta versionada:

| Recurso | Localizacao | Reconstrucao |
|---------|-------------|-------------|
| Build config | `railway.toml` (backend + frontend) | `railway up` ou GitHub auto-deploy |
| Docker image | `backend/Dockerfile`, `frontend/Dockerfile` | Build automatico no deploy |
| Runtime env vars | Dashboard Railway + `.env.example` | Reaplicar manualmente |
| CI/CD pipelines | `.github/workflows/deploy.yml` | Gatilho automatico no push para `main` |

**Excecao:** Variaveis de ambiente sensiveis (API keys, tokens) nao estao versionadas. Devem ser reaplicadas manualmente via Railway dashboard ou CLI (`railway variables set`).

### 2.4 Codigo Fonte

| Recurso | Backup | Observacao |
|---------|--------|------------|
| Repositorio Git | GitHub (remoto) + clones locais | Source of truth |
| Branches | Todas no GitHub | `main` protegida com code review obrigatorio |
| Commits | Imutaveis apos push | Historico completo disponivel |
| Issues/PRs | GitHub nativo | Export manual via API se necessario |

## 3. Procedimento de Restore

### 3.1 Supabase Point-in-Time Recovery (PITR)

**Pre-requisito:** Plano Pro ou superior com PITR ativado.

```bash
# Via Supabase Dashboard:
# 1. Database > Backups > Point-in-Time Recovery
# 2. Selecionar timestamp desejado (ate 2 dias retroativos)
# 3. Confirmar restore (cria novo projeto ou substitui o atual)

# Via Supabase CLI (quando disponivel):
npx supabase db pull --project-ref <ref>
# Restore aponta para o backup, nao para o projeto ativo
```

**Apos restore:**
1. Verificar integridade dos dados: `SELECT count(*)` nas tabelas principais
2. Verificar autenticacao: tentar login com usuario de teste
3. Verificar RLS policies: consultar como usuario nao-admin
4. Reaplicar migrations pendentes se o restore for de data anterior ao deploy mais recente:
   ```bash
   npx supabase db push --include-all
   ```

### 3.2 Restore a partir de Daily Snapshot

```bash
# Via Supabase Dashboard:
# 1. Database > Backups > Backups disponiveis
# 2. Selecionar snapshot desejado (ate 7 dias retroativos)
# 3. Criar novo projeto a partir do snapshot
# 4. Reconfigurar URL e chaves no Railway
```

**Nota:** Snapshots sao de todo o projeto (incluindo `auth` schema). Restauracao substitui completamente o banco de dados.

### 3.3 Restore Railway (Infraestrutura)

```bash
# Se o servico Railway precisar ser recriado do zero:
# 1. Criar novo projeto no Railway
# 2. Conectar repositorio GitHub
# 3. Configurar variaveis de ambiente (consultar .env.example)
# 4. Fazer deploy

# Deploy forcado a partir da CLI:
railway up -d   # Do diretorio raiz do monorepo
```

## 4. Cenarios de Disaster Recovery

### 4.1 Perda de Regiao Supabase

**Impacto:** Indisponibilidade total do banco de dados. Sistema incapacitado de servir requisicoes.

**Sintomas:**
- Health check `/health/ready` retorna `unhealthy`
- Todas as queries ao Supabase falham com erro de conexao
- Frontend exibe erro de carregamento

**Procedimento:**
1. **Verificar status:** https://status.supabase.com
2. **Aguardar restauracao:** Supabase gerencia a replicacao entre regioes
3. **Se prolongado (>2h):** Contatar suporte Supabase (plano Pro tem suporte prioritario)
4. **Plano B (emergencia):** Restaurar a partir do ultimo snapshot via Suporte em nova regiao se disponivel

**Mitigacao:** Nao ha replicacao cross-region configurada atualmente. Tabelas de cache (`search_results_cache`) sao perdidas, mas serao reconstruidas via ingestao + DataLake queries.

### 4.2 Exclusao Acidental de Dados

**Cenario:** Query maliciosa ou erro humano (ex: `DELETE` sem `WHERE`, `DROP TABLE`).

**Procedimento:**
1. **Imediato:** Identificar o comando executado e timestamp aproximado
2. **PITR:** Se dentro da janela de 2 dias, restaurar para timestamp anterior ao incidente
   - Criar projeto separado para extracao dos dados perdidos
   - Exportar apenas as tabelas afetadas
   - Importar de volta no projeto original
3. **Snapshot:** Se fora da janela PITR, restaurar snapshot mais recente
   - Perda de dados entre o snapshot e o incidente (ate 24h)
4. **Verificar integridade:** Validar que dados restaurados nao corromperam relacoes existentes

**Prevencao:**
- RLS policies previnem exclusao em massa por usuarios nao-admin
- Conexoes service_role devem ser usadas com cautela (apenas em worker jobs)
- `SUPABASE_SERVICE_ROLE_KEY` restrita a variaveis de ambiente Railway

### 4.3 Ataque Ransomware / Comprometimento de Credenciais

**Impacto:** Potencial criptografia/exclusao de dados se atacante obtiver acesso ao Supabase.

**Procedimento:**
1. **Isolamento:** Rotacionar imediatamente `SUPABASE_SERVICE_ROLE_KEY` e `SUPABASE_ANON_KEY`
   ```bash
   railway variables set SUPABASE_SERVICE_ROLE_KEY=<nova_chave>
   ```
2. **Avaliacao:** Verificar logs de auditoria do Supabase (queries executadas, IPs de origem)
3. **Restore:** Aplicar PITR ou snapshot para timestamp anterior ao comprometimento
4. **Notificacao:** Notificar usuarios afetados se dados pessoais foram comprometidos (LGPD)

**Prevencao:**
- Service role key NUNCA exposta ao frontend ou em logs
- Todas as queries de usuario passam por RLS (nunca service_role)
- API keys rodam exclusivamente em ambiente server-side

### 4.4 Perda do Repositorio GitHub

**Impacto:** Impossibilidade de deploy, perda de codigo fonte.

**Mitigacao:**
- Repositorio clonado localmente por cada desenvolvedor
- Historico de commits distribuido (cada clone tem copia completa)
- GitHub mantem backups internos (disponivel via GitHub Support)

**Procedimento:**
1. Recriar repositorio no GitHub
2. Fazer push de clone local:
   ```bash
   git remote add origin git@github.com:<org>/<repo>.git
   git push -u origin main --all
   ```
3. Verificar GitHub Actions (secrets precisam ser reconfiguradas):
   ```bash
   gh secret list
   gh secret set <KEY> --body "<value>"
   ```

## 5. Teste de Restore (Schedule Trimestral)

### Objetivo

Validar que o procedimento de restore funciona dentro do RTO de 4 horas.

### Criterios de Sucesso

1. Restore completo do banco (dados + schema) em ambiente isolado
2. Aplicacao backend consegue conectar e servir requisicoes
3. Dados de autenticacao (login de usuario) funcionam
4. Dados de producao (buscas, pipeline) estao presentes e com integridade

### Procedimento de Teste

```bash
# Trimestralmente (meses 3, 6, 9, 12):
# 1. Criar projeto Supabase temporario a partir do snapshot
npx supabase projects create --name "dr-test-YYYY-MM-DD"

# 2. Aplicar migrations ate a data do snapshot
npx supabase db push --project-ref <test-ref>

# 3. Configurar ambiente Railway temporario
railway variables set SUPABASE_URL=<test-url> SUPABASE_SERVICE_ROLE_KEY=<test-key>

# 4. Executar health checks
curl -f https://<temp-url>/health/ready

# 5. Verificar dados criticos
# - Usuario admin consegue login
# - Busca retorna resultados
# - Pipeline items estao presentes

# 6. Destruir ambiente de teste
railway down
npx supabase projects delete <test-ref>
```

**Documentacao do teste:** Cada execucao deve gerar relatorio sucinto com:
- Timestamp do snapshot utilizado
- Duracao total do procedimento
- Problemas encontrados e resolucoes
- Aprovacao final (PASS/FAIL)

### Runbook de Referencia

Consultar `docs/runbooks/incident-response.md` para procedimento completo de resposta a incidentes, incluindo arvore de decisao para acionamento do restore.

## 6. Custos

| Componente | Custo | Detalhes |
|------------|-------|----------|
| Supabase daily snapshots | Incluso no plano | Retencao de 7 dias no plano Pro |
| Supabase PITR | Custo adicional | Requer upgrade de plano para ativar |
| Armazenamento WAL | Incluso | Gerenciado pela Supabase |
| Railway rebuild | Sem custo adicional | Infra-as-code: deploy recria do zero |
| GitHub | Incluso | Backup distribuido do repositorio |
| Ambiente de teste DR | Custo marginal | Projeto Supabase temporario + Railway |

**Recomendacao:** Ativar PITR no plano Pro assim que o orcamento permitir. O custo adicional e justificado pela reducao do RPO de 24h (snapshot) para <1h (PITR).

## 7. Melhorias Futuras

| Item | Prioridade | Esforco | Beneficio |
|------|-----------|---------|-----------|
| Ativar PITR no Supabase | Alta | Baixo (configuracao) | RPO de 24h -> 1h |
| Automatizar teste de restore trimestral | Media | Medio (script CI) | Validacao regular sem esforco manual |
| Documentar runbook de DR detalhado | Media | Baixo | Resposta mais rapida em incidente |
| Configurar replicacao cross-region Supabase | Baixa | Alto (mudanca de plano) | Alta disponibilidade geografica |
| Backup automatizado de env vars Railway | Baixa | Baixo (script) | Evitar configuracao manual apos rebuild |
| Criptografia de backups em repouso | Ja implementado | — | Supabase gerencia nativamente |
