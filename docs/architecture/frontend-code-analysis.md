# Frontend Code Analysis — SmartLic

> **Ultima revisao:** 2026-06-15
> **Stack:** Next.js 16.1, React 18.3, TypeScript 5.9, Tailwind CSS 3.4
> **Estado:** Producao v0.5 — beta com trials pagos

---

## 1. Visao Geral

O frontend do SmartLic e uma aplicacao Next.js 16.1 com ~25 paginas core autenticadas/marketing + **10k+ paginas programmaticas SEO** (ISR `revalidate=3600`). A arquitetura segue o modelo de **API proxy** — o frontend nunca chama o backend diretamente; todas as requisicoes passam por route handlers do Next.js que atuam como intermediarios.

### 1.1 Estrutura de diretorios

```
frontend/
  app/                    # Next.js App Router — pages + API routes
    page.tsx              # Landing page (SSG)
    layout.tsx            # Root layout com providers globais
    (protected)/          # Rotas autenticadas (layout group)
    api/                  # ~50+ API proxy route handlers
    buscar/               # Pagina principal de busca
    components/           # Componentes compartilhados do app
    hooks/                # Hooks customizados
    types.ts              # Re-export de tipos gerados
  components/             # ~72+ componentes compartilhados
  lib/                    # Utilitarios, config, fetcher
  contexts/               # Contextos React (UserContext)
  layouts/                # Layouts compartilhados
```

### 1.2 Stack de dependencias principais

| Categoria | Biblioteca | Uso |
|-----------|-----------|-----|
| Framework | Next.js 16.1, React 18.3 | App Router, SSR/SSG/ISR |
| Tipagem | TypeScript 5.9 | Strict mode, interfaces |
| Estilo | Tailwind CSS 3.4 + CSS variables | Design system com tokens (WCAG AA) |
| Animacao | Framer Motion | Transicoes de pagina, micro-interacoes |
| Graficos | Recharts | Dashboard, analytics |
| State/Data | SWR 2.x | Data fetching, cache, revalidation |
| Auth | Supabase SSR | Autenticacao com cookies |
| Kanban | @dnd-kit | Pipeline de oportunidades (code-split) |
| Tour | Shepherd.js | Onboarding interativo (code-split) |
| Analytics | Sentry + Mixpanel + Clarity | Erros, eventos, heatmaps |
| Testes | Jest + React Testing Library | 2681+ testes, 376 arquivos |
| E2E | Playwright | 60 testes de fluxo critico |

---

## 2. Paginas Core

### 2.1 Autenticacao e Marketing (SSG/CSR)

| Rota | Proposito | Render | Autenticacao |
|------|-----------|--------|-------------|
| `/` | Landing page institucional | SSG | Nao |
| `/login` | Login com email/senha + Google OAuth | CSR | Nao |
| `/signup` | Cadastro | CSR | Nao |
| `/auth/callback` | Callback OAuth Supabase | CSR | Nao |
| `/recuperar-senha` | Recuperacao de senha | CSR | Nao |
| `/redefinir-senha` | Redefinicao de senha | CSR | Nao |
| `/planos` | Pagina de precos | SSG | Nao |
| `/planos/obrigado` | Pos-checkout | CSR | Sim |
| `/pricing` | Tabela de precos comparativa | SSG | Nao |
| `/features` | Funcionalidades | SSG | Nao |
| `/ajuda` | Central de ajuda com busca | SSG | Nao |
| `/termos` | Termos de uso | SSG | Nao |
| `/privacidade` | Politica de privacidade | SSG | Nao |
| `/sobre` | Sobre o SmartLic | SSG | Nao |
| `/stack` | Stack tecnologico | SSG | Nao |

### 2.2 Paginas Autenticadas Core (CSR, auth-gated)

