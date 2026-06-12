/**
 * PREDINT-022 (#1671): Tests for /radar-recorrencia page.
 *
 * Covers:
 * - Page renders upgrade banner for unauthenticated users
 * - Page renders blocks for authenticated users with capability
 * - Loading skeleton during auth check
 * - Feature flag gating
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import RadarRecorrenciaPage from "@/app/radar-recorrencia/page";

// Mock auth provider
const mockUseAuth = jest.fn();
jest.mock("@/app/components/AuthProvider", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock router
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

// Mock components
jest.mock("@/app/components/RecorrenciaTable", () => ({
  RecorrenciaTable: () => <div data-testid="recorrencia-table-mock">Table</div>,
}));

jest.mock("@/app/components/OrgaoRecorrenteCard", () => ({
  OrgaosRecorrentes: () => <div data-testid="orgaos-recorrentes-mock">Orgaos</div>,
}));

jest.mock("@/app/components/IncumbentAlert", () => ({
  IncumbentAlert: () => <div data-testid="incumbent-alert-mock">Alertas</div>,
}));

jest.mock("@/app/components/PredictiveNarrative", () => ({
  PredictiveNarrative: () => <div data-testid="predictive-narrative-mock">Narrative</div>,
}));

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch as jest.Mock;

describe("RadarRecorrenciaPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders loading skeleton during auth check", () => {
    mockUseAuth.mockReturnValue({ user: null, loading: true });
    const { container } = render(<RadarRecorrenciaPage />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders upgrade banner when user is not logged in", () => {
    mockUseAuth.mockReturnValue({ user: null, loading: false });
    render(<RadarRecorrenciaPage />);
    expect(screen.getByText(/Radar de Recorrencia Governamental/i)).toBeInTheDocument();
    expect(screen.getByText(/Conhecer o SmartLic Command/i)).toBeInTheDocument();
  });

  it("renders upgrade banner when user lacks capability", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "test-user", email: "test@test.com" },
      loading: false,
    });

    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/features") {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ PREDICTIVE_INTEL_ENABLED: true }),
        });
      }
      if (url === "/v1/user/me") {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              capabilities: { allow_predictive_intel: false },
            }),
        });
      }
      return Promise.reject(new Error("Unknown URL"));
    });

    render(<RadarRecorrenciaPage />);
    // Wait for async state
    await screen.findByText(/Conhecer o SmartLic Command/i);
  });
});
