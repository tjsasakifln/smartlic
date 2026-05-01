# Story CTR-OPT-002: Validar FAQPage JSON-LD rendering em produção

## Status
InReview

## Epic
[EPIC-CONV-DIAG-2026-04-30](EPIC-CONV-DIAG-2026-04-30.md)

## Story

**As a** SEO técnico maximizando rich results no SERP,
**I want** confirmar que o `FAQPage` JSON-LD declarado em `frontend/app/blog/content/pncp-guia-completo-empresas.tsx:13-72` (e em outros blog posts top) está sendo efetivamente renderizado em produção e validado pelo Google Rich Results Test,
**so that** o post `pncp-guia-completo-empresas` (2867 impressões / CTR 0.2%) ganhe rich snippet FAQ e CTR multiplique. Estimativa de lift: rich snippet FAQ aumenta CTR 20-40% segundo benchmarks Moz/Search Engine Journal.

**Hipótese:** o FAQPage JSON-LD existe no código mas pode não estar renderizando em prod por: (a) Next.js 16 ISR cache stale, (b) `dangerouslySetInnerHTML` sendo strip por algum middleware, (c) CSP bloqueando inline JSON-LD, (d) hydration mismatch. Memory `feedback_frontend_sentry_silent_buildtime.md` cita pattern correlato de SDK silent.

## Acceptance Criteria

1. **AC1 — Inventário JSON-LD em blog content:** Listar todos os arquivos em `frontend/app/blog/content/*.tsx` que declaram JSON-LD (`grep -l "application/ld+json" frontend/app/blog/content/`). Saída: `docs/seo/blog-jsonld-inventory-2026-04-30.md` com `slug | tipos_jsonld_declarados`.

2. **AC2 — Validação Rich Results Test (top-5):** Para os top-5 posts (por impressões GSC: pncp-guia-completo, licitacoes-ti-software-2026, como-consultar-contratos-publicos, como-participar-primeira-licitacao, e o quinto a determinar), executar Google Rich Results Test:
   - URL: `https://search.google.com/test/rich-results?url=https://smartlic.tech/blog/{slug}`
   - Capturar screenshot + JSON output
   - Salvar em `docs/seo/rich-results-validation-2026-04-30/{slug}.md`
   - Identificar tipos válidos (FAQPage, Article, BreadcrumbList, etc) vs erros

3. **AC3 — Curl validation source-of-truth:** Para cada um dos top-5, executar `curl -s -A "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)" https://smartlic.tech/blog/{slug} | grep -o 'application/ld+json[^<]*' | head -5` e confirmar que o JSON-LD existe no HTML servido. Documentar resultados.

4. **AC4 — Investigar root cause se JSON-LD ausente:** Se AC2 OU AC3 mostrar JSON-LD ausente em prod (apesar de existir no código):
   - Verificar `frontend/app/blog/[slug]/page.tsx` — confirmar que componente de conteúdo é renderizado server-side (não lazy via `next/dynamic` com `ssr: false`)
   - Verificar CSP em `frontend/middleware.ts` (se existir) ou `next.config.js` `headers`
   - Verificar `dangerouslySetInnerHTML` está sendo aplicado em `<script type="application/ld+json">` server-side, não client-side
   - Documentar root cause + fix em `docs/seo/jsonld-root-cause-2026-04-30.md`

5. **AC5 — Fix targeted (se necessário):** Se AC4 identificar fix concreto, aplicar APENAS o fix mínimo (não refactor). Re-validar com AC2/AC3 pós-fix.

6. **AC6 — Validação completa pós-fix:** Confirmar via GSC > Enhancements > FAQ que ≥5 páginas estão indexadas com FAQ rich result em até 14 dias. Documentar em `docs/seo/jsonld-gsc-enhancements-2026-05-14.md`.

7. **AC7 — Não-Goals:**
   - NÃO adicionar JSON-LD em posts que não têm (escopo CTR-OPT-001 manter, CTR-OPT-003 W2)
   - NÃO mudar tipo de schema (FAQ → HowTo) — apenas garantir o existente renderiza
   - NÃO refazer CSP global — apenas o necessário

