/**
 * CONSULT-001 (#1613): Tests for ClientList component.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ClientList from "../../../frontend/app/consultoria/clientes/components/ClientList";
import type { Client } from "../../../frontend/app/consultoria/clientes/components/ClientList";

describe("ClientList", () => {
  const mockOnRevoke = jest.fn();
  const mockOnShare = jest.fn();

  const activeClient: Client = {
    id: "rel-1",
    client_id: "client-1",
    client_email: "cliente@teste.com",
    status: "active",
    created_at: "2026-06-12T00:00:00Z",
  };

  const revokedClient: Client = {
    id: "rel-2",
    client_id: "client-2",
    client_email: "revogado@teste.com",
    status: "revoked",
    created_at: "2026-06-10T00:00:00Z",
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading state", () => {
    render(
      <ClientList
        clients={[]}
        loading={true}
        onRevoke={mockOnRevoke}
        onShare={mockOnShare}
      />,
    );

    expect(screen.getByText("Carregando clientes...")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(
      <ClientList
        clients={[]}
        loading={false}
        onRevoke={mockOnRevoke}
        onShare={mockOnShare}
      />,
    );

    expect(
      screen.getByText(/Nenhum cliente encontrado/),
    ).toBeInTheDocument();
  });

  it("renders active client with actions", () => {
    render(
      <ClientList
        clients={[activeClient]}
        loading={false}
        onRevoke={mockOnRevoke}
        onShare={mockOnShare}
      />,
    );

    expect(screen.getByText("cliente@teste.com")).toBeInTheDocument();
    expect(screen.getByText("Ativo")).toBeInTheDocument();
    expect(screen.getByText("Compartilhar")).toBeInTheDocument();
    expect(screen.getByText("Revogar")).toBeInTheDocument();
  });

  it("renders revoked client without actions", () => {
    render(
      <ClientList
        clients={[revokedClient]}
        loading={false}
        onRevoke={mockOnRevoke}
        onShare={mockOnShare}
      />,
    );

    expect(screen.getByText("revogado@teste.com")).toBeInTheDocument();
    expect(screen.getByText("Revogado")).toBeInTheDocument();
    expect(screen.queryByText("Compartilhar")).not.toBeInTheDocument();
    expect(screen.queryByText("Revogar")).not.toBeInTheDocument();
  });

  it("calls onRevoke when revoke button is clicked", () => {
    render(
      <ClientList
        clients={[activeClient]}
        loading={false}
        onRevoke={mockOnRevoke}
        onShare={mockOnShare}
      />,
    );

    fireEvent.click(screen.getByText("Revogar"));
    expect(mockOnRevoke).toHaveBeenCalledWith("client-1");
  });

  it("calls onShare when share button is clicked", () => {
    render(
      <ClientList
        clients={[activeClient]}
        loading={false}
        onRevoke={mockOnRevoke}
        onShare={mockOnShare}
      />,
    );

    fireEvent.click(screen.getByText("Compartilhar"));
    expect(mockOnShare).toHaveBeenCalledWith("client-1");
  });

  it("renders multiple clients", () => {
    render(
      <ClientList
        clients={[activeClient, revokedClient]}
        loading={false}
        onRevoke={mockOnRevoke}
        onShare={mockOnShare}
      />,
    );

    expect(screen.getByText("cliente@teste.com")).toBeInTheDocument();
    expect(screen.getByText("revogado@teste.com")).toBeInTheDocument();
  });
});
