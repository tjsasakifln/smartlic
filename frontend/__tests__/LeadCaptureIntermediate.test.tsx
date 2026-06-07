/**
 * CONV-003-4 (#1515): Tests for LeadCaptureIntermediate component.
 *
 * Tests:
 *   - Renders email input and submit button
 *   - Validates email format (empty, invalid)
 *   - Calls onSuccess callback on successful submission
 *   - Shows error state on API failure
 *   - Shows loading state during submission
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { LeadCaptureIntermediate } from "../app/components/conversion/LeadCaptureIntermediate";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const defaultProps = {
  sectorId: "engenharia",
  sourcePage: "/blog/licitacoes/engenharia",
  onSuccess: jest.fn(),
};

function mockFetchSuccess() {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: true,
    status: 200,
    json: async () => ({ success: true }),
    text: async () => JSON.stringify({ success: true }),
  });
}

function mockFetchError(status = 502) {
  (global.fetch as jest.Mock).mockResolvedValueOnce({
    ok: false,
    status,
    json: async () => ({ error: "Erro ao processar" }),
    text: async () => JSON.stringify({ error: "Erro ao processar" }),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("LeadCaptureIntermediate", () => {
  beforeEach(() => {
    (global.fetch as jest.Mock) = jest.fn();
    jest.spyOn(console, "error").mockImplementation(() => {});
    defaultProps.onSuccess = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("renders email input and submit button", () => {
    render(<LeadCaptureIntermediate {...defaultProps} />);

    expect(screen.getByTestId("lead-capture-form")).toBeInTheDocument();
    expect(screen.getByTestId("lead-capture-email-input")).toBeInTheDocument();
    expect(screen.getByTestId("lead-capture-submit")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("seu@email.com"),
    ).toBeInTheDocument();
  });

  it("shows error when submitting empty email", () => {
    render(<LeadCaptureIntermediate {...defaultProps} />);

    const submitButton = screen.getByTestId("lead-capture-submit");
    fireEvent.click(submitButton);

    expect(
      screen.getByText("Por favor, informe seu email."),
    ).toBeInTheDocument();
    expect(defaultProps.onSuccess).not.toHaveBeenCalled();
  });

  it("shows error when submitting invalid email", () => {
    render(<LeadCaptureIntermediate {...defaultProps} />);

    const input = screen.getByTestId("lead-capture-email-input");
    const submitButton = screen.getByTestId("lead-capture-submit");

    fireEvent.change(input, { target: { value: "email-invalido" } });
    fireEvent.click(submitButton);

    expect(
      screen.getByText("Por favor, informe um email válido."),
    ).toBeInTheDocument();
    expect(defaultProps.onSuccess).not.toHaveBeenCalled();
  });

  it("submits valid email and calls onSuccess", async () => {
    mockFetchSuccess();

    render(<LeadCaptureIntermediate {...defaultProps} />);

    const input = screen.getByTestId("lead-capture-email-input");
    const submitButton = screen.getByTestId("lead-capture-submit");

    fireEvent.change(input, { target: { value: "teste@exemplo.com" } });
    fireEvent.click(submitButton);

    // Should show loading state
    expect(submitButton).toBeDisabled();
    expect(submitButton.textContent).toContain("Enviando");

    // Wait for API call to complete
    await waitFor(() => {
      expect(defaultProps.onSuccess).toHaveBeenCalledTimes(1);
    });

    // Should have called fetch with correct params
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/lead-capture",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: expect.stringContaining("teste@exemplo.com"),
      }),
    );

    // Verify body contains the expected fields
    const callBody = JSON.parse(
      (global.fetch as jest.Mock).mock.calls[0][1].body,
    );
    expect(callBody.email).toBe("teste@exemplo.com");
    expect(callBody.sector_id).toBe("engenharia");
    expect(callBody.source_page).toBe("/blog/licitacoes/engenharia");
    expect(callBody.report_type).toBe("partial_preview");
  });

  it("shows error message when API call fails", async () => {
    mockFetchError(502);

    render(<LeadCaptureIntermediate {...defaultProps} />);

    const input = screen.getByTestId("lead-capture-email-input");
    const submitButton = screen.getByTestId("lead-capture-submit");

    fireEvent.change(input, { target: { value: "teste@exemplo.com" } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText("Erro ao processar"),
      ).toBeInTheDocument();
    });

    expect(defaultProps.onSuccess).not.toHaveBeenCalled();
  });

  it("shows generic error when API returns non-JSON error", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error("parse error");
      },
      text: async () => "Internal Server Error",
    });

    render(<LeadCaptureIntermediate {...defaultProps} />);

    const input = screen.getByTestId("lead-capture-email-input");
    const submitButton = screen.getByTestId("lead-capture-submit");

    fireEvent.change(input, { target: { value: "teste@exemplo.com" } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText("Erro ao processar. Tente novamente."),
      ).toBeInTheDocument();
    });

    expect(defaultProps.onSuccess).not.toHaveBeenCalled();
  });

  it("shows error message when network fails", async () => {
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error("Network error"));

    render(<LeadCaptureIntermediate {...defaultProps} />);

    const input = screen.getByTestId("lead-capture-email-input");
    const submitButton = screen.getByTestId("lead-capture-submit");

    fireEvent.change(input, { target: { value: "teste@exemplo.com" } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText("Network error"),
      ).toBeInTheDocument();
    });

    expect(defaultProps.onSuccess).not.toHaveBeenCalled();
  });

  it("disables input and button during loading", async () => {
    // Don't resolve the fetch
    (global.fetch as jest.Mock).mockReturnValueOnce(new Promise(() => {}));

    render(<LeadCaptureIntermediate {...defaultProps} />);

    const input = screen.getByTestId("lead-capture-email-input");
    const submitButton = screen.getByTestId("lead-capture-submit");

    fireEvent.change(input, { target: { value: "teste@exemplo.com" } });
    fireEvent.click(submitButton);

    expect(input).toBeDisabled();
    expect(submitButton).toBeDisabled();
    expect(submitButton.textContent).toContain("Enviando");
  });

  it("clears error when user types after an error", () => {
    render(<LeadCaptureIntermediate {...defaultProps} />);

    const input = screen.getByTestId("lead-capture-email-input");
    const submitButton = screen.getByTestId("lead-capture-submit");

    // Submit empty to trigger error
    fireEvent.click(submitButton);
    expect(
      screen.getByText("Por favor, informe seu email."),
    ).toBeInTheDocument();

    // Type something to clear the error
    fireEvent.change(input, { target: { value: "a" } });
    expect(
      screen.queryByText("Por favor, informe seu email."),
    ).not.toBeInTheDocument();
  });
});
