/**
 * FEEDBACK-005: SectorAffinitySettings component tests.
 *
 * AC1: Shows loading state while fetching
 * AC2: Renders sector list with muted and active sectors
 * AC3: Mute toggle calls PATCH endpoint and fires Mixpanel
 * AC4: Unmute toggle calls PATCH endpoint and fires Mixpanel
 * AC5: Shows error state on API failure
 * AC6: Shows empty state when no sectors returned
 * AC7: Error state has retry button that re-fetches
 * AC8: Toggle reverts on API failure
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { SectorAffinitySettings } from "../app/components/SectorAffinitySettings";

// ─── Types ───────────────────────────────────────────────────────────────

/** Matches the backend SectorAffinityResponse shape. */
interface SectorAffinity {
  sector_id: string;
  sector_name: string;
  affinity_score: number;
  muted: boolean;
}

// ─── Constants ───────────────────────────────────────────────────────────

const ACCESS_TOKEN = "mock-access-token";

const MOCK_SECTORS: SectorAffinity[] = [
  { sector_id: "ti_software", sector_name: "TI e Software", affinity_score: 0.85, muted: false },
  { sector_id: "engenharia_obras", sector_name: "Engenharia e Obras", affinity_score: 0.42, muted: true },
  { sector_id: "saude", sector_name: "Saúde", affinity_score: 0.0, muted: true },
  { sector_id: "educacao", sector_name: "Educação", affinity_score: 0.63, muted: false },
];

// ─── Mocks ───────────────────────────────────────────────────────────────

const mockMixpanelTrack = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();

  // Mock window.mixpanel
  Object.defineProperty(window, "mixpanel", {
    value: { track: mockMixpanelTrack },
    writable: true,
    configurable: true,
  });

  // Set env var
  process.env.NEXT_PUBLIC_API_URL = "https://api.smartlic.tech";
});

afterEach(() => {
  jest.restoreAllMocks();
  delete (window as Record<string, unknown>).mixpanel;
});

// ─── Helpers ─────────────────────────────────────────────────────────────

function mockFetchSuccess(data: SectorAffinity[]) {
  (global.fetch as jest.Mock) = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => data,
  });
}

function mockFetchPatchSuccess(updated: SectorAffinity) {
  (global.fetch as jest.Mock) = jest.fn().mockImplementation((url: string, options?: RequestInit) => {
    // GET returns the initial list
    if (!options || options.method === "GET" || !options.method) {
      return Promise.resolve({
        ok: true,
        json: async () => MOCK_SECTORS,
      });
    }
    // PATCH returns the updated item
    return Promise.resolve({
      ok: true,
      json: async () => updated,
    });
  });
}

function mockFetchFailure() {
  (global.fetch as jest.Mock) = jest.fn().mockResolvedValue({
    ok: false,
    status: 500,
  });
}

function mockFetchPatchFailure() {
  let callCount = 0;
  (global.fetch as jest.Mock) = jest.fn().mockImplementation(() => {
    callCount++;
    // First call (GET) succeeds
    if (callCount === 1) {
      return Promise.resolve({
        ok: true,
        json: async () => MOCK_SECTORS,
      });
    }
    // PATCH fails
    return Promise.resolve({
      ok: false,
      status: 500,
    });
  });
}

// ─── Tests ───────────────────────────────────────────────────────────────

