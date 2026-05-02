# Story CTR-OPT-001: Rewrite title/meta dos top-20 blog posts GSC (CTR multiplier)

## Status
InProgress

## Epic
[EPIC-CONV-DIAG-2026-04-30](EPIC-CONV-DIAG-2026-04-30.md)

## Story

**As a** content marketer querendo multiplicar CTR orgânico sem investir em mais conteúdo,
**I want** rewrite dos titles e meta-descriptions dos top-20 blog posts indexados (com >100 impressões/28d em GSC) usando copy benefit-driven + nº/data + power words,
**so that** o CTR médio destas páginas suba de 1.3% para ≥3% nos próximos 30d. Lift estimado em 1 post (`pncp-guia-completo-empresas`, baseline CTR 0.2%): de 6 → 58 clicks/mês com 8pt de trabalho (9x lift).

**User explicitamente pediu:** "conteúdo deve ser simplesmente irresistível e de valor genuíno, potencialmente viral entre empresas e pessoas B2G".

## Acceptance Criteria

1. **AC1 — Lista top-20 GSC:** Compilar lista dos 20 blog posts com >100 impressões em 28d via GSC Search Performance (filtrar por path `^/blog/`). Saída: tabela `docs/seo/top-20-blog-baseline-2026-04-30.md` com colunas `slug | impressions_28d | clicks_28d | ctr_atual | position_avg | title_atual | description_atual`. **Output literal e auditável.**

2. **AC2 — Diretrizes de copy SERP:** Documentar em `docs/seo/serp-copy-guidelines.md` as regras a seguir para todo rewrite:
   - **Title (max 60 chars):** Benefit-driven + power word + nº/data quando aplicável. Exemplo: "PNCP em 2026: Guia Prático para Achar Editais em 5 Minutos" (NÃO "PNCP: Guia Completo para Empresas — Como Buscar e Monitorar Editais")
   - **Meta description (max 155 chars):** Promessa específica + chamada para ação implícita + sinal de autoridade. Exemplo: "Aprenda em 8 passos a encontrar editais relevantes no PNCP, com filtros que poucos conhecem. Atualizado para 2026."
   - **Power words validadas:** prático, definitivo, em [N] passos, atualizado [ano], evite, antes que, descubra, desbloqueie, [N] erros que
   - **Anti-padrões:** "Guia Completo" (cliché), "Como fazer X" (genérico), reticências, ALL CAPS

3. **AC3 — Rewrite dos top-20:** Para CADA um dos 20 posts em AC1:
   - Atualizar `metadata` export em `frontend/app/blog/[slug]/page.tsx::generateMetadata` SE título for derivado dinâmico, OU
   - Atualizar o objeto `metadata` no arquivo de conteúdo em `frontend/app/blog/content/{slug}.tsx` (verificar se exporta metadata — alguns são apenas componentes; nesses casos atualizar `BLOG_POSTS` registry se houver, OU `generateMetadata` central)
   - Documentar TODAS as mudanças (before/after) em `docs/seo/top-20-blog-rewrite-2026-04-30.md`

4. **AC4 — Top-3 priority com data específica:** Para os 3 posts de maior impressão (`pncp-guia-completo-empresas` 2867, `licitacoes-ti-software-2026` 614, `como-consultar-contratos-publicos-pncp` 481), o rewrite DEVE incluir explicitamente:
   - Ano "2026" no title
   - Número específico no title (ex: "8 passos", "5 erros")
   - Verbo de ação no início da description

5. **AC5 — Não quebrar canonical/OG:** Manter `alternates.canonical`, `openGraph.images`, structured data (FAQPage, Article) intactos. Apenas substituir `title` + `description`. Verificar via grep que não há outras referências hardcoded ao title antigo.

6. **AC6 — Não-Goals (escopo claro):** Esta story NÃO faz:
   - Re-escrita de corpo do artigo (apenas SERP copy)
   - A/B test de titles (escopo CTR-OPT-006 W3)
   - Novos artigos (escopo CTR-OPT-003/004 W2)
   - Mudança de URLs/slugs (preservaria backlinks; out of scope)

7. **AC7 — Validation pós-deploy:** Após merge, monitorar GSC por 14 dias e comparar CTR delta dos 20 posts vs baseline. Aceitar como sucesso se ≥10 posts mostrarem CTR delta > +50% em 14d. Documentar em `docs/seo/ctr-opt-001-results-2026-05-14.md` (criar empty placeholder para QA reabrir).

