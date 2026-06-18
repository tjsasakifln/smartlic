# ADR-035: Testes Baseados em Propriedades com Hypothesis

**Status:** Proposed
**Date:** 2026-06-17
**Deciders:** @architect, @qa
**Issue:** #1920

## Context

Testes unitários tradicionais cobrem casos conhecidos, mas são inerentemente limitados: cobrem apenas os inputs que o desenvolvedor imaginou. Para funções críticas (schemas Pydantic, parsing de datas, pipeline de filtros), edge cases imprevistos podem causar falhas em produção. Precisávamos de uma camada adicional de testes que explore automaticamente o espaço de inputs.

## Decision

Complementar testes unitários com property-based testing usando Hypothesis. 4 alvos iniciais: (1) Pydantic models — round-trip serialize/desserialize; (2) Date parsing — parse nunca levanta exceção não tratada; (3) Filter pipeline — ordem dos filtros não altera resultado final (comutatividade); (4) Numeric validation — range validation é idempotente.

## Alternatives Considered

1. **Apenas fixtures (pytest parametrize):** Cobre mais casos que testes manuais, mas ainda limitado pelo que o dev lista.
2. **Fuzzing (Atheris/boofuzz):** Focado em segurança e crash detection — escopo diferente do necessário.
3. **Hypothesis:** Open source, integração nativa com pytest, estratégias declarativas — melhor custo-benefício.

## Consequences

- **Positivo:** Cobertura de edge cases imprevistos que testes manuais não alcançam; estratégias declarativas reduzem boilerplate; Hypothesis gera e encolhe contra-exemplos automaticamente.
- **Negativo:** Cobertura inicial limitada (~5 arquivos); sem CI profile configurado (deadline mais curto para CI); sem fuzzing de segurança.
- **Mitigação:** Expansão planejada para mais módulos; CI profile com deadline configurável.

## References

- `backend/tests/test_hypothesis_*.py` (arquivos de teste)
- `hypothesis` (pip package)
- Hypothesis strategies: `from_type()`, `builds()`, `dates()`, `text()`, `lists()`, `floats()`
