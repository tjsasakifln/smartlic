/**
 * REPORT-MONTHLY-001 (#1620): Tests for ReportPreview component.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import ReportPreview from "../../../frontend/app/relatorios/mensal/components/ReportPreview";

describe("ReportPreview", () => {
  const defaultProps = {
    sectorId: "alimentos",
    sectorName: "Alimentos",
    period: "2026-05",
    totalLicitacoes: 150,
    totalValue: 2500000.0,
    avgValue: 16666.67,
    topOpportunities: [
      {
        objeto: "Contrato de alimentos para escolas",
        orgao: "Prefeitura de SP",
        valor: 500000.0,
        data: "2026-05-15",
      },
    ],
    topWinners: [
      {
        nome: "Fornecedor Ltda",
        cnpj: "12.345.678/0001-90",
        total: 1200000.0,
        contratos: 5,
      },
    ],
    executiveSummary:
      "No periodo, o setor de Alimentos registrou 150 contratos.",
    loading: false,
  };

  it("shows loading state", () => {
    render(<ReportPreview {...defaultProps} loading={true} />);
    expect(
      screen.getByText("Carregando preview do relatorio..."),
    ).toBeInTheDocument();
  });

  it("renders executive summary", () => {
    render(<ReportPreview {...defaultProps} />);
    expect(
      screen.getByText("1. Resumo Executivo"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/No periodo, o setor de Alimentos/),
    ).toBeInTheDocument();
  });

  it("renders key metrics", () => {
    render(<ReportPreview {...defaultProps} />);
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("Total de Contratos")).toBeInTheDocument();
    expect(screen.getByText("Valor Total")).toBeInTheDocument();
    expect(screen.getByText("Valor Medio")).toBeInTheDocument();
  });

  it("renders top opportunities section", () => {
    render(<ReportPreview {...defaultProps} />);
    expect(
      screen.getByText("2. Top Oportunidades"),
    ).toBeInTheDocument();
    expect(screen.getByText("Objeto")).toBeInTheDocument();
    expect(screen.getByText("Orgao")).toBeInTheDocument();
    expect(screen.getByText("Valor")).toBeInTheDocument();
  });

  it("renders top winners section", () => {
    render(<ReportPreview {...defaultProps} />);
    expect(
      screen.getByText("3. Quem Ganhou"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Fornecedor Ltda"),
    ).toBeInTheDocument();
  });

  it("shows empty state when no top opportunities", () => {
    render(
      <ReportPreview {...defaultProps} topOpportunities={[]} />,
    );
    expect(
      screen.getByText("Nenhuma oportunidade encontrada no periodo."),
    ).toBeInTheDocument();
  });

  it("shows empty state when no top winners", () => {
    render(<ReportPreview {...defaultProps} topWinners={[]} />);
    expect(
      screen.getByText("Nenhum vencedor encontrado no periodo."),
    ).toBeInTheDocument();
  });
});
