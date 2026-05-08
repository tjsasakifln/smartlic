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

  return (
    <section className="mt-4 bg-blue-50 rounded-lg p-6 text-center">
      <h2 className="text-xl font-bold text-gray-900 mb-2">
        Monitore editais do setor de {razaoSocial}
      </h2>
      <p className="text-gray-600 mb-4">
        O SmartLic rastreia licitações abertas nas fontes oficiais e avisa quando surgem
        oportunidades relevantes para sua empresa.
      </p>
      <Link
        href={destination}
        onClick={() =>
          trackPseoEvent('pseo_checkout_click', {
            source_template: 'fornecedor_page',
            destination,
          })
        }
        className="inline-block px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors"
      >
        Testar 14 dias grátis →
      </Link>
    </section>
  );
}
