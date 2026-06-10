# LLM Model Fallback Plan

> GAP-016: Contingencia para deprecacao do modelo GPT-4.1-nano.
> Documenta as opcoes de fallback, monitoramento e verificacao de cobertura.

## Modelo Atual

**Modelo:** `gpt-4.1-nano` (OpenAI)

**Configuracao via env var:** O modelo e definido pela variavel de ambiente `LLM_ARBITER_MODEL`:

- `backend/llm_arbiter/classification.py` (linha 46):
  ```python
  LLM_MODEL = os.getenv("LLM_ARBITER_MODEL", "gpt-4.1-nano")
  ```

- `backend/config/features.py` (linha 24):
  ```python
  LLM_ARBITER_MODEL: str = os.getenv("LLM_ARBITER_MODEL", "gpt-4.1-nano")
  ```

Ambos os locais leem da mesma env var `LLM_ARBITER_MODEL`. O fallback padrao e
`gpt-4.1-nano`. A alteracao da env var e suficiente para trocar o modelo em
todos os pontos de uso — nenhuma alteracao de codigo e necessaria.

**Pricing atual (gpt-4.1-nano, por milhao de tokens):**
- Input: $0.10
- Output: $0.40

Definido em `classification.py` (linhas 54-56):
```python
_PRICING_INPUT_PER_M = 0.10
_PRICING_OUTPUT_PER_M = 0.40
```

> **Nota:** Se o modelo for alterado, os precos em `_PRICING_INPUT_PER_M` e
> `_PRICING_OUTPUT_PER_M` devem ser atualizados para refletir o novo modelo.
> Estes valores sao usados em `_log_token_usage()` para tracking de custo.

## Monitoramento de Deprecacao

1. **OpenAI deprecation warnings:** O SDK da OpenAI emite warnings no log
   quando um modelo entra em status de deprecacao iminente. Estes warnings
   aparecem como `openai.Warning` no stderr.
2. **Sentry alert:** Configurar `sentry_sdk.capture_message()` para capturar
   qualquer `openai.Warning` relacionado a modelo deprecated. Fingerprint
   sugerido: `["llm_model_deprecation", model_name]`.
3. **Health check:** O endpoint `/v1/health` inclui verificacao dos providers
   OpenAI. Uma chamada de health check com `max_tokens=1` pode detectar
   erros de modelo (404, 401).
4. **Metricas:** `LLM_COST_USD`, `LLM_TOKENS_DETAILED` (com label
   `model=LLM_MODEL`) — uma queda abrupta no volume de tokens processados
   pode indicar falha silenciosa do modelo.

## Candidatos a Fallback (ordem de prioridade)

### 1. GPT-4.1-mini (recomendado)

| Propriedade | Valor |
|-------------|-------|
| Familia | Mesma familia do GPT-4.1-nano |
| Custo (input) | ~$0.15/1M tokens (estimado) |
| Custo (output) | ~$0.60/1M tokens (estimado) |
| Compatibilidade | Mesmo formato structured output |
| Risco | Baixo — mesma geracao de API |

**Nota:** Modelo mais leve dentro da familia 4.1. Se o nano for deprecated
mas o mini permanecer, esta e a migracao mais segura. Ajustar
`_PRICING_INPUT_PER_M` e `_PRICING_OUTPUT_PER_M` se o pricing for diferente.

### 2. GPT-4o-mini (alternativa custo-beneficio)

| Propriedade | Valor |
|-------------|-------|
| Familia | GPT-4o (multimodal) |
| Custo (input) | ~$0.15/1M tokens |
| Custo (output) | ~$0.60/1M tokens |
| Compatibilidade | Structured output suportado |
| Risco | Medio — diferencas no comportamento de classificacao |

**Nota:** Mais amplamente disponivel e com boa relacao custo-beneficio.
Pode exigir recalibracao dos prompts em `prompt_builder.py` e re-execucao
do benchmark de classificacao.

### 3. GPT-4o (ultimo recurso)

| Propriedade | Valor |
|-------------|-------|
| Familia | GPT-4o (multimodal) |
| Custo (input) | ~$2.50/1M tokens |
| Custo (output) | ~$10.00/1M tokens |
| Compatibilidade | Total |
| Risco | Alto custo operacional |

**Nota:** Capaz de substituir qualquer modelo da familia 4.1/4o, mas com
custo 10-25x maior. Usar apenas como fallback emergencial enquanto um
modelo mais barato e validado.

