/**
 * Tests for ObrigadoClient component (#1337).
 *
 * Covers:
 * - Loading state (initial render, no session_id)
 * - Session status fetch (success)
 * - Product name display
 * - Error state (network failure)
 * - Not found state (404)
 * - Processing state
 * - Ready/completed state
 * - Navigation links
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import ObrigadoClient from "../../app/obrigado/ObrigadoClient";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockUseSearchParams = jest.fn();
const mockUseRouter = jest.fn();

jest.mock("next/navigation", () => ({
  useSearchParams: () => mockUseSearchParams(),
  useRouter: () => mockUseRouter(),
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();
const mockMixpanelTrack = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
  globalThis.fetch = mockFetch;
  (window as any).mixpanel = { track: mockMixpanelTrack };
});

afterEach(() => {
  (window as any).mixpanel = undefined;
});

function mockSearchParams(params: Record<string, string>) {
  const urlSearchParams = new URLSearchParams(params);
  mockUseSearchParams.mockReturnValue(urlSearchParams);
}

function mockFetchResponse(
  status: number,
  data: Record<string, unknown> | null,
) {
  mockFetch.mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ObrigadoClient", () => {
  describe("Loading state", () => {
    it('shows "Verificando pagamento..." on initial render', () => {
      mockFetch.mockReturnValue(new Promise(() => {}));
      mockSearchParams({ session_id: "cs_test_abc123" });

      render(<ObrigadoClient />);

      expect(screen.getByText("Verificando pagamento...")).toBeInTheDocument();
    });

    it("shows not-found state when session_id is missing", () => {
      mockSearchParams({});

      render(<ObrigadoClient />);

      expect(
        screen.getByText("Nenhuma sessão de pagamento encontrada."),
      ).toBeInTheDocument();
    });
  });

  describe("Session fetch", () => {
    it("fetches session status on mount", async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "completed",
        sku: "relatorio-licitacoes",
        product_name: "Relatório de Licitações",
        pdf_url: null,
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          "/api/checkout/session/cs_test_abc123",
        );
      });
    });

    it("displays product name when available", async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "completed",
        sku: "relatorio-licitacoes",
        product_name: "Relatório de Licitações",
        pdf_url: null,
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(
          screen.getByText("Relatório de Licitações"),
        ).toBeInTheDocument();
      });
    });

    it('shows "Pagamento confirmado!" on success', async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "completed",
        sku: "relatorio-licitacoes",
        product_name: "Relatório de Licitações",
        pdf_url: null,
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(
          screen.getAllByText("Pagamento confirmado!").length,
        ).toBeGreaterThanOrEqual(1);
      });
    });

    it("handles 404 gracefully", async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(404, null);

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(
          screen.getByText(/pode levar alguns instantes/i),
        ).toBeInTheDocument();
      });
    });

    it("handles network error gracefully", async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetch.mockRejectedValue(new Error("Network failure"));

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(
          screen.getByText(/Não foi possível verificar o status/i),
        ).toBeInTheDocument();
      });
    });

    it("shows processing message for generating status", async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "generating",
        sku: "relatorio-licitacoes",
        product_name: "Relatório de Licitações",
        pdf_url: null,
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(
          screen.getByText("Seu relatório está sendo gerado."),
        ).toBeInTheDocument();
      });
    });

    it("shows ready message for ready status", async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "ready",
        sku: "relatorio-licitacoes",
        product_name: "Relatório de Licitações",
        pdf_url: "https://storage.example.com/report.pdf",
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(
          screen.getByText("Seu relatório está pronto para download!"),
        ).toBeInTheDocument();
      });
    });

    it("shows download link when pdf_url is available", async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "ready",
        sku: "relatorio-licitacoes",
        product_name: "Relatório de Licitações",
        pdf_url: "https://storage.example.com/report.pdf",
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(screen.getByText("Baixar relatório")).toBeInTheDocument();
      });
    });

    it("handles failed status gracefully", async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "failed",
        sku: "relatorio-licitacoes",
        product_name: "Relatório de Licitações",
        pdf_url: null,
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(
          screen.getByText(/ocorreu um erro ao gerar o relatório/i),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Navigation links", () => {
    it('renders "Ir para busca" link', async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "completed",
        product_name: null,
        sku: null,
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(screen.getByText("Ir para busca")).toBeInTheDocument();
      });
    });

    it('renders "Ver minhas compras" link', async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "completed",
        product_name: null,
        sku: null,
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(screen.getByText("Ver minhas compras")).toBeInTheDocument();
      });
    });

    it("renders support email link", async () => {
      mockSearchParams({ session_id: "cs_test_abc123" });
      mockFetchResponse(200, {
        status: "completed",
        product_name: null,
        sku: null,
      });

      render(<ObrigadoClient />);

      await waitFor(() => {
        expect(
          screen.getByText("tiago@confenge.com.br"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Tracking events", () => {
    it("tracks page view on mount", () => {
      mockSearchParams({ session_id: "cs_test_abc123" });

      render(<ObrigadoClient />);

      expect(mockMixpanelTrack).toHaveBeenCalledWith(
        "obrigado_page_viewed",
        expect.objectContaining({ session_id: "cs_test_abc123" }),
      );
    });
  });
});