| Rota | Proposito | Complexidade |
|------|-----------|-------------|
| `/buscar` | **Pagina principal** — formulario de busca com filtros, progresso SSE, resultados, grade de UFs | Alta — ~7 sub-hooks, SSE, paywall preview |
| `/dashboard` | Dashboard pessoal com 6 endpoints de analise | Media — Recharts, SWR multi-endpoint |
| `/historico` | Historico de buscas salvas e sessoes | Media — lista com paginacao, filtros |
| `/pipeline` | Kanban de oportunidades (drag-and-drop) | Alta — @dnd-kit code-split, tour integrado |
| `/mensagens` | InMail — suporte com threads | Media — chat 4-state lifecycle |
| `/onboarding` | Wizard 3-passos (CNAE -> UFs -> analise) | Media — CNAE mapping, auto-dispatch |
| `/conta` | Configuracoes da conta + billing portal + MFA | Media — multiplas abas, danger zone |
| `/conta/plano` | Gerenciamento de plano | Baixa |
| `/conta/equipe` | Convidar membros da equipe | Baixa |
| `/conta/seguranca` | MFA, sessoes ativas | Baixa |
| `/conta/api` | API keys | Baixa |
| `/conta/dados` | Exportacao de dados (LGPD) | Baixa |
| `/conta/preferencias` | Preferencias de notificacao | Baixa |
| `/conta/perfil` | Edicao de perfil | Baixa |
| `/conta/cancelar-trial` | Cancelamento de trial com survey | Media |

### 2.3 Paginas Admin (CSR, admin role)

| Rota | Proposito |
|------|-----------|
| `/admin` | Dashboard admin geral |
| `/admin/cache` | Gerenciamento de cache |
| `/admin/feature-flags` | Feature flags runtime |
| `/admin/emails` | Templates e disparos de email |
| `/admin/metrics` | Metricas do sistema |
| `/admin/partners` | Gestao de parceiros |
| `/admin/seo` | SEO admin |
| `/admin/slo` | SLO dashboard |
| `/admin/billing/sync` | Sincronizacao de billing |
| `/admin/calibration` | Calibracao de scoring |
| `/admin/founding` | Founding members admin |

### 2.4 Paginas Programmaticas SEO (ISR `revalidate=3600`)

Estas paginas sao geradas dinamicamente a partir do DataLake e impulsionam o inbound organico.

| Padrao de Rota | Volume Estimado | Fonte de Dados |
|---------------|----------------|---------------|
| `/observatorio/[slug]` | Milhares | `pncp_raw_bids` |
| `/observatorio/raio-x-{setor,municipio,orgao,alerta}/[id]` | Milhares | Agregacoes do DataLake |
| `/cnpj/[cnpj]` | Por fornecedor no DataLake | `pncp_supplier_contracts` |
| `/fornecedores/[cnpj]` | Por fornecedor | `pncp_supplier_contracts` |
| `/orgaos/[slug]` | Por orgao publico | `pncp_raw_bids` |
| `/municipios/[slug]` | Por municipio | `pncp_raw_bids` |
| `/licitacoes/[setor]` | Combinatorial setor x UF | DataLake |
| `/contratos/[setor]/[uf]` | Contratos por setor/UF | `pncp_supplier_contracts` |
| `/contratos/orgao/[cnpj]` | Contratos por orgao | `pncp_supplier_contracts` |
| `/blog/{contratos,licitacoes,panorama,programmatic}/[setor]` | Combinatorial setor | DataLake |
| `/alertas-publicos/[setor]/[uf]` | Preview de alertas | `pncp_raw_bids` |
| `/indice-municipal/[municipio-uf]` | Scoring municipal | `indice_municipal` |
| `/compliance/[cnpj]` | Dados de compliance | `pncp_supplier_contracts` |

**JSON-LD structured data** (FAQPage, Organization, ItemList) e injetado em todas as paginas SEO para enriquecimento de busca.

---

## 3. Componentes (~72+)

### 3.1 Componentes Compartilhados (`components/`)

