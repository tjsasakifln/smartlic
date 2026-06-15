# Algoritmo de Deduplicacao (Dedup) — SmartLic

> **Ultima revisao:** 2026-06-15
> **Modulo:** `backend/consolidation/dedup.py`
> **Orquestrador:** `backend/consolidation/source_merger.py`

---

## 1. Contexto

O SmartLic agrega dados de licitacoes de **3 fontes distintas**: PNCP (portal nacional), PCP v2 (portal de compras publicas), e ComprasGov v3 (dados abertos). Cada fonte pode retornar a mesma licitacao com identificadores, valores ou orgaos ligeiramente diferentes. O algoritmo de deduplicacao opera em **5 camadas sequenciais** para identificar e mesclar duplicatas, garantindo que o usuario veja cada oportunidade uma unica vez.

**Localizacao dos arquivos:**

| Arquivo | Proposito |
|---------|-----------|
| `backend/consolidation/dedup.py` | Engine principal de dedup com 5 camadas |
| `backend/consolidation/source_merger.py` | Orquestrador — `ConsolidationService.fetch_all()` chama `DeduplicationEngine.run()` |
| `backend/consolidation/__init__.py` | Facade que expoe `DEDUP_FIELDS_MERGED` e `DEDUP_FUZZY_HITS` |
| `backend/config/features.py` | Configuracoes `DEDUP_FUZZY_ENABLED` e `DEDUP_FUZZY_THRESHOLD` |
| `backend/unified_schemas/unified.py` | Modelo `UnifiedProcurement` usado pelo dedup |
| `backend/tests/test_consolidation.py` | Testes do fluxo completo de consolidacao |
| `backend/tests/test_consolidation_fuzzy_dedup.py` | Testes especificos do fuzzy dedup |

---

## 2. Visao Geral do Fluxo

```
[ConsolidationService.fetch_all()]
    |
    | Busca paralela: PNCP + PCP + ComprasGov (asyncio.gather)
    | Timeout por fonte, modo degradado, early return, fallback
    v
[Lista combinada de UnifiedProcurement]
    |
    v
[DeduplicationEngine.run()]
    |
    +---> Camada 1: source_id dedup (IDs exatos duplicados)
    +---> Camada 2: dedup_key exact dedup (hash SHA256 + merge-enrichment)
    +---> [SE DEDUP_FUZZY_ENABLED=true]
    |       +---> Camada 3: fuzzy Jaccard matching (mesmo objeto, editais diferentes)
    |       +---> Camada 4: process-number dedup (mesmo orgao + ano, editais adjacentes)
    |       +---> Camada 5: title-prefix dedup (cross-org duplicates)
    v
[Lista deduplicada] -> to_legacy_format() -> ConsolidationResult
```

---

## 3. Camada 1: source_id Dedup

**Arquivo:** `dedup.py::_deduplicate_by_source_id()`

**Proposito:** Remover registros com o mesmo `source_id` (ex: mesmo PNCP contract ID) que aparecem de multiplas fontes — por exemplo, quando o datalake e a API live retornam o mesmo registro.

**Mecanismo:**
1. Agrupa registros por `source_id`
2. Para cada grupo, mantem o registro de **maior prioridade** (menor numero = maior prioridade)
3. Registros sem `source_id` sao preservados (passam para proxima camada)

**Fonte de prioridade:**
```python
# backend/source_config/sources.py
PNCP  = SourceConfig(code="PNCP",   priority=1)   # Maior prioridade
PCP   = SourceConfig(code="PCP",    priority=2)
ComprasGovLegado = SourceConfig(code="CGL", priority=3)
ComprasGovNovo   = SourceConfig(code="CGN", priority=3)
```

**Metrica:** Contagem de registros removidos via log `[DEDUP] source_id dedup removed N duplicates`.

---

## 4. Camada 2: dedup_key Exact Matching + Merge-Enrichment

**Arquivo:** `dedup.py::_deduplicate()`

**Proposito:** Identificar registros com a mesma `dedup_key` (hash SHA256 do objeto normalizado) e fazer merge-enrichment entre vencedor e perdedor.

