# LLM Arbiter Design & Fallback Plan

> DES-LLM-001: Design do LLM Arbiter, modelo de classificacao setorial,
> fallback em caso de deprecacao, e cobertura da env var `LLM_ARBITER_MODEL`.

## Visao Geral

O LLM Arbiter e o componente responsavel por classificar a relevancia setorial
de licitacoes publicas usando um modelo de linguagem (atualmente GPT-4.1-nano
da OpenAI). Ele opera em tres niveis de classificacao:

1. **Keyword matching** (>5% densidade) — sem chamada LLM
2. **LLM standard / conservative** (1-5%) — chamada LLM com prompt setorial
3. **LLM zero-match** (0%) — chamada LLM binaria SIM/NAO

## Arquitetura

```
search_pipeline.py
  +-- filter/pipeline.py
  |     +-- keyword density tiers (sem LLM)
  |     +-- llm_arbiter/classification.py    <- LLM_MODEL definido aqui
  |     |     +-- strategies/_base.py         <- usa _cls.LLM_MODEL
  |     |     +-- strategies/standard.py
  |     |     +-- strategies/conservative.py
  |     |     +-- zero_match.py               <- importa LLM_MODEL
  |     |     +-- batch_api.py                <- importa LLM_MODEL
  |     |     +-- async_runtime.py
  |     +-- pipeline/stages/post_filter_llm.py <- le LLM_ARBITER_MODEL via os.getenv
  |     +-- bid_analyzer.py                    <- importa LLM_ARBITER_MODEL de config
  +-- llm.py (executive summaries)
        +-- gerar_resumo()                     <- importa LLM_ARBITER_MODEL de config
        +-- gerar_analise_concorrencia()       <- importa LLM_ARBITER_MODEL de config
```

## Configuracao via Env Var

### Todos os callsites que respeitam `LLM_ARBITER_MODEL`

| Arquivo | Linha | Mecanismo | Status |
|---------|-------|-----------|--------|
| `backend/config/features.py` | 24 | `os.getenv("LLM_ARBITER_MODEL", "gpt-4.1-nano")` | OK |
| `backend/config/__init__.py` | 44 | Re-exporta `LLM_ARBITER_MODEL` | OK |
| `backend/llm_arbiter/classification.py` | 46 | `os.getenv("LLM_ARBITER_MODEL", "gpt-4.1-nano")` -> `LLM_MODEL` | OK |
| `backend/llm_arbiter/strategies/_base.py` | 163 | Usa `_cls.LLM_MODEL` (herdado de `classification`) | OK |
| `backend/llm_arbiter/zero_match.py` | 16, 93 | Importa `LLM_MODEL` de `classification` | OK |
| `backend/llm_arbiter/batch_api.py` | 105, 123 | Importa `LLM_MODEL` de `classification` | OK |
| `backend/pipeline/stages/post_filter_llm.py` | 29 | `os.getenv("LLM_ARBITER_MODEL", "gpt-4.1-nano")` | OK |
| `backend/bid_analyzer.py` | 155-157, 271-273 | Importa `LLM_ARBITER_MODEL` de `config` | OK |
| `backend/llm.py` | 30 | Importa `LLM_ARBITER_MODEL` de `config` | OK |
| `backend/llm.py` | 338, 360, 500 | Usa `LLM_ARBITER_MODEL` | OK |
| `backend/intel_sectors_config.yaml` | 2099 | YAML estatico (`model: "gpt-4.1-nano"`) | NOTA |

> **Nota:** O arquivo `backend/intel_sectors_config.yaml` contem `model: "gpt-4.1-nano"`
> como configuracao estatica do modulo Intel Reports. Este YAML nao e carregado
> por codigo Python ativo na pipeline principal. Se o modulo Intel Reports for
> ativado no futuro, este valor precisara ser sincronizado manualmente com a env var.

### Como trocar o modelo

```bash
# Trocar para GPT-4o-mini (sem deploy):
railway variables set LLM_ARBITER_MODEL=gpt-4o-mini

# Rollback:
railway variables set LLM_ARBITER_MODEL=gpt-4.1-nano
```

A troca exige restart do servico Railway (ou reload das feature flags via
`/v1/admin/feature-flags/reload`).

## Fallback Plan (GAP-016)

> Detalhes completos em `_reversa_sdd/specs/14-llm-fallback-plan.md`.

### Candidatos a Fallback

| Prioridade | Modelo | Custo Input | Custo Output | Risco |
|------------|--------|-------------|--------------|-------|
| 1 | GPT-4.1-mini | ~$0.15/1M | ~$0.60/1M | Baixo — mesma familia 4.1 |
| 2 | GPT-4o-mini | ~$0.15/1M | ~$0.60/1M | Medio — prompt pode exigir recalibracao |
| 3 | GPT-4o | ~$2.50/1M | ~$10.00/1M | Alto custo — ultimo recurso |

### Pricing

O pricing do modelo atual esta definido em `backend/llm_arbiter/classification.py`
(linhas 55-56) como constantes `_PRICING_INPUT_PER_M` e `_PRICING_OUTPUT_PER_M`.

Ao trocar o modelo, estes valores DEVEM ser atualizados para refletir o pricing
do novo modelo, pois sao usados em `_log_token_usage()` para tracking de custo
nas metricas `LLM_COST_USD` e `LLM_COST_BRL`.

### Monitoramento de Deprecacao

1.  **OpenAI SDK warnings:** O SDK emite `openai.Warning` no stderr quando um
    modelo entra em status de deprecacao.
2.  **Health check:** `backend/health.py` ja possui `check_openai_health()` que
    testa conectividade OpenAI via `models.list(limit=1)`. Melhoria adicionada
    para logar warnings de deprecacao no modelo configurado.
3.  **Sentry:** Configurar `sentry_sdk.capture_message()` com fingerprint
    `["llm_model_deprecation", model_name]` para capturar warnings de deprecacao.
4.  **Metricas:** `LLM_TOKENS_DETAILED` (label `model=LLM_MODEL`) — queda abrupta
    no volume de tokens processados pode indicar falha silenciosa do modelo.
