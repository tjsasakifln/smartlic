/**
 * WIDGET-COMPINT-001: Widget pages base layout.
 *
 * Minimal/no chrome for embed pages. Only the widget content.
 * No header, nav, or footer — those are handled inside the widget pages.
 */

import { ReactNode } from 'react';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  robots: { index: false, follow: true }, // noindex — embed pages não devem aparecer em busca
};

export default function WidgetsLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
