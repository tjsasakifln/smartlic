'use client';

import Link from 'next/link';
import { trackPseoEvent } from '@/lib/analytics/pseo';

interface AlertEntityCtaProps {
  /** Entity type: cnpj | orgao | setor | municipio */
  entityType: string;
  /** Entity ID/slug */
  entityId: string;
  /** Display label for the entity (e.g., company name, sector name, orgão name) */
  entityLabel: string;
  /** Optional UF for setor+uf combination */
  uf?: string;
}

/**
 * Alert CTA component for pSEO entity pages (CONV-014).
 * Renders a call-to-action that links to /dashboard/alertas with pre-filled
 * filter params, and fires an alert_upgrade_cta_click tracking event.
 */
export default function AlertEntityCta({
  entityType,
  entityId,
  entityLabel,
  uf,
}: AlertEntityCtaProps) {
  const params = new URLSearchParams();
  params.set(entityType, entityId);
  if (uf) params.set('uf', uf);

  const destination = `/dashboard/alertas?${params.toString()}`;

  const getCtaLabel = (): string => {
    switch (entityType) {
      case 'cnpj':
        return `Monitorar contratos de ${entityLabel}`;
      case 'orgao':
        return `Monitorar editais de ${entityLabel}`;
      case 'setor':
        return uf
          ? `Criar alerta de ${entityLabel} em ${uf}`
          : `Criar alerta de ${entityLabel}`;
      case 'municipio':
        return `Receber editais de ${entityLabel}`;
      default:
        return 'Criar alerta personalizado';
    }
  };

  const getSourceTemplate = (): string => {
    switch (entityType) {
      case 'cnpj': return 'alerta_fornecedor_page';
      case 'orgao': return 'alerta_orgao_page';
      case 'setor': return 'alerta_setor_page';
      case 'municipio': return 'alerta_municipio_page';
      default: return 'alerta_setor_page';
    }
  };

  return (
    <section className="mt-6 rounded-xl border border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-800 p-6">
      <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-1">
        {getCtaLabel()}
      </h3>
      <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
        Receba notificações automáticas quando novos editais forem publicados.
        {!uf && ' Defina seus filtros e seja avisado por email.'}
      </p>
      <Link
        href={destination}
        onClick={() =>
          trackPseoEvent('alert_upgrade_cta_click', {
            source_template: getSourceTemplate(),
            entity_type: entityType,
            entity_id: entityId,
            uf: uf || null,
          })
        }
        className="inline-block rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
        data-cta-source={`pseo-alert-${entityType}`}
      >
        {getCtaLabel()} →
      </Link>
    </section>
  );
}
