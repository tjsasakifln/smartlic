# Contratos — Módulo `search`

> Gerado pelo Writer (Reversa) em 2026-06-08 | Fonte: `backend/routes/search/`

---

## POST `/buscar`

**Request:**
```json
{
  "termo": "serviços de limpeza",
  "ufs": ["SP", "RJ", "MG"],
  "setores": ["limpeza", "facilities"],
  "modalidades": [6, 4],
  "valor_minimo": 50000.0,
  "valor_maximo": 500000.0,
  "data_inicio": "2026-01-01",
  "data_fim": "2026-06-08",
  "ordenacao": "confianca"
}
```

**Response 202:**
```json
{
  "search_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "CREATED",
  "estimated_time_s": 45
}
```

**Response 429 (quota):**
```json
{
  "detail": "Quota excedida. Limite: 1000 buscas/mês.",
  "retry_after": 3600
}
```

## GET `/buscar/{search_id}/state`

**Response 200:**
```json
{
  "search_id": "550e8400-...",
  "status": "FILTERING",
  "stage": "filter",
  "progress_pct": 45,
  "results_count": 230,
  "stage_started_at": "2026-06-08T15:30:05Z",
  "created_at": "2026-06-08T15:29:58Z"
}
```

## GET `/buscar/{search_id}/events` (SSE)

**Event stream:**
```
event: stage_update
data: {"stage": "fetching", "progress_pct": 10, "message": "Buscando PNCP SP..."}

event: progress
data: {"stage": "filtering", "progress_pct": 60, "filtered_count": 230}

event: complete
data: {"status": "COMPLETED", "results_count": 230, "duration_s": 42.5}

event: error
data: {"status": "FAILED", "error": "Datalake timeout", "duration_s": 105.0}
```

**Headers:** Content-Type: text/event-stream | Cache-Control: no-cache | Connection: keep-alive

## GET `/buscar/{search_id}/results`

**Query params:** `?page=1&per_page=20&ordenacao=confianca`

**Response 200:**
```json
{
  "search_id": "550e8400-...",
  "status": "COMPLETED",
  "total": 230,
  "page": 1,
  "per_page": 20,
  "results": [
    {
      "id": "uuid",
      "titulo": "Pregão Eletrônico 123/2026",
      "orgao": "Prefeitura Municipal de São Paulo",
      "uf": "SP",
      "modalidade": "Pregão Eletrônico",
      "valor_estimado": 350000.0,
      "data_publicacao": "2026-06-01",
      "classification": "RELEVANTE",
      "classification_source": "keyword",
      "viability_score": 78.5,
      "sector": "limpeza"
    }
  ]
}
```

## POST `/buscar/{search_id}/retry`

**Response 202:** `{"search_id": "...", "status": "CREATED", "message": "Busca reiniciada"}`
**Response 409:** `{"detail": "Busca ainda em andamento. Estado atual: FETCHING"}`

## GET `/buscar/historico`

**Query params:** `?page=1&per_page=10`

**Response 200:**
```json
{
  "total": 45,
  "page": 1,
  "searches": [
    {
      "search_id": "uuid",
      "termo": "serviços de limpeza",
      "status": "COMPLETED",
      "results_count": 230,
      "created_at": "2026-06-08T15:29:58Z",
      "duration_s": 42.5
    }
  ]
}
```
