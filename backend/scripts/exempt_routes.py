"""RBAC-ORG-002: Allow-list of route modules that are explicitly public/non-org-scoped.

These routes are exempt from the org-rbac CI gate (`audit_org_id_propagation.py`).
Adding entries requires @architect + @devops review (analogous to prod-env-blocklist.txt).

Categories:
- SEO programmatic: public, no-auth, drives organic inbound (sectors, observatorio, blog,
  *_publicos, sitemaps, calculadora, comparador, lead-capture, alertas-publicos,
  indice-municipal, blog_stats, dados-publicos, daily-digest, weekly-digest)
- Health: public liveness/readiness probes
- Webhooks: external-callbacks (Stripe, Resend, etc.) — auth via signature, not org_id
- Auth flows: signup/login/oauth — pre-membership, no org context
- Sitemap: index + sub-sitemaps for SEO crawlers
"""

EXEMPT_MODULES: frozenset[str] = frozenset(
    {
        # Public read endpoints (SEO programmatic — no auth)
        "alertas_publicos",
        "blog_stats",
        "calculadora",
        "comparador",
        "compliance_publicos",
        "contratos_publicos",
        "dados_publicos",
        "daily_digest",
        "empresa_publica",
        "indice_municipal",
        "itens_publicos",
        "lead_capture",
        "municipios_publicos",
        "observatorio",
        "orgao_publico",
        "sectors_public",
        "stats_public",
        "weekly_digest",
        # Sitemaps (SEO crawler XML)
        "sitemap_cnpjs",
        "sitemap_licitacoes",
        "sitemap_licitacoes_do_dia",
        "sitemap_orgaos",
        "_sitemap_cache_headers",
        # Health / liveness
        "health",
        "health_core",
        # Auth flows (pre-membership)
        "auth_check",
        "auth_email",
        "auth_oauth",
        "auth_signup",
        # Trial emails webhook (Resend HMAC-verified)
        "trial_emails",
        # Public share GET (token-scoped, no org)
        "share",
        # Public features list
        "features",
        # Public plans listing
        "plans",
        # Lead capture (no auth)
        "survey",
    }
)