#### `components/ui/` — Biblioteca base
| Componente | Proposito | Stories |
|-----------|-----------|---------|
| `button` | Botao com variantes (primary, secondary, ghost) | Sim |
| `Input` | Campo de texto estilizado | Sim |
| `Label` | Rotulo de formulario | Sim |
| `Modal` | Modal generico | Sim |
| `Pagination` | Navegacao paginada | Sim |
| `EmptyState` | Estado vazio com CTA | Sim |
| `ErrorMessage` | Mensagem de erro | Sim |
| `ErrorStateWithRetry` | Estado de erro com botao retry | Sim |
| `ViabilityBadge` | Badge de viabilidade (4 fatores) | Nao |
| `AnimateOnScroll` | Animacao ao scroll | Nao |
| `CurrencyInput` | Input monetario brasileiro | Nao |
| `PasswordStrengthIndicator` | Indicador de forca de senha | Nao |

#### `components/billing/` — Faturamento e planos
| Componente | Proposito |
|-----------|-----------|
| `PlanCard` | Card de plano |
| `PlanToggle` | Alternador mensal/anual |
| `PaymentFailedBanner` | Banner de falha de pagamento |
| `CancelSubscriptionModal` | Modal de cancelamento |
| `TrialUpsellCTA` | CTA de upgrade pos-trial |
| `TrialValueTracker` | Tracker de valor usado no trial |
| `TrialPaywall` | Paywall de trial expirado |
| `TrialExtensionCard` | Card de extensao de trial |
| `PaymentRecoveryModal` | Modal de recuperacao de pagamento |

#### `components/layout/` — Layout
| Componente | Proposito |
|-----------|-----------|
| `NavigationShell` | Shell de navegacao principal |
| `Sidebar` | Sidebar de navegacao |
| `BottomNav` | Navegacao inferior (mobile) |
| `MobileDrawer` | Drawer para mobile |
| `PageHeader` | Cabecalho de pagina |
| `MobileMenu` | Menu responsivo |

#### `components/tour/` — Onboarding
| Componente | Proposito |
|-----------|-----------|
| `Tour` | Wrapper Shepherd.js com steps configuraveis |

#### `components/auth/` — Autenticacao
| Componente | Proposito |
|-----------|-----------|
| `MfaEnforcementBanner` | Banner de imposicao MFA |
| `MfaSetupWizard` | Wizard de configuracao MFA |
| `TotpVerificationScreen` | Tela de verificacao TOTP |

#### Outros componentes compartilhados
| Componente | Categoria | Proposito |
|-----------|-----------|-----------|
| `ErrorBoundary` | Cross-cutting | Error boundary generico |
| `PageErrorBoundary` | Cross-cutting | Error boundary por pagina |
| `AuthLoadingScreen` | Cross-cutting | Tela de loading de auth |
| `SWRProvider` | Cross-cutting | Provider global SWR |
| `FeedbackButtons` | Cross-cutting | Botoes de feedback (like/dislike) |
| `ShareAnalysisButton` | Cross-cutting | Compartilhar analise |
| `EmptyStatePeriod` | Data | Estado vazio por periodo |
| `LoadingWithTimeout` | Cross-cutting | Loading com timeout |
| `Skeleton` | UI | Componente skeleton (loading states) |
| `AdminPageSkeleton` | Admin | Skeleton para paginas admin |
| `ContaPageSkeleton` | Account | Skeleton para pagina de conta |
| `PlanosPageSkeleton` | Plans | Skeleton para pagina de planos |
| `KeyboardShortcutsHelp` | UX | Ajuda de atalhos de teclado |
| `ProfileCompletionPrompt` | Onboarding | Prompt de completude de perfil |
| `ProfileCongratulations` | Onboarding | Parabens por completar perfil |
| `ProfileProgressBar` | Onboarding | Barra de progresso do perfil |
| `TrialProgressBar` | Trial | Barra de progresso do trial |
| `TrialExitSurveyModal` | Trial | Modal de survey de saida |
| `OnboardingTourButton` | Onboarding | Botao do tour de onboarding |
| `LeadCapture` | Marketing | Captura de lead |
| `ComingSoonPage` | Marketing | Pagina "em breve" |
| `CaseStudyCard` | Marketing | Card de case study |
| `FounderBadge` | Marketing | Badge de founding member |
| `CompatibilityBadge` | Marketing | Badge de compatibilidade |
| `GlobalErrorBoundary` | Cross-cutting | Error boundary global |

