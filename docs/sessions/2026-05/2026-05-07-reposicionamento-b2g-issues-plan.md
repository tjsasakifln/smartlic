# Reposicionamento SmartLic — SaaS → Infraestrutura B2G (Phase 0 fake-door)

**Data:** 2026-05-07
**Owner:** @sm — coordenação · /copymasters review (consenso 8/8 já aplicado) · @analyst legal
**Status:** PLAN-ONLY · aguarda GO humano para batch-create

## Reframe vs plano original (advisor + discriminadores empíricos)

| Sinal | Achado | Decisão |
|-------|--------|---------|
| Paying users | n=0 (7 profiles total) | Phase 0 fake-door antes de Stripe OTP |
| GSC top queries | CNPJs/razões sociais (entidades) | pSEO rankeia por entidade — preserve |
| GSC PNCP queries | ZERO | REPO-705 rename SEO-safe (manter P0) |
| Memory cap backlog | ≤20 Ready | 22 issues P0 (não 72) — defer P1/P2 spawn-on-demand |
| Memory PMF T0 | Intel Reports | Defer p/ Phase 1 (após validação demanda) |
| Advisor over-decomp | 8 issues p/ /consultoria-b2g | Consolidado em 3 issues |
| /copymasters | NÃO invocado no plano original | INVOCADO — copy locked v1 abaixo |

**Phase 0 hipótese a validar (14d gate):** ≥10 form-submits qualificados em /consultoria-b2g (com setor + telefone + CNPJ) → libera Phase 1 (Radar/Report/Intel reais + Stripe OTP).

**Phase 1 trigger se hipótese falsa:** revisar tese ou pivotar para Intel Reports T0 (DataLake monetization direto sem consultiva).

## Copy locked v1 — Conselho Copymasters consenso 8/8

### Hero homepage
- **Headline:** "Decisão comercial em licitação não nasce de PDF. Nasce de inteligência."
- **Subheadline:** "SmartLic lê o edital, mapeia o concorrente, calcula a chance real. Sua empresa decide go/no-go em minutos — não em três dias de leitura."
- **CTA primário:** "Testar plataforma" → `/signup?source=hero-primary`
- **CTA secundário:** "Solicitar diagnóstico B2G" → `/consultoria-b2g#diagnostico`

### 3-Tier block (homepage + footer)
- **SmartLic SaaS** (R$297-397/mês): "Você opera. A plataforma filtra editais, mapeia concorrentes e entrega análise por edital. Para times comerciais que já sabem o que fazem."
- **Radar B2G** (a partir R$1.500/mês): "Briefing diário com os editais que importam para sua empresa, concorrência mapeada e recomendação de disputa. Você acorda sabendo onde atuar."
- **Consultoria B2G** (sob consulta): "Núcleo externo de inteligência operando para sua empresa. Estratégia setorial, dossiê de concorrência, defesa em impugnação. Quando o jogo é grande demais para errar."

### Hero /consultoria-b2g
- **Headline:** "Um núcleo externo de inteligência B2G operando dentro da sua empresa."
- **Subheadline:** "Estratégia setorial, dossiê de concorrência, parecer de viabilidade e suporte em impugnação. Para empresas que tratam licitação como negócio, não como aposta."

### Disclaimer hero (não-afiliação)
"Criado por servidor público com mais de 10 anos em licitações. Plataforma independente, sem vínculo com órgãos governamentais."

### 6 CTAs padronizados
| CTA | Label final | Destino |
|-----|------------|---------|
| Testar SaaS | "Testar plataforma" | `/signup?source={origin}` |
| Diagnóstico | "Solicitar diagnóstico B2G" | `/consultoria-b2g#diagnostico` |
| Radar | "Receber radar da minha empresa" | `/consultoria-b2g?modalidade=radar#diagnostico` |
| Análise edital | "Solicitar análise de edital" | `/consultoria-b2g?modalidade=report#diagnostico` |
| Mapear setor | "Mapear meu setor" | `/consultoria-b2g?modalidade=intel#diagnostico` |
| Falar especialista | "Falar com especialista B2G" | `/consultoria-b2g#diagnostico` |

**Insight Phase 0:** TODOS os CTAs premium pousam em `/consultoria-b2g` com query-param `?modalidade=` capturado pelo form. UMA landing valida demanda das três modalidades simultaneamente. Stripe OTP, /radar-b2g, /report-b2g, /intel-b2g só após gate 14d.

