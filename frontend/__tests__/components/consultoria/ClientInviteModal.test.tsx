import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ClientInviteModal from "../../../app/consultoria/clientes/components/ClientInviteModal";

describe("ClientInviteModal", () => {
  const props = { onClose: jest.fn(), onInvite: jest.fn().mockResolvedValue(undefined) };

  beforeEach(() => jest.clearAllMocks());

  it("renders form", () => {
    render(<ClientInviteModal {...props} />);
    expect(screen.getByText("Convidar Cliente")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("cliente@exemplo.com")).toBeInTheDocument();
  });

  it("validates empty email", async () => {
    render(<ClientInviteModal {...props} />);
    fireEvent.click(screen.getByText("Gerar Link de Convite"));
    expect(await screen.findByText("Informe o email.")).toBeInTheDocument();
  });

  it("calls onInvite with valid email", async () => {
    render(<ClientInviteModal {...props} />);
    fireEvent.change(screen.getByPlaceholderText("cliente@exemplo.com"), { target: { value: "a@b.com" } });
    fireEvent.click(screen.getByText("Gerar Link de Convite"));
    await waitFor(() => expect(props.onInvite).toHaveBeenCalledWith("a@b.com"));
  });

  it("calls onClose on cancel", () => {
    render(<ClientInviteModal {...props} />);
    fireEvent.click(screen.getByText("Cancelar"));
    expect(props.onClose).toHaveBeenCalled();
  });
});
