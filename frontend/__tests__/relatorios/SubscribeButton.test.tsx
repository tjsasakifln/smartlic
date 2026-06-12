/**
 * REPORT-MONTHLY-001 (#1620): Tests for SubscribeButton component.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SubscribeButton from "../../../frontend/app/relatorios/mensal/components/SubscribeButton";

describe("SubscribeButton", () => {
  const mockOnSubscribe = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders with sector name and price", () => {
    render(
      <SubscribeButton
        sectorId="alimentos"
        sectorName="Alimentos"
        onSubscribe={mockOnSubscribe}
      />,
    );

    expect(
      screen.getByText(/Panorama Mensal — Alimentos/),
    ).toBeInTheDocument();
    expect(screen.getByText("R$ 97")).toBeInTheDocument();
    expect(
      screen.getByText("Assinar Agora"),
    ).toBeInTheDocument();
  });

  it("calls onSubscribe when clicked", async () => {
    mockOnSubscribe.mockResolvedValueOnce(undefined);

    render(
      <SubscribeButton
        sectorId="engenharia"
        sectorName="Engenharia"
        onSubscribe={mockOnSubscribe}
      />,
    );

    fireEvent.click(screen.getByText("Assinar Agora"));

    await waitFor(() => {
      expect(mockOnSubscribe).toHaveBeenCalledWith("engenharia");
    });
  });

  it("shows success message after subscribing", async () => {
    mockOnSubscribe.mockResolvedValueOnce(undefined);

    render(
      <SubscribeButton
        sectorId="alimentos"
        sectorName="Alimentos"
        onSubscribe={mockOnSubscribe}
      />,
    );

    fireEvent.click(screen.getByText("Assinar Agora"));

    await waitFor(() => {
      expect(
        screen.getByText(/Inscricao realizada com sucesso/),
      ).toBeInTheDocument();
    });
  });

  it("shows error message when subscription fails", async () => {
    mockOnSubscribe.mockRejectedValueOnce(
      new Error("Voce ja esta inscrito neste relatorio"),
    );

    render(
      <SubscribeButton
        sectorId="alimentos"
        sectorName="Alimentos"
        onSubscribe={mockOnSubscribe}
      />,
    );

    fireEvent.click(screen.getByText("Assinar Agora"));

    await waitFor(() => {
      expect(
        screen.getByText("Voce ja esta inscrito neste relatorio"),
      ).toBeInTheDocument();
    });
  });

  it("shows cancel policy", () => {
    render(
      <SubscribeButton
        sectorId="alimentos"
        sectorName="Alimentos"
        onSubscribe={mockOnSubscribe}
      />,
    );

    expect(
      screen.getByText(/Cancele quando quiser/),
    ).toBeInTheDocument();
  });
});
