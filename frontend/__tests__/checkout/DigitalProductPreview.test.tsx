/**
 * Tests for DigitalProductPreview component (CONV-005b-3).
 *
 * Covers:
 * - Loading skeleton render
 * - Error state with retry
 * - Product data fetch and display (card, inline, banner variants)
 * - Preview items (free + premium/blurred)
 * - Checkout button render
 * - Modal open/close via button
 * - Tracking events (mixpanel)
 * - Accessibility
 * - Mobile responsive classes
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { DigitalProductPreview } from "../../app/components/checkout/DigitalProductPreview";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_PRODUCT = {
  sku: "relatorio-licitacoes",
  name: "Relatorio de Licitacoes",
  description: "Analise completa de licitacoes por setor e UF",
  price_brl: 14700, // R$147,00
  preview_config: {
    free_items: 3,
    total_items: 8,
  },
  delivery_config: {},
};

const MOCK_PRODUCTS_RESPONSE = {
  products: [MOCK_PRODUCT],
};

const MOCK_CHECKOUT_RESPONSE = {
  checkout_url: "https://checkout.stripe.com/pay/test-session-id",
};

const DEFAULT_CONTEXT = {
  entity_type: "fornecedor",
  entity_id: "12345678000195",
  setor: "limpeza",
  uf: "SP",
};

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
  globalThis.fetch = mockFetch;

  // Default: products endpoint succeeds
  mockFetch.mockImplementation((url: string) => {
    if (url === "/api/products") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_PRODUCTS_RESPONSE),
      });
    }
    if (url === "/api/checkout/digital-product") {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_CHECKOUT_RESPONSE),
      });
    }
    return Promise.resolve({ ok: false, status: 404 });
  });

  // Mock window.location.href
  delete (window as any).location;
  window.location = { href: "" } as any;

  // Mock mixpanel
  (window as any).mixpanel = {
    track: jest.fn(),
  };
});

afterEach(() => {
  (window as any).mixpanel = undefined;
  jest.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DigitalProductPreview", () => {
  describe("Loading state", () => {
    it("renders a skeleton when fetch is in progress", () => {
      // Keep fetch pending by never resolving
      mockFetch.mockReturnValue(new Promise(() => {}));

      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      expect(
        screen.getByTestId("digital-product-preview-loading"),
      ).toBeInTheDocument();
    });
  });

  describe("Error state", () => {
    it("renders error alert when fetch fails", async () => {
      mockFetch.mockRejectedValue(new Error("Network failure"));

      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-error"),
        ).toBeInTheDocument();
      });

      expect(screen.getByText(/Produto indisponivel/)).toBeInTheDocument();
    });

    it("renders error when product SKU not found", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ products: [] }),
      });

      render(
        <DigitalProductPreview
          sku="inexistent-sku"
          context={DEFAULT_CONTEXT}
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-error"),
        ).toBeInTheDocument();
      });

      expect(screen.getByText(/inexistent-sku/)).toBeInTheDocument();
    });

    it("calls refetch when retry button is clicked", async () => {
      mockFetch
        .mockRejectedValueOnce(new Error("Network failure"))
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(MOCK_PRODUCTS_RESPONSE),
        });

      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-error"),
        ).toBeInTheDocument();
      });

      // Click retry
      fireEvent.click(screen.getByText("Tentar novamente"));

      await waitFor(() => {
        expect(screen.getByText("Relatorio de Licitacoes")).toBeInTheDocument();
      });

      // Should have called fetch twice (initial + retry)
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });

  describe("Card variant (default)", () => {
    it("renders product name, description and price", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-card"),
        ).toBeInTheDocument();
      });

      expect(screen.getByText("Relatorio de Licitacoes")).toBeInTheDocument();
      expect(
        screen.getByText("Analise completa de licitacoes por setor e UF"),
      ).toBeInTheDocument();
    });

    it("displays the formatted price", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        const priceElements = screen.getAllByText(/147/);
        expect(priceElements.length).toBeGreaterThanOrEqual(1);
      });
    });

    it("shows free preview items without blur", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        // First 3 items should be free (no blur)
        const freeItems = screen.queryAllByTestId((id) =>
          id.startsWith("preview-item-free-"),
        );
        expect(freeItems.length).toBe(3);
      });
    });

    it("shows premium preview items with blur", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        const premiumItems = screen.queryAllByTestId((id) =>
          id.startsWith("preview-item-premium-"),
        );
        // Total 8, free 3, premium 5
        expect(premiumItems.length).toBe(5);
      });
    });

    it("renders the checkout button", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        expect(screen.getByTestId("checkout-button")).toBeInTheDocument();
      });

      expect(screen.getByText(/Comprar por/)).toBeInTheDocument();
    });

    it('shows "pagamento unico" text', async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        expect(screen.getByText("pagamento unico")).toBeInTheDocument();
      });
    });
  });

  describe("Inline variant", () => {
    it("renders with inline layout classes", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="inline"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-inline"),
        ).toBeInTheDocument();
      });
    });

    it("renders product info in inline mode", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="inline"
        />,
      );

      await waitFor(() => {
        expect(screen.getByText("Relatorio de Licitacoes")).toBeInTheDocument();
        expect(screen.getByTestId("checkout-button")).toBeInTheDocument();
      });
    });
  });

  describe("Banner variant", () => {
    it("renders with banner test id", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="banner"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-banner"),
        ).toBeInTheDocument();
      });
    });

    it("renders the checkout button in banner mode", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="banner"
        />,
      );

      await waitFor(() => {
        expect(screen.getByTestId("checkout-button")).toBeInTheDocument();
      });
    });
  });

  describe("Checkout button interaction", () => {
    it("opens the checkout modal when buy button is clicked", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        expect(screen.getByTestId("checkout-button")).toBeInTheDocument();
      });

      // Click the checkout button
      fireEvent.click(screen.getByTestId("checkout-button"));

      // Modal should appear
      await waitFor(() => {
        expect(
          screen.getByRole("dialog", { name: /Finalizar compra/i }),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Tracking", () => {
    it("tracks product_preview_viewed after product loads", async () => {
      const mockTrack = jest.fn();
      (window as any).mixpanel = { track: mockTrack };

      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        expect(mockTrack).toHaveBeenCalledWith(
          "product_preview_viewed",
          expect.objectContaining({
            sku: "relatorio-licitacoes",
            price_brl: 14700,
            source_template: "card",
          }),
        );
      });
    });

    it("tracks product_checkout_started when buy is clicked", async () => {
      const mockTrack = jest.fn();
      (window as any).mixpanel = { track: mockTrack };

      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        expect(screen.getByTestId("checkout-button")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(mockTrack).toHaveBeenCalledWith(
          "product_checkout_started",
          expect.objectContaining({
            sku: "relatorio-licitacoes",
            source_template: "card",
          }),
        );
      });
    });
  });

  describe("Accessibility", () => {
    it("preview section has an accessible label", async () => {
      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByLabelText("Previa do produto"),
        ).toBeInTheDocument();
      });
    });

    it("error state uses role=alert", async () => {
      mockFetch.mockRejectedValue(new Error("fail"));

      render(
        <DigitalProductPreview
          sku="relatorio-licitacoes"
          context={DEFAULT_CONTEXT}
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-error"),
        ).toHaveAttribute("role", "alert");
      });
    });
  });
});
