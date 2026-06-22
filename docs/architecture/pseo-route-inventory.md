# Inventário de Rotas pSEO — SmartLic

**Documento:** `docs/architecture/pseo-route-inventory.md`
**Fonte de verdade (máquina):** `docs/architecture/pseo-routes.yaml`
**Criado em:** 2026-06-22 — PSEO-000
**Versão:** 1

---

## Objetivo

Auditar e documentar o inventário completo de rotas pSEO (programmatic SEO) do SmartLic. Cada família de rota é classificada por sistema de renderização, funções de fetch, padrão de erro, e configuração de ISR.

**Sem este inventário, qualquer refatoração é cega.** PRs recentes (#2044, #2045, #2042, #2043) atacaram sintomas sem visão completa do sistema.

---

## Sumário Executivo

| Métrica | Valor |
|---------|-------|
| Total de famílias de rota | **18** |
| Total de arquivos `page.tsx` pSEO | **48** |
| Páginas estáticas estimadas | **~2.000** (SSG) |
| Páginas ISR estimadas | **~40.000+** (geração sob demanda) |
| Bibliotecas compartilhadas | **6** (`programmatic.ts`, `seo.ts`, `seo-metadata.ts`, `blog.ts`, `safe-fetch.ts`, `concurrency.ts`) |
| Backend routers pSEO | **18** (`*_publicos.py`, `observatorio.py`, `blog_stats.py`, etc.) |
| `error.tsx` presente em | **11/18** famílias |
| `loading.tsx` presente em | **0/18** famílias (só rotas autenticadas têm loading) |

---

## 1. Famílias de Rota

### 1.1 Blog Editorial

Rotas de conteúdo editorial produzido por humanos. Renderização via `lib/blog.ts` (CMS Supabase).

| Rota | Arquivo | Revalidate | Fetch Functions | error.tsx | loading.tsx |
|------|---------|------------|-----------------|-----------|-------------|
| `/blog` | `blog/page.tsx` | — (SSG) | — | `blog/error.tsx` | — |
| `/blog/[slug]` | `blog/[slug]/page.tsx` | — (SSR) | `getArticleBySlug` | `blog/error.tsx` | — |
| `/blog/author/[slug]` | `blog/author/[slug]/page.tsx` | 3600 | `getAuthorBySlug`, `getArticlesByAuthor` | `blog/error.tsx` | — |
| `/blog/weekly` | `blog/weekly/page.tsx` | — (SSG) | — | `blog/error.tsx` | — |
| `/blog/weekly/[slug]` | `blog/weekly/[slug]/page.tsx` | 3600 | `fetchWeeklyData` | `blog/error.tsx` | — |

**Volume estimado:** ~250 páginas (posts + autores + weekly)
**Sistema de renderização:** Blog Editorial (lib/blog.ts)
**Gaps:** Sem loading states.

### 1.2 Blog Programmatic

Rotas de blog geradas programaticamente a partir do DataLake. Maior família em volume de páginas.

| Rota | Arquivo | Revalidate | Fetch Functions | Backend Endpoint | Vol. |
|------|---------|------------|-----------------|------------------|------|
| `/blog/programmatic/[setor]` | `blog/programmatic/[setor]/page.tsx` | 3600 | `fetchSectorBlogStats`, `getSectorFromSlug`, `getEditorialContent` | `GET /v1/blog/stats/programmatic/{setor}` | 15 |
| `/blog/programmatic/[setor]/[uf]` | `blog/programmatic/[setor]/[uf]/page.tsx` | 3600 | `fetchSectorUfBlogStats`, `getSectorFromSlug`, `generateSectorFAQs` | `GET /v1/blog/stats/programmatic/{setor}/{uf}` | 405 |
| `/blog/licitacoes` | `blog/licitacoes/page.tsx` | — (SSG) | — | — | 1 |
| `/blog/licitacoes/[setor]/[uf]` | `blog/licitacoes/[setor]/[uf]/page.tsx` | 3600 | `fetchSectorUfBlogStats`, `getSectorFromSlug`, `generateLicitacoesFAQs` | `GET /v1/blog/stats/licitacoes/{setor}/{uf}` | 405 |
| `/blog/licitacoes/cidade/[cidade]` | `blog/licitacoes/cidade/[cidade]/page.tsx` | 3600 | `fetchCidadeStats`, `getCityBySlug` | `GET /v1/blog/stats/licitacoes/cidade/{cidade}` | 100 |
| `/blog/licitacoes/cidade/[cidade]/[setor]` | `blog/licitacoes/cidade/[cidade]/[setor]/page.tsx` | 3600 | `getCityBySlug`, `getSectorBySlug`, `generateCidadeSectorFAQs` | `GET /v1/blog/stats/licitacoes/cidade/{cidade}/{setor}` | 500 |
| `/blog/contratos/[setor]` | `blog/contratos/[setor]/page.tsx` | 3600 | `fetchContratosSetorStats`, `getSectorFromSlug`, `generateContratosSetorFAQs` | `GET /v1/blog/stats/contratos/{setor}` | 15 |
| `/blog/panorama` | `blog/panorama/page.tsx` | — (SSG) | — | — | 1 |
| `/blog/panorama/[setor]` | `blog/panorama/[setor]/page.tsx` | 3600 | `fetchPanoramaStats`, `getSectorFromSlug`, `generatePanoramaFAQs` | `GET /v1/blog/stats/panorama/{setor}` | 15 |
| `/blog/licitacoes-do-dia` | `blog/licitacoes-do-dia/page.tsx` | 3600 | `fetchLatestDigest` | `GET /v1/blog/stats/licitacoes-do-dia/latest` | 1 |
| `/blog/licitacoes-do-dia/[date]` | `blog/licitacoes-do-dia/[date]/page.tsx` | 3600 | `fetchDailyData`, `getAdjacentDates` | `GET /v1/blog/stats/licitacoes-do-dia/{date}` | 365 |

**Volume estimado:** ~1.800 páginas
**Sistema de renderização:** Direct Fetch (`lib/programmatic.ts`)
**error.tsx:** `blog/error.tsx` (compartilhado com blog editorial)
**Gaps:** Sem loading states. Sem error boundaries por sub-rota (todas compartilham `blog/error.tsx`).

### 1.3 Entity Pages — CNPJ / Fornecedores / Compliance

Páginas de perfil de entidade. Alto volume, ISR sob demanda.

| Rota | Arquivo | Revalidate | Fetch Functions | Fetch Pattern | Vol. |
|------|---------|------------|-----------------|---------------|------|
| `/cnpj` | `cnpj/page.tsx` | — (SSG) | — | — | 1 |
| `/cnpj/[cnpj]` | `cnpj/[cnpj]/page.tsx` | 3600 | `fetchPerfil` | `fetchWithBudget` (15s, retry=1, throwOn5xx) | 10k+ |
| `/fornecedores` | `fornecedores/page.tsx` | — (SSG) | — | — | 1 |
| `/fornecedores/[cnpj]` | `fornecedores/[cnpj]/page.tsx` | 3600 | `fetchFornecedoresStats` | `fetchWithBudget` (15s, throwOn5xx) | 5k+ |
| `/fornecedores/[cnpj]/[uf]` | `fornecedores/[cnpj]/[uf]/page.tsx` | 3600 | `fetchFornecedoresStats` | `ssgLimitedFetch` / `fetchWithBudget` | 1k+ |
| `/compliance` | `compliance/page.tsx` | — (SSG) | — | — | 1 |
| `/compliance/[cnpj]` | `compliance/[cnpj]/page.tsx` | — (SSR) | `fetchComplianceCheck` | `fetchWithBudget` | 500 |

**error.tsx:** `cnpj/error.tsx`, `fornecedores/error.tsx`, `compliance/error.tsx`
**Gaps:** Sem loading states. `/compliance/[cnpj]` sem revalidate definido (SSR puro).

### 1.4 Entity Pages — Órgãos, Municípios, Itens

| Rota | Arquivo | Revalidate | Fetch Functions | Fetch Pattern | Vol. |
|------|---------|------------|-----------------|---------------|------|
| `/orgaos` | `orgaos/page.tsx` | — (SSG) | — | — | 1 |
| `/orgaos-publicos` | `orgaos-publicos/page.tsx` | — (SSG) | — | — | 1 |
| `/orgaos/[slug]` | `orgaos/[slug]/page.tsx` | 3600 | `fetchOrgaoStats` | `ssgLimitedFetch` / `fetchWithBudget` | 5k+ |
| `/municipios` | `municipios/page.tsx` | — (SSG) | — | — | 1 |
| `/municipios/[slug]` | `municipios/[slug]/page.tsx` | 3600 | `fetchMunicipioStats` | `ssgLimitedFetch` | 5.570 |
| `/indice-municipal` | `indice-municipal/page.tsx` | — (SSG) | — | — | 1 |
| `/indice-municipal/[municipio-uf]` | `indice-municipal/[municipio-uf]/page.tsx` | 3600 | `fetchIndiceMunicipal` | `fetchWithBudget` | 5.570 |
| `/itens` | `itens/page.tsx` | — (SSG) | — | — | 1 |
| `/itens/[catmat]` | `itens/[catmat]/page.tsx` | 86400 | `fetchItemStats` | `ssgLimitedFetch` | 2k+ |

**Nota sobre `/itens/[catmat]`:** Única rota pSEO com `dynamic = 'force-static'`. Revalidate de 24h.
**error.tsx:** `orgaos/error.tsx`, `municipios/error.tsx`, `itens/error.tsx`
**Gaps:** Sem error.tsx em `orgaos-publicos` e `indice-municipal`. Sem loading states.

### 1.5 Data Pages — Licitações, Contratos, Observatório, Alertas

| Rota | Arquivo | Revalidate | Fetch Functions | Fetch Pattern | Vol. |
|------|---------|------------|-----------------|---------------|------|
| `/licitacoes` | `licitacoes/page.tsx` | — (SSG) | — | — | 1 |
| `/licitacoes/[setor]` | `licitacoes/[setor]/page.tsx` | 21600 | `fetchSectorLicitacoes`, `getSectorFromSlug` | `ssgLimitedFetch` (pool semaphore) | 15 |
| `/contratos` | `contratos/page.tsx` | — (SSG) | — | — | 1 |
| `/contratos/[setor]/[uf]` | `contratos/[setor]/[uf]/page.tsx` | 14400 | `fetchContratosStats`, `getSectorFromSlug` | `ssgLimitedFetch` (10s timeout, throwOn5xx) | 405 |
| `/contratos/orgao/[cnpj]` | `contratos/orgao/[cnpj]/page.tsx` | 14400 | `fetchOrgaoContratosStats` | `fetchWithBudget` (15s, throwOn5xx) | 3k+ |
| `/observatorio` | `observatorio/page.tsx` | — (SSG) | — | — | 1 |
| `/observatorio/[slug]` | `observatorio/[slug]/page.tsx` | 86400 | `fetchObservatorioArticle` | `ssgLimitedFetch` / `fetchWithBudget` | 500 |
| `/observatorio/embed/[slug]` | `observatorio/embed/[slug]/page.tsx` | — (SSR) | `fetchObservatorioArticle` | `fetch` direto | 500 |
| `/alertas-publicos` | `alertas-publicos/page.tsx` | — (SSG) | — | — | 1 |
| `/alertas-publicos/[setor]/[uf]` | `alertas-publicos/[setor]/[uf]/page.tsx` | 3600 | `fetchAlertasPublicos`, `getSectorFromSlug` | `fetchWithBudget` (15s) | 405 |

**error.tsx:** `licitacoes/error.tsx`, `contratos/error.tsx`, `observatorio/error.tsx`, `alertas-publicos/error.tsx`
**Gaps:** Sem loading states. `/observatorio/embed/[slug]` usa fetch direto sem pool protection.

### 1.6 Content & Marketing Pages

Páginas de conteúdo estático ou com fetch mínimo. Sem error boundaries dedicados.

| Rota | Arquivo | Revalidate | Fetch | error.tsx | Vol. |
|------|---------|------------|-------|-----------|------|
| `/calculadora` | `calculadora/page.tsx` | — (SSG) | — | — | 1 |
| `/calculadora/embed` | `calculadora/embed/page.tsx` | 3600 | — | — | 1 |
| `/estatisticas` | `estatisticas/page.tsx` | 21600 | `fetchStats` → `GET /v1/stats/public` | — | 1 |
| `/estatisticas/embed` | `estatisticas/embed/page.tsx` | 3600 | `fetchStats` | — | 1 |
| `/ferramentas/pncp-licitacoes` | `ferramentas/pncp-licitacoes/page.tsx` | 3600 | — | — | 1 |
| `/licitacoes-publicas-2026` | `licitacoes-publicas-2026/page.tsx` | 3600 | `fetchStats` | — | 1 |
| `/perguntas` | `perguntas/page.tsx` | — (SSG) | — | — | 1 |
| `/perguntas/[slug]` | `perguntas/[slug]/page.tsx` | 3600 | — | — | 30 |
| `/perguntas/indice-reajuste-contrato-publico` | `perguntas/indice-reajuste-contrato-publico/page.tsx` | 3600 | — | — | 1 |
| `/casos` | `casos/page.tsx` | — (SSG) | `getAllCases` | — | 1 |
| `/casos/[slug]` | `casos/[slug]/page.tsx` | 3600 | `getCaseBySlug` | — | 10 |
| `/guia` | `guia/page.tsx` | — (SSG) | — | — | 1 |
| `/guia/[slug]` | `guia/[slug]/page.tsx` | — (SSG) | — | — | 5 |
| `/guia/guia-pratico-b2g` | `guia/guia-pratico-b2g/page.tsx` | — (SSG) | — | — | 1 |
| `/glossario` | `glossario/page.tsx` | — (SSG) | — | — | 1 |
| `/glossario/[termo]` | `glossario/[termo]/page.tsx` | 3600 | `fetchTermo` | — | 100 |
| `/masterclass` | `masterclass/page.tsx` | 3600 | — | — | 1 |
| `/masterclass/[tema]` | `masterclass/[tema]/page.tsx` | 3600 | — | — | 10 |

### 1.7 Vertical Landing Pages

| Rota | Arquivo | Revalidate | error.tsx |
|------|---------|------------|-----------|
| `/para-empresas` | `para-empresas/page.tsx` | 3600 | — |
| `/para-advogados` | `para-advogados/page.tsx` | 3600 | — |
| `/para-construtoras` | `para-construtoras/page.tsx` | 3600 | — |
| `/para-consultorias` | `para-consultorias/page.tsx` | 3600 | — |
| `/para-empresas-de-ti` | `para-empresas-de-ti/page.tsx` | 3600 | — |
| `/para-fornecedores` | `para-fornecedores/page.tsx` | 3600 | — |
| `/para-quem-quer-subcontratar` | `para-quem-quer-subcontratar/page.tsx` | 3600 | — |
| `/como-avaliar-licitacao` | `como-avaliar-licitacao/page.tsx` | — (SSG) | — |
| `/como-evitar-prejuizo-licitacao` | `como-evitar-prejuizo-licitacao/page.tsx` | — (SSG) | — |
| `/como-filtrar-editais` | `como-filtrar-editais/page.tsx` | — (SSG) | — |
| `/como-priorizar-oportunidades` | `como-priorizar-oportunidades/page.tsx` | — (SSG) | — |
| `/intencao/comercial` | `intencao/comercial/page.tsx` | — (SSG) | — |
| `/intencao/investigativa` | `intencao/investigativa/page.tsx` | — (SSG) | — |
| `/intencao/juridica` | `intencao/juridica/page.tsx` | — (SSG) | — |
| `/intencao/subcontratacao` | `intencao/subcontratacao/page.tsx` | — (SSG) | — |

**Total:** 15 landing pages estáticas/marketing. Nenhuma possui `error.tsx` ou `loading.tsx`.

---

## 2. Bibliotecas Compartilhadas

### 2.1 `lib/programmatic.ts` (1004 LOC, 38 exports)

Motor central do pSEO. Contém:

- **Fetch functions:** `fetchSectorBlogStats`, `fetchSectorUfBlogStats`, `fetchPanoramaStats`, `fetchAlertasPublicos`, `fetchContratosSetorStats`
- **Static params generators:** `generateSectorParams`, `generateSectorUfParams`, `generateLicitacoesParams`
- **Editorial content:** `getEditorialContent`, `getPanoramaEditorial`, `getRegionalEditorial`, `getCidadeSectorEditorial`
- **FAQ generators:** `generateSectorFAQs`, `generatePanoramaFAQs`, `generateLicitacoesFAQs`, `generateContratosSetorFAQs`, `generateCidadeSectorFAQs`
- **Data constants:** `ALL_UFS`, `UF_NAMES`, `UF_PREPOSITIONS`, `SECTOR_SLUG_TO_BACKEND_ID`, `BACKEND_ID_TO_FRONTEND_SLUG`
- **Utilities:** `getSectorFromSlug`, `getUfPrep`, `formatBRL`, `formatBRLCompact`, `backendIdToFrontendSlug`

**Problema identificado:** 1004 LOC com fetch functions, types, editorial content (650+ linhas), FAQ generators, e static params — mas nenhuma página usa todas essas exports. Mix de responsabilidades (dados + conteúdo + UI).

### 2.2 `lib/seo.ts` (280 LOC, 9 exports)

Utilitários de metadata SEO: `buildCanonical`, `buildOperationalTitle`, `buildOperationalDescription`, `getFreshnessLabel`, `SITE_URL`.

### 2.3 `lib/blog.ts` (2494 LOC, 9 exports)

CMS editorial do blog: `getAllSlugs`, `getArticleBySlug`, `getAllAuthorSlugs`, `getAuthorBySlug`, `getArticlesByAuthor`, `fetchWeeklyData`, `fetchLatestDigest`, `fetchDailyData`.

### 2.4 `lib/safe-fetch.ts` (209 LOC, 3 exports)

`fetchWithBudget` — fetch unificado com timeout, retries, e `throwOn5xx` para ISR stale-preservation. Padrão recomendado para novas páginas.

### 2.5 `lib/concurrency.ts` (109 LOC, 2 exports)

`ssgLimitedFetch` — fetch com pool protection via `asyncio.Semaphore`. POOL-001 (`SEOSemaphore(3)`). Usado em páginas com `generateStaticParams` para evitar saturação do backend.

---

## 3. Matriz de Ciclo de Vida ISR

| Revalidate | Frescor | Uso | Páginas |
|------------|---------|-----|---------|
| **null (SSG)** | Build-time only | Landing pages, índices, how-to articles | ~30 |
| **3600 (1h)** | Alta frescor | Blog programmatic, entity pages, conteúdo | ~35 rotas |
| **14400 (4h)** | Média frescor | Contratos setor×UF, contratos/órgão | 2 rotas |
| **21600 (6h)** | Baixa frescor | Licitações/setor, estatísticas | 2 rotas |
| **86400 (24h)** | Mínima frescor | Observatório, itens CATMAT | 2 rotas |

**Risco de staleness:** Páginas com revalidate ≥ 6h podem servir dados desatualizados por até 24h. O circuit breaker e SWR devem ser validados para estas rotas (→ PSEO-011).

---

## 4. Gaps Documentados

### 4.1 Error Boundaries Ausentes

Rotas pSEO SEM `error.tsx`:

| Rota | Risco |
|------|-------|
| `/glossario`, `/glossario/[termo]` | Erro 500 → fallback para `app/error.tsx` raiz (genérico) |
| `/guia`, `/guia/[slug]`, `/guia/guia-pratico-b2g` | Idem |
| `/calculadora`, `/calculadora/embed` | Idem |
| `/estatisticas`, `/estatisticas/embed` | Idem |
| `/perguntas`, `/perguntas/[slug]` | Idem |
| `/casos`, `/casos/[slug]` | Idem |
| `/masterclass`, `/masterclass/[tema]` | Idem |
| `/para-*` (7 páginas) | Idem |
| `/como-*` (4 páginas) | Idem |
| `/intencao/*` (4 páginas) | Idem |
| `/orgaos-publicos` | Idem |
| `/licitacoes-publicas-2026` | Idem |
| `/indice-municipal`, `/indice-municipal/[municipio-uf]` | Idem |
| `/ferramentas/pncp-licitacoes` | Idem |

**Total:** 13 grupos de rota sem error boundary dedicado.

### 4.2 Loading States Ausentes

**NENHUMA rota pSEO possui `loading.tsx`.** Apenas rotas autenticadas (`(protected)`, `admin`, `buscar`, `conta`, `dashboard`, `historico`, `pipeline`, `planos`) têm loading states.

Impacto: durante regen ISR, o usuário vê a página antiga (stale) sem indicador de carregamento. Se a página nunca foi gerada (first visit), o servidor renderiza sincronamente — sem feedback visual de progresso.

### 4.3 Fetch sem Tipagem / Pool Protection

| Rota | Fetch Pattern | Risco |
|------|---------------|-------|
| `/observatorio/embed/[slug]` | `fetch` direto | Sem retry, sem pool, sem throwOn5xx |
| `/estatisticas` | `fetch` direto | Sem pool protection durante regen |

### 4.4 `lib/programmatic.ts` — Monólito de 1004 LOC

O arquivo mistura:
- Fetch functions (data fetching)
- Editorial content (650+ linhas de texto)
- FAQ generators (template strings)
- Type definitions
- Static params generators
- UF/Sector constants

**Nenhuma página consome todas as exports.** Isso será abordado em PSEO-002 (separação em módulos).

---

## 5. ADR-SEO-001: Prefixos Protegidos

16 prefixos de rota protegidos pela regra "nunca `notFound()` em gap de dados":

`/observatorio`, `/cnpj`, `/fornecedores`, `/orgaos`, `/municipios`, `/licitacoes`, `/contratos`, `/alertas-publicos`, `/itens`, `/blog`, `/casos`, `/glossario`, `/guia`, `/masterclass`, `/perguntas`, `/compliance`

**CI gate:** `.github/workflows/audit-seo-notfound.yml`
**ADR:** `docs/adr/ADR-SEO-001-programmatic-routes-no-notfound-on-data-gap.md`

---

## 6. Backend Routers pSEO (18 routers)

Todos em `backend/routes/`, públicos (sem auth), servindo dados para as páginas pSEO:

| Router | Endpoints | Descrição |
|--------|-----------|-----------|
| `blog_stats.py` | `/v1/blog/stats/*` | Stats para blog programmatic |
| `observatorio.py` | `/v1/observatorio/*` | Artigos do observatório |
| `empresa_publica.py` | `/v1/empresa/*` | Perfil B2G de empresa |
| `orgao_publico.py` | `/v1/orgaos/*` | Perfil de órgão público |
| `contratos_publicos.py` | `/v1/contratos/*` | Contratos — setor×UF, órgão |
| `dados_publicos.py` | `/v1/stats/public` | Dados agregados |
| `municipios_publicos.py` | `/v1/municipios/*` | Perfil de município |
| `itens_publicos.py` | `/v1/itens/*` | Item CATMAT |
| `compliance_publicos.py` | `/v1/compliance/*` | Compliance check |
| `indice_municipal.py` | `/v1/indice-municipal/*` | Índice municipal |
| `alertas_publicos.py` | `/v1/alertas-publicos/*` | Pré-visualização de alertas |
| `sectors_public.py` | `/v1/setores/*` | Lista de setores |
| `stats_public.py` | `/v1/stats/*` | Estatísticas públicas |
| `calculadora.py` | `/v1/calculadora/*` | Calculadora ROI |
| `comparador.py` | `/v1/comparador/*` | Comparador de editais |
| `daily_digest.py` | `/v1/daily-digest/*` | Digest diário |
| `weekly_digest.py` | `/v1/weekly-digest/*` | Digest semanal |
| `sitemap_*.py` (5) | `/v1/sitemap/*` | Sitemaps XML |

---

## 7. Issues Subsequentes (PSEO-002 a PSEO-014)

Este inventário (PSEO-000) desbloqueia as seguintes issues:

| Issue | Título | Dependência |
|-------|--------|-------------|
| PSEO-002 (#2065) | Separar conteúdo editorial e tipos em módulos | Bloqueado por PSEO-000 ✅ |
| PSEO-004 (#2066) | Error boundaries por grupo de rota | Bloqueado por PSEO-000 ✅ |
| PSEO-005 (#2067) | Loading boundaries (skeletons) | Bloqueado por PSEO-000 ✅ |
| PSEO-006 (#2068) | Unificar motor de renderização | Bloqueado por PSEO-002 |
| PSEO-007 (#2069) | Circuit breaker frontend | Bloqueado por PSEO-004 |
| PSEO-008 (#2070) | Observabilidade pSEO | Bloqueado por PSEO-000 ✅ |
| PSEO-009 (#2071) | Error handling centralizado backend | Independente |
| PSEO-010 (#2072) | Health endpoint pSEO | Independente |
| PSEO-011 (#2073) | Testes ISR stale-serve | Bloqueado por PSEO-004, PSEO-006 |
| PSEO-012 (#2075) | Validar impacto SEO | Bloqueado por PSEO-013 |
| PSEO-013 (#2076) | Rollout canário com feature flags | Bloqueado por PSEO-004, PSEO-006 |
| PSEO-014 (#2074) | Documentar arquitetura final + runbook | Bloqueado por todas acima |

---

## 8. Notas de Descoberta

1. **Nenhum PSEOTemplate unificado existe.** Cada página implementa seu próprio fetch + render, resultando em duplicação de padrões (error handling, metadata, FAQ rendering).

2. **3 padrões de fetch coexistem:** `fetchWithBudget` (recomendado), `ssgLimitedFetch` (pool), e `fetch` direto (legado). Não há consistência entre famílias de rota.

3. **`/itens/[catmat]` é a única rota com `dynamic = 'force-static'`.** Todas as outras usam `dynamic = 'auto'` (default).

4. **`/observatorio/embed/[slug]` é a única rota embed sem ISR.** Renderiza SSR puro — cada request bate no backend.

5. **Apenas 11 das 18 famílias têm `error.tsx`.** As 7 famílias sem error boundary dedicado caem no `error.tsx` raiz (`app/error.tsx`), que é genérico.

6. **`lib/programmatic.ts` com 1004 LOC** é o maior ponto de acoplamento. Qualquer mudança nos tipos ou fetch functions afeta todas as páginas que importam dele — mesmo que não usem a função alterada.
