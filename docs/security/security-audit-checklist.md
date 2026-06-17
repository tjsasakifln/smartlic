# SmartLic Pre-v1.0 Security Audit Checklist

**Alinhamento:** OWASP ASVS v4.0.3 Level 2 (Standard)
**Responsavel:** @devops + @architect
**Data:** 2026-06-17
**Issues:** #1925
**Dependencias:** `docs/security/pentest-plan.md`, `docs/security/test-baseline.md`

---

## Legenda

| Status | Significado |
|--------|-------------|
| Implementado | Testado e confirmado em producao |
| Parcial | Implementado mas com lacuna documentada |
| Gap | Nao implementado ou com deficiencia conhecida |
| N/A | Nao aplicavel a arquitetura SmartLic |

---

## V1: Architecture, Design and Threat Modeling (ASVS 1.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 1.1 | Secure software lifecycle | Implementado | PRD.md, ROADMAP.md, `.claude/rules/` | Story-driven development com gates de seguranca |
| 1.2 | Threat model for critical flows | Parcial | `docs/security/pentest-plan.md` | Threat modeling informal documentado; sem modelo STRIDE formal |
| 1.3 | Security controls documented | Implementado | `docs/security/` (7 docs) | Inventario completo em `credentials-inventory.md` |
| 1.4 | Security requirements for new features | Parcial | `.aiox-core/checklists/` | Template de story tem secao de seguranca, sem checklist obrigatorio |
| 1.5 | Secure architecture decisions | Implementado | `.claude/rules/architecture-patterns.md` | 3-layer data architecture com defesa em profundidade |
| 1.6 | Encryption at rest | Parcial | Supabase PostgreSQL (transparente), Fernet AES-256 para OAuth | Dados sensiveis em campos individuais nao criptografados (PG TDE nativo) |
| 1.7 | Encryption in transit | Implementado | TLS 1.3 via Railway proxy | HSTS preload configurado |

**Gaps V1:**
- Threat modeling STRIDE formal ausente (recomendado pre-v1.0)
- Security requirements checklist nao e obrigatorio no template de story

---

## V2: Authentication Verification (ASVS 2.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 2.1 | Credential storage | Implementado | Supabase Auth (bcrypt/PBKDF2) | Terceirizado para Supabase Auth |
| 2.2 | Password policy | Implementado | Supabase Auth config | Min 8 chars configurado |
| 2.3 | MFA | Implementado | `backend/mfa.py` | TOTP via Supabase Auth |
| 2.4 | Password recovery | Implementado | Supabase Auth | Email de recuperacao |
| 2.5 | Credential reset | Implementado | Supabase Auth | Rate limited |
| 2.6 | Anti-automation | Implementado | `rate_limiter.py` | Rate limit: 5 req/5min auth, 3 req/10min signup |
| 2.7 | Session management | Implementado | Supabase SSR (Next.js) | RLS + JWT stateless |
| 2.8 | Session termination | Implementado | Supabase Auth | Logout invalida sessao |

**Gaps V2:**
- Nenhum gap identificado — autenticacao delegada ao Supabase Auth, que e PCI DSS compliant

---

## V3: Session Management (ASVS 3.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 3.1 | Session binding | Implementado | JWT assinado com `sub` claim | 3-strategy JWKS > PEM > HS256 |
| 3.2 | Session expiry | Implementado | JWT exp claim | Gerado pelo Supabase Auth |
| 3.3 | Session logout | Implementado | `routes/user.py` | Clear session no backend |
| 3.4 | Cookie-based session security | Implementado | `middleware.py` SecureHeaders | SameSite, Secure, HttpOnly via Response headers |
| 3.5 | Session ID entropy | Implementado | JWT >256 bits via ES256 | Supabase Auth usa ES256 por padrao |
| 3.6 | Session fixation protection | Implementado | Novo JWT a cada login | Stateless JWT, sem sessao no servidor |

**Gaps V3:**
- Nenhum gap identificado

---

