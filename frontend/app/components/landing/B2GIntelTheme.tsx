'use client';

import { useEffect } from 'react';

/**
 * REPO-COMMS #1289: Aplica data-theme="b2g-intel" ao document element
 * enquanto a landing page está montada. Remove ao desmontar.
 *
 * HOTFIX 2026-06-07: ThemeProvider aplica estilos inline via
 * root.style.setProperty() que vencem regras CSS [data-theme="b2g-intel"].
 * Solução: B2GIntelTheme também aplica os tokens b2g-intel como inline styles
 * para sobrescrever ThemeProvider (useEffect de B2GIntelTheme roda DEPOIS do
 * ThemeProvider por estar mais profundo na árvore React).
 */
const B2G_INTEL_TOKENS: Record<string, string> = {
  '--canvas': '#0a0e14',
  '--ink': '#e6edf3',
  '--ink-secondary': '#8b949e',
  '--ink-muted': '#6e7681',
  '--ink-faint': '#30363d',
  '--brand-navy': '#58a6ff',
  '--brand-blue': '#58a6ff',
  '--brand-blue-hover': '#79b8ff',
  '--brand-blue-subtle': 'rgba(88, 166, 255, 0.1)',
  '--surface-0': '#0a0e14',
  '--surface-1': '#12171f',
  '--surface-2': '#1a202c',
  '--surface-elevated': '#1a202c',
  '--success': '#3fb950',
  '--success-subtle': 'rgba(63, 185, 80, 0.12)',
  '--error': '#f85149',
  '--error-subtle': 'rgba(248, 81, 73, 0.12)',
  '--warning': '#d29922',
  '--warning-subtle': 'rgba(210, 153, 34, 0.12)',
  '--border': '#30363d',
  '--border-strong': 'rgba(255, 255, 255, 0.15)',
  '--border-accent': 'rgba(88, 166, 255, 0.3)',
  '--ring': '#58a6ff',
};

function saveThemeProviderState(root: HTMLElement) {
  const saved: Record<string, string> = {};
  for (const key of Object.keys(B2G_INTEL_TOKENS)) {
    const val = root.style.getPropertyValue(key);
    if (val) saved[key] = val;
  }
  return saved;
}

function restoreThemeProviderState(root: HTMLElement, saved: Record<string, string>) {
  for (const [key, val] of Object.entries(saved)) {
    root.style.setProperty(key, val);
  }
  // Remove keys that weren't there before
  for (const key of Object.keys(B2G_INTEL_TOKENS)) {
    if (!(key in saved)) {
      root.style.removeProperty(key);
    }
  }
}

export default function B2GIntelTheme({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    const el = document.documentElement;

    // Save current ThemeProvider inline state
    const prevTokens = saveThemeProviderState(el);
    const prevDataTheme = el.getAttribute('data-theme');

    // Apply b2g-intel tokens as inline styles (override ThemeProvider)
    el.setAttribute('data-theme', 'b2g-intel');
    for (const [key, val] of Object.entries(B2G_INTEL_TOKENS)) {
      el.style.setProperty(key, val);
    }

    return () => {
      // Restore ThemeProvider inline state
      restoreThemeProviderState(el, prevTokens);

      if (prevDataTheme) {
        el.setAttribute('data-theme', prevDataTheme);
      } else {
        el.removeAttribute('data-theme');
      }
    };
  }, []);

  return <>{children}</>;
}