### 3.2 Componentes de Busca (`app/buscar/components/`, ~55 arquivos)

#### Principais componentes
| Componente | Proposito |
|-----------|-----------|
| `SearchForm` | Formulario principal com filtros (setor, UF, periodo, modalidade, valor) |
| `SearchResults` | Container de resultados com multi-estados |
| `FilterPanel` | Painel de filtros avancados |
| `UfProgressGrid` | Grid de progresso por UF (SSE) |
| `CacheBanner` | Banner de dados em cache |
| `DegradationBanner` | Banner de modo degradado |
| `PartialResultsPrompt` | Prompt de resultados parciais |
| `SourcesUnavailable` | Banner de fontes indisponiveis |
| `ErrorDetail` | Detalhamento de erro |
| `LlmSourceBadge` | Badge de classificacao LLM |
| `ReliabilityBadge` | Badge de confiabilidade |
| `EnhancedLoadingProgress` | Progresso de loading aprimorado |
| `WhyThisOpportunity` | Explicacao de por que uma oportunidade foi classificada |

#### Sub-componentes de resultados (`search-results/`)
| Componente | Proposito |
|-----------|-----------|
| `ResultCard` | Card individual de resultado |
| `ResultsList` | Lista de resultados |
| `ResultsHeader` | Cabecalho com contagem e acoes |
| `ResultsFilters` | Filtros inline de resultados |
| `ResultsPagination` | Paginacao de resultados |
| `ResultsToolbar` | Barra de ferramentas |
| `ResultsLoadingSection` | Sessao de loading |

### 3.3 Componentes do Pipeline (`app/pipeline/`)

| Componente | Proposito |
|-----------|-----------|
| `PipelineKanban` | Kanban drag-and-drop (code-split, lazy via `next/dynamic`) |
| `PipelineColumn` | Coluna do kanban |
| `PipelineCard` | Card de oportunidade |
| `PipelineMobileTabs` | Abas para mobile |
| `ReadOnlyKanban` | Kanban read-only (trial expirado) |

---

## 4. Data Flow

### 4.1 Fluxo de dados: SWR -> API Proxy -> Backend

```
[Componente React]
    | useSWR(url, fetcher)
    v
[SWR Provider] (config global: dedupingInterval=5s, errorRetryCount=3)
    |
    v
[API Proxy Route Handler] (app/api/*/route.ts)
    | fetch(backendUrl + path, { headers: { Authorization: Bearer <token> } })
    v
[Backend FastAPI] (api.smartlic.tech/v1/*)
    | Processa requisicao
    v
[Resposta JSON]
    |
    v
[SWR Cache] (L1 memoria + revalidateOnFocus=false)
    |
    v
[Componente React] renderiza com dados
```

### 4.2 API Proxy Layer

O diretorio `frontend/app/api/` contem ~50+ route handlers que atuam como proxy para o backend. Cada handler:

1. Extrai o token JWT do cookie de sessao do Supabase
2. Encaminha a requisicao para `NEXT_PUBLIC_BACKEND_URL`
3. Retorna a resposta para o frontend

**Principais proxies:** `buscar`, `buscar-progress`, `buscar-results`, `analytics`, `admin`, `feedback`, `trial-status`, `user`, `plans`, `pipeline`, `sessions`, `messages`, `onboarding`, `share`, `auth`, `setores`, `empresa`, `comparador`, `calculadora`, `download`, `export`, `billing`, `checkout`, `subscription-status`, `health`, `metrics`, `alerts`, `lead-capture`, `csp-report`, `pseo`, `referral`, `survey`, `organs`, `relatorio`, `reports`, `intel-reports`, `me`, `conta`, `mfa`, `change-password`, `stats`, `new-bids-count`, `first-analysis`, `profile-completeness`, `profile-context`, `sectors`

### 4.3 Fluxo de Busca (Buscar Page)

O fluxo de busca e o mais complexo do sistema, envolvendo 7 sub-hooks orquestrados:

