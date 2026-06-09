# Design — Módulo `pipeline`

> Gerado pelo Writer (Reversa) em 2026-06-08
> Doc level: completo | Fonte: `backend/consolidation/`, `backend/filter/`, `backend/pipeline/`, `backend/viability.py`

---

## Visão Geral

Pipeline de processamento pós-fetch: recebe resultados brutos multi-fonte, deduplica em 5 camadas progressivas, aplica filtros em ordem fail-fast (do mais barato ao mais caro), classifica via keyword density + LLM, e pontua viabilidade em 4 fatores.

## Arquitetura Interna

```
Resultados Brutos (PNCP + PCP + ComprasGov)
  │
  ▼
┌─────────────────────────────────────────────┐
│ CONSOLIDATION (consolidation/)               │
│                                              │
│ 1. source_id dedup     (O(n), hash map)     │
│ 2. dedup_key exata     (O(n), hash map)     │
│ 3. fuzzy Jaccard       (O(n²), threshold)  │
│ 4. process-number      (O(n), regex)        │
│ 5. title-prefix        (O(n log n), sort)   │
│                                              │
│ Merge-enrichment: PNCP(pri=1) > PCP(pri=2)  │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ FILTER (filter/)                             │
│                                              │
│ 1. UF check           (O(1), set lookup)    │
│ 2. Value range        (O(1), numeric cmp)   │
│ 3. Keyword density    (O(k), k=keywords)    │
│ 4. LLM zero-match     (O(1) API call)       │
│ 5. Status/date        (O(1), validation)    │
│                                              │
│ Fail-fast: descarta no primeiro mismatch     │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────┐
│ VIABILITY (viability.py)                     │
│                                              │
│ Score = modalidade(30%) + timeline(25%)     │
│       + valor(25%) + geografia(20%)          │
│                                              │
│ Range: 0-100                                 │
└──────────────────────┬──────────────────────┘
                       │
                       ▼
              Resultados Classificados
```

## Camadas de Dedup (Detalhe)

### Camada 1: source_id
- **Algoritmo:** Hash map por `(source, source_id)`
- **Complexidade:** O(n)
- **Ação:** Remove duplicata exata da mesma fonte

### Camada 2: dedup_key exata
- **Algoritmo:** Hash map por `dedup_key` (hash normalizado de objeto + órgão + UF + modalidade)
- **Complexidade:** O(n)
- **Ação:** Merge — fonte prioritária vence, secundária enriquece

### Camada 3: fuzzy Jaccard
- **Algoritmo:** Jaccard similarity entre conjuntos de tokens do objeto
- **Parâmetros:** `DEDUP_FUZZY_THRESHOLD` (default 0.80, configurável via env var DEDUP_FUZZY_THRESHOLD)
- **Stopwords:** 30 palavras PT-BR ignoradas (de, para, com, em, que, etc.)
- **Complexidade:** O(n²) no pior caso, mitigado por early pruning
- **Ação:** Se similaridade > threshold → merge

### Camada 4: process-number
- **Algoritmo:** Regex extrai nº do processo (padrões: `\d{4,}/\d{4,}`, `PE \d+/\d+`)
- **Complexidade:** O(n)
- **Ação:** Mesmo nº processo → merge

### Camada 5: title-prefix
- **Algoritmo:** Ordena por título, compara prefixos de N tokens
- **Complexidade:** O(n log n)
- **Ação:** Prefixo comum significativo → merge cauteloso

## Ordem de Filtro (Fail-Fast)

A ordem é determinística e otimizada por custo computacional:

| Posição | Filtro | Custo | Descarta |
|---------|--------|-------|----------|
| 1 | UF | O(1) set lookup | UFs não solicitadas |
| 2 | Valor | O(1) numérico | Fora da faixa |
| 3 | Keyword density | O(k) string match | 0% match → vai para LLM |
| 4 | LLM zero-match | API call (~500ms) | IRRELEVANTE |
| 5 | Status/date | O(1) validação | Status inválido, data futura |

Cada filtro que descarta evita que os filtros seguintes (mais caros) processem o item.

## Classificação por Keyword Density

```
Densidade = (keywords_matched / total_keywords_do_setor) × 100

> 5%  → fonte = "keyword"        (alta confiança, sem LLM)
2-5%  → fonte = "llm_standard"   (confiança média, LLM opcional)
0%    → fonte = "llm_zero_match" (sem keywords, LLM obrigatório)
```

## Viabilidade (4 Fatores)

```
Score = modalidade_score × 0.30
      + timeline_score  × 0.25
      + valor_score     × 0.25
      + geografia_score × 0.20

Modalidade:  Pregão(100) > Concorrência(80) > Dispensa(60) > ...
Timeline:    data_entrega - hoje → urgência
Valor:       valor_estimado no range ideal do setor
Geografia:   UF na região de atuação do usuário
```

## Dependências

| Dependência | Uso |
|-------------|-----|
| `clients/` | Dados brutos das APIs (transformados em UnifiedBid) |
| `llm_arbiter/` | Classificação zero-match via GPT-4.1-nano |
| `sectors_data.yaml` | 20 setores com keywords, exclusões, faixas de valor |
| `pipeline/budget.py` | `_run_with_budget()` — timeout waterfall por estágio |

## Feature Flags

| Flag | Default | Efeito |
|------|---------|--------|
| `LLM_ZERO_MATCH_ENABLED` | true | Habilita classificação LLM para zero-match |
| `LLM_ARBITER_ENABLED` | true | Habilita LLM arbiter global |
| `LLM_FALLBACK_PENDING_ENABLED` | true | Fallback = PENDING_REVIEW (vs REJECT) |
| `VIABILITY_ASSESSMENT_ENABLED` | true | Habilita scoring de viabilidade |
| `SYNONYM_MATCHING_ENABLED` | true | Expansão de sinônimos PT-BR |
| `DATALAKE_QUERY_ENABLED` | true | Datalake como fonte primária |

## 🔴 Lacunas

| # | Lacuna |
|---|--------|
| DES-PIP-001 | ~~Valor exato de `DEDUP_FUZZY_THRESHOLD` — inferido ~0.85 do código, confirmar~~ | **RESOLVIDO (#1587):** Configurável via `DEDUP_FUZZY_THRESHOLD` env var, default 0.80 |
| DES-PIP-002 | Lista completa das 30 stopwords PT-BR — extraída parcialmente |
| DES-PIP-003 | Peso dos fatores de viabilidade é fixo ou configurável por setor? |
