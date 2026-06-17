# Partner Program -- Business Rules Specification

**Status:** Implemented (database schema + backend routes + service layer)
**Last updated:** 2026-06-17
**ADRs:** `docs/adr/partner-program.md`
**Stories:** STORY-323 (Revenue Share Tracking), EPIC-CI-GREEN-MAIN-2026Q2/STORY-CIG-FE-12-admin-partners
**Related: User Referral Program** (`backend/routes/referral.py` -- separate program, see section 7)

---

## 1. Overview

The Partner Program is a revenue-sharing program for consultancy firms and partner companies that refer clients to SmartLic. Partners earn a recurring commission on the subscription revenue of clients they bring in.

**This is distinct from the User Referral Program** (section 7), which is an end-user program offering 1 month free per conversion.

---

## 2. Commission Structure

### 2.1 Default Commission Rate

| Parameter | Value |
|-----------|-------|
| Default commission | **20% lifetime revenue share** |
| Source of truth | `partners.revenue_share_pct` column |
| Override | Each partner can have a negotiated `revenue_share_pct` (set by admin at creation) |

### 2.2 Commission Calculation

```
Commission = SUM(referral.monthly_revenue) * partner.revenue_share_pct / 100
```

Where:
- `monthly_revenue` is the monthly subscription amount of each active referral
- A referral is "active" when `converted_at IS NOT NULL AND (churned_at IS NULL OR churned_at > month_start)`
- Churned referrals are excluded from the month they churn

### 2.3 How Commission is Tracked

On checkout completion, the Stripe webhook creates a `partner_referrals` row with:
- `monthly_revenue`: the subscription amount in BRL
- `revenue_share_amount`: calculated as `monthly_revenue * revenue_share_pct / 100`
- `converted_at`: timestamp of checkout completion

The `revenue_share_amount` is stored at conversion time. If the partner's `revenue_share_pct` changes later, existing referral rows keep their original share amount (historical integrity).

### 2.4 Churn Handling

On `customer.subscription.deleted`, the Stripe webhook calls `mark_referral_churned()` which stamps `partner_referrals.churned_at`. Churned referrals are excluded from future commission calculations.

---

## 3. Attribution Rules

### 3.1 Attribution Mechanisms (Two-Factor)

The partner program uses a **last-click attribution model** with two mechanisms:

#### Mechanism 1: Signup Flow (`?partner=` query param)

1. User signs up with `?partner={slug}` in the URL (e.g., `https://smartlic.tech/signup?partner=triunfo-legis`)
2. Backend calls `attribute_signup_to_partner()` during signup
3. Stores `profiles.referred_by_partner_id` on the user's profile
4. On checkout completion, `create_partner_referral()` reads `referred_by_partner_id` from the profile

#### Mechanism 2: Coupon-Based Attribution (Fallback)

1. Partner's Stripe coupon ID is stored in `partners.stripe_coupon_id`
2. During checkout, if the user applies a coupon that matches a partner's `stripe_coupon_id`
3. `create_partner_referral()` falls back to looking up the partner by coupon
4. Also updates the user's profile with `referred_by_partner_id` for future reference

### 3.2 Attribution Priority

```
1. Profile attribution (referred_by_partner_id from signup) -- PRIME
2. Coupon-based (stripe_coupon_id match) -- FALLBACK
3. No attribution -- referral NOT created
```

### 3.3 Attribution Window

A **30-day last-click attribution window** is documented but NOT yet enforced in code. The current implementation attributes at any time. Enforcing the 30-day window is a follow-up implementation item (see section 8).

### 3.4 Timestamp Tracking

The pipeline tracks:
- `partner_referrals.signup_at`: When the referred user signed up
- `partner_referrals.converted_at`: When the referred user first paid
- `partner_referrals.churned_at`: When the referred user cancelled

---

## 4. Payout Cycle

### 4.1 Current State (Report Only -- No Automated Payout)

| Aspect | Status |
|--------|--------|
| Monthly report generation | **Implemented** (day 1 at 09:00 BRT via `generate_monthly_revenue_report()`) |
| Pix payout execution | **NOT implemented** (follow-up item) |
| CPF/CNPJ collection | **NOT implemented** (required before payout) |

### 4.2 Monthly Report

The system generates a monthly revenue share report via `generate_monthly_revenue_report()`:
- Runs on day 1 of each month at 09:00 BRT
- Calculates commission for all active partners
- Output: `{year, month, partner_reports[], total_revenue, total_share}`

### 4.3 Planned Payout Cadence

| Item | Planned Value |
|------|---------------|
| Payout frequency | Monthly |
| Payout day | Day 5 of each month |
| Payout method | Pix |
| Pre-requisite | CPF/CNPJ validation |
| Audit trail | Reconciliation between calculated and paid amounts |

---

## 5. Partner Management (Admin)

### 5.1 Partner Statuses

