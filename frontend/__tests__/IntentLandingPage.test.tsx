/**
 * Tests for IntentLandingPage — CONV-007-1
 *
 * Covers:
 * - 4 clusters render correctly
 * - Custom steps render
 * - CTAs have correct hrefs
 * - Mobile responsiveness (CSS classes)
 * - JSON-LD structured data presence
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import IntentLandingPage from '../app/components/IntentLandingPage';
import type { IntentCluster } from '../app/components/conversion/IntentRouter';

const baseProps = {
  cluster: 'comercial' as IntentCluster,
  headline: 'Test Headline',
  subtitle: 'Test Subtitle',
  steps: [
    { title: 'Step 1', description: 'Description 1' },
    { title: 'Step 2', description: 'Description 2' },
    { title: 'Step 3', description: 'Description 3' },
  ],
  socialProofText: 'Social proof text',
  ctaPrimary: { text: 'Primary CTA', href: '/primary' },
  ctaSecondary: { text: 'Secondary CTA', href: '/secondary' },
  pageTitle: 'Test Page Title',
  pageDescription: 'Test page description',
};

describe('IntentLandingPage', () => {
  describe('cluster rendering', () => {
    it.each([
      ['comercial', 'Encontre editais para sua empresa'],
      ['investigativa', 'Dados de licitação para seus clientes'],
      ['juridica', 'Fundamentação jurídica para licitações'],
      ['subcontratacao', 'Seja subcontratado em licitações'],
    ] as [IntentCluster, string][])(
      'renders %s cluster with correct headline',
      (cluster, headline) => {
        render(
          <IntentLandingPage {...baseProps} cluster={cluster} headline={headline} />,
        );
        const h1 = screen.getByRole('heading', { level: 1, name: headline });
        expect(h1).toBeInTheDocument();
      },
    );
  });

  describe('steps', () => {
    it('renders heading "Como funciona"', () => {
      render(<IntentLandingPage {...baseProps} />);
      expect(
        screen.getByRole('heading', { level: 2, name: 'Como funciona' }),
      ).toBeInTheDocument();
    });

    it('renders all 3 custom step titles', () => {
      const steps = [
        { title: 'Alpha step', description: 'Alpha desc' },
        { title: 'Beta step', description: 'Beta desc' },
        { title: 'Gamma step', description: 'Gamma desc' },
      ];
      render(<IntentLandingPage {...baseProps} steps={steps} />);

      for (const step of steps) {
        expect(
          screen.getByRole('heading', { level: 3, name: step.title }),
        ).toBeInTheDocument();
      }
    });

    it('renders step descriptions', () => {
      render(<IntentLandingPage {...baseProps} />);

      for (const step of baseProps.steps) {
        expect(screen.getByText(step.description)).toBeInTheDocument();
      }
    });
  });

  describe('CTAs', () => {
    it('renders primary CTA with correct href', () => {
      render(
        <IntentLandingPage
          {...baseProps}
          ctaPrimary={{ text: 'Sign Up Now', href: '/signup?test=1' }}
        />,
      );

      // CTA appears in hero and final section — check all have same href
      const primaryLinks = screen.getAllByRole('link', {
        name: 'Sign Up Now',
      });
      expect(primaryLinks.length).toBeGreaterThan(0);
      primaryLinks.forEach((link) => {
        expect(link).toHaveAttribute('href', '/signup?test=1');
      });
    });

    it('renders secondary CTA with correct href', () => {
      render(
        <IntentLandingPage
          {...baseProps}
          ctaSecondary={{ text: 'Learn More', href: '/about' }}
        />,
      );

      // Secondary CTA appears in hero and final section
      const secondaryLinks = screen.getAllByRole('link', {
        name: 'Learn More',
      });
      expect(secondaryLinks.length).toBeGreaterThan(0);
      secondaryLinks.forEach((link) => {
        expect(link).toHaveAttribute('href', '/about');
      });
    });

    it('renders primary CTA in the hero section', () => {
      render(<IntentLandingPage {...baseProps} />);

      // The primary CTA should appear as a link (button-like anchor)
      const primaryLinks = screen.getAllByRole('link', {
        name: baseProps.ctaPrimary.text,
      });
      expect(primaryLinks.length).toBeGreaterThan(0);
    });

    it('renders secondary CTA in the hero and final section', () => {
      render(<IntentLandingPage {...baseProps} />);

      // Secondary CTA link text appears in both hero and final CTA sections
      const secondaryLinks = screen.getAllByRole('link', {
        name: baseProps.ctaSecondary.text,
      });
      expect(secondaryLinks.length).toBe(2); // Hero + final CTA
    });

    it('renders primary CTA in both hero and final section', () => {
      render(<IntentLandingPage {...baseProps} />);

      const primaryLinks = screen.getAllByRole('link', {
        name: baseProps.ctaPrimary.text,
      });
      expect(primaryLinks.length).toBe(2); // Hero + final CTA
    });
  });

  describe('social proof', () => {
    it('renders social proof text', () => {
      const proofText = 'Trusted by 1000+ companies';
      render(
        <IntentLandingPage {...baseProps} socialProofText={proofText} />,
      );

      expect(screen.getByText(proofText)).toBeInTheDocument();
    });
  });

  describe('JSON-LD structured data', () => {
    function getJsonLdScript(): HTMLScriptElement | null {
      const scripts = document.querySelectorAll(
        'script[type="application/ld+json"]',
      );
      for (const script of scripts) {
        try {
          const data = JSON.parse(script.innerHTML);
          if (data['@type'] === 'WebPage') return script as HTMLScriptElement;
        } catch {
          // skip invalid JSON
        }
      }
      return null;
    }

    it('includes a JSON-LD script with WebPage type', () => {
      render(<IntentLandingPage {...baseProps} />);

      const script = getJsonLdScript();
      expect(script).not.toBeNull();
    });

    it('includes correct WebPage schema data', () => {
      const pageTitle = 'Custom Page Title for SEO';
      const pageDescription = 'Custom description for SEO testing';

      render(
        <IntentLandingPage
          {...baseProps}
          pageTitle={pageTitle}
          pageDescription={pageDescription}
        />,
      );

      const script = getJsonLdScript();
      expect(script).not.toBeNull();

      const data = JSON.parse(script!.innerHTML);
      expect(data['@type']).toBe('WebPage');
      expect(data.name).toBe(pageTitle);
      expect(data.description).toBe(pageDescription);
    });

    it('includes SmartLic organization as provider', () => {
      render(<IntentLandingPage {...baseProps} />);

      const script = getJsonLdScript();
      expect(script).not.toBeNull();

      const data = JSON.parse(script!.innerHTML);
      expect(data.provider).toBeDefined();
      expect(data.provider['@type']).toBe('Organization');
      expect(data.provider.name).toBe('SmartLic');
      expect(data.provider.url).toBe('https://smartlic.tech');
    });

    it('sets inLanguage to pt-BR', () => {
      render(<IntentLandingPage {...baseProps} />);

      const script = getJsonLdScript();
      const data = JSON.parse(script!.innerHTML);
      expect(data.inLanguage).toBe('pt-BR');
    });
  });

  describe('responsive design', () => {
    it('uses responsive hero layout classes', () => {
      const { container } = render(<IntentLandingPage {...baseProps} />);

      // Hero section has flex-col on mobile, sm:flex-row on desktop
      const ctaContainers = container.querySelectorAll(
        '.flex.flex-col.sm\\:flex-row',
      );
      expect(ctaContainers.length).toBeGreaterThan(0);
    });

    it('uses full-width CTAs on mobile (w-full sm:w-auto)', () => {
      const { container } = render(<IntentLandingPage {...baseProps} />);

      const mobileCtas = container.querySelectorAll('.w-full.sm\\:w-auto');
      expect(mobileCtas.length).toBeGreaterThan(0);
    });

    it('renders steps in a responsive grid (grid sm:grid-cols-3)', () => {
      const { container } = render(<IntentLandingPage {...baseProps} />);

      const grid = container.querySelector('.grid.sm\\:grid-cols-3');
      expect(grid).not.toBeNull();
    });

    it('includes responsive text sizes on heading', () => {
      const { container } = render(<IntentLandingPage {...baseProps} />);

      const h1 = container.querySelector('h1');
      expect(h1).not.toBeNull();
      expect(h1!.className).toContain('sm:text-4xl');
      expect(h1!.className).toContain('lg:text-5xl');
    });
  });

  describe('subtitle', () => {
    it('renders subtitle text', () => {
      const subtitle = 'Test subtitle text';
      render(
        <IntentLandingPage {...baseProps} subtitle={subtitle} />,
      );
      expect(screen.getByText(subtitle)).toBeInTheDocument();
    });
  });

  describe('semantic HTML', () => {
    it('uses <main> semantic element', () => {
      const { container } = render(<IntentLandingPage {...baseProps} />);

      const main = container.querySelector('main');
      expect(main).not.toBeNull();
    });

    it('uses section elements with aria-labels', () => {
      render(<IntentLandingPage {...baseProps} />);

      expect(
        screen.getByRole('region', { name: 'Hero' }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole('region', { name: 'Como funciona' }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole('region', { name: 'Credibilidade' }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole('region', { name: 'Chamada para acao' }),
      ).toBeInTheDocument();
    });

    it('uses correct heading hierarchy (h1 → h2 → h3)', () => {
      const { container } = render(<IntentLandingPage {...baseProps} />);

      const headings = container.querySelectorAll('h1, h2, h3');
      expect(headings.length).toBeGreaterThan(0);

      // Check h1 exists
      expect(container.querySelector('h1')).not.toBeNull();
      // Check h2 exists (Como funciona)
      expect(container.querySelector('h2')).not.toBeNull();
      // Check h3 elements exist (step titles)
      expect(container.querySelectorAll('h3').length).toBe(
        baseProps.steps.length,
      );
    });
  });
});