describe("SectorAffinitySettings", () => {
  test("AC1: shows loading state while fetching", () => {
    // Don't resolve the fetch to keep loading
    (global.fetch as jest.Mock) = jest.fn().mockImplementation(() => new Promise(() => {}));

    render(<SectorAffinitySettings accessToken={ACCESS_TOKEN} />);

    expect(screen.getByText("Carregando preferências...")).toBeInTheDocument();
  });

  test("AC2: renders sector list with muted and active sectors", async () => {
    mockFetchSuccess(MOCK_SECTORS);

    render(<SectorAffinitySettings accessToken={ACCESS_TOKEN} />);

    // Wait for loading to finish
    await waitFor(() => {
      expect(screen.getByTestId("sector-affinity-settings")).toBeInTheDocument();
    });

    // Header
    expect(screen.getByText("Preferências de Setores")).toBeInTheDocument();

    // Muted sections heading
    expect(screen.getByText("Setores que não me interessam")).toBeInTheDocument();

    // Muted sectors (with strikethrough)
    const engenhariaRow = screen.getByTestId("sector-row-engenharia_obras");
    expect(engenhariaRow).toBeInTheDocument();
    expect(engenhariaRow).toHaveTextContent("Engenharia e Obras");

    const saudeRow = screen.getByTestId("sector-row-saude");
    expect(saudeRow).toBeInTheDocument();

    // Active sectors
    expect(screen.getByText("Setores ativos")).toBeInTheDocument();

    const tiRow = screen.getByTestId("sector-row-ti_software");
    expect(tiRow).toBeInTheDocument();
    expect(tiRow).toHaveTextContent("TI e Software");
    expect(tiRow).toHaveTextContent("Afinidade: 85%");

    const educacaoRow = screen.getByTestId("sector-row-educacao");
    expect(educacaoRow).toBeInTheDocument();
    expect(educacaoRow).toHaveTextContent("Afinidade: 63%");
  });

  test("AC3: mute toggle calls PATCH endpoint and fires Mixpanel", async () => {
    const updatedEducacao: SectorAffinity = {
      sector_id: "educacao",
      sector_name: "Educação",
      affinity_score: 0.0,
      muted: true,
    };

    mockFetchPatchSuccess(updatedEducacao);

    render(<SectorAffinitySettings accessToken={ACCESS_TOKEN} />);

    await waitFor(() => {
      expect(screen.getByTestId("sector-affinity-settings")).toBeInTheDocument();
    });

    // Click mute on "Educação"
    const muteButton = screen.getByTestId("mute-educacao");
    await userEvent.click(muteButton);

    // Should call PATCH with muted: true
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "https://api.smartlic.tech/v1/profile/sector-affinity/educacao",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ muted: true }),
        }),
      );
    });

    // Should fire Mixpanel event
    expect(mockMixpanelTrack).toHaveBeenCalledWith("sector_muted", {
      sector_id: "educacao",
      sector_name: "Educação",
    });
  });

  test("AC4: unmute toggle calls PATCH endpoint and fires Mixpanel", async () => {
    const updatedEngenharia: SectorAffinity = {
      sector_id: "engenharia_obras",
      sector_name: "Engenharia e Obras",
      affinity_score: 0.42,
      muted: false,
    };

    mockFetchPatchSuccess(updatedEngenharia);

    render(<SectorAffinitySettings accessToken={ACCESS_TOKEN} />);

    await waitFor(() => {
      expect(screen.getByTestId("sector-affinity-settings")).toBeInTheDocument();
    });

    // Click unmute on "Engenharia e Obras"
    const unmuteButton = screen.getByTestId("unmute-engenharia_obras");
    await userEvent.click(unmuteButton);

    // Should call PATCH with muted: false
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "https://api.smartlic.tech/v1/profile/sector-affinity/engenharia_obras",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ muted: false }),
        }),
      );
    });

    // Should fire Mixpanel event
    expect(mockMixpanelTrack).toHaveBeenCalledWith("sector_unmuted", {
      sector_id: "engenharia_obras",
      sector_name: "Engenharia e Obras",
    });
  });

  test("AC5: shows error state on API failure", async () => {
    mockFetchFailure();

    render(<SectorAffinitySettings accessToken={ACCESS_TOKEN} />);

    await waitFor(() => {
      expect(screen.getByTestId("sector-affinity-error")).toBeInTheDocument();
    });

    expect(
      screen.getByText("Não foi possível carregar suas preferências. Tente novamente."),
    ).toBeInTheDocument();
  });

  test("AC6: shows empty state when no sectors returned", async () => {
    mockFetchSuccess([]);

    render(<SectorAffinitySettings accessToken={ACCESS_TOKEN} />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Nenhuma preferência de setor encontrada. Comece a buscar para que suas preferências sejam detectadas automaticamente.",
        ),
      ).toBeInTheDocument();
    });
  });

  test("AC7: error state has retry button that re-fetches", async () => {
    // First call fails, second call succeeds
    let callCount = 0;
    (global.fetch as jest.Mock) = jest.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({ ok: false, status: 500 });
      }
      return Promise.resolve({ ok: true, json: async () => MOCK_SECTORS });
    });

    render(<SectorAffinitySettings accessToken={ACCESS_TOKEN} />);

    // Wait for error state
    await waitFor(() => {
      expect(screen.getByTestId("sector-affinity-error")).toBeInTheDocument();
    });

    // Click retry
    const retryButton = screen.getByText("Tentar novamente");
    await userEvent.click(retryButton);

    // Should re-fetch and show sectors
    await waitFor(() => {
      expect(screen.getByTestId("sector-affinity-settings")).toBeInTheDocument();
    });
    expect(screen.getByText("TI e Software")).toBeInTheDocument();
  });

  test("AC8: toggle reverts on API failure", async () => {
    mockFetchPatchFailure();

    render(<SectorAffinitySettings accessToken={ACCESS_TOKEN} />);

    await waitFor(() => {
      expect(screen.getByTestId("sector-affinity-settings")).toBeInTheDocument();
    });

    // TI e Software is active — click mute
    const muteButton = screen.getByTestId("mute-ti_software");
    await userEvent.click(muteButton);

    // Wait for PATCH to fail
    await waitFor(() => {
      // The "tiemos de Reativar" is the active button — TI should revert back to active
      // We check that it was restored: mute button reappears
      expect(screen.getByTestId("mute-ti_software")).toBeInTheDocument();
    });

    // Should still fire the Mixpanel event even though API failed
    expect(mockMixpanelTrack).toHaveBeenCalledWith("sector_muted", {
      sector_id: "ti_software",
      sector_name: "TI e Software",
    });
  });

  test("footer note is always visible", async () => {
    mockFetchSuccess(MOCK_SECTORS);

    render(<SectorAffinitySettings accessToken={ACCESS_TOKEN} />);

    await waitFor(() => {
      expect(screen.getByTestId("sector-affinity-settings")).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        "Setores silenciados nunca são removidos — apenas têm influência reduzida nos resultados. Você pode reativá-los a qualquer momento.",
      ),
    ).toBeInTheDocument();
  });
});
