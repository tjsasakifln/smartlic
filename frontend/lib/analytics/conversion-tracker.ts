/**
 * CONV-009 (#1318): Typed conversion analytics event schema — 4 layers.
 *
 * Defines typed tracking functions for the full conversion funnel:
 *   Layer 1 — Engagement (scroll, time-on-page, insight cards, internal search)
 *   Layer 2 — Intent (CTA view/click, preview unlock, WhatsApp, demo)
 *   Layer 3 — Conversion (signup, checkout, report purchase, alert subscription)
 *   Layer 4 — Revenue (revenue_event with attribution)
 *
 * All functions respect LGPD cookie consent (same gate as analytics-events.ts).
 * All functions are SSR-safe: they return early when window is unavailable.
 * All functions never throw — errors are swallowed silently.
 *
 * Import pattern:
 *   import { trackPageScroll } from '@/lib/analytics/conversion-tracker';
 */

import mixpanel from 'mixpanel-browser';
import { getCookieConsent } from '@/app/components/CookieConsentBanner';

// ---------------------------------------------------------------------------
// Shared context — every event carries these when available
// ---------------------------------------------------------------------------

export interface ConversionContext {
  /** Template/section name, e.g. 'fornecedor_page', 'cnpj_page' */
  source_template?: string;
  /** Entity being viewed (CNPJ, slug, edital ID, etc.) */
  entity_id?: string;
  /** Sector slug, e.g. 'pavimentacao-asfaltica' */
  setor?: string;
  /** Two-letter UF code, e.g. 'SC' */
  uf?: string;
  /** Intent cluster for attribution, e.g. 'fornecedor', 'orgao' */
  intent_cluster?: string;
  /** Page URL for context */
  page_url?: string;
  /** Referrer URL for attribution */
  referrer?: string;
  /** Allow extra properties for compatibility with Record<string, unknown> */
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Layer 1 — Engagement
// ---------------------------------------------------------------------------

export type ScrollDepth = 25 | 50 | 75 | 100;

export interface PageScrollEvent extends ConversionContext {
  depth: ScrollDepth;
  /** Total document height in pixels */
  page_height?: number;
  /** Viewport height in pixels */
  viewport_height?: number;
}

export interface InsightCardEvent extends ConversionContext {
  /** Card identifier or index (e.g. 'card-0', 'card-1') */
  card_id: string;
  /** Card type, e.g. 'relevance', 'viability', 'summary' */
  card_type?: string;
}

export interface InternalSearchEvent extends ConversionContext {
  /** Search query string */
  query: string;
  /** Number of results returned */
  result_count?: number;
  /** For result_click — clicked result index */
  result_index?: number;
  /** For result_click — the result identifier */
  result_id?: string;
}

export interface TimeOnPageEvent extends ConversionContext {
  /** Seconds elapsed since page load */
  seconds: number;
}

// ---------------------------------------------------------------------------
// Layer 2 — Intent
// ---------------------------------------------------------------------------

export interface CTAEvent extends ConversionContext {
  /** CTA identifier, e.g. 'hero-cta', 'sticky-trial', 'inline-intel' */
  cta_id: string;
  /** Position on page, e.g. 'hero', 'sidebar', 'footer', 'inline' */
  cta_position: string;
  /** CTA variant, e.g. 'primary', 'secondary', 'ghost' */
  cta_variant?: string;
  /** Destination URL or route */
  cta_destination?: string;
  /** CTA text or label */
  cta_label?: string;
}

export interface PreviewUnlockEvent extends ConversionContext {
  /** Type of preview gate, e.g. 'free_trial', 'signup' */
  gate_type: string;
  /** Which preview was attempted, e.g. 'edital_list', 'report_preview' */
  preview_id: string;
  /** Whether the attempt succeeded */
  unlocked: boolean;
}

export interface WhatsAppClickEvent extends ConversionContext {
  /** Origin section of the page */
  origin: string;
  /** WhatsApp number or link used */
  number?: string;
}

export interface DemoRequestEvent extends ConversionContext {
  /** Form step: 'start' or 'submit' */
  step: 'start' | 'submit';
  /** For submit — company name if provided */
  company_name?: string;
  /** For submit — contact email if provided */
  email?: string;
}

// ---------------------------------------------------------------------------
// Layer 3 — Conversion
// ---------------------------------------------------------------------------

export interface SignupEvent extends ConversionContext {
  /** Signup method, e.g. 'email', 'google' */
  method?: string;
  /** For error — error message or code */
  error?: string;
  /** UTM source for attribution */
  utm_source?: string;
  /** UTM campaign for attribution */
  utm_campaign?: string;
}

export interface CheckoutEvent extends ConversionContext {
  /** Checkout ID or session reference */
  checkout_id?: string;
  /** Plan or product being purchased */
  plan?: string;
  /** Price in BRL cents */
  amount_cents?: number;
  /** Billing interval, e.g. 'month', 'year' */
  interval?: string;
  /** For abandoned — reason if known */
  abandon_reason?: string;
}

export interface ReportPurchaseEvent extends ConversionContext {
  /** Report type, e.g. 'intel_report', 'viability_report' */
  report_type: string;
  /** Session or report ID */
  session_id?: string;
  /** Purchase price in BRL cents */
  amount_cents?: number;
}

export interface AlertSubscriptionEvent extends ConversionContext {
  /** Alert type, e.g. 'setor', 'fornecedor', 'orgao', 'keyword' */
  alert_type: string;
  /** Alert target entity identifier */
  alert_target?: string;
}

// ---------------------------------------------------------------------------
// Layer 4 — Revenue
// ---------------------------------------------------------------------------

export type RevenueEventType =
  | 'microtransaction'
  | 'subscription_new'
  | 'subscription_renewal'
  | 'subscription_upgrade';

export interface RevenueEventPayload extends ConversionContext {
  /** Revenue event subtype */
  revenue_type: RevenueEventType;
  /** Revenue amount in BRL cents */
  amount_cents: number;
  /** Currency code (default: 'BRL') */
  currency?: string;
  /** Product or plan name */
  product?: string;
  /** Template/slug attribution for revenue-by-template analysis */
  template?: string;
  /** Intent cluster attribution */
  intent_cluster?: string;
  /** GSC query origin when available via referrer */
  query_origin?: string;
  /** UTM source attribution */
  utm_source?: string;
  /** UTM campaign attribution */
  utm_campaign?: string;
  /** Transaction or invoice ID */
  transaction_id?: string;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function isTrackingEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  if (!process.env.NEXT_PUBLIC_MIXPANEL_TOKEN) return false;
  const consent = getCookieConsent();
  return consent?.analytics === true;
}

function safeTrack(eventName: string, properties: Record<string, unknown>): void {
  if (!isTrackingEnabled()) return;
  try {
    mixpanel.track(eventName, {
      ...properties,
      timestamp: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'development',
    });
  } catch {
    // Mixpanel not initialized — swallow silently
  }
}

// =========================================================================
// Layer 1 — Engagement
// =========================================================================

/**
 * Track page scroll depth milestone (25%, 50%, 75%, 100%).
 * Should fire at most once per threshold per page load.
 */
export function trackPageScroll(event: PageScrollEvent): void {
  safeTrack(`page_scroll_${event.depth}`, event);
}

/**
 * Track when an insight card is viewed (displayed on screen).
 */
export function trackInsightCardView(event: InsightCardEvent): void {
  safeTrack('insight_card_view', event);
}

/**
 * Track when an insight card is clicked.
 */
export function trackInsightCardClick(event: InsightCardEvent): void {
  safeTrack('insight_card_click', event);
}

/**
 * Track an internal search query performed by the user.
 */
export function trackInternalSearchQuery(event: InternalSearchEvent): void {
  safeTrack('internal_search_query', event);
}

/**
 * Track when user clicks an internal search result.
 */
export function trackInternalSearchResultClick(event: InternalSearchEvent): void {
  safeTrack('internal_search_result_click', event);
}

/**
 * Track time-on-page milestone (30s, 60s, 120s).
 * Should fire at most once per threshold per page load.
 */
export function trackTimeOnPage(event: TimeOnPageEvent): void {
  safeTrack(`time_on_page_${event.seconds}s`, event);
}

// =========================================================================
// Layer 2 — Intent
// =========================================================================

/**
 * Track when a CTA becomes visible in the viewport.
 */
export function trackCTAView(event: CTAEvent): void {
  safeTrack('cta_view', event);
}

/**
 * Track when a CTA is clicked.
 */
export function trackCTAClick(event: CTAEvent): void {
  safeTrack('cta_click', event);
}

/**
 * Track a preview unlock attempt (e.g. clicking "Ver 3 editais gratis").
 */
export function trackPreviewUnlockAttempt(event: PreviewUnlockEvent): void {
  safeTrack('preview_unlock_attempt', event);
}

/**
 * Track a WhatsApp click.
 */
export function trackWhatsAppClick(event: WhatsAppClickEvent): void {
  safeTrack('whatsapp_click', event);
}

/**
 * Track demo request start or submit.
 */
export function trackDemoRequestStart(event: ConversionContext): void {
  safeTrack('demo_request_start', event);
}

/**
 * Track demo request submission.
 */
export function trackDemoRequestSubmit(event: ConversionContext): void {
  safeTrack('demo_request_submit', event);
}

// =========================================================================
// Layer 3 — Conversion
// =========================================================================

/**
 * Track signup flow start.
 */
export function trackSignupStart(event: SignupEvent): void {
  const { error: _, ...props } = event;
  safeTrack('signup_start', props);
}

/**
 * Track successful signup completion.
 */
export function trackSignupComplete(event: SignupEvent): void {
  const { error: _, ...props } = event;
  safeTrack('signup_complete', props);
}

/**
 * Track signup error.
 */
export function trackSignupError(event: SignupEvent): void {
  safeTrack('signup_error', event);
}

/**
 * Track checkout flow start with plan and amount.
 */
export function trackCheckoutStart(event: CheckoutEvent): void {
  safeTrack('checkout_start', event);
}

/**
 * Track successful checkout completion.
 */
export function trackCheckoutComplete(event: CheckoutEvent): void {
  safeTrack('checkout_complete', event);
}

/**
 * Track checkout abandonment.
 */
export function trackCheckoutAbandoned(event: CheckoutEvent): void {
  safeTrack('checkout_abandoned', event);
}

/**
 * Track report preview view.
 */
export function trackReportPreviewView(event: ReportPurchaseEvent): void {
  safeTrack('report_preview_view', event);
}

/**
 * Track report purchase start.
 */
export function trackReportPurchaseStart(event: ReportPurchaseEvent): void {
  safeTrack('report_purchase_start', event);
}

/**
 * Track report purchase completion.
 */
export function trackReportPurchaseComplete(event: ReportPurchaseEvent): void {
  safeTrack('report_purchase_complete', event);
}

/**
 * Track alert subscription start.
 */
export function trackAlertSubscriptionStart(event: AlertSubscriptionEvent): void {
  safeTrack('alert_subscription_start', event);
}

/**
 * Track alert subscription completion.
 */
export function trackAlertSubscriptionComplete(event: AlertSubscriptionEvent): void {
  safeTrack('alert_subscription_complete', event);
}

// =========================================================================
// Layer 4 — Revenue
// =========================================================================

/**
 * Track a revenue-generating event with full attribution context.
 *
 * Revenue events carry template, intent_cluster, and query_origin so
 * downstream dashboards can compute:
 *   - Receita por mil impressoes organicas
 *   - Receita por template / intent_cluster
 *   - RPM (revenue per mille) for programmatic pages
 */
export function trackRevenueEvent(event: RevenueEventPayload): void {
  safeTrack('revenue_event', {
    ...event,
    currency: event.currency ?? 'BRL',
  });
}
