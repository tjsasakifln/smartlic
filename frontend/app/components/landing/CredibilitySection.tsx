'use client';

import React from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { fadeInUp, staggerContainer } from '@/lib/animations';

/**
 * COPY-COP-004 (#1125): CredibilitySection — replaces fabricated testimonials
 * with real, verifiable technical proof points (CDC art. 37 compliance).
 *
 * Data: 2M+ contracts indexed, 87% noise eliminated, 27 UFs, PNCP+PCP+ComprasGov.
 */
export default function CredibilitySection() {
  return (
    <section
      className="py-16 sm:py-20 bg-[var(--surface-0)]"
      data-testid="credibility-section"
    >
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-50px' }}
        >
          <h2 className="text-2xl sm:text-3xl font-bold text-center text-[var(--ink)] mb-4">
            Dados reais. Fontes oficiais. Nenhum bl&aacute;-bl&aacute;-bl&aacute;.
          </h2>
          <p className="text-center text-[var(--ink-secondary)] mb-12 max-w-2xl mx-auto">
            O SmartLic &eacute; constru&iacute;do com dados p&uacute;blicos do governo e algoritmos
            transparentes. Cada n&uacute;mero aqui &eacute; verific&aacute;vel.
          </p>

          <motion.div className="grid sm:grid-cols-3 gap-6 mb-12" variants={fadeInUp}>
            <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-2xl p-6 text-center">
              <p className="text-3xl sm:text-4xl font-bold text-[var(--brand-blue)] mb-2">
                2 milh&otilde;es+
              </p>
              <p className="text-sm text-[var(--ink-secondary)]">contratos p&uacute;blicos indexados</p>
            </div>
            <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-2xl p-6 text-center">
              <p className="text-3xl sm:text-4xl font-bold text-[var(--brand-blue)] mb-2">87%</p>
              <p className="text-sm text-[var(--ink-secondary)]">de ru&iacute;do eliminado na filtragem</p>
            </div>
            <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-2xl p-6 text-center">
              <p className="text-3xl sm:text-4xl font-bold text-[var(--brand-blue)] mb-2">27 estados</p>
              <p className="text-sm text-[var(--ink-secondary)]">cobertura nacional integrada</p>
            </div>
          </motion.div>

          <motion.div className="flex flex-wrap justify-center gap-3 mb-12" variants={fadeInUp}>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--surface-1)] border border-[var(--border)] rounded-full text-[var(--ink-secondary)]">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />PNCP
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--surface-1)] border border-[var(--border)] rounded-full text-[var(--ink-secondary)]">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />PCP v2
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--surface-1)] border border-[var(--border)] rounded-full text-[var(--ink-secondary)]">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />ComprasGov v3
            </span>
          </motion.div>

          <motion.div className="flex flex-wrap justify-center gap-4 sm:gap-6" variants={fadeInUp}>
            <Link href="/changelog" className="text-sm text-[var(--brand-blue)] hover:underline font-medium" data-testid="credibility-changelog">
              Changelog p&uacute;blico &rarr;
            </Link>
            <Link href="/sobre" className="text-sm text-[var(--brand-blue)] hover:underline font-medium" data-testid="credibility-metodologia">
              Metodologia documentada &rarr;
            </Link>
            <a href="https://pncp.gov.br" target="_blank" rel="noopener noreferrer" className="text-sm text-[var(--ink-muted)] hover:text-[var(--brand-blue)] transition-colors">
              Portal Nacional de Contrata&ccedil;&otilde;es P&uacute;blicas
            </a>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
