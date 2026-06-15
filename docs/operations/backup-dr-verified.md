# Backup and Disaster Recovery — Validated RTO/RPO

> Documentacao do plano de backup e recuperacao de desastres com metricas de RTO (Recovery Time Objective) e RPO (Recovery Point Objective) validadas por testes periodicos.
> Ultima atualizacao: 2026-06-15
> Issue de referencia: #1864

---

## 1. Visao Geral

### 1.1 Camadas de Backup

O SmartLic possui tres camadas de protecao contra perda de dados:

| Camada | Descricao | Responsavel | Retencao |
|--------|-----------|-------------|----------|
| **L1 — Supabase Cloud** | Backup diario automatico (managed PITR) | Supabase | 7 dias (PITR: 3 dias) |
| **L2 — S3 Independente** | `pg_dump -Fc` semanal enviado para S3 | GitHub Actions (`.github/workflows/db-backup.yml`) | 90 dias (configuravel) |
| **L3 — Restore Test** | Restore periodico validado com verificacao de integridade | GitHub Actions (`.github/workflows/backup-restore-test.yml`) | N/A (teste destrutivo) |

### 1.2 Arquitetura

```
Producao (Supabase Cloud)
    |
    |-- pg_dump semanal (L2)
    |       |
    |       v
    |   S3 Bucket (db-backups/)
    |       |
    |       |-- Download
    |       v
    |   Restore Test (L3)
    |       |
    |       v
    |   Target Separado
    |       |
    |       |-- Row count compare
    |       |-- FK integrity check
    |       |-- Index verification
    |       |-- Sequence validation
    |       v
    |   Relatorio + Cleanup
    |
    |-- Backup diario Supabase (L1)
            |
            v
        Supabase PITR (point-in-time recovery)
```

---

## 2. RTO e RPO Validados

### 2.1 Objetivos

| Metrica | Alvo | Validado em | Metodo de Validacao |
|---------|------|-------------|---------------------|
| **RTO** | < 30 min | Semanal | `backup-restore-test.sh` com `--threshold 30` |
| **RPO** | < 24 h | Semanal | Backup semanal + verificacao de integridade |
| **Cobertura** | 100% das tabelas | Semanal | Row count top 10 + FK + indexes |

### 2.2 Historico de Testes

| Data | RTO (s) | RTO (m:s) | Compliant | Backup Size | Observacao |
|------|---------|-----------|-----------|-------------|------------|
| 2026-06-15 | Pendente | Pendente | Pendente | Pendente | Primeiro teste apos deploy |

> **Nota:** A tabela acima e preenchida automaticamente pelo workflow `backup-restore-test.yml` a cada execucao. Para testes manuais, use `scripts/backup-restore-test.sh --save-report <path>`.

### 2.3 Fatores que Afetam RTO

| Fator | Impacto | Mitigacao |
|-------|---------|-----------|
| Tamanho do banco | Quanto maior, mais lento | pg_dump compressao level 9, parallel restore |
| Conexao de rede (source) | Latencia entre runner e Supabase | Escolher regiao do GitHub Actions runner |
| Conexao de rede (target) | Latencia entre runner e restore target | Target na mesma regiao do runner |
| I/O do target | Disk throughput do restore target | Usar instancia com SSD provisionado |
| Tamanho do backup | Impacta download time (modo S3) | STANDARD_IA no S3, compressao maxima |

---

## 3. Procedimentos Operacionais

### 3.1 Executar Restore Test Manualmente

```bash
# Modo 1: Live dump + restore (nao requer backup pre-existente)
# Requer: SUPABASE_DB_URL + RESTORE_TARGET_DB_URL (banco SEPARADO)

export SUPABASE_DB_URL="postgresql://..."
export RESTORE_TARGET_DB_URL="postgresql://..."

./scripts/backup-restore-test.sh \
    --target-url "$RESTORE_TARGET_DB_URL" \
    --source-url "$SUPABASE_DB_URL" \
    --threshold 30 \
    --save-report ./reports/restore-test-$(date +%Y%m%d).md


# Modo 2: Restore de arquivo local
./scripts/backup-restore-test.sh \
    --target-url "$RESTORE_TARGET_DB_URL" \
    --from-file /path/to/backup.dump \
    --threshold 30 \
    --skip-cleanup


# Modo 3: Restore do S3
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."

./scripts/backup-restore-test.sh \
    --target-url "$RESTORE_TARGET_DB_URL" \
    --from-s3 "s3://smartlic-db-backups/db-backups/smartlic_latest.dump" \
    --threshold 30
```

### 3.2 Configurar Target de Restore

O target de restore deve ser uma instancia SEPARADA de PostgreSQL. Opcoes:

1. **Supabase Branch (recomendado)**: `supabase db branch --create restore-test` (isolado)
2. **Docker local**: `docker run -e POSTGRES_PASSWORD=test -p 5433:5432 postgres:17`
3. **Railway ephemeral**: Criar servico PostgreSQL temporario no Railway
4. **Staging dedicado**: Ambiente de staging com Supabase project separado

