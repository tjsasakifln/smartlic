# Audit: `.execute()` callsites unprotected (RES-BE-002c AC1)

**Generated:** 2026-04-30T01:08:23Z
**Command:**
```bash
scripts/audit_execute_callsites.sh
```

**Pattern grep:** `.execute(` em `backend/routes/` excluindo `_run_with_budget`, `asyncio.to_thread`, `test_`.

## Callsites unprotected

| File:line | Context (function) | Tier (manual) | Notes |
|-----------|-------------------|---------------|-------|
| `backend/routes/auth_signup.py:94` | def _update_profile_with_stripe( | TODO | |
| `backend/routes/blog_stats.py:39` |  | TODO | |
| `backend/routes/blog_stats.py:924` | def _query_contratos_sync( | TODO | |
| `backend/routes/comparador.py:165` | async def get_bids_by_ids( | TODO | |
| `backend/routes/compliance_publicos.py:177` | async def _fetch_razao_social(cnpj: str) -> str: | TODO | |
| `backend/routes/conta.py:101` | def _load_profile_and_subscription(sb, user_id: str) -> tuple[Optional[dict], Op | TODO | |
| `backend/routes/conta.py:113` | def _load_profile_and_subscription(sb, user_id: str) -> tuple[Optional[dict], Op | TODO | |
| `backend/routes/conta.py:257` | def cancel_trial_execute(payload: CancelTrialRequest) -> CancelTrialResponse: | TODO | |
| `backend/routes/conta.py:265` | def cancel_trial_execute(payload: CancelTrialRequest) -> CancelTrialResponse: | TODO | |
| `backend/routes/contratos_publicos.py:184` | async def _fetch_sector_contracts(sector_id_clean: str, uf_upper: str) -> list[d | TODO | |
| `backend/routes/contratos_publicos.py:236` | async def orgao_contratos_stats(cnpj: str): | TODO | |
| `backend/routes/contratos_publicos.py:650` | async def _build_fornecedor_profile(cnpj_clean: str) -> dict: | TODO | |
| `backend/routes/empresa_publica.py:450` | async def _fetch_contratos_local(cnpj: str) -> tuple[list[dict], str]: | TODO | |
| `backend/routes/features.py:135` | def fetch_features_from_db(user_id: str) -> UserFeaturesResponse: | TODO | |
| `backend/routes/features.py:70` | def fetch_features_from_db(user_id: str) -> UserFeaturesResponse: | TODO | |
| `backend/routes/features.py:95` | def fetch_features_from_db(user_id: str) -> UserFeaturesResponse: | TODO | |
| `backend/routes/founding.py:100` | def _already_registered(sb, email: str) -> bool: | TODO | |
| `backend/routes/founding.py:162` | async def founding_checkout( | TODO | |
| `backend/routes/founding.py:182` | async def founding_checkout( | TODO | |
| `backend/routes/founding.py:230` | async def founding_checkout( | TODO | |
| `backend/routes/indice_municipal.py:266` | async def get_municipio( | TODO | |
| `backend/routes/itens_publicos.py:443` | async def _fetch_price_data(nome_item: str) -> tuple[list[float], list[dict]]: | TODO | |
| `backend/routes/lead_capture.py:48` | async def capture_lead(req: LeadCaptureRequest): | TODO | |
| `backend/routes/mfa.py:107` | async def _check_brute_force(user_id: str) -> int: | TODO | |
| `backend/routes/mfa.py:128` | async def _record_attempt(user_id: str, success: bool) -> None: | TODO | |
| `backend/routes/mfa.py:157` | async def get_mfa_status(user: dict = Depends(require_auth)): | TODO | |
| `backend/routes/mfa.py:193` | async def generate_recovery_codes(user: dict = Depends(require_auth)): | TODO | |
| `backend/routes/mfa.py:205` | async def generate_recovery_codes(user: dict = Depends(require_auth)): | TODO | |
| `backend/routes/mfa.py:235` | async def verify_recovery_code( | TODO | |
| `backend/routes/mfa.py:246` | async def verify_recovery_code( | TODO | |
| `backend/routes/mfa.py:273` | async def verify_recovery_code( | TODO | |
| `backend/routes/mfa.py:304` | async def regenerate_recovery_codes(user: dict = Depends(require_auth)): | TODO | |
| `backend/routes/mfa.py:310` | async def regenerate_recovery_codes(user: dict = Depends(require_auth)): | TODO | |
| `backend/routes/municipios_publicos.py:378` | async def municipio_profile(slug: str): | TODO | |
| `backend/routes/observatorio.py:324` | def _query_historical_sync(data_inicial: str, data_final: str) -> list[dict]: | TODO | |
| `backend/routes/orgao_publico.py:225` | async def _build_orgao_stats(cnpj: str) -> dict: | TODO | |
| `backend/routes/orgao_publico.py:376` | async def _fetch_contracts_data(orgao_cnpj: str, limit: int = 10) -> dict: | TODO | |
| `backend/routes/plans.py:87` | async def get_plans_with_capabilities(db=Depends(get_db)): | TODO | |
| `backend/routes/referral.py:107` | def _get_or_create_code_for_user(sb, user_id: str) -> str: | TODO | |
| `backend/routes/referral.py:163` | async def get_referral_code(user: dict = Depends(require_auth)): | TODO | |
| `backend/routes/referral.py:205` | async def get_referral_stats(user: dict = Depends(require_auth)): | TODO | |
| `backend/routes/referral.py:255` | async def redeem_referral( | TODO | |
| `backend/routes/referral.py:280` | async def redeem_referral( | TODO | |
| `backend/routes/referral.py:79` | def _get_or_create_code_for_user(sb, user_id: str) -> str: | TODO | |
| `backend/routes/referral.py:92` | def _get_or_create_code_for_user(sb, user_id: str) -> str: | TODO | |
| `backend/routes/relatorio.py:102` | async def request_relatorio(payload: RelatorioRequest, request: Request): | TODO | |
| `backend/routes/seo_admin.py:48` | async def get_seo_metrics( | TODO | |
| `backend/routes/sitemap_cnpjs.py:178` | def _fetch_top_cnpjs() -> dict: | TODO | |
| `backend/routes/sitemap_cnpjs.py:216` | def _fetch_top_cnpjs() -> dict: | TODO | |
| `backend/routes/sitemap_cnpjs.py:321` | def _fetch_top_fornecedores_cnpjs() -> dict: | TODO | |
| `backend/routes/sitemap_licitacoes.py:272` | async def count_contracts(setor_id: str, keywords: list[str], uf: str) -> tuple[ | TODO | |
| `backend/routes/sitemap_licitacoes_do_dia.py:133` | def _fetch_indexable_dates() -> dict: | TODO | |
| `backend/routes/sitemap_orgaos.py:112` | def _fetch_top_orgaos() -> dict: | TODO | |
| `backend/routes/sitemap_orgaos.py:145` | def _fetch_top_orgaos() -> dict: | TODO | |
| `backend/routes/sitemap_orgaos.py:262` | def _fetch_contratos_orgao_indexable() -> dict: | TODO | |
| `backend/routes/user.py:162` | async def get_profile(user: dict = Depends(require_auth), db=Depends(get_db)): | TODO | |
| `backend/routes/user.py:316` | async def get_recommended_plan( | TODO | |

## Total

Unprotected callsites: **57**

## Tier classification (manual)

- **Top tier (sweep this PR):** SEO public + bot-thrashable (contratos_publicos, orgao_publico, sitemap_*, observatorio)
- **Mid tier (defer next session):** auth path (mfa.py, conta.py, auth_signup.py) — baixo bot impact
- **Low tier (defer):** referral.py, plans.py — funcionalidade rara

Priorização final em `docs/audit/execute-sweep-priority-list.md` (cross-ref Sentry impressions 7d).
