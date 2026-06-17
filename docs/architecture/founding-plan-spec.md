# Founding Plan -- Business Rules Specification

**Status:** Implemented (v2 lifetime)
**Last updated:** 2026-06-17
**ADRs:** `docs/adr/ADR-BIZ-FOUND-002-founding-policy.md`, `docs/adr/founding-plan-canonical.md`
**Epic/Stories:** BIZ-FOUND-002, STORY-BIZ-001, #783 (v2 lifetime pivot), #785 (lifetime entitlement)

---

## 1. Overview

The Founding Plan (Plano Fundadores) is a limited-time, fixed-cap offer for early adopters of SmartLic. It grants lifetime access to SmartLic Pro via a one-time payment of R$997, plus a permanent 50% discount on the Consulting tier.

The program has evolved through two phases:

| Phase | Model | Price | Period | Status |
|-------|-------|-------|--------|--------|
| v1 (STORY-BIZ-001) | Monthly subscription at 50% off | R$197/month | 2026-04-xx to 2026-05-06 | Superseded |
| v2 (#783) | One-time lifetime payment | R$997 | 2026-05-07 to present | **Current** |

---

## 2. Eligibility Rules

### 2.1 Who Can Purchase

- Any business entity (B2G) with a valid Brazilian CNPJ.
- Purchase is made by an individual (nome, email, CNPJ, razao_social, motivo).
- No prior SmartLic account required -- founding is sold to unauthenticated visitors.
- "motivo" field requires minimum 140 characters (qualifying question).

### 2.2 Who Cannot Purchase

- Emails that already have a SmartLic profile (returns HTTP 409).
- Duplicate CNPJ is allowed (checked at checkout, not a blocker).
- Self-referral not applicable (no referral flow for founding).

### 2.3 Seat Cap (50 total)

The Founding Plan has a hard cap of **50 seats** (completed checkouts). Once reached, all subsequent checkout attempts receive HTTP 410 Gone with `error_code: founding_cap_reached`.

Cap counting basis: `founding_leads WHERE checkout_status = 'completed'` (not profiles.plan_type).

### 2.4 Deadline

| Original deadline | Extended deadline | Status (as of 2026-06-17) |
|-------------------|-------------------|---------------------------|
| 2026-05-30 23:59:59 BRT | 2026-06-30 23:59:59 -03:00 | Active (extended by v2 lifetime pivot) |

The deadline was extended from 2026-05-30 to 2026-06-30 in the v2 lifetime pivot migration (`20260507100100_founding_policy_lifetime_pivot.sql`). After the deadline, checkout returns HTTP 410 with `error_code: founding_deadline_passed`.

### 2.5 Auto-Disable

An ARQ cron job (`founders_auto_disable_check`) runs periodically and auto-disables the offer 1 day after the deadline (timezone safety margin). Sets `founding_policy.active = False` and sends a Sentry warning.

---

## 3. Pricing

### 3.1 Current Pricing (v2 Lifetime)

| Item | Value |
|------|-------|
| Payment model | One-time (`mode='payment'`) |
| Price | R$997 (99700 BRL cents) |
| Payment methods | Credit card (`card`) and Boleto (`boleto`) |
| Stripe Price ID | Configured via env var `FOUNDING_ONE_TIME_PRICE_ID` |
| Coupon/Discount | None applied (no coupon block) |
| Offer mode | `lifetime` |

### 3.2 Legacy Pricing (v1 -- Superseded)

| Item | Value |
|------|-------|
| Payment model | Subscription (`mode='subscription'`) |
| Price | R$197/month (50% off standard Pro) |
| Coupon | `FOUNDING30` (30% off / 12 months, later `FOUNDING_LIFETIME` 50% off forever) |

### 3.3 Stripe Configuration

The Stripe Product and Price are provisioned out-of-band via script:

```bash
python scripts/create_founding_lifetime_price.py
```

Prints `FOUNDING_ONE_TIME_PRICE_ID=price_xxx` which must be set as Railway env var. The script is idempotent (reuses existing Product/Price by name and amount).

---

## 4. Entitlements

On successful checkout completion, the following entitlements are activated on the user's profile:

| Field | Value | Description |
|-------|-------|-------------|
| `is_founder` | `true` | Founder flag |
| `founder_since` | ISO 8601 timestamp | When checkout completed |
| `founder_offer_version` | `v2_lifetime` | Offer version from Stripe metadata |
| `founder_checkout_source` | Source string | utm_source or `founding_page` |
| `consulting_discount_pct` | 50 (default) | Lifetime discount on Consulting tier |
| `plan_type` | `smartlic_pro` | Plan assignment |
| `trial_expires_at` | `null` | Trial cleared |

The `consulting_discount_pct` is read from `founding_policy.consulting_discount_pct` (default 50). The offer version and checkout source are preserved from Stripe session metadata.

### 4.1 Post-Purchase Flow

1. **User has an account**: Entitlement activated immediately. Founders welcome email dispatched (fire-and-forget background thread, idempotency via `founding_leads.welcome_sent_at`).
2. **User has NO account**: Entitlement activation deferred. Supabase magic-link invite sent (`_send_founding_invite`) so the buyer can create their account and claim access. Invite idempotency via `founding_leads.magic_link_sent_at`.

---

## 5. How Founding Plan Differs from Regular Plans

| Aspect | Founding Plan | Regular Plans (Pro, Consultor, etc.) |
|--------|--------------|--------------------------------------|
| Payment | One-time R$997 | Monthly/quarterly/annual subscription |
| Access duration | Lifetime | While subscription is active |
| Price changes | Frozen (lifetime guarantee) | Subject to future pricing updates |
| Seat cap | 50 total | Unlimited |
| Deadline | 2026-06-30 | No deadline |
| Consulting discount | 50% off forever | None |
| Trial | None (purchase directly) | 14-day free trial |
| Availability check | `check_founding_availability()` RPC | No gate |
| Post-purchase invite | Magic link for unauthenticated buyers | Regular signup flow |

---

## 6. Availability & Race Guard

### 6.1 Public Availability Endpoint

`GET /v1/founding/availability` (anonymous) returns:
- `available`: boolean
- `seats_total`: 50
- `seats_remaining`: integer
- `seats_taken`: integer
- `deadline_at`: ISO timestamp or null
- `paused`: boolean
- `reason`: string enum
- `offer_mode`: `lifetime`
- `price_brl_cents`: 99700

Cached with `Cache-Control: public, s-maxage=30`. Disabled by feature flag `FOUNDERS_OFFER_ENABLED=false`.

### 6.2 Reason Enum (why unavailable)

| reason | Meaning |
|--------|---------|
| `founding_cap_reached` | 50 seats filled |
| `founding_deadline_passed` | After 2026-06-30 |
| `founding_paused` | Admin soft-pause |
| `founding_disabled` | `founding_policy.active = false` |
| `founding_policy_missing` | No policy row in DB |

### 6.3 Two-Layer Race Guard

**Layer 1 (pre-checkout):** `check_founding_availability()` RPC uses `SELECT FOR UPDATE` on the `founding_policy` row + counts completed leads atomically. Concurrent callers serialize on the row lock. Returns `available=false` with structured `error_code` for HTTP 410 responses.

**Layer 2 (post-completion):** Stripe webhook `checkout.session.completed` re-runs the RPC AFTER flipping the lead row to `completed`. If `founding_cap_reached` is detected:
1. Sets `checkout_status = 'cap_violated'`
2. Issues Stripe Refund against the `payment_intent`
3. Queues apology email to customer
4. Logs Sentry error for operator alert

---

## 7. Admin Operations

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/admin/founding/policy` | GET | Policy snapshot + live seat usage |
| `/v1/admin/founding/leads` | GET | List founding leads with filter |
| `/v1/admin/founding/pause` | POST | Soft-pause checkouts (paused_at + paused_by) |
| `/v1/admin/founding/resume` | POST | Clear pause |

All admin endpoints require `is_admin` or `is_master` role.

---

## 8. Feature Flag

`FOUNDERS_OFFER_ENABLED` (default: `true`) disables the entire founding flow when set to `false`:
- `GET /v1/founding/availability` returns `available=false`, `reason=founders_offer_disabled`
- `POST /v1/founding/checkout` returns HTTP 410

---

## 9. Database Schema

### `founding_policy` (single-row, id=1)

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | INT | 1 | Single-row enforcement (CHECK id=1) |
| seat_limit | INT | 50 | Hard cap |
| deadline_at | TIMESTAMPTZ | | Cutoff timestamp |
| discount_pct | INT | 50 | Lifetime discount % |
| coupon_code | TEXT | FOUNDING_LIFETIME | Stripe coupon reference |
| active | BOOLEAN | TRUE | Hard kill switch |
| paused_at | TIMESTAMPTZ | NULL | Soft-pause timestamp |
| paused_by | UUID | NULL | Admin who paused |
| paused_reason | TEXT | NULL | Reason for pause |
| offer_mode | TEXT | 'lifetime' | 'subscription' or 'lifetime' |
| price_brl_cents | INT | 99700 | One-time price in BRL cents |
| consulting_discount_pct | INT | 50 | Consulting tier discount % |

### `founding_leads`

Tracks each checkout attempt. Status enum: `pending`, `completed`, `abandoned`, `failed`, `cap_violated`.

---

## 10. Key Files

| File | Purpose |
|------|---------|
| `backend/routes/founding.py` | Checkout + availability endpoints |
| `backend/routes/admin_founding.py` | Admin policy management |
| `backend/webhooks/handlers/founding.py` | Webhook handlers + race guard + entitlement activation |
| `backend/jobs/cron/founders_auto_disable.py` | Auto-disable cron after deadline |
| `backend/tests/test_founding_canonical_policy.py` | Policy gate tests |
| `backend/tests/test_founding_checkout.py` | Checkout flow tests |
| `backend/tests/test_founding_webhook_*.py` | Webhook handler tests |
| `backend/tests/test_founding_session_status.py` | Session status tests |
| `backend/tests/test_founders_welcome_email.py` | Welcome email tests |
| `scripts/create_founding_lifetime_price.py` | Stripe price provisioner |
| `frontend/app/api/founding/availability/route.ts` | Frontend availability proxy |
| `frontend/app/api/founding/checkout/route.ts` | Frontend checkout proxy |
| `frontend/hooks/useFoundersAvailability.ts` | Frontend availability hook |
| `supabase/migrations/20260428100000_founding_canonical_policy.sql` | Founding policy table |
| `supabase/migrations/20260428100100_check_founding_availability_rpc.sql` | Availability RPC |
| `supabase/migrations/20260507100100_founding_policy_lifetime_pivot.sql` | v2 lifetime pivot |
