import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { TrackingLink } from '@/components/TrackingLink';

const mockTrackEvent = jest.fn();

jest.mock('@/hooks/useAnalytics', () => ({
  useAnalytics: () => ({ trackEvent: mockTrackEvent }),
}));

jest.mock('next/link', () => {
  const MockLink = ({ href, children, className, onClick, ...rest }: {
    href: string;
    children: React.ReactNode;
    className?: string;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <a href={href} className={className} onClick={onClick} {...rest}>
      {children}
    </a>
  );
  MockLink.displayName = 'MockLink';
  return MockLink;
});

describe('TrackingLink', () => {
  beforeEach(() => {
    mockTrackEvent.mockClear();
  });

  it('renders children correctly', () => {
    render(
      <TrackingLink href="/signup" eventName="cta_clicked">
        Teste gratis
      </TrackingLink>
    );
    expect(screen.getByText('Teste gratis')).toBeInTheDocument();
  });

  it('renders with correct href', () => {
    render(
      <TrackingLink href="/signup?utm_campaign=test" eventName="cta_clicked">
        Click
      </TrackingLink>
    );
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/signup?utm_campaign=test');
  });

  it('applies className prop', () => {
    render(
      <TrackingLink href="/signup" eventName="cta_clicked" className="btn-primary">
        Click
      </TrackingLink>
    );
    const link = screen.getByRole('link');
    expect(link).toHaveClass('btn-primary');
  });

  it('calls trackEvent with eventName on click', () => {
    render(
      <TrackingLink href="/signup" eventName="cta_clicked">
        Click
      </TrackingLink>
    );
    fireEvent.click(screen.getByRole('link'));
    expect(mockTrackEvent).toHaveBeenCalledTimes(1);
    expect(mockTrackEvent).toHaveBeenCalledWith('cta_clicked', undefined);
  });

  it('calls trackEvent with eventProps on click', () => {
    const props = { cta_name: 'hero', page_cnpj: '12345678000100' };
    render(
      <TrackingLink href="/signup" eventName="cta_clicked" eventProps={props}>
        Click
      </TrackingLink>
    );
    fireEvent.click(screen.getByRole('link'));
    expect(mockTrackEvent).toHaveBeenCalledWith('cta_clicked', props);
  });

  it('passes additional props to link', () => {
    render(
      <TrackingLink href="/signup" eventName="cta_clicked" data-testid="tracking-link">
        Click
      </TrackingLink>
    );
    expect(screen.getByTestId('tracking-link')).toBeInTheDocument();
  });
});
