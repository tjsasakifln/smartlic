/**
 * Tests for fetchContratosSetorStats — P0-3: throwOn5xx pattern.
 *
 * Estrategia A: throw on 5xx durante ISR runtime para preservar stale cache.
 * Build phase: retorna null (sem cache ISR para preservar).
 * 4xx: retorna null (dados ausentes legítimos = EmptyStateSEO com noindex).
 */

jest.mock('@/lib/concurrency', () => ({
  ssgLimitedFetch: jest.fn(),
}));

jest.mock('@sentry/nextjs', () => ({
  addBreadcrumb: jest.fn(),
  captureException: jest.fn(),
  captureMessage: jest.fn(),
}));

/**
 * Getter que sempre retorna a mock function atual do ssgLimitedFetch.
 * Necessario porque jest.resetModules() recria as funcoes mock nos
 * modulos mockados, invalidando referencias previamente capturadas.
 */
function mockFetch(): jest.Mock {
  return jest.requireMock('@/lib/concurrency').ssgLimitedFetch as jest.Mock;
}

const mockResponse = (overrides: Partial<Response> = {}): Response =>
  ({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
    ...overrides,
  }) as Response;

beforeEach(() => {
  jest.clearAllMocks();
  process.env.BACKEND_URL = 'https://api.smartlic.tech';
  // Garante IS_BUILD_PHASE = false para testes ISR runtime
  delete process.env.NEXT_PHASE;
  delete process.env.__NEXT_PHASE;
});

// ---------------------------------------------------------------------------
// AC5: backend 500 during ISR runtime → function throws
// ---------------------------------------------------------------------------
describe('ISR runtime — backend 5xx', () => {
  it('throws Error on 500 to preserve ISR stale cache (AC5)', async () => {
    mockFetch().mockResolvedValue(mockResponse({ ok: false, status: 500 }));

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');

    await expect(fetchContratosSetorStats('informatica')).rejects.toThrow(
      /contratos_setor_stats_backend_5xx:500/,
    );
  });

  it('throws Error on 503 to preserve ISR stale cache', async () => {
    mockFetch().mockResolvedValue(mockResponse({ ok: false, status: 503 }));

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');

    await expect(fetchContratosSetorStats('saude')).rejects.toThrow(
      /contratos_setor_stats_backend_5xx:503/,
    );
  });
});

// ---------------------------------------------------------------------------
// AC6: backend 500 during build phase → returns null
// ---------------------------------------------------------------------------
describe('build phase — backend 5xx', () => {
  it('returns null on 500 during build phase (AC6)', async () => {
    process.env.NEXT_PHASE = 'phase-production-build';
    jest.resetModules();

    mockFetch().mockResolvedValue(mockResponse({ ok: false, status: 500 }));

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');
    const result = await fetchContratosSetorStats('software');
    expect(result).toBeNull();
  });

  it('returns null on 502 during build phase', async () => {
    process.env.NEXT_PHASE = 'phase-production-build';
    jest.resetModules();

    mockFetch().mockResolvedValue(mockResponse({ ok: false, status: 502 }));

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');
    const result = await fetchContratosSetorStats('facilities');
    expect(result).toBeNull();
  });

  it('still works on 200 during build phase', async () => {
    process.env.NEXT_PHASE = 'phase-production-build';
    jest.resetModules();

    const mockStats = {
      sector_id: 'software_desenvolvimento',
      sector_name: 'Software e Desenvolvimento',
      total_contracts: 500,
      total_value: 50000000,
      avg_value: 100000,
      top_orgaos: [],
      top_fornecedores: [],
      monthly_trend: [],
      by_uf: [],
      last_updated: '2026-04-08T12:00:00Z',
    };
    mockFetch().mockResolvedValue(
      mockResponse({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockStats),
      }),
    );

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');
    const result = await fetchContratosSetorStats('software');
    expect(result).toEqual(mockStats);
  });
});

// ---------------------------------------------------------------------------
// AC7: backend 404 → returns null (dados ausentes legítimos)
// ---------------------------------------------------------------------------
describe('backend 4xx — no data', () => {
  it('returns null on 404 (AC7)', async () => {
    mockFetch().mockResolvedValue(mockResponse({ ok: false, status: 404 }));

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');
    const result = await fetchContratosSetorStats('informatica');
    expect(result).toBeNull();
  });

  it('returns null on 403', async () => {
    mockFetch().mockResolvedValue(mockResponse({ ok: false, status: 403 }));

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');
    const result = await fetchContratosSetorStats('saude');
    expect(result).toBeNull();
  });

  it('returns null on 429 (rate limit)', async () => {
    mockFetch().mockResolvedValue(mockResponse({ ok: false, status: 429 }));

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');
    const result = await fetchContratosSetorStats('transporte');
    expect(result).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------
describe('edge cases', () => {
  it('returns null when BACKEND_URL is not set', async () => {
    delete process.env.BACKEND_URL;

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');
    const result = await fetchContratosSetorStats('informatica');
    expect(result).toBeNull();
    expect(mockFetch()).not.toHaveBeenCalled();
  });

  it('uses SECTOR_SLUG_TO_BACKEND_ID mapping when available', async () => {
    mockFetch().mockResolvedValue(
      mockResponse({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ sector_id: 'software_desenvolvimento' }),
      }),
    );

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');

    await fetchContratosSetorStats('software');
    expect(mockFetch()).toHaveBeenCalledWith(
      expect.stringContaining('software_desenvolvimento'),
      expect.anything(),
    );
  });

  it('returns data on successful response', async () => {
    const mockStats = {
      sector_id: 'informatica',
      sector_name: 'Informatica',
      total_contracts: 1000,
      total_value: 100000000,
      avg_value: 100000,
      top_orgaos: [{ nome: 'Min Educacao', total: 100 }],
      top_fornecedores: [],
      monthly_trend: [{ month: '2026-01', count: 50, value: 5000000 }],
      by_uf: [{ uf: 'SP', count: 200, value: 20000000 }],
      last_updated: '2026-04-08T12:00:00Z',
    };
    mockFetch().mockResolvedValue(
      mockResponse({
        ok: true,
        status: 200,
        json: () => Promise.resolve(mockStats),
      }),
    );

    const { fetchContratosSetorStats } = await import('@/lib/programmatic');
    const result = await fetchContratosSetorStats('informatica');
    expect(result).toEqual(mockStats);
  });
});
