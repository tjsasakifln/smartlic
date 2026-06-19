/**
 * P0-4: Tests for fetchSectorStats throwOn5xx pattern.
 *
 * AC5: backend 500 → throw during ISR runtime
 * AC6: backend 500 → null during build phase
 * AC3: backend 4xx → null
 * AC4: Sentry breadcrumb in all outcomes
 */

import { fetchSectorStats, type SectorStats } from '@/lib/sectors';
import * as Sentry from '@sentry/nextjs';

// Mutable sentry mock
jest.mock('@sentry/nextjs', () => ({
  addBreadcrumb: jest.fn(),
}));

const SentryMock = Sentry as unknown as {
  addBreadcrumb: jest.Mock;
};

// Mutable programmatic mock — getter ensures IS_BUILD_PHASE is read fresh
// on each call instead of being frozen at module-import time.
const mockProgrammaticModule: { IS_BUILD_PHASE: boolean } = {
  IS_BUILD_PHASE: false,
};

jest.mock('@/lib/programmatic', () => ({
  __esModule: true,
  get IS_BUILD_PHASE() {
    return mockProgrammaticModule.IS_BUILD_PHASE;
  },
}));

// Minimal Response-compatible object matching the shape fetchSectorStats uses
function mockResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

const MOCK_STATS: SectorStats = {
  sector_id: 'informatica',
  sector_name: 'Hardware e Equipamentos de TI',
  sector_description: 'Computadores, servidores, periféricos',
  slug: 'informatica',
  total_open: 150,
  total_value: 50_000_000,
  avg_value: 333_333,
  top_ufs: [{ name: 'SP', count: 40 }],
  top_modalidades: [{ name: 'Pregão Eletrônico', count: 100 }],
  sample_items: [
    {
      titulo: 'Aquisição de computadores',
      orgao: 'MEC',
      valor: 500_000,
      uf: 'DF',
      data: '2026-06-01',
    },
  ],
  last_updated: '2026-06-18',
};

describe('fetchSectorStats (P0-4 throwOn5xx)', () => {
  const ORIGINAL_FETCH = global.fetch;
  const ORIGINAL_BACKEND_URL = process.env.BACKEND_URL;

  beforeAll(() => {
    process.env.BACKEND_URL = 'https://api.smartlic.tech';
  });

  afterAll(() => {
    process.env.BACKEND_URL = ORIGINAL_BACKEND_URL;
  });

  beforeEach(() => {
    SentryMock.addBreadcrumb.mockReset();
  });

  afterEach(() => {
    global.fetch = ORIGINAL_FETCH;
  });

  // --- ISR runtime (IS_BUILD_PHASE = false) ---

  it('AC5: backend 500 throws Error durante ISR runtime', async () => {
    mockProgrammaticModule.IS_BUILD_PHASE = false;
    global.fetch = jest.fn().mockResolvedValue(mockResponse(null, 500)) as jest.Mock;

    await expect(fetchSectorStats('informatica')).rejects.toThrow(
      'sector_stats_backend_5xx:500',
    );

    // AC4: Sentry breadcrumb emitted
    expect(SentryMock.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'fetch',
        message: expect.stringContaining('5xx (500) ISR throw'),
        level: 'error',
      }),
    );
  });

  it('AC6: backend 500 retorna null durante build phase', async () => {
    mockProgrammaticModule.IS_BUILD_PHASE = true;
    global.fetch = jest.fn().mockResolvedValue(mockResponse(null, 500)) as jest.Mock;

    const result = await fetchSectorStats('informatica');
    expect(result).toBeNull();

    // AC4: Sentry breadcrumb para build phase
    expect(SentryMock.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'fetch',
        message: expect.stringContaining('5xx (500) during build'),
        level: 'warning',
      }),
    );
  });

  // --- 4xx ---

  it('AC3: backend 404 retorna null (no data)', async () => {
    global.fetch = jest.fn().mockResolvedValue(mockResponse(null, 404)) as jest.Mock;

    const result = await fetchSectorStats('inexistente');
    expect(result).toBeNull();

    expect(SentryMock.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'fetch',
        message: expect.stringContaining('404 no data'),
        level: 'warning',
      }),
    );
  });

  it('backend 403 retorna null (acesso negado)', async () => {
    global.fetch = jest.fn().mockResolvedValue(mockResponse(null, 403)) as jest.Mock;

    const result = await fetchSectorStats('informatica');
    expect(result).toBeNull();

    expect(SentryMock.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'fetch',
        message: expect.stringContaining('403 no data'),
        level: 'warning',
      }),
    );
  });

  // --- Success ---

  it('backend 200 retorna SectorStats', async () => {
    global.fetch = jest.fn().mockResolvedValue(mockResponse(MOCK_STATS, 200)) as jest.Mock;

    const result = await fetchSectorStats('informatica');
    expect(result).toEqual(MOCK_STATS);
    expect(result?.sector_id).toBe('informatica');
    expect(result?.total_open).toBe(150);

    expect(SentryMock.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'fetch',
        message: 'fetchSectorStats: success',
        level: 'info',
      }),
    );
  });

  // --- Edge cases ---

  it('retorna null quando BACKEND_URL nao configurado', async () => {
    delete process.env.BACKEND_URL;

    const result = await fetchSectorStats('informatica');
    expect(result).toBeNull();

    expect(SentryMock.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'fetch',
        message: 'fetchSectorStats: no BACKEND_URL',
        level: 'info',
      }),
    );

    process.env.BACKEND_URL = 'https://api.smartlic.tech';
  });

  it('retorna null em network error (nao-5xx)', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('ECONNREFUSED')) as jest.Mock;

    const result = await fetchSectorStats('informatica');
    expect(result).toBeNull();

    expect(SentryMock.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'fetch',
        message: 'fetchSectorStats: network error',
        level: 'error',
      }),
    );
  });

  it('relança 5xx Error com prefixo sector_stats_backend_5xx mesmo em catch inesperado', async () => {
    // Simula cenário onde throw acontece fora do branch 5xx
    mockProgrammaticModule.IS_BUILD_PHASE = false;
    const fetchMock = jest.fn().mockImplementation(async () => {
      throw new Error('sector_stats_backend_5xx:503');
    });
    global.fetch = fetchMock as jest.Mock;

    await expect(fetchSectorStats('informatica')).rejects.toThrow(
      'sector_stats_backend_5xx:503',
    );
  });
});
