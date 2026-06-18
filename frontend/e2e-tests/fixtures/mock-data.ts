/**
 * Shared Mock Data for Critical Business Flow E2E Tests (Issue #1863)
 *
 * Provides reusable mock data structures and factory functions shared across
 * the 6 critical flow specs. Each scenario may override or extend as needed.
 *
 * Design: ADAPT from existing e2e-tests/helpers/test-utils.ts patterns.
 * Every factory produces deterministic data with overridable fields.
 */

import { Page, Route } from '@playwright/test';

// ---------------------------------------------------------------------------
// Auth mocks
// ---------------------------------------------------------------------------

export interface MockSession {
  access_token: string;
  refresh_token: string;
  expires_at: number;
}

export const MOCK_SESSION: MockSession = {
  access_token: 'mock-critical-flow-access-token',
  refresh_token: 'mock-critical-flow-refresh-token',
  expires_at: Date.now() + 3600_000,
};

export interface MockUser {
  id: string;
  email: string;
  user_metadata: { full_name: string };
  app_metadata: Record<string, unknown>;
}

export function makeMockUser(overrides: Partial<MockUser> = {}): MockUser {
  return {
    id: 'critical-flow-user-id',
    email: 'critical-flow@test.smartlic.tech',
    user_metadata: { full_name: 'Critical Flow Tester' },
    app_metadata: {},
    ...overrides,
  };
}

export function makeTrialUser(overrides: Partial<MockUser> = {}): MockUser {
  return makeMockUser({
    id: 'critical-flow-trial-user',
    email: 'critical-flow-trial@test.smartlic.tech',
    user_metadata: { full_name: 'Trial Critical Flow Tester' },
    ...overrides,
  });
}

export function makePaidUser(overrides: Partial<MockUser> = {}): MockUser {
  return makeMockUser({
    id: 'critical-flow-paid-user',
    email: 'critical-flow-paid@test.smartlic.tech',
    user_metadata: { full_name: 'Paid Critical Flow Tester' },
    ...overrides,
  });
}

// ---------------------------------------------------------------------------
// User / Me response — must match backend UserProfileResponse schema
// ---------------------------------------------------------------------------

/** Backward-compat: accept legacy field names mapped to new schema. */
export interface MeResponse {
  user_id?: string;
  /** @deprecated use user_id */
  id?: string;
  email: string;
  /** @deprecated — not in UserProfileResponse, kept for compat */
  full_name?: string;
  is_admin: boolean;
  plan_id: string;
  plan_name: string;
  /** @deprecated use quota_remaining */
  credits_remaining?: number | null;
  /** @deprecated */
  credits_total?: number;
  quota_remaining?: number | null;
  quota_used?: number;
  /** @deprecated use quota_reset_date */
  reset_date?: string;
  quota_reset_date?: string;
  trial_expires_at?: string;
  subscription_status?: string;
  mfa_enabled?: boolean;
  capabilities?: Record<string, unknown>;
  dunning_phase?: string;
  is_founder?: boolean;
}

export function makeMeResponse(overrides: Partial<MeResponse> = {}): Record<string, unknown> {
  return {
    user_id: overrides.user_id || overrides.id || 'critical-flow-user-id',
    email: overrides.email || 'critical-flow@test.smartlic.tech',
    plan_id: overrides.plan_id || 'free_trial',
    plan_name: overrides.plan_name || 'Avaliacao Gratuita',
    capabilities: overrides.capabilities || { max_history_days: 30, allow_excel: true, allow_pipeline: true },
    quota_used: overrides.quota_used ?? 0,
    quota_remaining: overrides.quota_remaining ?? overrides.credits_remaining ?? 3,
    quota_reset_date: overrides.quota_reset_date || overrides.reset_date || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
    trial_expires_at: overrides.trial_expires_at || new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    subscription_status: overrides.subscription_status || 'trialing',
    is_admin: overrides.is_admin || false,
    dunning_phase: overrides.dunning_phase || 'healthy',
    days_since_failure: null,
    subscription_end_date: null,
    is_founder: overrides.is_founder || false,
    founder_since: null,
    founder_offer_version: null,
    founder_checkout_source: null,
    consulting_discount_pct: null,
    last_login_at: new Date().toISOString(),
    login_count: 1,
    allow_network_analytics: null,
  };
}

// ---------------------------------------------------------------------------
// Plans / Billing mocks
// ---------------------------------------------------------------------------

export interface Plan {
  id: string;
  name: string;
  billing_period?: string;
  price: number;
  features: string[];
}

