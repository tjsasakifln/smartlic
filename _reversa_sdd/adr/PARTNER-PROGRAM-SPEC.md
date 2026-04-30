# ADR-PARTNER-PROGRAM-SPEC: Programa de Parceiros SmartLic

## Status

Accepted — 2026-04-29

Owners: @analyst (Alex) — spec authoring; @pm (Morgan) — epic placement; @architect (Aria) — implementation gates.

## Context

SmartLic está em estágio pre-revenue beta com n=2 signups (memory `reference_smartlic_baseline_2026_04_24`). Aquisição orgânica via SEO programmatic (10k+ pages ISR) é o vetor primário, mas o funil trial→paid ainda não está calibrado (memory `feedback_n2_below_noise_eng_theater`).

Um programa de parceiros (afiliados) é canal complementar de aquisição com CAC marginal baixo: pagamento só sobre receita realizada (não MQL/SQL). O backend já possui infraestrutura parcial:

- Tabelas `partners` + `partner_referrals` em `supabase/migrations/20260301200000_create_partners.sql`
- Endpoints administrativos em `backend/routes/partners.py`
- Faltam: spec funcional, política de comissão, regras de atribuição, fluxo de payout, controles antifraude

Em 2026-04-29, durante batch L-7 de AskUserQuestion, o stakeholder (founder) resolveu 5 dimensões funcionais que estavam em aberto desde a criação da story `GAP-PARTNER-001` (review-report.md Gap-3). Este ADR consolida essas decisões para destravar a próxima fase (escrita de spec funcional + epic placement em Sprint 3+).

**Memory de origem:** `project_partner_program_decisions_2026_04_29`

## Decision

### 1. Comissão

- **Taxa:** 20% lifetime sobre receita líquida do referenciado.
- **Receita líquida** = MRR efetivamente cobrado pelo Stripe, líquido de:
  - Trials (zero comissão durante os 14 dias gratuitos)
  - Reembolsos / chargebacks (estornados do saldo do parceiro no ciclo seguinte)
  - Impostos retidos pelo Stripe ou pelo SmartLic (PIS/COFINS, IRRF — ver §6 Compliance)
- **Lifetime** = comissão se mantém enquanto o referenciado for cliente ativo (assinatura paga). Cancelamento do referenciado encerra a comissão prospectivamente; comissões já creditadas são preservadas.
- **Plano único de comissão** nesta primeira fase. Tier-based (silver/gold/platinum) é deferido para v2 condicionado a n≥30 paid users (ver `feedback_n2_below_noise_eng_theater`).

### 2. Pagamento (Payout)

- **Método:** Pix (chave única do parceiro — CPF, CNPJ, e-mail ou telefone, à escolha).
- **Cadência:** mensal, **dia 5** de cada mês, referente à receita realizada no mês anterior (M-1).
- **Valor mínimo:** R$ 50,00 por payout. Saldo abaixo do mínimo acumula para o ciclo seguinte sem expirar (rollover indefinido enquanto a conta do parceiro estiver ativa).
- **Janela de hold:** 14 dias após cobrança (alinhado a janela típica de chargeback Stripe). Comissão de uma fatura paga em 20/abr só entra no payout dia 5/jun (não 5/mai).
- **Operação inicial:** manual (admin gera lote de Pix mensal, conciliando com extrato `partner_payouts`). Automação via Pix API (gateway) é gate condicionado a >50 parceiros ativos.
- **Reconciliação:** registro em `partner_payouts` com status `pending` → `paid` → (`failed` se Pix bouncar; nesse caso volta a `pending` no ciclo seguinte com flag de investigação).

### 3. Atribuição

- **Modelo:** last-click 30 dias.
- **Mecânica:**
  - Link de afiliado: `https://smartlic.tech/?ref=<partner_slug>`
  - Backend grava cookie HTTP-only `smartlic_ref=<partner_slug>` com `Max-Age=2592000` (30d) e `SameSite=Lax`.
  - Em qualquer signup posterior dentro da janela, `partner_referrals` recebe linha (`referee_user_id`, `partner_id`, `attributed_at`, `source=cookie|utm`).
  - Se múltiplos parceiros distintos tocam o lead na janela, **last-click vence** (último cookie sobrescreve).
  - UTM tag `?ref=<partner_slug>` é canônica; aliases `?utm_source=<partner_slug>` ou `?aff=<partner_slug>` são aceitos como fallback (mesma resolução).
- **Self-referral:** bloqueado por checagem de e-mail/CPF/CNPJ idêntico entre `partners.contact_email` e `profiles.email` no signup.
- **Crédito retroativo:** não. Signups anteriores ao primeiro click do parceiro não são atribuídos.

### 4. Self-service (Cadastro)

