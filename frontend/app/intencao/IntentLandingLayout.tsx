'use client';

import { type ReactNode } from 'react';
import B2GIntelTheme from '../components/landing/B2GIntelTheme';
import LandingNavbar from '../components/landing/LandingNavbar';
import Footer from '../components/Footer';

interface IntentLandingLayoutProps {
  children: ReactNode;
}

/**
 * Shared layout component for intent cluster landing pages (/intencao/*).
 *
 * Provides B2GIntelTheme, LandingNavbar, and Footer for visual consistency
 * across all 4 intent cluster landing pages (comercial, investigativa,
 * juridica, subcontratacao).
 *
 * @example
 * ```tsx
 * <IntentLandingLayout>
 *   <YourPageContent />
 * </IntentLandingLayout>
 * ```
 */
export default function IntentLandingLayout({
  children,
}: IntentLandingLayoutProps) {
  return (
    <B2GIntelTheme>
      <LandingNavbar />
      <main id="main-content" className="min-h-screen">
        {children}
      </main>
      <Footer />
    </B2GIntelTheme>
  );
}