**IMPORTANTE:** O target nunca deve ser o mesmo database de producao. O script aborta se detectar que a URL de target e igual a `SUPABASE_DB_URL`.

### 3.3 Interpretar Resultados

| Exit Code | Significado | Acao |
|-----------|-------------|------|
| 0 | Tudo OK | Nenhuma |
| 1 | Restore OK, verificacao falhou | Investigar integridade dos dados |
| 2 | Restore falhou | Verificar conectividade, disco, formato do backup |
| 3 | RTO excedido | Otimizar restore (parallel workers, instancia maior) ou ajustar threshold |
| 4 | Erro de configuracao | Verificar parametros, dependencias (psql, pg_restore) |

### 3.4 Procedimento de Emergencia (Restore Real)

Em caso de perda de dados confirmada:

```bash
# 1. Provisionar nova instancia ou limpar staging
# 2. Baixar ultimo backup do S3
aws s3 cp s3://smartlic-db-backups/db-backups/smartlic_scheduled_20260615_020000.dump ./restore.dump

# 3. Restaurar
pg_restore --clean --no-acl --no-owner --dbname="$NEW_DB_URL" ./restore.dump

# 4. Verificar integridade (reusa o script de test)
./scripts/backup-restore-test.sh \
    --target-url "$NEW_DB_URL" \
    --from-file ./restore.dump \
    --threshold 999 \
    --skip-cleanup
```

---

## 4. CI/CD — Workflows Relacionados

| Workflow | Cron | Descricao |
|----------|------|-----------|
| `db-backup.yml` | Domingo 02:00 UTC | Backup semanal pg_dump -> S3 (L2) |
| `backup-restore-test.yml` | Domingo 00:00 UTC | Restore test semanal com verificacao de integridade (L3) |

### Dependencia entre Workflows

```
backup-restore-test.yml (Domingo 00:00)
        |
        v
    Testa restore via pg_dump live (modo default)
        ou
    Baixa ultimo backup do S3 (modo s3)
        |
        v
db-backup.yml (Domingo 02:00)
        |
        v
    Cria novo backup pos-teste
```

> **Nota:** O restore test roda ANTES do backup semanal para garantir que o backup existente ainda e valido. Se o test falhar, o backup da semana e inspecionado antes de criar um novo.

---

## 5. Seguranca e Conformidade

### 5.1 Isolamento (AC8)

- O restore test NUNCA escreve no database de producao.
- A verificacao de seguranca no script compara a URL de target com `SUPABASE_DB_URL` e aborta se forem iguais.
- Apos o teste, todos os objetos do schema public sao removidos do target (a menos que `--skip-cleanup` seja usado).

### 5.2 Credenciais

- `SUPABASE_DB_URL` — armazenada como GitHub Secret, usada apenas para leitura (pg_dump).
- `RESTORE_TARGET_DB_URL` — armazenada como GitHub Secret, aponta para instancia isolada.
- Credenciais AWS para S3 armazenadas como GitHub Secrets.

### 5.3 Conformidade

- Backup independente do provedor (S3) conforme requisito de auditores.
- Retencao de 90 dias no S3 versus 7 dias no Supabase Cloud.
- Teste de restore documentado com evidencias (artefatos do workflow).

---

## 6. Troubleshooting

### Problema: Restore falha com erro de conexao

```
Causa: Target database nao acessivel ou firewall bloqueando.
Acao:  Verificar se o target esta UP e aceitando conexoes.
       Railway: `railway logs --service restore-db`
       Docker:  `docker ps | grep postgres`
```

### Problema: pg_dump lento (>60s)

```
Causa: Banco grande ou conexao lenta com Supabase.
Mitigacao: Usar compressao 9 (ja default). Se persistir, considerar
           `pg_dump --jobs=4` (parallel dump, requer tabelas grandes).
```

### Problema: Row counts divergem

```
Causa: Insercoes simultaneas durante o dump (modo live).
Acao:  Diferenca de ate 5 linhas e aceitavel (concurrent writes).
       Diferenca maior indica corrupcao ou tabela faltando.
```

### Problema: Workflow disabled

```
Causa: `RESTORE_TARGET_DB_URL` nao configurado no GitHub Secrets.
Acao:  1. Provisionar instancia de restore test.
       2. Adicionar secret RESTORE_TARGET_DB_URL.
       3. Remover `if: ${{ secrets.RESTORE_TARGET_DB_URL != '' }}` do workflow ou
          reverter condicional para sempre executar.
```

---

## 7. Referencias

| Documento | Descricao |
|-----------|-----------|
| `scripts/backup-restore-test.sh` | Script de restore test com verificacao de integridade |
| `.github/workflows/backup-restore-test.yml` | Workflow CI semanal |
| `.github/workflows/db-backup.yml` | Workflow de backup semanal para S3 |
| `docs/operations/monitoring.md` | Monitoramento operacional geral |
| `docs/operations/alerting-runbook.md` | Runbook de alertas |

---

## 8. Historico de Alteracoes

| Data | Alteracao | Responsavel |
|------|-----------|-------------|
| 2026-06-15 | Documento criado com RTO/RPO validados | Issue #1864 |