- **Sem aprovação manual** na primeira fase. Qualquer pessoa/empresa cadastra via formulário em `/parceiros/cadastro`.
- **Identificação obrigatória:**
  - PF: CPF + nome completo + e-mail + chave Pix
  - PJ: CNPJ + razão social + e-mail responsável + chave Pix
- **Validação ao submeter:**
  - CPF/CNPJ formato válido (não verificado contra Receita Federal nesta fase)
  - E-mail confirmação via link (token 24h)
  - Aceite explícito do termo (clickwrap — ver §6)
- **Slug do parceiro:** gerado server-side a partir do nome (slugify + dedup com sufixo numérico). Editável uma vez nos primeiros 7 dias.
- **Anti-fraude mínimo:**
  - Rate-limit: máx 3 cadastros/IP/dia
  - Bloqueio de e-mails descartáveis (lista MX comum: mailinator, guerrilla, etc.)
  - Self-referral check (ver §3)

### 5. Tracking

- **Cookie:** `smartlic_ref=<partner_slug>`, HTTP-only, `Max-Age=2592000` (30d), `SameSite=Lax`, `Secure` em prod.
- **UTM canônica:** `?ref=<partner_slug>` (caso exista, sobrescreve o cookie atual com o novo `partner_slug` e reinicia a janela 30d).
- **Eventos Mixpanel:**
  - `partner_link_click` (no carregamento da home com `?ref=` na URL)
  - `partner_signup_attributed` (no signup do referenciado, payload com `partner_slug` + `attribution_source`)
  - `partner_first_payment` (na primeira fatura paga do referenciado, dispara cálculo de comissão)
- **Tabelas:**
  - `partners` — cadastro
  - `partner_referrals` — relação 1:N (parceiro → leads/signups), com `attributed_at`, `first_payment_at`, `lifetime_revenue_brl`
  - `partner_payouts` — registro mensal de pagamentos (status, valor, ciclo, Pix txid)

### 6. Compliance

- **Termo de aceitação online (clickwrap):** apresentado no cadastro. Versão e timestamp gravados em `partners.terms_accepted_version` + `partners.terms_accepted_at`. Mudanças no termo forçam reaceite.
- **Conteúdo mínimo do termo:**
  - Política de comissão (20% lifetime + janela hold + cancelamento)
  - Política de fraude (autoexclusão, self-referral, fake signups)
  - Política de pagamento (cadência, mínimo, rollover, hold)
  - Direitos de rescisão (parceiro pode cancelar a qualquer momento; SmartLic pode cancelar com notificação 30d em caso de ToS violation imediata em caso de fraude)
  - Foro: comarca de São Paulo/SP
- **Tributação:**
  - **PF (CPF):** SmartLic emite RPA (Recibo de Pagamento a Autônomo) e retém IRRF + INSS quando aplicável. Parceiro recebe Pix líquido.
  - **PJ (CNPJ):** parceiro emite **nota fiscal de serviço** (NFS-e) pelo valor bruto da comissão antes do payout. SmartLic paga o bruto via Pix; retenções de PIS/COFINS/CSLL/ISS conforme município/atividade do parceiro.
- **LGPD:** cookie `smartlic_ref` não é PII isoladamente, mas a tabela `partner_referrals` correlaciona `referee_user_id` (PII). Banner de consentimento atual já cobre cookies funcionais (ver `frontend/components/CookieConsent`).
- **Stripe Coupon:** o parceiro pode receber um cupom Stripe associado ao `partner_slug` para oferecer desconto de boas-vindas ao referenciado (ex: `?ref=alex` aplica `WELCOME10`). Gated por feature flag `PARTNERS_ENABLED` e configurado no painel admin (out-of-scope desta spec inicial).

## Consequences

### Positive

- **Aquisição leveraged**: CAC marginal próximo de zero (pagamento só sobre receita realizada).
- **Alinhamento de incentivos**: lifetime (não one-shot) prioriza qualidade do referenciado, não volume.
- **Self-service**: desbloqueia parceiros sem dependência de SDR/admin, escalando linearmente.
- **Last-click 30d**: padrão de mercado, fácil de explicar e auditar.
- **Pix mensal**: simples operacionalmente, sem dependência de gateway internacional (vs. PayPal / wire transfer).

### Negative

- **Complexidade fiscal PF**: RPA + INSS/IRRF requer integração contábil ou processo manual (planilha + boletos GPS/DARF). Inicialmente manual.
- **Reconciliação mensal**: até automação de Pix API, dia 5 vira ritual operacional (1-2h/mês para <20 parceiros; revisitar quando >50).
- **Hold de 14 dias**: parceiros podem reclamar do delay; mitigação é comunicação clara no termo + dashboard com saldo `pending_release_at`.
- **Sem aprovação manual**: aumenta superfície de fraude (signups fake, self-referral). Mitigado por rate-limit + e-mail dedup + self-referral check.

