# Auditoria de Acessibilidade — WCAG AA

**Issue:** [#1815](https://github.com/tjsasakifln/SmartLic/issues/1815)
**Prioridade:** P2
**Status:** Plano documentado — execução pendente
**Data:** 2026-06-15

## 1. Objetivo

Validar conformidade WCAG AA (Web Content Accessibility Guidelines 2.1) em todas as ~25 páginas core do SmartLic, garantindo que usuários com deficiência possam utilizar o sistema com leitores de tela, navegação por teclado e contraste adequado.

## 2. Stack e Ferramentas

| Ferramenta | Tipo | Uso | Custo |
|-----------|------|-----|-------|
| **axe-core** | Scan automatizado | Auditoria de todas as páginas | Gratuito, open source |
| **@axe-core/playwright** | Integração E2E | Testes automatizados no CI | Gratuito, open source |
| **Lighthouse** | Auditoria integrada | Chrome DevTools → Accessibility score | Gratuito, nativo Chrome |
| **NVDA** | Leitor de tela | Teste manual Windows | Gratuito, open source |
| **VoiceOver** | Leitor de tela | Teste manual macOS | Gratuito, nativo macOS |
| **WAVE** | Browser extension | Inspeção visual rápida | Gratuito |

## 3. Escopo da Auditoria

### 3.1 Páginas Core (~25 páginas)

| Categoria | Páginas | Prioridade |
|-----------|---------|:---:|
| **Autenticação** | Login, Registro, Recuperação de senha, MFA | 🔴 Crítica |
| **Busca** | Busca consolidada, Resultados SSE, Filtros | 🔴 Crítica |
| **Pipeline** | Kanban de oportunidades, Drag-and-drop | 🔴 Crítica |
| **Export** | Relatórios Excel, PDF | 🔴 Crítica |
| **Dashboard** | Analytics, Métricas, Gráficos Recharts | 🟡 Alta |
| **Configurações** | Perfil, Preferências de setor, Mute sectors | 🟡 Alta |
| **Billing** | Planos, Histórico de pagamentos, Invoice | 🟡 Alta |
| **Admin** | Painel admin, Gestão de usuários | 🟢 Média |
| **SEO** | Landing pages programáticas (~10k páginas ISR) | 🟢 Média |
| **Onboarding** | Tour Shepherd.js | 🟢 Média |

### 3.2 Componentes Dinâmicos (atenção especial)

- **Pipeline Kanban:** Drag-and-drop com @dnd-kit (code-split lazy)
- **Busca SSE:** Atualizações em tempo real via EventSource
- **Filtros:** Combobox, multiselect, date range picker
- **Modal:** Diálogos de confirmação, onboarding
- **Toast:** Notificações de sistema
- **Charts:** Recharts com tooltips interativos

## 4. Metodologia de Teste

### 4.1 Fase 1 — Scan Automatizado (axe-core)

```bash
# Scan de todas as páginas em staging
npx @axe-core/playwright --page-urls "https://staging.smartlic.tech/**/*"

# Ou via script Playwright customizado
npx playwright test tests/accessibility/a11y-scan.spec.ts
```

**Configuração axe-core:**
- Standard: WCAG 2.1 AA
- Rules: todas habilitadas por padrão
- Exclusões: iframes de terceiros (Stripe.js, Mixpanel)
- Threshold: zero críticos ou sérios

### 4.2 Fase 2 — Navegação por Teclado

**Fluxo principal:** Busca → Pipeline → Export

| Passo | Ação | Tecla Esperada | Critério WCAG |
|-------|------|---------------|---------------|
| 1 | Acessar busca | Tab → Enter | 2.1.1 Keyboard |
| 2 | Digitar termo | Teclado normal | 2.1.1 Keyboard |
| 3 | Selecionar filtros | Tab → Space/Enter | 2.1.1 Keyboard |
| 4 | Navegar resultados | Tab → Arrow keys | 2.1.1 Keyboard |
| 5 | Mover card pipeline | Tab → Space → Arrow | 2.1.1 + 2.5.3 |
| 6 | Abrir detalhes | Enter | 2.1.1 Keyboard |
| 7 | Exportar | Tab → Enter | 2.1.1 Keyboard |
| 8 | Fechar modal | Escape | 2.1.1 Keyboard |

**Checklist teclado:**

- [ ] Todos elementos interativos focáveis (Tab)
- [ ] Focus visible em todos os estados (2.4.7 Focus Visible)
- [ ] Ordem de tabulação lógica (2.4.3 Focus Order)
- [ ] Sem focus traps (2.1.2 No Keyboard Trap)
- [ ] Atalhos de teclado documentados (2.1.4 Character Key Shortcuts)
- [ ] Skip-to-content link na primeira posição (2.4.1 Bypass Blocks)

### 4.3 Fase 3 — Leitor de Tela

**Ferramenta:** NVDA (Windows) ou VoiceOver (macOS)

**Roteiro de teste:**

1. **Login:** Anuncia campos email/senha, erros de validação, estado "carregando"
2. **Busca:** Anuncia número de resultados, loading state, cada card de edital
3. **Pipeline:** Anuncia colunas do kanban, posição do card, ação de mover
4. **Filtros:** Anuncia filtro selecionado, contagem de resultados atualizada
5. **Export:** Anuncia progresso da geração, link de download
6. **Billing:** Anuncia plano atual, valores, botão de upgrade
7. **Dashboard:** Anuncia gráficos com descrições alternativas

### 4.4 Fase 4 — Contraste de Cores

**Validar todos os estados de UI:**

| Estado | Elementos | Contraste Mínimo | Critério |
|--------|-----------|:---:|---------|
| **Normal** | Texto corpo, headings, labels | 4.5:1 | 1.4.3 |
| **Normal** | Texto grande (≥18px bold ou ≥24px) | 3:1 | 1.4.3 |
| **Hover** | Links, botões, cards | 4.5:1 | 1.4.3 |
| **Focus** | Focus ring em todos elementos | 3:1 (contra adjacente) | 1.4.11 |
| **Active** | Botões pressionados, tabs ativas | 4.5:1 | 1.4.3 |
| **Disabled** | Inputs e botões desabilitados | N/A (indicar visualmente) | 1.4.3 |
| **Error** | Mensagens de erro, bordas | 4.5:1 | 1.4.3 |
| **Success** | Toast, confirmações | 4.5:1 | 1.4.3 |
| **Placeholder** | Texto placeholder em inputs | 4.5:1 | 1.4.3 |

### 4.5 Fase 5 — Testes Específicos

**2.4.2 Page Titled:**
- [ ] Cada página tem `<title>` único e descritivo
- [ ] Título reflete estado (ex: "Busca · SmartLic" → "Resultados (42) · Busca · SmartLic")

**2.4.4 Link Purpose (In Context):**
- [ ] Texto de links é descritivo (não "clique aqui", "saiba mais")
- [ ] Links com mesmo texto vão para mesmo destino

**3.3.2 Labels or Instructions:**
- [ ] Todos inputs têm `<label>` associado
- [ ] Campos obrigatórios indicados visualmente e programaticamente
- [ ] Instruções de formato (ex: "DD/MM/AAAA") próximas ao campo

**4.1.3 Status Messages:**
- [ ] Toast notifications usam `role="status"` ou `aria-live`
- [ ] Loading states anunciados ao leitor de tela
- [ ] Contagem de resultados atualizada via `aria-live="polite"`

**1.4.1 Use of Color:**
- [ ] Informação nunca é comunicada apenas por cor
- [ ] Gráficos usam padrões/ícones além de cor
- [ ] Links identificáveis mesmo sem cor (sublinhado padrão)

**1.4.13 Content on Hover or Focus:**
- [ ] Tooltips: hoverable (não desaparecem ao mover mouse)
- [ ] Tooltips: dismissível com Escape
- [ ] Conteúdo adicional persistente até dismiss

## 5. Template de Finding

```markdown
### [F-ID] Título Descritivo

- **Severidade:** 🔴 Crítico | 🟠 Sério | 🟡 Moderado | 🟢 Leve
- **Critério WCAG:** X.X.X Nome do Critério (Nível A/AA)
- **Componente:** Nome do componente ou página
- **Descrição:** O que está em violação
- **Steps to Reproduce:**
  1. Navegue para [URL]
  2. Interaja com [elemento]
  3. Observe [problema]
- **Impacto:** Quem é afetado e como
- **Correção Recomendada:** O que mudar no código
- **Antes/Depois:** Exemplo de código
- **Prazo:** Imediato | Próximo sprint | Backlog
```

## 6. CI Integration

### 6.1 Playwright + axe-core (PR Gate)

```typescript
// tests/accessibility/a11y-scan.spec.ts
import { test, expect } from '@playwright/test';
import { injectAxe, checkA11y } from '@axe-core/playwright';

const CRITICAL_PAGES = [
  '/buscar',
  '/pipeline',
  '/dashboard',
  '/configuracoes',
];

for (const path of CRITICAL_PAGES) {
  test(`a11y scan: ${path}`, async ({ page }) => {
    await page.goto(path);
    await injectAxe(page);
    const results = await checkA11y(page, null, {
      detailedReport: true,
      detailedReportOptions: { html: true },
    });
    // Falha se violations incluir critical ou serious
    const violations = results.violations.filter(
      v => v.impact === 'critical' || v.impact === 'serious'
    );
    expect(violations).toEqual([]);
  });
}
```

### 6.2 GitHub Actions Workflow

Incluir no workflow de CI existente ou criar `.github/workflows/a11y-check.yml`:
- Dispara em PRs que tocam `frontend/**`
- Roda `npx playwright test tests/accessibility/`
- Bloqueia merge se houver violations critical/serious

## 7. Cronograma de Execução

| Fase | Descrição | Duração Estimada | Responsável |
|------|-----------|:---:|---|
| 1 | Scan axe-core todas as páginas | 2h | QA |
| 2 | Navegação por teclado | 3h | QA + Dev |
| 3 | Leitor de tela (NVDA + VoiceOver) | 3h | QA |
| 4 | Validação de contraste | 2h | UX/Design |
| 5 | Documentação de findings | 2h | QA |
| **Total** | | **12h (2 dias)** | |

## 8. Referências

- [WCAG 2.1 Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [axe-core Documentation](https://github.com/dequelabs/axe-core)
- [@axe-core/playwright](https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright)
- [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)
- [NVDA Screen Reader](https://www.nvaccess.org/)
- [Lighthouse Accessibility](https://developer.chrome.com/docs/lighthouse/accessibility/)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
