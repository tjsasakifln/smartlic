import { render, screen } from '@testing-library/react';
import IntelConcorrenteClient from '@/app/intel-concorrente/IntelConcorrenteClient';

// Mock fetch
global.fetch = jest.fn();

describe('IntelConcorrenteClient', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockClear();
  });

  it('renders the main title and description', () => {
    render(<IntelConcorrenteClient />);

    expect(screen.getByText('Inteligencia Concorrencial')).toBeInTheDocument();
    expect(
      screen.getByText(/Analise concorrentes/)
    ).toBeInTheDocument();
  });

  it('renders sector selector', () => {
    render(<IntelConcorrenteClient />);

    expect(screen.getByLabelText(/Setor/)).toBeInTheDocument();
    expect(screen.getByText('Tecnologia da Informacao')).toBeInTheDocument();
  });

  it('renders the competitor search component', () => {
    render(<IntelConcorrenteClient />);

    expect(screen.getByLabelText(/CNPJ/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Carregar Panorama/i })).toBeInTheDocument();
  });

  it('shows empty state initially', () => {
    render(<IntelConcorrenteClient />);

    expect(
      screen.getByText(/Bem-vindo a Inteligencia Concorrencial/)
    ).toBeInTheDocument();
  });
});
