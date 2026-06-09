# Tasks — Módulo `search`

> Gerado pelo Writer (Reversa) em 2026-06-08
> Fonte: `backend/search/`, `backend/routes/search/`, `backend/models/search_state.py`

---

| ID | Tarefa | Arquivo Legado | Critério de Pronto | Confiança |
|----|--------|----------------|-------------------|-----------|
| T-SRC-001 | Implementar `SearchState` com 11 estados e transições válidas | `models/search_state.py` | Todas as transições válidas aceitas. Inválidas → CRITICAL log + rejeição. | 🟢 |
| T-SRC-002 | Implementar POST `/buscar` com resposta 202 em <2s | `routes/search/post_handler.py` | 202 + search_id retornado. Validação de parâmetros, quota, permissões. | 🟢 |
| T-SRC-003 | Implementar pipeline de 7 estágios como state machine | `search/` | Estados transitam em ordem. Cada estágio emite progresso. | 🟢 |
| T-SRC-004 | Implementar SSE broker com Redis pub/sub | `routes/search/sse.py` | EventSource conecta, recebe stage_update, progress, complete, error. | 🟢 |
| T-SRC-005 | Implementar polling fallback GET `/buscar/{id}/state` | `routes/search/` | Retorna estado atual + progresso %. Timeout 30s long-polling. | 🟢 |
| T-SRC-006 | Implementar cache L1 InMemory 4h TTL com SWR | `cache/` | Cache hit <4h → retorna. Cache hit >4h → retorna + revalida. | 🟢 |
| T-SRC-007 | Implementar cache L2 Supabase 24h TTL | `cache/` | Populado após pipeline. Chave = hash parâmetros. | 🟢 |
| T-SRC-008 | Implementar busca no datalake via RPC `search_datalake` | `datalake_query.py` | Full-text search PT-BR com filtros UF, modalidade, valor. | 🟢 |
| T-SRC-009 | Implementar time budget waterfall | `pipeline/budget.py` | Invariante: pipeline > consolidation > per_source > per_uf. Testado. | 🟢 |
| T-SRC-010 | Implementar retry POST `/buscar/{id}/retry` | `routes/search/` | Reinicia busca do estado FAILED ou TIMED_OUT. Reseta progresso. | 🟢 |
| T-SRC-011 | Implementar GET `/buscar/historico` | `routes/search/` | Lista buscas do usuário com paginação. Ordenado por data. | 🟢 |
| T-SRC-012 | Implementar fallback para live APIs quando datalake off | `search/` | Datalake erro → tenta PNCP/PCP/Gov direto. Timeout menor (70s). | 🟡 |
| T-SRC-013 | Implementar GET `/buscar/{id}/results` | `routes/search/` | Retorna resultados com paginação, ordenação, filtros. | 🟢 |
| T-SRC-014 | Implementar limpeza de cache stale (Redis EXPIRE + pg_cron) | `cache/` | TTL nativo (Redis EXPIRE 4h + jitter) + pg_cron DELETE diário. 🟡 | 🟡 |

## Ordem

```
T-SRC-001 (state machine)
  ├─ T-SRC-003 (pipeline 7 stages)
  │   ├─ T-SRC-009 (time budget)
  │   ├─ T-SRC-008 (datalake RPC)
  │   └─ T-SRC-012 (live API fallback)
  ├─ T-SRC-002 (POST /buscar)
  ├─ T-SRC-004 (SSE broker)
  ├─ T-SRC-005 (polling fallback)
  ├─ T-SRC-006 (cache L1)
  ├─ T-SRC-007 (cache L2)
  ├─ T-SRC-013 (GET results)
  ├─ T-SRC-010 (retry)
  ├─ T-SRC-011 (history)
  └─ T-SRC-014 (cache cleanup)
```

**Estimativa:** 14 tarefas, ~35 story points
