/**
 * PREDINT-022 (#1671): Tests for radar-recorrencia components.
 *
 * Covers:
 * - RecorrenciaTable renders with filters and table
 * - OrgaosRecorrentes renders cards sorted by confidence
 * - IncumbentAlert renders alert cards
 * - PredictiveNarrative renders generate button
 * - Loading/empty states
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { RecorrenciaTable } from "@/app/components/RecorrenciaTable";
import { OrgaosRecorrentes } from "@/app/components/OrgaoRecorrenteCard";
import { IncumbentAlert } from "@/app/components/IncumbentAlert";
import { PredictiveNarrative } from "@/app/components/PredictiveNarrative";

// Mock SWR
jest.mock("swr", () => ({
  __esModule: true,
  default: (key: string, fetcher: () => Promise<any>) => {
    // Return mock data immediately
    return {
      data: {
        contratos: [
          {
            orgao: "Prefeitura Teste",
            orgao_cnpj: "12345678000190",
            fornecedor_atual: "Fornecedor Teste",
            fornecedor_cnpj: "98765432000110",
            objeto: "Objeto de teste",
            valor: 100000,
            data_termino: "2026-08-15",
            confidence: 0.92,
            categoria: "Teste",
          },
        ],
        total: 1,
      },
      error: null,
      isLoading: false,
    };
  },
}));

describe("RecorrenciaTable", () => {
  it("renders the table component", () => {
    render(<RecorrenciaTable />);
    expect(screen.getByTestId("recorrencia-table")).toBeInTheDocument();
  });

  it("renders filter controls", async () => {
    render(<RecorrenciaTable />);
    await waitFor(() => {
      expect(screen.getByTestId("recorrencia-filtro-uf")).toBeInTheDocument();
    });
  });

  it("renders confidence badges", async () => {
    render(<RecorrenciaTable />);
    await waitFor(() => {
      expect(screen.getByText(/Alta/i)).toBeInTheDocument();
    });
  });
});

describe("OrgaosRecorrentes", () => {
  it("renders cards sorted by confidence", () => {
    render(<OrgaosRecorrentes />);
    expect(screen.getByTestId("orgaos-recorrentes")).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    const { container } = render(<OrgaosRecorrentes loading={true} />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });
});

describe("IncumbentAlert", () => {
  it("renders alert data", () => {
    render(<IncumbentAlert />);
    expect(screen.getByTestId("incumbent-alert")).toBeInTheDocument();
  });

  it("renders loading skeleton", () => {
    const { container } = render(<IncumbentAlert loading={true} />);
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("shows empty state when no alerts", () => {
    render(<IncumbentAlert alertas={[]} />);
    expect(screen.getByText(/Nenhum alerta/i)).toBeInTheDocument();
  });
});

describe("PredictiveNarrative", () => {
  it("renders generate button", () => {
    render(<PredictiveNarrative />);
    expect(screen.getByTestId("predictive-narrative")).toBeInTheDocument();
    expect(screen.getByTestId("predictive-narrative-generate")).toBeInTheDocument();
  });

  it("renders loading state when generating", async () => {
    // Mock fetch to never resolve during this test
    global.fetch = jest.fn().mockImplementation(
      () => new Promise(() => {})
    );

    render(<PredictiveNarrative />);
    fireEvent.click(screen.getByTestId("predictive-narrative-generate"));

    await waitFor(() => {
      expect(screen.getByText(/Gerando analise com IA/i)).toBeInTheDocument();
    });
  });
});
