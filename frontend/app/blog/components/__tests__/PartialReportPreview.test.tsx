/**
 * Tests for PartialReportPreview (#1312 REV-004).
 *
 * Covers:
 *  - Email capture form renders initially
 *  - Preview renders after email submission
 *  - 3 free items shown
 *  - 5 blurred items shown with blur class
 *  - CTA button renders in preview mode
 *  - Mobile responsive (sm: classes present)
 *  - preCapturedEmail prop skips email gate
 */

import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom";
import { PartialReportPreview } from "../PartialReportPreview";

// ---------------------------------------------------------------------------
// Mock fetch — URL-aware: returns different responses per endpoint
// ---------------------------------------------------------------------------

function mockResponseFor(url: string, init?: RequestInit) {
  // Product lookup
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

  // Lead-capture (default: success)
  const body = init?.body ? JSON.parse(init.body as string) : {};
  const isError = (body as { _test_error?: string })._test_error;
  if (isError) {
    return Promise.resolve({
      ok: false,
      json: async () => ({ detail: isError }),
    });
  }

  return Promise.resolve({
    ok: true,
    json: async () => ({}),
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  (global as unknown as { fetch: jest.Mock }).fetch = jest.fn(mockResponseFor);
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
// Helper: render component, submit email, wait for preview
// ---------------------------------------------------------------------------

async function renderAndSubmitEmail(props = BASE_PROPS) {
  render(<PartialReportPreview {...props} />);

  const input = screen.getByTestId("partial-report-email-input");
  fireEvent.change(input, { target: { value: "teste@email.com" } });
  fireEvent.click(screen.getByTestId("partial-report-email-submit"));

  await waitFor(() => {
    expect(
      screen.getByTestId("partial-report-preview"),
    ).toBeInTheDocument();
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("PartialReportPreview", () => {
  it("renders email capture form by default", () => {
    render(<PartialReportPreview {...BASE_PROPS} />);

    expect(
      screen.getByTestId("partial-report-email-gate"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("partial-report-email-input"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("partial-report-email-submit"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Ver diagnostico gratuito"),
    ).toBeInTheDocument();
  });

  it("shows preview after successful email submission", async () => {
    await renderAndSubmitEmail();

    expect(
      screen.getByTestId("partial-report-preview"),
    ).toBeInTheDocument();
  });

  it("shows 3 free preview items", async () => {
    await renderAndSubmitEmail();
    const freeItems = screen.getAllByTestId("preview-item-free");
    expect(freeItems).toHaveLength(3);
  });

  it("shows 5 blurred items", async () => {
    await renderAndSubmitEmail();
    const blurredItems = screen.getAllByTestId("preview-item-blurred");
    expect(blurredItems).toHaveLength(5);
  });

  it("blurred items have blur-sm class", async () => {
    await renderAndSubmitEmail();
    const blurredItems = screen.getAllByTestId("preview-item-blurred");
    expect(blurredItems[0]).toHaveClass("blur-sm");
  });

  it("shows price of R$ 47 in preview", async () => {
    await renderAndSubmitEmail();
    expect(screen.getByText("R$ 47")).toBeInTheDocument();
  });

  it("skips email gate when preCapturedEmail is provided", () => {    render(
      <PartialReportPreview
        {...BASE_PROPS}
        preCapturedEmail="pre@captured.com"
      />,
    );

    expect(
      screen.queryByTestId("partial-report-email-gate"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("partial-report-preview"),
    ).toBeInTheDocument();
  });

  it("has responsive classes (sm: prefix)", async () => {
    render(<PartialReportPreview {...BASE_PROPS} />);

    const gate = screen.getByTestId("partial-report-email-gate");
    expect(gate.className).toMatch(/\bsm:|\bsm\b/);
  });

  it("shows error message on failed email submission", async () => {
    // Override the lead-capture mock to return an error
    const errorMock = jest.fn(
      (url: string, _init?: RequestInit) => {
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
        // Lead-capture fails
        return Promise.resolve({
          ok: false,
          json: async () => ({ detail: "Email invalido" }),
        });
      },
    );
    (global as unknown as { fetch: jest.Mock }).fetch = errorMock;

    render(<PartialReportPreview {...BASE_PROPS} />);

    const input = screen.getByTestId("partial-report-email-input");

    await act(async () => {
      fireEvent.change(input, { target: { value: "invalido" } });
    });

    // Submit the form directly instead of clicking the button
    const form = input.closest("form")!;
    await act(async () => {
      fireEvent.submit(form);
    });

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