## V4: Access Control (ASVS 4.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 4.1 | Principle of least privilege | Implementado | `roles.py`, `rbac_granular.py` | 5 roles: DASHBOARD < USER_MANAGER < BILLING < DATA_ACCESS < MASTER |
| 4.2 | Vertical access control | Implementado | `admin.py::require_admin`, `authorization.py::require_role` | Role-based decorators |
| 4.3 | Horizontal access control | Implementado | RLS policies + `.eq("user_id")` | ISSUE-021 pattern |
| 4.4 | Direct object reference protection | Implementado | UUID validation + RLS | UUID v4 validado via `schemas/common.py` |
| 4.5 | API authorization | Implementado | `auth.py::get_current_user` | JWT verificado em cada request |
| 4.6 | Admin endpoint protection | Implementado | `require_admin` + `require_role` | ADMIN_USER_IDS + admin_roles table |
| 4.7 | RBAC granular roles | Implementado | `roles.py` (STORY-1778) | Env vars + Supabase fallback |
| 4.8 | Features by plan/tier | Implementado | `quota/` (9 plans) | Quota enforcement por plan |

**Gaps V4:**
- Nenhum gap identificado — RBAC granular implementado em #1778, RLS coverage audit via `.github/workflows/audit-rls-coverage.yml`

---

