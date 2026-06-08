/**
 * Tests for SectorUfIntelReportCTA component (Issue #633).
 *
 * Covers:
 * - Rendering with default props
 * - DigitalProductPreview integration (loading, error, card/inline/banner variants)
 * - Tracking events (sector_uf_cta_impression, sector_uf_cta_click)
 * - Custom checkout label
 * - Custom className passthrough
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SectorUfIntelReportCTA from "../../app/components/SectorUfIntelReportCTA";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_PRODUCT = {
  sku: "mapa-oportunidade-setorial",
  name: "Mapa de Oportunidade Setorial",
  description: "Analise completa do setor por UF",
  price_brl: 4700, // R$47,00
  preview_config: {
    free_items: 3,
    total_items: 8,
    item_labels: [
      "Total de editais abertos",
      "Valor total estimado",
      "Principais orgaos compradores",
      "Top fornecedores do setor",
      "Distribuicao por modalidade",
      "Tendencia de contratacao",
      "Analise de concorrencia",
      "Score de viabilidade medio",
    ],
  },
  delivery_config: {},
};

const MOCK_PRODUCTS_RESPONSE = {
  products: [MOCK_PRODUCT],
};

const MOCK_CHECKOUT_RESPONSE = {
  checkout_url: "https://checkout.stripe.com/pay/test-session-id",
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

describe("SectorUfIntelReportCTA", () => {
  describe("Rendering", () => {
    it("renders DigitalProductPreview with correct SKU", async () => {
      const { container } = render(
        <SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />,
      );

      await waitFor(() => {
        // The product name (from mock data) should appear
        expect(
          screen.getByText("Mapa de Oportunidade Setorial"),
        ).toBeInTheDocument();
      });

      // Verify fetch was called for the correct SKU
      expect(mockFetch).toHaveBeenCalledWith("/api/products");
    });

    it("shows free preview items without blur", async () => {
      render(<SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />);

      await waitFor(() => {
        // First 3 items should be free (no blur)
        const freeItems = screen.queryAllByTestId((id) =>
          id.startsWith("preview-item-free-"),
        );
        expect(freeItems.length).toBe(3);
      });
    });

    it("shows premium preview items with blur", async () => {
      render(<SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />);

      await waitFor(() => {
        const premiumItems = screen.queryAllByTestId((id) =>
          id.startsWith("preview-item-premium-"),
        );
        // Total 8, free 3, premium 5
        expect(premiumItems.length).toBe(5);
      });
    });

    it("renders the checkout button", async () => {
      render(<SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />);

      await waitFor(() => {
        expect(screen.getByTestId("checkout-button")).toBeInTheDocument();
      });
    });
  });

  describe("Checkout label", () => {
    it("uses default checkout label when not provided", async () => {
      render(<SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />);

      await waitFor(() => {
        expect(
          screen.getByText("Mapa Completo deste Setor — R$47"),
        ).toBeInTheDocument();
      });
    });

    it("accepts custom checkout label", async () => {
      render(
        <SectorUfIntelReportCTA
          sectorName="limpeza"
          uf="SP"
          checkoutLabel="Quero este mapa personalizado — R$47"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByText("Quero este mapa personalizado — R$47"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Variants", () => {
    it("renders with inline variant (default)", async () => {
      render(<SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />);

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-inline"),
        ).toBeInTheDocument();
      });
    });

    it("renders with card variant", async () => {
      render(
        <SectorUfIntelReportCTA
          sectorName="limpeza"
          uf="SP"
          variant="card"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-card"),
        ).toBeInTheDocument();
      });
    });

    it("renders with banner variant", async () => {
      render(
        <SectorUfIntelReportCTA
          sectorName="limpeza"
          uf="SP"
          variant="banner"
        />,
      );

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-banner"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Tracking", () => {
    it("tracks sector_uf_cta_impression on mount", async () => {
      const mockTrack = jest.fn();
      (window as any).mixpanel = { track: mockTrack };

      render(<SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />);

      await waitFor(() => {
        expect(mockTrack).toHaveBeenCalledWith(
          "sector_uf_cta_impression",
          expect.objectContaining({
            sector_id: "limpeza",
            uf: "SP",
            sku: "mapa-oportunidade-setorial",
          }),
        );
      });
    });

    it("tracks sector_uf_cta_click when checkout starts", async () => {
      const mockTrack = jest.fn();
      (window as any).mixpanel = { track: mockTrack };

      render(<SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />);

      await waitFor(() => {
        expect(screen.getByTestId("checkout-button")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(mockTrack).toHaveBeenCalledWith(
          "sector_uf_cta_click",
          expect.objectContaining({
            sector_id: "limpeza",
            uf: "SP",
            sku: "mapa-oportunidade-setorial",
          }),
        );
      });
    });
  });

  describe("Loading state", () => {
    it("renders loading skeleton while fetching product", () => {
      // Keep fetch pending
      mockFetch.mockReturnValue(new Promise(() => {}));

      render(<SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />);

      expect(
        screen.getByTestId("digital-product-preview-loading"),
      ).toBeInTheDocument();
    });
  });

  describe("Error state", () => {
    it("renders error alert when fetch fails", async () => {
      mockFetch.mockRejectedValue(new Error("Network failure"));

      render(<SectorUfIntelReportCTA sectorName="limpeza" uf="SP" />);

      await waitFor(() => {
        expect(
          screen.getByTestId("digital-product-preview-error"),
        ).toBeInTheDocument();
      });
    });
  });

  describe("Custom className", () => {
    it("passes className to DigitalProductPreview", async () => {
      const { container } = render(
        <SectorUfIntelReportCTA
          sectorName="limpeza"
          uf="SP"
          className="my-custom-class"
        />,
      );

      await waitFor(() => {
        const element = container.querySelector(".my-custom-class");
        expect(element).toBeInTheDocument();
      });
    });
  });
});
