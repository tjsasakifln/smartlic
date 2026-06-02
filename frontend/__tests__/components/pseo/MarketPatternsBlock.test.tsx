/**
 * Tests for MarketPatternsBlock — Issue #1288 (NETINT-011)
 *
 * Covers:
 *  - Loading skeleton is shown initially
 *  - Cards render market data from API (média licitações, valor médio, órgãos, sazonalidade)
 *  - Empty state when API returns zeroed data ("Dados de mercado em consolidação")
 *  - Returns null when API call fails (graceful degradation)
 *  - Returns null when data is null
 */

import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { MarketPatternsBlock } from "@/components/pseo/MarketPatternsBlock";

const MOCK_RESPONSE = {
  setor: "engenharia",
  setor_nome: "Engenharia, Projetos e Obras",
  media_licitacoes_mes: 145,
  valor_medio_contratos: 1250000.0,
  top_orgaos: [
    { nome: "Prefeitura Municipal", total_contratos: 45, valor_total: 5200000.0 },
    { nome: "Governo Estadual", total_contratos: 32, valor_total: 8500000.0 },
    { nome: "Departamento de Obras", total_contratos: 28, valor_total: 10200000.0 },
    { nome: "Secretaria de Educação", total_contratos: 18, valor_total: 3800000.0 },
  ],
  sazonalidade: [
    { mes: "Jan", total_publicacoes: 82 },
    { mes: "Fev", total_publicacoes: 71 },
    { mes: "Mar", total_publicacoes: 95 },
    { mes: "Abr", total_publicacoes: 65 },
    { mes: "Mai", total_publicacoes: 58 },
    { mes: "Jun", total_publicacoes: 48 },
  ],
  total_empresas_entrantes: 35,
  tendencia_desconto: {
    desconto_medio_pct: 18,
    variacao_anual_pct: -5,
  },
  last_updated: "2026-06-01T00:00:00Z",
};

const EMPTY_RESPONSE = {
  setor: "engenharia",
  setor_nome: "Engenharia, Projetos e Obras",
  media_licitacoes_mes: 0,
  valor_medio_contratos: 0,
  top_orgaos: [],
  sazonalidade: [],
  total_empresas_entrantes: 0,
  tendencia_desconto: {
    desconto_medio_pct: 0,
    variacao_anual_pct: 0,
  },
  last_updated: "2026-06-01T00:00:00Z",
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
});

describe("MarketPatternsBlock", () => {
  const defaultProps = {
    setor: "engenharia",
  };

  it("renders loading skeleton initially", () => {
    // Never resolve the fetch to keep loading state
    global.fetch = jest.fn().mockImplementation(() => new Promise(() => {}));
    const { container } = render(<MarketPatternsBlock {...defaultProps} />);

    // Skeleton should have animate-pulse elements
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders market data cards after data loads", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<MarketPatternsBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Padrões de Mercado")).toBeInTheDocument();
    });

    // Check section heading
    expect(
      screen.getByText("Inteligência agregada para Engenharia, Projetos e Obras")
    ).toBeInTheDocument();

    // Check media licitacoes/mes
    expect(screen.getByText("Média de licitações/mês")).toBeInTheDocument();
    expect(screen.getByText("145")).toBeInTheDocument();

    // Check valor medio
    expect(screen.getByText("Valor médio dos contratos")).toBeInTheDocument();
  });

  it("renders top orgaos list", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<MarketPatternsBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Principais órgãos compradores")).toBeInTheDocument();
    });

    expect(screen.getByText("Prefeitura Municipal")).toBeInTheDocument();
    expect(screen.getByText("Governo Estadual")).toBeInTheDocument();
    expect(screen.getByText("Departamento de Obras")).toBeInTheDocument();
  });

  it("renders seasonality section", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<MarketPatternsBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Sazonalidade (últimos 6 meses)")).toBeInTheDocument();
    });

    // Month labels should appear
    expect(screen.getByText("Jan")).toBeInTheDocument();
    expect(screen.getByText("Mar")).toBeInTheDocument();
    expect(screen.getByText("Jun")).toBeInTheDocument();
  });

  it("shows consolidation message when API returns zeroed data", async () => {
    mockFetch(EMPTY_RESPONSE);
    render(<MarketPatternsBlock {...defaultProps} />);

    // Wait for consolidation message to appear after API resolves
    await waitFor(() => {
      expect(
        screen.getByText(/Dados de mercado em consolidação/i)
      ).toBeInTheDocument();
    });
  });

  it("returns null when API call fails", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("Network error"));
    const { container } = render(<MarketPatternsBlock {...defaultProps} />);

    // Wait for fetch to be called, then for error state to resolve
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    // Now wait for the component to re-render after error
    await waitFor(() => {
      const heading = screen.queryByText("Padrões de Mercado");
      expect(heading).not.toBeInTheDocument();
    });

    // Container should be empty (null render)
    expect(container.firstChild).toBeNull();
  });

  it("returns null when data is null", async () => {
    mockFetch(null as unknown as object);
    const { container } = render(<MarketPatternsBlock {...defaultProps} />);

    // Wait for fetch to be called
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    // After fetch resolves with null, data state stays null → component renders null
    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it("requires setor parameter", () => {
    mockFetch(MOCK_RESPONSE);
    const { container } = render(<MarketPatternsBlock setor="informatica" />);
    // Should render loading skeleton (not crash)
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("uses correct API URL with setor parameter", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<MarketPatternsBlock {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByText("Padrões de Mercado")).toBeInTheDocument();
    });

    expect(global.fetch).toHaveBeenCalledWith(
      "/api/pseo/market-patterns?setor=engenharia"
    );
  });
});
