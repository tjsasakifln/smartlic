import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SeasonalCalendar, SectorSeasonality } from "../../app/radar/components/SeasonalCalendar";

const mockSectors: SectorSeasonality[] = [
  {
    setor: "Saude",
    meses: [
      { mes: 1, volume_medio: 500000, quantidade_media: 12, setor_dominante: "Saude", orgaos_principais: ["Prefeitura SP", "Governo SP"], indice_sazonalidade: 0.45, tendencia: "crescimento", variacao_anual: 0.12 },
      { mes: 2, volume_medio: 300000, quantidade_media: 8, setor_dominante: "Saude", orgaos_principais: ["Prefeitura SP"], indice_sazonalidade: 0.2, tendencia: "estabilidade", variacao_anual: -0.05 },
      { mes: 3, volume_medio: 100000, quantidade_media: 5, setor_dominante: "Saude", orgaos_principais: [], indice_sazonalidade: 0.05, tendencia: "declinio", variacao_anual: -0.1 },
    ],
  },
  {
    setor: "Educacao",
    meses: [
      { mes: 1, volume_medio: 200000, quantidade_media: 6, setor_dominante: "Educacao", orgaos_principais: ["MEC"], indice_sazonalidade: 0.3, tendencia: "crescimento", variacao_anual: 0.08 },
      { mes: 2, volume_medio: 150000, quantidade_media: 4, setor_dominante: "Educacao", orgaos_principais: ["Secretaria SP"], indice_sazonalidade: 0.15, tendencia: "estabilidade", variacao_anual: 0.02 },
      { mes: 3, volume_medio: 80000, quantidade_media: 3, setor_dominante: "Educacao", orgaos_principais: [], indice_sazonalidade: 0.05, tendencia: "declinio", variacao_anual: -0.03 },
    ],
  },
];

describe("SeasonalCalendar", () => {
  // =====================================================
  // Render states
  // =====================================================

  it("renders loading skeleton when loading", () => {
    render(<SeasonalCalendar data={[]} loading />);
    expect(screen.getByTestId("calendar-skeleton")).toBeInTheDocument();
  });

  it("renders empty state when no data", () => {
    render(<SeasonalCalendar data={[]} />);
    expect(screen.getByTestId("calendar-empty")).toBeInTheDocument();
  });

  it("renders error state with retry button", () => {
    const onRetry = jest.fn();
    render(<SeasonalCalendar data={[]} error="Erro" onRetry={onRetry} />);
    expect(screen.getByTestId("calendar-error")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Tentar novamente"));
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders the heatmap grid with data", () => {
    render(<SeasonalCalendar data={mockSectors} />);
    expect(screen.getByTestId("seasonal-calendar")).toBeInTheDocument();
    expect(screen.getByText("Saude")).toBeInTheDocument();
    expect(screen.getByText("Educacao")).toBeInTheDocument();
  });

  // =====================================================
  // Filters
  // =====================================================

  it("renders UF filter when availableUfs provided", () => {
    render(
      <SeasonalCalendar
        data={mockSectors}
        availableUfs={["SP", "RJ", "MG"]}
        onUfChange={jest.fn()}
      />
    );
    expect(screen.getByTestId("filter-uf")).toBeInTheDocument();
    expect(screen.getByText("SP")).toBeInTheDocument();
    expect(screen.getByText("RJ")).toBeInTheDocument();
  });

  it("renders year filter when onYearChange provided", () => {
    render(
      <SeasonalCalendar
        data={mockSectors}
        onYearChange={jest.fn()}
      />
    );
    expect(screen.getByTestId("filter-year")).toBeInTheDocument();
  });

  it("calls onUfChange when UF filter changes", () => {
    const onUfChange = jest.fn();
    render(
      <SeasonalCalendar
        data={mockSectors}
        availableUfs={["SP", "RJ"]}
        onUfChange={onUfChange}
      />
    );
    fireEvent.change(screen.getByTestId("filter-uf"), { target: { value: "RJ" } });
    expect(onUfChange).toHaveBeenCalledWith("RJ");
  });

  it("calls onYearChange when year filter changes", () => {
    const onYearChange = jest.fn();
    render(<SeasonalCalendar data={mockSectors} onYearChange={onYearChange} />);
    const yearSelect = screen.getByTestId("filter-year");
    const currentYear = new Date().getFullYear();
    fireEvent.change(yearSelect, { target: { value: String(currentYear - 1) } });
    expect(onYearChange).toHaveBeenCalledWith(currentYear - 1);
  });

  it("filters sectors by selectedSectors", () => {
    render(
      <SeasonalCalendar
        data={mockSectors}
        selectedSectors={["Saude"]}
      />
    );
    expect(screen.getByText("Saude")).toBeInTheDocument();
    expect(screen.queryByText("Educacao")).not.toBeInTheDocument();
  });

  // =====================================================
  // Interactions
  // =====================================================

  it("shows tooltip on cell hover", () => {
    render(<SeasonalCalendar data={mockSectors} />);
    const cells = screen.getAllByRole("button");
    expect(cells.length).toBeGreaterThan(0);
    fireEvent.mouseEnter(cells[0]);
    expect(screen.getByTestId("calendar-tooltip")).toBeInTheDocument();
  });

  it("hides tooltip on cell leave", () => {
    render(<SeasonalCalendar data={mockSectors} />);
    const cells = screen.getAllByRole("button");
    fireEvent.mouseEnter(cells[0]);
    expect(screen.getByTestId("calendar-tooltip")).toBeInTheDocument();
    fireEvent.mouseLeave(cells[0]);
    expect(screen.queryByTestId("calendar-tooltip")).not.toBeInTheDocument();
  });

  it("opens modal on cell click", () => {
    render(<SeasonalCalendar data={mockSectors} />);
    const cells = screen.getAllByRole("button");
    fireEvent.click(cells[0]);
    expect(screen.getByTestId("calendar-detail-modal")).toBeInTheDocument();
  });

  it("closes modal on close button click", () => {
    render(<SeasonalCalendar data={mockSectors} />);
    const cells = screen.getAllByRole("button");
    fireEvent.click(cells[0]);
    expect(screen.getByTestId("calendar-detail-modal")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Fechar"));
    expect(screen.queryByTestId("calendar-detail-modal")).not.toBeInTheDocument();
  });

  // =====================================================
  // Accessibility
  // =====================================================

  it("has accessible aria-labels on cells", () => {
    render(<SeasonalCalendar data={mockSectors} />);
    const cells = screen.getAllByRole("button");
    cells.forEach((cell) => {
      expect(cell).toHaveAttribute("aria-label");
    });
  });

  it("has accessible modal with aria-modal", () => {
    render(<SeasonalCalendar data={mockSectors} />);
    const cells = screen.getAllByRole("button");
    fireEvent.click(cells[0]);
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
  });
});
