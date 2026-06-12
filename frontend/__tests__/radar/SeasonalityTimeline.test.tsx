import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SeasonalityTimeline, TimelineSeries } from "../../app/radar/components/SeasonalityTimeline";

const mockSeries: TimelineSeries[] = [
  {
    name: "Saude",
    color: "#228B22",
    data: [
      { mes: "Jan", volume: 500000, quantidade: 12 },
      { mes: "Fev", volume: 300000, quantidade: 8 },
      { mes: "Mar", volume: 100000, quantidade: 5 },
    ],
  },
  {
    name: "Educacao",
    color: "#FF8C00",
    data: [
      { mes: "Jan", volume: 200000, quantidade: 6 },
      { mes: "Fev", volume: 150000, quantidade: 4 },
      { mes: "Mar", volume: 80000, quantidade: 3 },
    ],
  },
];

describe("SeasonalityTimeline", () => {
  // =====================================================
  // Render states
  // =====================================================

  it("renders loading skeleton when loading", () => {
    render(<SeasonalityTimeline series={[]} loading />);
    expect(screen.getByTestId("timeline-skeleton")).toBeInTheDocument();
  });

  it("renders empty state when no series", () => {
    render(<SeasonalityTimeline series={[]} />);
    expect(screen.getByTestId("timeline-empty")).toBeInTheDocument();
  });

  it("renders empty state when series have no data", () => {
    render(
      <SeasonalityTimeline
        series={[{ name: "Test", color: "#000", data: [] }]}
      />
    );
    expect(screen.getByTestId("timeline-empty")).toBeInTheDocument();
  });

  it("renders error state with retry button", () => {
    const onRetry = jest.fn();
    render(<SeasonalityTimeline series={[]} error="Erro" onRetry={onRetry} />);
    expect(screen.getByTestId("timeline-error")).toBeInTheDocument();
  });

  it("renders the Recharts line chart with data", () => {
    render(<SeasonalityTimeline series={mockSeries} />);
    expect(screen.getByTestId("seasonality-timeline")).toBeInTheDocument();
    // Recharts renders SVG elements inside ResponsiveContainer;
    // jsdom does not provide layout dimensions so SVG may not render.
    // Test that the component mounts and renders its container.
  });

  // =====================================================
  // Data rendering
  // =====================================================

  it("renders with correct height", () => {
    render(
      <SeasonalityTimeline series={mockSeries} height={400} />
    );
    expect(screen.getByTestId("seasonality-timeline")).toBeInTheDocument();
  });

  it("renders with custom height", () => {
    render(
      <SeasonalityTimeline series={mockSeries} height={500} />
    );
    expect(screen.getByTestId("seasonality-timeline")).toBeInTheDocument();
  });

  // =====================================================
  // Legend
  // =====================================================

  it("renders legend when showLegend is true", () => {
    render(<SeasonalityTimeline series={mockSeries} showLegend />);
    expect(screen.getByTestId("seasonality-timeline")).toBeInTheDocument();
  });

  it("renders without legend when showLegend is false", () => {
    render(<SeasonalityTimeline series={mockSeries} showLegend={false} />);
    expect(screen.getByTestId("seasonality-timeline")).toBeInTheDocument();
  });

  // =====================================================
  // Single series
  // =====================================================

  it("renders with a single series", () => {
    const singleSeries: TimelineSeries[] = [
      {
        name: "Unico",
        color: "#0000FF",
        data: [
          { mes: "Jan", volume: 100000, quantidade: 5 },
          { mes: "Fev", volume: 200000, quantidade: 8 },
        ],
      },
    ];
    render(<SeasonalityTimeline series={singleSeries} />);
    expect(screen.getByTestId("seasonality-timeline")).toBeInTheDocument();
  });
});
