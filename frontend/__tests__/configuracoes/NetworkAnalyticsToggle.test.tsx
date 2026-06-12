/**
 * @jest-environment jsdom
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NetworkAnalyticsToggle } from "../../app/configuracoes/components/NetworkAnalyticsToggle";

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock NEXT_PUBLIC_API_URL
const ORIGINAL_ENV = process.env;
beforeEach(() => {
  jest.resetAllMocks();
  process.env = { ...ORIGINAL_ENV, NEXT_PUBLIC_API_URL: "https://api.test.com" };
});

afterEach(() => {
  process.env = ORIGINAL_ENV;
});

function createFetchResponse(data: unknown, ok = true) {
  return Promise.resolve({
    ok,
    json: () => Promise.resolve(data),
  } as Response);
}

describe("NetworkAnalyticsToggle", () => {
  const accessToken = "test-token-123";

  it("renders loading state initially", () => {
    // Keep fetch pending
    mockFetch.mockReturnValue(new Promise(() => {}));

    render(<NetworkAnalyticsToggle accessToken={accessToken} />);

    // Should show skeleton while loading
    const toggleContainer = screen.getByTestId("network-analytics-toggle");
    expect(toggleContainer).toBeInTheDocument();
    // Loading state has animate-pulse elements
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("shows toggle as off when allow_network_analytics is null", async () => {
    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ allow_network_analytics: null, email: "test@test.com" })
    );

    render(<NetworkAnalyticsToggle accessToken={accessToken} />);

    await waitFor(() => {
      expect(screen.getByTestId("toggle-switch")).toBeInTheDocument();
    });

    const toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("aria-checked", "false");
  });

  it("shows toggle as on when allow_network_analytics is true", async () => {
    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ allow_network_analytics: true, email: "test@test.com" })
    );

    render(<NetworkAnalyticsToggle accessToken={accessToken} />);

    await waitFor(() => {
      expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
    });
  });

  it("shows toggle as off when allow_network_analytics is false", async () => {
    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ allow_network_analytics: false, email: "test@test.com" })
    );

    render(<NetworkAnalyticsToggle accessToken={accessToken} />);

    await waitFor(() => {
      expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
    });
  });

  it("toggles optimistically and saves on click (false -> true)", async () => {
    // First call: GET /me returns allow_network_analytics = false
    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ allow_network_analytics: false, email: "test@test.com" })
    );

    render(<NetworkAnalyticsToggle accessToken={accessToken} />);

    await waitFor(() => {
      expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
    });

    // Second call: PUT /profile/network-analytics succeeds
    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ allow_network_analytics: true, success: true })
    );

    // Click the toggle
    fireEvent.click(screen.getByRole("switch"));

    // Should be optimistically true
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");

    // Wait for the async PATCH to resolve
    await waitFor(() => {
      // Should have called PUT with the right body
      expect(mockFetch).toHaveBeenCalledWith(
        "https://api.test.com/v1/profile/network-analytics",
        expect.objectContaining({
          method: "PUT",
          headers: expect.objectContaining({
            "Content-Type": "application/json",
            Authorization: `Bearer ${accessToken}`,
          }),
          body: JSON.stringify({ allow_network_analytics: true }),
        })
      );
    });
  });

  it("toggles optimistically and saves on click (true -> false)", async () => {
    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ allow_network_analytics: true, email: "test@test.com" })
    );

    render(<NetworkAnalyticsToggle accessToken={accessToken} />);

    await waitFor(() => {
      expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
    });

    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ allow_network_analytics: false, success: true })
    );

    fireEvent.click(screen.getByRole("switch"));

    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "https://api.test.com/v1/profile/network-analytics",
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({ allow_network_analytics: false }),
        })
      );
    });
  });

  it("rolls back visual state on PATCH error", async () => {
    // Initial state: true (opted in)
    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ allow_network_analytics: true, email: "test@test.com" })
    );

    render(<NetworkAnalyticsToggle accessToken={accessToken} />);

    await waitFor(() => {
      expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
    });

    // PATCH fails
    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ detail: "Erro ao salvar" }, false)
    );

    // Click to toggle off
    fireEvent.click(screen.getByRole("switch"));

    // Should revert to true after the failed call
    await waitFor(() => {
      expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
    });
  });

  it("shows tooltip on hover", async () => {
    mockFetch.mockResolvedValueOnce(
      createFetchResponse({ allow_network_analytics: true, email: "test@test.com" })
    );

    render(<NetworkAnalyticsToggle accessToken={accessToken} />);

    await waitFor(() => {
      expect(screen.getByTestId("toggle-tooltip")).toBeInTheDocument();
    });

    const tooltipTrigger = screen.getByTestId("toggle-tooltip");
    expect(tooltipTrigger).toHaveAttribute("aria-label");
    expect(tooltipTrigger.getAttribute("aria-label")).toContain("anonimos");
  });

  it("handles null API response gracefully", async () => {
    mockFetch.mockResolvedValueOnce(
      createFetchResponse(null)
    );

    render(<NetworkAnalyticsToggle accessToken={accessToken} />);

    await waitFor(() => {
      const toggle = screen.getByRole("switch");
      expect(toggle).toHaveAttribute("aria-checked", "false");
    });
  });
});
