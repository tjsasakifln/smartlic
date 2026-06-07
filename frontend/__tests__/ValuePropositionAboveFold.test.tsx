/**
 * Tests for ValuePropositionAboveFold component (CONV-001).
 *
 * Verifies:
 * - Correct headline per entityType
 * - Renders valueProp and supportingDetail
 * - Semantic HTML validation
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import ValuePropositionAboveFold from '../app/components/conversion/ValuePropositionAboveFold';

describe('ValuePropositionAboveFold', () => {
  it('renders correct headline for orgao entity type', () => {
    render(
      <ValuePropositionAboveFold
        entityType="orgao"
        entityName="Prefeitura de Florianópolis"
        valueProp="Análise completa de licitações"
      />,
    );
    expect(
      screen.getByText('Quer vender para Prefeitura de Florianópolis?'),
    ).toBeInTheDocument();
  });

  it('renders correct headline for fornecedor entity type', () => {
    render(
      <ValuePropositionAboveFold
        entityType="fornecedor"
        entityName="Empresa ABC Ltda"
        valueProp="Monitore seus concorrentes"
      />,
    );
    expect(
      screen.getByText('Quer vencer mais licitações como Empresa ABC Ltda?'),
    ).toBeInTheDocument();
  });

  it('renders correct headline for cnpj entity type', () => {
    render(
      <ValuePropositionAboveFold
        entityType="cnpj"
        entityName="Empresa XYZ Ltda"
        valueProp="Análise de contratos"
      />,
    );
    expect(
      screen.getByText('Quer vencer mais licitações como Empresa XYZ Ltda?'),
    ).toBeInTheDocument();
  });

  it('renders correct headline for setor entity type', () => {
    render(
      <ValuePropositionAboveFold
        entityType="setor"
        entityName="Facilities"
        valueProp="Oportunidades de negócio"
      />,
    );
    expect(
      screen.getByText('Oportunidades no setor — Facilities'),
    ).toBeInTheDocument();
  });

  it('renders correct headline for municipio entity type', () => {
    render(
      <ValuePropositionAboveFold
        entityType="municipio"
        entityName="São Paulo"
        valueProp="Licitações municipais"
      />,
    );
    expect(
      screen.getByText('Licitações em São Paulo — acompanhe em tempo real'),
    ).toBeInTheDocument();
  });

  it('renders correct headline for contrato entity type', () => {
    render(
      <ValuePropositionAboveFold
        entityType="contrato"
        entityName="Contrato 2024/001"
        valueProp="Análise detalhada"
      />,
    );
    expect(
      screen.getByText('Análise completa do contrato — Contrato 2024/001'),
    ).toBeInTheDocument();
  });

  it('renders valueProp text', () => {
    render(
      <ValuePropositionAboveFold
        entityType="orgao"
        entityName="Prefeitura"
        valueProp="Análise personalizada com IA"
      />,
    );
    expect(
      screen.getByText('Análise personalizada com IA'),
    ).toBeInTheDocument();
  });

  it('renders supportingDetail when provided', () => {
    render(
      <ValuePropositionAboveFold
        entityType="orgao"
        entityName="Prefeitura"
        valueProp="Análise completa"
        supportingDetail="Dados atualizados diariamente"
      />,
    );
    expect(
      screen.getByText('Dados atualizados diariamente'),
    ).toBeInTheDocument();
  });

  it('does not render supportingDetail when not provided', () => {
    render(
      <ValuePropositionAboveFold
        entityType="orgao"
        entityName="Prefeitura"
        valueProp="Análise completa"
      />,
    );
    expect(screen.queryByText('Dados atualizados diariamente')).toBeNull();
  });

  it('uses semantic HTML — h1 and section with aria-label', () => {
    render(
      <ValuePropositionAboveFold
        entityType="orgao"
        entityName="Prefeitura"
        valueProp="Análise"
      />,
    );
    expect(
      screen.getByRole('heading', { level: 1 }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('region', { name: 'Proposta de valor' }),
    ).toBeInTheDocument();
  });
});