```
[useSearchOrchestration] (orquestrador principal)
    |
    +-- useSearchState         (estado UI: abas, modais, filtros visuais)
    +-- useSearchFilters       (filtros de busca: setor, UF, periodo, etc.)
    +-- useSearch              (core: dispara POST /buscar, gerencia resultado)
    +-- useSearchSSE           (conexao SSE: progresso por UF em tempo real)
    +-- useSearchBillingState  (estado de billing: trial, quota, plano)
    +-- useSearchComputedProps (propriedades derivadas: fase, estado de UI)
    +-- useSearchExport        (exportacao: Excel, Google Sheets)
    +-- useSearchRetry         (retry de busca com fallback)
    +-- useSearchPersistence   (persistencia de ultima busca)
    +-- useUfProgress          (progresso individual por UF)
```

**Fluxo de requisicao:**

1. Usuario preenche formulario (`SearchForm`) e clica em "Buscar"
2. `useSearch.buscar()` faz POST `/buscar` -> API proxy -> backend (202 Accepted)
3. `useSearchSSE` abre conexao SSE com `GET /buscar-progress/{id}`
4. Backend envia eventos SSE: `uf_started`, `uf_complete`, `source_status`, `done`, etc.
5. `UfProgressGrid` renderiza progresso em tempo real
6. Ao receber `done`, `SearchResults` renderiza resultados com paginacao
7. `PartialResultsPrompt` aparece se houver timeout parcial

### 4.4 Camadas de Cache

```
[useSWR] -> dedupingInterval 5s, errorRetryCount 3
    |
    v
[SWR Cache] (em memoria, revalidateOnFocus=false)
    |
    v
[API Proxy] -> fetch(NEXT_PUBLIC_BACKEND_URL)
    |
    v
[Backend] -> L1 InMemoryCache (4h) -> L2 Redis (4h) -> Supabase search_results_cache (24h)
```

---

## 5. State Management

### 5.1 AuthProvider

`frontend/app/components/AuthProvider.tsx`

Provider global de autenticacao via Supabase SSR. Gerencia:

- `user`: Usuario logado ou null
- `session`: Sessao ativa
- `loading`: Estado de carregamento inicial
- `isAdmin`: Flag de admin (verifica `/v1/me`)
- `sessionExpired`: Sessao expirada
- Metodos: `signInWithEmail`, `signUpWithEmail`, `signInWithMagicLink`, `signInWithGoogle`, `signOut`

**Padroes de seguranca:**
- `isMountedRef` previne setState apos desmontagem (UX-408 AC1)
- Timeout com fallback para `getSession()` local (evita dependencia de rede)
- Auth guard redireciona para `/` se nao autenticado

### 5.2 SWRProvider

`frontend/components/SWRProvider.tsx`

Configuracao global do SWR:

```typescript
<SWRConfig value={{
  fetcher,              // fetch wrapper com tratamento de erro
  revalidateOnFocus: false,  // evita chamadas ao voltar de aba
  dedupingInterval: 5000,    // evita requisicoes duplicadas
  errorRetryCount: 3,        // retry com backoff exponencial
}}>
```

### 5.3 UserContext

`frontend/contexts/UserContext.tsx`

Contexto adicional para dados do usuario que nao fazem parte do auth (perfil, preferencias).

### 5.4 Estado de Busca (Search State)

O estado de busca e fragmentado em hooks especializados:

| Hook | Responsabilidade |
|------|-----------------|
| `useSearchState` | Estado de UI (abas abertas, modais, customize panel) |
| `useSearchFilters` | Estado dos filtros (setor, UF, periodo, modalidade, valor) |
| `useSearch` | Estado da busca (resultados, loading, erro) |
| `useSearchSSE` | Estado da conexao SSE (conectado, progresso, heartbeats) |
| `useSearchBillingState` | Estado de billing (trial restante, quota, plano) |
| `useSearchComputedProps` | Estado derivado (fase, exibir componentes) |

---

## 6. Code Splitting

### 6.1 Dynamic Imports (next/dynamic)

O projeto usa `next/dynamic` para code-split de componentes pesados:

