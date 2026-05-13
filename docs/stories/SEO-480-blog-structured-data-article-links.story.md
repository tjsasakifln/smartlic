# SEO-480: /blog — adicionar structured data Blog + expor artigos no DOM

**Status:** Ready
**Origem:** Selenium Quality Audit — test_structured_data_present, test_blog_has_articles_listed (2026-04-22)
**Epic:** EPIC-SEO-2026-04
**Prioridade:** P1 — Alto (crawlability e rich results bloqueados)
**Complexidade:** M (Medium)
**Sprint:** SEO-sprint-atual
**Owner:** @dev
**Tipo:** Fix SEO + Crawlability

---

## Problema

O audit detectou 2 issues em `/blog`:

### Issue 1 — Structured data `Blog` ausente

`/blog` tem JSON-LD: `['Organization', 'WebSite', 'SoftwareApplication']`.
Falta o tipo `Blog` (ou `BlogPosting` list). Sem esse schema, Google não reconhece a página como hub de blog e não gera rich results de artigos (sitelinks, carrossel).

### Issue 2 — 0 artigos visíveis no DOM

Audit detectou 0 `article a`, `[class*='post'] a`, `[class*='article'] a` na página `/blog`.
Googlebot usa rendering JavaScript, mas crawlability de artigos individuais depende de links no HTML. Se os artigos são carregados via fetch client-side sem SSR, o Googlebot pode não os indexar via link discovery.

Métrica do audit:
```json
"blog_article_links_count": 0
```

---

## Critérios de Aceite

### Structured Data (AC1–AC2)

- [x] **AC1:** `/blog` inclui JSON-LD com `@type: "Blog"` (com `blogPost[]` de `BlogPosting` items)
- [x] **AC2:** Schema inclui `name`, `description`, e 10 `blogPost` entries com `headline`, `url`, `datePublished`

### Artigos no DOM (AC3–AC4)

- [x] **AC3:** Server Component renderiza artigos com `<a href="/blog/[slug]">` via SSR (props de `BLOG_ARTICLES` para `BlogListClient`)
- [x] **AC4:** Selenium audit passa: links contagem ≥5 via `<article>` semantic wrappers

### Regressão (AC5)

- [x] **AC5:** TypeScript compila sem erros. 591 blog tests passing (internal-links, programmatic, infrastructure, b2g-articles, consultorias-articles, contratos-setor, pncp-cluster).

---

## Investigação Prévia

Verificar se `/blog` usa `"use client"` no page.tsx — se sim, artigos são client-side only e Googlebot vê HTML vazio. Fix: mover fetch de artigos para Server Component ou usar `generateStaticParams`.

Arquivos prováveis:
- `frontend/app/blog/page.tsx` — adicionar structured data + confirmar SSR do listing
- `frontend/app/blog/layout.tsx` — se JSON-LD estiver no layout

---

## Riscos

- **R1 (Médio):** Se `/blog` usa `"use client"` — migrar para Server Component pode introduzir regressão se existir estado client-side na página. Investigar antes de implementar.
- **R2 (Baixo):** Adicionar `Blog` schema com artigos dinâmicos pode gerar schema inválido se campos obrigatórios (`headline`, `datePublished`) estiverem ausentes em algum post. Validar com schema.org validator.

## Dependências

- Nenhuma story bloqueante
- Epic: EPIC-SEO-2026-04

## Notas

- Não remover schemas existentes (`Organization`, `WebSite`, `SoftwareApplication`) — adicionar `Blog` ao array
- Validar schema em https://validator.schema.org após deploy (não committar URL)
- Prioridade alta: `/blog` é entrada orgânica para trial — artigos não crawleáveis = perda de tráfego SEO

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-22 | @sm | Story criada a partir do Selenium Quality Audit |
| 2026-04-22 | @po | Validação 10-point: **8/10 → GO** — adicionados Riscos, Dependências; R1 sinaliza investigação obrigatória antes do código |
| 2026-04-23 | @dev | Implementado em `20166f20` — JSON-LD Blog schema + `<article>` wrappers em /blog |
| 2026-05-13 | @dev | ACs verificadas: TypeScript OK, 591 blog tests passing, story fechada |
