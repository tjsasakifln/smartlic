/**
 * FOUNDER-004 (#1417): Tests for /admin/metrics founder dashboard page.
 *
 * Covers:
 * - Admin-only access (non-admin redirect)
 * - Loading state (skeleton)
 * - Error state (retry)
 * - Metric cards rendered with correct values
 * - MRR history chart data
 * - Empty state when no data
 * - Responsive grid structure
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock AuthProvider
const mockUseAuth = jest.fn();
jest.mock("../app/components/AuthProvider", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/admin/metrics",
}));

// Mock next/link
jest.mock("next/link", () => {
  return function MockLink({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) {
    return <a href={href} {...rest}>{children}</a>;
  };
});

// Mock Recharts to avoid SSR/resize observer issues in jsdom
jest.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Line: () => <div data-testid="chart-line" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div data-testid="cartesian-grid" />,
  Tooltip: () => <div data-testid="chart-tooltip" />,
}));

import AdminFounderMetricsPage from "../app/admin/metrics/page";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const MOCK_METRICS = {
  mrr: 15000.0,
  churn_rate_30d: 0.05,
  trial_to_paid_30d: 0.12,
  trial_to_paid_90d: 0.18,
  activation_d7: 0.45,
  retention_d1: 0.72,
  retention_d7: 0.38,
  retention_d30: 0.22,
  arpa: 425.5,
  total_subscribers: 42,
  period_start: "2026-01-01",
  period_end: "2026-06-06",
  mrr_history: [
    { month: "2026-01", mrr: 8000.0, subscriber_count: 22 },
    { month: "2026-02", mrr: 10000.0, subscriber_count: 28 },
    { month: "2026-03", mrr: 12000.0, subscriber_count: 33 },
    { month: "2026-04", mrr: 13500.0, subscriber_count: 38 },
    { month: "2026-05", mrr: 15000.0, subscriber_count: 42 },
  ],
};

describe("AdminFounderMetricsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  // -----------------------------------------------------------------------
  // Auth guards
  // -----------------------------------------------------------------------

  it("shows loading while auth is loading", () => {
    mockUseAuth.mockReturnValue({
      session: null,
      loading: true,
      isAdmin: false,
      isAdminLoading: true,
    });

    render(<AdminFounderMetricsPage />);
    expect(screen.getByText("Carregando...")).toBeInTheDocument();
  });

  it("shows login link when not authenticated", () => {
    mockUseAuth.mockReturnValue({
      session: null,
      loading: false,
      isAdmin: false,
      isAdminLoading: false,
    });

    render(<AdminFounderMetricsPage />);
    expect(screen.getByText("Login necessario")).toBeInTheDocument();
  });

  it("shows access denied for non-admin users", () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: false,
      isAdminLoading: false,
    });

    render(<AdminFounderMetricsPage />);
    expect(screen.getByText("Acesso Restrito")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Loading state
  // -----------------------------------------------------------------------

  it("shows skeleton while fetching data", () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    // Return a promise that never resolves to keep loading state
    global.fetch = jest.fn(() => new Promise(() => {}));

    render(<AdminFounderMetricsPage />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  // -----------------------------------------------------------------------
  // Error state
  // -----------------------------------------------------------------------

  it("shows error message and retry button on fetch failure", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    global.fetch = jest.fn().mockRejectedValue(new Error("Network error"));

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });

    expect(screen.getByText("Tentar novamente")).toBeInTheDocument();
  });

  it("shows error detail from backend response", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({ detail: "Servico temporariamente indisponivel" }),
    });

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Servico temporariamente indisponivel")
      ).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Success state — metric cards
  // -----------------------------------------------------------------------

  it("renders metric cards with correct values", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_METRICS),
    });

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      // MRR
      expect(screen.getByText("MRR")).toBeInTheDocument();
      expect(screen.getByText("R$ 15.000,00")).toBeInTheDocument();
    });

    // Churn
    expect(screen.getByText("Churn (30d)")).toBeInTheDocument();
    expect(screen.getByText("5.0%")).toBeInTheDocument();

    // Trial -> Paid
    expect(screen.getByText("Trial → Paid (30d)")).toBeInTheDocument();
    expect(screen.getByText("12.0%")).toBeInTheDocument();

    // ARPA
    expect(screen.getByText("ARPA")).toBeInTheDocument();
    expect(screen.getByText("R$ 425,50")).toBeInTheDocument();

    // Subscribers
    expect(screen.getByText("Assinantes")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Success state — MRR chart
  // -----------------------------------------------------------------------

  it("renders MRR chart when history data is available", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_METRICS),
    });

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      expect(screen.getByText("Evolucao do MRR")).toBeInTheDocument();
    });

    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
    expect(screen.getByTestId("line-chart")).toBeInTheDocument();
  });

  it("shows empty chart message when no history data", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    const noHistoryMetrics = { ...MOCK_METRICS, mrr_history: [] };

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(noHistoryMetrics),
    });

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Dados de MRR historico indisponiveis")
      ).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Success state — engagement metrics section
  // -----------------------------------------------------------------------

  it("renders engagement metrics section", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_METRICS),
    });

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Metricas de Engajamento")
      ).toBeInTheDocument();
    });

    // Retention D30
    expect(screen.getByText("Retencao D30")).toBeInTheDocument();
    expect(screen.getByText("22.0%")).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Empty state
  // -----------------------------------------------------------------------

  it("renders page header when data loads", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    // Return empty metrics to verify header renders
    const emptyMetrics = {
      mrr: 0, churn_rate_30d: 0, trial_to_paid_30d: 0, trial_to_paid_90d: 0,
      activation_d7: 0, retention_d1: 0, retention_d7: 0, retention_d30: 0,
      arpa: 0, total_subscribers: 0,
      period_start: "2026-01-01", period_end: "2026-06-06",
      mrr_history: [],
    };

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(emptyMetrics),
    });

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      expect(screen.getByText("Metricas Financeiras")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Retry mechanism
  // -----------------------------------------------------------------------

  it("retries fetch when retry button is clicked after error", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    // First call fails
    global.fetch = jest
      .fn()
      .mockRejectedValueOnce(new Error("Network error"))
      // Second call succeeds
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(MOCK_METRICS),
      });

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });

    // Click retry
    fireEvent.click(screen.getByText("Tentar novamente"));

    await waitFor(() => {
      expect(screen.getByText("MRR")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Responsive grid structure
  // -----------------------------------------------------------------------

  it("renders all metric card labels and engagement section", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_METRICS),
    });

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      expect(screen.getByText("Metricas Financeiras")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("MRR")).toBeInTheDocument();
      expect(screen.getByText("ARPA")).toBeInTheDocument();
      expect(screen.getByText("Assinantes")).toBeInTheDocument();
      expect(screen.getByText("Metricas de Engajamento")).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Last refresh timestamp
  // -----------------------------------------------------------------------

  it("shows last refresh timestamp after data loads", async () => {
    mockUseAuth.mockReturnValue({
      session: { access_token: "token" },
      loading: false,
      isAdmin: true,
      isAdminLoading: false,
    });

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_METRICS),
    });

    render(<AdminFounderMetricsPage />);

    await waitFor(() => {
      expect(screen.getByText(/atualizado/)).toBeInTheDocument();
    });
  });
});
