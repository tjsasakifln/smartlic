/**
 * CONSULT-001 (#1613): Tests for ClientInviteModal component.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ClientInviteModal from "../../../frontend/app/consultoria/clientes/components/ClientInviteModal";

describe("ClientInviteModal", () => {
  const mockOnClose = jest.fn();
  const mockOnInvite = jest.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <ClientInviteModal
        isOpen={false}
        onClose={mockOnClose}
        onInvite={mockOnInvite}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders modal when open", () => {
    render(
      <ClientInviteModal
        isOpen={true}
        onClose={mockOnClose}
        onInvite={mockOnInvite}
      />,
    );

    expect(screen.getByText("Convidar Cliente")).toBeInTheDocument();
    expect(screen.getByLabelText("Email do cliente")).toBeInTheDocument();
    expect(screen.getByText("Convidar")).toBeInTheDocument();
    expect(screen.getByText("Cancelar")).toBeInTheDocument();
  });

  it("calls onInvite with email on submit", async () => {
    render(
      <ClientInviteModal
        isOpen={true}
        onClose={mockOnClose}
        onInvite={mockOnInvite}
      />,
    );

    const input = screen.getByLabelText("Email do cliente");
    fireEvent.change(input, { target: { value: "teste@cliente.com" } });

    const submitButton = screen.getByText("Convidar");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnInvite).toHaveBeenCalledWith("teste@cliente.com");
    });
  });

  it("shows error for empty email", async () => {
    render(
      <ClientInviteModal
        isOpen={true}
        onClose={mockOnClose}
        onInvite={mockOnInvite}
      />,
    );

    const submitButton = screen.getByText("Convidar");
    fireEvent.click(submitButton);

    expect(await screen.findByText("Informe o email do cliente.", undefined, { timeout: 3000 })).toBeInTheDocument();
    expect(mockOnInvite).not.toHaveBeenCalled();
  });

  it("shows success message after invite", async () => {
    mockOnInvite.mockResolvedValueOnce(undefined);

    render(
      <ClientInviteModal
        isOpen={true}
        onClose={mockOnClose}
        onInvite={mockOnInvite}
      />,
    );

    const input = screen.getByLabelText("Email do cliente");
    fireEvent.change(input, { target: { value: "teste@cliente.com" } });

    const submitButton = screen.getByText("Convidar");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText(/Convite enviado para teste@cliente.com/),
      ).toBeInTheDocument();
    });
  });

  it("shows error message when invite fails", async () => {
    mockOnInvite.mockRejectedValueOnce(new Error("Limite de assentos atingido"));

    render(
      <ClientInviteModal
        isOpen={true}
        onClose={mockOnClose}
        onInvite={mockOnInvite}
      />,
    );

    const input = screen.getByLabelText("Email do cliente");
    fireEvent.change(input, { target: { value: "teste@cliente.com" } });

    const submitButton = screen.getByText("Convidar");
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(
        screen.getByText("Limite de assentos atingido"),
      ).toBeInTheDocument();
    });
  });

  it("calls onClose when cancel is clicked", () => {
    render(
      <ClientInviteModal
        isOpen={true}
        onClose={mockOnClose}
        onInvite={mockOnInvite}
      />,
    );

    const cancelButton = screen.getByText("Cancelar");
    fireEvent.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalled();
  });
});
