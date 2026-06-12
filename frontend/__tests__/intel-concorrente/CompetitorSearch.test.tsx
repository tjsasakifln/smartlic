import { render, screen, fireEvent } from '@testing-library/react';
import CompetitorSearch from '@/app/intel-concorrente/components/CompetitorSearch';

const mockOnSearch = jest.fn();

describe('CompetitorSearch', () => {
  beforeEach(() => {
    mockOnSearch.mockClear();
  });

  it('renders the search input and button', () => {
    render(<CompetitorSearch onSearch={mockOnSearch} loading={false} />);

    expect(screen.getByLabelText(/CNPJ/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /analisar/i })).toBeInTheDocument();
  });

  it('disables button with invalid CNPJ', () => {
    render(<CompetitorSearch onSearch={mockOnSearch} loading={false} />);

    const button = screen.getByRole('button', { name: /analisar/i });
    expect(button).toBeDisabled();
  });

  it('formats CNPJ as user types', () => {
    render(<CompetitorSearch onSearch={mockOnSearch} loading={false} />);

    const input = screen.getByLabelText(/CNPJ/i);
    fireEvent.change(input, { target: { value: '12345678000195' } });

    expect(input).toHaveValue('12.345.678/0001-95');
  });

  it('calls onSearch with raw CNPJ on submit', () => {
    render(<CompetitorSearch onSearch={mockOnSearch} loading={false} />);

    const input = screen.getByLabelText(/CNPJ/i);
    fireEvent.change(input, { target: { value: '12345678000195' } });

    const button = screen.getByRole('button', { name: /analisar/i });
    fireEvent.click(button);

    expect(mockOnSearch).toHaveBeenCalledWith('12345678000195');
  });

  it('shows loading state', () => {
    render(<CompetitorSearch onSearch={mockOnSearch} loading={true} />);

    expect(screen.getByRole('button', { name: /buscando/i })).toBeDisabled();
  });
});
