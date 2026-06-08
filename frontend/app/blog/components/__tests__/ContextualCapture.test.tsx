/**
 * Tests for ContextualCapture (#1312 REV-004).
 *
 * Covers:
 *  - Sentinel div renders when not visible
 *  - Email form appears after scroll threshold (mock)
 *  - Submit transitions to PartialReportPreview
 *  - Error state on failed submission
 *  - Mobile responsive layout
 */

import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ContextualCapture } from "../ContextualCapture";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockFetch = jest.fn();
let intersectionCallback: ((entries: IntersectionObserverEntry[]) => void) | null = null;

beforeEach(() => {
  jest.clearAllMocks();
  // URL-aware mock: products always succeed, lead-capture always succeeds
  (global as unknown as { fetch: jest.Mock }).fetch = jest.fn(
    (url: string) => {
      if (url === "/api/products") {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            products: [
              {
                sku: "relatorio-setorial",
                price_brl: 4700,
                name: "Relatorio completo",
                description: null,
                delivery_config: {},
                preview_config: {},
              },
            ],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    },
  );

  // Mock IntersectionObserver to fire immediately
  const mockObserve = jest.fn();
  const mockDisconnect = jest.fn();

  intersectionCallback = null;

  (global as unknown as { IntersectionObserver: unknown }).IntersectionObserver =
    jest.fn((cb: (entries: IntersectionObserverEntry[]) => void) => {
      intersectionCallback = cb;
      return {
        observe: mockObserve,
        disconnect: mockDisconnect,
        unobserve: jest.fn(),
      };
    });
});

afterEach(() => {
  // Restore scroll position
  window.scrollY = 0;
});

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const PREVIEW_DATA = [
  { label: "Total de editais no setor (12 meses)", value: "2.847" },
  { label: "Valor total adjudicado", value: "R$ 89,2 M" },
  { label: "Ticket medio por contrato", value: "R$ 31.340" },
];

const BLURRED_DATA = [
  { label: "Principais orgaos contratantes" },
  { label: "Concorrentes frequentes por orgao" },
  { label: "Prazo medio de publicacao a sessao" },
  { label: "Taxa de sucesso por modalidade" },
  { label: "Valor estimado vs adjudicado medio" },
];

const BASE_PROPS = {
  previewData: PREVIEW_DATA,
  blurredData: BLURRED_DATA,
  productSku: "relatorio-setorial",
  contextInfo: { entity_type: "setor", entity_id: "teste" },
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ContextualCapture", () => {
  it("renders sentinel when not visible (before scroll threshold)", () => {
    render(<ContextualCapture {...BASE_PROPS} />);

    expect(
      screen.getByTestId("contextual-capture-sentinel"),
    ).toBeInTheDocument();
  });

  it("shows email form when IntersectionObserver fires", () => {
    render(<ContextualCapture {...BASE_PROPS} />);

    // Trigger intersection
    act(() => {
      intersectionCallback?.([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    expect(
      screen.getByTestId("contextual-capture"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("contextual-capture-email-input"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("contextual-capture-submit"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Ver diagnostico gratuito"),
    ).toBeInTheDocument();
  });

  it("transitions to PartialReportPreview after successful email submit", async () => {
    render(<ContextualCapture {...BASE_PROPS} />);

    // Trigger intersection to show form
    act(() => {
      intersectionCallback?.([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    // Fill and submit email
    const input = screen.getByTestId("contextual-capture-email-input");
    fireEvent.change(input, { target: { value: "cliente@empresa.com" } });
    fireEvent.click(screen.getByTestId("contextual-capture-submit"));

    // Should show PartialReportPreview
    await waitFor(() => {
      expect(
        screen.getByTestId("partial-report-preview"),
      ).toBeInTheDocument();
    });

    // And free items should be present
    expect(screen.getAllByTestId("preview-item-free")).toHaveLength(3);
  });

  it("shows error message on failed email submission", async () => {
    // Override fetch: products succeed, lead-capture fails
    (global as unknown as { fetch: jest.Mock }).fetch = jest.fn(
      (url: string) => {
        if (url === "/api/products") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              products: [
                {
                  sku: "relatorio-setorial",
                  price_brl: 4700,
                  name: "Relatorio completo",
                  description: null,
                  delivery_config: {},
                  preview_config: {},
                },
              ],
            }),
          });
        }
        return Promise.resolve({
          ok: false,
          json: async () => ({ detail: "Erro ao registrar" }),
        });
      },
    );

    render(<ContextualCapture {...BASE_PROPS} />);

    // Trigger intersection
    act(() => {
      intersectionCallback?.([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    // Submit with email
    const input = screen.getByTestId("contextual-capture-email-input");
    fireEvent.change(input, { target: { value: "teste@test.com" } });
    fireEvent.click(screen.getByTestId("contextual-capture-submit"));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("has responsive layout with sm: breakpoint classes", () => {
    render(<ContextualCapture {...BASE_PROPS} />);

    // Trigger intersection
    act(() => {
      intersectionCallback?.([{ isIntersecting: true } as IntersectionObserverEntry]);
    });

    const capture = screen.getByTestId("contextual-capture");
    expect(capture.className).toMatch(/\bsm:|\bsm\b/);
  });
});
