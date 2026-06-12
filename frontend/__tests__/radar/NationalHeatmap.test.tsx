import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { NationalHeatmap, UfHeatmapData } from "../../app/radar/components/NationalHeatmap";

const mockData: UfHeatmapData[] = [
  {
    uf: "SP",
    volume_previsto: 2500000,
    quantidade_prevista: 45,
    orgaos_principais: ["Governo SP", "Prefeitura SP"],
    categorias_principais: ["Saude", "Educacao"],
    valor_estimado: 2500000,
    confidence: 85,
  },
  {
    uf: "RJ",
    volume_previsto: 1500000,
    quantidade_prevista: 30,
    orgaos_principais: ["Governo RJ"],
    categorias_principais: ["Infraestrutura"],
    valor_estimado: 1500000,
    confidence: 72,
  },
  {
    uf: "MG",
    volume_previsto: 800000,
    quantidade_prevista: 20,
    orgaos_principais: ["Governo MG"],
    categorias_principais: ["Seguranca"],
    valor_estimado: 800000,
    confidence: 45,
  },
];

describe("NationalHeatmap", () => {
  // =====================================================
  // Render states
  // =====================================================

  it("renders loading skeleton when loading", () => {
    render(<NationalHeatmap data={[]} loading />);
    expect(screen.getByTestId("heatmap-skeleton")).toBeInTheDocument();
  });

  it("renders empty state when no data", () => {
    render(<NationalHeatmap data={[]} />);
    expect(screen.getByTestId("heatmap-empty")).toBeInTheDocument();
  });

  it("renders error state with retry button", () => {
    const onRetry = jest.fn();
    render(<NationalHeatmap data={[]} error="Erro" onRetry={onRetry} />);
    expect(screen.getByTestId("heatmap-error")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Tentar novamente"));
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders SVG map with data", () => {
    render(<NationalHeatmap data={mockData} />);
    expect(screen.getByTestId("national-heatmap")).toBeInTheDocument();
    expect(screen.getByTestId("brazil-heatmap-svg")).toBeInTheDocument();
  });

  it("renders all 27 state paths in SVG", () => {
    render(<NationalHeatmap data={mockData} />);
    const paths = document.querySelectorAll('[data-testid="brazil-heatmap-svg"] path');
    expect(paths.length).toBe(27);
  });

  it("renders UF labels on the map", () => {
    render(<NationalHeatmap data={mockData} />);
    const svg = screen.getByTestId("brazil-heatmap-svg");
    expect(svg).toBeInTheDocument();
    // Check that SP label appears in text elements
    const texts = svg.querySelectorAll("text");
    expect(texts.length).toBe(27);
  });

  // =====================================================
  // UFs without data
  // =====================================================

  it("renders all UFs even when data is partial", () => {
    render(<NationalHeatmap data={[mockData[0]]} />);
    const paths = document.querySelectorAll('[data-testid="brazil-heatmap-svg"] path');
    expect(paths.length).toBe(27);
  });

  // =====================================================
  // Filters
  // =====================================================

  it("renders sector filter when availableSectors provided", () => {
    render(
      <NationalHeatmap
        data={mockData}
        availableSectors={["Saude", "Educacao"]}
        onSectorChange={jest.fn()}
      />
    );
    expect(screen.getByTestId("heatmap-filter-sectors")).toBeInTheDocument();
  });

  it("renders month filter when onMesChange provided", () => {
    render(
      <NationalHeatmap
        data={mockData}
        onMesChange={jest.fn()}
      />
    );
    expect(screen.getByTestId("heatmap-filter-mes")).toBeInTheDocument();
  });

  it("calls onMesChange when month changes", () => {
    const onMesChange = jest.fn();
    render(<NationalHeatmap data={mockData} onMesChange={onMesChange} />);
    const mesSelect = screen.getByTestId("heatmap-filter-mes");
    fireEvent.change(mesSelect, { target: { value: "3" } });
    expect(onMesChange).toHaveBeenCalledWith(3);
  });

  // =====================================================
  // Interactions
  // =====================================================

  it("shows tooltip on state hover", () => {
    render(<NationalHeatmap data={mockData} />);
    const svg = screen.getByTestId("brazil-heatmap-svg");
    const spPath = svg.querySelector('[data-uf="SP"]');
    expect(spPath).toBeInTheDocument();
    fireEvent.mouseEnter(spPath!);
    expect(screen.getByTestId("heatmap-tooltip")).toBeInTheDocument();
    expect(screen.getAllByText("SP").length).toBeGreaterThan(0);
  });

  it("hides tooltip on state leave", () => {
    render(<NationalHeatmap data={mockData} />);
    const svg = screen.getByTestId("brazil-heatmap-svg");
    const spPath = svg.querySelector('[data-uf="SP"]');
    fireEvent.mouseEnter(spPath!);
    expect(screen.getByTestId("heatmap-tooltip")).toBeInTheDocument();
    fireEvent.mouseLeave(spPath!);
    expect(screen.queryByTestId("heatmap-tooltip")).not.toBeInTheDocument();
  });

  it("calls onUfClick when state is clicked", () => {
    const onUfClick = jest.fn();
    render(<NationalHeatmap data={mockData} onUfClick={onUfClick} />);
    const svg = screen.getByTestId("brazil-heatmap-svg");
    const spPath = svg.querySelector('[data-uf="SP"]');
    fireEvent.click(spPath!);
    expect(onUfClick).toHaveBeenCalledWith("SP");
  });

  // =====================================================
  // Accessibility
  // =====================================================

  it("has aria-label on SVG map", () => {
    render(<NationalHeatmap data={mockData} />);
    expect(screen.getByTestId("brazil-heatmap-svg")).toHaveAttribute("aria-label");
  });

  it("has aria-label on each state path", () => {
    render(<NationalHeatmap data={mockData} />);
    const svg = screen.getByTestId("brazil-heatmap-svg");
    const paths = svg.querySelectorAll("path");
    paths.forEach((path) => {
      expect(path).toHaveAttribute("aria-label");
    });
  });
});
