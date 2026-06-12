/**
 * Tests for EmbedIntelFeed — Issue #1519 (NETINT-014)
 *
 * Covers:
 *  - Renders loading skeleton initially (before IntersectionObserver triggers)
 *  - Lazy-loads via IntersectionObserver when visible
 *  - Shows market signals after successful API fetch
 *  - Falls back to static content on API error
 *  - ISR-safe: does not throw during build/render
 *  - Has data-embed-intel-feed attribute for testing
 */

import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { EmbedIntelFeed } from "@/components/pseo/EmbedIntelFeed";

const MOCK_RESPONSE = {
  sector: "Engenharia",
  signals: [
    { label: "45 novos contratos este mês", value: "R$2,5 mi", trend: "up" },
    { label: "Valor total em contratos", value: "R$2,5 mi", trend: "up" },
    { label: "12 fornecedores ativos", value: "Engenharia", trend: "stable" },
  ],
  generated_at: "2026-06-11T00:00:00Z",
};

const EMPTY_RESPONSE = {
  sector: "Engenharia",
  signals: [],
  generated_at: "2026-06-11T00:00:00Z",
};

function mockFetch(response: object, status = 200) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  } as Response);
}

beforeEach(() => {
  jest.clearAllMocks();
  // Mock IntersectionObserver to always trigger immediately
  const mockObserve = jest.fn();
  const mockDisconnect = jest.fn();
  global.IntersectionObserver = jest.fn().mockImplementation((callback) => {
    // Immediately trigger intersection
    callback([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
    return {
      observe: mockObserve,
      disconnect: mockDisconnect,
      unobserve: jest.fn(),
      root: null,
      rootMargin: "",
      thresholds: [],
      takeRecords: () => [],
    };
  });
});

describe("EmbedIntelFeed", () => {
  const defaultProps = {
    sector: "engenharia",
  };

  it("renders with data-embed-intel-feed attribute", () => {
    // Keep loading state
    global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));
    const { container } = render(<EmbedIntelFeed {...defaultProps} />);
    const section = container.querySelector("[data-embed-intel-feed]");
    expect(section).toBeInTheDocument();
  });

  it("shows market signals after successful fetch", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<EmbedIntelFeed {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Mercado de Engenharia")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(
        screen.getByText("45 novos contratos este mês"),
      ).toBeInTheDocument();
    });

    expect(screen.getByText("Valor total em contratos")).toBeInTheDocument();
    expect(screen.getByText("12 fornecedores ativos")).toBeInTheDocument();
  });

  it("falls back to static content on API error", async () => {
    mockFetch({ error: "Server error" }, 500);
    render(<EmbedIntelFeed sector="engenharia" />);

    await waitFor(() => {
      expect(screen.getByText("Mercado de Engenharia")).toBeInTheDocument();
    });

    // Should show fallback content instead of erroring
    await waitFor(() => {
      expect(
        screen.getByText("Acompanhe as oportunidades"),
      ).toBeInTheDocument();
    });
  });

  it("falls back to static content on network error", async () => {
    global.fetch = jest
      .fn()
      .mockRejectedValue(new Error("Network error"));
    render(<EmbedIntelFeed sector="engenharia" />);

    await waitFor(() => {
      expect(screen.getByText("Mercado de Engenharia")).toBeInTheDocument();
    });

    await waitFor(() => {
      expect(
        screen.getByText("Acompanhe as oportunidades"),
      ).toBeInTheDocument();
    });
  });

  it("renders with UF parameter", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<EmbedIntelFeed sector="engenharia" uf="SP" />);

    await waitFor(() => {
      expect(screen.getByText("Mercado de Engenharia")).toBeInTheDocument();
    });
  });

  it("handles empty signals list gracefully", async () => {
    mockFetch(EMPTY_RESPONSE);
    render(<EmbedIntelFeed {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText("Mercado de Engenharia"),
      ).toBeInTheDocument();
    });

    // Should show consolidation message
    expect(
      screen.getByText("Dados de mercado em consolidação."),
    ).toBeInTheDocument();
  });

  it("ISR-safe: does not throw during render", () => {
    // Simulate what would happen during build (no fetch resolution)
    global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));
    expect(() => render(<EmbedIntelFeed {...defaultProps} />)).not.toThrow();
  });
});
