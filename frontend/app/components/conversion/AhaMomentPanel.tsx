'use client';

/**
 * AhaMomentPanel — CONV-004
 *
 * An insight/revelation panel that shows key data points about an entity
 * to create an "aha moment". Renders a grid of insight cards (2-4) with
 * icon, label, large value, and optional subtext.
 *
 * Responsive: 2-column grid on mobile, 4-column on desktop.
 * Uses Framer Motion for fade-in animation.
 */

import React from 'react';
import { motion } from 'framer-motion';

export type InsightIcon = 'chart' | 'money' | 'building' | 'target';

export interface InsightCard {
  label: string;
  value: string;
  subtext?: string;
  icon?: InsightIcon;
}

export interface AhaMomentPanelProps {
  /** Entity type for scoped analytics */
  entityType: string;
  /** Array of insight cards (2-4 cards) */
  insights: InsightCard[];
}

const ICON_MAP: Record<InsightIcon, string> = {
  chart: '📊',
  money: '💰',
  building: '🏛️',
  target: '🎯',
};

const containerVariants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.12,
    },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: 'easeOut' as const },
  },
};

export default function AhaMomentPanel({
  entityType,
  insights,
}: AhaMomentPanelProps) {
  if (insights.length === 0) return null;

  return (
    <section aria-label="Insights" className="my-8">
      <motion.div
        className="grid grid-cols-2 gap-4 md:grid-cols-4"
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.2 }}
      >
        {insights.map((insight, index) => (
          <motion.div
            key={`insight-${entityType}-${index}`}
            variants={cardVariants}
            className="rounded-xl border border-gray-200 bg-white p-4 text-center shadow-sm"
            data-testid={`insight-card-${index}`}
          >
            {insight.icon && (
              <span
                className="mb-2 inline-block text-3xl"
                role="img"
                aria-hidden="true"
              >
                {ICON_MAP[insight.icon]}
              </span>
            )}
            <p className="text-2xl font-bold text-gray-900">{insight.value}</p>
            <p className="mt-1 text-sm font-medium text-gray-500">
              {insight.label}
            </p>
            {insight.subtext && (
              <p className="mt-1 text-xs text-gray-400">{insight.subtext}</p>
            )}
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