### Risks

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Fraude self-cadastro (parceiros fake gerando signups fake) | Média | Médio | Rate-limit IP + e-mail validation + self-referral check + audit trimestral de outliers (parceiros com >10 signups/mês mas <10% conversion) |
| Disputa fiscal PF (parceiro contesta retenção INSS) | Baixa | Baixo | Termo clickwrap explicita PIS/COFINS/INSS; valor líquido informado no dashboard antes do payout |
| Stripe chargeback retroativo após payout enviado | Baixa | Baixo | Hold 14d cobre ~95% dos chargebacks; saldo negativo do parceiro é compensado nos ciclos seguintes |
| Last-click manipulation (parceiro força reload com seu link antes do checkout) | Baixa | Baixo | Aceito como custo do modelo (todos os last-click programs têm); mitigado por audit anual |
| Cookie blocked / Safari ITP rebaixa janela | Média | Baixo | UTM canônica `?ref=` no signup form é fallback; documentar em FAQ |

## Implementation

### Existing infrastructure (reaproveitar)

- **DB tables (já existem):**
  - `partners` — `supabase/migrations/20260301200000_create_partners.sql`
  - `partner_referrals` — mesma migration
  - **Pendente:** validar se `partner_payouts` existe; caso contrário, criar em migration nova `YYYYMMDDHHMMSS_partner_payouts.sql` + paired `.down.sql` (ver Migration Policy STORY-6.3).
- **Backend routes (já existem):** `backend/routes/partners.py` (admin endpoints). **Pendente:** endpoints públicos `/v1/partners/signup`, `/v1/partners/me`, `/v1/partners/dashboard`.
- **Feature flag:** `PARTNERS_ENABLED` (env var; default `false` até spec funcional aprovada).

### Defer (out-of-scope deste ADR; capturado para epic children)

- **Frontend:**
  - `/parceiros` (landing pública, marketing)
  - `/parceiros/cadastro` (form self-service)
  - `/parceiros/dashboard` (métricas + saldo + payouts)
  - Story dedicada (TBD em epic placement).
- **Stripe Coupon API:** integração para cupom referral_code automático por `partner_slug`.
- **Pix API automation:** quando >50 parceiros ativos.
- **RPA / NFS-e:** processo contábil manual nesta fase; revisitar com contador antes de >10 PF parceiros ativos.

### Implementation gates

| Gate | Critério | Owner |
|------|----------|-------|
| G1 — Spec funcional aprovada | `_reversa_sdd/specs/06-partner-program.spec.md` criada com user stories + OpenAPI excerpt + RLS validations | @analyst (AC3 da story) |
| G2 — Epic placement decidido | `EPIC-MON-DIST-2026-04` ou novo `EPIC-PARTNER-2026-Q3` | @pm (AC4 da story) |
| G3 — Trial→paid pipeline calibrado | n≥30 paid users (memory `feedback_n2_below_noise_eng_theater`) | Founder / @pm |
| G4 — Implementation kickoff | G1+G2+G3 satisfeitos | @pm sprint planning |

### Backlog children (a serem criadas após G1+G2)

1. **PARTNER-BE-001** — endpoints públicos `/v1/partners/{signup,me,dashboard}` + RLS policies
2. **PARTNER-BE-002** — middleware cookie `smartlic_ref` + UTM ingestion no signup flow
3. **PARTNER-BE-003** — job mensal cálculo de comissão + população `partner_payouts`
4. **PARTNER-FE-001** — `/parceiros` landing + `/parceiros/cadastro` form
5. **PARTNER-FE-002** — `/parceiros/dashboard` métricas + histórico payouts
6. **PARTNER-OPS-001** — runbook reconciliação mensal Pix (dia 5)
7. **PARTNER-LEGAL-001** — termo clickwrap revisado + RPA/NFS-e SOP

## References

- **Memory:** `project_partner_program_decisions_2026_04_29` (decisões batch L-7 user-input 2026-04-29)
- **Memory:** `reference_smartlic_baseline_2026_04_24` (pre-revenue n=2 baseline)
- **Memory:** `feedback_n2_below_noise_eng_theater` (anti-eng-theater n<5 floor)
- **Story:** `docs/stories/2026-04/GAP-PARTNER-001-program-spec.story.md`
- **Gap origin:** `_reversa_sdd/review-report.md` Gap-3
- **DB:** `supabase/migrations/20260301200000_create_partners.sql`
- **Backend:** `backend/routes/partners.py`
- **Future spec:** `_reversa_sdd/specs/06-partner-program.spec.md` (a ser criada em AC3)
- **Briefing:** `_reversa_sdd/sm-briefing-100pct.md` §11.2 (gating trial→paid)