export function makePlansResponse(overrides: { plans?: Plan[] } = {}) {
  return {
    plans: overrides.plans ?? [
      {
        id: 'smartlic_pro',
        name: 'SmartLic Pro',
        billing_period: 'monthly',
        price: 397,
        features: ['1000 buscas/mes', 'Excel export', 'Pipeline Kanban'],
      },
      {
        id: 'smartlic_pro_semiannual',
        name: 'SmartLic Pro',
        billing_period: 'semiannual',
        price: 357,
        features: ['1000 buscas/mes', 'Excel export', 'Pipeline Kanban'],
      },
      {
        id: 'smartlic_pro_annual',
        name: 'SmartLic Pro',
        billing_period: 'annual',
        price: 297,
        features: ['1000 buscas/mes', 'Excel export', 'Pipeline Kanban'],
      },
    ],
  };
}

export function makeCheckoutResponse(overrides: { checkout_url?: string } = {}) {
  return {
    checkout_url: overrides.checkout_url ?? 'https://checkout.stripe.com/critical-flow-test-session',
  };
}

// ---------------------------------------------------------------------------
// Search / Results mocks
// ---------------------------------------------------------------------------

export interface SearchResult {
  search_id: string;
  download_id: string | null;
  total_raw: number;
  total_filtrado: number;
  resumo: {
    resumo_executivo: string;
    total_oportunidades: number;
    valor_total: number;
    destaques: string[];
    distribuicao_uf: Record<string, number>;
    alerta_urgencia: string | null;
  };
  licitacoes?: Array<{
    id: string;
    titulo: string;
    orgao: string;
    uf: string;
    valor_estimado: number;
    data_abertura: string;
    modalidade: string;
  }>;
  excel_available?: boolean;
  download_url?: string;
}

export function makeSearchResult(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    search_id: 'critical-flow-search-id',
    download_id: 'critical-flow-download-id',
    total_raw: 125,
    total_filtrado: 15,
    resumo: {
      resumo_executivo:
        'Resumo Executivo: Encontradas 15 licitacoes de uniformes em SC e PR, totalizando R$ 750.000,00. As oportunidades incluem uniformes escolares, fardamento militar e roupas profissionais.',
      total_oportunidades: 15,
      valor_total: 750000,
      destaques: [
        'Destaque para licitacao de uniformes escolares em Curitiba no valor de R$ 120.000,00',
        'Oportunidade de fardamento militar em Florianopolis com prazo de entrega de 45 dias',
      ],
      distribuicao_uf: { SC: 8, PR: 7 },
      alerta_urgencia: null,
    },
    licitacoes: [
      {
        id: 'lic-1',
        titulo: 'Pregao Eletronico 001/2026 - Uniformes Escolares',
        orgao: 'Prefeitura de Curitiba',
        uf: 'PR',
        valor_estimado: 120000,
        data_abertura: new Date(Date.now() + 5 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
        modalidade: 'Pregao Eletronico',
      },
      {
        id: 'lic-2',
        titulo: 'Concorrencia 005/2026 - Fardamento Militar',
        orgao: 'Governo do Estado de SC',
        uf: 'SC',
        valor_estimado: 85000,
        data_abertura: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10),
        modalidade: 'Concorrencia',
      },
    ],
    excel_available: true,
    download_url: '/api/download/critical-flow-download-id',
    ...overrides,
  };
}

/**
 * Build a sequence of SSE events for the progress stream.
 */
export function buildSSEEvents(searchId: string) {
  return [
    { stage: 'connecting', progress: 3, message: 'Conectando aos portais...', detail: {} },
    { stage: 'fetching', progress: 25, message: 'Buscando em SC...', detail: { uf_index: 1, uf_total: 2 } },
    { stage: 'fetching', progress: 50, message: 'Buscando em PR...', detail: { uf_index: 2, uf_total: 2 } },
    { stage: 'filtering', progress: 65, message: 'Filtrando resultados...', detail: {} },
    { stage: 'llm', progress: 80, message: 'Gerando resumo executivo...', detail: {} },
    { stage: 'excel', progress: 95, message: 'Preparando Excel...', detail: {} },
    {
      stage: 'search_complete', progress: 100, message: 'Busca concluida', detail: {
        has_results: true, search_id: searchId, total_results: 15, results_ready: true,
        results_url: `/v1/search/${searchId}/results`, is_partial: false,
      },
    },
  ];
}

// ---------------------------------------------------------------------------
// Pipeline mocks
// ---------------------------------------------------------------------------

export interface PipelineItem {
  id: string;
  title: string;
  value: number;
  stage: 'prospecting' | 'qualified' | 'proposal' | 'won' | 'lost';
  uf: string;
  deadline: string;
  notes: string;
  created_at: string;
}

export interface PipelineResponse {
  items: PipelineItem[];
  total: number;
}

