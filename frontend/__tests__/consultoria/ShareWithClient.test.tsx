/**
 * CONSULT-001 (#1613): Tests for ShareWithClient component.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ShareWithClient from "../../../frontend/app/consultoria/clientes/components/ShareWithClient";

describe("ShareWithClient", () => {
  const mockOnClose = jest.fn();
  const mockOnShare = jest.fn().mockResolvedValue(undefined);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders nothing when closed", () => {
    const { container } = render(
      <ShareWithClient
        clientId="client-1"
        isOpen={false}
        onClose={mockOnClose}
        onShare={mockOnShare}
      />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("renders modal when open", () => {
    render(
      <ShareWithClient
        clientId="client-1"
        clientEmail="cliente@teste.com"
        isOpen={true}
        onClose={mockOnClose}
        onShare={mockOnShare}
      />,
    );

    expect(screen.getByText(/Compartilhar com/)).toBeInTheDocument();
    expect(screen.getByText("cliente@teste.com")).toBeInTheDocument();
    expect(screen.getByText("Tipo de recurso")).toBeInTheDocument();
    expect(screen.getByText("ID do recurso")).toBeInTheDocument();
    expect(screen.getByText("Compartilhar")).toBeInTheDocument();
  });

  it("allows selecting resource type", () => {
    render(
      <ShareWithClient
        clientId="client-1"
        isOpen={true}
        onClose={mockOnClose}
        onShare={mockOnShare}
      />,
    );

    const select = screen.getByRole("combobox");
    expect(select).toBeInTheDocument();

    // Default should be "busca"
    expect(select).toHaveValue("busca");

    // Change to pipeline
    fireEvent.change(select, { target: { value: "pipeline" } });
    expect(select).toHaveValue("pipeline");
  });

  it("calls onShare with correct params", async () => {
    render(
      <ShareWithClient
        clientId="client-1"
        isOpen={true}
        onClose={mockOnClose}
        onShare={mockOnShare}
      />,
    );

    const resourceInput = screen.getByPlaceholderText("UUID do recurso");
    fireEvent.change(resourceInput, {
      target: { value: "abc-123-def-456" },
    });

    const shareButton = screen.getByText("Compartilhar");
    fireEvent.click(shareButton);

    await waitFor(() => {
      expect(mockOnShare).toHaveBeenCalledWith(
        "client-1",
        "busca",
        "abc-123-def-456",
      );
    });
  });

  it("shows error when resource id is empty", async () => {
    render(
      <ShareWithClient
        clientId="client-1"
        isOpen={true}
        onClose={mockOnClose}
        onShare={mockOnShare}
      />,
    );

    const shareButton = screen.getByText("Compartilhar");
    fireEvent.click(shareButton);

    expect(
      screen.getByText("Informe o ID do recurso."),
    ).toBeInTheDocument();
    expect(mockOnShare).not.toHaveBeenCalled();
  });

  it("shows success message after sharing", async () => {
    mockOnShare.mockResolvedValueOnce(undefined);

    render(
      <ShareWithClient
        clientId="client-1"
        isOpen={true}
        onClose={mockOnClose}
        onShare={mockOnShare}
      />,
    );

    const resourceInput = screen.getByPlaceholderText("UUID do recurso");
    fireEvent.change(resourceInput, { target: { value: "resource-1" } });

    const shareButton = screen.getByText("Compartilhar");
    fireEvent.click(shareButton);

    await waitFor(() => {
      expect(
        screen.getByText("Recurso compartilhado com sucesso!"),
      ).toBeInTheDocument();
    });
  });

  it("shows error message when share fails", async () => {
    mockOnShare.mockRejectedValueOnce(
      new Error("Cliente não encontrado"),
    );

    render(
      <ShareWithClient
        clientId="client-1"
        isOpen={true}
        onClose={mockOnClose}
        onShare={mockOnShare}
      />,
    );

    const resourceInput = screen.getByPlaceholderText("UUID do recurso");
    fireEvent.change(resourceInput, { target: { value: "resource-1" } });

    const shareButton = screen.getByText("Compartilhar");
    fireEvent.click(shareButton);

    await waitFor(() => {
      expect(
        screen.getByText("Cliente não encontrado"),
      ).toBeInTheDocument();
    });
  });

  it("calls onClose when close button is clicked", () => {
    render(
      <ShareWithClient
        clientId="client-1"
        isOpen={true}
        onClose={mockOnClose}
        onShare={mockOnShare}
      />,
    );

    const closeButton = screen.getByLabelText("Fechar");
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalled();
  });
});
