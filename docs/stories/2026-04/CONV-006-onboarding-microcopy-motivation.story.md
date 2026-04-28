# CONV-006: Onboarding step copy + motivation microcopy

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster UX Writing/Yifrah, Saito + Cluster Growth/Bush)
**Prioridade:** P1 — signup→trial completion é gargalo #2
**Complexidade:** S (1 dia)
**Owner:** @dev + @ux-design-expert
**Tipo:** Frontend / Copy
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

`frontend/app/onboarding/components/OnboardingStep1.tsx:16-19` copy atual:

```
"Qual é o seu negócio?"
"Informe seu segmento para encontrarmos oportunidades relevantes"
```

**Falhas (Yifrah Microcopy):**
- "Oportunidades relevantes" é vago — não educa valor de CNAE
- Step não motiva completude (Yifrah: microcopy de motivação > microcopy de instrução)
- Step 3 (analyzing) opaco — risco de abandono durante load

**Princípio Bowling Alley (Wes Bush):** cada step é um obstáculo. Reduzir fricção via motivação clara + progresso visível.

---

## Decisão

1. Step 1 (CNAE): explicar **why** — "92% dos editais têm exigências por segmento"
2. Step 2 (UFs): callout de norma social — "Empresas B2G geralmente atuam em 3-5 estados"
3. Step 3 (objetivo): expandir help text com promessa quantificada — "+40% precisão"
4. Step "analyzing" (transição): progresso real visível ("3/27 estados analisados...")
5. Reforço de progresso entre steps

---

## Critérios de Aceite

### Step 1 — CNAE

- [ ] **AC1:** Copy nova `OnboardingStep1.tsx`:
  ```
  H: "Vamos mapear suas oportunidades em 2 minutos"
  Sub: "Seu CNAE é o filtro #1 — 92% dos editais têm exigências por segmento.
        Acertar aqui = ver só editais que sua empresa pode realmente vencer."
  ```

### Step 2 — UFs

- [ ] **AC2:** Callout norma social acima do seletor de UFs:
  ```
  "Empresas B2G geralmente atuam em 3-5 estados — pode ajustar a qualquer momento."
  ```
- [ ] **AC3:** Default 3 UFs pré-selecionadas baseado em CNPJ (se fornecido) ou geo-localização browser (fallback)

### Step 3 — Objetivo

- [ ] **AC4:** Help text expandido:
  ```
  "Quanto mais específico você for aqui, +40% de precisão nos matches.
  Ex: 'Uniformes escolares SP, ≥R$100k, foco escolas públicas'"
  ```
- [ ] **AC5:** Contador de chars (max 200) com microcopy motivacional:
  - 0-50 chars: "Adicione mais detalhes para melhor precisão"
  - 50-150 chars: "Bom! Suas análises ficarão mais afiadas"
  - 150-200 chars: "Excelente — IA terá contexto completo"

### Step "Analyzing" — Transição

- [ ] **AC6:** Estado "Analisando..." substituído por progresso real:
  ```
  "Analisando [X]/[27] estados — encontrei [N] oportunidades até agora..."
  ```
- [ ] **AC7:** ProgressBar visual com percentage real (não fake)
- [ ] **AC8:** Se TTV >10s, exibir "Estamos com volume alto — só mais alguns segundos"

### Reforço de Progresso

- [ ] **AC9:** Header onboarding mostra "Passo X de 3" + barra visual
- [ ] **AC10:** Microcopy entre steps (toast/sub-header):
  - Step 1→2: "Ótimo! Agora vamos definir região de atuação"
  - Step 2→3: "Quase lá — última pergunta"

### Verificação

- [ ] **AC11:** Tests `frontend/__tests__/onboarding/Step1.test.tsx` validam copy nova render
- [ ] **AC12:** E2E Playwright completa onboarding 3-step com novo copy sem erros
- [ ] **AC13:** Tracking event `onboarding_step_view` envia `step_number` + tempo gasto no step

---

## Arquivos Impactados

**Modificados:**
- `frontend/app/onboarding/components/OnboardingStep1.tsx` — copy nova
- `frontend/app/onboarding/components/OnboardingStep2.tsx` (ou similar para UFs) — callout + default
- `frontend/app/onboarding/components/OnboardingStep3.tsx` (ou similar para objetivo) — help text + char counter
- `frontend/app/onboarding/page.tsx` — header progresso + transição copy + analyzing real progress
- `frontend/__tests__/onboarding/Step1.test.tsx` (e equivalents) — testes copy
- `frontend/e2e-tests/onboarding-flow.spec.ts` (se existir) — E2E

**Backend (verificação):**
- `backend/routes/onboarding.py` — first-analysis dispatch deve emitir progress events para CONV-007

---

## Riscos

- **R1 (Médio):** Default UFs por geo browser pode ser inacurado (VPN, viagem). **Mitigação:** AC3 fallback com aviso "Detectamos que você está em [UF]. Correto?" + opção de ajustar.
- **R2 (Médio):** Progresso real (AC6) requer SSE ou polling do backend durante first-analysis. Memory: já existe SSE infra (`backend/progress.py`). **Mitigação:** reutilizar SSE existente, não criar novo.
- **R3 (Baixo):** Char counter dinâmico pode parecer "controlador". **Mitigação:** AC5 microcopy positiva, não negativa ("Bom!" > "Insuficiente").

---

## Dependências

- CONV-001 (instrumentação) Done — `onboarding_step_view`, `onboarding_complete` events
- Backend SSE progress (já existente em `backend/progress.py`)
- CONV-007 (TTV measurement) coordenado — exibir tempo real

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P1 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Yifrah motivation microcopy + Bush Bowling Alley. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO**. Copy exato em 3 steps + transições. AC6 progresso real reutiliza SSE existente (não duplica infra). Status Draft → Ready. |
