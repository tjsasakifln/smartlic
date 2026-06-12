/**
 * VITRINE-001 (#1612): Tests for SectorPosition component.
 */

import { render, screen } from '@testing-library/react';
import SectorPosition from '@/app/inteligencia/[cnpj]/components/SectorPosition';
import type { RankingInfoVitrine } from '@/app/inteligencia/[cnpj]/page';

const mockRanking: RankingInfoVitrine = {
  percentil: 95.0,
  posicao: 50,
  total_empresas_setor: 1000,
  texto_contexto:
    'Esta empresa está entre as top 5% do setor Construção em contratos públicos, com 50 contratos registrados.',
};

describe('SectorPosition', () => {
  it('renders ranking info when provided', () => {
    render(<SectorPosition ranking={mockRanking} />);
    expect(
      screen.getByText(/top 5% do setor Construção/),
    ).toBeTruthy();
  });

  it('renders section title', () => {
    render(<SectorPosition ranking={mockRanking} />);
    expect(screen.getByText('Ranking Setorial')).toBeTruthy();
  });

  it('renders comparison text with company count', () => {
    render(<SectorPosition ranking={mockRanking} />);
    expect(
      screen.getByText(/1\.000 empresas do mesmo setor/),
    ).toBeTruthy();
  });

  it('returns null when ranking is null', () => {
    const { container } = render(<SectorPosition ranking={null} />);
    expect(container.innerHTML).toBe('');
  });
});
