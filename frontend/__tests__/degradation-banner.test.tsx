/**
 * ISSUE-1791: Tests for graceful degradation components.
 *
 * Tests:
 * 1. DegradationBanner renders when backend offline
 * 2. DegradationBanner hides when backend online
 * 3. DegradationBanner is dismissible
 * 4. DegradationBanner shows "recuperando" state
 * 5. DegradationBanner has Recarregar button when offline
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { DegradationBanner } from "../app/components/DegradationBanner";

// ============================================================================
// Mock BackendStatusIndicator
// ============================================================================

const mockStatus: { status: "online" | "offline" | "recovering"; isPolling: boolean; checkHealth: jest.Mock } = {
  status: "online",
  isPolling: false,
  checkHealth: jest.fn(),
};

jest.mock("../app/components/BackendStatusIndicator", () => {
  function MockProvider({ children }: { children: React.ReactNode }) {
    return <>{children}</>;
  }
  function MockIndicator() {
    return null;
  }
  return {
    useBackendStatusContext: () => ({
      status: mockStatus.status,
      isPolling: mockStatus.isPolling,
      checkHealth: mockStatus.checkHealth,
    }),
    useBackendStatus: () => ({
      status: mockStatus.status,
      isPolling: mockStatus.isPolling,
      checkHealth: mockStatus.checkHealth,
    }),
    BackendStatusProvider: MockProvider,
    BackendStatusIndicator: MockIndicator,
  };
});

// ============================================================================
// Tests
// ============================================================================

describe("DegradationBanner", () => {
  beforeEach(() => {
    mockStatus.status = "online";
    mockStatus.isPolling = false;
    try {
      sessionStorage.clear();
    } catch { /* noop */ }
  });

  it("renders nothing when backend is online", () => {
    const { container } = render(<DegradationBanner />);
    expect(container.firstChild).toBeNull();
  });

  it("renders offline banner when backend is offline", () => {
    mockStatus.status = "offline";
    render(<DegradationBanner />);

    expect(screen.getByTestId("degradation-banner")).toBeInTheDocument();
    expect(screen.getByText(/Backend temporariamente indisponivel/i)).toBeInTheDocument();
    expect(screen.getByText(/Algumas funcionalidades podem estar limitadas/i)).toBeInTheDocument();
  });

  it("renders recovering banner when backend is recovering", () => {
    mockStatus.status = "recovering";
    render(<DegradationBanner />);

    expect(screen.getByTestId("degradation-banner")).toBeInTheDocument();
    expect(screen.getByText(/Backend recuperado/i)).toBeInTheDocument();
  });

  it("is dismissible via Dispensar button", () => {
    mockStatus.status = "offline";
    render(<DegradationBanner />);
    expect(screen.getByTestId("degradation-banner")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Dispensar"));

    expect(screen.queryByTestId("degradation-banner")).not.toBeInTheDocument();
  });

  it("persists dismissal across re-renders via sessionStorage", () => {
    mockStatus.status = "offline";
    const { unmount } = render(<DegradationBanner />);
    expect(screen.getByTestId("degradation-banner")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Dispensar"));
    expect(screen.queryByTestId("degradation-banner")).not.toBeInTheDocument();

    unmount();
    render(<DegradationBanner />);
    expect(screen.queryByTestId("degradation-banner")).not.toBeInTheDocument();
  });

  it("shows Recarregar button when offline", () => {
    mockStatus.status = "offline";
    render(<DegradationBanner />);
    expect(screen.getByText("Recarregar")).toBeInTheDocument();
  });

  it("does not show Recarregar button when recovering", () => {
    mockStatus.status = "recovering";
    render(<DegradationBanner />);
    expect(screen.queryByText("Recarregar")).not.toBeInTheDocument();
  });
});
