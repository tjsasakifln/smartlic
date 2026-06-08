/**
 * Tests for SubcontratacaoSetorBlock — Issue #1321
 *
 * Covers:
 *  - Renders block with data-testid
 *  - Shows CTA link to /subcontratacao with setor param
 *  - Shows setor name in text
 *  - Shows loading state initially
 *  - Shows placeholder text when API unavailable
 *  - Hidden when API returns zero percent
 *  - Renders dynamic percentage from API
 */

import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SubcontratacaoSetorBlock } from "@/app/components/SubcontratacaoSetorBlock";

const MOCK_DATA = {
  percentual_subcontratacao: 35,
  total_fornecedores: 120,
};

const ZERO_DATA = {
  percentual_subcontratacao: 0,
  total_fornecedores: 10,
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

describe("SubcontratacaoSetorBlock", () => {
  const defaultProps = {
    setor: "construcao-civil",
    setorLabel: "Construção Civil",
  };

  it("renders with data-testid", () => {
    mockFetch(MOCK_DATA);
    render(<SubcontratacaoSetorBlock {...defaultProps} />);
    expect(
      screen.getByTestId("subcontratacao-setor-block")
    ).toBeInTheDocument();
  });

  it("renders CTA link to /subcontratacao with setor query param", async () => {
    mockFetch(MOCK_DATA);
    render(<SubcontratacaoSetorBlock {...defaultProps} />);

    await waitFor(() => {
      const link = screen.getByTestId("subcontratacao-setor-cta");
      expect(link).toBeInTheDocument();
      expect(link.getAttribute("href")).toMatch(/\/subcontratacao\?setor=/);
    });
  });

  it("shows loading state initially", () => {
    global.fetch = jest.fn(() => new Promise(() => {}));
    render(<SubcontratacaoSetorBlock {...defaultProps} />);
    expect(
      screen.getByText(/Verificando dados/i)
    ).toBeInTheDocument();
  });

  it("shows placeholder text when API fails", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("Network error"));
    render(<SubcontratacaoSetorBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(/frequentemente subcontratam/i)
      ).toBeInTheDocument();
    });
  });

  it("shows nothing when API returns zero percent", async () => {
    mockFetch(ZERO_DATA);
    const { container } = render(
      <SubcontratacaoSetorBlock {...defaultProps} />
    );

    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it("renders dynamic percentage from API", async () => {
    mockFetch(MOCK_DATA);
    render(<SubcontratacaoSetorBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(/35% das empresas vencedoras/i)
      ).toBeInTheDocument();
    });
  });

  it("renders heading", async () => {
    mockFetch(MOCK_DATA);
    render(<SubcontratacaoSetorBlock {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(/Subcontratação no setor/i)
      ).toBeInTheDocument();
    });
  });
});
