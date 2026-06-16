# Data Retention Policy

> **Documento:** GAP-005 (#1877)
> **Ultima revisao:** 2026-06-15
> **Responsavel:** DevOps/Backend

## Resumo Executivo

100% das tabelas temporais do SmartLic possuem politica de retencao documentada.
Tabelas com purge automatizado sao monitoradas via Prometheus (`data_purge_rows_total`)
e CI semanal verifica se os purges estao rodando dentro do prazo.

## Politicas por Tabela

| Tabela | Coluna Temporal | Retencao | Purge | Responsavel | Status |
|--------|----------------|----------|-------|-------------|--------|
| `pncp_raw_bids` | `data_publicacao` | 400 dias | Hard-delete via pg_cron (`purge-old-bids`, 07 UTC) | pg_cron + ingestion | Implementado |
| `search_sessions` | `created_at` | Stale: 1h, Old: 7d | Soft stale + hard delete terminal | `session_cleanup.py` | Implementado |
| `search_results_store` | `expires_at` | TTL (12h) | Hard-delete via cron loop (6h) | `session_cleanup.py` | Implementado |
| `search_results_cache` | `created_at` | 5 mais recentes por user | pg_cron (`cleanup-search-results-store`, 6h) | pg_cron | Implementado |
| `stripe_webhook_events` | `processed_at` | 90 dias | Hard-delete via cron loop (24h) | `billing.py` (HARDEN-028) | Implementado |
| **`trial_email_log`** | `sent_at` | **180 dias** | **Hard-delete via `data_retention.py`** | **`data_retention.py`** | **GAP-005 (este PR)** |
| **`messages`** | `created_at` | **365 dias** | **Hard-delete via `data_retention.py`** | **`data_retention.py`** | **GAP-005 (este PR)** |
| **`ingestion_checkpoints`** | `completed_at` / `started_at` | **30 dias** | **Hard-delete (completed/failed only)** | **`data_retention.py`** | **GAP-005 (este PR)** |
| `analytics_events` | N/A (Mixpanel) | Gerenciado pelo Mixpanel | N/A — servico externo | Mixpanel | Documentado |
| `pncp_supplier_contracts` | `data_assinatura` | Mantido permanentemente (SEO) | Sem purge (fonte de dados SEO) | — | Planejado |

### Legenda

- **Implementado**: Purge automatizado rodando em producao
- **GAP-005 (este PR)**: Purge adicionado neste PR (#1877)
- **Documentado**: Politica definida, mas sem purge automatizado
- **Planejado**: Politica a ser definida em iteracao futura

## Detalhamento por Tabela

### `pncp_raw_bids` — 400 dias
- **Coluna:** `data_publicacao`
- **Purge:** pg_cron `purge-old-bids` diario as 07:00 UTC
- **Justificativa:** STORY-OBS-001 — necessario para observatorio/SEO programmatic
- **Monitoramento:** STORY-1.1 pg_cron health monitor (Sentry alert se >25h stale)

### `search_sessions` — Stale 1h / Old 7d
- **Coluna:** `created_at`
- **Stale:** Sessoes em `in_progress`/`created`/`processing` > 1h → `timed_out`
- **Old:** Sessoes `failed`/`timeout`/`timed_out` > 7d → hard delete
- **Responsavel:** `backend/jobs/cron/session_cleanup.py::cleanup_stale_sessions()`

### `search_results_store` — TTL 12h
- **Coluna:** `expires_at`
- **Purge:** Loop a cada 6h deleta registros com `expires_at < now()`
- **Responsavel:** `backend/jobs/cron/session_cleanup.py::cleanup_expired_results()`

### `search_results_cache` — 5 mais recentes por usuario
- **Coluna:** `created_at`
- **Purge:** pg_cron `cleanup-search-results-store` a cada 6h
- **Politica:** Mantem apenas as 5 entradas mais recentes por `user_id`
- **Historico:** Substituiu trigger per-INSERT (DEBT-IO-BUDGET)

### `stripe_webhook_events` — 90 dias
- **Coluna:** `processed_at`
- **Purge:** Loop a cada 24h via `billing.py::purge_old_stripe_events()`
- **Justificativa:** STORY-307 audit trail requirement
- **Nota:** Usa DELETE batch via pg_cron function `purge_old_stripe_webhook_events()`

### `trial_email_log` — 180 dias (GAP-005)
- **Coluna:** `sent_at`
- **Purge:** Loop diario via `data_retention.py::purge_trial_email_log()`
- **Justificativa:** Historico de trials antigos nao e necessario apos 6 meses

### `messages` — 365 dias (GAP-005)
- **Coluna:** `created_at`
- **Purge:** Loop diario via `data_retention.py::purge_messages()`
- **Conversas:** `conversations` com `last_message_at` > 365d tambem sao removidas
- **Justificativa:** Mensagens de suporte com mais de 1 ano sao raramente consultadas;
  usuarios podem exportar via LGPD antes do purge

### `ingestion_checkpoints` — 30 dias (GAP-005)
- **Coluna:** `completed_at` (fallback: `started_at`)
- **Purge:** Loop diario via `data_retention.py::purge_ingestion_checkpoints()`
- **Escopo:** Apenas checkpoints com status `completed` ou `failed`
- **Justificativa:** Checkpoints de ingestao com mais de 30 dias nao sao relevantes
  para restart de crawlers

### `analytics_events` (Mixpanel)
- **Tipo:** Servico externo (Mixpanel SDK)
- **Retencao:** Gerenciada pelo Mixpanel (plano Growth: ilimitado)
- **Agregacao:** Nao ha tabela local `analytics_events`
- **Nota:** Se agregacao local for necessaria no futuro, usar padrao `analytics_daily`

### `pncp_supplier_contracts` — Permanente
- **Coluna:** `data_assinatura`
- **Purge:** Nao previsto
- **Justificativa:** Fonte de dados para SEO programmatic (10k+ paginas ISR)
  e contratos historicos sao valor permanente para usuarios B2G

## Metricas Prometheus

| Metrica | Tipo | Labels | Descricao |
|---------|------|--------|-----------|
| `data_purge_rows_total` | Counter | `table` | Linhas purgadas por tabela |
| `data_purge_bytes_freed` | Gauge | — | Estimativa de bytes liberados |
| `data_purge_duration_seconds` | Histogram | — | Duracao do ciclo de purge |

## CI Semanal

O script `scripts/audit-data-retention.sh` verifica:
1. Se os purges estao rodando (checa idade maxima de registros por tabela)
2. Se alguma tabela excedeu 2x o periodo de retencao sem purge
3. Alerta via exit code non-zero se alguma tabela esta fora da politica

Agendamento: `.github/workflows/audit-data-retention.yml` (todo domingo as 09:00 UTC)
