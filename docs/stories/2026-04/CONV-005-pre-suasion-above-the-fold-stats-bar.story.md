# CONV-005: Pre-Suasion above-the-fold com âncora estatística

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Psicologia/Cialdini Pre-Suasion + Cluster Brand/Howell)
**Prioridade:** P2
**Complexidade:** S (1 dia)
**Owner:** @dev + @ux-design-expert
**Tipo:** Frontend / Copy
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

Cialdini *Pre-Suasion* (Stanford GSB): atenção do visitor é vetor de persuasão — o frame mental setado nos primeiros 3 segundos influencia a decisão subsequente. SmartLic landing atual entra direto no hero sem pre-suade.

Inserir barra estatística acima do hero ancora autoridade + escala antes do CTA, complementando CONV-003 (hero rewrite).

**Princípio:** plantar números grandes verificáveis muda a percepção de "este é um SaaS qualquer" para "este é o player da categoria B2G".

---

## Decisão

1. Barra estatística top-of-page (acima do hero) com 3 números:
   - 1.500.000 editais indexados
   - 400 dias de histórico
   - 27 estados cobertos
2. Logos de fontes oficiais públicas (PNCP, Compras.gov, PCP) — autoridade visual
3. Números refletem dados reais via API ou static fallback semanal
4. Implementação não-intrusiva (max 60px altura, mobile responsive)

---

## Critérios de Aceite

### Implementação

- [ ] **AC1:** Componente `<PreSuasionStatsBar />` em `frontend/components/landing/PreSuasionStatsBar.tsx` com layout:
  ```
  [PNCP logo] [Compras.gov logo] [PCP logo] | 1.500.000 editais indexados • 400 dias de histórico • 27 estados
  ```
- [ ] **AC2:** Componente renderizado acima do `<HeroSection />` em `/` (homepage) e `/pricing` (não em logged-in pages)
- [ ] **AC3:** Números via API endpoint `GET /v1/stats/datalake` (já existir em `routes/stats_public.py`?) OU static fallback em `frontend/lib/stats/datalake-snapshot.ts` atualizado semanalmente via cron

### Performance + A11y

- [ ] **AC4:** Bar altura ≤60px desktop, ≤80px mobile
- [ ] **AC5:** Logos servidos como SVG inline (zero requests adicionais), aria-label descritivo
- [ ] **AC6:** Lighthouse score não degrada (verificar pré vs pós em `/`)
- [ ] **AC7:** WCAG AA contrast ≥4.5:1 nos números

### Verificação Numérica

- [ ] **AC8:** Endpoint `/v1/stats/datalake` retorna JSON `{bids_count, bids_oldest_age_days, ufs_covered}` baseado em queries reais ao DataLake
- [ ] **AC9:** Fallback estático atualizado semanalmente (cron `update_datalake_snapshot` em `backend/jobs/cron/`)
- [ ] **AC10:** Tooltip nos números: "Atualizado em [data]" para credibilidade

### Tracking

- [ ] **AC11:** Evento `presuasion_bar_view` (impression tracking) — Mixpanel
- [ ] **AC12:** Se barra é clicável (link para `/observatorio`?), tracking `presuasion_bar_click`

---

## Arquivos Impactados

**Novos:**
- `frontend/components/landing/PreSuasionStatsBar.tsx`
- `frontend/lib/stats/datalake-snapshot.ts` — static fallback
- `frontend/__tests__/components/PreSuasionStatsBar.test.tsx`
- `backend/routes/stats_public.py` — endpoint `/v1/stats/datalake` (se não existir)
- `backend/jobs/cron/datalake_stats_snapshot.py` — refresh semanal

**Modificados:**
- `frontend/app/page.tsx` — adicionar componente
- `frontend/app/pricing/page.tsx` (ou `/planos`) — adicionar componente
- `backend/jobs/cron/scheduler.py` — registrar cron snapshot

---

## Riscos

- **R1 (Médio):** Endpoint `/v1/stats/datalake` query DB pode ser lento se cache não implementado. **Mitigação:** Redis cache TTL 1h + AC9 fallback estático.
- **R2 (Baixo):** Logos PNCP/Compras.gov/PCP usados sem autorização explícita podem gerar conflito. **Mitigação:** verificar terms of use de cada (são órgãos públicos, branding via portal de transparência geralmente permitido para indicar fonte de dados).
- **R3 (Baixo):** Mobile layout cramped com 3 logos + 3 stats. **Mitigação:** AC1 layout responsivo, stack vertical em <768px.

---

## Dependências

- CONV-001 (instrumentação) Done — `presuasion_bar_view` event
- DataLake operacional (já é) — queries para stats
- CONV-003 (hero rewrite) — coordenação visual hero + bar

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P2 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Pre-Suasion (Cialdini). Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO**. Stats bar discreto + verificável. R2 logos terms of use vale double-check antes de produção. Status Draft → Ready. |
