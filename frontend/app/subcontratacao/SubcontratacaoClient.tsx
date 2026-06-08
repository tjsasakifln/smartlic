'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { CheckoutButton } from '@/app/components/checkout/CheckoutButton';
import { DigitalProductPreview } from '@/app/components/checkout/DigitalProductPreview';
import {
  useScrollAnimation,
  fadeInUp,
  staggerContainer,
} from '@/lib/animations';
import type { components } from '@/app/api-types.generated';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DigitalProductOut = components['schemas']['DigitalProductOut'];
type ProductsResponse = components['schemas']['ProductsResponse'];

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PRODUCT_SKU = 'subcontratacao-map';

const PRODUCT_CONTEXT = {
  entity_type: 'subcontratacao' as const,
  entity_id: 'flagship',
};

/**
 * Subcontratacao stats — dados publicos do mercado B2G brasileiro.
 * Fontes: Lei 14.133/2021, TCU, PNCP.
 */
interface StatItem {
  value: string;
  label: string;
}

const STATS: StatItem[] = [
  { value: '87%', label: 'dos contratos publicos permitem subcontratacao' },
  { value: '15+', label: 'setores com oportunidades ativas de parceria' },
  { value: 'R$ 12 Bi+', label: 'movimentados em subcontratacao por ano' },
];

/**
 * Top setores com maior volume de subcontratacao em licitacoes publicas.
 * Dados estimados com base em contratos publicos federais e estaduais.
 */
interface SectorItem {
  name: string;
  percentage: number;
  description: string;
}

const SECTORS: SectorItem[] = [
  {
    name: 'Construcao Civil',
    percentage: 28,
    description: 'Obras, reformas e infraestrutura',
  },
  {
    name: 'Servicos de Limpeza',
    percentage: 18,
    description: 'Conservacao e higienizacao predial',
  },
  {
    name: 'Manutencao Predial',
    percentage: 14,
    description: 'Instalacoes eletricas, hidraulicas e prediais',
  },
  {
    name: 'Tecnologia da Informacao',
    percentage: 11,
    description: 'Software, hardware e suporte tecnico',
  },
  {
    name: 'Alimentacao',
    percentage: 9,
    description: 'Refeicoes coletivas e merenda escolar',
  },
  {
    name: 'Seguranca Patrimonial',
    percentage: 8,
    description: 'Vigilancia e monitoramento',
  },
  {
    name: 'Transporte e Logistica',
    percentage: 7,
    description: 'Frota, fretamento e entregas',
  },
  {
    name: 'Moveis e Equipamentos',
    percentage: 5,
    description: 'Mobiliario, maquinas e equipamentos',
  },
];

// ---------------------------------------------------------------------------
// Client Component
// ---------------------------------------------------------------------------

