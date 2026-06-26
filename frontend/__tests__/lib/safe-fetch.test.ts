/**
 * FOUND-SCALE-002: Tests for safeFetch + fetchWithBudget wrappers.
 * PSEO-P1-2048: Added tests for two-tier throwOn5xx + Retry-After + isBuildPhase.
 */
import { safeFetch, fetchWithBudget, isBuildPhase } from '../../lib/safe-fetch';
import * as Sentry from '@sentry/nextjs';

jest.mock('@sentry/nextjs', () => ({
  captureException: jest.fn(),
  captureMessage: jest.fn(),
  addBreadcrumb: jest.fn(),
}));

const SentryMock = Sentry as unknown as {
  captureException: jest.Mock;
  captureMessage: jest.Mock;
  addBreadcrumb: jest.Mock;
};

// jsdom does not provide a global `Response` constructor. Build minimal
// mock matching Response shape we use (`ok`, `status`, `json()`).
function mockResponse(body: unknown, status = 200, headers?: Record<string, string>): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    headers: new Map(Object.entries(headers || {})),
    ...(headers ? { headers: new Map(Object.entries(headers)) } : {}),
  } as unknown as Response;
}

describe('isBuildPhase() (PSEO-P1-2048)', () => {
  const originalEnv = process.env;

  afterEach(() => {
    process.env = { ...originalEnv };
  });

  it('returns true when NEXT_PHASE is phase-production-build', () => {
    process.env.NEXT_PHASE = 'phase-production-build';
    expect(isBuildPhase()).toBe(true);
  });

  it('returns true when NEXT_PHASE is phase-development-build', () => {
    process.env.NEXT_PHASE = 'phase-development-build';
    expect(isBuildPhase()).toBe(true);
  });

  it('returns false when NEXT_PHASE is absent', () => {
    delete process.env.NEXT_PHASE;
    expect(isBuildPhase()).toBe(false);
  });

  it('returns false when NEXT_PHASE is phase-production-server', () => {
    process.env.NEXT_PHASE = 'phase-production-server';
    expect(isBuildPhase()).toBe(false);
  });
});

describe('safeFetch (FOUND-SCALE-002 AC4)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    SentryMock.captureException.mockReset();
    SentryMock.captureMessage.mockReset();
    SentryMock.addBreadcrumb.mockReset();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('returns Response on 200 OK', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({ ok: true }, 200),
    ) as jest.Mock;
    const resp = await safeFetch('https://api.test/x');
    expect(resp).not.toBeNull();
    expect(resp?.status).toBe(200);
    expect(SentryMock.addBreadcrumb).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'fetch',
        level: 'info',
      }),
    );
  });

  it('returns null on HTTP error and emits Sentry message', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({ error: true }, 502),
    ) as jest.Mock;
    const resp = await safeFetch('https://api.test/x', { label: 'test-502' });
    expect(resp).toBeNull();
    expect(SentryMock.captureMessage).toHaveBeenCalledWith(
      expect.stringContaining('HTTP 502'),
      expect.objectContaining({
        tags: expect.objectContaining({ fetch_outcome: 'http_error' }),
      }),
    );
  });

  it('returns null on network error and emits Sentry exception', async () => {
    const networkErr = new Error('ECONNREFUSED');
    global.fetch = jest.fn().mockRejectedValue(networkErr) as jest.Mock;
    const resp = await safeFetch('https://api.test/x', { label: 'test-net' });
    expect(resp).toBeNull();
    expect(SentryMock.captureException).toHaveBeenCalledWith(
      networkErr,
      expect.objectContaining({
        tags: expect.objectContaining({ fetch_outcome: 'network_error' }),
      }),
    );
  });

  it('returns null on TimeoutError and tags as timeout', async () => {
    const timeoutErr = new Error('signal timed out');
    timeoutErr.name = 'TimeoutError';
    global.fetch = jest.fn().mockRejectedValue(timeoutErr) as jest.Mock;
    const resp = await safeFetch('https://api.test/x', { label: 'test-timeout' });
    expect(resp).toBeNull();
    expect(SentryMock.captureException).toHaveBeenCalledWith(
      timeoutErr,
      expect.objectContaining({
        tags: expect.objectContaining({ fetch_outcome: 'timeout' }),
      }),
    );
  });

  // PSEO-P1-2048: Two-tier throwOn5xx
  it('returns null on 5xx with throwOn5xx=true during build phase', async () => {
    const origPhase = process.env.NEXT_PHASE;
    process.env.NEXT_PHASE = 'phase-production-build';
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({}, 503),
    ) as jest.Mock;
    const resp = await safeFetch('https://api.test/x', {
      label: 'test-build-5xx',
      throwOn5xx: true,
    });
    expect(resp).toBeNull();
    process.env.NEXT_PHASE = origPhase;
  });

  it('returns null on 5xx with throwOn5xx=false (default behavior unchanged)', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({}, 502),
    ) as jest.Mock;
    const resp = await safeFetch('https://api.test/x', { label: 'test-502' });
    expect(resp).toBeNull();
    expect(SentryMock.captureMessage).toHaveBeenCalledWith(
      expect.stringContaining('HTTP 502'),
      expect.objectContaining({
        tags: expect.objectContaining({ fetch_outcome: 'http_error' }),
      }),
    );
  });
});

