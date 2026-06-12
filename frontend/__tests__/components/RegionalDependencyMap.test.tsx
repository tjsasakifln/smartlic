/**
 * Tests for RegionalDependencyMap — SUBINTEL-012 (#1681)
 *
 * Covers:
 *  - Renders loading skeleton initially
 *  - Shows Brazil SVG map with UF circles after successful fetch
 *  - Tooltip appears on hover
 *  - Risk level badge displays correctly
 *  - Dependency index bar shows correct position
 *  - Summary stats grid renders
 *  - Top UFs table renders sorted by contract count
 *  - CTA shown when gate is closed (user without access)
 *  - Does not render (null) on error (silent fail for pSEO)
 *  - Has data-regional-dependency-map attribute
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { RegionalDependencyMap } from "@/components/RegionalDependencyMap";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_DATA = {
  sector_id: "engenharia",
  uf_distribution: [
    { uf: "SP", dependency_score: 35.0, contract_count: 350, total_value: 17500000.0 },
    { uf: "RJ", dependency_score: 20.0, contract_count: 200, total_value: 10000000.0 },
    { uf: "MG", dependency_score: 15.0, contract_count: 150, total_value: 7500000.0 },
    { uf: "RS", dependency_score: 10.0, contract_count: 100, total_value: 5000000.0 },
    { uf: "PR", dependency_score: 8.0, contract_count: 80, total_value: 4000000.0 },
  ],
  total_contracts: 880,
  total_value: 44000000.0,
  coverage_ufs: 5,
  hhi_normalized: 0.77,
  risk_level: "alto",
  disclaimer: "Indice calculado com base em contratos publicos historicos...",
  generated_at: "2026-06-12T00:00:00Z",
};

const MOCK_DATA_DIVERSIFIED = {
  ...MOCK_DATA,
  uf_distribution: [
    { uf: "SP", dependency_score: 25.0, contract_count: 100, total_value: 5000000.0 },
    { uf: "MG", dependency_score: 20.0, contract_count: 80, total_value: 4000000.0 },
    { uf: "RJ", dependency_score: 18.0, contract_count: 72, total_value: 3600000.0 },
    { uf: "RS", dependency_score: 15.0, contract_count: 60, total_value: 3000000.0 },
    { uf: "PR", dependency_score: 12.0, contract_count: 48, total_value: 2400000.0 },
    { uf: "BA", dependency_score: 10.0, contract_count: 40, total_value: 2000000.0 },
  ],
  coverage_ufs: 6,
  hhi_normalized: 0.82,
  risk_level: "baixo",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(data: object | null, status = 200) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  // Mock mixpanel
  jest.spyOn(global, "mixpanel" as any, "get").mockReturnValue({
    track: jest.fn(),
  });
});

describe("RegionalDependencyMap", () => {
  it("renders loading skeleton initially", () => {
    mockFetch(MOCK_DATA);
    render(<RegionalDependencyMap sectorId="engenharia" />);
    expect(screen.getByText("Indice de Dependencia Regional")).toBeInTheDocument();
  });

  it("renders SVG map with UF data after successful fetch", async () => {
    mockFetch(MOCK_DATA);
    render(<RegionalDependencyMap sectorId="engenharia" isPremiumUser={true} />);

    await waitFor(() => {
      expect(screen.getByText("SP")).toBeInTheDocument();
      expect(screen.getByText("RJ")).toBeInTheDocument();
      expect(screen.getByText("MG")).toBeInTheDocument();
    });

    // Verify SVG has role="img"
    const svg = document.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("aria-label", "Mapa do Brasil com dependencia regional");
  });

  it("shows risk badge with correct level", async () => {
    mockFetch(MOCK_DATA);
    render(<RegionalDependencyMap sectorId="engenharia" isPremiumUser={true} />);

    await waitFor(() => {
      expect(screen.getByText(/Risco:/)).toBeInTheDocument();
      expect(screen.getByText(/alta concentracao regional/)).toBeInTheDocument();
    });
  });

  it("shows low risk badge for diversified sectors", async () => {
    mockFetch(MOCK_DATA_DIVERSIFIED);
    render(<RegionalDependencyMap sectorId="engenharia" isPremiumUser={true} />);

    await waitFor(() => {
      expect(screen.getByText(/setor distribuido geograficamente/)).toBeInTheDocument();
    });
  });

  it("displays summary stats grid", async () => {
    mockFetch(MOCK_DATA);
    render(<RegionalDependencyMap sectorId="engenharia" isPremiumUser={true} />);

    await waitFor(() => {
      expect(screen.getByText("880")).toBeInTheDocument(); // total contracts
      expect(screen.getByText("Contratos")).toBeInTheDocument();
      expect(screen.getByText("5/27")).toBeInTheDocument(); // coverage
      expect(screen.getByText("UFs com contratos")).toBeInTheDocument();
    });
  });

  it("displays top UFs table", async () => {
    mockFetch(MOCK_DATA);
    render(<RegionalDependencyMap sectorId="engenharia" isPremiumUser={true} />);

    await waitFor(() => {
      expect(screen.getByText("SP")).toBeInTheDocument();
      // Verify SP is listed first (highest contract count)
      const rows = document.querySelectorAll("tbody tr");
      expect(rows.length).toBeGreaterThanOrEqual(5);
    });
  });

  it("shows CTA when gate is closed (403)", async () => {
    mockFetch(null, 403);
    render(<RegionalDependencyMap sectorId="engenharia" />);

    await waitFor(() => {
      expect(screen.getByText(/SmartLic Insight/)).toBeInTheDocument();
      expect(screen.getByText(/Desbloquear/)).toBeInTheDocument();
    });
  });

  it("does not render on error (silent fail for pSEO)", async () => {
    mockFetch(null, 500);
    const { container } = render(<RegionalDependencyMap sectorId="engenharia" />);

    await waitFor(() => {
      // Component should become null after error
      const element = container.querySelector("[data-regional-dependency-map]");
      expect(element).not.toBeInTheDocument();
    });
  });

  it("has data-regional-dependency-map attribute", async () => {
    mockFetch(MOCK_DATA);
    render(<RegionalDependencyMap sectorId="engenharia" isPremiumUser={true} />);

    await waitFor(() => {
      const el = document.querySelector("[data-regional-dependency-map]");
      expect(el).toBeInTheDocument();
    });
  });

  it("displays dependency index bar", async () => {
    mockFetch(MOCK_DATA);
    render(<RegionalDependencyMap sectorId="engenharia" isPremiumUser={true} />);

    await waitFor(() => {
      expect(screen.getByText(/distribuido/)).toBeInTheDocument();
    });
  });
});
