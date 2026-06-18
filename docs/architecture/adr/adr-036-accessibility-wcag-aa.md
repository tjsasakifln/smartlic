# ADR-036: Conformidade WCAG AA no Frontend

**Status:** Accepted
**Date:** 2026-06-17
**Deciders:** @architect, @ux-design-expert, @pm
**Issue:** #1926

## Context

O SmartLic não possuía auditoria formal de acessibilidade. Usuários com deficiência visual, motora ou cognitiva enfrentavam barreiras: navegação por teclado incompleta, contraste insuficiente, falta de ARIA labels em componentes custom, ausência de landmarks semânticos. Para contratações públicas (B2G), acessibilidade é requisito legal crescente (Lei Brasileira de Inclusao — LBI 13.146/2015) e diferencial competitivo.

## Decision

Realizar auditoria WCAG 2.1 AA completa com axe-core, cobrindo 7 critérios prioritários: 1.1.1 Non-text Content, 1.3.1 Info and Relationships, 1.4.1 Use of Color, 1.4.3 Contrast (4.5:1), 2.1.1 Keyboard, 2.4.7 Focus Visible, 4.1.2 Name/Role/Value. Integrar axe-core como CI gate, `eslint-plugin-jsx-a11y` no lint, e `@testing-library/jest-dom` para testes de acessibilidade.

## Alternatives Considered

1. **WCAG AAA:** Mais restritivo, mas ~5x mais caro em esforço de design. AA é padrão de mercado e suficiente para LBI.
2. **Apenas lighthouse audit:** Ferramenta de diagnóstico, não de enforcement contínuo — sem CI gate, regressões passam despercebidas.
3. **Ferramenta terceira (Deque Axe devTools):** Versão paga — axe-core open source cobre os mesmos critérios.

## Consequences

- **Positivo:** 7 critérios WCAG AA validados; CI gate com axe-core previne regressões; lint com jsx-a11y captura problemas em tempo de desenvolvimento.
- **Negativo:** Testes de screen reader são manuais (VoiceOver/NVDA) — sem automação; ~72 componentes auditados — novos componentes precisam de gate no CI; sem monitoramento contínuo de regressão.
- **Mitigação:** CI gate com axe-core cobrirá novos componentes; auditoria manual periódica para screen readers.

## References

- `docs/accessibility/WCAG-AA-audit-2026-06.md` (auditoria completa)
- `docs/accessibility/ci-gate.md` (diretrizes de CI)
- axe-core, `eslint-plugin-jsx-a11y`, `@testing-library/jest-dom`
- WCAG 2.1 AA: https://www.w3.org/TR/WCAG21/