| Componente | Pagina | Tamanho Estimado | Razoes |
|-----------|--------|-----------------|--------|
| `PipelineKanban` | `/pipeline` | Grande (200KB+) | @dnd-kit e dependencias de drag-and-drop |
| `ReadOnlyKanban` | `/pipeline` | Grande | @dnd-kit (mesmo bundle) |
| `SearchStateManager` | `/buscar` | Medio | Logica complexa de estado de busca |
| `ExportTimeSavedModal` | `/buscar` | Pequeno | So aparece apos primeira exportacao |
| `DashboardTimeSeriesChart` | `/dashboard` | Medio | Recharts dinamicamente |
| `DashboardDimensionsWidget` | `/dashboard` | Medio | Recharts |
| `DashboardProfileSection` | `/dashboard` | Medio | Perfil com graficos |
| `Tour` (interior do pipeline) | `/pipeline` | Medio | Shepherd.js e dependencias |
| `LoginForm` | `/login` | Medio | Formulario com validacao |
| `BlogPostContent` | `/blog/[slug]` | Medio | Conteudo de blog com markdown |

**Padrao de implementacao:**

```typescript
const PipelineKanban = dynamic(
  () => import("./PipelineKanban").then((mod) => mod.PipelineKanban),
  { ssr: false, loading: () => <KanbanSkeleton /> }
);
```

**Skeleton de loading** e sempre fornecido como `loading` prop para evitar layout shift.

### 6.2 Code Splitting por Pagina

- **Pipeline:** `@dnd-kit/core`, `@dnd-kit/sortable` — so carregam na pagina `/pipeline`
- **Tour:** `shepherd.js` — so carrega no pipeline e onboarding
- **Dashboard:** `recharts` — lazy nos widgets individuais
- **Busca:** `SearchStateManager` — lazy para reduzir bundle inicial da pagina

---

## 7. Padroes de Interface

### 7.1 Error Boundaries

Tres niveis de error boundary:

1. **Global** (`error.tsx`, `global-error.tsx`) — Captura erros nao tratados em qualquer pagina
2. **Por pagina** (`PageErrorBoundary`, `ErrorBoundary`) — Usado em `/conta`, `/dashboard`, `/historico`
3. **Por componente** (`SearchErrorBoundary`) — Captura erros especificos da busca, com `onReset` para recuperacao

**Implementacao do SearchErrorBoundary:**

```typescript
class SearchErrorBoundary extends Component<Props, State> {
  state = { hasError: false };
  static getDerivedStateFromError() { return { hasError: true }; }
  componentDidCatch(error, errorInfo) {
    console.error("[SearchErrorBoundary] Component crash:", error, errorInfo);
  }
}
```

### 7.2 Loading States

| Componente | Uso |
|-----------|-----|
| `Skeleton` | Loading generico para qualquer conteudo |
| `AdminPageSkeleton` | Loading de paginas admin |
| `ContaPageSkeleton` | Loading de pagina de conta |
| `PlanosPageSkeleton` | Loading de pagina de planos |
| `AuthLoadingScreen` | Tela de loading durante verificacao de auth |
| `LoadingWithTimeout` | Loading com timeout (fallback se demorar) |
| `ResultsLoadingSection` | Loading de resultados de busca |
| `ProgressBar` | Barra de progresso (busca) |
| `ProgressSteps` | Steps de progresso (busca) |
| `ProgressAnimation` | Animacao de progresso (busca) |
| `EnhancedLoadingProgress` | Loading aprimorado com estimativas |
| `NProgressProvider` | Barra de progresso no topo (navegacao) |

### 7.3 Empty States

| Componente | Uso |
|-----------|-----|
| `EmptyState` | Estado vazio generico com CTA |
| `EmptyStatePeriod` | Estado vazio por periodo (sem dados no periodo) |
| `SearchEmptyState` | Estado vazio da busca (sem resultados) |
| `EmptyResults` | Resultados vazios apos filtragem |
| `OnboardingEmptyState` | Estado vazio com CTA de onboarding |
| `ZeroResultsSuggestions` | Sugestoes quando busca retorna 0 resultados |

### 7.4 Banners de Estado

O sistema possui ~20 banners para comunicar estados ao usuario:

