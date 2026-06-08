'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import mixpanel from 'mixpanel-browser';
import { useIntentDetection } from './IntentRouter';
import type { IntentCluster } from './IntentRouter';

// ── Constants ──────────────────────────────────────────────────────

const SECTORS = [
  { value: '', label: 'Todos os setores' },
  { value: 'construcao-civil', label: 'Construcao Civil' },
  { value: 'saude', label: 'Saude' },
  { value: 'tecnologia', label: 'Tecnologia' },
  { value: 'educacao', label: 'Educacao' },
  { value: 'servicos', label: 'Servicos' },
  { value: 'alimentacao', label: 'Alimentacao' },
  { value: 'transporte', label: 'Transporte' },
  { value: 'energia', label: 'Energia' },
  { value: 'seguranca', label: 'Seguranca' },
  { value: 'meio-ambiente', label: 'Meio Ambiente' },
];

interface IntentCard {
  id: string;
  emoji: string;
  title: string;
  description: string;
  route: string;
}

const INTENT_CARDS: IntentCard[] = [
  {
    id: 'vender',
    emoji: '\u{1F4BC}',
    title: 'Quero vender para o governo',
    description: 'Encontre editais do seu setor',
    route: '/para-empresas',
  },
  {
    id: 'pesquisar',
    emoji: '\u{1F50D}',
    title: 'Quero pesquisar um concorrente',
    description: 'Analise de quem ganha licitacoes',
    route: '/buscar',
  },
  {
    id: 'parceiros',
    emoji: '\u{1F91D}',
    title: 'Quero encontrar parceiros',
    description: 'Oportunidades de subcontratacao',
    route: '/para-fornecedores',
  },
  {
    id: 'mercado',
    emoji: '\u{1F4CA}',
    title: 'Quero entender meu mercado',
    description: 'Dados e tendencias do setor publico',
    route: '/observatorio',
  },
  {
    id: 'acompanhar',
    emoji: '\u{1F514}',
    title: 'Quero acompanhar editais',
    description: 'Alertas personalizados de novas licitacoes',
    route: '/signup?source=intent-home',
  },
  {
    id: 'preparar',
    emoji: '✅',
    title: 'Quero me preparar para licitar',
    description: 'Checklist, documentos, compliance',
    route: '/para-advogados',
  },
];

const INTENT_CLUSTER_ROUTES: Partial<Record<IntentCluster, string>> = {
  comercial: '/para-empresas',
  investigativa: '/buscar',
  juridica: '/para-advogados',
  subcontratacao: '/para-fornecedores',
};

const INTENT_CLUSTER_LABEL_PT: Partial<Record<IntentCluster, string>> = {
  comercial: 'oportunidades comerciais',
  investigativa: 'analise de mercado',
  juridica: 'informacoes juridicas',
  subcontratacao: 'parceiros e subcontratacao',
};

// ── Helpers ─────────────────────────────────────────────────────────

function safeTrack(name: string, props?: Record<string, unknown>) {
  try {
    mixpanel.track(name, props);
  } catch {
    // Mixpanel not available (SSR, blocked, or not initialized)
  }
}

// ── Component ──────────────────────────────────────────────────────

