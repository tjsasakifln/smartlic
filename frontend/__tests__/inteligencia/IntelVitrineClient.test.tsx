/**
 * VITRINE-001 (#1612): Tests for IntelVitrineClient (charts) component.
 */

import { render, screen } from '@testing-library/react';
import IntelVitrineClient from '@/app/inteligencia/[cnpj]/IntelVitrineClient';
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
  distribuicao_uf: [
    { chave: 'SP', quantidade: 30, valor_total: 1500000.0 },
    { chave: 'RJ', quantidade: 10, valor_total: 500000.0 },
    { chave: 'MG', quantidade: 5, valor_total: 250000.0 },
  ],
  distribuicao_ano: [
    { chave: '2025', quantidade: 20, valor_total: 1000000.0 },
    { chave: '2026', quantidade: 30, valor_total: 1500000.0 },
  ],
  distribuicao_modalidade: [
    { chave: 'Pregão', quantidade: 40, valor_total: 2000000.0 },
    { chave: 'Dispensa', quantidade: 10, valor_total: 500000.0 },
  ],
  generated_at: '2026-06-12T00:00:00',
  aviso_legal: 'Aviso legal de teste.',
};

const formatBRL = (value: number): string => {
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toFixed(1)} mi`;
  }
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
};

describe('IntelVitrineClient', () => {
  it('renders distribution section title', () => {
    render(
      <IntelVitrineClient vitrine={mockVitrine} formatBRL={formatBRL} />,
    );
    expect(screen.getByText('Distribuição de Contratos')).toBeTruthy();
  });

  it('renders chart sub-titles when data available', () => {
    render(
      <IntelVitrineClient vitrine={mockVitrine} formatBRL={formatBRL} />,
    );
    expect(screen.getByText('Contratos por UF')).toBeTruthy();
    expect(screen.getByText('Evolução por Ano')).toBeTruthy();
    expect(screen.getByText('Distribuição por Modalidade')).toBeTruthy();
  });

  it('renders nothing when no chart data', () => {
    const emptyVitrine = {
      ...mockVitrine,
      distribuicao_uf: [],
      distribuicao_ano: [],
      distribuicao_modalidade: [],
    };
    const { container } = render(
      <IntelVitrineClient vitrine={emptyVitrine} formatBRL={formatBRL} />,
    );
    expect(container.innerHTML).toBe('');
  });
});
