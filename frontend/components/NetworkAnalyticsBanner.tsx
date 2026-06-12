'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useUser } from '../contexts/UserContext';

const BANNER_DISMISSED_KEY = 'network_banner_dismissed';

export default function NetworkAnalyticsBanner() {
  const { user } = useUser();
  const [visible, setVisible] = useState(false);
  const [activating, setActivating] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Only show for logged-in users who haven't dismissed in this session
    const wasDismissed = localStorage.getItem(BANNER_DISMISSED_KEY) === 'true';
    if (!user || wasDismissed) {
      setDismissed(true);
      return;
    }

    // Check if user has already made a decision (allow_network_analytics is not null)
    // We infer this from user profile data — if the user object has the field
    // and it's explicitly true or false, skip the banner
    const hasDecided = (user as unknown as Record<string, unknown>)?.allow_network_analytics !== undefined
      && (user as unknown as Record<string, unknown>)?.allow_network_analytics !== null;

    if (!hasDecided) {
      setVisible(true);
    }
  }, [user]);

  const handleActivate = useCallback(async () => {
    setActivating(true);
    try {
      const response = await fetch('/v1/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allow_network_analytics: true }),
      });

      if (response.ok) {
        // Show success state briefly, then fade out
        setTimeout(() => {
          setVisible(false);
          localStorage.setItem(BANNER_DISMISSED_KEY, 'true');
        }, 1500);
      } else {
        setActivating(false);
      }
    } catch {
      setActivating(false);
    }
  }, []);

  const handleDismiss = useCallback(() => {
    setVisible(false);
    localStorage.setItem(BANNER_DISMISSED_KEY, 'true');
  }, []);

  if (!visible || dismissed) return null;

  return (
    <div
      className={`
        fixed bottom-4 left-4 right-4 z-50 mx-auto max-w-lg
        bg-white dark:bg-gray-800 rounded-lg shadow-xl border
        border-gray-200 dark:border-gray-700 p-4
        transition-all duration-300 ease-in-out
        ${activating ? 'opacity-50 scale-95' : 'opacity-100 scale-100'}
      `}
      role="alert"
      aria-live="polite"
    >
      <p className="text-sm text-gray-700 dark:text-gray-300 mb-3 leading-relaxed">
        A SmartLic agora aprende com o uso coletivo para gerar sinais de
        mercado mais precisos para todos. Enviamos apenas contagens anonimas
        &mdash; nunca seus dados pessoais ou CNPJ.
      </p>

      <div className="flex items-center gap-2">
        <button
          onClick={handleActivate}
          disabled={activating}
          className={`
            flex-1 px-4 py-2 text-sm font-medium rounded-button
            bg-brand-blue text-white hover:bg-brand-blue/90
            focus:outline-none focus:ring-2 focus:ring-brand-blue focus:ring-offset-2
            dark:focus:ring-offset-gray-800
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors
          `}
        >
          {activating ? 'Ativando...' : 'Ativar contribuicao'}
        </button>

        <a
          href="/privacidade"
          className="px-4 py-2 text-sm font-medium text-gray-600 dark:text-gray-400
                     hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
        >
          Saiba mais
        </a>

        <button
          onClick={handleDismiss}
          className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300
                     transition-colors focus:outline-none focus:ring-2 focus:ring-gray-400
                     rounded-full"
          aria-label="Fechar banner"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {activating && (
        <p className="text-xs text-green-600 dark:text-green-400 mt-2">
          Contribuicao ativada! Obrigado por ajudar a melhorar a plataforma.
        </p>
      )}
    </div>
  );
}
