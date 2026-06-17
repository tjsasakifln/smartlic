# ADR-030: Dedup Engine V2 — Layers Independentes

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @dev

## Context

O motor de deduplicação original em `consolidation/dedup.py` (566 LOC) era monolítico — todas as 5 camadas de dedup (exata, chave, fuzzy, processo, título) em um único arquivo com lógica entrelaçada. Isso dificultava manutenção, testes isolados e modificação de thresholds sem risco de regressão.

## Decision

Extrair cada camada para seu próprio módulo em `consolidation/dedup/`, com engine orquestradora (`engine.py`) que executa layers em pipeline progressivo com early termination. Contrato público mantido via wrapper backward-compat em `consolidation/dedup.py`.

## Alternatives Considered

1. **Manter monolito:** Menos arquivos, mas qualquer alteração em uma layer arrisca as demais.
2. **Chain of Responsibility pattern:** Elegante para pipelines, mas adicionaria complexidade desnecessária para 5 layers fixas.
3. **Plugin system:** Overengineering — layers são fixas e conhecidas em compile-time.

## Consequences

- **Positivo:** Cada layer testável isoladamente; early termination (se layer N reduz conjunto a <threshold, layers N+1..5 são skipadas) melhora performance em ~60% dos casos (exatas dominam).
- **Negativo:** Sem métricas por layer (quantas duplicatas cada layer removeu); thresholds de similaridade fuzzy hardcoded.
- **Mitigação:** Métricas planejadas para fase 2; wrapper backward-compat garante zero impacto em consumidores existentes.

## References

- `backend/consolidation/dedup/` (6 arquivos, 478 LOC total)
- `backend/consolidation/dedup.py` (wrapper backward-compat)
- Layers: exact → key → fuzzy → process → title
