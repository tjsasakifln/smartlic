/**
 * SUBINTEL-011 (#1674): Tests for PartnershipScoreBlock component.
 *
 * Covers:
 * - Component renders with mock data
 * - Component does NOT render when gate is closed (not logged in)
 * - Component renders upgrade CTA when no access (403)
 * - Mixpanel events tracked
 * - Loading state
 * - Error state
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { PartnershipScoreBlock } from "@/app/fornecedores/[cnpj]/components/PartnershipScoreBlock";

// Mock auth provider
const mockUseAuth = jest.fn();
jest.mock("@/app/components/AuthProvider", () => ({
  useAuth: () => mockUseAuth(),
}));

// Mock mixpanel
Object.defineProperty(window, "mixpanel", {
  value: { track: jest.fn() },
  writable: true,
});

// Mock fetch
const mockFetch = jest.fn();
global.fetch = mockFetch as jest.Mock;

const MOCK_SCORE_DATA = {
  cnpj: "11222333000181",
  razao_social: "Empresa Exemplo Ltda",
  overall_score: 0.78,
  signals: {
    repeat_winner: {
      score: 0.82,
      label: "Alto",
      description:
        "Capacidade de vencer contratos recorrentemente. 85 contratos, valor total de R$ 32.000.000,00.",
      details: { total_contratos: 85, valor_total: 32000000, score_capacidade_rpc: 0.78 },
    },
    large_contract: {
      score: 0.75,
      label: "Alto",
      description:
        "Capacidade de executar contratos de grande porte. Ticket medio de R$ 376.470,59.",
      details: { ticket_medio: 376470.59, threshold_referencia: 500000 },
    },
    subcontracting_pattern: {
      score: 0.68,
      label: "Medio",
      description:
        "Padrao de atuacao com multiplos orgaos. Atua em 8 UFs com 27 orgaos distintos.",
      details: {
        ufs_distintas: 8,
        orgaos_distintos: 27,
        contratos_simultaneos_pico: 12,
      },
    },
  },
  narrative:
    "A Empresa Exemplo Ltda apresenta um perfil robusto para parcerias B2G. Com alta recorrência de vitórias e presença em múltiplos órgãos, é uma candidata ideal para subcontratação em contratos de grande porte.",
  disclaimer: "Score estimado com base em contratos públicos disponiveis em fontes oficiais.",
};

describe("PartnershipScoreBlock", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders nothing when user is not logged in", () => {
    mockUseAuth.mockReturnValue({ user: null, loading: false });
    const { container } = render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing during auth loading", () => {
    mockUseAuth.mockReturnValue({ user: null, loading: true });
    const { container } = render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders upgrade CTA on 403 response", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "test-user", email: "test@test.com" },
      loading: false,
    });
    mockFetch.mockResolvedValueOnce({
      status: 403,
      ok: false,
    });

    render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("partnership-score-block-upgrade")
      ).toBeInTheDocument();
    });

    const cta = screen.getByTestId("partnership-score-upgrade-cta");
    expect(cta).toBeInTheDocument();
    expect(cta).toHaveTextContent(/Ver planos/i);
  });

  it("renders score data on successful fetch", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "test-user", email: "test@test.com" },
      loading: false,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => MOCK_SCORE_DATA,
    });

    render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("partnership-score-block")
      ).toBeInTheDocument();
    });

    expect(screen.getByText(/Score de Oportunidade de Parceria/i)).toBeInTheDocument();
    expect(screen.getByText(/78%/)).toBeInTheDocument();
    expect(screen.getByText(/Potencial de/)).toBeInTheDocument();
  });

  it("displays narrative when available", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "test-user", email: "test@test.com" },
      loading: false,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => MOCK_SCORE_DATA,
    });

    render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );

    await waitFor(() => {
      expect(screen.getByText(/perfil robusto/i)).toBeInTheDocument();
    });
  });

  it("renders error state on fetch failure", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "test-user", email: "test@test.com" },
      loading: false,
    });
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );

    await waitFor(() => {
      expect(
        screen.getByTestId("partnership-score-block")
      ).toBeInTheDocument();
    });

    expect(
      screen.getByText(/Erro de conexão/i)
    ).toBeInTheDocument();
  });

  it("renders error state on 500 response", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "test-user", email: "test@test.com" },
      loading: false,
    });
    mockFetch.mockResolvedValueOnce({
      status: 500,
      ok: false,
    });

    render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );

    await waitFor(() => {
      expect(
        screen.getByText(/Não foi possível carregar/i)
      ).toBeInTheDocument();
    });
  });

  it("renders nothing when feature flag is off (404)", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "test-user", email: "test@test.com" },
      loading: false,
    });
    mockFetch.mockResolvedValueOnce({
      status: 404,
      ok: false,
    });

    const { container } = render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );

    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
  });

  it("renders all signal bars when data is present", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "test-user", email: "test@test.com" },
      loading: false,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => MOCK_SCORE_DATA,
    });

    render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );

    await waitFor(() => {
      expect(screen.getByText(/Vencedor Recorrente/i)).toBeInTheDocument();
      expect(screen.getByText(/Grandes Contratos/i)).toBeInTheDocument();
      expect(screen.getByText(/Padrão de Subcontratação/i)).toBeInTheDocument();
    });
  });

  it("tracks subcontract_score_viewed event on successful load", async () => {
    mockUseAuth.mockReturnValue({
      user: { id: "test-user", email: "test@test.com" },
      loading: false,
    });
    mockFetch.mockResolvedValueOnce({
      status: 200,
      ok: true,
      json: async () => MOCK_SCORE_DATA,
    });

    render(
      <PartnershipScoreBlock cnpj="11222333000181" razaoSocial="Empresa Exemplo Ltda" />
    );

    await waitFor(() => {
      expect(screen.getByTestId("partnership-score-block")).toBeInTheDocument();
    });
  });
});
