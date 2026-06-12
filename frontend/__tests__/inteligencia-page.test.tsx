/**
 * VITRINE-001 (#1612): Tests for /inteligencia/[cnpj] page.
 *
 * Tests the IntelVitrineClient component which handles chart rendering,
 * and validates the response type structure.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import IntelVitrineClient from '../app/inteligencia/[cnpj]/IntelVitrineClient';
import type { IntelVitrineData } from '../app/inteligencia/[cnpj]/page';

// Mock recharts (needs ESM transform in Jest)
jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="bar-chart">{children}</div>
  ),
  Bar: () => <div data-testid="bar" />,
  XAxis: () => <div data-testid="x-axis" />,
  YAxis: () => <div data-testid="y-axis" />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
  LineChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="line-chart">{children}</div>
  ),
  Line: () => <div data-testid="line" />,
  PieChart: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="pie-chart">{children}</div>
  ),
  Pie: () => <div data-testid="pie" />,
  Cell: () => <div />,
}));

const formatBRL = (value: number): string => {
  if (value >= 1_000_000_000) {
    return `R$ ${(value / 1_000_000_000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} bi`;
  }
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mi`;
  }
  if (value >= 1_000) {
    return `R$ ${(value / 1_000).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })} mil`;
  }
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
};

describe('IntelVitrineClient', () => {
  const mockVitrine: IntelVitrineData = {
    cnpj: '12345678000195',
    razao_social: 'EMPRESA EXEMPLO LTDA',
    nome_fantasia: 'Empresa Exemplo',
    setor_principal: 'Construção de edifícios',
    setor_nome: 'Construção Civil',
    total_contratos_12m: 45,
    valor_total_12m: 2500000,
    total_contratos_alltime: 150,
    valor_total_alltime: 15000000,
    ranking: {
      percentil: 95,
      posicao: 50,
      total_empresas_setor: 1000,
      texto_contexto:
        'Esta empresa está entre as top 5% do setor Construção Civil em contratos públicos, com 150 contratos registrados.',
    },
    top_orgaos: [
      {
        nome: 'Prefeitura Municipal de São Paulo',
        cnpj: '12345678000199',
        total_contratos: 50,
        valor_total: 5000000,
      },
      {
        nome: 'Governo do Estado de São Paulo',
        cnpj: '12345678000198',
        total_contratos: 30,
        valor_total: 3000000,
      },
    ],
    distribuicao_uf: [
      { chave: 'SP', quantidade: 80, valor_total: 8000000 },
      { chave: 'RJ', quantidade: 40, valor_total: 4000000 },
      { chave: 'MG', quantidade: 30, valor_total: 3000000 },
    ],
    distribuicao_ano: [
      { chave: '2026', quantidade: 15, valor_total: 1500000 },
      { chave: '2025', quantidade: 45, valor_total: 4500000 },
      { chave: '2024', quantidade: 50, valor_total: 5000000 },
    ],
    distribuicao_modalidade: [],
    generated_at: '2026-06-11T12:00:00Z',
    aviso_legal: 'Dados públicos do PNCP.',
  };

  it('renders charts section with distribution data', () => {
    render(<IntelVitrineClient vitrine={mockVitrine} formatBRL={formatBRL} />);

    expect(screen.getByText('Distribuição de Contratos')).toBeInTheDocument();
    expect(screen.getByText('Contratos por UF')).toBeInTheDocument();
    expect(screen.getByText('Evolução por Ano')).toBeInTheDocument();
  });

  it('renders bar chart for UF distribution', () => {
    render(<IntelVitrineClient vitrine={mockVitrine} formatBRL={formatBRL} />);
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('renders line chart for yearly distribution', () => {
    render(<IntelVitrineClient vitrine={mockVitrine} formatBRL={formatBRL} />);
    expect(screen.getByTestId('line-chart')).toBeInTheDocument();
  });

  it('does not render pie chart when modalidade data is empty', () => {
    render(<IntelVitrineClient vitrine={mockVitrine} formatBRL={formatBRL} />);
    expect(screen.queryByTestId('pie-chart')).not.toBeInTheDocument();
  });

  it('renders pie chart when modalidade data is present', () => {
    const vitrineWithModalidade: IntelVitrineData = {
      ...mockVitrine,
      distribuicao_modalidade: [
        { chave: 'Concorrência', quantidade: 60, valor_total: 6000000 },
        { chave: 'Dispensa', quantidade: 40, valor_total: 4000000 },
        { chave: 'Pregão', quantidade: 50, valor_total: 5000000 },
      ],
    };
    render(
      <IntelVitrineClient
        vitrine={vitrineWithModalidade}
        formatBRL={formatBRL}
      />,
    );
    expect(screen.getByTestId('pie-chart')).toBeInTheDocument();
  });

  it('renders nothing when no distribution data', () => {
    const emptyVitrine: IntelVitrineData = {
      ...mockVitrine,
      distribuicao_uf: [],
      distribuicao_ano: [],
      distribuicao_modalidade: [],
    };
    const { container } = render(
      <IntelVitrineClient vitrine={emptyVitrine} formatBRL={formatBRL} />,
    );
    expect(container.firstChild).toBeNull();
  });
});

describe('IntelVitrineData type and formatting', () => {
  const mockFullData: IntelVitrineData = {
    cnpj: '12345678000195',
    razao_social: 'TESTE LTDA',
    nome_fantasia: null,
    setor_principal: null,
    setor_nome: null,
    total_contratos_12m: 0,
    valor_total_12m: 0,
    total_contratos_alltime: 0,
    valor_total_alltime: 0,
    ranking: null,
    top_orgaos: [],
    distribuicao_uf: [],
    distribuicao_ano: [],
    distribuicao_modalidade: [],
    generated_at: '2026-06-11T12:00:00Z',
    aviso_legal: '',
  };

  it('handles null optional fields correctly', () => {
    // Should not throw when rendered with null fields
    expect(() =>
      render(<IntelVitrineClient vitrine={mockFullData} formatBRL={formatBRL} />),
    ).not.toThrow();
  });

  it('formatBRL handles billions', () => {
    expect(formatBRL(1_500_000_000)).toBe('R$ 1,5 bi');
  });

  it('formatBRL handles millions', () => {
    expect(formatBRL(2_500_000)).toBe('R$ 2,5 mi');
  });

  it('formatBRL handles thousands', () => {
    expect(formatBRL(500_000)).toBe('R$ 500 mil');
  });

  it('formatBRL handles small values', () => {
    const result = formatBRL(1500);
    // 1500 / 1000 = 1.5, rounded to 0 decimal places = 2
    expect(result).toContain('R$');
    expect(result).toContain('mil');
  });

  it('formatBRL handles exact currency', () => {
    const result = formatBRL(999);
    expect(result).toContain('R$');
    expect(result).toContain('999');
  });
});
