/**
 * Tests for AhaMomentPanel component (CONV-004).
 *
 * Verifies:
 * - Renders correct number of insight cards
 * - Renders icon, label, value, subtext
 * - Grid layout classes
 * - Returns null for empty insights
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import AhaMomentPanel from '../app/components/conversion/AhaMomentPanel';

const mockInsights = [
  {
    label: 'Contratos ativos',
    value: '47',
    subtext: 'Últimos 12 meses',
    icon: 'chart' as const,
  },
  {
    label: 'Valor total',
    value: 'R$ 12,5M',
    subtext: 'Média R$ 266k',
    icon: 'money' as const,
  },
  {
    label: 'Órgãos atendidos',
    value: '23',
    subtext: 'Em 5 estados',
    icon: 'building' as const,
  },
  {
    label: 'Taxa de sucesso',
    value: '73%',
    subtext: 'vs 58% média do setor',
    icon: 'target' as const,
  },
];

describe('AhaMomentPanel', () => {
  it('renders correct number of insight cards', () => {
    render(
      <AhaMomentPanel entityType="fornecedor" insights={mockInsights} />,
    );
    // 4 cards rendered
    expect(screen.getByText('47')).toBeInTheDocument();
    expect(screen.getByText('R$ 12,5M')).toBeInTheDocument();
    expect(screen.getByText('23')).toBeInTheDocument();
    expect(screen.getByText('73%')).toBeInTheDocument();
  });

  it('renders labels for all insights', () => {
    render(
      <AhaMomentPanel entityType="fornecedor" insights={mockInsights} />,
    );
    expect(screen.getByText('Contratos ativos')).toBeInTheDocument();
    expect(screen.getByText('Valor total')).toBeInTheDocument();
    expect(screen.getByText('Órgãos atendidos')).toBeInTheDocument();
    expect(screen.getByText('Taxa de sucesso')).toBeInTheDocument();
  });

  it('renders subtext for insights that have it', () => {
    render(
      <AhaMomentPanel entityType="fornecedor" insights={mockInsights} />,
    );
    expect(screen.getByText('Últimos 12 meses')).toBeInTheDocument();
    expect(screen.getByText('Média R$ 266k')).toBeInTheDocument();
    expect(screen.getByText('Em 5 estados')).toBeInTheDocument();
    expect(screen.getByText('vs 58% média do setor')).toBeInTheDocument();
  });

  it('renders icons for insights', () => {
    render(
      <AhaMomentPanel entityType="fornecedor" insights={mockInsights} />,
    );
    // Emoji icons rendered with aria-hidden
    const icons = screen.getAllByRole('img', { hidden: true });
    expect(icons).toHaveLength(4);
    expect(icons[0]).toHaveTextContent('📊');
    expect(icons[1]).toHaveTextContent('💰');
    expect(icons[2]).toHaveTextContent('🏛️');
    expect(icons[3]).toHaveTextContent('🎯');
  });

  it('renders grid layout classes', () => {
    const { container } = render(
      <AhaMomentPanel entityType="fornecedor" insights={mockInsights} />,
    );
    const grid = container.querySelector('.grid');
    expect(grid).toHaveClass('grid-cols-2');
    expect(grid).toHaveClass('md:grid-cols-4');
  });

  it('renders section with aria-label', () => {
    render(
      <AhaMomentPanel entityType="fornecedor" insights={mockInsights} />,
    );
    expect(
      screen.getByRole('region', { name: 'Insights' }),
    ).toBeInTheDocument();
  });

  it('returns null for empty insights array', () => {
    const { container } = render(
      <AhaMomentPanel entityType="fornecedor" insights={[]} />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('works with 2 insights', () => {
    const twoInsights = mockInsights.slice(0, 2);
    render(
      <AhaMomentPanel entityType="orgao" insights={twoInsights} />,
    );
    expect(screen.getByText('Contratos ativos')).toBeInTheDocument();
    expect(screen.getByText('Valor total')).toBeInTheDocument();
    expect(screen.queryByText('Órgãos atendidos')).toBeNull();
  });

  it('renders with entityType setor', () => {
    render(
      <AhaMomentPanel
        entityType="setor"
        insights={[{ label: 'Editais', value: '1.234', icon: 'target' }]}
      />,
    );
    expect(screen.getByText('Editais')).toBeInTheDocument();
    expect(screen.getByText('1.234')).toBeInTheDocument();
  });
});
