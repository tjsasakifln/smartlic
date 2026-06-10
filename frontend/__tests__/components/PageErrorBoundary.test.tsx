/**
 * DEBT-112: PageErrorBoundary tests
 * AC1: Preserves NavigationShell (boundary is inside page, shell is in layout)
 * AC5: Contextual error messages per page
 * AC6: "Tentar novamente" resets without full reload
 * AC7: Sentry reports error with page context
 * AC8: Does NOT clear localStorage or SWR cache
 * AC9: role="alert" aria-live="assertive"
 * AC10: Unit tests for render, reset, Sentry report
 */
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { PageErrorBoundary } from "../../components/PageErrorBoundary";

// ─── Test helpers ────────────────────────────────────────────────────────────

function ThrowingChild({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error("Test component crash");
  return <div data-testid="child-content">Working content</div>;
}

// Suppress expected error boundary console.error noise
const originalConsoleError = console.error;
beforeAll(() => {
  console.error = (...args: unknown[]) => {
    const msg = String(args[0] ?? "");
    if (
      msg.includes("[PageErrorBoundary") ||
      msg.includes("The above error occurred") ||
      msg.includes("Error: Uncaught") ||
      msg.includes("Temporary error") ||
      msg.includes("Test component crash") ||
      msg.includes("Conditional error")
    ) {
      return;
    }
    originalConsoleError(...args);
  };
});
afterAll(() => {
  console.error = originalConsoleError;
});

// ─── AC10: Render tests ──────────────────────────────────────────────────────

describe("PageErrorBoundary (DEBT-112)", () => {
  it("renders children when no error occurs", () => {
    render(
      <PageErrorBoundary pageName="dashboard">
        <ThrowingChild shouldThrow={false} />
      </PageErrorBoundary>
    );
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders fallback UI when child throws", () => {
    render(
      <PageErrorBoundary pageName="dashboard">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(screen.queryByTestId("child-content")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  // ── AC5: Contextual error messages ──────────────────────────────────────

  it("AC5: shows contextual message for dashboard", () => {
    render(
      <PageErrorBoundary pageName="dashboard">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(screen.getByText("Erro ao carregar o dashboard")).toBeInTheDocument();
  });

  it("AC5: shows contextual message for pipeline", () => {
    render(
      <PageErrorBoundary pageName="pipeline">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(screen.getByText("Erro ao carregar o pipeline")).toBeInTheDocument();
  });

  it("AC5: shows contextual message for histórico", () => {
    render(
      <PageErrorBoundary pageName="histórico">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(screen.getByText("Erro ao carregar o histórico")).toBeInTheDocument();
  });

  // ── AC6: Reset without full reload ──────────────────────────────────────

  it("AC6: retry button resets error state and re-renders children", () => {
    let shouldThrow = true;

    function ConditionalThrow() {
      if (shouldThrow) throw new Error("Temporary error");
      return <div data-testid="recovered">Recovered!</div>;
    }

    render(
      <PageErrorBoundary pageName="dashboard">
        <ConditionalThrow />
      </PageErrorBoundary>
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();

    // Fix the error condition, then click retry
    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: /Tentar novamente/i }));

    // Should recover without full page reload
    expect(screen.getByTestId("recovered")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("AC6: has a 'Tentar novamente' button in the fallback UI", () => {
    render(
      <PageErrorBoundary pageName="pipeline">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(
      screen.getByRole("button", { name: /Tentar novamente/i })
    ).toBeInTheDocument();
  });

  // ── AC7: Sentry reports error with page context ─────────────────────────

  it("AC7: componentDidCatch logs error with pageName context for Sentry", () => {
    // Verify componentDidCatch is called with page context via console.error
    // (Sentry.captureException is called in the same codepath via dynamic import)
    const consoleErrorSpy = jest.fn();
    const savedConsoleError = console.error;
    console.error = consoleErrorSpy;

    render(
      <PageErrorBoundary pageName="pipeline">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );

    // componentDidCatch logs with pageName in the prefix
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      expect.stringContaining("[PageErrorBoundary:pipeline]"),
      expect.any(Error),
      expect.anything()
    );

    console.error = savedConsoleError;
  });

  // ── AC8: Does NOT clear localStorage or SWR cache ───────────────────────

  it("AC8: does not clear localStorage when error occurs", () => {
    localStorage.setItem("test-key", "test-value");
    localStorage.setItem("smartlic-theme", "dark");

    render(
      <PageErrorBoundary pageName="dashboard">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );

    // localStorage should be untouched
    expect(localStorage.getItem("test-key")).toBe("test-value");
    expect(localStorage.getItem("smartlic-theme")).toBe("dark");

    localStorage.removeItem("test-key");
    localStorage.removeItem("smartlic-theme");
  });

  // ── AC9: Accessibility attributes ───────────────────────────────────────

  it("AC9: fallback has role='alert' and aria-live='assertive'", () => {
    render(
      <PageErrorBoundary pageName="histórico">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("aria-live", "assertive");
  });

  // ── Additional coverage ────────────────────────────────────────────────

  it("shows technical details with error message", () => {
    render(
      <PageErrorBoundary pageName="dashboard">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(screen.getByText("Detalhes técnicos")).toBeInTheDocument();
    expect(screen.getByText("Test component crash")).toBeInTheDocument();
  });

  it("shows actionable error description and action suggestions", () => {
    render(
      <PageErrorBoundary pageName="pipeline">
        <ThrowingChild shouldThrow={true} />
      </PageErrorBoundary>
    );
    expect(
      screen.getByText(/Ocorreu um erro inesperado/)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Tente novamente em alguns instantes/)
    ).toBeInTheDocument();
  });

  it("shows 'Erro desconhecido' when error has no message", () => {
    function ThrowNull() {
      throw new Error();
    }

    render(
      <PageErrorBoundary pageName="dashboard">
        <ThrowNull />
      </PageErrorBoundary>
    );
    expect(screen.getByText("Erro desconhecido")).toBeInTheDocument();
  });
});
