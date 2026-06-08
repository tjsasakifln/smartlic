/**
 * Tests for SubcontratacaoBuscaFilter — Issue #1321
 *
 * Covers:
 *  - Renders with data-testid
 *  - Shows label text
 *  - Toggle click triggers onChange
 *  - Reflects checked state
 *  - Can be disabled
 */

import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SubcontratacaoBuscaFilter } from "@/app/components/SubcontratacaoBuscaFilter";

describe("SubcontratacaoBuscaFilter", () => {
  it("renders with data-testid", () => {
    render(
      <SubcontratacaoBuscaFilter checked={false} onChange={() => {}} />
    );
    expect(
      screen.getByTestId("subcontratacao-busca-filter")
    ).toBeInTheDocument();
  });

  it("shows label text", () => {
    render(
      <SubcontratacaoBuscaFilter checked={false} onChange={() => {}} />
    );
    expect(
      screen.getByText(/Oportunidades de subcontratação/i)
    ).toBeInTheDocument();
  });

  it("fires onChange when toggle clicked", () => {
    const handleChange = jest.fn();
    render(
      <SubcontratacaoBuscaFilter checked={false} onChange={handleChange} />
    );
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);
    expect(handleChange).toHaveBeenCalledWith(true);
  });

  it("reflects checked state", () => {
    const { rerender } = render(
      <SubcontratacaoBuscaFilter checked={false} onChange={() => {}} />
    );
    let toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("aria-checked", "false");

    rerender(
      <SubcontratacaoBuscaFilter checked={true} onChange={() => {}} />
    );
    toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("does not fire onChange when disabled", () => {
    const handleChange = jest.fn();
    render(
      <SubcontratacaoBuscaFilter
        checked={false}
        onChange={handleChange}
        disabled={true}
      />
    );
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);
    expect(handleChange).not.toHaveBeenCalled();
  });

  it("has correct aria attributes", () => {
    render(
      <SubcontratacaoBuscaFilter checked={true} onChange={() => {}} />
    );
    const toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });
});
