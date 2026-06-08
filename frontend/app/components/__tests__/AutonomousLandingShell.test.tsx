/**
 * AutonomousLandingShell Tests (#1509)
 *
 * Tests: renders title, description, social proof, trust signals,
 * CTA area, what-is-this section, and bottom CTA.
 */

import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import AutonomousLandingShell from "@/app/components/AutonomousLandingShell";

// Mock next/link
jest.mock("next/link", () => {
  return function MockLink({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) {
    return (
      <a href={href} className={className}>
        {children}
      </a>
    );
  };
});

// Mock LandingNavbar
jest.mock("@/app/components/landing/LandingNavbar", () => {
  return function MockLandingNavbar() {
    return <div data-testid="landing-navbar">LandingNavbar</div>;
  };
});

// Mock Footer
jest.mock("@/app/components/Footer", () => {
  return function MockFooter() {
    return <div data-testid="footer">Footer</div>;
  };
});

describe("AutonomousLandingShell", () => {
  const defaultProps = {
    entityType: "fornecedor" as const,
    entityName: "Empresa ABC Ltda",
    entityDescription: "Fornecedora de serviços de TI para o governo.",
    children: <div data-testid="children-content">Main content</div>,
    ctaComponent: (
      <button data-testid="cta-button">Receber alertas grátis</button>
    ),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders the landing navbar", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(screen.getByTestId("landing-navbar")).toBeInTheDocument();
  });

  it("renders the footer", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(screen.getByTestId("footer")).toBeInTheDocument();
  });

  it("renders the entity name as heading", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(
      screen.getByRole("heading", { name: /Empresa ABC Ltda/i })
    ).toBeInTheDocument();
  });

  it("renders the entity description", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(
      screen.getByText(/Fornecedora de serviços de TI/i)
    ).toBeInTheDocument();
  });

  it("renders children content", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(screen.getByTestId("children-content")).toBeInTheDocument();
  });

  it("renders CTA button when ctaComponent is provided", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(screen.getByTestId("cta-button")).toBeInTheDocument();
  });

  it("renders 'Só quero ver os dados' link in CTA area", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    const link = screen.getByText(/Só quero ver os dados/i);
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/observatorio");
  });

  it("renders default social proof items when no custom socialProof provided", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(screen.getByText("2.000+")).toBeInTheDocument();
    expect(screen.getByText("50.000+")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Empresas cadastradas")).toBeInTheDocument();
    expect(screen.getByText("Editais analisados")).toBeInTheDocument();
    expect(screen.getByText("Fontes oficiais")).toBeInTheDocument();
  });

  it("renders custom social proof items when provided", () => {
    const customProof = [
      { label: "Clientes ativos", value: "150" },
      { label: "Contratos monitorados", value: "12k" },
    ];
    render(
      <AutonomousLandingShell
        {...defaultProps}
        socialProof={customProof}
      />
    );
    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("12k")).toBeInTheDocument();
    expect(screen.getByText("Clientes ativos")).toBeInTheDocument();
    // Default items should NOT be present
    expect(screen.queryByText("2.000+")).not.toBeInTheDocument();
  });

  it("renders 'O que é o SmartLic?' section", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(
      screen.getByRole("heading", { name: /O que é o SmartLic/i })
    ).toBeInTheDocument();
  });

  it("renders trust signals section", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(
      screen.getByRole("heading", { name: /Por que confiar no SmartLic/i })
    ).toBeInTheDocument();
    expect(screen.getByText("Dados oficiais")).toBeInTheDocument();
    expect(screen.getByText("Classificação por IA")).toBeInTheDocument();
    expect(screen.getByText("Análise de viabilidade")).toBeInTheDocument();
  });

  it("renders testimonial quote", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(
      screen.getByText(/O SmartLic nos ajudou a encontrar licitações/i)
    ).toBeInTheDocument();
  });

  it("renders 'Saiba mais sobre a plataforma' link", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    const link = screen.getByText(/Saiba mais sobre a plataforma/i);
    expect(link).toHaveAttribute("href", "/sobre");
  });

  it("renders bottom CTA section when ctaComponent is provided", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    expect(
      screen.getByRole("heading", { name: /Não perca nenhuma licitação/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Cadastre-se gratuitamente/i)
    ).toBeInTheDocument();
  });

  it("renders 'Começar grátis' link in bottom CTA with correct reference", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    const link = screen.getByText(/Começar grátis/i);
    expect(link).toHaveAttribute(
      "href",
      expect.stringContaining("/signup?ref=autonomous-fornecedor")
    );
  });

  it("renders 'Ver planos e preços' link in bottom CTA", () => {
    render(<AutonomousLandingShell {...defaultProps} />);
    const link = screen.getByText(/Ver planos e preços/i);
    expect(link).toHaveAttribute("href", "/planos");
  });

  it("does not render CTA areas when ctaComponent is not provided", () => {
    render(
      <AutonomousLandingShell
        entityType="setor"
        entityName="Setor de Saúde"
        children={<div>Content</div>}
      />
    );
    expect(
      screen.queryByText(/Não perca nenhuma licitação/i)
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Só quero ver os dados/i)
    ).not.toBeInTheDocument();
  });

  it("does not render entity description when not provided", () => {
    render(
      <AutonomousLandingShell
        entityType="orgao"
        entityName="Órgão Teste"
        children={<div>Content</div>}
      />
    );
    expect(screen.getByRole("heading", { name: /Órgão Teste/i })).toBeInTheDocument();
  });

  describe("entity types", () => {
    const entityTypes = [
      { type: "fornecedor" as const, expectSuffix: "deste fornecedor" },
      { type: "orgao" as const, expectSuffix: "deste órgão" },
      { type: "setor" as const, expectSuffix: "deste setor" },
      { type: "municipio" as const, expectSuffix: "deste município" },
      { type: "contrato" as const, expectSuffix: "deste contrato" },
      { type: "item" as const, expectSuffix: "deste item" },
    ];

    entityTypes.forEach(({ type, expectSuffix }) => {
      it(`renders correct CTA suffix for entityType="${type}"`, () => {
        render(
          <AutonomousLandingShell
            entityType={type}
            entityName={`Entity ${type}`}
            ctaComponent={<button>CTA</button>}
          >
            <div>Content</div>
          </AutonomousLandingShell>
        );
        expect(screen.getByText(new RegExp(expectSuffix, "i"))).toBeInTheDocument();
      });
    });
  });
});
