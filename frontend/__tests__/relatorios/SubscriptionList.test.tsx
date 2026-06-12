/**
 * REPORT-MONTHLY-001 (#1620): Tests for SubscriptionList component.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import SubscriptionList from "../../../frontend/app/relatorios/mensal/components/SubscriptionList";

describe("SubscriptionList", () => {
  const mockOnCancel = jest.fn();

  const activeSub = {
    id: "sub-1",
    sector_id: "alimentos",
    status: "active",
    created_at: "2026-06-01T00:00:00Z",
  };

  const canceledSub = {
    id: "sub-2",
    sector_id: "engenharia",
    status: "canceled",
    created_at: "2026-05-01T00:00:00Z",
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading state", () => {
    render(
      <SubscriptionList
        subscriptions={[]}
        loading={true}
        onCancel={mockOnCancel}
      />,
    );

    expect(
      screen.getByText("Carregando assinaturas..."),
    ).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(
      <SubscriptionList
        subscriptions={[]}
        loading={false}
        onCancel={mockOnCancel}
      />,
    );

    expect(
      screen.getByText(/Voce ainda nao possui assinaturas/),
    ).toBeInTheDocument();
  });

  it("renders active subscription", () => {
    render(
      <SubscriptionList
        subscriptions={[activeSub]}
        loading={false}
        onCancel={mockOnCancel}
      />,
    );

    expect(
      screen.getByText(/Panorama Mensal — Alimentos/),
    ).toBeInTheDocument();
    expect(screen.getByText("Cancelar")).toBeInTheDocument();
  });

  it("renders canceled subscription without cancel button", () => {
    render(
      <SubscriptionList
        subscriptions={[canceledSub]}
        loading={false}
        onCancel={mockOnCancel}
      />,
    );

    expect(
      screen.getByText(/Panorama Mensal — Engenharia/),
    ).toBeInTheDocument();
    expect(screen.getByText("Cancelado")).toBeInTheDocument();
    expect(
      screen.queryByText("Cancelar"),
    ).not.toBeInTheDocument();
  });

  it("calls onCancel when cancel button is clicked", () => {
    render(
      <SubscriptionList
        subscriptions={[activeSub]}
        loading={false}
        onCancel={mockOnCancel}
      />,
    );

    fireEvent.click(screen.getByText("Cancelar"));
    expect(mockOnCancel).toHaveBeenCalledWith("sub-1");
  });

  it("renders multiple subscriptions", () => {
    render(
      <SubscriptionList
        subscriptions={[activeSub, canceledSub]}
        loading={false}
        onCancel={mockOnCancel}
      />,
    );

    expect(
      screen.getByText(/Panorama Mensal — Alimentos/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Panorama Mensal — Engenharia/),
    ).toBeInTheDocument();
  });
});
