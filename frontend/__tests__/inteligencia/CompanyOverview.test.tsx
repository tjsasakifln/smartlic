/**
 * VITRINE-001 (#1612): Tests for CompanyOverview component.
 */

import { render, screen } from '@testing-library/react';
import CompanyOverview from '@/app/inteligencia/[cnpj]/components/CompanyOverview';
import type { IntelVitrineData } from '@/app/inteligencia/[cnpj]/page';

const mockVitrine: IntelVitrineData = {
  cnpj: '12345678901234',
  razao_social: 'Empresa Teste Ltda',
  nome_fantasia: 'Teste',
  setor_principal: 'Construção',
  setor_nome: 'Construção Civil',
  total_contratos_12m: 10,
  valor_total_12m: 500000.0,
  total_contratos_alltime: 50,
  valor_total_alltime: 2500000.0,
  ranking: null,
  top_orgaos: [],
  distribuicao_uf: [],
  distribuicao_ano: [],
  distribuicao_modalidade: [],
  generated_at: '2026-06-12T00:00:00',
  aviso_legal: 'Aviso legal de teste.',
};

const formatBRL = (value: number): string => {
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toFixed(1)} mi`;
  }
  if (value >= 1_000) {
    return `R$ ${(value / 1_000).toFixed(0)} mil`;
  }
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
};

describe('CompanyOverview', () => {
  it('renders company name', () => {
    render(
      <CompanyOverview
        vitrine={mockVitrine}
        formatBRL={formatBRL}
        cnpjMasked="12.345.678/9012-34"
      />,
    );
    expect(screen.getByText('Empresa Teste Ltda')).toBeTruthy();
  });

  it('renders KPI cards with contract counts', () => {
    render(
      <CompanyOverview
        vitrine={mockVitrine}
        formatBRL={formatBRL}
        cnpjMasked="12.345.678/9012-34"
      />,
    );
    expect(screen.getByText('10')).toBeTruthy();
    expect(screen.getByText('50')).toBeTruthy();
  });

  it('renders sector badge when available', () => {
    render(
      <CompanyOverview
        vitrine={mockVitrine}
        formatBRL={formatBRL}
        cnpjMasked="12.345.678/9012-34"
      />,
    );
    expect(screen.getByText('Construção Civil')).toBeTruthy();
  });

  it('renders CNPJ masked', () => {
    render(
      <CompanyOverview
        vitrine={mockVitrine}
        formatBRL={formatBRL}
        cnpjMasked="12.345.678/9012-34"
      />,
    );
    expect(screen.getByText(/12\.345\.678\/9012-34/)).toBeTruthy();
  });

  it('handles missing nome_fantasia', () => {
    const vitrineSemFantasia = { ...mockVitrine, nome_fantasia: null };
    render(
      <CompanyOverview
        vitrine={vitrineSemFantasia}
        formatBRL={formatBRL}
        cnpjMasked="12.345.678/9012-34"
      />,
    );
    // Should still render company name
    expect(screen.getByText('Empresa Teste Ltda')).toBeTruthy();
  });

  it('handles missing sector', () => {
    const vitrineSemSetor = { ...mockVitrine, setor_nome: null };
    render(
      <CompanyOverview
        vitrine={vitrineSemSetor}
        formatBRL={formatBRL}
        cnpjMasked="12.345.678/9012-34"
      />,
    );
    // CNPJ without setor should still render
    expect(screen.getByText('Empresa Teste Ltda')).toBeTruthy();
  });
});
