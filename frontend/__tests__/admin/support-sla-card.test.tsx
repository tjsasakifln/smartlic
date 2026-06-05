/**
 * STORY-353 AC7+AC9: Support SLA card tests for admin dashboard.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import "@testing-library/jest-dom";

function renderWithSWR(ui: React.ReactElement) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      {ui}
    </SWRConfig>
  );
}

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
}));

// Mock next/link
jest.mock("next/link", () => {
  return function MockLink({ children, href }: { children: React.ReactNode; href: string }) {
    return <a href={href}>{children}</a>;
  };
});

// Mock sonner
jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

// Mock plans
jest.mock("../../lib/plans", () => ({
  PLAN_CONFIGS: {
    free_trial: { displayNamePt: "Trial", price: null },
    smartlic_pro: { displayNamePt: "SmartLic Pro", price: "R$397/mes" },
  },
}));

// Mock AuthProvider
const mockSession = {
  access_token: "test-token",
  user: { id: "admin-1", email: "admin@test.com" },
};

jest.mock("../../app/components/AuthProvider", () => ({
  useAuth: () => ({
    session: mockSession,
    loading: false,
    isAdmin: true,
  }),
}));

import AdminPage from "../../app/admin/page";

describe("STORY-353: Support SLA Card", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders SLA card with data", async () => {
    const slaData = {
      avg_response_hours: 4.5,
      pending_count: 2,
      breached_count: 1,
    };

    global.fetch = jest.fn().mockImplementation((url: string) => {
      if (url.includes("/api/admin/support-sla")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(slaData),
        });
      }
      if (url.includes("/api/admin/users")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ users: [], total: 0 }),
        });
      }
      if (url.includes("/api/status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ sources: {}, uptime_pct_30d: 99.9 }),
        });
      }
      if (url.includes("/api/admin/reconciliation")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ runs: [] }),
        });
      }
      if (url.includes("/api/admin/users/segments")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            total_users: 128,
            count_by_state: { anonymous: 5, lead: 18, trial_active: 32 },
            transitions_last_week: [],
            power_users: [],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderWithSWR(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByText("SLA de Suporte")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("4.5h")).toBeInTheDocument();
    });

    expect(screen.getByText("Tempo medio de resposta")).toBeInTheDocument();
    expect(screen.getByText("Aguardando resposta")).toBeInTheDocument();
    expect(screen.getByText(/SLA violado/)).toBeInTheDocument();
  });

  it("renders SLA card with zero state", async () => {
    const slaData = {
      avg_response_hours: 0,
      pending_count: 0,
      breached_count: 0,
    };

    global.fetch = jest.fn().mockImplementation((url: string) => {
      if (url.includes("/api/admin/support-sla")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(slaData),
        });
      }
      if (url.includes("/api/admin/users")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ users: [], total: 0 }),
        });
      }
      if (url.includes("/api/status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ sources: {} }),
        });
      }
      if (url.includes("/api/admin/reconciliation")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ runs: [] }),
        });
      }
      if (url.includes("/api/admin/users/segments")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            total_users: 128,
            count_by_state: { anonymous: 5, lead: 18, trial_active: 32 },
            transitions_last_week: [],
            power_users: [],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderWithSWR(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByText("SLA de Suporte")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(screen.getByText("0h")).toBeInTheDocument();
    });
  });

  it("handles SLA fetch failure gracefully", async () => {
    global.fetch = jest.fn().mockImplementation((url: string) => {
      if (url.includes("/api/admin/support-sla")) {
        return Promise.reject(new Error("Network error"));
      }
      if (url.includes("/api/admin/users")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ users: [], total: 0 }),
        });
      }
      if (url.includes("/api/status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ sources: {} }),
        });
      }
      if (url.includes("/api/admin/reconciliation")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ runs: [] }),
        });
      }
      if (url.includes("/api/admin/users/segments")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            total_users: 128,
            count_by_state: { anonymous: 5, lead: 18, trial_active: 32 },
            transitions_last_week: [],
            power_users: [],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderWithSWR(<AdminPage />);

    await waitFor(() => {
      expect(screen.getByText("SLA de Suporte")).toBeInTheDocument();
    });

    // Should show "Dados indisponiveis" when fetch fails
    await waitFor(() => {
      expect(screen.getByText("Dados indisponiveis")).toBeInTheDocument();
    });
  });
});
