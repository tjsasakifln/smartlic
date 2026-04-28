# CONV-004: Friction reduction signup form — Google OAuth + ≤4 campos + CTA reescrito

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Psicologia/Fogg + Cluster Growth/Bush, Shah)
**Prioridade:** P1 — visitor→signup é gargalo #1
**Complexidade:** M (1-2 dias)
**Owner:** @dev + @ux-design-expert
**Tipo:** Frontend / Auth
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

`frontend/app/signup/components/SignupForm.tsx:374` CTA atual = "Criar conta" (genérico, zero remoção de fricção). Trust box em `:371-378` lista features, não outcomes ordenados por fricção removida.

**Aplicação Fogg B=MAP** (Behavior = Motivation × Ability × Prompt):
- **Prompt:** OK (CTA visível)
- **Motivação:** Fraca (CONV-003 corrige no hero)
- **Ability:** Não otimizada — sem Google OAuth, formulário não enxuto

**Lift documentado:**
- Eleken case study: 12 → 4 campos = 4.2% → 9.1% completion (+117%)
- Custify: Google OAuth = +20-35% signup rate
- Combined effect: +20-40% signup completion

---

## Decisão

1. Auditar campos atuais do signup form
2. Reduzir para ≤4 campos: email + senha + nome + CNPJ (CNPJ optional)
3. Adicionar Google OAuth via Supabase Auth nativo (provider já suportado)
4. Reescrever CTA: "Criar conta" → "Começar trial grátis (14 dias, sem cartão)"
5. Reordenar trust box: Sem cartão → 14 dias → Cancelar 2 cliques (ordem de fricção removida descendente)
6. Mover CNPJ para `/onboarding` step opcional (memory: anti-pattern Brasil — pedir CNPJ no signup mata conversão)

---

## Critérios de Aceite

### Auditoria + Redução de Campos

- [ ] **AC1:** Documentar campos atuais em `docs/experiments/conv-004-signup-baseline.md` (count, ordem, validação)
- [ ] **AC2:** Form reduzido para ≤4 campos: `email`, `password`, `nome`, `cnpj?` (optional)
- [ ] **AC3:** CNPJ se ausente no signup é solicitado em `/onboarding` step adicional OU no primeiro acesso a feature que precisa (lazy collection)
- [ ] **AC4:** Validação inline mantida (email format, password strength, nome ≥2 chars)

### Google OAuth

- [ ] **AC5:** Supabase Auth Google provider habilitado em produção (verificar `supabase auth providers list` ou dashboard)
- [ ] **AC6:** Botão "Continuar com Google" acima do form (above-form pattern — mais visível)
- [ ] **AC7:** Fluxo OAuth retorna user com email + nome do Google (popula automaticamente); CNPJ obtido em `/onboarding`
- [ ] **AC8:** OAuth callback (`/auth/callback`) tracking event `signup_complete` com `auth_method: 'google'` vs `'email'`

### CTA + Trust Box

- [ ] **AC9:** CTA primário texto: `"Começar trial grátis (14 dias, sem cartão)"`
- [ ] **AC10:** Trust box reordenado:
  ```
  ✓ Sem cartão de crédito
  ✓ 14 dias completos
  ✓ Cancelar em 2 cliques
  ```
- [ ] **AC11:** Subheadline reescrita: atual "Veja quais licitações valem a pena para sua empresa — em 2 minutos" → nova "Encontre 10+ editais com 80%+ compatibilidade — em 2 min" (specificity)

### A/B Test

- [ ] **AC12:** Variant A (atual) preservada via feature flag `signup_variant: A | B`
- [ ] **AC13:** Variant B = AC2 + AC5 + AC9 + AC10 + AC11 combinados (não testar isolado — friction reduction é efeito sistêmico)
- [ ] **AC14:** Test runs ≥14d OU n≥500 signup_view events (whichever later)
- [ ] **AC15:** Métrica primária: signup_view → signup_complete CVR; secundária: TTV

### Verificação

- [ ] **AC16:** Form mantém WCAG AA (labels, error states, keyboard nav)
- [ ] **AC17:** Tests `frontend/__tests__/signup/SignupForm.test.tsx` cobrem: ≤4 campos render, OAuth button click, CTA copy, trust box ordering
- [ ] **AC18:** E2E Playwright: fluxo Google OAuth signup → onboarding (CNPJ collection) → buscar

---

## Arquivos Impactados

**Modificados:**
- `frontend/app/signup/page.tsx` — subheadline + estrutura
- `frontend/app/signup/components/SignupForm.tsx` — campos + CTA + OAuth button + trust box
- `frontend/app/auth/callback/page.tsx` — handle Google OAuth callback + tracking
- `frontend/app/onboarding/page.tsx` — adicionar step CNPJ se ausente do signup
- `frontend/lib/feature-flags/signup-variant.ts` (novo) — A/B toggle
- `frontend/__tests__/signup/SignupForm.test.tsx` — testes atualizados

**Novos:**
- `docs/experiments/conv-004-signup-baseline.md`
- `docs/experiments/conv-004-signup-results.md` (ao final do A/B test)

**Backend (verificação):**
- `backend/auth.py` — confirmar suporte a OAuth provider
- `backend/routes/onboarding.py` — adicionar step CNPJ collection se ausente

---

## Riscos

- **R1 (Alto):** OAuth Google requer config Supabase + Google Cloud Console. Setup pode bloquear. **Mitigação:** @devops valida config produção antes de merge; rollback via feature flag.
- **R2 (Médio):** Mover CNPJ para onboarding cria step adicional → pode aumentar abandono onboarding. **Mitigação:** AC3 lazy collection (só quando feature precisa), não step obrigatório.
- **R3 (Médio):** "Trial grátis 14 dias sem cartão" promessa precisa ser cumprida. Verificar `backend/services/billing.py` permite trial sem payment method. **Mitigação:** smoke test antes de deploy.
- **R4 (Baixo):** Email duplicado — usuário existente que tenta OAuth com mesmo email do account email/senha. **Mitigação:** Supabase Auth resolve via "link account" flow nativo.

---

## Dependências

- CONV-001 (instrumentação) Done — eventos `signup_view`, `signup_complete` com `auth_method` property
- Supabase Google OAuth provider configurado em produção (@devops verifica)
- Memory `reference_admin_bypass_paywall`: testar com user normal, não admin

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P1 do EPIC-CONV-FUNNEL-2026-Q2. Lift esperado +20-40% (Eleken/Custify). Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO**. 18 ACs cobrem auditoria + redução + OAuth + CTA + A/B. R1 OAuth setup é dependência operacional (@devops valida config). Status Draft → Ready. |
