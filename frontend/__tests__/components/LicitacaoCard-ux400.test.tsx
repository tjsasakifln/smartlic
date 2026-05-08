/**
 * UX-400: Tests for link fallback, source badge, edital number, and CNPJ display.
 *
 * AC3: Disabled button when link is null/empty with tooltip
 * AC4: Source badge renders for each data source
 * AC5: Edital number displayed below title
 * AC6: CNPJ formatted next to orgao
 * AC7: No <a href=""> in DOM when link unavailable
 */

import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { LicitacaoCard } from '@/app/components/LicitacaoCard';
import type { LicitacaoItem } from '@/app/types';

function makeLicitacao(overrides: Partial<LicitacaoItem> = {}): LicitacaoItem {
  return {
    pncp_id: "12345678000190-1-000001/2026",
    objeto: "Aquisição de materiais de escritório",
    orgao: "Prefeitura de São Paulo",
    uf: "SP",
    municipio: "São Paulo",
    valor: 150000,
    modalidade: "Pregão Eletrônico",
    data_publicacao: "2026-03-01",
    data_abertura: null,
    data_encerramento: null,
    link: "https://pncp.gov.br/app/editais/12345678000190/2026/1",
    ...overrides,
  };
}

// =============================================================================
// AC3 + AC7: Disabled button for null/empty link
// =============================================================================

describe('UX-400 AC3+AC7: Link disabled state', () => {
  it('renders clickable link when link is a valid URL', () => {
    render(<LicitacaoCard licitacao={makeLicitacao()} />);
    const link = screen.getByRole('link', { name: /ver edital/i });
    expect(link).toHaveAttribute('href', 'https://pncp.gov.br/app/editais/12345678000190/2026/1');
    expect(link).not.toHaveClass('opacity-50');
  });

  it('AC3: shows disabled button with tooltip when link is null', () => {
    render(<LicitacaoCard licitacao={makeLicitacao({ link: null })} />);

    // Should not render an <a> tag
    const links = screen.queryAllByRole('link', { name: /ver edital/i });
    expect(links).toHaveLength(0);

    // Should render disabled span
    const disabledBtn = screen.getByRole('button', { name: /ver edital/i });
    expect(disabledBtn).toHaveAttribute('aria-disabled', 'true');
    expect(disabledBtn).toHaveClass('opacity-50');
    expect(disabledBtn).toHaveClass('cursor-not-allowed');
  });

  it('AC7: no <a href=""> exists in DOM when link is empty string', () => {
    const { container } = render(
      <LicitacaoCard licitacao={makeLicitacao({ link: "" as unknown as null })} />
    );

    // No anchor tags with empty href
    const emptyLinks = container.querySelectorAll('a[href=""]');
    expect(emptyLinks).toHaveLength(0);
  });

  it('AC7: no <a href=""> exists in DOM when link is null', () => {
    const { container } = render(
      <LicitacaoCard licitacao={makeLicitacao({ link: null })} />
    );

    const emptyLinks = container.querySelectorAll('a[href=""]');
    expect(emptyLinks).toHaveLength(0);
  });
});

// =============================================================================
// AC4: Source badge
// =============================================================================

describe('UX-400 AC4: Source badge', () => {
  it('renders PNCP badge when _source is PNCP', () => {
    render(<LicitacaoCard licitacao={makeLicitacao({ _source: "PNCP" })} />);
    const badge = screen.getByTestId('source-badge');
    expect(badge).toHaveTextContent('Fontes Oficiais');
  });

  it('renders PCP badge when _source is PCP', () => {
    render(<LicitacaoCard licitacao={makeLicitacao({ _source: "PCP" })} />);
    const badge = screen.getByTestId('source-badge');
    expect(badge).toHaveTextContent('PCP');
  });

  it('renders ComprasGov badge when _source is ComprasGov', () => {
    render(<LicitacaoCard licitacao={makeLicitacao({ _source: "ComprasGov" })} />);
    const badge = screen.getByTestId('source-badge');
    expect(badge).toHaveTextContent('ComprasGov');
  });

  it('does not render source badge when _source is undefined', () => {
    render(<LicitacaoCard licitacao={makeLicitacao()} />);
    expect(screen.queryByTestId('source-badge')).not.toBeInTheDocument();
  });
});

// =============================================================================
// AC5: Edital number
// =============================================================================

describe('UX-400 AC5: Edital number display', () => {
  it('shows numero_compra when available', () => {
    render(<LicitacaoCard licitacao={makeLicitacao({ numero_compra: "PE-2026/001" })} />);
    expect(screen.getByText('PE-2026/001')).toBeInTheDocument();
  });

  it('falls back to pncp_id when numero_compra not available', () => {
    render(<LicitacaoCard licitacao={makeLicitacao()} />);
    expect(screen.getByText('12345678000190-1-000001/2026')).toBeInTheDocument();
  });
});

// =============================================================================
// AC6: CNPJ display
// =============================================================================

describe('UX-400 AC6: CNPJ display', () => {
  it('shows formatted CNPJ next to orgao name', () => {
    render(<LicitacaoCard licitacao={makeLicitacao({ cnpj_orgao: "12345678000190" })} />);
    expect(screen.getByText(/12\.345\.678\/0001-90/)).toBeInTheDocument();
  });

  it('does not show CNPJ when not available', () => {
    render(<LicitacaoCard licitacao={makeLicitacao()} />);
    expect(screen.queryByText(/CNPJ:/)).not.toBeInTheDocument();
  });
});

// =============================================================================
// Snapshot: card with and without link
// =============================================================================

describe('UX-400: Card snapshots', () => {
  it('card with valid link matches snapshot', () => {
    const { container } = render(
      <LicitacaoCard
        licitacao={makeLicitacao({
          _source: "PNCP",
          numero_compra: "PE-001/2026",
          cnpj_orgao: "12345678000190",
        })}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });

  it('card without link matches snapshot', () => {
    const { container } = render(
      <LicitacaoCard
        licitacao={makeLicitacao({
          link: null,
          _source: "PCP",
          numero_compra: "PROC-99",
          cnpj_orgao: "98765432000100",
        })}
      />
    );
    expect(container.firstChild).toMatchSnapshot();
  });
});
