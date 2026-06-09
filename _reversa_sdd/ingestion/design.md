# Design — Módulo `ingestion`

> Gerado pelo Writer (Reversa) em 2026-06-08 | Fonte: `backend/ingestion/`

## Visão Geral
Pipeline ETL que popula o datalake PostgreSQL com editais e contratos PNCP. Agendado via ARQ cron. Camada L1 da arquitetura SmartLic.

## Arquitetura Interna

```
Scheduler (ARQ cron, 9 jobs)
  ├─ 05:00 UTC — ingestion_full_crawl_job       (4h timeout, max_tries=3)
  ├─ 11/17/23 UTC — ingestion_incremental_job     (1h timeout, max_tries=3)
  ├─ 07:00 UTC — ingestion_purge_job            (10min, max_tries=1)
  ├─ 06:00 UTC — contracts_full_crawl_job (seg/qua/sex, 8h)
  ├─ 12/18/00 UTC — contracts_incremental_job
  ├─ 08:00 UTC — enrich_entities_job (BrasilAPI)
  ├─ 09:00 UTC — enrich_municipios_job (IBGE)
  └─ (manual) — ingestion_backfill_job (10h)

Crawler
  ├─ crawl_uf_modalidade() → unidade atômica
  ├─ crawl_full() → 27 UFs × 6 mod × 7d
  ├─ crawl_incremental() → checkpoint + 3d + overlap
  └─ crawl_backfill() → 365d em chunks de 7d

Loader
  ├─ bulk_upsert(records, 500) → RPC upsert_pncp_raw_bids
  └─ purge_old_bids(400) → RPC purge_old_bids

Checkpoint
  ├─ get_last_checkpoint(uf, mod, source) → date|None
  ├─ save_checkpoint(uf, mod, data, stats)
  └─ create/complete ingestion_run
```

## Fluxo Principal: Full Crawl

1. ARQ cron dispara `ingestion_full_crawl_job` às 5 UTC
2. Verifica `DATALAKE_ENABLED`
3. Itera 27 UFs em batches de 5 com Semaphore(5), delay 2s
4. Para cada (UF, modalidade): fetch páginas → transform → upsert 500 → checkpoint → métricas
5. `complete_ingestion_run()` + ISR revalidation fire-and-forget

## Máquina de Estados (ingestion_run)
```
pending → in_progress → completed
              └→ failed → in_progress (próximo cron retry)
```

## Timeouts ARQ
| Job | Timeout | Esperado | Retries |
|-----|---------|----------|---------|
| Full crawl | 4h | 30-60min | 3 |
| Incremental | 1h | 10-20min | 3 |
| Purge | 10min | <1min | 1 |
| Backfill | 10h | 4-8h | 1 |
| Contracts full | 8h | 3-6h | 3 |

## Configuração (14 env vars)
`DATALAKE_ENABLED`, `INGESTION_FULL_CRAWL_HOUR_UTC=5`, `INGESTION_INCREMENTAL_HOURS=11,17,23`, `INGESTION_DATE_RANGE_DAYS=7`, `INGESTION_INCREMENTAL_DAYS=3`, `INGESTION_BATCH_SIZE_UFS=5`, `INGESTION_BATCH_DELAY_S=2.0`, `INGESTION_CONCURRENT_UFS=5`, `INGESTION_MAX_PAGES=50`, `INGESTION_UPSERT_BATCH_SIZE=500`, `INGESTION_MODALIDADES=4,5,6,7,8,12`, `INGESTION_UFS=27`, `INGESTION_RETENTION_DAYS=400`, `INGESTION_PURGE_GRACE_DAYS=400`

## pg_cron Jobs
| Job | Schedule | Descrição |
|-----|----------|-----------|
| `cleanup-orphan-checkpoints` | Domingo 08:00 UTC | Deleta checkpoints cuja UF não está na lista ativa de 27 UFs |

## 🔴 Lacunas
| # | Lacuna |
|---|--------|
| ~~DES-ING-002~~ | ~~Limpeza de checkpoints órfãos (UF removida, modalidade deprecada)~~ ✅ Resolvido via `cleanup_orphan_checkpoints()` + pg_cron semanal |
| DES-ING-003 | Bulk upsert de contratos — mesma RPC que bids? Schema compatível? |
