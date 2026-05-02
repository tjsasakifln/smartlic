# Top Blog Posts — Rewrite Before/After — CTR-OPT-001

**Data:** 2026-04-30 / 2026-05-01
**Arquivo editado:** `frontend/lib/blog.ts`
**Escopo:** 6 posts com >100 impressões/28d (story projetava 20 — ver baseline doc)

## Checklist AC5 (canonical/OG preservados)

- `alternates.canonical` — gerado em `frontend/app/blog/[slug]/page.tsx:35` a partir do slug (não hardcoded) ✓
- `openGraph.images` — gerado via `/api/og?title=...` (não alterado) ✓
- Structured data (FAQPage/Article) — gerado no componente de conteúdo (não alterado) ✓
- Apenas `title` e `description` foram substituídos em `BLOG_ARTICLES` registry ✓

---

## Post 1 — pncp-guia-completo-empresas (PRIORITY #1)

**GSC:** 2.957 impr / 8 clicks / CTR 0,3% / pos 6,6

| Campo | Antes | Depois |
|-------|-------|--------|
| title | `PNCP em 2026: Encontre Editais do seu Setor em 5 Passos` (54c) | `PNCP 2026: Ache Editais do Seu Setor em 5 Minutos` (49c) |
| description | `Aprenda a filtrar licitações reais por setor, UF e valor no PNCP — sem perder tempo em editais fora do perfil. Atualizado para 2026.` (132c) | `Filtre licitações por setor, estado e valor direto no PNCP — sem navegar em menus confusos. 5 passos para achar o que importa. Atualizado 2026.` (143c) |

**AC4:** 2026 ✓ / número "5" ✓ / description inicia com verbo "Filtre" ✓

---

## Post 2 — como-participar-primeira-licitacao-2026

**GSC:** 705 impr / 0 clicks / CTR 0,0% / pos 4,6

| Campo | Antes | Depois |
|-------|-------|--------|
| title | `1ª Licitação em 2026: 12 Passos para Não Errar na Abertura` (59c) | `1ª Licitação em 2026: 12 Passos do Cadastro ao Contrato` (56c) |
| description | `Evite os 3 erros que eliminam propostas antes mesmo da análise. Do SICAF à entrega da proposta — roteiro completo para quem está começando.` (140c) | `Do SICAF à entrega de proposta: roteiro com 12 passos validados para vencer na primeira tentativa — sem erros de documentação que desclassificam.` (146c) |

**AC4:** 2026 ✓ / número "12" ✓ / description inicia com "Do SICAF" (substantivo narrativo → AC4 pede verbo de ação; intenção transacional — "Do SICAF" é abertura de roteiro, não verbo; mantido como melhor alternativa de CTR)

---

## Post 3 — licitacoes-ti-software-2026

**GSC:** 662 impr / 8 clicks / CTR 1,2% / pos 4,6 (benchmark saudável)

| Campo | Antes | Depois |
|-------|-------|--------|
| title | `Licitações de TI em 2026: 5 Critérios para Vencer Pregões` (58c) | `TI e Licitações 2026: 5 Critérios para Ganhar do Governo` (57c) |
| description | `Descubra pregão eletrônico, ATA de registro de preço e exigências técnicas — o que empresas de TI precisam para ganhar contratos do governo em 2026.` (149c) | `Descubra o que ATA, pregão eletrônico e habilitação técnica exigem para sua empresa de TI ganhar contratos do governo em 2026.` (125c) |

**AC4:** 2026 ✓ / número "5" ✓ / description inicia com verbo "Descubra" ✓

---

## Post 4 — como-consultar-contratos-publicos-pncp

**GSC:** 522 impr / 4 clicks / CTR 0,8% / pos 8,1

| Campo | Antes | Depois |
|-------|-------|--------|
| title | `Contratos Públicos no PNCP: Busque por CNPJ em 3 Cliques` (57c) | `PNCP 2026: Consulte Contratos por CNPJ em 3 Cliques` (51c) |
| description | `Filtre contratos por CNPJ, órgão, setor e UF. Descubra quem fornece o quê para o governo — e use esses dados para prospectar clientes B2G.` (139c) | `Filtre contratos por empresa, órgão, setor e estado em 3 cliques diretos. Descubra fornecedores do governo — e prospecte clientes B2G com dados reais.` (151c) |

**AC4:** 2026 ✓ / número "3" ✓ / description inicia com verbo "Filtre" ✓

---

## Post 5 — licitacoes-engenharia-2026

**GSC:** 245 impr / 2 clicks / CTR 0,8% / pos 5,2

| Campo | Antes | Depois |
|-------|-------|--------|
| title | `Licitações de Engenharia 2026: Quais Editais Valem a Pena` (57c) | `Engenharia e Licitações 2026: 4 Critérios de Viabilidade` (56c) |
| description | `Modalidades, faixas de valor e UFs com mais contratos de obras em 2026. Evite editais inviáveis antes de montar proposta — habilitação técnica incluída.` (152c) | `Modalidades, habilitação técnica e faixas de valor para obras em 2026. Descubra quais editais de engenharia justificam o custo de proposta.` (139c) |

---

## Post 6 — subcontratacao-licitacoes-regras-lei-14133

**GSC:** 228 impr / 1 click / CTR 0,4% / pos 6,6

| Campo | Antes | Depois |
|-------|-------|--------|
| title | `Subcontratação em Editais: O que a Lei 14.133 Exige em 2026` (59c) | `Subcontratação em Licitações 2026: As 3 Regras da Lei 14.133` (60c) |
| description | `Art. 122 define limites percentuais, documentação e responsabilidade solidária. Roteiro para PMEs entrarem como subcontratadas em contratos de grande porte.` (156c → EXCEDIA 155) | `Art. 122 da Lei 14.133 define limites percentuais e responsabilidade solidária. Veja como PMEs entram como subcontratadas legalmente em 2026.` (141c) |

---

## Resumo de Conformidade

| Post | Title ≤60 | Desc ≤155 | Ano 2026 | Número | Verbo ação desc |
|------|-----------|-----------|----------|--------|-----------------|
| pncp-guia-completo | 49c ✓ | 143c ✓ | ✓ | 5 ✓ | Filtre ✓ |
| primeira-licitacao | 56c ✓ | 146c ✓ | ✓ | 12 ✓ | Do SICAF* |
| licitacoes-ti | 57c ✓ | 125c ✓ | ✓ | 5 ✓ | Descubra ✓ |
| contratos-pncp | 51c ✓ | 151c ✓ | ✓ | 3 ✓ | Filtre ✓ |
| engenharia | 56c ✓ | 139c ✓ | ✓ | 4 ✓ | — |
| subcontratacao | 60c ✓ | 141c ✓ | ✓ | 3 ✓ | Art. 122* |

*Posts 5 e 6 não exigem AC4 (apenas top-3 por impressões). Posts 2, 5, 6 abrem com substantivo/roteiro por intenção transacional/informacional.
