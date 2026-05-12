---
id: ADR-LLM-HARNESS-001
title: LLM Harness Primary Model — DeepSeek V4 Pro
status: Active
date: 2026-05-11
activated: 2026-05-11
review-by: 2026-08-01
deciders: [Tiago Sasaki]
---

# ADR-LLM-HARNESS-001: LLM Harness Primary Model — DeepSeek V4 Pro

## Contexto

DeepSeek V4 Pro foi lançado em 2026-04-24. Claude Code suporta modelos não-Anthropic via `ANTHROPIC_BASE_URL`. Adotado como harness primário por necessidade imediata de custo (runway-critical).

**Dados:**
- DeepSeek V4 Pro: $0.435/1M input vs Claude Sonnet $3.00/1M (7-10× mais barato)
- DeepSeek V4 Flash: $0.14/1M input (95% mais barato — usado como subagent model)
- Output ceiling: 8K chat / 64K thinking (vs Claude 128K) — requer chunking
- Tool-call drift mensurável em chains >30 steps — mitigado com otimizações de sessão

## Decisão

**DeepSeek V4 Pro é o modelo primário ativo do harness** (desde 2026-05-11).

`CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash` para agentes filhos (cost optimization).

Backend LLM (GPT-4.1-nano via OpenAI SDK) é completamente separado — não afetado.

## Configuração Ativa

```bash
# Local apenas — NUNCA commitar
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=<DEEPSEEK_API_KEY>
export ANTHROPIC_MODEL=deepseek-v4-pro[1m]
export ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-v4-pro[1m]
export ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-v4-pro[1m]
export ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-v4-flash
export CLAUDE_CODE_SUBAGENT_MODEL=deepseek-v4-flash
```

**Sufixo `[1m]`** ativa 1M context (default é 200K sem o sufixo). Crítico para análise de repo grande.

## Otimizações de Workflow para DeepSeek V4 Pro

| Dimensão | Ajuste | Motivo |
|---|---|---|
| `/compact` trigger | 60% contexto (não 75%) | DeepSeek deriva mais cedo em sessions longas |
| Output grande | Dividir em seções <4K tokens | Ceiling 8K chat mode |
| Migrations longas | Múltiplos arquivos `.sql` menores | Idem |
| Chains >25 tool calls | Enunciar plano antes de executar | Reduz drift acumulado |
| Checkpoint | A cada ~20 tool calls: resumir estado | Âncora de contexto explícita |
| Subagente crítico | `model: "opus"` no Agent spawn | Força V4 Pro (não Flash) |
| Instrução ao modelo | Listas numeradas > condicionais aninhados | Melhor instruction following |
| Constraints | "NEVER X" > "avoid X" | Binary > gradient |
| Caveman mode (ultra) | Manter sempre | -75% tokens → sessions mais longas |

## Gatilhos de Re-avaliação

Re-avaliar em **2026-08-01** ou antes se:
- Regressão detectada em flows críticos (RLS, Stripe, migrations) → rollback imediato para Claude
- DeepSeek V4 depreciado — migrar para versão seguinte
- Gasto DeepSeek harness exceder $100/mês (re-avaliar se vale Pro vs Flash)

## Referências

- [DeepSeek V4 Pro Release](https://api-docs.deepseek.com/news/news260424)
- [Claude Code Custom Endpoints](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code)
- [Aider LLM Leaderboard](https://aider.chat/docs/leaderboards/)
- `MEMORY.md` entrada: `reference_llm_harness_policy.md`