## Convenções de issue

### Labels GitHub a criar (REPO-001)
```
reposicionamento-b2g · phase-0
epic:1-homepage · epic:2-consultoria · epic:6-pseo · epic:7-cta
epic:9-nav · epic:10-tracking · epic:11-copy · epic:12-legal
priority:p0 · priority:p1 · priority:p2
area:frontend · area:backend · area:copy · area:legal · area:tracking
```

### Template AC issue
```markdown
## Objetivo
{1 linha}

## Contexto
Phase 0 reposicionamento B2G. Plano: docs/sessions/2026-05/2026-05-07-reposicionamento-b2g-issues-plan.md

## Escopo
- {item}

## Fora de escopo
- {item}

## Critérios de aceite
- [ ] AC1 testável
- [ ] AC2 testável
- [ ] AC3 — preserva comportamento existente

## Arquivos prováveis
- `path:line`

## Plano de teste
1. Manual: ...
2. Automated: pytest/jest comando

## Riscos
- {risco + mitigação}

## Dependências
- Bloqueado por: #N
```

---

# Issues Phase 0 (22 P0)

## REPO-001 · Housekeeping: criar labels GitHub · P0

**Escopo:** criar labels listados acima via `gh label create`. PR único de housekeeping.

**ACs:**
- [ ] 17 labels existem no repo
- [ ] PR README atualizado em `docs/contributing/labels.md` (se já existir; senão skip)

**Files:** N/A (gh CLI)

---

## REPO-002 · Doc copywriting guidelines `docs/copywriting-guidelines.md` · P0

**Escopo:**
- Documentar tese, tom, lexico (decisão > automação · IA-meio > IA-produto)
- Lista palavras proibidas com alternativas
- Tom B2B/B2G brasileiro
- Tabela 27 UFs com preposição correta (na BA, no RS, no PR, no DF, em SP, em MG…)
- Anchors: copymasters consenso 8/8 (link a este doc)

**Files:** novo `docs/copywriting-guidelines.md`

**ACs:**
- [ ] ≥ 10 exemplos before/after
- [ ] Tabela 27 UFs com preposição
- [ ] Seção "promessas que NÃO podemos fazer"

**Risco:** copy locked v1 pode evoluir; manter doc versionado

---

## REPO-003 · Audit legal disclaimers · P0 — bloqueia REPO-005, 015, 020, 021

**Escopo:**
- Inventário literal: footer, /termos, /privacidade, hero, FAQ
- Identificar promessas implícitas/explícitas de vitória/garantia
- Output: `docs/legal-audit-2026-05.md` com tabela ocorrência | risco | recomendação
- Aprovação @analyst antes de prosseguir

**ACs:**
- [ ] Audit doc commitado
- [ ] Lista de mudanças mapeadas em outras issues (links)

**Risco:** descoberta de gap regulatório → bloqueador adicional

---

## REPO-004 · Backend: estender `lead_capture` source enum + utm tracking · P0 — bloqueia REPO-009, 014

**Escopo:**
- `backend/routes/lead_capture.py` `LeadCaptureRequest`: adicionar sources `consultoria|radar|report|intel|diagnostico` no enum
- Adicionar campos opcionais: `utm_source`, `utm_campaign`, `referer_path`, `nome`, `empresa`, `cnpj`, `telefone`, `modalidade_interesse` (radar|report|intel|nao_sei), `mensagem` (max 500)
- Migration `supabase/migrations/{ts}_extend_lead_capture.sql` + `.down.sql` (CHECK constraint + colunas)
- Tests: novos sources aceitos, source inválido → 422, schema migration aplicado

**Files:**
- `backend/routes/lead_capture.py`
- `backend/tests/test_lead_capture.py`
- `supabase/migrations/{ts}_extend_lead_capture.sql` + `.down.sql`

**ACs:**
- [ ] Pydantic accepts: calculadora|cnpj|alertas|consultoria|radar|report|intel|diagnostico
- [ ] Backward compat: 3 sources antigos continuam funcionando
- [ ] Migration aplicada local + Supabase prod (`npx supabase db push`)
- [ ] Tests cobrem 8 sources × 2 caminhos (com/sem opcionais)

---

## REPO-005 · CNPJ inconsistente Footer vs Privacy → fontes verdade · P0

