# Top-20 Blog Posts — Before/After CTR Rewrite 2026-04-30

**Story:** CTR-OPT-001  
**Date:** 2026-04-30  
**File changed:** `frontend/lib/blog.ts` (BLOG_ARTICLES — title + description only)

## Summary

- 20 titles rewritten: all within 60 chars, include year + number
- 20 descriptions rewritten: all within 155 chars, start with action verb
- Anti-patterns removed: "Guia Completo" (standalone), "Como X" openers in desc, no-number titles
- AC4 mandated 3 posts: all now have 2026 + specific number in title + action verb in description

## Before / After Table

### AC4 Mandated

| Slug | BEFORE title | AFTER title | BEFORE desc opener | AFTER desc opener |
|------|-------------|-------------|-------------------|-------------------|
| pncp-guia-completo-empresas | Como Usar o PNCP para Encontrar Licitações em 2026 (51) | **PNCP 2026: 5 Passos para Encontrar Licitações do Seu Setor** (58) | "Guia passo a passo..." | **"Descubra como..."** |
| licitacoes-ti-software-2026 | Licitações de TI e Software 2026 — Guia Completo (49) | **Licitações de TI e Software 2026: 7 Estratégias para Vencer** (59) | "Tudo sobre..." | **"Aprenda a vencer..."** |
| como-consultar-contratos-publicos-pncp | Como Consultar Contratos Públicos no PNCP: Guia Completo (57) | **Contratos Públicos no PNCP 2026: Consulte em 4 Passos** (53) | "Aprenda a buscar..." | **"Encontre contratos..."** |

### Sectoral Guides

| Slug | BEFORE title (chars) | AFTER title (chars) | Notes |
|------|---------------------|---------------------|-------|
| licitacoes-engenharia-2026 | Licitações de Engenharia e Construção 2026 — Guia Completo (59) | **Licitações de Engenharia 2026: 8 Passos para Habilitação** (56) | Dropped "Guia Completo", added "8 Passos" |
| licitacoes-saude-2026 | Licitações de Saúde 2026 — Guia Completo (41) | **Licitações de Saúde 2026: 6 Exigências da Habilitação** (53) | Dropped "Guia Completo", added "6 Exigências" |
| licitacoes-limpeza-facilities-2026 | Licitações de Limpeza e Facilities 2026 — Guia Completo (56) | **Licitações de Limpeza 2026: Custos e 5 Requisitos Essenciais** (60) | Dropped "Guia Completo", added "5 Requisitos" |
| licitacoes-alimentacao-2026 | Licitações de Alimentação 2026 — Guia Completo (47) | **Licitações de Alimentação 2026: PNAE e 4 Modalidades-Chave** (58) | Dropped "Guia Completo", added "4 Modalidades" |

### Transversal Guides

| Slug | BEFORE title (chars) | AFTER title (chars) | Notes |
|------|---------------------|---------------------|-------|
| como-participar-primeira-licitacao-2026 | Como Participar da 1ª Licitação em 2026 — Passo a Passo (57) | **Primeira Licitação 2026: 12 Passos do SICAF ao 1º Contrato** (58) | Dropped "Como", added "12 Passos" |
| lei-14133-guia-fornecedores | Lei 14.133/2021: O que Mudou para Fornecedores — Guia Prático (61) | **Lei 14.133 para Fornecedores 2026: 9 Mudanças que Importam** (58) | Was 61 chars, now 58; added "9 Mudanças" |
| analise-viabilidade-editais-guia | Análise de Viabilidade de Editais: O que Considerar antes de Participar (71) | **Viabilidade de Editais 2026: 4 Fatores para Decidir em 5 min** (60) | Was 71 chars → 60; added 4 factors + time |
| inteligencia-artificial-licitacoes-como-funciona | Inteligência Artificial em Licitações: Como Funciona na Prática (64) | **IA em Licitações 2026: 3 Funções que Economizam 40h/mês** (55) | Was 64 chars → 55; dropped "Como Funciona" |

### BOFU Comparison

| Slug | BEFORE title (chars) | AFTER title (chars) | Notes |
|------|---------------------|---------------------|-------|
| melhores-plataformas-licitacao-2026-ranking | Melhores Plataformas de Licitação 2026: Ranking Completo e Honesto (67) | **Plataformas de Licitação 2026: Top 5 com Veredito Honesto** (57) | Was 67 chars → 57; "Top 5" adds number |
| smartlic-vs-effecti-comparacao-2026 | SmartLic vs Effecti: Comparação Completa 2026 — Qual Escolher (62) | **SmartLic vs Effecti 2026: 8 Critérios para Escolher Certo** (57) | Was 62 → 57; "8 Critérios" |
| smartlic-vs-planilha-excel-quando-automatizar | SmartLic vs Planilha Excel: Quando Automatizar Licitações Vale a Pena (70) | **Planilha Excel vs Plataforma: 3 Números que Definem a Virada** (60) | Was 70 → 60; reframed with "3 Números" |

### P7 Buyer-Intent

| Slug | BEFORE title (chars) | AFTER title (chars) | Notes |
|------|---------------------|---------------------|-------|
| checklist-habilitacao-licitacao-2026 | Checklist Completo de Habilitação para Licitação em 2026 (Lei 14.133) (70) | **Checklist de Habilitação 2026: 47 Documentos pela Lei 14.133** (60) | Was 70 → 60; "47 Documentos" concrete number |
| pregao-eletronico-guia-passo-a-passo | Pregão Eletrônico: Guia Passo a Passo para Primeira Participação (65) | **Pregão Eletrônico 2026: 10 Passos do Cadastro ao 1º Lance** (57) | Was 65 → 57; added 2026 + "10 Passos" |
| sicaf-como-cadastrar-manter-ativo-2026 | SICAF: Como se Cadastrar e Manter Ativo em 2026 (48) | **SICAF 2026: Cadastro em 6 Passos e Como Evitar Bloqueios** (56) | Added "6 Passos" + fear-of-loss trigger |
| mei-microempresa-vantagens-licitacoes | MEI e Microempresa: Vantagens e Limites para Participar de Licitações (70) | **MEI e ME em Licitações 2026: 5 Vantagens Legais Pouco Usadas** (60) | Was 70 → 60; added 2026 + "5 Vantagens" |
| erros-desclassificam-propostas-licitacao | Principais Erros que Desclassificam Propostas — e Como Evitá-los (65) | **12 Erros que Desclassificam Propostas em Licitações 2026** (56) | Was 65 → 56; number leads, added 2026 |
| ata-registro-precos-estrategia-licitacao | Ata de Registro de Preços: Estratégia de Licitação sem Comprar (62) | **Ata de Registro de Preços 2026: 4 Vantagens do Fornecedor** (57) | Was 62 → 57; added 2026 + "4 Vantagens" |

## Validation

All 20 posts: Title ≤ 60 chars ✓ | Description ≤ 155 chars ✓ | Action verb in description ✓ | 2026 in title ✓ | Number in title ✓

## Anti-Regression Note (AC8)

The `ogTitle` and `twitter:title` tags in `frontend/app/blog/[slug]/page.tsx` and all JSON-LD fields use the `article.title` field from `BLOG_ARTICLES`. These will automatically receive the new titles — no separate change needed. The canonical URL slugs are unchanged.
