import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ClientList from "../../../app/consultoria/clientes/components/ClientList";

describe("ClientList", () => {
  const clients = [
    { id: "1", consultant_id: "c1", client_id: "cl1", client_email: "a@b.com", status: "active", created_at: "2026-06-10T10:00:00Z" },
    { id: "2", consultant_id: "c1", client_id: null, client_email: null, status: "active", created_at: "2026-06-11T10:00:00Z" },
    { id: "3", consultant_id: "c1", client_id: "cl3", client_email: "c@d.com", status: "revoked", created_at: "2026-06-09T10:00:00Z" },
  ];
  const props = { clients, onRevoke: jest.fn(), loading: false };

  it("renders active and revoked sections", () => {
    render(<ClientList {...props} />);
    expect(screen.getByText("Ativos (2)")).toBeInTheDocument();
    expect(screen.getByText("Revogados (1)")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(<ClientList clients={[]} onRevoke={jest.fn()} loading={false} />);
    expect(screen.getByText("Nenhum cliente ainda")).toBeInTheDocument();
  });

  it("calls onRevoke on confirm", () => {
    jest.spyOn(window, "confirm").mockReturnValue(true);
    render(<ClientList {...props} />);
    fireEvent.click(screen.getAllByText("Revogar")[0]);
    expect(props.onRevoke).toHaveBeenCalledWith("1");
  });
});