**Escopo:**
- Footer atual: 56.688.745/0001-00
- Privacy atual: 56.528.581/0001-00
- Confirmar CNPJ correto via Receita Federal/SEFAZ (CONFENGE Avaliações e Inteligência Artificial LTDA)
- Atualizar arquivo errado + criar `docs/legal/empresa.md` com fonte verdade

**Files:** `frontend/app/components/Footer.tsx`, `frontend/app/privacidade/page.tsx`, novo `docs/legal/empresa.md`

**ACs:**
- [ ] Único CNPJ em todo codebase (grep `\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}` retorna 1 valor distinto)
- [ ] Doc fonte verdade commitado

**Deps:** REPO-003 (audit)

---

## REPO-006 · Hero homepage: nova headline + sub + CTAs duplos · P0

**Escopo:**
- Atualizar `frontend/lib/copy/valueProps.ts` com copy locked (consenso copymasters 8/8)
- `HeroSection.tsx`: 2 CTAs (primary + secondary)
- Snapshot tests atualizados

**Files:**
- `frontend/lib/copy/valueProps.ts`
- `frontend/app/components/landing/HeroSection.tsx`
- `frontend/__tests__/landing/HeroSection.test.tsx`

**ACs:**
- [ ] Headline literal: "Decisão comercial em licitação não nasce de PDF. Nasce de inteligência."
- [ ] Sub literal: "SmartLic lê o edital, mapeia o concorrente, calcula a chance real. Sua empresa decide go/no-go em minutos — não em três dias de leitura."
- [ ] 2 CTAs visíveis ≥1024px e ≥375px
- [ ] data-testid `hero-cta-primary` + `hero-cta-secondary`
- [ ] Snapshot test atualizado

**Deps:** REPO-002 (guidelines link)

---

## REPO-007 · Disclaimer hero (não-afiliação gov) · P0

**Escopo:**
- Linha curta abaixo do hero: "Criado por servidor público com mais de 10 anos em licitações. Plataforma independente, sem vínculo com órgãos governamentais."
- Estilo discreto (`text-sm text-zinc-400`), abaixo dos CTAs

**Files:** `HeroSection.tsx`, `valueProps.ts`

**ACs:**
- [ ] Texto literal renderizado abaixo CTAs
- [ ] Footer disclaimer existente preservado
- [ ] Texto aprovado em REPO-003

**Deps:** REPO-003, REPO-006

---

## REPO-008 · Bloco "3 níveis SaaS · Radar · Consultoria" · P0

**Escopo:**
- Novo `frontend/app/components/landing/ThreeTiersSection.tsx`
- 3 cards com value props + pricing (copy locked)
- CTAs por card: "Testar grátis" / "Receber radar da minha empresa" / "Falar com especialista B2G"
- Inserir entre `OpportunityCost` e `BeforeAfter` em `page.tsx`

**Files:** novo `ThreeTiersSection.tsx`, edit `page.tsx`

**ACs:**
- [ ] 3 cards com pricing visível
- [ ] CTAs com `data-cta-tier={saas|radar|consultoria}`
- [ ] Responsivo (1 col mobile, 3 col desktop)
- [ ] Storybook story (se padrão existente em outros components)

**Deps:** REPO-002, REPO-006

---

## REPO-009 · `/consultoria-b2g` página completa (skeleton+hero+pacotes+FAQ) · P0

