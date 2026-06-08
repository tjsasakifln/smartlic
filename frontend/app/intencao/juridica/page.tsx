/**
 * Intent landing page — Juridica (legal questions / Lei 14.133)
 *
 * Route: /intencao/juridica
 * Users arrive via IntentRouter (#1511) when searching for legal aspects
 * of public bidding, Lei 14.133, impugnacoes, and compliance.
 *
 * CTA is lead capture (Diagnostico + Consultoria), not direct checkout.
 */
import type { Metadata } from 'next';
import IntentLandingPage from '../../components/IntentLandingPage';
import IntentLandingLayout from '../IntentLandingLayout';

export const metadata: Metadata = {
  title: 'Assessoria Jurídica em Licitações — SmartLic',
  description:
    'Entenda a Lei 14.133, evite impugnações, prepare sua empresa para licitar com segurança jurídica.',
};

export default function JuridicaPage() {
  return (
    <IntentLandingLayout>
      <IntentLandingPage
        cluster="juridica"
        headline="Fundamentação jurídica para licitações"
        subtitle="Entenda a Lei 14.133, prepare sua empresa para licitar, evite impugnações e recursos"
        steps={[
          {
            title: '100% da legislação federal disponível',
            description:
              'Consulte a Lei 14.133, decretos regulamentadores e portarias atualizadas em um só lugar, com busca inteligente.',
          },
          {
            title: 'Editais completos com análise jurídica',
            description:
              'Acesse editais integrais com cláusulas destacadas e alertas para pontos críticos de habilitação e documentação.',
          },
          {
            title: 'Diagnóstico personalizado gratuito',
            description:
              'Receba uma avaliação gratuita da situação da sua empresa frente aos requisitos legais das licitações públicas.',
          },
        ]}
        socialProofText="Mais de 100 mil editais analisados com suporte jurídico. Advogados e consultores de todo o Brasil utilizam o SmartLic para embasar recursos e impugnações."
        ctaPrimary={{
          text: 'Diagnóstico gratuito →',
          href: '/signup?source=intent-juridica',
        }}
        ctaSecondary={{
          text: 'Falar com consultoria',
          href: '/contato',
        }}
        pageTitle="Assessoria Jurídica em Licitações — SmartLic"
        pageDescription="Entenda a Lei 14.133, evite impugnações, prepare sua empresa para licitar com segurança jurídica."
      />
    </IntentLandingLayout>
  );
}
