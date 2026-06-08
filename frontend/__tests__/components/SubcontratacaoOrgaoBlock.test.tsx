/**
 * Tests for SubcontratacaoOrgaoBlock — Issue #1321
 *
 * Covers:
 *  - Renders block with data-testid
 *  - Shows CTA link to /subcontratacao
 *  - Shows orgao name in text
 *  - Renders heading
 */

import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SubcontratacaoOrgaoBlock } from "@/app/components/SubcontratacaoOrgaoBlock";

describe("SubcontratacaoOrgaoBlock", () => {
  const defaultProps = {
    slug: "prefeitura-municipal-sao-paulo",
    nome: "Prefeitura Municipal de São Paulo",
  };

  it("renders with data-testid", () => {
    render(<SubcontratacaoOrgaoBlock {...defaultProps} />);
    expect(
      screen.getByTestId("subcontratacao-orgao-block")
    ).toBeInTheDocument();
  });

  it("renders CTA link to /subcontratacao", () => {
    render(<SubcontratacaoOrgaoBlock {...defaultProps} />);
    const link = screen.getByTestId("subcontratacao-orgao-cta");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/subcontratacao");
  });

  it("shows orgao name in description", () => {
    render(<SubcontratacaoOrgaoBlock {...defaultProps} />);
    expect(
      screen.getByText(/Prefeitura Municipal de São Paulo/i)
    ).toBeInTheDocument();
  });

  it("renders heading", () => {
    render(<SubcontratacaoOrgaoBlock {...defaultProps} />);
    expect(
      screen.getByText(/Subcontratação/i)
    ).toBeInTheDocument();
  });

  it("renders CTA with correct label", () => {
    render(<SubcontratacaoOrgaoBlock {...defaultProps} />);
    expect(
      screen.getByText(/Mapear pontes neste órgão/i)
    ).toBeInTheDocument();
  });
});
