/**
 * UrgencyBadge Component Tests (CONV-016)
 *
 * Tests:
 *  - Color coding for different time ranges
 *  - Text matches expected patterns
 *  - Edge cases (null date, future date)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { UrgencyBadge, daysSince, urgencyLabel } from '@/components/pseo/UrgencyBadge';

describe('UrgencyBadge', () => {
  describe('daysSince helper', () => {
    it('should return -1 for null input', () => {
      expect(daysSince(null)).toBe(-1);
    });

    it('should return -1 for undefined input', () => {
      expect(daysSince(undefined)).toBe(-1);
    });

    it('should return -1 for empty string', () => {
      expect(daysSince('')).toBe(-1);
    });

    it('should return 0 for today', () => {
      const today = new Date().toISOString().split('T')[0];
      expect(daysSince(today)).toBe(0);
    });

    it('should return a positive number for a past date', () => {
      const pastDate = new Date();
      pastDate.setDate(pastDate.getDate() - 10);
      const dateStr = pastDate.toISOString().split('T')[0];
      const result = daysSince(dateStr);
      expect(result).toBeGreaterThanOrEqual(9);
      expect(result).toBeLessThanOrEqual(11);
    });
  });

  describe('urgencyLabel helper', () => {
    it('should return "Ativo esta semana" for dates within 7 days', () => {
      const label = urgencyLabel(new Date().toISOString().split('T')[0]);
      expect(label).toBe('Ativo esta semana');
    });

    it('should return "Sem atividade recente" for null', () => {
      expect(urgencyLabel(null)).toBe('Sem atividade recente');
    });

    it('should return "Ativo este mês" for a date 20 days ago', () => {
      const past = new Date();
      past.setDate(past.getDate() - 20);
      expect(urgencyLabel(past.toISOString().split('T')[0])).toBe('Ativo este mês');
    });

    it('should return "Ativo recentemente" for a date 60 days ago', () => {
      const past = new Date();
      past.setDate(past.getDate() - 60);
      expect(urgencyLabel(past.toISOString().split('T')[0])).toBe('Ativo recentemente');
    });

    it('should return "Sem atividade recente" for a date 180 days ago', () => {
      const past = new Date();
      past.setDate(past.getDate() - 180);
      expect(urgencyLabel(past.toISOString().split('T')[0])).toBe('Sem atividade recente');
    });
  });

  describe('rendering', () => {
    it('should render with "Ativo esta semana" for daysSinceLastEvent <= 7', () => {
      render(<UrgencyBadge daysSinceLastEvent={3} />);
      expect(screen.getByText('Ativo esta semana')).toBeInTheDocument();
    });

    it('should render with "Ativo este mês" for daysSinceLastEvent between 7 and 30', () => {
      render(<UrgencyBadge daysSinceLastEvent={15} />);
      expect(screen.getByText('Ativo este mês')).toBeInTheDocument();
    });

    it('should render with "Ativo recentemente" for daysSinceLastEvent between 30 and 90', () => {
      render(<UrgencyBadge daysSinceLastEvent={60} />);
      expect(screen.getByText('Ativo recentemente')).toBeInTheDocument();
    });

    it('should render with "Sem atividade recente" for daysSinceLastEvent > 90', () => {
      render(<UrgencyBadge daysSinceLastEvent={120} />);
      expect(screen.getByText('Sem atividade recente')).toBeInTheDocument();
    });

    it('should render with "Sem atividade recente" for negative daysSinceLastEvent', () => {
      render(<UrgencyBadge daysSinceLastEvent={-1} />);
      expect(screen.getByText('Sem atividade recente')).toBeInTheDocument();
    });

    it('should use custom label when provided', () => {
      render(<UrgencyBadge daysSinceLastEvent={3} label="5 contratos este mês" />);
      expect(screen.getByText('5 contratos este mês')).toBeInTheDocument();
    });

    it('should apply custom className', () => {
      const { container } = render(
        <UrgencyBadge daysSinceLastEvent={3} className="my-custom-class" />
      );
      const badge = container.firstChild as HTMLElement;
      expect(badge.className).toContain('my-custom-class');
    });

    it('should render a colored dot indicator', () => {
      const { container } = render(<UrgencyBadge daysSinceLastEvent={3} />);
      const dot = container.querySelector('span.inline-block');
      expect(dot).toBeInTheDocument();
    });
  });
});
