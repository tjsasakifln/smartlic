/**
 * VIAB-UX-004: "Por que esta oportunidade?" expandable section tests
 *
 * Tests:
 * - AC1: Toggle button renders with correct text
 * - AC2: Content is hidden when isOpen=false, shown when isOpen=true
 * - AC3: onToggle is called when button is clicked
 * - AC4: Sector name is displayed when provided
 * - AC5: Matched terms are shown as joined keywords
 * - AC6: "Detecção automática por IA" shown when no matched terms
 * - AC7: Viability factors breakdown is rendered in grid
 * - AC8: Each factor shows its score badge
 * - AC9: Mixpanel tracking on expand
 * - AC10: Chevron rotation on expand/collapse
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock framer-motion (pass through children)
jest.mock("framer-motion", () => {
  const React = require("react");
  const motion = new Proxy(
    {},
    {
      get: (_target: unknown, prop: string) =>
        React.forwardRef(
          (
            { children, ...props }: { children?: React.ReactNode; [key: string]: unknown },
            ref: React.Ref<HTMLElement>,
          ) => {
            const safe: Record<string, unknown> = {};
            for (const [k, v] of Object.entries(props)) {
              if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
                safe[k] = v;
              }
            }
            return React.createElement(prop, { ...safe, ref }, children);
          },
        ),
    },
  );
  return { motion, AnimatePresence: ({ children }: { children?: React.ReactNode }) => children };
});

// Mock formatCurrencyBR
jest.mock("../../frontend/lib/format-currency", () => ({
  formatCurrencyBR: (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v),
}));

import WhyThisOpportunity from "../app/buscar/components/WhyThisOpportunity";

describe("WhyThisOpportunity", () => {
  const defaultProps = {
    bidId: "bid-123",
    isOpen: false,
    onToggle: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Clean up mixpanel mock
    delete (window as any).mixpanel;
  });

  // AC1: Toggle button renders with correct text
  it("renders toggle button with correct label", () => {
    render(<WhyThisOpportunity {...defaultProps} />);
    const btn = screen.getByTestId("why-toggle-btn");
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent("Por que esta oportunidade?");
  });

  // AC1: Button shows aria-expanded false when closed
  it("has aria-expanded=false when closed", () => {
    render(<WhyThisOpportunity {...defaultProps} />);
    const btn = screen.getByTestId("why-toggle-btn");
    expect(btn).toHaveAttribute("aria-expanded", "false");
  });

  // AC1: Button shows aria-expanded true when open
  it("has aria-expanded=true when open", () => {
    render(<WhyThisOpportunity {...defaultProps} isOpen={true} />);
    const btn = screen.getByTestId("why-toggle-btn");
    expect(btn).toHaveAttribute("aria-expanded", "true");
  });

  // AC2: Content is hidden when isOpen=false
  it("does not render content when isOpen is false", () => {
    render(<WhyThisOpportunity {...defaultProps} />);
    expect(screen.queryByTestId("why-content")).not.toBeInTheDocument();
  });

  // AC2: Content is shown when isOpen=true
  it("renders content when isOpen is true", () => {
    render(<WhyThisOpportunity {...defaultProps} isOpen={true} />);
    expect(screen.getByTestId("why-content")).toBeInTheDocument();
  });

  // AC3: onToggle is called when button is clicked
  it("calls onToggle when button is clicked", () => {
    const onToggle = jest.fn();
    render(<WhyThisOpportunity {...defaultProps} onToggle={onToggle} />);
    fireEvent.click(screen.getByTestId("why-toggle-btn"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  // AC4: Sector name is displayed when provided
  it("shows sector name when provided", () => {
    render(
      <WhyThisOpportunity
        {...defaultProps}
        isOpen={true}
        sectorName="Vestuário"
        viabilityScore={85}
      />,
    );
    expect(screen.getByTestId("why-sector")).toHaveTextContent("Setor detectado:");
    expect(screen.getByTestId("why-sector")).toHaveTextContent("Vestuário");
    expect(screen.getByTestId("why-sector")).toHaveTextContent("confiança: 85%");
  });

  // AC4: Does not show sector line when sectorName not provided
  it("does not show sector line when sectorName is not provided", () => {
    render(<WhyThisOpportunity {...defaultProps} isOpen={true} />);
    expect(screen.queryByTestId("why-sector")).not.toBeInTheDocument();
  });

  // AC5: Matched terms are shown as joined keywords
  it("shows matched terms as joined keywords", () => {
    render(
      <WhyThisOpportunity
        {...defaultProps}
        isOpen={true}
        matchedTerms={["uniforme", "escolar", "fardamento"]}
      />,
    );
    expect(screen.getByTestId("why-keywords")).toHaveTextContent(
      "uniforme, escolar, fardamento",
    );
  });

  // AC6: Shows "Detecção automática por IA" when no matched terms
  it('shows "Detecção automática por IA" when no matched terms', () => {
    render(
      <WhyThisOpportunity
        {...defaultProps}
        isOpen={true}
        matchedTerms={[]}
      />,
    );
    expect(screen.getByTestId("why-keywords")).toHaveTextContent(
      "Detecção automática por IA",
    );
  });

  // AC6: Also handles undefined matchedTerms
  it('shows "Detecção automática por IA" when matchedTerms is undefined', () => {
    render(<WhyThisOpportunity {...defaultProps} isOpen={true} />);
    expect(screen.getByTestId("why-keywords")).toHaveTextContent(
      "Detecção automática por IA",
    );
  });

  // AC7: Viability factors breakdown is rendered in grid
  it("renders viability factors when provided", () => {
    const factors = {
      modalidade: 80,
      modalidade_label: "Pregão — ideal para seu perfil",
      timeline: 70,
      timeline_label: "45 dias — prazo confortável",
      value_fit: 60,
      value_fit_label: "Compatível com seu mercado",
      geography: 90,
      geography_label: "Mesma região de atuação",
    };
    render(
      <WhyThisOpportunity
        {...defaultProps}
        isOpen={true}
        viabilityFactors={factors}
        viabilityScore={75}
      />,
    );
    expect(screen.getByTestId("why-factor-prazo")).toBeInTheDocument();
    expect(screen.getByTestId("why-factor-valor")).toBeInTheDocument();
    expect(screen.getByTestId("why-factor-local")).toBeInTheDocument();
    expect(screen.getByTestId("why-factor-modalidade")).toBeInTheDocument();
  });

  // AC8: Each factor shows its score badge
  it("shows score badges for each factor", () => {
    const factors = {
      modalidade: 80,
      modalidade_label: "Pregão",
      timeline: 70,
      timeline_label: "45 dias",
      value_fit: 60,
      value_fit_label: "Compatível",
      geography: 90,
      geography_label: "Mesma região",
    };
    render(
      <WhyThisOpportunity
        {...defaultProps}
        isOpen={true}
        viabilityFactors={factors}
      />,
    );
    expect(screen.getByTestId("why-factor-prazo-score")).toHaveTextContent("70");
    expect(screen.getByTestId("why-factor-valor-score")).toHaveTextContent("60");
    expect(screen.getByTestId("why-factor-local-score")).toHaveTextContent("90");
    expect(screen.getByTestId("why-factor-modalidade-score")).toHaveTextContent("80");
  });

  // AC8: Shows valor formatting when valor is provided
  it("shows valor in factor description when valor is provided", () => {
    const factors = {
      modalidade: 80,
      modalidade_label: "Pregão",
      timeline: 70,
      timeline_label: "45 dias",
      value_fit: 60,
      value_fit_label: "Compatível com seu mercado",
      geography: 90,
      geography_label: "Mesma região",
    };
    render(
      <WhyThisOpportunity
        {...defaultProps}
        isOpen={true}
        viabilityFactors={factors}
        valor={250000}
      />,
    );
    // Check that the valor factor includes formatted currency + label
    expect(screen.getByTestId("why-factor-valor")).toHaveTextContent("R$");
    expect(screen.getByTestId("why-factor-valor")).toHaveTextContent("250.000,00");
  });

  // AC8: Shows local with municipio/UF
  it("shows location with municipio/UF format", () => {
    const factors = {
      modalidade: 80,
      modalidade_label: "Pregão",
      timeline: 70,
      timeline_label: "45 dias",
      value_fit: 60,
      value_fit_label: "Compatível",
      geography: 90,
      geography_label: "Capital e região metropolitana",
    };
    render(
      <WhyThisOpportunity
        {...defaultProps}
        isOpen={true}
        viabilityFactors={factors}
        municipio="São Paulo"
        uf="SP"
      />,
    );
    expect(screen.getByTestId("why-factor-local")).toHaveTextContent(
      "São Paulo/SP — Capital e região metropolitana",
    );
  });

  // AC8: Shows confidence badge next to toggle button
  it("shows viability score badge next to toggle button", () => {
    render(
      <WhyThisOpportunity
        {...defaultProps}
        viabilityScore={72}
      />,
    );
    const btn = screen.getByTestId("why-toggle-btn");
    expect(btn).toHaveTextContent("72%");
  });

  // AC9: Mixpanel tracking on expand
  it("tracks mixpanel event when expanded", () => {
    const mixpanelTrack = jest.fn();
    (window as any).mixpanel = { track: mixpanelTrack };

    const { rerender } = render(<WhyThisOpportunity {...defaultProps} />);
    expect(mixpanelTrack).not.toHaveBeenCalled();

    // Open
    rerender(<WhyThisOpportunity {...defaultProps} isOpen={true} />);
    expect(mixpanelTrack).toHaveBeenCalledTimes(1);
    expect(mixpanelTrack).toHaveBeenCalledWith("why_this_opportunity_expanded", {
      bid_id: "bid-123",
    });
  });

  // AC9: Does not track without bidId
  it("does not track mixpanel event when bidId is not provided", () => {
    const mixpanelTrack = jest.fn();
    (window as any).mixpanel = { track: mixpanelTrack };

    const { rerender } = render(
      <WhyThisOpportunity {...defaultProps} bidId={undefined} />,
    );
    rerender(
      <WhyThisOpportunity {...defaultProps} bidId={undefined} isOpen={true} />,
    );
    expect(mixpanelTrack).not.toHaveBeenCalled();
  });

  // AC9: Does not track when mixpanel is unavailable
  it("does not throw when mixpanel is not available", () => {
    const { rerender } = render(<WhyThisOpportunity {...defaultProps} />);
    expect(() => {
      rerender(<WhyThisOpportunity {...defaultProps} isOpen={true} />);
    }).not.toThrow();
  });

  // AC10: Chevron rotation on expand
  it("applies rotate-180 class to chevron when open", () => {
    const { container, rerender } = render(<WhyThisOpportunity {...defaultProps} />);
    const chevronClosed = container.querySelector("svg");
    // When closed, chevron should not be rotated
    expect(chevronClosed).not.toHaveClass("rotate-180");

    rerender(<WhyThisOpportunity {...defaultProps} isOpen={true} />);
    const chevronOpen = container.querySelector("svg");
    expect(chevronOpen).toHaveClass("rotate-180");
  });

  // AC8: Shows correct score colors
  it("applies correct score color classes", () => {
    const factors = {
      modalidade: 85,
      modalidade_label: "Pregão",
      timeline: 50,
      timeline_label: "30 dias",
      value_fit: 30,
      value_fit_label: "Abaixo do esperado",
      geography: 70,
      geography_label: "Fora da região",
    };
    render(
      <WhyThisOpportunity
        {...defaultProps}
        isOpen={true}
        viabilityFactors={factors}
      />,
    );
    // Score 85 >= 70 → emerald
    const score85 = screen.getByTestId("why-factor-modalidade-score");
    expect(score85.className).toContain("emerald");

    // Score 50 >= 40 → amber
    const score50 = screen.getByTestId("why-factor-prazo-score");
    expect(score50.className).toContain("amber");

    // Score 30 < 40 → gray
    const score30 = screen.getByTestId("why-factor-valor-score");
    expect(score30.className).toContain("gray");
  });
});
