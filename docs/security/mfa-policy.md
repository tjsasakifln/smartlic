# Politica de MFA (Multi-Factor Authentication) — SmartLic

**Status:** Aprovado v1.0
**Responsavel:** @dev (Dex)
**Data:** 2026-06-15
**Issue:** #1882
**Ultima Revisao:** 2026-06-15

---

## 1. Resumo Executivo

O SmartLic implementa MFA via TOTP (Time-based One-Time Password) com codigos
de recuperacao para garantir acesso seguro a contas de alto privilegio e acoes
sensiveis. A politica segue o principio de **privilegio minimo**: usuarios com
maior acesso ou impacto potencial tem MFA obrigatorio; usuarios regulares tem
MFA opcional mas recomendado.

## 2. Obrigatoriedade por Role

| Role     | MFA Obrigatorio | Grace Period | Fundamento                          |
|----------|----------------|--------------|-------------------------------------|
| admin    | SIM            | Nenhum       | Acesso irrestrito a todos os dados  |
| master   | SIM            | Nenhum       | Acesso a funcionalidades premium    |
| regular  | NAO (opcional) | N/A          | Usuario padrao sem privilegios      |

### 2.1. Admin/Master

Usuarios com role `admin` ou `master` tem MFA obrigatorio desde o primeiro
login apos ativacao da conta. Nao ha periodo de carencia. Se MFA nao estiver
configurado, o acesso a qualquer rota protegida e bloqueado com HTTP 403 e
header `X-MFA-Required: true`.

**Endpoint de configuracao:** `POST /v1/mfa/enroll` + `POST /v1/mfa/verify-totp`

## 3. Obrigatoriedade por Plano

| Plano        | MFA Obrigatorio | Grace Period | Fundamento                          |
|-------------|----------------|--------------|-------------------------------------|
| consultoria | SIM            | 14 dias      | Acesso a dados de terceiros         |
| smartlic_pro| NAO (opcional) | N/A          | Plano individual                    |
| trial       | NAO (opcional) | N/A          | Periodo de teste                    |
| master      | SIM (por role) | Nenhum       | Role master, nao plano              |

### 3.1. Consultoria

Usuarios no plano `consultoria` tem 14 dias de carencia a partir da ativacao
para configurar MFA. Durante este periodo, o endpoint `GET /v1/mfa/status`
retorna `enforce_reason: "consultoria"` e `grace_days_remaining` para que o
frontend exiba o banner de alerta.

Apos o periodo de carencia, o comportamento e identico ao de admin/master:
bloqueio com HTTP 403 + `X-MFA-Required: true` + `X-MFA-Reason: consultoria`.

## 4. Acoes Sensiveis

As seguintes acoes requerem MFA **independentemente do plano ou role** do
usuario:

| Acao                      | Endpoint                                       | Middleware                     |
|---------------------------|------------------------------------------------|--------------------------------|
| Excluir conta             | `DELETE /v1/me`                                | `require_mfa_high_impact`      |
| Alterar senha             | `POST /v1/change-password`                     | `require_mfa_high_impact`      |
| Acessar billing portal    | `POST /v1/billing-portal`                      | `require_mfa_high_impact`      |
| Cancelar assinatura       | `POST /v1/api/subscriptions/cancel`            | `require_mfa_high_impact`      |
| Atualizar ciclo cobranca  | `POST /v1/api/subscriptions/update-billing-period` | `require_mfa_high_impact`  |
| Upgrade para lifetime      | `POST /v1/upgrade-to-lifetime`                 | `require_mfa_high_impact`      |

Se o usuario regular (nao-admin, nao-consultoria) ja tiver MFA configurado,
estas acoes exigem `aal2` (step-up). Se nao tiver MFA, o acesso e bloqueado
com instrucoes para configurar.

## 5. Codigos de Recuperacao

### 5.1. Geracao

- **Quantidade:** 10 codigos por batch (AC3).
- **Formato:** `XXXX-XXXX` (8 caracteres hex, uppercase, com separador).
- **Hash:** bcrypt (PBKDF2-based, armazenado em `mfa_recovery_codes.code_hash`).
- **Momento:** Gerados automaticamente durante `POST /v1/mfa/enroll`.
- **Exibicao:** Unica vez no response — o usuario deve salva-los.
- **Regeneracao:** `POST /v1/mfa/regenerate-recovery` invalida todos os
  codigos anteriores e gera novo batch (requer `aal2`).

### 5.2. Uso

- **Uso unico:** Cada codigo e marcado com `used_at` timestamp apos uso.
- **Verificacao:** `POST /v1/mfa/verify-recovery` — compara o codigo fornecido
  contra os hashes armazenados.
- **Brute force:** Maximo 3 tentativas falhas por hora (`mfa_recovery_attempts`).
  Apos o limite, HTTP 429 por 1 hora.

### 5.3. Seguranca

- Codigos sao gerados com `secrets.token_hex()` (CSPRNG).
- Hash bcrypt com salt aleatorio (protecao contra rainbow tables).
- Logs nunca contem codigos em texto plano.
- Rate limiter global: `require_rate_limit(5, 900s)` em `/verify-totp`.

## 6. Forcar Matriculamento (Brute Force Trigger)

Quando um usuario excede o limite de tentativas de recovery code, o backend
define `profiles.force_mfa_enrollment_until = NOW() + 3 dias`. Durante esta
janela, MFA e obrigatorio mesmo para usuarios regulares (HTTP 403 +
`X-MFA-Reason: bruteforce`).

A janela expirada e limpa automaticamente pelo cron `auth_cleanup`
(`clear_expired_force_mfa`).

## 7. Backward Compatibility (AC5)

Usuarios existentes sem MFA **nao sao bloqueados**, exceto nos casos acima:

- Usuarios regulares continuam acessando normalmente sem MFA (recomendado mas
  opcional).
- A unica diferenca visivel e o banner no frontend recomendando configuracao.
- Se o usuario ja configurou MFA, acoes sensiveis exigem passo adicional
  (step-up para `aal2`).

## 8. Endpoints MFA

| Metodo | Path                          | Descricao                              | Auth     |
|--------|-------------------------------|----------------------------------------|----------|
| GET    | `/v1/mfa/status`              | Status MFA + enforcement reason         | Bearer   |
| POST   | `/v1/mfa/enroll`              | Cadastrar TOTP + backup codes          | Bearer   |
| POST   | `/v1/mfa/verify-totp`         | Verificar TOTP, elevar para aal2       | Bearer   |
| POST   | `/v1/mfa/recovery-codes`      | Gerar recovery codes (apos enroll)     | Bearer   |
| POST   | `/v1/mfa/verify-recovery`     | Usar recovery code                     | Bearer   |
| POST   | `/v1/mfa/regenerate-recovery` | Regenerar recovery codes (requer aal2) | Bearer   |

## 9. Referencias

- Codigo fonte: `backend/auth.py` (`require_mfa`, `require_mfa_high_impact`)
- Politica programatica: `backend/mfa.py` (`get_mfa_policy()`)
- Rotas MFA: `backend/routes/mfa.py`
- Testes: `backend/tests/test_mfa.py`, `backend/tests/test_mfa_enforcement.py`
- Schema: `profiles.force_mfa_enrollment_until`, `mfa_factors`, `mfa_recovery_codes`
- Cron: `backend/jobs/cron/auth_cleanup.py`
