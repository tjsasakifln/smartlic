/**
 * Tests for SubcontratacaoFornecedorBlock — Issue #1321
 *
 * Covers:
 *  - Renders block with data-testid
 *  - Shows CTA link to /subcontratacao
 *  - Shows loading state initially
 *  - Shows placeholder text when API unavailable
 *  - Hidden when API returns zero contracts
 */

import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SubcontratacaoFornecedorBlock } from "@/app/components/SubcontratacaoFornecedorBlock";

const MOCK_DATA = {
  contratos_subcontratacao: 12,
  total_contratos: 45,
};

const ZERO_DATA = {
  contratos_subcontratacao: 0,
  total_contratos: 5,
};

function mockFetch(response: object | null, status = 200) {
  global.fetch = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => response,
  } as Response);
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("SubcontratacaoFornecedorBlock", () => {
  const defaultProps = {
    cnpj: "12345678000190",
    razaoSocial: "Empresa Exemplo Ltda",
  };

  it("renders with data-testid", () => {
    mockFetch(MOCK_DATA);
    render(<SubcontratacaoFornecedorBlock {...defaultProps} />);
    expect(
      screen.getByTestId("subcontratacao-fornecedor-block")
    ).toBeInTheDocument();
  });

  it("renders CTA link to /subcontratacao", async () => {
    mockFetch(MOCK_DATA);
    render(<SubcontratacaoFornecedorBlock {...defaultProps} />);

    await waitFor(() => {
      const link = screen.getByTestId("subcontratacao-fornecedor-cta");
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", "/subcontratacao");
    });
  });

  it("shows loading state initially", () => {
    // Don't resolve the mock
    global.fetch = jest.fn(() => new Promise(() => {}));
    render(<SubcontratacaoFornecedorBlock {...defaultProps} />);
    expect(
      screen.getByText(/Verificando oportunidades/i)
    ).toBeInTheDocument();
  });

  it("shows placeholder text when API fails", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("Network error"));
    render(<SubcontratacaoFornecedorBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(/frequentemente subcontratam/i)
      ).toBeInTheDocument();
    });
  });

  it("shows nothing when API returns zero contracts", async () => {
    mockFetch(ZERO_DATA);
    const { container } = render(
      <SubcontratacaoFornecedorBlock {...defaultProps} />
    );

    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it("renders dynamic contract count from API", async () => {
    mockFetch(MOCK_DATA);
    render(<SubcontratacaoFornecedorBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(/venceu 12 contratos que podem envolver subcontratação/i)
      ).toBeInTheDocument();
    });
  });

  it("renders heading", async () => {
    mockFetch(MOCK_DATA);
    render(<SubcontratacaoFornecedorBlock {...defaultProps} />);

    await waitFor(() => {
      const headings = screen.getAllByText(/Pontes de subcontratação/i);
      expect(headings.length).toBeGreaterThan(0);
    });
  });
});
