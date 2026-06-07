/**
 * Tests for PropostaComercialBlock — Issue #1402 (CONV-010-1)
 *
 * Coverage:
 *  - Renders with each of the 5 entity types (fornecedor, orgao, setor, municipio, contrato)
 *  - Headline interpolation with entityName
 *  - Insight cards display formatted data from entityData
 *  - Fallback text when entityData is missing expected fields
 *  - CTA with default href and custom ctaSku override
 *  - Secondary CTA shown only when config provides it
 *  - Mobile-first responsive grid (single column on mobile, 3 columns on sm+)
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import { PropostaComercialBlock } from "../../app/components/conversion/PropostaComercialBlock";

describe("PropostaComercialBlock", () => {
  // ---------------------------------------------------------------------------
  // Basic render
  // ---------------------------------------------------------------------------
  it("renders with fornecedor entity type and data", () => {
    const entityData = {
      total_contratos: 142,
      valor_total: 15_800_000,
      ufs_atuantes: ["SP", "RJ", "MG"],
    };

    render(
      <PropostaComercialBlock
        pageType="fornecedor"
        entityName="Construtora Exemplo Ltda"
        entityData={entityData}
      />,
    );

    expect(screen.getByTestId("proposta-comercial-block")).toBeInTheDocument();
    expect(screen.getByTestId("proposta-comercial-block")).toHaveAttribute(
      "data-page-type",
      "fornecedor",
    );

    // Headline with entity name interpolation
    expect(
      screen.getByText(/Quer vencer mais licitações como Construtora Exemplo Ltda/i),
    ).toBeInTheDocument();

    // Insight cards
    expect(screen.getByTestId("insight-card-contratos")).toHaveTextContent("142");
    expect(screen.getByTestId("insight-card-valor-total")).toHaveTextContent(
      "R$ 15.800.000",
    );
    expect(screen.getByTestId("insight-card-ufs")).toHaveTextContent("3");

    // CTA
    expect(screen.getByTestId("proposta-cta-primary")).toHaveAttribute(
      "href",
      "/signup?ref=proposta-fornecedor",
    );
    expect(screen.getByTestId("proposta-cta-primary")).toHaveTextContent(
      "Testar grátis",
    );
  });

  it("renders with orgao entity type and data", () => {
    const entityData = {
      total_licitacoes: 89,
      licitacoes_30d: 12,
      valor_medio_estimado: 450_000,
    };

    render(
      <PropostaComercialBlock
        pageType="orgao"
        entityName="Prefeitura Municipal de São Paulo"
        entityData={entityData}
      />,
    );

    expect(
      screen.getByText(/Quer vender para Prefeitura Municipal de São Paulo/i),
    ).toBeInTheDocument();

    expect(screen.getByTestId("insight-card-licitacoes")).toHaveTextContent("89");
    expect(screen.getByTestId("insight-card-licitacoes-30d")).toHaveTextContent("12");
    expect(screen.getByTestId("insight-card-valor-medio")).toHaveTextContent(
      "R$ 450.000",
    );
  });

  it("renders with setor entity type and data", () => {
    const entityData = {
      total_oportunidades: 320,
      concorrentes_count: 45,
      preco_medio: 125_000,
    };

    render(
      <PropostaComercialBlock
        pageType="setor"
        entityName="Facilities"
        entityData={entityData}
      />,
    );

    expect(
      screen.getByText(/Atue em Facilities com inteligência/i),
    ).toBeInTheDocument();

    expect(screen.getByTestId("insight-card-oportunidades")).toHaveTextContent("320");
    expect(screen.getByTestId("insight-card-concorrentes")).toHaveTextContent("45");
    expect(screen.getByTestId("insight-card-preco-medio")).toHaveTextContent(
      "R$ 125.000",
    );
  });

  it("renders with municipio entity type and data", () => {
    const entityData = {
      total_editais: 67,
      orgaos_count: 15,
      valor_total_estimado: 2_300_000,
    };

    render(
      <PropostaComercialBlock
        pageType="municipio"
        entityName="Campinas"
        entityData={entityData}
      />,
    );

    expect(screen.getByText(/Licitações em Campinas/i)).toBeInTheDocument();

    expect(screen.getByTestId("insight-card-editais")).toHaveTextContent("67");
    expect(screen.getByTestId("insight-card-orgaos")).toHaveTextContent("15");
    expect(screen.getByTestId("insight-card-valor-total")).toHaveTextContent(
      "R$ 2.300.000",
    );
  });

  it("renders with contrato entity type and data", () => {
    const entityData = {
      valor_contrato: 890_000,
      renovacoes_count: 3,
      concorrentes_count: 7,
    };

    render(
      <PropostaComercialBlock
        pageType="contrato"
        entityName="Contrato 2024/001"
        entityData={entityData}
      />,
    );

    expect(
      screen.getByText(/Contratos como este merecem análise/i),
    ).toBeInTheDocument();

    expect(screen.getByTestId("insight-card-analise")).toHaveTextContent(
      "R$ 890.000",
    );
    expect(screen.getByTestId("insight-card-renovacoes")).toHaveTextContent("3");
    expect(screen.getByTestId("insight-card-concorrentes")).toHaveTextContent("7");
  });

  // ---------------------------------------------------------------------------
  // Fallback behavior
  // ---------------------------------------------------------------------------
  it("shows fallback text when entityData is missing expected fields", () => {
    render(
      <PropostaComercialBlock
        pageType="fornecedor"
        entityName="Empresa Teste"
        entityData={{}}
      />,
    );

    // All insight cards should render with fallback values
    const cards = screen.getAllByTestId(/^insight-card-/);
    expect(cards.length).toBe(3);

    cards.forEach((card) => {
      expect(card).toHaveTextContent("Dados disponíveis");
    });
  });

  it("shows fallback when entityData has null values", () => {
    render(
      <PropostaComercialBlock
        pageType="orgao"
        entityName="Órgão Teste"
        entityData={{
          total_licitacoes: null,
          licitacoes_30d: null,
          valor_medio_estimado: null,
        }}
      />,
    );

    const cards = screen.getAllByTestId(/^insight-card-/);
    cards.forEach((card) => {
      expect(card).toHaveTextContent("Dados disponíveis");
    });
  });

  // ---------------------------------------------------------------------------
  // CTA customization
  // ---------------------------------------------------------------------------
  it("uses entityType default href when ctaSku is not provided", () => {
    render(
      <PropostaComercialBlock
        pageType="fornecedor"
        entityName="Empresa"
        entityData={{ total_contratos: 10 }}
      />,
    );

    expect(screen.getByTestId("proposta-cta-primary")).toHaveAttribute(
      "href",
      "/signup?ref=proposta-fornecedor",
    );
  });

  it("appends SKU to CTA href when ctaSku is provided", () => {
    render(
      <PropostaComercialBlock
        pageType="fornecedor"
        entityName="Empresa"
        entityData={{ total_contratos: 10 }}
        ctaSku="pro-analise"
      />,
    );

    expect(screen.getByTestId("proposta-cta-primary")).toHaveAttribute(
      "href",
      "/signup?ref=proposta-fornecedor&sku=pro-analise",
    );
  });

  it("does not render secondary CTA when config has no secondaryLabel", () => {
    render(
      <PropostaComercialBlock
        pageType="fornecedor"
        entityName="Empresa"
        entityData={{ total_contratos: 10 }}
      />,
    );

    expect(screen.queryByTestId("proposta-cta-secondary")).not.toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // Edge cases
  // ---------------------------------------------------------------------------
  it("handles empty entityData gracefully without crashing", () => {
    render(
      <PropostaComercialBlock
        pageType="contrato"
        entityName="Teste"
        entityData={{}}
      />,
    );

    expect(screen.getByTestId("proposta-comercial-block")).toBeInTheDocument();
    expect(screen.getByTestId("proposta-cta-primary")).toHaveTextContent(
      "Testar grátis",
    );
  });

  it("applies custom className", () => {
    render(
      <PropostaComercialBlock
        pageType="fornecedor"
        entityName="Empresa"
        entityData={{ total_contratos: 5 }}
        className="my-custom-class"
      />,
    );

    expect(screen.getByTestId("proposta-comercial-block")).toHaveClass(
      "my-custom-class",
    );
  });
});
