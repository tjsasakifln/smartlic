'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { trackPseoEvent } from '@/lib/analytics/pseo';

interface Props {
  cnpj: string;
  razaoSocial: string;
}

/**
 * Client component for the fornecedor lead-capture CTA section.
 * Fires pseo_supplier_viewed on mount and pseo_checkout_click on CTA click.
 * Extracted from the server component to keep the page SSR-rendered.
 *
 * CONV-002b: Updated to PSEOTemplate-style contextual CTA with
 * trial + "Só quero ver os dados" secondary link.
 */
export default function FornecedorPseoCTA({ cnpj, razaoSocial }: Props) {
  useEffect(() => {
    trackPseoEvent('pseo_supplier_viewed', {
      source_template: 'fornecedor_page',
      page_url: window.location.href,
      cnpj,
      nome: razaoSocial,
    });
  }, [cnpj, razaoSocial]);

  const destination = `/signup?ref=cnpj&cnpj=${cnpj}&utm_source=pseo&utm_medium=organic&utm_content=fornecedor_page`;

  const handleCheckoutClick = () => {
    trackPseoEvent('pseo_checkout_click', {
      source_template: 'fornecedor_page',
      destination,
    });
  };

  return (
    <section className="max-w-5xl mx-auto px-4 py-8">
      <div className="rounded-2xl border border-brand-blue/30 bg-brand-blue/5 dark:bg-brand-blue/10 p-6 sm:p-8">
        <p className="text-lg text-gray-900 dark:text-white mb-4">
          Quer receber alertas de editais e contratos públicos de <strong>{razaoSocial}</strong>?
        </p>
        <div className="flex flex-col sm:flex-row gap-3">
          <Link
            href={destination}
            onClick={handleCheckoutClick}
            className="inline-block px-6 py-3 bg-brand-blue text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors text-center"
          >
            Receber alertas grátis 14 dias →
          </Link>
          <Link
            href="/observatorio"
            className="inline-block px-6 py-3 bg-white dark:bg-gray-900 text-brand-navy dark:text-white font-medium rounded-lg border border-gray-300 dark:border-gray-700 hover:border-brand-blue transition-colors text-center"
          >
            Só quero ver os dados
          </Link>
        </div>
      </div>
    </section>
  );
}
