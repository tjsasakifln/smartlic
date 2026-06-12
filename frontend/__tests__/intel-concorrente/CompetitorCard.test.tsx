import { render, screen } from '@testing-library/react';
import CompetitorCard from '@/app/intel-concorrente/components/CompetitorCard';

describe('CompetitorCard', () => {
  const defaultProps = {
    razao_social: 'Empresa Teste Ltda',
    cnpj: '12.345.678/0001-95',
    total_contratado: 1000000.0,
    total_contratos: 50,
    ufs_count: 5,
    tendencia: 'crescimento',
  };

  it('renders company name and CNPJ', () => {
    render(<CompetitorCard {...defaultProps} />);

    expect(screen.getByText('Empresa Teste Ltda')).toBeInTheDocument();
    expect(screen.getByText(/CNPJ: 12\.345\.678\/0001-95/)).toBeInTheDocument();
  });

  it('renders financial metrics', () => {
    render(<CompetitorCard {...defaultProps} />);

    expect(screen.getByText(/Total Contratado/)).toBeInTheDocument();
    expect(screen.getByText('R$ 1.000.000,00')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('renders trend badge for crescimento', () => {
    render(<CompetitorCard {...defaultProps} />);

    expect(screen.getByText('Em expansao')).toBeInTheDocument();
  });

  it('renders trend badge for retracao', () => {
    render(<CompetitorCard {...{ ...defaultProps, tendencia: 'retracao' }} />);

    expect(screen.getByText('Em retracao')).toBeInTheDocument();
  });

  it('renders trend badge for estavel', () => {
    render(<CompetitorCard {...{ ...defaultProps, tendencia: 'estavel' }} />);

    expect(screen.getByText('Estavel')).toBeInTheDocument();
  });
});