**Escopo (CONSOLIDADO - advisor #5):** uma issue, uma PR, uma landing page completa. Sub-secções como tarefas internas:

- Rota `frontend/app/consultoria-b2g/page.tsx` (Server Component, SSG)
- `generateMetadata` title/desc/OG/canonical
- Hero (copy locked)
- Bloco "Problemas que resolvemos" (4-6 problemas mapeados a Radar/Report/Intel)
- Bloco "3 modalidades" (Radar Operacional R$1.500+ · Inteligência Estratégica R$5.000+ · Operação Premium sob consulta)
- FAQ 6-8 Q/A com JSON-LD FAQPage
- Bloco "Tecnologia proprietária" (link `/buscar` preview)
- Sitemap atualizado (sub-sitemap 0)

**Files:**
- novo `frontend/app/consultoria-b2g/page.tsx`
- novo `frontend/app/consultoria-b2g/components/ConsultoriaForm.tsx` (extraído como component reusável; ver REPO-014)
- edit `frontend/app/sitemap.ts`

**ACs:**
- [ ] Rota responde 200 em `/consultoria-b2g`
- [ ] OG image dinâmica
- [ ] Sitemap inclui rota
- [ ] Indexável (sem noindex)
- [ ] FAQ ≥ 6 itens com JSON-LD
- [ ] Performance: LCP < 2.5s no Vercel/Railway preview

**Fora de escopo:**
- Stripe OTP (Phase 1)
- Backend pipeline geração (Phase 1)
- Páginas separadas /radar-b2g, /report-b2g, /intel-b2g

**Deps:** REPO-002, REPO-004, REPO-014

---

## REPO-010 · LandingNavbar reorganização — dropdown Soluções · P0

**Escopo:**
- LandingNavbar dropdown "Soluções": SaaS · Radar · Report · Intel (todos pousam em `/consultoria-b2g?modalidade=X` Phase 0)
- Item top-level "Consultoria" → `/consultoria-b2g`
- Mobile: drawer com mesma hierarquia
- CTA "Testar plataforma" mantido em destaque

**Files:** `frontend/app/components/landing/LandingNavbar.tsx`

**ACs:**
- [ ] Dropdown desktop com 4 itens
- [ ] Mobile drawer expand/collapse
- [ ] CTA primário visível desktop+mobile

**Deps:** REPO-009

---

## REPO-011 · Footer: coluna "Soluções" + disclaimer atualizado · P0

**Escopo:**
- Footer.tsx — adicionar coluna "Soluções": SaaS · Radar B2G · Consultoria B2G · Exemplos (link Phase 1)
- Manter disclaimer existente "SmartLic não é afiliado ao governo"

**Files:** `frontend/app/components/Footer.tsx`

**ACs:**
- [ ] Coluna "Soluções" com 4 links (3 reais + 1 placeholder Phase 1)
- [ ] Disclaimer preservado
- [ ] Mobile: accordion

**Deps:** REPO-009

---

## REPO-012 · pSEO: componente "Vale a pena disputar?" reusável · P0

**Escopo:**
- Novo `frontend/components/ViabilityVerdict.tsx`
- Props: `score`, `label?` (PARTICIPAR/AVALIAR/NÃO RECOMENDADO), `reasons?` (string[]), `disclaimer` (always rendered)
- Visual: badge colorido (green/yellow/red) + 1-line rationale + disclaimer "Recomendação algorítmica. Não substitui análise jurídica/técnica final."
- Storybook story

**Files:** novo `frontend/components/ViabilityVerdict.tsx`, novo `*.stories.tsx`

**ACs:**
- [ ] Component aceita 3 níveis (PARTICIPAR/AVALIAR/NÃO RECOMENDADO)
- [ ] Disclaimer sempre presente
- [ ] Storybook 3 estados

**Deps:** REPO-003

---

## REPO-013 · Plug REPO-012 em `/cnpj/[cnpj]` + `/licitacoes/[setor]` · P1

**Escopo:**
- Em `/cnpj/[cnpj]`: derivar score do `perfil.score` existente; mapear `<7=AVALIAR <4=NÃO RECOMENDADO ≥7=PARTICIPAR`
- Em `/licitacoes/[setor]`: derivar de `stats.competitividade`
- Plug abaixo do hero, antes do conteúdo principal

**Files:** edit `frontend/app/cnpj/[cnpj]/page.tsx`, edit `frontend/app/licitacoes/[setor]/page.tsx`

**ACs:**
- [ ] Component renderiza condicionalmente (só se score disponível)
- [ ] Não quebra páginas com dados parciais
- [ ] Snapshot/integration tests cobrem 3 níveis

**Deps:** REPO-012

---

## REPO-014 · Componente `<DiagnosticForm />` standalone · P0

**Escopo:**
- Reusable form em `frontend/components/forms/DiagnosticForm.tsx`
- Props: `defaultModalidade?`, `source` (mandatório p/ tracking)
- Campos: nome · email · empresa · CNPJ (opt) · setor (select) · modalidade_interesse (select: Radar/Report/Intel/Não sei) · mensagem (max 500)
- Validação zod (extender `lib/schemas/forms.ts`)
- Submit POST `/v1/lead-capture` com `source` + utm_params + telefone
- Success state inline + Mixpanel event `consultoria_form_submitted`
- Error state inline + retry

**Files:**
- novo `frontend/components/forms/DiagnosticForm.tsx`
- edit `frontend/lib/schemas/forms.ts`
- novo `*.stories.tsx`
- novo `frontend/__tests__/forms/DiagnosticForm.test.tsx`

**ACs:**
- [ ] Form valida client-side (zod) + server-side (Pydantic)
- [ ] Submit success → toast/section + analytics event
- [ ] Submit error → mensagem inline + retry
- [ ] Lead salvo em `leads` table com source + modalidade

**Deps:** REPO-004

---

## REPO-015 · pSEO: CTA contextual em `/cnpj`, `/orgaos`, `/licitacoes`, `/municipios` · P1

**Escopo:**
- Em cada template pSEO listado: adicionar CTA contextual abaixo do conteúdo principal:
  - `/cnpj/[cnpj]`: "Mapear meu setor" → `/consultoria-b2g?modalidade=intel`
  - `/orgaos/[slug]`: "Solicitar análise de edital" → `/consultoria-b2g?modalidade=report`
  - `/licitacoes/[setor]`: "Receber radar da minha empresa" → `/consultoria-b2g?modalidade=radar`
  - `/municipios/[slug]`: "Solicitar diagnóstico B2G" → `/consultoria-b2g#diagnostico`
- Passar setor/uf/cnpj como query-param p/ pre-preencher form
- Tracking: `cta_click` com source pSEO origin

**Files:** edits 4 templates pSEO

**ACs:**
- [ ] CTA presente em 4 templates
- [ ] Query-params propagados ao form
- [ ] Não compete visualmente com CTA SaaS existente (InlineTrialCTA mantido em paralelo)

**Deps:** REPO-009

---

## REPO-016 · pSEO: title/meta refresh GSC-driven · P1

**Escopo:**
- Ler GSC export `C:\Users\tj_sa\Downloads\https___smartlic.tech_-Performance-on-Search-2026-05-06\Páginas.csv` + `Consultas.csv`
- Identificar páginas com impressões >10 e CTR <2% → low-CTR titles
- Reescrever title/description seguindo modelo intenção:
  - edital: "Esta oportunidade vale sua atenção?"
  - órgão: "Como este órgão compra e quais oportunidades publica?"
  - setor: "Onde estão as melhores oportunidades para empresas deste setor?"
  - município: "Quais licitações estão abertas {na/no} {UF}?"
- Aplicar correção UF preposição (REPO-002 tabela)

**Files:** edits `generateMetadata` em ≥4 páginas pSEO

**ACs:**
- [ ] Audit doc com top-10 páginas low-CTR
- [ ] ≥10 títulos atualizados
- [ ] Preposição UF correta em 27 UFs
- [ ] noindex preservado para pages com <5 bids

**Deps:** REPO-002 (tabela UFs)

---

## REPO-017 · "PNCP → nossas fontes" rename UI/copy · P0

**Escopo:**
- Grep + replace em `frontend/app/**/*.tsx`, `frontend/lib/copy/**`, `frontend/components/**`, `backend/routes/*_publicos.py` (apenas templates SEO)
- "PNCP" → "nossas fontes" / "fontes oficiais consolidadas"
- WHITELIST (preservar): backend `pncp_*` tables/code, `pncp_canary.py`, `PNCP_API_BASE_URL` env, `/termos` técnico explanation, comentários técnicos, docs internos
- GSC-validated SEO-safe (zero queries com "PNCP")

**Files:** scan multi-file. Whitelist documentado em PR description.

**ACs:**
- [ ] Grep `\bPNCP\b` em UI (não-whitelist) retorna 0
- [ ] Backend code 100% intacto
- [ ] Whitelist documentada
- [ ] Build + tests passam

**Risco:** SEO regression marginal. Mitigação: GSC monitor 14d pós-deploy

---

## REPO-018 · Tracking: eventos padronizados Mixpanel · P0

**Escopo:**
- Novo `frontend/lib/analytics-events.ts` com 4 eventos tipados:
  - `cta_click` (label, source, destination, cta_type: 'self-service'|'consultive')
  - `form_started` (form_name, source)
  - `form_submitted` (form_name, source, modalidade?)
  - `lead_captured` (source, modalidade?)
- Refactor: `useAnalytics()` hook expõe funções tipadas
- Plug em REPO-006 (hero CTAs), REPO-008 (3-tier), REPO-010 (navbar), REPO-014 (form), REPO-015 (pSEO CTAs)

**Files:** novo `frontend/lib/analytics-events.ts`, edit `frontend/hooks/useAnalytics.ts`

**ACs:**
- [ ] 4 eventos tipados em TypeScript
- [ ] Doc inline com props mandatórios
- [ ] Plug em ≥5 entry points

**Deps:** REPO-006, REPO-008, REPO-010, REPO-014

---

## REPO-019 · Mixpanel funnel "modalidade interesse" · P0

**Escopo:**
- Super-property `pseo_origin` quando lead vem de pSEO (REPO-015)
- Funnel Mixpanel doc: page_load → cta_click → form_started → form_submitted → lead_captured
- Doc operacional: how to query funnel split por modalidade (radar/report/intel)
- Phase 0 gate metric: ≥10 form_submitted distintos com modalidade ≠ "nao_sei" em 14d

**Files:** novo `docs/analytics-phase0-funnel.md`

**ACs:**
- [ ] Funnel definido em Mixpanel UI (manual setup, doc passo a passo)
- [ ] Super-property aparece em ≥1 evento via prod test
- [ ] Doc com query/dashboard URL

**Deps:** REPO-018

---

## REPO-020 · Disclaimer "recomendação algorítmica" em pSEO + Verdict · P0

**Escopo:**
- `frontend/components/legal/AdvisoryDisclaimer.tsx` (novo)
- Texto literal aprovado REPO-003: "Recomendação algorítmica baseada em dados públicos. Não substitui análise jurídica, técnica ou comercial final."
- Plug em: `<ViabilityVerdict />` (REPO-012), `/alertas-publicos`, `/cnpj` (perfil score), futuros Report/Intel pages

**Files:** novo `AdvisoryDisclaimer.tsx`, edits 3+ páginas

**ACs:**
- [ ] Disclaimer presente em ≥4 surfaces
- [ ] Texto literal aprovado REPO-003
- [ ] Estilo discreto (não overload visual)

**Deps:** REPO-003, REPO-012

---

## REPO-021 · Remover copy sugerindo "garantia de ganho" · P0

**Escopo:**
- Aplicar mudanças mapeadas em REPO-003 audit
- Grep terms: "garanta", "vença", "ganhe certeza", "automaticamente vencerá", "sucesso garantido"
- Substituir conforme guidelines REPO-002

**Files:** scan multi-file conforme audit

**ACs:**
- [ ] Zero ocorrências de termos proibidos em UI
- [ ] Guidelines aplicado em copy refinado

**Deps:** REPO-003

---

## REPO-022 · Phase 0 gate decision doc + 14d trigger · P1

**Escopo:**
- Doc `docs/sessions/2026-05/2026-05-21-phase0-gate-decision.md` (placeholder, populado em 14d pós-deploy)
- Critérios de gate (lock 2026-05-07, avaliação 2026-05-21):
  - **PASS:** ≥10 form_submitted distintos com modalidade ≠ "nao_sei" + ≥1 lead com CNPJ válido + setor preenchido
  - **FAIL:** <10 form_submitted ou apenas modalidade "nao_sei" → re-tese ou pivot Intel Reports T0
- Após gate PASS: spawn issues Phase 1 (Radar/Report/Intel pages reais + Stripe OTP R$497/R$997)

**Files:** novo doc placeholder com schema YAML

**ACs:**
- [ ] Doc commitado com critérios explícitos
- [ ] Cron lembrete @14d (calendar/reminder)

**Deps:** REPO-019 (funnel), REPO-009 (form deployed)

---

# Sumário & ordem

**Total: 22 issues P0** (cabe no cap ≤20 com 2 buffer)

P1 spawn-on-demand: REPO-013 (plug verdict), REPO-015 (pSEO CTAs), REPO-016 (GSC refresh), REPO-022 (gate doc).

## Dependency graph (P0 críticos)

```
REPO-001 (labels)
REPO-002 (guidelines doc) ─┬─→ REPO-006, 008, 011, 016
REPO-003 (legal audit)    ─┬─→ REPO-005, 007, 020, 021
REPO-004 (lead-capture)   ─┬─→ REPO-009, 014
REPO-006 (hero) ────────────→ REPO-007, 008, 018
REPO-009 (consultoria) ─────→ REPO-010, 011, 015
REPO-012 (Verdict) ──────────→ REPO-013, 020
REPO-014 (form) ─────────────→ REPO-018
REPO-018 (events) ───────────→ REPO-019, 022
```

## Ordem ótima de execução (1 dev FTE)

```
Dia 1 — Foundation (parallel-safe)
  REPO-001 (labels)
  REPO-002 (guidelines)
  REPO-003 (legal audit)
  REPO-004 (lead-capture extend) — backend

Dia 2 — Foundations validate
  REPO-005 (CNPJ fix)
  REPO-014 (DiagnosticForm component)
  REPO-012 (ViabilityVerdict component)

Dia 3-4 — Pages
  REPO-006 (hero homepage)
  REPO-007 (disclaimer hero)
  REPO-008 (3-tier block)
  REPO-009 (/consultoria-b2g)

Dia 5 — Wire-up
  REPO-010 (navbar)
  REPO-011 (footer)
  REPO-017 (PNCP rename)
  REPO-020 (advisory disclaimer)
  REPO-021 (remove garantia copy)

Dia 6 — Tracking + ship
  REPO-018 (events typed)
  REPO-019 (funnel setup)
  REPO-022 (gate doc placeholder)

Dia 7 — Buffer + smoke
  REPO-013 (plug Verdict pSEO) [P1, opportunistic]
  REPO-015 (CTA contextual pSEO) [P1, opportunistic]
  REPO-016 (GSC refresh) [P1, opportunistic]

Deploy → 14d soak → REPO-022 gate decision
```

**Capacity:** ~7-8 dias 1 FTE; 2 devs paralelos ~4-5 dias.

## MVP Phase 0 ready-to-ship

Issues P0 que precisam estar em main antes do gate começar contando:

```
Foundation: 001, 002, 003, 004
Critical legal: 005, 020, 021
Pages: 006, 007, 008, 009
Wire-up: 010, 011, 017
Tracking: 018, 019, 022
Components: 012, 014
```

22 issues. Tudo P0.

## Phase 1 spawn-on-demand (após gate PASS)

NÃO criar agora. Issues abaixo nascem se gate PASS confirmado:

- /radar-b2g page real (3 issues)
- /report-b2g page + Stripe OTP R$497 (4 issues)
- /intel-b2g page + Stripe OTP R$997 (4 issues)
- /exemplos/* demo pages (3 issues)
- Stripe products setup (1 issue)
- Backend pipelines geração (4 issues)

~19 issues Phase 1 quando triggered. Total roadmap: 22 + 19 = 41 issues (vs 72 originais).

## Checklist final de release Phase 0

- [ ] 22 P0 mergeadas em main
- [ ] `npm run build` passa CI
- [ ] Deploy Railway prod smoke test
- [ ] GSC: monitorar CTR pSEO 14d (linha de base hoje)
- [ ] Mixpanel: 4 eventos tipados chegando (cta_click, form_started, form_submitted, lead_captured)
- [ ] Funnel Phase 0 setup em Mixpanel UI
- [ ] Lead capture: 8 sources visíveis em tabela `leads`
- [ ] Sentry: zero novos erros 24h pós-deploy
- [ ] Sitemap: `/consultoria-b2g` em sitemap-0.xml
- [ ] Legal review confirmado (@analyst aprovou disclaimers)
- [ ] Copy guidelines aplicado em ≥80% das páginas reposicionadas
- [ ] Cron 14d lembrete agendado para REPO-022 gate decision
- [ ] CNPJ único no codebase (grep verifica)

## Riscos macro

1. **SEO impact REPO-017** (PNCP rename) — GSC zero queries reduz risco a marginal. Mitigação: 14d monitor + revert se queda > 30%.
2. **Phase 0 fail (n<10 leads)** — gate vira pivot trigger. Aceitável (validação > eng theater).
3. **Copy locked v1 evoluir** — copymasters consenso 8/8 mas pode mudar com dados. Doc REPO-002 versionado.
4. **Dependency stack-up** — REPO-003 (legal audit) bloqueia 4 issues. Mitigação: agendar @analyst dia 1.
5. **Cap backlog ≤20** — 22 issues estoura por 2. Aceitável dado todos P0 + 4 P1 spawn-on-demand.

---

## Próximos passos (após GO humano)

1. Revisar este doc + ajustar se necessário
2. /copymasters opcional re-review p/ /consultoria-b2g hero específico (REPO-009)
3. /conselho opcional review técnico (REPO-004 migration + REPO-018 events schema)
4. Batch-create 22 issues via script `gh issue create` (lotes de 5)
5. Aplicar labels REPO-001 antes de batch
6. Atribuir milestones P0 (todas no mesmo)
7. Iniciar Dia 1 foundation work