**Mecanismo:**
1. Agrupa registros por `dedup_key`
2. Registros sem `dedup_key` sao mantidos individualmente (chave `_nokey_{id}`)
3. Para cada grupo com conflito:
   - Determina **vencedor** (maior prioridade de fonte)
   - Aplica **merge-enrichment** (HARDEN-006): campos vazios no vencedor sao preenchidos com valores do perdedor
   - Loga warning se houver discrepancia de valor >5% entre fontes

**Merge-Enrichment (HARDEN-006):**

Campos elegiveis para merge:
```python
_MERGE_FIELDS = ("valor_estimado", "modalidade", "orgao", "objeto")
```

Regra:
- Se o campo do vencedor estiver vazio (`None`, `""`, ou `0`) E o campo do perdedor for preenchido -> copia do perdedor
- O campo `merged_from` do vencedor registra a origem (`{field_name: source_name}`)
- Incrementa metrica `DEDUP_FIELDS_MERGED{field=...}` no Prometheus

**Discrepancia de valor (AC17):**
```python
if diff_pct > 0.05:
    logger.warning(f"[CONSOLIDATION] Value discrepancy >5% for dedup_key={key}: ...")
```

---

## 5. Camada 3: Fuzzy Jaccard Matching

**Arquivo:** `dedup.py::_deduplicate_fuzzy()`

**Proposito:** Identificar a mesma licitacao com numeros de edital diferentes (ex: pregao vs resultado). Usa similaridade Jaccard sobre o texto do objeto.

**Configuracoes:**

| Variavel | Default | Descricao |
|----------|---------|-----------|
| `DEDUP_FUZZY_ENABLED` | `true` | Habilita/desabilita camadas fuzzy (3, 4, 5) |
| `DEDUP_FUZZY_THRESHOLD` | `0.80` | Threshold de similaridade Jaccard |

**Mecanismo:**

1. **Blocking:** Agrupa registros por `cnpj_orgao` (evita comparacao O(n²) global)
2. **Tokenizacao:** Converte `objeto` em frozenset de tokens:
   ```python
   # _tokenize_objeto()
   texto.lower() -> NFD normalize -> remove combining marks -> remove pontuacao
   -> split -> remove tokens com len <= 2 -> remove stopwords PT-BR
   ```
3. **Similaridade Jaccard:** `|A ∩ B| / |A ∪ B|`
4. **Lot detection:** Se ambos tem numero de lote diferente, NAO deduplica
5. **Valor check:** Se `valor_estimado` > 0 em ambos, a diferenca deve ser <= 20% (para sim >= 0.80) ou <= 5% (para sim entre 0.60 e 0.80)
6. **Edital proximity:** Se sem lote e sim < threshold, mas sim >= 0.60 e numeros de edital tem gap <= 3, deduplica como lotes sequenciais

**Log de diagnostico:**
```python
f"[FUZZY-DEDUP-DIAG] sim={sim:.3f} lot_a={lot_a} lot_b={lot_b} val_a={val_a} val_b={val_b}"
```

**Metrica:** `DEDUP_FUZZY_HITS{layer="fuzzy"}` — incrementada a cada remocao.

---

## 6. Camada 4: Process-Number Dedup

**Arquivo:** `dedup.py::_deduplicate_by_process_number()`

**Proposito:** Capturar duplicatas onde o mesmo orgao publica editais adjacentes (ex: "/000065" e "/000066") para a mesma contratacao.

**Mecanismo:**

1. **Grouping:** Agrupa registros por chave `{cnpj_orgao}|{ano}` extraida do `source_id`
2. **Pattern:** `-(\d{4,6})/(\d{4})$` extrai numero do processo e ano
3. **Similaridade:** Jaccard >= `DEDUP_FUZZY_THRESHOLD` (0.80)
4. **Lot check:** Se ambos tem numero de lote diferente, NAO deduplica
5. **Valor check:** Diferenca de valor <= 20%
6. **Vencedor:** Maior prioridade de fonte vence

**Exemplo de captura:**
- `12345678000195-2026-000065/2026` -> process base `12345678000195|2026`
- `12345678000195-2026-000066/2026` -> mesmo base -> candidato a dedup

