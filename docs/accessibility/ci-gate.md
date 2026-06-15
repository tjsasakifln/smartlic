# Accessibility CI Gate — axe-core no Pipeline

**Issue:** [#1871](https://github.com/tjsasakifln/SmartLic/issues/1871)
**Última atualização:** 2026-06-15

## Visão Geral

O CI Gate de acessibilidade integra o [axe-core](https://www.deque.com/axe/) via
[`@axe-core/playwright`](https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright)
no pipeline de CI do SmartLic. A cada PR que modifica componentes do frontend, o
workflow `a11y-gate.yml` escaneia 10 páginas críticas e bloqueia o merge se
violações **critical** ou **serious** forem detectadas.

## Como rodar localmente

### Pré-requisitos

```bash
cd frontend
npm install
```

O `@axe-core/playwright` já está nas dependências do projeto.

### Executar o scan completo (10 páginas)

```bash
npm run test:a11y
```

Isso roda o Playwright com o projeto `chromium` e gera relatório HTML + lista
no terminal. O servidor Next.js deve estar rodando em `http://localhost:3000`.

### Iniciar servidor separadamente (se preferir)

```bash
# Terminal 1: servidor Next.js
npm run dev

# Terminal 2: scan a11y
npm run test:a11y
```

### Executar página específica

```bash
npx playwright test e2e-tests/a11y/critical-pages.spec.ts -g "Home" --project=chromium
```

### Executar com navegador visível (debug)

```bash
npx playwright test e2e-tests/a11y/ --project=chromium --headed
```

## Páginas escaneadas

O scan cobre as 10 páginas críticas do funil de conversão e retenção:

| # | Página | Rota | Requer Auth | Mocks |
|---|--------|------|-------------|-------|
| 1 | Home | `/` | Nao | Nenhum |
| 2 | Login | `/login` | Nao | Nenhum |
| 3 | Signup | `/signup` | Nao | Nenhum |
| 4 | Planos | `/planos` | Nao | Plans API |
| 5 | Observatorio | `/observatorio` | Nao | Nenhum |
| 6 | Buscar | `/buscar` | Sim | Auth + Setores + Search + Download |
| 7 | Pipeline | `/pipeline` | Sim | Auth + Pipeline API |
| 8 | Conta | `/conta` | Sim | Auth + Subscription API |
| 9 | Checkout | `/planos/obrigado` | Sim | Auth + Plans + Checkout API |
| 10 | Onboarding | `/onboarding` | Sim | Auth |

## Threshold de violações

| Impacto | Comportamento no CI | Acao |
|---------|---------------------|------|
| `critical` | **BLOQUEIA o PR** | Deve ser corrigido antes do merge |
| `serious` | **BLOQUEIA o PR** | Deve ser corrigido antes do merge |
| `moderate` | Logado no relatorio | Permitido com comentario no PR documentando o porque |
| `minor` | Logado no relatorio | Nao bloqueante, triado assincronamente |

## Arquivos de configuracao

| Arquivo | Proposito |
|---------|-----------|
| `frontend/e2e-tests/a11y/axe-config.ts` | Configuracao centralizada do axe-core (tags WCAG, exclusoes, thresholds) |
| `frontend/e2e-tests/a11y/critical-pages.spec.ts` | Spec com 10 testes de pagina (um por pagina critica) |
| `frontend/e2e-tests/fixtures/axe.ts` | Fixture compartilhada do Playwright (makeAxeBuilder + assertNoSeriousViolations) |
| `.github/workflows/a11y-gate.yml` | Workflow CI que roda o scan em PRs |
| `frontend/package.json` | Script `test:a11y` |

## CI Workflow

O workflow `a11y-gate.yml`:

1. **Trigger:** PRs para `main` que modificam `frontend/app/components/**`, `frontend/e2e-tests/a11y/**`, `frontend/e2e-tests/fixtures/axe.ts`, ou o proprio workflow
2. **Build:** Compila o frontend em modo producao (`npm run build`)
3. **Start:** Inicia o servidor Next.js (standalone ou `next start`)
4. **Scan:** Executa `npm run test:a11y` com `CI=true`
5. **Report:** Gera relatorio HTML + JUnit XML
6. **Artifacts:** Upload do relatorio HTML, resultados JUnit e JSON de violacoes

**Tempo estimado:** ~5-8 minutos (vs ~15min do E2E completo)

## Triage de violacoes

Quando o CI falha por violacoes de acessibilidade:

1. Abra o artifact `a11y-report` do workflow run
2. Abra `index.html` no navegador
3. Para cada teste falho, expanda e veja o attachment `axe-<pagina>.json`
4. Filtre por `"impact": "critical"` ou `"impact": "serious"`
5. Identifique o seletor CSS em `nodes[].target` e o rule ID em `id`
6. Veja `docs/testing/a11y-e2e.md` para guia de correcao por rule ID

### Desabilitar uma regra (ultimo recurso)

Se a violacao for em codigo de terceiros (iframe Stripe, widget Google),
registre uma issue de tracking e desabilite a regra no spec:

```ts
const results = await makeAxeBuilder()
  .disableRules(['color-contrast']) // tracked in #ISSUE_NUM
  .analyze();
```

Maximo de 5 regras desabilitadas por spec.

## Adicionar novas paginas ao scan

1. Adicione um novo `test()` em `frontend/e2e-tests/a11y/critical-pages.spec.ts`
2. Se a pagina requer auth, use `mockAuthAPI(page, 'user')`
3. Adicione mocks de API conforme necessario (veja padroes nos testes existentes)
4. Rode localmente: `npm run test:a11y -g "Nome da pagina"`
5. Confirme zero violacoes critical/serious antes do PR

## Referencias

- [axe-core docs](https://www.deque.com/axe/)
- [@axe-core/playwright](https://github.com/dequelabs/axe-core-npm/tree/develop/packages/playwright)
- [WCAG 2.1 AA](https://www.w3.org/WAI/WCAG21/quickref/)
- [E2E A11y Triage Runbook](../testing/a11y-e2e.md)
- [Issue #1871](https://github.com/tjsasakifln/SmartLic/issues/1871)
