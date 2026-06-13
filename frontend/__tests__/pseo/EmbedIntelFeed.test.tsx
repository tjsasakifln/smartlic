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

// Mock IntersectionObserver — plain class survives jest.config.js resetMocks/restoreMocks.
// Cannot use jest.fn() because resetMocks clears its implementation, causing
// `new IntersectionObserver(cb)` to return an object without `observe`.
//
// Strategy: store the latest callback in a module-level variable.
// mockIntersectionCallback.mock.calls[0] would be empty because the mock
// is never *invoked* — only its .mockImplementation() setter is used.
// jest.clearAllMocks() in beforeEach clears mockImplementation, so we
// stash the callback in a plain variable that survives clearAllMocks.
let storedCallback: IntersectionObserverCallback | null = null;
const mockObserve = jest.fn();
const mockDisconnect = jest.fn();

beforeAll(() => {
  class TestIntersectionObserver {
    observe = mockObserve;
    unobserve = jest.fn();
    disconnect = mockDisconnect;
    takeRecords = jest.fn().mockReturnValue([]);
    root = null;
    rootMargin = "";
    thresholds = [];
    constructor(callback: IntersectionObserverCallback) {
      storedCallback = callback;
    }
  }
  Object.defineProperty(global, 'IntersectionObserver', {
    value: TestIntersectionObserver as unknown as typeof IntersectionObserver,
    writable: true,
    configurable: true,
  });
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

    // Simulate intersection — callback was stored in module-level variable
    if (storedCallback) {
      storedCallback([{ isIntersecting: true }] as IntersectionObserverEntry[]);
    }

    await waitFor(() => {
      expect(screen.getByText(/Mercado de Engenharia/)).toBeInTheDocument();
    });

    expect(screen.getByText("45 novos contratos este mês")).toBeInTheDocument();
  });

  it("falls back to static data on API failure", async () => {
    jest.spyOn(global, "fetch").mockRejectedValueOnce(new Error("Network error"));

    render(<EmbedIntelFeed sector="engenharia" />);

    // Simulate intersection — callback was stored in module-level variable
    if (storedCallback) {
      storedCallback([{ isIntersecting: true }] as IntersectionObserverEntry[]);
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