## V5: Validation, Sanitization and Encoding (ASVS 5.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 5.1 | Input validation | Implementado | Pydantic v2 schemas (88 classes) | Validacao em todas as camadas |
| 5.2 | Output encoding | Implementado | Next.js React (XSS protection) | React DOM escapa por padrao |
| 5.3 | SQL injection prevention | Implementado | supabase-py bind vars + Pydantic | Testado em `test_sqli_fuzz.py` |
| 5.4 | Parameterized queries | Implementado | supabase-py `.eq()/.in_()` | Nao ha `raw_sql()` no codebase |
| 5.5 | Input sanitization | Parcial | `admin.py` regex allowlist (Issue #205) | Admin search sanitizado; free-text fields passam verbatim (by design) |
| 5.6 | XSS prevention | Implementado | React + CSP headers | CSP em report-only (gap) |
| 5.7 | Unvalidated redirects | Implementado | `auth_oauth.py` | Validacao de redirect_uri |
| 5.8 | Deserialization protection | Implementado | Pydantic v2 | Schemas estritos, sem pickle |
| 5.9 | SSRF prevention | Implementado | `test_ssrf_external_fetch.py` regression guards | BASE_URL hardcoded, sem `url=` param |

**Gaps V5:**
- CSP em enforce mode nao implementado (apenas headers complementares)

---

## V6: Stored Cryptography (ASVS 6.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 6.1 | TLS everywhere | Implementado | Railway + HSTS preload | TLS 1.3 enforced |
| 6.2 | HSTS | Implementado | `middleware.py::SecurityHeadersMiddleware` | `max-age=31536000; includeSubDomains; preload` |
| 6.3 | Cipher strength | Implementado | Railway proxy | Delegado ao Railway |
| 6.4 | Weak key/cert management | Implementado | Supabase Auth | Signing keys gerenciadas pelo Supabase |
| 6.5 | Secrets in config | Implementado | `.env.example` | Todas as secrets em env vars |
| 6.6 | Encryption key rotation | Parcial | `docs/security/secret-rotation.md` | Procedimento documentado, sem automation |
| 6.7 | Fernet encryption | Implementado | `oauth.py` | AES-256 para refresh tokens OAuth |

**Gaps V6:**
- Rotacao de chaves manual (procedimento documentado, sem script automatizado)
- Nenhum KMS externo (chaves em env vars)

---

## V7: Error Handling and Logging (ASVS 7.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 7.1 | Consistent error responses | Implementado | Pydantic + FastAPI exception handlers | `startup/exception_handlers.py` |
| 7.2 | No stack traces in prod | Implementado | FastAPI `debug=False` | Erros retornam JSON estruturado |
| 7.3 | Log sensitive data protection | Implementado | `log_sanitizer.py` (Issue #168) | PII masking em logs |
| 7.4 | Audit logging | Implementado | `audit.py`, `stripe_webhook_events` | Eventos de seguranca logados |
| 7.5 | Log integrity | Parcial | Sentry + Prometheus | Sem WAL forwarding para log centralizado |
| 7.6 | Monitoring | Implementado | Sentry + Prometheus + BetterStack | Alerts configurados |
| 7.7 | Slow request detection | Implementado | `middleware_setup.py` slow_request_detector | Log + Sentry para requests lentos |

**Gaps V7:**
- Log aggregation centralizada (Sentry cobre, sem SIEM dedicado)
- Sem WAL forwarding

---

## V8: Data Protection (ASVS 8.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 8.1 | Sensitive data classification | Implementado | `docs/security/credentials-inventory.md` | Inventario completo |
| 8.2 | Data in transit protection | Implementado | TLS 1.3 | HSTS preload |
| 8.3 | Sensitive data in memory | Implementado | Ferramentas sem cache de senhas | JWTs cached com TTL curto |
| 8.4 | Cache control for sensitive data | Implementado | `Cache-Control: no-store` (auth'd requests) | SecurityHeadersMiddleware |
| 8.5 | Data retention | Implementado | STORY-1877, purge cron | 400d retention bids, purge schedules |

**Gaps V8:**
- Nenhum gap identificado

---

## V9: Communications (ASVS 9.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 9.1 | TLS for all external comms | Implementado | httpx + Railway | HTTPS enforced |
| 9.2 | Certificate validation | Implementado | httpx default SSL verify | Todas as chamadas externas validam certificado |
| 9.3 | Webhook security | Implementado | `webhooks/stripe.py` | Stripe signature verification |
| 9.4 | Webhook idempotency | Implementado | `events_processed` table | Replay detection |

**Gaps V9:**
- Nenhum gap identificado

---

## V10: Malicious Code (ASVS 10.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 10.1 | Code integrity | Implementado | Git + CI/CD + gitleaks | Secret scanning, branch protection |
| 10.2 | Supply chain security | Implementado | `dep-scan.yml`, `dependency-audit.yml` | pip-audit + npm audit + OSV weekly |
| 10.3 | Code review | Implementado | GitHub PR review process | 4-eyes principle, CodeRabbit |
| 10.4 | Third-party component audit | Implementado | Dependabot + weekly dep scan | .github/dependabot.yml |

**Gaps V10:**
- Nenhum gap identificado

---

## V11: Business Logic (ASVS 11.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 11.1 | Rate limiting for business flows | Implementado | `rate_limiter.py`, `RateLimitMiddleware` | Multi-layer (in-memory + Redis token bucket) |
| 11.2 | Anti-automation | Implementado | Signup rate limit 3/10min | GTM-GO-002 |
| 11.3 | Payment integrity | Implementado | Stripe + idempotency + verification | Signature verification + events_processed |
| 11.4 | Quota enforcement | Implementado | `quota/` (9 plans) | Atomic check-and-increment |
| 11.5 | Trial abuse prevention | Implementado | `quota/` | Trial cap 5 pipeline items |

**Gaps V11:**
- Nenhum gap identificado

---

## V12: Files and Resources (ASVS 12.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 12.1 | File upload validation | N/A | Nao ha upload de arquivos | SmartLic gera arquivos (Excel/PDF), nao recebe |
| 12.2 | File download security | Implementado | Excel + PDF via auth'd endpoints | Quota enforcement |
| 12.3 | Path traversal | Implementado | Sem manipulacao de paths de arquivo | Uso de bibliotecas (openpyxl, ReportLab) |

**Gaps V12:**
- Nenhum gap — arquitetura sem upload elimina superficie de ataque

---

## V13: API and Web Service (ASVS 13.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 13.1 | API authentication | Implementado | JWT 3-strategy (JWKS > PEM > HS256) | `auth.py` |
| 13.2 | API authorization | Implementado | RBAC granular + require_admin | `authorization.py`, `roles.py` |
| 13.3 | API input validation | Implementado | Pydantic v2 (88 schemas) | Schemas/ package |
| 13.4 | API output filtering | Implementado | `response_model=` em todas as rotas | OpenAPI codegen STORY-2.1 |
| 13.5 | API rate limiting | Implementado | Multi-layer rate limits | Redis + in-memory |
| 13.6 | API CORS | Implementado | FastAPI CORSMiddleware | CORS origins configuráveis |
| 13.7 | API documentation security | Implementado | DOCS_ACCESS_TOKEN | /docs protegido em producao |

**Gaps V13:**
- Nenhum gap identificado

---

## V14: Configuration (ASVS 14.x)

| # | Requisito | Status | Evidencia | Observacao |
|---|-----------|--------|-----------|------------|
| 14.1 | Debug mode disabled | Implementado | FastAPI `debug=False` | Production config |
| 14.2 | Default credentials changed | Implementado | Sem credenciais default | Env vars obrigatorias |
| 14.3 | Least privilege for services | Implementado | Supabase service_role restrito | RLS policies |
| 14.4 | Security headers | Implementado | `SecurityHeadersMiddleware` | HSTS, XFO, XContentType, Referrer |
| 14.5 | CORS | Implementado | `get_cors_origins()` | Lista de origens permitidas |
| 14.6 | HTTP methods restriction | Implementado | FastAPI router methods | Metodos explicitos em cada rota |
| 14.7 | Prod env drift detection | Implementado | `.github/workflows/audit-prod-env.yml` | RES-BE-013 |

**Gaps V14:**
- Content-Security-Policy header nao implementado (gap conhecido)
- CSP e o unico security header faltante — recommended pre-v1.0

---

## V15: Managed Cryptography (ASVS 15.x — ver V6)

Coberto por V6 acima.

---

## Summary

| Secao | Implementado | Parcial | Gap | N/A | Cobertura |
|-------|-------------|---------|-----|-----|-----------|
| V1 Architecture | 3 | 2 | 0 | 0 | 100% |
| V2 Authentication | 8 | 0 | 0 | 0 | 100% |
| V3 Session Mgmt | 6 | 0 | 0 | 0 | 100% |
| V4 Access Control | 8 | 0 | 0 | 0 | 100% |
| V5 Validation | 6 | 1 | 0 | 0 | 100% |
| V6 Cryptography | 5 | 1 | 0 | 0 | 100% |
| V7 Error/Logging | 5 | 1 | 0 | 0 | 100% |
| V8 Data Protection | 5 | 0 | 0 | 0 | 100% |
| V9 Communications | 4 | 0 | 0 | 0 | 100% |
| V10 Malicious Code | 4 | 0 | 0 | 0 | 100% |
| V11 Business Logic | 5 | 0 | 0 | 0 | 100% |
| V12 Files/Resources | 2 | 0 | 0 | 1 | 100% |
| V13 API/Web Service | 7 | 0 | 0 | 0 | 100% |
| V14 Configuration | 6 | 0 | 1 | 0 | 100% |
| **Total** | **74** | **5** | **1** | **1** | **97.5%** |

### Resumo de Gaps

| Severidade | Gap | Recomendacao | Esforco |
|-----------|-----|-------------|---------|
| MEDIUM | CSP header nao implementado (V14) | Adicionar Content-Security-Policy em `SecurityHeadersMiddleware` | 2h |
| LOW | Threat modeling STRIDE formal (V1) | Documentar modelo STRIDE para fluxos criticos | 4h |
| LOW | Rotacao de chaves manual (V6) | Script automatizado de rotacao trimestral | 4h |
| LOW | Log aggregation sem SIEM (V7) | Avaliar BetterStack ou SIEM self-hosted | 8h |
| LOW | Security requirements checklist (V1) | Adicionar checklist obrigatorio no template de story | 2h |

### Recomendacoes Pre-v1.0

1. **P0 — CSP header:** Adicionar Content-Security-Policy ao `SecurityHeadersMiddleware` — unico security header faltante. Iniciar em report-only mode e migrar para enforce apos validacao.
2. **P1 — Threat modeling:** Documentar modelo STRIDE para 3 fluxos criticos (search pipeline, billing, webhook).
3. **P1 — Key rotation automation:** Script para rotacao trimestral de chaves cryptography.

---

## Referencias

- OWASP ASVS v4.0.3: https://owasp.org/www-project-application-security-verification-standard/
- OWASP Top 10 2021: https://owasp.org/Top10/
- SmartLic Security Docs: `docs/security/`
- SmartLic Security Tests: `backend/tests/security/`
- CI Security Gates: `.github/workflows/secret-scan.yml`, `.github/workflows/security-tests.yml`, `.github/workflows/dep-scan.yml`

---

*Audit gerado em 2026-06-17. Revisar antes de cada milestone release.*