describe('fetchWithBudget (FOUND-SCALE-002 AC7)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    SentryMock.captureException.mockReset();
    SentryMock.captureMessage.mockReset();
    SentryMock.addBreadcrumb.mockReset();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('returns parsed JSON on success (no retry)', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({ value: 42 }, 200),
    ) as jest.Mock;
    const result = await fetchWithBudget<{ value: number }>('https://api.test/x', {
      label: 'test',
      retries: 0,
    });
    expect(result).toEqual({ value: 42 });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it('retries once and succeeds on 2nd attempt', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce(mockResponse({}, 502))
      .mockResolvedValueOnce(mockResponse({ value: 1 }, 200)) as jest.Mock;
    const result = await fetchWithBudget<{ value: number }>('https://api.test/x', {
      label: 'test-retry',
      retries: 1,
    });
    expect(result).toEqual({ value: 1 });
    expect(global.fetch).toHaveBeenCalledTimes(2);
  });

  it('returns fallback after all attempts fail (default throwOn5xx=false)', async () => {
    global.fetch = jest
      .fn()
      .mockResolvedValue(mockResponse({}, 503)) as jest.Mock;
    const fallback = { value: 0, fallback: true };
    const result = await fetchWithBudget('https://api.test/x', {
      label: 'test-exhausted',
      retries: 1,
      fallback,
    });
    expect(result).toEqual(fallback);
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(SentryMock.captureMessage).toHaveBeenCalledWith(
      expect.stringContaining('fetchWithBudget_exhausted_test-exhausted'),
      expect.objectContaining({
        tags: expect.objectContaining({ fetch_outcome: 'budget_exhausted' }),
      }),
    );
  });

  it('applies extract transformer on parsed data', async () => {
    global.fetch = jest.fn().mockResolvedValue(
      mockResponse({ items: [{ id: 1 }, { id: 2 }] }, 200),
    ) as jest.Mock;
    const result = await fetchWithBudget<number[]>('https://api.test/x', {
      label: 'test-extract',
      retries: 0,
      extract: (data) => (data as { items: { id: number }[] }).items.map((i) => i.id),
    });
    expect(result).toEqual([1, 2]);
  });

  it('uses next.revalidate by default 3600s', async () => {
    const fetchMock = jest.fn().mockResolvedValue(mockResponse({ ok: true }, 200));
    global.fetch = fetchMock as jest.Mock;
    await fetchWithBudget('https://api.test/x', { label: 'test-isr', retries: 0 });
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.test/x',
      expect.objectContaining({
        next: expect.objectContaining({ revalidate: 3600 }),
      }),
    );
  });

  // PSEO-P1-2048: Two-tier throwOn5xx — build phase returns fallback
  it('returns fallback on 5xx with throwOn5xx=true during build', async () => {
    const origPhase = process.env.NEXT_PHASE;
    process.env.NEXT_PHASE = 'phase-production-build';
    global.fetch = jest
      .fn()
      .mockResolvedValue(mockResponse({}, 500)) as jest.Mock;
    const result = await fetchWithBudget('https://api.test/x', {
      label: 'test-build',
      retries: 1,
      fallback: null,
      throwOn5xx: true,
    });
    expect(result).toBeNull();
    expect(global.fetch).toHaveBeenCalledTimes(2);
    process.env.NEXT_PHASE = origPhase;
  });

});
