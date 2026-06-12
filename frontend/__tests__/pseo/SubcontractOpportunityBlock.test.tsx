/**
 * Tests for SubcontractOpportunityBlock — SUBINTEL-022 (#1678)
 */
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SubcontractOpportunityBlock } from "@/components/pseo/SubcontractOpportunityBlock";

const MOCK_RESPONSE = {
  bid_id: "test-bid-123",
  bid_value: 3200000.0,
  bid_sector: "engenharia",
  subcontract_potential_score: 0.85,
  reasons: [
    { reason: "Valor acima de R$1M sugere necessidade de subcontratacao", weight: 0.3 },
    { reason: "Setor de engenharia tem alta taxa de subcontratacao", weight: 0.2 },
  ],
  historical_suppliers: [
    {
      cnpj: "12345678000199",
      razao_social: "Construtora X Ltda",
      similar_contracts_count: 7,
      total_value: 18500000.0,
      avg_value: 2642857.14,
      last_contract_year: 2026,
      match_reason: "Fornecedor historico do mesmo orgao",
    },
  ],
  disclaimer: "Analise estimada com base em contratos publicos historicos.",
  generated_at: "2026-06-12T00:00:00Z",
};

function mockFetch(data: object | null, status = 200) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  } as Response);
}

beforeEach(() => {
  jest.clearAllMocks();
  global.IntersectionObserver = jest.fn().mockImplementation((callback) => {
    callback([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);
    return { observe: jest.fn(), disconnect: jest.fn(), unobserve: jest.fn(), root: null, rootMargin: "", thresholds: [], takeRecords: () => [] };
  });
});

describe("SubcontractOpportunityBlock", () => {
  it("renders loading skeleton initially", () => {
    global.fetch = jest.fn().mockReturnValue(new Promise(() => {}));
    render(<SubcontractOpportunityBlock bidId="test-bid-123" sector="engenharia" />);
    expect(screen.getByText("Potencial de Subcontratacao")).toBeInTheDocument();
  });

  it("shows score and reasons after successful API fetch", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<SubcontractOpportunityBlock bidId="test-bid-123" sector="engenharia" />);
    await waitFor(() => {
      expect(screen.getByText("85%")).toBeInTheDocument();
      expect(screen.getByText(/Valor acima de R\$1M/)).toBeInTheDocument();
    });
  });

  it("displays historical suppliers", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<SubcontractOpportunityBlock bidId="test-bid-123" sector="engenharia" />);
    await waitFor(() => {
      expect(screen.getByText("Construtora X Ltda")).toBeInTheDocument();
      expect(screen.getByText(/7 contratos similares/)).toBeInTheDocument();
    });
  });

  it("shows CTA when gate is closed (403)", async () => {
    mockFetch(null, 403);
    render(<SubcontractOpportunityBlock bidId="test-bid-123" sector="engenharia" />);
    await waitFor(() => {
      expect(screen.getByText(/SmartLic Insight/)).toBeInTheDocument();
      expect(screen.getByText(/Desbloquear/)).toBeInTheDocument();
    });
  });

  it("falls back to static content on API error (ISR-safe)", async () => {
    mockFetch(null, 500);
    render(<SubcontractOpportunityBlock bidId="test-bid-123" sector="engenharia" />);
    await waitFor(() => {
      expect(screen.getByText(/Dados indisponiveis/)).toBeInTheDocument();
    });
  });

  it("has data attribute", async () => {
    mockFetch(MOCK_RESPONSE);
    render(<SubcontractOpportunityBlock bidId="test-bid-123" sector="engenharia" />);
    await waitFor(() => {
      expect(document.querySelector("[data-subcontract-opportunity-block]")).toBeInTheDocument();
    });
  });
});
