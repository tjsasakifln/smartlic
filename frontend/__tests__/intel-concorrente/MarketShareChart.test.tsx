import { render, screen } from '@testing-library/react';
import MarketShareChart from '@/app/intel-concorrente/components/MarketShareChart';

// Recharts ResponsiveContainer has 0-width in jsdom → chart labels invisible.
// Mock to inject fixed width/height into the child chart element,
// matching real ResponsiveContainer behavior (React.cloneElement).
jest.mock('recharts', () => {
  const actual = jest.requireActual('recharts');
  const React = require('react');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => {
      if (React.isValidElement(children)) {
        return React.cloneElement(children, { width: 600, height: 300 });
      }
      return children;
    },
  };
});

describe('MarketShareChart', () => {
  it('renders empty state when no competitors', () => {
    render(<MarketShareChart competitors={[]} />);

    expect(screen.getByText(/Market Share por Concorrente/)).toBeInTheDocument();
    expect(
      screen.getByText(/Selecione um setor/)
    ).toBeInTheDocument();
  });

  it('renders chart with competitor data', () => {
    const competitors = [
      { razao_social: 'Empresa A', market_share: 35.0, total_contratado: 350000 },
      { razao_social: 'Empresa B', market_share: 25.0, total_contratado: 250000 },
      { razao_social: 'Empresa C', market_share: 15.0, total_contratado: 150000 },
    ];

    render(<MarketShareChart competitors={competitors} />);

    expect(screen.getByText(/Market Share por Concorrente/)).toBeInTheDocument();
    // The chart should render with Recharts
    expect(screen.getByText('Empresa A')).toBeInTheDocument();
    expect(screen.getByText('Empresa B')).toBeInTheDocument();
    expect(screen.getByText('Empresa C')).toBeInTheDocument();
  });

  it('limits to top 10 competitors', () => {
    const competitors = Array.from({ length: 15 }, (_, i) => ({
      razao_social: `Empresa ${i}`,
      market_share: 10 - i * 0.5,
      total_contratado: 100000 - i * 5000,
    }));

    render(<MarketShareChart competitors={competitors} />);

    // Should show top 10
    expect(screen.getByText('Empresa 0')).toBeInTheDocument();
    expect(screen.getByText('Empresa 9')).toBeInTheDocument();
  });
});