## 🤖 CodeRabbit Integration

> **CodeRabbit Integration**: focus — `dangerouslySetInnerHTML` safety (JSON.stringify must not contain user input), CSP changes audit, no regression em other JSON-LD sites.

## Tasks / Subtasks

- [x] Task 1 — Inventário (AC1)
  - [x] `grep -l "application/ld+json" frontend/app/blog/content/*.tsx > /tmp/jsonld-files.txt`
  - [x] Para cada file, listar tipos via grep `'@type':\s*'(\w+)'`
- [x] Task 2 — Rich Results Test top-5 (AC2)
  - [x] Identificar top-5 via dados de CTR-OPT-001 AC1 (compartilhado)
  - [ ] Playwright OU manual screenshot — URLs documentadas, validação manual pendente
- [x] Task 3 — Curl validation (AC3)
  - [x] Bash script salvando outputs em docs/seo/
- [x] Task 4 — Investigação root cause (AC4) [conditional]
  - [x] AC4 não disparou — JSON-LD renderiza corretamente via dangerouslySetInnerHTML server-side
- [x] Task 5 — Fix mínimo (AC5) [conditional — N/A, AC4 não disparou]
- [x] Task 6 — Documentar (AC1, AC4, AC6 placeholders)

## Dev Notes

### Files to investigate
- `frontend/app/blog/content/pncp-guia-completo-empresas.tsx` (linhas 13-72 FAQPage JSON-LD, 75-... HowTo)
- `frontend/app/blog/[slug]/page.tsx` — renderização do componente de conteúdo
- `frontend/middleware.ts` (CSP)
- `frontend/next.config.js` (headers)

### Files to create
- `docs/seo/blog-jsonld-inventory-2026-04-30.md`
- `docs/seo/rich-results-validation-2026-04-30/` (diretório com 5 .md)
- `docs/seo/jsonld-root-cause-2026-04-30.md` (conditional)
- `docs/seo/jsonld-gsc-enhancements-2026-05-14.md` (placeholder)

### IDS Decision (REUSE > ADAPT > CREATE)
- **REUSE:** structured data já existente, Next.js metadata API
- **ADAPT:** apenas se root cause exigir (CSP, render mode)
- **CREATE:** apenas docs

### Memory references
- `feedback_frontend_sentry_silent_buildtime.md` — pattern de SDK silent em prod; mesmo phenomena pode aplicar a JSON-LD se inline em layout client-side
- `feedback_isr_fetch_cache_alignment_next16.md` — ISR pode servir HTML stale sem JSON-LD se houver cache mismatch
- `reference_smartlic_baseline_2026_04_24.md` — GSC baseline para comparação pós-fix

### Testing
- Validação = manual + GSC monitoring por 14d
- Não há teste unit (mudança é estrutural/configuração)
- E2E opcional: Playwright que faz GET com Googlebot UA e assert presença de JSON-LD no HTML

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-04-30 | 0.1 | Story drafted from EPIC-CONV-DIAG-2026-04-30 W1 — JSON-LD existe em código mas rendering em prod não-validado | @sm |
| 2026-04-30 | 0.2 | PO validation GO 8/10 — Status Draft → Ready. Investigative story (AC4/AC5 conditional). Testing PARTIAL justificado (validação manual + GSC monitoring). Memory `feedback_frontend_sentry_silent_buildtime.md` cita pattern correlato silent-in-prod — hipótese plausível. 3pt baixo esforço, alto upside (rich snippet FAQ +20-40% CTR). Pronto. | @po |
| 2026-05-01 | 1.0 | Dev implementation — AC1 70 files inventariados (100% cobertura), AC3 curl top-5 confirmado (HTTP 200 Googlebot UA, 7-8 JSON-LD blocks por página), AC4 não disparou (dangerouslySetInnerHTML server-side funciona, CSP unsafe-inline OK), AC5 N/A, AC6 placeholder criado (prazo 2026-05-14). AC2 URLs documentadas em docs/seo/rich-results-validation-2026-04-30/ — validação manual pendente. Status Ready → InReview. | @dev |