## Feature Flag

A env var `LLM_ARBITER_MODEL` ja permite troca de modelo sem deploy:

```bash
# Trocar para GPT-4o-mini no Railway:
railway variables set LLM_ARBITER_MODEL=gpt-4o-mini

# Rollback:
railway variables set LLM_ARBITER_MODEL=gpt-4.1-nano
```

Nenhuma alteracao de codigo necessaria — a leitura via `os.getenv()` em ambos
`classification.py` e `config/features.py` garante que o novo modelo seja
usado em todas as chamadas LLM apos restart do servico (ou recarga de
feature flags).

## Callsites do LLM Arbiter

A constante `LLM_MODEL` (em `classification.py`) e usada nos seguintes locais:

1. **`_log_token_usage()`** — labels de metrica Prometheus (`model=LLM_MODEL`)
2. **Estrategias de classificacao** (`llm_arbiter/strategies/*.py`) — cada
   strategy cria o client OpenAI e passa `model=LLM_MODEL`
3. **Prompts de zero-match** — `llm_arbiter/zero_match.py` usa `LLM_MODEL`
4. **Batch API** — `llm_arbiter/batch_api.py` usa `LLM_MODEL`

A config em `config/features.py` re-exporta `LLM_ARBITER_MODEL` para uso
por outros modulos que importam de `config` ao inves de `llm_arbiter`.

## Callsites Cobertos (GAP-016)

Alem dos callsites do LLM Arbiter, a seguinte cobertura foi verificada/corrigida:

### LLM Executive Summaries (`backend/llm.py`)

**Antes (hardcoded):** 3 ocorrencias de `"gpt-4.1-nano"`
- `gerar_resumo()` — `model="gpt-4.1-nano"` (linha 335)
- `gerar_resumo()` — `_model_name = "gpt-4.1-nano"` (linha 357)
- `gerar_analise_concorrencia()` — `model="gpt-4.1-nano"` (linha 497)

**Depois:** Todas usam `LLM_ARBITER_MODEL` importado de `config.features`.

### Bid Analyzer (`backend/bid_analyzer.py`)

**Status:** Ja usava `from config import LLM_ARBITER_MODEL` (linhas 155-157, 271-273).
Nenhuma alteracao necessaria.

### Post-Filter LLM (`backend/pipeline/stages/post_filter_llm.py`)

**Status:** Ja usava `os.getenv("LLM_ARBITER_MODEL", "gpt-4.1-nano")` (linha 29).
Nenhuma alteracao necessaria.

### Intel Reports (`backend/intel_sectors_config.yaml`)

**Status:** YAML estatico com `model: "gpt-4.1-nano"` (linha 2099). Nao carregado
por codigo Python ativo. Sincronizar manualmente se o modulo for ativado.

## Verification Checklist


- [x] `LLM_ARBITER_MODEL` env var respeitada em `classification.py` (linha 46)
- [x] `LLM_ARBITER_MODEL` env var respeitada em `config/features.py` (linha 24)
- [x] Health check detecta warnings de deprecacao da OpenAI (`check_openai_health()` em `backend/health.py`)
- [ ] Modelos alternativos testados com suite de benchmark
      (15 amostras/setor, precision >= 85%, recall >= 70%)

## Procedimentos de Emergencia

### Troca rapida de modelo (sem deploy)

```bash
# 1. Verificar modelo atual no Railway
railway variables get LLM_ARBITER_MODEL

# 2. Trocar para fallback
railway variables set LLM_ARBITER_MODEL=gpt-4.1-mini

# 3. Verificar metricas de custo no Prometheus
#    smartlic_llm_cost_usd_total{model="gpt-4.1-mini"}

# 4. Verificar classificacoes no Sentry (erros 4xx da API OpenAI)

# 5. Reverter se necessario
railway variables set LLM_ARBITER_MODEL=gpt-4.1-nano
```

### Teste de modelo alternativo em staging

```bash
# 1. Setar env var em staging
railway variables set --environment staging LLM_ARBITER_MODEL=gpt-4o-mini

# 2. Executar benchmark
cd backend && pytest tests/test_llm_arbiter*.py -v --benchmark-only

# 3. Verificar precision/recall
#    Expect: precision >= 85%, recall >= 70%

# 4. Se aprovado, promover para producao
railway variables set LLM_ARBITER_MODEL=gpt-4o-mini
```
