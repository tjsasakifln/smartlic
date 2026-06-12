/**
 * VITRINE-001 (#1612): Tests for PublicContractsList component.
 */

import { render, screen } from '@testing-library/react';
import PublicContractsList from '@/app/inteligencia/[cnpj]/components/PublicContractsList';
import type { OrgaoInfoVitrine } from '@/app/inteligencia/[cnpj]/page';

const mockOrgaos: OrgaoInfoVitrine[] = [
  {
    nome: 'Prefeitura Municipal de Sao Paulo',
    cnpj: '11222333000181',
    total_contratos: 20,
    valor_total: 1000000.0,
  },
  {
    nome: 'Governo do Estado de SP',
    cnpj: '99888777000155',
    total_contratos: 15,
    valor_total: 750000.0,
  },
];

const formatBRL = (value: number): string => {
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toFixed(1)} mi`;
  }
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
};

describe('PublicContractsList', () => {
  it('renders top orgaos', () => {
    render(
      <PublicContractsList topOrgaos={mockOrgaos} formatBRL={formatBRL} />,
    );
    expect(screen.getByText('Prefeitura Municipal de Sao Paulo')).toBeTruthy();
    expect(screen.getByText('Governo do Estado de SP')).toBeTruthy();
  });

  it('renders contract counts', () => {
    render(
      <PublicContractsList topOrgaos={mockOrgaos} formatBRL={formatBRL} />,
    );
    expect(screen.getByText('20 contratos')).toBeTruthy();
    expect(screen.getByText('15 contratos')).toBeTruthy();
  });

  it('returns null for empty list', () => {
    const { container } = render(
      <PublicContractsList topOrgaos={[]} formatBRL={formatBRL} />,
    );
    expect(container.innerHTML).toBe('');
  });
});
