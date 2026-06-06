/**
 * GTM-RESILIENCE-D04: ViabilityBadge component tests.
 *
 * AC8: Visual indicators with 3 levels
 * AC11: Tooltip shows factor breakdown
 *
 * DEBT-FE-002: Updated to use data-tooltip-content attribute instead of title.
 * The title attribute was removed for WCAG 2.1 AA compliance — tooltip content
 * is now accessible via keyboard/focus and via the data-tooltip-content attribute
 * for test introspection.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import ViabilityBadge from "../components/ViabilityBadge";
import type { ViabilityFactors } from "../components/ViabilityBadge";

const mockFactors: ViabilityFactors = {
  modalidade: 100,
  modalidade_label: "Ótimo",
  timeline: 80,
  timeline_label: "12 dias",
  value_fit: 100,
  value_fit_label: "Ideal",
  geography: 100,
  geography_label: "Sua região",
};

/** Helper: get tooltip content from the badge (uses data-tooltip-content) */
function getTooltipContent(badge: HTMLElement): string {
  return badge.getAttribute("data-tooltip-content") || "";
}

describe("ViabilityBadge", () => {
  // AC8: Three levels with correct labels
  it("renders 'Viabilidade alta' in green for alta level", () => {
    render(<ViabilityBadge level="alta" score={85} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("Viabilidade alta");
    expect(badge).toHaveAttribute("data-viability-level", "alta");
    // Green styling
    expect(badge.className).toContain("bg-emerald-100");
  });

  it("renders 'Viabilidade média' in yellow for media level", () => {
    render(<ViabilityBadge level="media" score={55} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    expect(badge).toHaveTextContent("Viabilidade média");
    expect(badge).toHaveAttribute("data-viability-level", "media");
    expect(badge.className).toContain("bg-yellow-100");
  });

  it("renders 'Viabilidade baixa' in gray for baixa level", () => {
    render(<ViabilityBadge level="baixa" score={25} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    expect(badge).toHaveTextContent("Viabilidade baixa");
    expect(badge).toHaveAttribute("data-viability-level", "baixa");
    expect(badge.className).toContain("bg-gray-100");
  });

  // AC8: Returns null when no level
  it("returns null when level is null", () => {
    const { container } = render(
      <ViabilityBadge level={null} score={null} factors={null} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("returns null when level is undefined", () => {
    const { container } = render(
      <ViabilityBadge level={undefined} score={undefined} factors={undefined} />
    );
    expect(container.firstChild).toBeNull();
  });

  // AC11: Tooltip with factor breakdown
  it("shows tooltip with factor breakdown including weights", () => {
    render(<ViabilityBadge level="alta" score={95} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    const tooltipContent = getTooltipContent(badge);
    expect(tooltipContent).toContain("Viabilidade: 95/100");
    expect(tooltipContent).toContain("Modalidade (30%): Ótimo (100/100)");
    expect(tooltipContent).toContain("Prazo (25%): 12 dias (80/100)");
    expect(tooltipContent).toContain("Valor (25%): Ideal (100/100)");
    expect(tooltipContent).toContain("UF (20%): Sua região (100/100)");
  });

  it("shows basic tooltip without factors", () => {
    render(<ViabilityBadge level="media" score={60} factors={null} />);
    const badge = screen.getByTestId("viability-badge");
    const tooltipContent = getTooltipContent(badge);
    expect(tooltipContent).toContain("Viabilidade: 60/100");
    expect(tooltipContent).not.toContain("Modalidade");
  });

  // VIAB-UX-003: Progress bars
  it("renders progress bars with correct widths when tooltip opens", () => {
    const { container } = render(
      <ViabilityBadge level="alta" score={85} factors={mockFactors} />
    );
    const badge = screen.getByTestId("viability-badge");

    // Open tooltip via focus
    fireEvent.focus(badge);

    const bars = container.querySelectorAll('[role="progressbar"]');
    expect(bars).toHaveLength(4);
    // mockFactors: modalidade=100, timeline=80, value_fit=100, geography=100
    expect(bars[0]).toHaveAttribute("aria-valuenow", "100");
    expect(bars[1]).toHaveAttribute("aria-valuenow", "80");
    expect(bars[2]).toHaveAttribute("aria-valuenow", "100");
    expect(bars[3]).toHaveAttribute("aria-valuenow", "100");
  });

  it("applies correct progress bar colors by score range", () => {
    const mixedFactors: ViabilityFactors = {
      modalidade: 85,  // >= 70 → green (bg-emerald-400)
      timeline: 55,    // 40-69 → yellow (bg-yellow-400)
      value_fit: 20,   // < 40 → gray (bg-gray-400)
      geography: 70,   // >= 70 → green
      modalidade_label: "Bom",
      timeline_label: "Médio",
      value_fit_label: "Baixo",
      geography_label: "OK",
    };

    const { container } = render(
      <ViabilityBadge level="media" score={55} factors={mixedFactors} />
    );
    const badge = screen.getByTestId("viability-badge");

    // Open tooltip via focus
    fireEvent.focus(badge);

    const bars = container.querySelectorAll('[role="progressbar"]');
    expect(bars).toHaveLength(4);

    // Order: Modalidade, Prazo, Valor, UF
    expect(bars[0]).toHaveClass("bg-emerald-400");
    expect(bars[1]).toHaveClass("bg-yellow-400");
    expect(bars[2]).toHaveClass("bg-gray-400");
    expect(bars[3]).toHaveClass("bg-emerald-400");
  });

  // Accessibility
  it("has correct aria-label for alta", () => {
    render(<ViabilityBadge level="alta" score={80} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    expect(badge).toHaveAttribute(
      "aria-label",
      "Viabilidade alta para sua empresa"
    );
  });

  it("is keyboard-focusable", () => {
    render(<ViabilityBadge level="media" score={55} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    expect(badge).toHaveAttribute("tabIndex", "0");
  });

  it("has role=img for semantic meaning", () => {
    render(<ViabilityBadge level="baixa" score={20} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    expect(badge).toHaveAttribute("role", "img");
  });

  // Renders distinct icon (chart bar, not shield)
  it("contains an SVG icon", () => {
    render(<ViabilityBadge level="alta" score={80} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    const svg = badge.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  // Score display edge cases
  it("handles score of 0", () => {
    render(<ViabilityBadge level="baixa" score={0} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    expect(getTooltipContent(badge)).toContain("Viabilidade: 0/100");
  });

  it("handles score of 100", () => {
    render(<ViabilityBadge level="alta" score={100} factors={mockFactors} />);
    const badge = screen.getByTestId("viability-badge");
    expect(getTooltipContent(badge)).toContain("Viabilidade: 100/100");
  });

  // CRIT-FLT-003 AC3: Tooltip for missing value source
  it("shows missing value warning in tooltip when valueSource is missing", () => {
    render(
      <ViabilityBadge
        level="media"
        score={55}
        factors={mockFactors}
        valueSource="missing"
      />
    );
    const badge = screen.getByTestId("viability-badge");
    expect(getTooltipContent(badge)).toContain(
      "Valor estimado não informado pelo órgão — viabilidade pode ser maior"
    );
  });

  it("does NOT show missing value warning when valueSource is estimated", () => {
    render(
      <ViabilityBadge
        level="alta"
        score={85}
        factors={mockFactors}
        valueSource="estimated"
      />
    );
    const badge = screen.getByTestId("viability-badge");
    expect(getTooltipContent(badge)).not.toContain("não informado pelo órgão");
  });

  it("does NOT show missing value warning when valueSource is null", () => {
    render(
      <ViabilityBadge
        level="alta"
        score={85}
        factors={mockFactors}
        valueSource={null}
      />
    );
    const badge = screen.getByTestId("viability-badge");
    expect(getTooltipContent(badge)).not.toContain("não informado pelo órgão");
  });
});
