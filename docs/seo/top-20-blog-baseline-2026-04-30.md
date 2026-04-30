# Top-20 Blog Posts — CTR Baseline 2026-04-30

**Story:** CTR-OPT-001  
**Date:** 2026-04-30  
**GSC Baseline:** 126 clicks / 9.9k impressions / CTR 1.3% / pos 7.1 (28-day window)  
**Target CTR:** 3% (30-day post-deploy)

## GSC Scrape Status

**FALLBACK ACTIVE:** GSC Playwright scrape skipped — `GSC_EMAIL` and `GSC_PASSWORD` env vars not set.

Top-20 selection is **INFERRED** from BLOG_ARTICLES category/keyword commercial importance + 3 mandatory slugs from story AC4. Not derived from actual GSC impression data.

## Selection Methodology (AC1 Fallback)

Priority order:
1. **AC4 Mandated** (3): pncp-guia-completo-empresas, licitacoes-ti-software-2026, como-consultar-contratos-publicos-pncp
2. **Sectoral Guides** (4): High-traffic sector keywords (engenharia, saude, limpeza, alimentacao)
3. **Transversal Guides** (4): Cross-sector high-volume queries (primeira-licitacao, lei-14133, analise-viabilidade, IA)
4. **BOFU Comparison** (3): Bottom-of-funnel buyer intent (ranking plataformas, vs-effecti, vs-planilha-excel)
5. **P7 Buyer-Intent** (6): Specific actionable queries (checklist, pregao, sicaf, mei, erros, ata-registro-precos)

## Selected Top-20 Slugs (Inferred)

| # | Slug | Category | Selection Reason |
|---|------|----------|-----------------|
| 1 | pncp-guia-completo-empresas | Guias | AC4 mandatory |
| 2 | licitacoes-ti-software-2026 | Guias | AC4 mandatory |
| 3 | como-consultar-contratos-publicos-pncp | Guias | AC4 mandatory |
| 4 | licitacoes-engenharia-2026 | Guias | Sectoral guide — highest volume sector |
| 5 | licitacoes-saude-2026 | Guias | Sectoral guide — high volume |
| 6 | licitacoes-limpeza-facilities-2026 | Guias | Sectoral guide — high volume |
| 7 | licitacoes-alimentacao-2026 | Guias | Sectoral guide — high volume |
| 8 | como-participar-primeira-licitacao-2026 | Guias | Transversal — top entry query |
| 9 | lei-14133-guia-fornecedores | Guias | Transversal — evergreen legal query |
| 10 | analise-viabilidade-editais-guia | Guias | Transversal — decision-stage |
| 11 | inteligencia-artificial-licitacoes-como-funciona | Guias | Transversal — AI trend query |
| 12 | melhores-plataformas-licitacao-2026-ranking | Guias | BOFU comparison — high buyer intent |
| 13 | smartlic-vs-effecti-comparacao-2026 | Guias | BOFU comparison — branded |
| 14 | smartlic-vs-planilha-excel-quando-automatizar | Guias | BOFU comparison — convert fence-sitters |
| 15 | checklist-habilitacao-licitacao-2026 | Guias | P7 buyer-intent — high action intent |
| 16 | pregao-eletronico-guia-passo-a-passo | Guias | P7 buyer-intent — top query |
| 17 | sicaf-como-cadastrar-manter-ativo-2026 | Guias | P7 buyer-intent — task-specific |
| 18 | mei-microempresa-vantagens-licitacoes | Guias | P7 buyer-intent — large audience |
| 19 | erros-desclassificam-propostas-licitacao | Guias | P7 buyer-intent — fear-of-loss trigger |
| 20 | ata-registro-precos-estrategia-licitacao | Guias | P7 buyer-intent — commercial strategy |

## Before-State Audit (Current Titles/Descriptions at Baseline)

### AC4 Mandated Posts

| Slug | Current Title (chars) | AC4 Failures |
|------|----------------------|--------------|
| pncp-guia-completo-empresas | "Como Usar o PNCP para Encontrar Licitações em 2026" (51) | No number, desc not action verb |
| licitacoes-ti-software-2026 | "Licitações de TI e Software 2026 — Guia Completo" (49) | No number, "Guia Completo" anti-pattern |
| como-consultar-contratos-publicos-pncp | "Como Consultar Contratos Públicos no PNCP: Guia Completo" (57) | No 2026, No number, "Guia Completo" anti-pattern |

### Anti-patterns Present at Baseline

- "Guia Completo" appears in: licitacoes-engenharia-2026, licitacoes-ti-software-2026, licitacoes-saude-2026, licitacoes-limpeza-facilities-2026, licitacoes-alimentacao-2026, lei-14133-guia-fornecedores (in title or desc), melhores-plataformas-licitacao-2026-ranking, checklist-habilitacao-licitacao-2026, como-consultar-contratos-publicos-pncp
- "Como Funciona" pattern: inteligencia-artificial-licitacoes-como-funciona
- Titles over 60 chars: analise-viabilidade-editais-guia (71 chars)
- Descriptions not starting with action verb: pncp-guia-completo-empresas, lei-14133-guia-fornecedores, licitacoes-ti-software-2026, licitacoes-saude-2026, licitacoes-limpeza-facilities-2026, licitacoes-alimentacao-2026

## Measurement Plan

- **T0 (baseline):** 2026-04-30 — GSC snapshot inferred (scrape skipped)
- **T+14 (check):** 2026-05-14 — First impression/CTR check in GSC
- **T+30 (result):** 2026-05-30 — Full evaluation at `docs/seo/ctr-opt-001-results-2026-05-14.md`
- **Target:** CTR 3% (from baseline 1.3%) — 2.3× improvement
