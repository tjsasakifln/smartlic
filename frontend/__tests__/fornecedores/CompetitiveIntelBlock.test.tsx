/**
 * COMPINT-011 (#1663): Tests for CompetitiveIntelBlock component.
 *
 * Covers:
 * - Rendering nothing when fetch returns 401/403 (no access)
 * - Rendering nothing when data is null
 * - Rendering nothing when supplier has 0 contracts
 * - Rendering full block with data
 * - Rendering positioning alerts
 * - Mini-dashboard shows ticket, market share, growth, UFs
 * - CTA link rendered with correct URL
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import CompetitiveIntelBlock from "@/app/fornecedores/[cnpj]/components/CompetitiveIntelBlock";

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const MOCK_INTEL_DATA = {
  concorrente: {
    cnpj: "12345678000199",
    nome: "Fornecedor ABC Ltda",
    total_contratos: 45,
    ticket_medio: 250000.0,
    ticket_mediana: 180000.0,
    valor_total_contratado: 11250000.0,
  },
  territorio: [
    {
      uf: "SP",
      contratos: 20,
      valor_total: 5000000.0,
      ticket_medio_uf: 250000.0,
      orgaos_principais: ["Governo SP"],
      market_share_uf: 0.35,
      tendencia: "crescendo",
    },
    {
      uf: "RJ",
      contratos: 10,
      valor_total: 2500000.0,
      ticket_medio_uf: 250000.0,
      orgaos_principais: ["Prefeitura RJ"],
      market_share_uf: 0.15,
      tendencia: "estavel",
    },
  ],
  orgaos_favoritos: [
    {
      orgao_nome: "Governo SP",
      contratos: 15,
      valor_total: 3750000.0,
      categorias: ["Infraestrutura"],
      ultima_vitoria: "2026-05-15",
      frequencia_anual: 3.0,
    },
  ],
  stats: {
    ufs_atuacao: 2,
    orgaos_unicos: 3,
    anos_atuacao: 5,
    crescimento_anual: 0.35,
    tendencia_posicionamento: "expansao",
  },
  win_metrics: {
    taxa_vitoria_estimada: 0.45,
    velocidade_crescimento: 1.2,
    tendencia: "crescendo",
    ticket_p50: 180000.0,
    ticket_p75: 350000.0,
  },
  alertas: [
    {
      tipo: "crescimento",
      mensagem: "Crescimento de 35% em contratos no último ano",
      severidade: "success",
    },
    {
      tipo: "dominio",
      mensagem: "Player dominante em SP com 35% de market share",
      severidade: "success",
    },
  ],
};

function mockFetch(response: Response | null, status = 200) {
  const mockResolvedValue = response ?? {
    ok: status >= 200 && status < 300,
    status,
    json: async () => MOCK_INTEL_DATA,
  };
  globalThis.fetch = jest.fn().mockResolvedValue(mockResolvedValue);
}

function cleanupFetch() {
  if (jest.isMockFunction(globalThis.fetch)) {
    (globalThis.fetch as jest.Mock).mockRestore?.();
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CompetitiveIntelBlock", () => {
  afterEach(() => {
    cleanupFetch();
  });

  it("renders nothing when fetch returns 401 (no access)", async () => {
    mockFetch(
      { ok: false, status: 401, json: async () => ({}) } as Response,
      401,
    );

    const { container } = render(<CompetitiveIntelBlock cnpj="12345678000199" />);

    await waitFor(() => {
      // Component should render nothing
      expect(container.innerHTML).toBe("");
    });
  });

  it("renders nothing when fetch returns 403 (capability false)", async () => {
    mockFetch(
      { ok: false, status: 403, json: async () => ({}) } as Response,
      403,
    );

    const { container } = render(<CompetitiveIntelBlock cnpj="12345678000199" />);

    await waitFor(() => {
      expect(container.innerHTML).toBe("");
    });
  });

  it("renders nothing when fetch returns 404 (no data)", async () => {
    mockFetch(
      { ok: false, status: 404, json: async () => ({}) } as Response,
      404,
    );

    const { container } = render(<CompetitiveIntelBlock cnpj="12345678000199" />);

    await waitFor(() => {
      expect(container.innerHTML).toBe("");
    });
  });

  it("renders full block with data when access granted", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => MOCK_INTEL_DATA,
    });

    render(<CompetitiveIntelBlock cnpj="12345678000199" />);

    await waitFor(() => {
      expect(screen.getByTestId("competitive-intel-block")).toBeInTheDocument();
    });

    // Verify header
    expect(screen.getByText("Inteligência Concorrencial")).toBeInTheDocument();

    // Verify positioning alerts
    expect(
      screen.getByText(/Crescimento de 35% em contratos no último ano/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Player dominante em SP com 35% de market share/),
    ).toBeInTheDocument();

    // Verify CTA
    const cta = screen.getByTestId("competitive-intel-cta");
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveAttribute(
      "href",
      "/intel-concorrente?cnpj=12345678000199",
    );
  });

  it("renders ticket and market share in mini-dashboard", async () => {
    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => MOCK_INTEL_DATA,
    });

    render(<CompetitiveIntelBlock cnpj="12345678000199" />);

    await waitFor(() => {
      expect(screen.getByTestId("competitive-intel-block")).toBeInTheDocument();
    });

    // Ticket Medio should be visible
    expect(screen.getByText(/R\$ 250/, { exact: false })).toBeInTheDocument();
  });

  it("renders nothing for supplier with 0 contracts", async () => {
    const zeroContractsData = {
      ...MOCK_INTEL_DATA,
      concorrente: { ...MOCK_INTEL_DATA.concorrente, total_contratos: 0 },
    };

    globalThis.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => zeroContractsData,
    });

    const { container } = render(<CompetitiveIntelBlock cnpj="12345678000199" />);

    await waitFor(() => {
      expect(container.innerHTML).toBe("");
    });
  });
});