| Status | Meaning |
|--------|---------|
| `active` | Partner is operational, can receive referrals |
| `inactive` | Partner is disabled, no new referrals attributed |
| `pending` | Partner awaiting activation |

### 5.2 Admin Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/admin/partners` | GET | List all partners (with referral counts) |
| `/v1/admin/partners` | POST | Create a new partner |
| `/v1/admin/partners/{id}/referrals` | GET | List referrals for a partner |
| `/v1/admin/partners/{id}/revenue` | GET | Revenue share for a specific month |

All admin endpoints require `is_admin` or `is_master` role. Feature flag `PARTNERS_ENABLED` controls availability (default: true).

### 5.3 Partner Default Values at Creation

| Field | Default | Notes |
|-------|---------|-------|
| `revenue_share_pct` | 20.00% | Can be set per partner |
| `status` | `active` | Auto-set on creation |
| `stripe_coupon_id` | null | Optional, for coupon-based attribution |

### 5.4 Partner Self-Service

Partners can access their own dashboard via `GET /v1/partner/dashboard`:
- Authenticated via their own SmartLic account
- Partner identified by matching `auth.users.email` to `partners.contact_email`
- Returns: partner info, referral list, total monthly share

---

## 6. Database Schema

### `partners`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| id | UUID | gen_random_uuid() | Primary key |
| name | TEXT | | Partner display name |
| slug | TEXT | | Unique URL slug (e.g., "triunfo-legis") |
| contact_email | TEXT | | Partner contact email |
| contact_name | TEXT | null | Optional contact person |
| stripe_coupon_id | TEXT | null | Stripe coupon for attribution |
| revenue_share_pct | NUMERIC(5,2) | 25.00 (migration default), 20.00 (code default) | Commission percentage |
| status | TEXT | 'active' | active, inactive, pending |
| created_at | TIMESTAMPTZ | now() | |

### `partner_referrals`

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| partner_id | UUID | FK to partners.id |
| referred_user_id | UUID | FK to auth.users.id |
| signup_at | TIMESTAMPTZ | When user signed up |
| converted_at | TIMESTAMPTZ | When user first paid |
| churned_at | TIMESTAMPTZ | When user cancelled |
| monthly_revenue | NUMERIC(10,2) | Subscription monthly value |
| revenue_share_amount | NUMERIC(10,2) | Calculated commission amount |

Unique constraint: `(partner_id, referred_user_id)` -- prevents duplicate attribution.

---

## 7. Distinction from User Referral Program

The Partner Program should NOT be confused with the User Referral Program (`backend/routes/referral.py`):

| Aspect | Partner Program | User Referral Program |
|--------|----------------|----------------------|
| Audience | Consultancy firms / companies | End users of SmartLic |
| Incentive | 20% revenue share (recurring) | 1 month free (one-time) |
| Attribution | Partner slug or Stripe coupon | 8-char referral code |
| Tracking | `partner_referrals` table | `referrals` table |
| Payout | Monthly Pix (planned) | Credit applied automatically |
| Admin | Full CRUD + reports | Self-serve only |
| Status | Implemented (payout pending) | Fully implemented |

---

## 8. Implementation Gaps (Follow-Up Items)

The following items from the ADR are documented but NOT yet implemented:

| Item | Description | Current Status |
|------|-------------|----------------|
| CPF/CNPJ collection | Partner identity data for payout | Not collected |
| 30-day attribution expiry | Enforce last-click window in code | Not enforced |
| Pix payout execution | Monthly payout on day 5 | Not implemented |
| Admin payout approval | Audit trail before payout | Not implemented |
| Reconciliation | Match calculated vs paid amounts | Not implemented |

---

## 9. Architecture Flow

```
Signup (with ?partner=slug)
  -> partner_service.attribute_signup_to_partner()
  -> stores profiles.referred_by_partner_id

Checkout (with or without coupon)
  -> checkout.session.completed webhook
  -> partner_service.create_partner_referral()
     -> reads referred_by_partner_id from profile
     -> OR looks up by stripe_coupon_id
  -> creates partner_referrals row

Subscription cancelled
  -> customer.subscription.deleted webhook
  -> partner_service.mark_referral_churned()
  -> stamps churned_at

Monthly report
  -> partner_service.generate_monthly_revenue_report()
  -> sums active referrals, calculates share
```

---

## 10. Key Files

| File | Purpose |
|------|---------|
| `backend/routes/partners.py` | Partner admin + self-service endpoints |
| `backend/services/partner_service.py` | Business logic (attribution, revenue calc, reporting) |
| `backend/schemas/parity.py` | Pydantic response models |
| `backend/webhooks/handlers/checkout.py` | Webhook that triggers `_create_partner_referral_async` |
| `backend/config/features.py` | `PARTNERS_ENABLED` feature flag |
| `supabase/migrations/20260301200000_create_partners.sql` | Partners + referrals tables |
| `frontend/app/admin/partners/` | Frontend admin pages |
