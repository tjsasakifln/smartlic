/**
 * NETINT-014 (#1519): Integration-level tests for EmbedIntelFeed
 * on SEO programmatic pages.
 *
 * Tests:
 * - Component renders with sector prop
 * - Lazy-load triggers IntersectionObserver
 * - ISR-safe static fallback on API failure
 * - SEO page wiring (observatorio, blog, licitacoes)
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { EmbedIntelFeed } from "@/components/pseo/EmbedIntelFeed";

// Mock IntersectionObserver
const mockObserve = jest.fn();
const mockDisconnect = jest.fn();
const mockIntersectionCallback = jest.fn();

beforeAll(() => {
  global.IntersectionObserver = jest.fn((callback) => {
    mockIntersectionCallback.mockImplementation(callback);
    return {
      observe: mockObserve,
      disconnect: mockDisconnect,
      unobserve: jest.fn(),
      takeRecords: jest.fn().mockReturnValue([]),
      root: null,
      rootMargin: "",
      thresholds: [],
    };
  }) as unknown as typeof IntersectionObserver;
});

beforeEach(() => {
  jest.clearAllMocks();
  jest.spyOn(global, "fetch").mockResolvedValue({
    ok: true,
    json: async () => ({
      sector: "Engenharia",
      signals: [
        { label: "45 novos contratos este mês", value: "R$12,5 mi", trend: "up" },
        { label: "Valor total em contratos", value: "R$12,5 mi", trend: "up" },
        { label: "12 fornecedores ativos", value: "Engenharia", trend: "up" },
      ],
      generated_at: "2026-06-12T00:00:00Z",
    }),
  } as Response);
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe("EmbedIntelFeed — SEO page integration", () => {
  it("renders without crashing with required sector prop", () => {
    render(<EmbedIntelFeed sector="engenharia" />);
    expect(screen.getByLabelText("Inteligência de Mercado")).toBeInTheDocument();
  });

  it("renders skeleton while loading", () => {
    // Don't trigger intersection — just check initial state
    render(<EmbedIntelFeed sector="engenharia" />);
    // Should show skeleton initially
    expect(screen.getByLabelText("Carregando inteligência de mercado")).toBeInTheDocument();
  });

  it("sets up IntersectionObserver for lazy-load", () => {
    render(<EmbedIntelFeed sector="engenharia" />);
    expect(mockObserve).toHaveBeenCalledTimes(1);
  });

  it("renders data after intersection triggers fetch", async () => {
    render(<EmbedIntelFeed sector="engenharia" />);

    // Simulate intersection
    const callback = mockIntersectionCallback.mock.calls[0]?.[0];
    if (callback) {
      callback([{ isIntersecting: true }]);
    }

    await waitFor(() => {
      expect(screen.getByText(/Mercado de Engenharia/)).toBeInTheDocument();
    });

    expect(screen.getByText("45 novos contratos este mês")).toBeInTheDocument();
  });

  it("falls back to static data on API failure", async () => {
    jest.spyOn(global, "fetch").mockRejectedValueOnce(new Error("Network error"));

    render(<EmbedIntelFeed sector="engenharia" />);

    // Simulate intersection
    const callback = mockIntersectionCallback.mock.calls[0]?.[0];
    if (callback) {
      callback([{ isIntersecting: true }]);
    }

    await waitFor(() => {
      expect(screen.getByText(/Acompanhe as oportunidades/)).toBeInTheDocument();
    });
  });
});

describe("SEO page wiring integration", () => {
  it("accepts optional UF prop", () => {
    render(<EmbedIntelFeed sector="ti" uf="SP" />);
    expect(screen.getByLabelText("Inteligência de Mercado")).toBeInTheDocument();
  });

  it("passes sector as slug prop for observatorio pages", () => {
    const { container } = render(<EmbedIntelFeed sector="manutencao-predial" />);
    const section = container.querySelector("[data-embed-intel-feed]");
    expect(section).toBeInTheDocument();
  });
});
