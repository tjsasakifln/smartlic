/**
 * Tests for CheckoutModal component (CONV-005b-3).
 *
 * Covers:
 * - Modal visibility (open/closed)
 * - Product summary display
 * - Checkout button interaction
 * - Loading state
 * - Error state
 * - Success state
 * - Close button and Escape key
 * - Body scroll lock
 * - Accessibility
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CheckoutModal } from "../../app/components/checkout/CheckoutModal";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_PRODUCT = {
  sku: "relatorio-licitacoes",
  name: "Relatorio de Licitacoes",
  description: "Analise completa de licitacoes por setor e UF",
  price_brl: 14700,
  preview_config: { free_items: 3, total_items: 8 },
  delivery_config: {},
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
// Setup
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();
const mockOnClose = jest.fn();
const mockOnComplete = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
  globalThis.fetch = mockFetch;

  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(MOCK_CHECKOUT_RESPONSE),
  });

  delete (window as any).location;
  window.location = { href: "" } as any;

  (window as any).mixpanel = { track: jest.fn() };
});

afterEach(() => {
  (window as any).mixpanel = undefined;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("CheckoutModal", () => {
  describe("Visibility", () => {
    it("renders when isOpen is true", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(
        screen.getByRole("dialog", { name: /Finalizar compra/i }),
      ).toBeInTheDocument();
    });

    it("does not render when isOpen is false", () => {
      render(
        <CheckoutModal
          isOpen={false}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  describe("Product summary", () => {
    it("displays the product name", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(screen.getByText("Relatorio de Licitacoes")).toBeInTheDocument();
    });

    it("displays the product description", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(
        screen.getByText("Analise completa de licitacoes por setor e UF"),
      ).toBeInTheDocument();
    });

    it("displays the formatted price", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      // R$147,00 appears in both summary and button text
      const priceElements = screen.getAllByText(/147,00/);
      expect(priceElements.length).toBeGreaterThanOrEqual(1);
    });

    it("displays context info when provided", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(screen.getByText(/fornecedor/)).toBeInTheDocument();
      expect(screen.getByText(/12345678000195/)).toBeInTheDocument();
    });

    it("shows payment method info", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(
        screen.getByText(/cartao, boleto ou PIX/i),
      ).toBeInTheDocument();
    });
  });

  describe("Close behavior", () => {
    it("calls onClose when close button is clicked", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByLabelText(/Fechar modal/i));

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it("calls onClose when Escape key is pressed", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.keyDown(document, { key: "Escape" });

      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  describe("Checkout flow", () => {
    it("calls the checkout API when confirm is clicked", async () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          "/api/checkout/digital-product",
          expect.objectContaining({
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: expect.stringContaining("relatorio-licitacoes"),
          }),
        );
      });
    });

    it("calls onComplete on successful checkout", async () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          onComplete={mockOnComplete}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(mockOnComplete).toHaveBeenCalledTimes(1);
      });
    });

    it("redirects to Stripe checkout URL on success", async () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(window.location.href).toBe(
          "https://checkout.stripe.com/pay/test-session-id",
        );
      });
    });

    it("shows loading state while checkout is processing", async () => {
      // Keep fetch pending
      mockFetch.mockReturnValue(new Promise(() => {}));

      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(screen.getByText(/Processando.../)).toBeInTheDocument();
      });
    });

    it("disables close button during loading", async () => {
      mockFetch.mockReturnValue(new Promise(() => {}));

      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(screen.getByLabelText(/Fechar modal/i)).toBeDisabled();
      });
    });
  });

  describe("Error state", () => {
    it("shows error message when checkout API fails", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 400,
        json: () =>
          Promise.resolve({ detail: "Produto indisponivel no momento." }),
      });

      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(
          screen.getByText("Produto indisponivel no momento."),
        ).toBeInTheDocument();
      });
    });

    it("shows default error message when API returns non-JSON", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error("not json")),
      });

      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(
          screen.getByText(/Nao foi possivel iniciar o checkout/),
        ).toBeInTheDocument();
      });
    });

    it("shows generic error on network failure", async () => {
      mockFetch.mockRejectedValue(new Error("Network failure"));

      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(screen.getByText("Network failure")).toBeInTheDocument();
      });
    });

    it("allows retry after error (button is re-enabled)", async () => {
      mockFetch
        .mockRejectedValueOnce(new Error("Network failure"))
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve(MOCK_CHECKOUT_RESPONSE),
        });

      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      // First attempt — fails
      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));
      await waitFor(() => {
        expect(screen.getByText("Network failure")).toBeInTheDocument();
      });

      // Button should be re-enabled
      expect(screen.getByTestId("checkout-modal-confirm")).not.toBeDisabled();
    });
  });

  describe("Body scroll lock", () => {
    it("locks body scroll when open", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(document.body.style.overflow).toBe("hidden");
    });

    it("restores body scroll when closed via isOpen=false", () => {
      const { rerender } = render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      rerender(
        <CheckoutModal
          isOpen={false}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(document.body.style.overflow).toBe("");
    });
  });

  describe("Accessibility", () => {
    it("has role=dialog and aria-modal=true", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      const dialog = screen.getByRole("dialog");
      expect(dialog).toHaveAttribute("aria-modal", "true");
    });

    it("has aria-labelledby pointing to the title", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      const dialog = screen.getByRole("dialog");
      const titleId = dialog.getAttribute("aria-labelledby");

      expect(titleId).toBe("checkout-modal-title");

      const title = document.getElementById(titleId!);
      expect(title).toHaveTextContent("Finalizar compra");
    });

    it("close button has accessible label", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      const closeButton = screen.getByLabelText(/Fechar modal/i);
      expect(closeButton.tagName).toBe("BUTTON");
    });

    it("confirm button has test id for programmatic access", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(screen.getByTestId("checkout-modal-confirm")).toBeInTheDocument();
    });
  });

  describe("Confidence footer", () => {
    it("shows secure payment message", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(screen.getByText(/Pagamento 100% seguro/)).toBeInTheDocument();
    });

    it("shows 30-day guarantee message", () => {
      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(screen.getByText(/Garantia 30 dias/)).toBeInTheDocument();
    });
  });

  describe("Tracking events", () => {
    it("tracks modal view on open", () => {
      const mockTrack = jest.fn();
      (window as any).mixpanel = { track: mockTrack };

      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(mockTrack).toHaveBeenCalledWith(
        "product_checkout_modal_viewed",
        expect.objectContaining({ sku: "relatorio-licitacoes" }),
      );
    });

    it("tracks checkout start when confirm is clicked", async () => {
      const mockTrack = jest.fn();
      (window as any).mixpanel = { track: mockTrack };

      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(mockTrack).toHaveBeenCalledWith(
          "product_checkout_started",
          expect.objectContaining({ sku: "relatorio-licitacoes" }),
        );
      });
    });

    it("tracks redirect event on successful checkout", async () => {
      const mockTrack = jest.fn();
      (window as any).mixpanel = { track: mockTrack };

      render(
        <CheckoutModal
          isOpen={true}
          onClose={mockOnClose}
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-modal-confirm"));

      await waitFor(() => {
        expect(mockTrack).toHaveBeenCalledWith(
          "product_checkout_redirected",
          expect.objectContaining({ sku: "relatorio-licitacoes" }),
        );
      });
    });
  });
});
