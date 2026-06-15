/**
 * Configuração axe-core para auditoria de acessibilidade WCAG AA.
 *
 * Uso:
 *   npx @axe-core/playwright --config frontend/a11y.config.ts
 *   npx playwright test tests/accessibility/
 *
 * Referência: docs/ux/accessibility-audit.md
 */

import type { AxeConfig } from '@axe-core/playwright';

const config: AxeConfig = {
  // Standard WCAG 2.1 Nível AA (inclui critérios Nível A)
  runOnly: {
    type: 'tag',
    values: ['wcag21aa', 'wcag21a', 'best-practice'],
  },

  // Regras específicas do projeto
  rules: {
    // Exceções: iframes de terceiros que não controlamos
    'frame-tested': { enabled: false },

    // Stripe.js injeta iframe que não podemos auditar
    'color-contrast': {
      enabled: true,
      // Ignorar elementos dentro do iframe do Stripe
      excludeHidden: true,
    },

    // Garantir que todas as páginas tenham skip link
    'skip-link': { enabled: true },

    // Validar ARIA labels em componentes dinâmicos
    'aria-required-children': { enabled: true },
    'aria-required-parent': { enabled: true },
    'aria-roles': { enabled: true },
    'aria-valid-attr-value': { enabled: true },
    'aria-valid-attr': { enabled: true },

    // Garantir região de conteúdo principal
    'landmark-one-main': { enabled: true },
    'landmark-unique': { enabled: true },

    // Links devem ser descritivos
    'link-name': { enabled: true },

    // Botões devem ter texto acessível
    'button-name': { enabled: true },

    // Imagens devem ter alt text
    'image-alt': { enabled: true },

    // Formulários devem ter labels
    'label': { enabled: true },
    'input-button-name': { enabled: true },

    // Headings em ordem lógica
    'heading-order': { enabled: true },
  },

  // Locales para suporte a português brasileiro
  locale: 'pt-BR',

  // Elementos a ignorar durante scan
  exclude: [
    // iframes de terceiros
    'iframe[src*="stripe.com"]',
    'iframe[src*="js.stripe.com"]',

    // Conteúdo injetado por extensões de navegador
    '[data-extension-injected]',

    // Elementos de debug (apenas em dev)
    '[data-testid="debug-panel"]',
  ],

  // Reportar apenas violations, não passes/incomplete
  resultTypes: ['violations'],

  // Thresholds para CI gate
  impactThreshold: ['critical', 'serious'],
};

export default config;
