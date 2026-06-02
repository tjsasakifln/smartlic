'use client';

import React from 'react';

// ---------------------------------------------------------------------------
// CONV-016: Visual badge with time-based color coding for pSEO urgency signals
// ---------------------------------------------------------------------------

type UrgencyLevel = 'green' | 'yellow' | 'neutral' | 'gray';

interface UrgencyBadgeProps {
  /** Days since the last event */
  daysSinceLastEvent: number;
  /** Optional custom text override */
  label?: string;
  /** Additional CSS classes */
  className?: string;
}

const COLOR_MAP: Record<UrgencyLevel, string> = {
  green: 'bg-green-100 text-green-800 border-green-200',
  yellow: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  neutral: 'bg-blue-50 text-blue-700 border-blue-100',
  gray: 'bg-gray-100 text-gray-500 border-gray-200',
};

const LEVEL_LABELS: Record<UrgencyLevel, { text: string; title: string }> = {
  green: { text: 'Ativo esta semana', title: 'Atividade registrada nos últimos 7 dias' },
  yellow: { text: 'Ativo este mês', title: 'Atividade registrada nos últimos 30 dias' },
  neutral: { text: 'Ativo recentemente', title: 'Atividade registrada nos últimos 90 dias' },
  gray: { text: 'Sem atividade recente', title: 'Nenhuma atividade registrada nos últimos 90 dias' },
};

function getUrgencyLevel(days: number): UrgencyLevel {
  if (days < 0) return 'gray';
  if (days <= 7) return 'green';
  if (days <= 30) return 'yellow';
  if (days <= 90) return 'neutral';
  return 'gray';
}

function getDaysSince(dateStr: string | null | undefined): number {
  if (!dateStr) return -1;
  try {
    const eventDate = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - eventDate.getTime();
    return Math.floor(diffMs / (1000 * 60 * 60 * 24));
  } catch {
    return -1;
  }
}

/**
 * UrgencyBadge — small badge showing recency of activity for an entity.
 * Color-coded: green (< 7d), yellow (7-30d), neutral (31-90d), gray (> 90d).
 */
export function UrgencyBadge({
  daysSinceLastEvent,
  label,
  className = '',
}: UrgencyBadgeProps) {
  const level = getUrgencyLevel(daysSinceLastEvent);
  const defaults = LEVEL_LABELS[level];
  const displayText = label ?? defaults.text;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${COLOR_MAP[level]} ${className}`}
      title={defaults.title}
    >
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          level === 'green'
            ? 'bg-green-500'
            : level === 'yellow'
            ? 'bg-yellow-500'
            : level === 'neutral'
            ? 'bg-blue-500'
            : 'bg-gray-400'
        }`}
      />
      {displayText}
    </span>
  );
}

/**
 * Convenience function to compute days-since from a date string
 * and return the badge. Used inline in server components.
 */
export function daysSince(dateStr: string | null | undefined): number {
  return getDaysSince(dateStr);
}

/**
 * Helper to get the appropriate label text for a date string.
 */
export function urgencyLabel(dateStr: string | null | undefined): string {
  const days = getDaysSince(dateStr);
  const level = getUrgencyLevel(days);
  return LEVEL_LABELS[level].text;
}
