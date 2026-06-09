# Requisitos — Módulo `search`

> Gerado pelo Writer (Reversa) em 2026-06-08
> Doc level: completo | Fonte: `backend/search/`, `backend/routes/search/`, `backend/models/search_state.py`

---

## RF — Requisitos Funcionais

| ID | Requisito | Fonte | Confiança |
|----|-----------|-------|-----------|
| RF-SRC-001 | Busca assíncrona: POST `/buscar` retorna 202 Accepted em <2s | `routes/search/post_handler.py` | 🟢 |
| RF-SRC-002 | Resultados transmitidos via SSE (EventSource) + JSON polling (dual-connection) | `routes/search/sse.py` | 🟢 |
| RF-SRC-003 | Pipeline de busca em 7 estágios: CREATED → VALIDATING → FETCHING → FILTERING → ENRICHING → GENERATING → PERSISTING → COMPLETED | `models/search_state.py` | 🟢 |
| RF-SRC-004 | 11 estados documentados na máquina de estado SearchSession | `models/search_state.py` | 🟢 |
| RF-SRC-005 | Transições inválidas rejeitadas com log CRITICAL | `models/search_state.py` | 🟢 |
| RF-SRC-006 | Estados terminais: COMPLETED, FAILED, RATE_LIMITED, TIMED_OUT | `models/search_state.py` | 🟢 |
| RF-SRC-007 | Busca no datalake (RPC `search_datalake`) como fonte primária | `datalake_query.py` | 🟢 |
| RF-SRC-008 | Fallback para live APIs quando datalake indisponível | `search/` | 🟡 |
| RF-SRC-009 | Cache de resultados: L1 InMemory (4h TTL) + L2 Supabase (24h TTL) com SWR | `cache/` | 🟢 |
| RF-SRC-010 | Ordenação padrão por `combined_score` (confiança) | `search_pipeline.py` | 🟢 |
| RF-SRC-011 | Time budget waterfall: pipeline 100s > consolidation 90s > per_source 70s > per_uf 25s | `pipeline/budget.py` | 🟢 |
| RF-SRC-012 | Timeout do pipeline: 100s total, 180s search | `pipeline/budget.py` | 🟢 |
| RF-SRC-013 | Retry de busca via POST `/buscar/{id}/retry` | `routes/search/` | 🟢 |
| RF-SRC-014 | Histórico de buscas acessível via GET `/buscar/historico` | `routes/search/` | 🟢 |

---

## RNF — Requisitos Não Funcionais

| ID | Requisito | Categoria | Evidência | Confiança |
|----|-----------|-----------|-----------|-----------|
| RNF-SRC-001 | POST `/buscar` <2s para 202 Accepted | Performance | `post_handler.py` | 🟢 |
| RNF-SRC-002 | Resultados via SSE com primeiro evento <5s | Performance | SSE pub/sub Redis | 🟡 |
| RNF-SRC-003 | Cache hit ratio >80% para buscas repetidas | Performance | L1 4h + L2 24h TTL | 🟡 |
| RNF-SRC-004 | Timeout pipeline nunca excede invariante waterfall | Resiliência | `tests/test_timeout_invariants.py` | 🟢 |
| RNF-SRC-005 | Graceful degradation quando datalake indisponível → live APIs | Disponibilidade | `search/` | 🟡 |

---

## Critérios de Aceitação

### Cenário: Busca bem-sucedida
**Dado** que o usuário autenticado envia parâmetros de busca (termo, UFs, setores, valor)
**Quando** faz POST `/buscar`
**Então** recebe 202 Accepted com `search_id` em <2s
**E** o SSE começa a emitir eventos em <5s
**E** cada estágio do pipeline emite `stage_update` via SSE
**E** ao final, GET `/buscar/{id}/results` retorna os resultados classificados

### Cenário: Timeout do pipeline
**Dado** que a busca excede 100s de processamento
**Quando** o pipeline atinge o timeout
**Então** o estado da busca transita para TIMED_OUT
**E** SSE emite evento de timeout
**E** GET `/buscar/{id}/results` retorna resultados parciais (se houver)

### Cenário: Cache hit
**Dado** que os mesmos parâmetros de busca foram usados nas últimas 4h
**Quando** o usuário faz POST `/buscar`
**Então** o sistema retorna resultados do cache L1 (InMemory)
**E** o pipeline NÃO é executado (skip completo)
**E** resposta em <500ms

### Cenário: Quota excedida
**Dado** que o usuário já usou todas as buscas do período
**Quando** faz POST `/buscar`
**Então** recebe 429 Too Many Requests
**E** estado da busca = RATE_LIMITED

---

## MoSCoW

| Prioridade | Requisitos |
|------------|------------|
| **Must** | RF-SRC-001 (async POST), RF-SRC-003 (7 stages), RF-SRC-004 (state machine), RF-SRC-007 (datalake) |
| **Should** | RF-SRC-002 (SSE dual), RF-SRC-009 (cache), RF-SRC-011 (time budget) |
| **Could** | RF-SRC-008 (live API fallback), RF-SRC-013 (retry), RF-SRC-014 (history) |
| **Won't** | — |