**Metrica:** `DEDUP_FUZZY_HITS{layer="process_number"}`

---

## 7. Camada 5: Title-Prefix Dedup (Cross-Org)

**Arquivo:** `dedup.py::_deduplicate_by_title_prefix()`

**Proposito:** Capturar duplicatas **cross-org** — a mesma licitacao aparece de fontes diferentes com CNPJs de orgao diferentes (ex: consorcios, republicacoes).

**Mecanismo:**

1. **Blocking:** Agrupa registros pelos primeiros 60 caracteres do `objeto` normalizado (tamanho minimo: 16 caracteres)
2. **Similaridade:** Jaccard >= `DEDUP_FUZZY_THRESHOLD` (0.80)
3. **Lot check:** Se ambos tem numero de lote diferente, NAO deduplica
4. **Valor check:** Diferenca de valor <= 20%
5. **Vencedor:** Maior prioridade de fonte vence

**Cenario tipico:**
- PNCP retorna licitacao com CNPJ do orgao A
- PCP retorna mesma licitacao com CNPJ do orgao B (consorcio)
- Camada 5 captura esta duplicata que as camadas anteriores (que bloqueiam por CNPJ) nao capturaram

**Metrica:** `DEDUP_FUZZY_HITS{layer="title_prefix"}`

---

## 8. Diagrama do Fluxo

```
                    +-----------------------------+
                    |   Consolidated Records      |
                    |   (PNCP + PCP + ComprasGov) |
                    +-------------+---------------+
                                  |
                                  v
                    +-------------+---------------+
                    |  Layer 1: source_id dedup   |
                    |  (mesmo ID de fonte)        |
                    +-------------+---------------+
                                  |
                                  v
                    +-------------+---------------+
                    |  Layer 2: dedup_key exact   |
                    |  (SHA256 hash + merge)      |
                    +-------------+---------------+
                                  |
                    +-------------+---------------+
                    | DEDUP_FUZZY_ENABLED=true?   |
                    +------+----------------------+
                           |                   |
                         Yes                  No
                           |                   |
                           v                   v
              +------------+-----+    +--------+--------+
              | Layer 3: Fuzzy    |    |  Return result  |
              | Jaccard matching  |    +-----------------+
              +------------------+
                      |
                      v
              +------------------+
              | Layer 4: Process |
              | Number dedup     |
              +------------------+
                      |
                      v
              +------------------+
              | Layer 5: Title   |
              | Prefix (cross-   |
              | org) dedup       |
              +------------------+
                      |
                      v
              +------------------+
              | Deduped results  |
              +------------------+
```

---

## 9. Configuracoes e Env Vars

| Variavel | Default | Descricao | Onde |
|----------|---------|-----------|------|
| `DEDUP_FUZZY_ENABLED` | `true` | Habilita camadas fuzzy (3,4,5). Quando `false`, apenas source_id + dedup_key executam | `backend/config/features.py:48` |
| `DEDUP_FUZZY_THRESHOLD` | `0.80` | Threshold Jaccard para fuzzy matching. Menor = mais agressivo, maior = mais seguro | `backend/config/features.py:49` |

**Como sobrescrever via construtor (testes):**

```python
# Para testes ou tuning
engine = DeduplicationEngine(
    adapters=adapters,
    fuzzy_enabled=False,        # Desliga fuzzy
    fuzzy_threshold=0.70,       # Mais agressivo
)
```

---

## 10. Metricas (Prometheus)

| Metrica | Tipo | Labels | Descricao |
|---------|------|--------|-----------|
| `smartlic_dedup_fuzzy_hits_total` | Counter | `layer={fuzzy,process_number,title_prefix}` | Total de remocoes por camada fuzzy |
| `smartlic_dedup_fields_merged_total` | Counter | `field={valor_estimado,modalidade,orgao,objeto}` | Total de merge-enrichments por campo |

Estas metricas sao re-exportadas via `consolidation/__init__.py` para permitir patch em testes (AC2).

---

## 11. Como Testar / Validar