export default function IntelHomeClient() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSector, setSelectedSector] = useState('');
  const { cluster, source } = useIntentDetection();
  const intentTrackedRef = useRef(false);

  // Track home_intent_routed once on mount when intent is detected
  useEffect(() => {
    if (intentTrackedRef.current) return;
    if (cluster !== 'geral') {
      safeTrack('home_intent_routed', { cluster, source });
      intentTrackedRef.current = true;
    }
  }, [cluster, source]);

  // Search submit handler
  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = searchQuery.trim();
      if (!trimmed) return;

      safeTrack('home_search_initiated', { query: trimmed, sector: selectedSector });

      const params = new URLSearchParams();
      params.set('q', trimmed);
      if (selectedSector) params.set('setor', selectedSector);
      router.push(`/buscar?${params.toString()}`);
    },
    [searchQuery, selectedSector, router],
  );

  // Card click handler
  const handleCardClick = useCallback(
    (card: IntentCard) => {
      safeTrack('home_intent_card_click', { card_id: card.id, card_title: card.title });
      router.push(card.route);
    },
    [router],
  );

  const isSearchDisabled = !searchQuery.trim();

  return (
    <main id="main-content" className="min-h-screen bg-canvas">
      {/* Intent Detection Banner */}
      {cluster !== 'geral' && INTENT_CLUSTER_ROUTES[cluster] && (
        <div
          className="border-b border-border bg-brand-blue-subtle"
          data-testid="intent-banner"
        >
          <div className="mx-auto max-w-landing px-4 py-3 text-center text-sm">
            <span className="text-ink-secondary">
              Detectamos que voce busca{' '}
              <strong className="text-brand-blue">
                {INTENT_CLUSTER_LABEL_PT[cluster] ?? cluster}
              </strong>
              . Veja nossa pagina dedicada:{' '}
            </span>
            <a
              href={INTENT_CLUSTER_ROUTES[cluster]!}
              className="ml-1 font-semibold text-brand-blue underline hover:text-brand-blue-hover"
            >
              Acessar &rarr;
            </a>
          </div>
        </div>
      )}

      {/* Search Section -- Above the Fold */}
      <section className="flex flex-col items-center justify-center px-4 pb-16 pt-24 md:pb-24 md:pt-32">
        <h1 className="mb-6 max-w-3xl text-balance text-center font-display text-h1 font-display text-gradient">
          Terminal de Inteligencia em Licitacoes Publicas
        </h1>
        <p className="mb-10 max-w-2xl text-balance text-center text-body-lg text-ink-secondary">
          Busque editais, analise concorrentes, encontre parceiros e tome decisoes
          estrategicas com dados reais do governo.
        </p>

        {/* Search Form */}
        <form
          onSubmit={handleSearch}
          className="flex w-full max-w-2xl flex-col gap-3 sm:flex-row"
          data-testid="home-search-form"
        >
          <div className="relative flex-1">
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Busque editais, fornecedores, orgaos..."
              className="h-12 w-full rounded-xl border border-border bg-surface-1 px-4 pr-10
                         text-ink placeholder:text-ink-muted
                         transition-shadow
                         focus:border-transparent focus:outline-none focus:ring-2 focus:ring-ring"
              aria-label="Termo de busca"
              data-testid="search-input"
            />
          </div>
          <select
            value={selectedSector}
            onChange={(e) => setSelectedSector(e.target.value)}
            className="h-12 cursor-pointer rounded-xl border border-border bg-surface-1 px-4
                       text-ink transition-shadow
                       focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label="Filtrar por setor"
            data-testid="sector-select"
          >
            {SECTORS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={isSearchDisabled}
            className="h-12 rounded-xl bg-brand-blue px-8 font-semibold text-white
                       transition-colors hover:bg-brand-blue-hover
                       focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2
                       disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="search-submit"
          >
            Buscar
          </button>
        </form>
      </section>

      {/* Intent Cards Section */}
      <section className="mx-auto max-w-landing px-4 pb-24" data-testid="intent-cards-section">
        <h2 className="sr-only">O que voce deseja fazer?</h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 md:gap-6">
          {INTENT_CARDS.map((card, index) => (
            <button
              key={card.id}
              onClick={() => handleCardClick(card)}
              className={`group rounded-xl border border-border bg-surface-1 p-6 text-left
                         shadow-sm transition-all duration-200
                         hover:-translate-y-1 hover:shadow-md
                         focus:outline-none focus:ring-2 focus:ring-ring
                         animate-fade-in-up stagger-${Math.min(index + 1, 5)}`}
              aria-label={`${card.title}: ${card.description}`}
              data-testid={`intent-card-${card.id}`}
            >
              <span className="mb-3 block text-3xl" role="img" aria-hidden="true">
                {card.emoji}
              </span>
              <h3 className="mb-1 text-base font-semibold text-ink transition-colors group-hover:text-brand-blue">
                {card.title}
              </h3>
              <p className="mb-3 text-sm text-ink-muted">{card.description}</p>
              <span className="text-sm font-medium text-brand-blue transition-colors group-hover:text-brand-blue-hover">
                Saiba mais &rarr;
              </span>
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}