const PIPELINE_STAGES: PipelineItem['stage'][] = ['prospecting', 'qualified', 'proposal', 'won', 'lost'];

export function makePipelineItem(overrides: Partial<PipelineItem> = {}): PipelineItem {
  return {
    id: `pipe-item-${Date.now()}`,
    title: 'Pregao 001/2026 - Uniformes Escolares',
    value: 120000,
    stage: 'prospecting',
    uf: 'SC',
    deadline: new Date(Date.now() + 15 * 24 * 60 * 60 * 1000).toISOString(),
    notes: '',
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

export function makePipelineResponse(count: number = 3): PipelineResponse {
  const items: PipelineItem[] = [
    makePipelineItem({
      id: 'pipe-1', title: 'Uniformes Escolares - Prefeitura de Curitiba', value: 120000,
      stage: 'prospecting', uf: 'PR', notes: '',
    }),
    makePipelineItem({
      id: 'pipe-2', title: 'Fardamento Militar - Governo SC', value: 85000,
      stage: 'qualified', uf: 'SC', notes: 'Documentacao em andamento',
    }),
    makePipelineItem({
      id: 'pipe-3', title: 'Equipamentos TI - Secretaria Educacao', value: 350000,
      stage: 'proposal', uf: 'RS', notes: 'Proposta sendo elaborada',
    }),
  ].slice(0, count);

  return { items, total: items.length };
}

// ---------------------------------------------------------------------------
// MFA mocks
// ---------------------------------------------------------------------------

export interface MFASetupResponse {
  secret: string;
  qr_code_url: string;
  recovery_codes: string[];
}

export function makeMFASetupResponse(): MFASetupResponse {
  return {
    secret: 'JBSWY3DPEHPK3PXP',
    qr_code_url: 'otpauth://totp/SmartLic:test@smartlic.tech?secret=JBSWY3DPEHPK3PXP&issuer=SmartLic',
    recovery_codes: ['RECOVERY-AAAA-BBBB', 'RECOVERY-CCCC-DDDD', 'RECOVERY-EEEE-FFFF'],
  };
}

// ---------------------------------------------------------------------------
// Trial mock
// ---------------------------------------------------------------------------

export interface TrialStatusResponse {
  plan_id: string;
  plan_name: string;
  trial_expires_at: string;
  is_expired: boolean;
  days_remaining: number;
  subscription_status: string;
}

export function makeTrialStatusResponse(
  daysRemaining: number = 7,
  status: string = 'trialing'
): TrialStatusResponse {
  const expiresAt = new Date(Date.now() + daysRemaining * 24 * 60 * 60 * 1000).toISOString();
  return {
    plan_id: 'free_trial',
    plan_name: 'Avaliacao Gratuita',
    trial_expires_at: expiresAt,
    is_expired: daysRemaining <= 0,
    days_remaining: Math.max(0, daysRemaining),
    subscription_status: status,
  };
}

// ---------------------------------------------------------------------------
// Setup helpers
// ---------------------------------------------------------------------------

/**
 * Set up auth mocking via addInitScript — injects a fake Supabase auth session
 * into localStorage before the page loads. Consistent with existing test-utils.ts
 * pattern from helpers/test-utils.ts.
 */
export async function setupAuthMock(
  page: Page,
  user: MockUser = makeMockUser(),
  session: MockSession = MOCK_SESSION
): Promise<void> {
  await page.addInitScript(
    (args: { user: MockUser; session: MockSession }) => {
      const authKey = 'sb-localhost-auth-token';
      const authData = {
        access_token: args.session.access_token,
        refresh_token: args.session.refresh_token,
        expires_at: args.session.expires_at,
        user: args.user,
      };
      localStorage.setItem(authKey, JSON.stringify(authData));
      localStorage.setItem('auth-user', JSON.stringify(args.user));
      localStorage.setItem('auth-session', JSON.stringify(args.session));
    },
    { user, session }
  );
}

/**
 * Mock the /me endpoint with custom data.
 * All specs call this to set the logged-in user profile and plan state.
 */
export async function mockMeEndpoint(page: Page, data: Partial<MeResponse> = {}): Promise<void> {
  const body = makeMeResponse(data);
  await page.route('**/me', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
  });
}

/**
 * Clear all client-side state (localStorage, sessionStorage, cookies).
 * Safe to call even if no page has been navigated.
 */
export async function cleanupTestState(page: Page): Promise<void> {
  try {
    await page.evaluate(() => {
      try { localStorage.clear(); } catch { /* ignore */ }
      try { sessionStorage.clear(); } catch { /* ignore */ }
    });
  } catch {
    // Page may not be loaded yet — skip gracefully
  }
  try {
    await page.context().clearCookies();
  } catch {
    // Context may not support cookies
  }
}
