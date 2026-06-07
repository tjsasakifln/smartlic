/**
 * Tests for CTAContextual component (CONV-002).
 *
 * Verifies:
 * - Correct text per variant
 * - Correct href per variant
 * - Override props work
 * - Mixpanel tracking on click
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import CTAContextual from '../app/components/conversion/CTAContextual';

describe('CTAContextual', () => {
  const originalMixpanel = (window as unknown as { mixpanel?: unknown }).mixpanel;

  afterEach(() => {
    (window as unknown as { mixpanel?: unknown }).mixpanel = originalMixpanel;
  });

  describe('variant: trial', () => {
    it('renders default trial text', () => {
      render(
        <CTAContextual variant="trial" entityType="orgao" entityName="Prefeitura" />,
      );
      expect(
        screen.getByText('Testar grátis por 7 dias'),
      ).toBeInTheDocument();
    });

    it('renders trial href with entity_ source prefix', () => {
      render(
        <CTAContextual variant="trial" entityType="orgao" entityName="Prefeitura" />,
      );
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/signup?source=entity_orgao');
    });

    it('renders secondary text for trial variant', () => {
      render(
        <CTAContextual variant="trial" entityType="orgao" entityName="Prefeitura" />,
      );
      expect(
        screen.getByText('Sem compromisso. Cancele quando quiser.'),
      ).toBeInTheDocument();
    });
  });

  describe('variant: report', () => {
    it('renders default report text', () => {
      render(
        <CTAContextual variant="report" entityType="fornecedor" entityName="Empresa" />,
      );
      expect(
        screen.getByText('Comprar relatório completo'),
      ).toBeInTheDocument();
    });

    it('renders report href with sku parameter', () => {
      render(
        <CTAContextual variant="report" entityType="fornecedor" entityName="Empresa" />,
      );
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/checkout?sku=relatorio-fornecedor');
    });

    it('does not render secondary text for report variant', () => {
      render(
        <CTAContextual variant="report" entityType="fornecedor" entityName="Empresa" />,
      );
      expect(
        screen.queryByText('Sem compromisso. Cancele quando quiser.'),
      ).toBeNull();
    });
  });

  describe('variant: search', () => {
    it('renders default search text', () => {
      render(
        <CTAContextual variant="search" entityType="setor" entityName="Facilities" />,
      );
      expect(
        screen.getByText('Buscar editais agora'),
      ).toBeInTheDocument();
    });

    it('renders search href pointing to /buscar', () => {
      render(
        <CTAContextual variant="search" entityType="setor" entityName="Facilities" />,
      );
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/buscar');
    });
  });

  describe('variant: contact', () => {
    it('renders default contact text', () => {
      render(
        <CTAContextual variant="contact" entityType="orgao" entityName="Prefeitura" />,
      );
      expect(
        screen.getByText('Falar com especialista'),
      ).toBeInTheDocument();
    });

    it('renders contact href pointing to /contato', () => {
      render(
        <CTAContextual variant="contact" entityType="orgao" entityName="Prefeitura" />,
      );
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/contato');
    });
  });

  describe('override props', () => {
    it('uses ctaText override when provided', () => {
      render(
        <CTAContextual
          variant="trial"
          entityType="orgao"
          entityName="Prefeitura"
          ctaText="Teste grátis agora"
        />,
      );
      expect(
        screen.getByText('Teste grátis agora'),
      ).toBeInTheDocument();
      expect(
        screen.queryByText('Testar grátis por 7 dias'),
      ).toBeNull();
    });

    it('uses ctaLink override when provided', () => {
      render(
        <CTAContextual
          variant="trial"
          entityType="orgao"
          entityName="Prefeitura"
          ctaLink="/custom-path"
        />,
      );
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/custom-path');
    });

    it('uses both ctaText and ctaLink overrides together', () => {
      render(
        <CTAContextual
          variant="report"
          entityType="fornecedor"
          entityName="Empresa"
          ctaText="Ver relatório"
          ctaLink="/relatorio/123"
        />,
      );
      const link = screen.getByRole('link');
      expect(link).toHaveAttribute('href', '/relatorio/123');
      expect(screen.getByText('Ver relatório')).toBeInTheDocument();
    });
  });

  describe('Mixpanel tracking', () => {
    it('fires cta_contextual_click on click', () => {
      const trackSpy = jest.fn();
      (window as unknown as { mixpanel: { track: jest.Mock } }).mixpanel = {
        track: trackSpy,
      };

      render(
        <CTAContextual variant="trial" entityType="orgao" entityName="Prefeitura" />,
      );
      fireEvent.click(screen.getByRole('link'));

      expect(trackSpy).toHaveBeenCalledWith('cta_contextual_click', {
        variant: 'trial',
        entityType: 'orgao',
        entityName: 'Prefeitura',
      });
    });

    it('does not throw when window.mixpanel is undefined', () => {
      delete (window as unknown as { mixpanel?: unknown }).mixpanel;

      render(
        <CTAContextual variant="trial" entityType="orgao" entityName="Prefeitura" />,
      );
      expect(() =>
        fireEvent.click(screen.getByRole('link')),
      ).not.toThrow();
    });
  });
});