8. **AC8 — Top-20 sem regressão de impressões:** Se algum post mostrar **redução** de impressões > 30% em 14d (sinal de over-optimization gerando penalidade), reverter o rewrite específico daquele post.

## 🤖 CodeRabbit Integration

> **CodeRabbit Integration**: focus — não quebrar canonical URLs, manter structured data intacta, não introduzir typos pt-BR (acentos), char count 60/155 enforced.

## Tasks / Subtasks

- [x] Task 1 — Compilar lista top-20 GSC (AC1)
  - [x] Acessar GSC Search Performance via Playwright OU `gh api` (se houver integração)
  - [x] Exportar CSV → converter para `docs/seo/top-20-blog-baseline-2026-04-30.md`
- [x] Task 2 — Documentar guidelines (AC2)
  - [x] Criar `docs/seo/serp-copy-guidelines.md`
- [x] Task 3 — Identificar onde editar metadata (AC3)
  - [x] Investigar `frontend/app/blog/[slug]/page.tsx::generateMetadata` (linha 35) — centralizado em `BLOG_ARTICLES` registry (`frontend/lib/blog.ts`) — 1 arquivo cobre todos os posts
  - [x] Rewrite aplicado em `frontend/lib/blog.ts` para os 6 posts qualificados (>100 impr)
- [x] Task 4 — Rewrite top-3 (AC4)
- [x] Task 5 — Rewrite restantes 3 (escopo real: 6 posts total, não 20)
- [x] Task 6 — Documentar todos before/after em `docs/seo/top-20-blog-rewrite-2026-04-30.md`
- [x] Task 7 — Criar placeholder para validation (AC7)

## Dev Notes

### Files to investigate (recon needed)
- `frontend/app/blog/[slug]/page.tsx:35` — `generateMetadata` central?
- `frontend/app/blog/page.tsx:13` — `export const metadata` para listing
- `frontend/app/blog/content/{slug}.tsx` — 20 arquivos a auditar
- Possível `frontend/app/blog/posts-registry.ts` ou similar (recon)

### Files to create
- `docs/seo/top-20-blog-baseline-2026-04-30.md`
- `docs/seo/serp-copy-guidelines.md`
- `docs/seo/top-20-blog-rewrite-2026-04-30.md`
- `docs/seo/ctr-opt-001-results-2026-05-14.md` (placeholder)

### IDS Decision (REUSE > ADAPT > CREATE)
- **REUSE:** `generateMetadata` Next.js pattern, `BLOG_POSTS` registry se existir, OG image template existente
- **ADAPT:** title/description nos arquivos de conteúdo (apenas SERP fields, não corpo)
- **CREATE:** 4 docs/seo md files

### Memory references
- `reference_smartlic_baseline_2026_04_24.md` — GSC 1.3% CTR atual; impressions 9.9k 28d
- `feedback_build_hammers_backend_cascade.md` — não relevante (apenas metadata, sem fetch)
- Memory NOVA candidata pós-deploy: "CTR baseline 2026-04-30 + delta 2026-05-14" para tracking longitudinal

### Testing
- Não há teste unit (mudança é metadata estática)
- Validation = manual via GSC + Rich Results test
- QA: rodar `gh api` ou Playwright contra `https://search.google.com/test/rich-results?url=https://smartlic.tech/blog/{slug}` para top-3
- Acceptance final = AC7 (14d pós-deploy)

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-04-30 | 0.1 | Story drafted from EPIC-CONV-DIAG-2026-04-30 W1 — pncp-guia-completo CTR 0.2% / 2867 impr é alvo prioritário | @sm |
| 2026-04-30 | 0.2 | PO validation GO 8/10 — Status Draft → Ready. Tech Guidance PARTIAL pois Task 3 inicia com recon (BLOG_POSTS registry vs per-file metadata) — aceitável: 5min grep resolve. Testing PARTIAL pois métrica é GSC delta 14d (placeholder AC7 criado). AC8 anti-regression cobre over-optimization risk. ROI 9x em pncp-guia-completo justifica P0. Pronto. | @po |
| 2026-05-01 | 1.0 | Implementação completa. Metadata centralizado em `frontend/lib/blog.ts` (BLOG_ARTICLES registry). 6 posts reescritos (escopo real: apenas 6 BLOG_ARTICLES com >100 impr/28d, não 20). AC1-AC7 concluídos. Canonical/OG preservados (gerados dinamicamente, não hardcoded). | @dev |
