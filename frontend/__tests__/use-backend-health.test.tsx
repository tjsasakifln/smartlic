/**
 * ISSUE-1791: Tests for useBackendHealth hook.
 *
 * Tests:
 * 1. Exposes isOnline=true when status is "online"
 * 2. Exposes isDegraded=true when status is "offline"
 * 3. Exposes isRecovering=true when status is "recovering"
 * 4. Allows triggering checkHealth
 */

import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import "@testing-library/jest-dom";

// ============================================================================
// Mock BackendStatusIndicator
// ============================================================================

const mockCheckHealth = jest.fn(() => Promise.resolve(true));
const mockStatus = { status: "online" as const, isPolling: false, checkHealth: mockCheckHealth };

jest.mock("../app/components/BackendStatusIndicator", () => {
  const actual = jest.requireActual("../app/components/BackendStatusIndicator");
  return {
    ...actual,
    useBackendStatusContext: () => mockStatus,
    useBackendStatus: () => mockStatus,
    BackendStatusProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

// ============================================================================
// Test helper component
// ============================================================================

function TestHealthConsumer({
  children,
}: {
  children: (state: import("../app/hooks/useBackendHealth").BackendHealthState) => React.ReactNode;
}) {
  const { useBackendHealth } = require("../app/hooks/useBackendHealth");
  const health = useBackendHealth();
  return <div data-testid="health-result">{children(health)}</div>;
}

// ============================================================================
// Tests
// ============================================================================

describe("useBackendHealth", () => {
  beforeEach(() => {
    mockStatus.status = "online";
    mockCheckHealth.mockResolvedValue(true);
  });

  it("exposes isOnline=true when backend is online", () => {
    render(
      <TestHealthConsumer>
        {(h) => (h.isOnline ? "online" : "offline")}
      </TestHealthConsumer>
    );
    expect(screen.getByTestId("health-result")).toHaveTextContent("online");
  });

  it("exposes isDegraded=true when backend is offline", () => {
    mockStatus.status = "offline";
    render(
      <TestHealthConsumer>
        {(h) => (h.isDegraded ? "degradado" : "ok")}
      </TestHealthConsumer>
    );
    expect(screen.getByTestId("health-result")).toHaveTextContent("degradado");
  });

  it("exposes isRecovering=true when backend is recovering", () => {
    mockStatus.status = "recovering";
    render(
      <TestHealthConsumer>
        {(h) => (h.isRecovering ? "recuperando" : "normal")}
      </TestHealthConsumer>
    );
    expect(screen.getByTestId("health-result")).toHaveTextContent("recuperando");
  });

  it("returns correct status string", () => {
    mockStatus.status = "offline";
    render(
      <TestHealthConsumer>
        {(h) => h.status}
      </TestHealthConsumer>
    );
    expect(screen.getByTestId("health-result")).toHaveTextContent("offline");
  });

  it("calls checkHealth from backend context", async () => {
    mockCheckHealth.mockResolvedValueOnce(true);

    function TestComponent() {
      const { useBackendHealth } = require("../app/hooks/useBackendHealth");
      const health = useBackendHealth();
      return <button onClick={() => health.checkHealth()}>check</button>;
    }
    render(<TestComponent />);

    await act(async () => {
      fireEvent.click(screen.getByText("check"));
    });

    expect(mockCheckHealth).toHaveBeenCalled();
  });
});
