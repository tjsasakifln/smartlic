/**
 * Tests for STORY-356 — Pipeline limit enforcement frontend handling.
 *
 * AC4 (updated): When backend returns 403 PIPELINE_LIMIT_EXCEEDED, frontend
 * redirects to upgrade page instead of showing "Limite" badge.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AddToPipelineButton } from '../../app/components/AddToPipelineButton';
import type { LicitacaoItem } from '../../app/types';

// Mock usePipeline hook
const mockAddItem = jest.fn();
jest.mock('../../hooks/usePipeline', () => ({
  usePipeline: () => ({
    addItem: mockAddItem,
    items: [],
    alerts: [],
    loading: false,
    error: null,
    total: 0,
    fetchItems: jest.fn(),
    fetchAlerts: jest.fn(),
    updateItem: jest.fn(),
    removeItem: jest.fn(),
  }),
}));

// Mock useAnalytics hook
const mockTrackEvent = jest.fn();
jest.mock('../../hooks/useAnalytics', () => ({
  useAnalytics: () => ({ trackEvent: mockTrackEvent }),
}));

describe('STORY-356: Pipeline limit enforcement', () => {
  const mockLicitacao: LicitacaoItem = {
    pncp_id: "12345678-1-000001/2026",
    objeto: "Aquisicao de uniformes",
    orgao: "Prefeitura de Sao Paulo",
    uf: "SP",
    municipio: "Sao Paulo",
    valor: 150000,
    modalidade: "Pregao Eletronico",
    data_publicacao: "2026-02-01",
    data_abertura: "2026-02-15",
    data_encerramento: "2026-03-01",
    status_display: "Recebendo Proposta",
    link: "https://pncp.gov.br/app/editais/12345",
    relevance_score: 0.95,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    // Replace window.location so href assignment can be observed
    delete (window as any).location;
    (window as any).location = { href: '' };
  });

  it('redirects to upgrade page when pipeline limit exceeded (AC4)', async () => {
    const limitError = new Error("Limite de 5 itens no pipeline atingido.");
    (limitError as any).isPipelineLimitExceeded = true;
    mockAddItem.mockRejectedValue(limitError);

    render(<AddToPipelineButton licitacao={mockLicitacao} />);
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(window.location.href).toBe(
        '/planos?utm_source=pipeline_cap&utm_campaign=trial_activation'
      );
    });
  });

  it('tracks pipeline_limit_upgrade_cta_clicked when limit exceeded', async () => {
    const limitError = new Error("Limite de 5 itens no pipeline atingido.");
    (limitError as any).isPipelineLimitExceeded = true;
    mockAddItem.mockRejectedValue(limitError);

    render(<AddToPipelineButton licitacao={mockLicitacao} />);
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(mockTrackEvent).toHaveBeenCalledWith(
        'pipeline_limit_upgrade_cta_clicked',
        expect.objectContaining({ pncp_id: mockLicitacao.pncp_id })
      );
    });
  });

  it('distinguishes limit error from upgrade error', async () => {
    // Upgrade error (no isPipelineLimitExceeded flag)
    mockAddItem.mockRejectedValue(new Error('Pipeline nao disponivel no seu plano.'));

    render(<AddToPipelineButton licitacao={mockLicitacao} />);
    fireEvent.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(screen.getByText('Upgrade')).toBeInTheDocument();
    });
  });
});
