# ADR-027: Endpoint Admin de Status de Retenção de Dados

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @dev
**Issue:** #1877 AC2

## Context

O cron de purge de dados (`run_data_retention_purge()`) executa automaticamente via ARQ + pg_cron, mas não havia visibilidade sobre sua última execução. Em incidentes de storage, operadores precisavam verificar rapidamente se o purge rodou, quantas linhas foram removidas e se houve erros. Sem um endpoint, a única forma era consultar Redis manualmente.

## Decision

Criar `GET /v1/admin/data-retention/status` que lê de 4 Redis keys escritas pelo purge (`data_retention:last_run:{table}`, `last_rows`, `last_error`, `last_duration`). 3 tabelas monitoradas: `trial_email_log`, `messages`, `ingestion_checkpoints`.

## Alternatives Considered

1. **Tabela de log no Supabase:** Mais durável que Redis, mas adiciona escrita extra no hot path do purge e requer migration.
2. **Métricas Prometheus:** Ótimas para dashboards, mas não carregam detalhes de última execução por tabela.

## Consequences

- **Positivo:** Diagnóstico rápido sem acesso Redis; graceful degradation se Redis estiver indisponível (retorna `status: "error"` com detail, não 500).
- **Negativo:** Tabelas monitoradas hardcoded (adicionar tabela requer code change); sem endpoint para dry-run manual.
- **Mitigação:** Fase futura pode migrar para tabela de log + endpoint de dry-run.

## References

- `backend/routes/admin_data_retention.py` (125 LOC)
- `backend/data_retention.py` (run_data_retention_purge)
- Redis keys: `data_retention:last_run:{table}` (TTL 7d)
