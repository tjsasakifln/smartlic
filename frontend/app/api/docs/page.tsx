import { Metadata } from 'next';
import { SwaggerUI } from './SwaggerUI';

/**
 * API-SELF-005: Swagger UI em /api/docs — acesso público à documentação
 * interativa da API. Aponta para o backend /openapi.json.
 */

export const metadata: Metadata = {
  title: 'Documentação da API — Swagger UI',
  description:
    'Documentação interativa da API SmartLic. Explore endpoints, autenticação X-API-Key, e schemas de resposta.',
  alternates: {
    canonical: 'https://smartlic.tech/api/docs',
  },
  openGraph: {
    title: 'Documentação da API SmartLic — Swagger UI',
    description: 'Explore a API REST de licitações públicas com Swagger UI interativo.',
    type: 'website',
  },
};

export default function ApiDocsPage() {
  return <SwaggerUI />;
}
