# SERP Copy Guidelines — SmartLic Blog

**Story:** CTR-OPT-001  
**Date:** 2026-04-30  
**Scope:** All blog posts in `frontend/lib/blog.ts::BLOG_ARTICLES`

## Rules

### Title (max 60 chars)

**Structure:** `[Keyword] [Power Word/Number] [Year]` or `[Number] [Keyword]: [Benefit]`

**Required elements (at least 2 of 3):**
- Current year (2026) — signals freshness
- Specific number (e.g. "8 passos", "5 erros", "12 documentos")
- Benefit or power word

**Power words allowed:**
- prático, definitivo, completo (only if paired with a number)
- evite, descubra, desbloqueie
- em N passos / N erros / N documentos / N critérios

**Anti-patterns (NEVER use):**
- "Guia Completo" standalone (no number)
- "Como fazer X" as the full title
- Ellipsis (...)
- ALL CAPS
- Titles starting with "O que é" for commercial-intent posts

### Description (max 155 chars)

**Rule:** MUST start with an action verb in imperative or active present tense.

**Good openers:**
- Descubra, Aprenda, Compare, Veja, Entenda, Use, Evite, Calcule, Baixe

**Include at least 2 of:**
- Specific number or data point
- Named entity (PNCP, Lei 14.133, SICAF, etc.)
- Outcome or benefit
- Time signal (em 5 min, antes do pregão, em 2026)

**Anti-patterns (NEVER use):**
- Starting with "Guia prático", "Guia completo", "Tudo sobre"
- Starting with "Como" (weak — use action verb instead)
- Repeating the title verbatim
- Vague openers: "Saiba mais", "Conheça", "Este artigo"

## Examples

### Good

| Title | Chars | Why |
|-------|-------|-----|
| `PNCP 2026: 5 Filtros para Encontrar Licitações em Minutos` | 57 | number + year + benefit |
| `12 Erros que Desclassificam Propostas — e Como Evitá-los` | 57 | number + power word |
| `Checklist de Habilitação 2026: 47 Documentos Organizados` | 57 | number + year |

### Bad

| Title | Why Bad |
|-------|---------|
| `Licitações de TI e Software 2026 — Guia Completo` | "Guia Completo" no number |
| `Como Consultar Contratos Públicos no PNCP: Guia Completo` | "Como" opener + "Guia Completo" |
| `Análise de Viabilidade de Editais: O que Considerar antes de Participar` | 71 chars, no number, no year |

### Good description

`Descubra os 4 fatores que definem se um edital vale o investimento — modalidade, prazo, valor e UF. Aplique antes de comprometer sua equipe.`
(starts with action verb, has number, has named criteria, has benefit)

### Bad description

`Guia passo a passo para buscar editais no PNCP por setor e estado. Filtre oportunidades reais...`
(starts with "Guia", not an action verb)

## Char Counting Reference

Use: `echo -n "your title here" | wc -c` or count manually.

- 60 chars = safe zone for full display on desktop + mobile SERP
- 50 chars = ideal for mobile-first (SERP truncates at ~58 chars on Android)
- 155 chars = Google meta description limit (truncates at ~160 on desktop)

## Application Priority

1. AC4 mandated 3 posts — ALL requirements strict
2. Sectoral guides — apply number + drop "Guia Completo"
3. Transversal + BOFU + P7 — apply power word + action verb in description