### 11.1 Testes Unitarios

```bash
# Testes especificos de fuzzy dedup (AC1, AC2, AC3)
pytest backend/tests/test_consolidation_fuzzy_dedup.py -v

# Testes do fluxo completo de consolidacao (inclui dedup)
pytest backend/tests/test_consolidation.py -v

# Testes de early return (interage com dedup)
pytest backend/tests/test_consolidation_early_return.py -v
```

### 11.2 Teste Manual com Logs

Execute uma busca e observe os logs de dedup:

```bash
# Busca com fuzzy dedup ativo
curl -X POST "https://api.smartlic.tech/v1/buscar" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ufs": ["SC"], "setor": "construcao_civil", "periodo": 30}'

# Procure nos logs:
# [DEDUP] source_id dedup removed N duplicates
# [DEDUP-MERGE] key=... field=...
# [FUZZY-DEDUP] Merged duplicate (Jaccard=...)
# [PROCESS-DEDUP] Merged duplicate (Jaccard=...)
# [TITLE-PREFIX-DEDUP] Removed N cross-org duplicates
# [CONSOLIDATION] Complete: N raw -> M deduped
```

### 11.3 Validacao de Threshold

Para verificar se o threshold atual esta adequado:

```python
# Exemplo de script de validacao
from consolidation.dedup import DeduplicationEngine

# Testar com diferentes thresholds
for threshold in [0.70, 0.75, 0.80, 0.85]:
    engine = DeduplicationEngine(adapters, fuzzy_threshold=threshold)
    deduped = engine.run(records)
    print(f"Threshold {threshold}: {len(records)} -> {len(deduped)} "
          f"({len(records) - len(deduped)} removidos)")
```

### 11.4 Teste de Regressao

```python
# Verificar que DEDUP_FUZZY_ENABLED=False funciona (AC3)
engine = DeduplicationEngine(adapters, fuzzy_enabled=False)
deduped = engine.run(records)
assert len(deduped) >= len(records_without_fuzzy)
```

---

## 12. Notas de Implementacao

### 12.1 Tokenizacao e Stopwords

A tokenizacao usa a lista `PT_BR_STOPWORDS` do arquivo `backend/filter/stopwords.py` (230 palavras), que combina stopwords NLTK PT-BR com termos de licitacao.

**Tratamento de acentos (ISSUE-027):**
```python
# NFD normalize + remove combining marks
texto = "".join(
    c for c in unicodedata.normalize("NFD", texto)
    if unicodedata.category(c) != "Mn"
)
```
Isso garante que "contratacao" e "contratação" produzam o mesmo token.

### 12.2 Lotes vs Duplicatas Legitimas

O algoritmo tem cuidado especial para NAO deduplicar licitacoes que sao lotes diferentes da mesma compra:

```python
_LOT_PATTERN = re.compile(
    r'\b(?:lote|item|grupo|lotes?)\s*(?:n[.ºo°]?\s*)?(\d+)\b',
    re.IGNORECASE,
)
```

Se dois registros tem o mesmo objeto mas numeros de lote diferentes, eles sao mantidos como entradas separadas.

### 12.3 Prioridade de Fontes

A prioridade determina qual registro "vence" em caso de conflito:

| Fonte | Prioridade | Codigo |
|-------|-----------|--------|
| PNCP | 1 (maior) | `PNCP` |
| PCP v2 | 2 | `PCP` |
| ComprasGov Legado | 3 | `CGL` |
| ComprasGov Novo | 3 | `CGN` |
| ComprasGov | 3 | `CGB` |
| SmartMatcher | 4 | `SMB` |
| DadosNet | 5 (menor) | `DDN` |

PNCP e considerado a fonte oficial, portanto tem prioridade maxima.

### 12.4 O(n²) Prevention

Todas as camadas fuzzy usam **blocking** para evitar comparacao O(n²) global:

- **Camada 3:** Bloqueia por `cnpj_orgao`
- **Camada 4:** Bloqueia por `{cnpj}|{ano}` (do source_id)
- **Camada 5:** Bloqueia por prefixo de 60 caracteres do objeto normalizado
