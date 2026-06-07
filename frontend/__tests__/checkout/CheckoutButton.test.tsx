/**
 * Tests for CheckoutButton component (CONV-005b-3).
 *
 * Covers:
 * - Default label with formatted price
 * - Custom label override
 * - Click handler calls fetch and redirects
 * - Loading state with spinner
 * - Error handling
 * - Disabled state
 * - Variant styles (inline, card, banner)
 * - Accessibility
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CheckoutButton } from "../../app/components/checkout/CheckoutButton";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_PRODUCT = {
  sku: "relatorio-licitacoes",
  name: "Relatorio de Licitacoes",
  description: "Analise completa",
  price_brl: 14700,
  preview_config: {},
  delivery_config: {},
};

const MOCK_CHECKOUT_RESPONSE = {
  checkout_url: "https://checkout.stripe.com/pay/test-session-id",
};

const DEFAULT_CONTEXT = {
  entity_type: "fornecedor",
  entity_id: "12345678000195",
};

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();

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

describe("CheckoutButton", () => {
  describe("Label rendering", () => {
    it("renders default label with formatted price", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(
        screen.getByText(/Comprar por/),
      ).toBeInTheDocument();
    });

    it("renders custom label when provided", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          label="Quero este relatorio"
        />,
      );

      expect(
        screen.getByText("Quero este relatorio"),
      ).toBeInTheDocument();
    });

    it("renders with button tag", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      const button = screen.getByTestId("checkout-button");
      expect(button.tagName).toBe("BUTTON");
    });
  });

  describe("Click behavior", () => {
    it("calls checkout API on click", async () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          "/api/checkout/digital-product",
          expect.objectContaining({
            method: "POST",
            headers: { "Content-Type": "application/json" },
          }),
        );
      });
    });

    it("sends SKU and context in request body", async () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          "/api/checkout/digital-product",
          expect.objectContaining({
            body: expect.stringContaining("relatorio-licitacoes"),
          }),
        );
      });
    });

    it("redirects to Stripe checkout URL on success", async () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(window.location.href).toBe(
          "https://checkout.stripe.com/pay/test-session-id",
        );
      });
    });

    it("calls onClick prop when provided", async () => {
      const onClick = jest.fn();

      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          onClick={onClick}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(onClick).toHaveBeenCalledTimes(1);
      });
    });

    it("calls onComplete prop on successful redirect", async () => {
      const onComplete = jest.fn();

      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          onComplete={onComplete}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(onComplete).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe("Loading state", () => {
    it("shows spinner and Aguarde... text while loading", async () => {
      // Keep fetch pending
      mockFetch.mockReturnValue(new Promise(() => {}));

      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(screen.getByText(/Aguarde.../)).toBeInTheDocument();
      });
    });

    it("disables button while loading", async () => {
      mockFetch.mockReturnValue(new Promise(() => {}));

      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(screen.getByTestId("checkout-button")).toBeDisabled();
      });
    });
  });

  describe("Error handling", () => {
    it("shows error from backend detail on failed checkout", async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 400,
        json: () =>
          Promise.resolve({ detail: "Produto nao encontrado" }),
      });

      const alertMock = jest.spyOn(window, "alert").mockImplementation(() => {});

      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(alertMock).toHaveBeenCalledWith("Produto nao encontrado");
      });

      alertMock.mockRestore();
    });

    it("shows default error on network failure", async () => {
      mockFetch.mockRejectedValue(new Error("Network failure"));

      const alertMock = jest.spyOn(window, "alert").mockImplementation(() => {});

      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      await waitFor(() => {
        expect(alertMock).toHaveBeenCalledWith("Network failure");
      });

      alertMock.mockRestore();
    });

    it("re-enables button after error", async () => {
      mockFetch.mockRejectedValue(new Error("fail"));

      const alertMock = jest.spyOn(window, "alert").mockImplementation(() => {});

      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));
      await waitFor(() => expect(alertMock).toHaveBeenCalled());

      expect(screen.getByTestId("checkout-button")).not.toBeDisabled();
      alertMock.mockRestore();
    });
  });

  describe("Disabled state", () => {
    it("renders disabled when disabled prop is true", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          disabled={true}
        />,
      );

      expect(screen.getByTestId("checkout-button")).toBeDisabled();
    });

    it("does not call fetch when disabled", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          disabled={true}
        />,
      );

      fireEvent.click(screen.getByTestId("checkout-button"));

      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe("Variant styles", () => {
    it("renders with card variant (default)", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          variant="card"
        />,
      );

      const button = screen.getByTestId("checkout-button");
      expect(button.className).toContain("rounded-xl");
    });

    it("renders with inline variant", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          variant="inline"
        />,
      );

      const button = screen.getByTestId("checkout-button");
      expect(button.className).toContain("rounded-lg");
    });

    it("renders with banner variant", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          variant="banner"
        />,
      );

      const button = screen.getByTestId("checkout-button");
      expect(button.className).toContain("bg-white");
    });
  });

  describe("Accessibility", () => {
    it("button has data-testid for programmatic access", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
        />,
      );

      expect(screen.getByTestId("checkout-button")).toBeInTheDocument();
    });

    it("disabled button has aria-disabled semantics via CSS", () => {
      render(
        <CheckoutButton
          product={MOCK_PRODUCT}
          context={DEFAULT_CONTEXT}
          disabled={true}
        />,
      );

      const button = screen.getByTestId("checkout-button");
      expect(button).toBeDisabled();
      expect(button.className).toContain("disabled:opacity-60");
    });
  });
});
