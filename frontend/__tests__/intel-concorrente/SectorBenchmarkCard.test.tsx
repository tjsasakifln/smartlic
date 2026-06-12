import { render, screen } from '@testing-library/react';
import SectorBenchmarkCard from '@/app/intel-concorrente/components/SectorBenchmarkCard';

describe('SectorBenchmarkCard', () => {
  const metricas = [
    {
      metrica: 'ticket_medio',
      label: 'Ticket Medio',
      valor_concorrente: 50000.0,
      percentil_concorrente: 65,
      benchmark_setor: {
        p25: 10000.0,
        p50: 30000.0,
        p75: 80000.0,
      },
      descricao: 'Este player esta no percentil 65 de ticket medio.',
    },
  ];

  it('renders nothing when metricas is empty', () => {
    const { container } = render(<SectorBenchmarkCard metricas={[]} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders benchmark card with metrics', () => {
    render(<SectorBenchmarkCard metricas={metricas} />);

    expect(screen.getByText('Benchmark Setorial')).toBeInTheDocument();
    expect(screen.getByText('Ticket Medio')).toBeInTheDocument();
    expect(screen.getByText(/P65/)).toBeInTheDocument();
  });

  it('renders sector percentiles', () => {
    render(<SectorBenchmarkCard metricas={metricas} />);

    expect(screen.getByText('P25 (Setor)')).toBeInTheDocument();
    expect(screen.getByText('P50 (Mediana)')).toBeInTheDocument();
    expect(screen.getByText('P75 (Setor)')).toBeInTheDocument();
  });

  it('renders description tooltip', () => {
    render(<SectorBenchmarkCard metricas={metricas} />);

    expect(
      screen.getByText(/Este player esta no percentil 65/)
    ).toBeInTheDocument();
  });

  it('renders multiple metrics', () => {
    const multiMetrics = [
      ...metricas,
      {
        metrica: 'total_contratos',
        label: 'Total de Contratos',
        valor_concorrente: 50,
        percentil_concorrente: 80,
        benchmark_setor: {
          p25: 10,
          p50: 30,
          p75: 70,
        },
        descricao: 'Acima da media do setor.',
      },
    ];

    render(<SectorBenchmarkCard metricas={multiMetrics} />);

    expect(screen.getByText('Ticket Medio')).toBeInTheDocument();
    expect(screen.getByText('Total de Contratos')).toBeInTheDocument();
  });
});
