# ADR-031: Stage Dedicado para Classificação Zero-Match + Recovery Path

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @dev

## Context

O caso mais caro da pipeline de filtro era o zero keyword match — itens com `keyword_density == 0.0` que precisavam de classificação LLM (GPT-4.1-nano) para decidir relevância. Originalmente isso era tratado inline no pipeline monolítico `filter/pipeline.py` (1.918 LOC). Quando o LLM falhava (timeout >5s, rate limit 429, erro 5xx), o item era simplesmente rejeitado — sem fallback. Precisávamos de um stage independente com recovery path determinístico.

## Decision

Extrair zero-match classification para `filter/stages/llm_zero_match.py` com batch LLM (até 10 itens/call) e criar `filter/stages/recovery.py` com fallback determinístico (keyword expansion + CNAE mapping) para quando o LLM falha. Se recovery também falhar, marca como `PENDING_REVIEW` em vez de `REJECT`.

## Alternatives Considered

1. **Apenas LLM sem fallback:** Implementação original — itens perdidos em qualquer falha de API.
2. **Falhar rápido (rejeitar tudo):** Menos complexo, mas piora recall do sistema em horários de pico.
3. **Fila assíncrona (ARQ):** Adiaria a classificação — inviável para resposta síncrona de busca.

## Consequences

- **Positivo:** Recovery path cobre 3 modos de falha (timeout, rate limit, erro 5xx); `PENDING_REVIEW` preserva itens que seriam perdidos; batch de 10 reduz custo de API em ~90% comparado a 1 chamada/item.
- **Negativo:** Recovery path sem métricas próprias; batch size hardcoded em 10.
- **Mitigação:** Métricas de recovery rate planejadas; batch size pode virar feature flag.

## References

- `backend/filter/stages/llm_zero_match.py` (182 LOC)
- `backend/filter/stages/recovery.py` (157 LOC)
- `backend/filter/pipeline.py` (pipeline orquestrador, 1.918 LOC)
- `backend/llm_arbiter/zero_match.py` (LLM client)