export default function SubcontratacaoClient() {
  const [product, setProduct] = useState<DigitalProductOut | null>(null);
  const [productLoading, setProductLoading] = useState(true);

  const fetchProduct = useCallback(async () => {
    setProductLoading(true);
    try {
      const res = await fetch('/api/products');
      if (!res.ok) return;
      const data = (await res.json()) as ProductsResponse;
      const found = (data.products ?? []).find((p) => p.sku === PRODUCT_SKU);
      if (found) setProduct(found);
    } catch {
      // Silently fail — page is still usable without the checkout button
    } finally {
      setProductLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchProduct();
  }, [fetchProduct]);

  const { ref: heroRef, isVisible: heroVisible } = useScrollAnimation(0.1);

  return (
    <main>
      {/* ================================================================ */}
      {/* HERO SECTION                                                     */}
      {/* ================================================================ */}
      <section
        ref={heroRef}
        aria-label="Hero"
        className="relative overflow-hidden bg-gradient-to-br from-brand-navy to-brand-blue px-4 py-20 sm:py-28"
      >
        {/* Background mesh */}
        <div
          className="absolute inset-0 -z-10 opacity-30"
          style={{
            background: `
              radial-gradient(circle at 20% 50%, var(--brand-blue-subtle) 0%, transparent 50%),
              radial-gradient(circle at 80% 20%, rgba(255,255,255,0.08) 0%, transparent 40%)
            `,
          }}
        />

        <motion.div
          className="mx-auto max-w-4xl text-center"
          variants={staggerContainer}
          initial="hidden"
          animate={heroVisible ? 'visible' : 'hidden'}
        >
          <motion.h1
            className="text-3xl font-bold leading-tight text-white sm:text-4xl lg:text-5xl"
            variants={fadeInUp}
          >
            Encontre oportunidades de{' '}
            <span className="text-gradient">subcontratacao</span> no governo
          </motion.h1>

          <motion.p
            className="mx-auto mt-6 max-w-2xl text-lg text-white/80 sm:text-xl"
            variants={fadeInUp}
          >
            PMEs podem ser subcontratadas por vencedores de licitacao. Descubra
            pontes de subcontratacao no seu setor e transforme contratos
            publicos em receita para sua empresa.
          </motion.p>

          {/* CTA */}
          <motion.div
            className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center"
            variants={fadeInUp}
          >
            {productLoading ? (
              <div
                className="h-12 w-64 animate-pulse rounded-xl bg-white/20"
                data-testid="hero-cta-skeleton"
              />
            ) : product ? (
              <CheckoutButton
                product={product}
                context={PRODUCT_CONTEXT}
                variant="banner"
                label="Encontrar oportunidades de subcontratacao"
                data-testid="hero-checkout-button"
              />
            ) : (
              <a
                href={`/signup?source=subcontratacao-flagship`}
                className="inline-block rounded-xl bg-green-600 px-8 py-3 text-lg font-bold text-white shadow-lg transition-all hover:scale-[1.02] hover:bg-green-700 active:scale-[0.98]"
                data-testid="hero-cta-fallback"
              >
                Encontrar oportunidades de subcontratacao
              </a>
            )}

            {!productLoading && (
              <p className="text-sm text-white/60">
                Acesso vitalicio por R$97 — pagamento unico
              </p>
            )}
          </motion.div>

          {/* Trust signal */}
          <motion.p
            className="mt-4 text-sm text-white/50"
            variants={fadeInUp}
          >
            Dados oficiais do PNCP, PCP e ComprasGov • Atualizado em tempo real
          </motion.p>
        </motion.div>
      </section>

      {/* ================================================================ */}
      {/* EXPLANATION SECTION                                              */}
      {/* ================================================================ */}
      <ExplanationSection />

      {/* ================================================================ */}
      {/* STATS SECTION                                                    */}
      {/* ================================================================ */}
      <StatsSection stats={STATS} />

      {/* ================================================================ */}
      {/* SECTORS SECTION                                                  */}
      {/* ================================================================ */}
      <SectorsSection sectors={SECTORS} />

      {/* ================================================================ */}
      {/* PRODUCT CTA SECTION                                              */}
      {/* ================================================================ */}
      <ProductCtaSection />
    </main>
  );
}

// ---------------------------------------------------------------------------
// Explanation Section
// ---------------------------------------------------------------------------

function ExplanationSection() {
  const { ref, isVisible } = useScrollAnimation(0.1);

  const steps = [
    {
      title: 'Empresa vence a licitacao',
      description:
        'Uma empresa vence um contrato publico e precisa terceirizar parte da execucao — seja por falta de capacidade operacional ou por exigencias legais de subcontratacao (Lei 14.133, Art. 122).',
    },
    {
      title: 'Surge a oportunidade',
      description:
        'O vencedor busca fornecedores especializados para atender o contrato. Sua empresa pode entrar como subcontratada, fornecendo produtos, servicos ou mao de obra.',
    },
    {
      title: 'Sua empresa recebe',
      description:
        'A subcontratacao e formalizada em contrato, com prazos e valores definidos. Sua empresa fatura sem precisar participar diretamente da licitacao.',
    },
  ];

  return (
    <section
      ref={ref}
      aria-label="Como funciona a subcontratacao"
      className="bg-canvas px-4 py-16 sm:py-24"
    >
      <motion.div
        className="mx-auto max-w-5xl"
        variants={staggerContainer}
        initial="hidden"
        animate={isVisible ? 'visible' : 'hidden'}
      >
        <motion.h2
          className="mb-4 text-center text-2xl font-bold tracking-tight text-ink sm:text-3xl"
          variants={fadeInUp}
        >
          Como funciona a subcontratacao em licitacoes
        </motion.h2>
        <motion.p
          className="mx-auto mb-12 max-w-2xl text-center text-lg text-ink-secondary"
          variants={fadeInUp}
        >
          A Lei 14.133/2021 permite que empresas vencedoras de licitacoes
          subcontratem parte do objeto — criando oportunidades para PMEs de
          todos os portes.
        </motion.p>

        <div className="grid gap-8 sm:grid-cols-3">
          {steps.map((step, index) => (
            <motion.article
              key={step.title}
              className="rounded-xl border border-[var(--border)] bg-surface-0 p-6 text-center shadow-sm"
              variants={fadeInUp}
            >
              <div
                className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-brand-blue/10"
                aria-hidden="true"
              >
                <span className="text-lg font-bold text-brand-blue">
                  {index + 1}
                </span>
              </div>
              <h3 className="mb-2 text-lg font-bold text-ink">
                {step.title}
              </h3>
              <p className="text-sm leading-relaxed text-ink-secondary">
                {step.description}
              </p>
            </motion.article>
          ))}
        </div>
      </motion.div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Stats Section
// ---------------------------------------------------------------------------

function StatsSection({ stats }: { stats: StatItem[] }) {
  const { ref, isVisible } = useScrollAnimation(0.1);

  return (
    <section
      ref={ref}
      aria-label="Estatisticas de subcontratacao"
      className="border-y border-[var(--border)] bg-surface-1 px-4 py-16 sm:py-20"
    >
      <motion.div
        className="mx-auto max-w-5xl"
        variants={staggerContainer}
        initial="hidden"
        animate={isVisible ? 'visible' : 'hidden'}
      >
        <motion.h2
          className="mb-10 text-center text-2xl font-bold tracking-tight text-ink sm:text-3xl"
          variants={fadeInUp}
        >
          O mercado de subcontratacao publica
        </motion.h2>

        <div className="grid gap-6 sm:grid-cols-3">
          {stats.map((stat) => (
            <motion.div
              key={stat.label}
              className="rounded-xl border border-[var(--border)] bg-surface-0 p-8 text-center shadow-sm"
              variants={fadeInUp}
            >
              <div className="text-4xl font-bold text-brand-blue sm:text-5xl">
                {stat.value}
              </div>
              <p className="mt-3 text-sm text-ink-secondary">{stat.label}</p>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sectors Section
// ---------------------------------------------------------------------------

function SectorsSection({ sectors }: { sectors: SectorItem[] }) {
  const { ref, isVisible } = useScrollAnimation(0.1);

  return (
    <section
      ref={ref}
      aria-label="Setores com mais subcontratacao"
      className="bg-canvas px-4 py-16 sm:py-24"
    >
      <motion.div
        className="mx-auto max-w-5xl"
        variants={staggerContainer}
        initial="hidden"
        animate={isVisible ? 'visible' : 'hidden'}
      >
        <motion.h2
          className="mb-4 text-center text-2xl font-bold tracking-tight text-ink sm:text-3xl"
          variants={fadeInUp}
        >
          Setores com maior potencial de subcontratacao
        </motion.h2>
        <motion.p
          className="mx-auto mb-12 max-w-2xl text-center text-lg text-ink-secondary"
          variants={fadeInUp}
        >
          Construcao civil, limpeza e TI lideram o ranking de contratos com
          subcontratacao no Brasil.
        </motion.p>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {sectors.map((sector) => (
            <motion.div
              key={sector.name}
              className="group rounded-xl border border-[var(--border)] bg-surface-0 p-5 transition-all duration-300 hover:-translate-y-1 hover:border-brand-blue/50 hover:shadow-md"
              variants={fadeInUp}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-lg font-bold text-ink">
                  {sector.name}
                </span>
                <span className="rounded-full bg-brand-blue/10 px-2.5 py-0.5 text-sm font-semibold text-brand-blue">
                  {sector.percentage}%
                </span>
              </div>
              <p className="text-sm text-ink-secondary">
                {sector.description}
              </p>
              {/* Progress bar */}
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-1">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-brand-blue to-green-500 transition-all duration-700"
                  style={{ width: `${sector.percentage}%` }}
                  role="progressbar"
                  aria-valuenow={sector.percentage}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${sector.percentage}% dos contratos`}
                />
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Product CTA Section
// ---------------------------------------------------------------------------

function ProductCtaSection() {
  const { ref, isVisible } = useScrollAnimation(0.1);

  return (
    <section
      ref={ref}
      aria-label="Mapa de subcontratacao"
      className="bg-surface-1 px-4 py-16 sm:py-24"
    >
      <motion.div
        className="mx-auto max-w-3xl text-center"
        variants={staggerContainer}
        initial="hidden"
        animate={isVisible ? 'visible' : 'hidden'}
      >
        <motion.h2
          className="mb-4 text-2xl font-bold tracking-tight text-ink sm:text-3xl"
          variants={fadeInUp}
        >
          Mapa de subcontratacao para o seu setor
        </motion.h2>
        <motion.p
          className="mx-auto mb-10 max-w-xl text-lg text-ink-secondary"
          variants={fadeInUp}
        >
          Veja exatamente quais empresas venceram contratos publicos no seu
          setor, quem precisa de subcontratados e por qual valor.
        </motion.p>

        <motion.div variants={fadeInUp}>
          <DigitalProductPreview
            sku={PRODUCT_SKU}
            context={PRODUCT_CONTEXT}
            variant="card"
            className="mx-auto max-w-md text-left"
          />
        </motion.div>

        <motion.p
          className="mx-auto mt-6 max-w-lg text-sm text-ink-muted"
          variants={fadeInUp}
        >
          Dados atualizados em tempo real do PNCP, PCP e ComprasGov. Acesso
          vitalicio com pagamento unico de R$97.
        </motion.p>
      </motion.div>
    </section>
  );
}
