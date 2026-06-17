# Environment Parity Blocklist (#1917)

Env vars that are **intentionally different** between staging and production
and should be **excluded** from the parity CI gate's critical-drift check.

> The parity CI gate (`parity-check.yml`) treats every env var present in
> staging but missing in production as a **critical drift** (exit 1). This file
> documents the planned exceptions — variables that legitimately exist in only
> one environment.

## Format

- One pattern per line.
- Lines starting with `#` are comments.
- Glob-style wildcards: `ENVIRONMENT` matches only that exact name,
  `NEXT_PUBLIC_*` matches any key starting with `NEXT_PUBLIC_`.
- Matching is case-sensitive.

## How to add an entry

1. Confirm the variable is genuinely environment-specific (not an accidental
   omission from production).
2. Add the key or glob pattern below.
3. Commit with a brief justification in the PR description.
4. PR requires review by **@devops**.

---

## Blocklist

```text
# ─── Environment identifier ─────────────────────────────────────────────────
# ENVIRONMENT and APP_ENV always differ between staging and production.
# This is expected and intentional.
ENVIRONMENT
APP_ENV

# ─── Debug / verbosity ──────────────────────────────────────────────────────
# Staging may enable debug-level logging and dev-mode flags that should never
# be set in production.  The parity gate would flag them as "staging-only"
# unless excluded here.
DEBUG
DEV_MODE
FASTAPI_DEBUG
LOG_LEVEL
PYTHONASYNCIODEBUG
PYTHONVERBOSE

# ─── Feature flags still in testing ─────────────────────────────────────────
# New feature flags are often deployed to staging first.  Once validated they
# are promoted to production.  List them here during the testing window and
# **remove the entry when promoted to production**.
# ENABLE_NEW_FEATURE_X

# ─── Service URLs ───────────────────────────────────────────────────────────
# Backend and frontend URLs are environment-specific (different Railway
# domains or custom domains).
BACKEND_URL
NEXT_PUBLIC_BACKEND_URL
FRONTEND_URL
NEXT_PUBLIC_FRONTEND_URL
STAGING_BACKEND_URL
STAGING_FRONTEND_URL

# ─── External service credentials ───────────────────────────────────────────
# API keys, tokens and webhook secrets are always environment-specific.
SENTRY_DSN
SENTRY_AUTH_TOKEN
MIXPANEL_TOKEN
NEXT_PUBLIC_MIXPANEL_TOKEN
RESEND_API_KEY
RESEND_WEBHOOK_SECRET
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
STRIPE_PUBLISHABLE_KEY

# ─── Database ───────────────────────────────────────────────────────────────
# Supabase project references and connection strings differ per environment.
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_ANON_KEY
SUPABASE_JWT_SECRET
SUPABASE_PROJECT_REF
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
DATABASE_URL

# ─── Railway-injected ‼DO NOT REMOVE‼ ───────────────────────────────────────
# Railway injects RAILWAY_* variables whose exact set varies by environment
# (different service IDs, different deployment IDs, etc.).  Listing them all
# explicitly is impractical; the wildcard covers all of them.
RAILWAY_*

# ─── OAuth ──────────────────────────────────────────────────────────────────
# OAuth client IDs / secrets may differ per environment (staging vs prod app
# registrations).
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
OAUTH_FERNET_KEY

# ─── Next.js / Frontend ─────────────────────────────────────────────────────
# Next.js public env vars carry the environment URL, which always differs
# between staging and prod.  Build-time env vars also differ.
NEXT_PUBLIC_*
NEXT_*

# ─── Stripe price/product IDs ───────────────────────────────────────────────
# Products and prices may be created separately in staging vs prod Stripe
# accounts.
STRIPE_PRICE_*
STRIPE_PRODUCT_*

# ─── Seed data ──────────────────────────────────────────────────────────────
# Admin/master seed passwords only exist in production; staging may have
# different test seeds.
SEED_*
```

## Lifecycle

| State | Meaning |
|-------|---------|
| **Active** | Listed below — parity CI will NOT flag these as critical |
| **Promoted** | Removed from this list after the var is added to production |
| **Removed** | No longer needed; entry was cleaned up |

Entries should be **removed** from this list once the corresponding variable
has been added to the production environment.  Use PRs to manage this lifecycle.