- `CacheBanner`, `ExpiredCacheBanner` — Estado do cache
- `DegradationBanner` — Modo degradado
- `PartialResultsPrompt`, `PartialTimeoutBanner` — Resultados parciais
- `RefreshBanner` — Dados desatualizados
- `SourcesUnavailable` — Fontes indisponiveis
- `FilterRelaxedBanner` — Filtros relaxados (zero resultados)
- `PaymentFailedBanner` — Falha de pagamento
- `TrialUpsellCTA` — Upsell de trial
- `CookieConsentBanner` — Consentimento LGPD
- `SessionExpiredBanner` — Sessao expirada
- `FoundersTopBanner` — Banner de founding members
- `ConnectionBanner` — Problemas de conexao
- `DataQualityBanner` — Qualidade dos dados
- `OnboardingBanner`, `OnboardingSuccessBanner` — Onboarding
- `RestoredResultsBanner` — Resultados restaurados
- `TruncationWarningBanner` — Resultados truncados
- `ReferralToast` — Indicacao

---

## 8. Analise de Bundle (Estimativas)

Com base na estrutura de dependencias e code-splitting:

| Pagina | Bundle JS Estimado | Dependencias Pesadas |
|--------|-------------------|---------------------|
| `/` (Landing) | ~120KB | Framer Motion, fontes |
| `/login` | ~150KB | Supabase Auth, formularios |
| `/buscar` | ~250KB | Framer Motion, SWR, SSE |
| `/dashboard` | ~280KB | + Recharts (lazy) |
| `/pipeline` | ~350KB | + @dnd-kit (lazy), Shepherd.js (lazy) |
| `/conta` | ~180KB | Multi-abas, formularios |
| `/observatorio/[slug]` (SEO) | ~100KB | Minimalista, SSR |
| `/cnpj/[cnpj]` (SEO) | ~100KB | Minimalista, SSR |

**Otimizacoes ativas:**
- Code-splitting de @dnd-kit e Shepherd.js
- `next/dynamic` com `ssr: false` para componentes que dependem de DOM
- Fontes com `display: swap` e preload seletivo
- SWR deduping (evita requisicoes duplicadas)
- `revalidateOnFocus: false` (evita revalidacao desnecessaria)

---

## 9. Sistema de Temas

O SmartLic usa **CSS variables** para o design system, com suporte a tema claro/escuro via `ThemeProvider`. As variaveis sao definidas em `globals.css` e seguem nomenclatura:

- `--brand-blue` — Cor primaria da marca
- `--surface-1`, `--surface-2` — Cores de superficie
- `--text-primary`, `--text-secondary` — Cores de texto
- `--border-default` — Cor de borda
- `--status-success`, `--status-warning`, `--status-error` — Cores de status

**Validacao WCAG AA** — todas as combinacoes de cor foram validadas para contraste.

---

## 10. Testes

### 10.1 Unitarios e Integracao (Jest + RTL)

- **376 arquivos de teste**, 2681+ testes passando
- Zero-failure policy
- `jest.setup.js` polyfills: `crypto.randomUUID` + `EventSource`
- Testes de componentes com `@testing-library/react`

### 10.2 E2E (Playwright)

- **60 testes** de fluxo critico do usuario
- Cobertura: login, busca, pipeline, billing, admin
- CI: `.github/workflows/e2e.yml`

### 10.3 Cobertura

- Threshold de cobertura: 60%
- Ferramenta: Jest `--coverage`

---

## 11. Observabilidade

| Ferramenta | Uso |
|-----------|-----|
| **Sentry** | Error tracking no frontend |
| **Mixpanel** | Eventos de produto e analise |
| **Microsoft Clarity** | Heatmaps e sessoes gravadas |
| **WebVitalsReporter** | Core Web Vitals (LCP, CLS, INP) |

Componentes de analytics:
- `AnalyticsProvider` — Provider global de eventos
- `GoogleAnalytics` — Google Analytics 4
- `ClarityAnalytics` — Microsoft Clarity
- `WebVitalsReporter` — Relatorio de Web Vitals
