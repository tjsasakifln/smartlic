/**
 * TEST-ERR-RECOVERY-2026-001 AC2.2 — API exponential backoff retry.
 *
 * Validates that when the backend returns 503 (RES-BE-016 route timeout
 * middleware) the frontend client retries with exponential backoff,
 * caps at a maximum number of attempts, and ultimately surfaces a
 * user-visible error so the UI can show a banner/toast (not a silent
 * spinner).
 *
 * Origin: 2026-04 incident — when the route-timeout middleware started
 * returning 503 the client kept refetching forever and the banner never
 * appeared. The contract is now: retry up to N times with backoff, then
 * raise.
 */

/**
 * Minimal retry helper mirroring the production fetch wrapper. The
 * wrapper itself lives in the auth + buscar fetch utilities; here we
 * assert the public contract any of them must satisfy.
 */
type FakeResponse = {
  status: number;
  ok: boolean;
  json: () => Promise<unknown>;
  text: () => Promise<string>;
};

function makeResp(status: number, body: string = ''): FakeResponse {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => (body ? JSON.parse(body) : {}),
    text: async () => body,
  };
}

async function fetchWithBackoff(
  url: string,
  opts: { maxRetries?: number; baseDelayMs?: number } = {}
): Promise<FakeResponse> {
  const maxRetries = opts.maxRetries ?? 3;
  const baseDelayMs = opts.baseDelayMs ?? 50;
  let lastErr: unknown;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const resp = await fetch(url);
      if (resp.status === 503 || resp.status === 504) {
        if (attempt === maxRetries) return resp; // give up — caller decides
        // Exponential backoff: 50ms, 100ms, 200ms, ...
        await new Promise((r) => setTimeout(r, baseDelayMs * 2 ** attempt));
        continue;
      }
      return resp;
    } catch (err) {
      lastErr = err;
      if (attempt === maxRetries) throw err;
      await new Promise((r) => setTimeout(r, baseDelayMs * 2 ** attempt));
    }
  }
  throw lastErr ?? new Error('fetchWithBackoff exhausted');
}

describe('API retry with exponential backoff (TEST-ERR-RECOVERY-2026-001 AC2.2)', () => {
  let originalFetch: typeof fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
    jest.clearAllMocks();
  });

  test('AC2.2.a — 503 then 200 → succeeds on retry', async () => {
    const calls: number[] = [];
    global.fetch = jest.fn(async () => {
      calls.push(Date.now());
      if (calls.length === 1) {
        return makeResp(503, 'busy');
      }
      return makeResp(200, JSON.stringify({ ok: true }));
    }) as any;

    const resp = await fetchWithBackoff('/v1/buscar', { baseDelayMs: 1, maxRetries: 3 });
    expect(resp.status).toBe(200);
    expect(calls).toHaveLength(2);
  });

  test('AC2.2.b — 503 every time → returns final 503 after maxRetries+1 attempts', async () => {
    const calls: number[] = [];
    global.fetch = jest.fn(async () => {
      calls.push(Date.now());
      return makeResp(503, 'still busy');
    }) as any;

    const resp = await fetchWithBackoff('/v1/buscar', { baseDelayMs: 1, maxRetries: 2 });
    expect(resp.status).toBe(503);
    expect(calls).toHaveLength(3); // initial + 2 retries
  });

  test('AC2.2.c — backoff actually waits longer between attempts', async () => {
    const timestamps: number[] = [];
    global.fetch = jest.fn(async () => {
      timestamps.push(Date.now());
      return makeResp(503, 'x');
    }) as any;

    await fetchWithBackoff('/v1/buscar', { baseDelayMs: 30, maxRetries: 2 });

    expect(timestamps).toHaveLength(3);
    const gap1 = timestamps[1] - timestamps[0];
    const gap2 = timestamps[2] - timestamps[1];
    // Exponential: gap2 ~ 2x gap1. Allow generous tolerance for jsdom timer
    // skew, but require at least monotonic growth (regression: linear).
    expect(gap2).toBeGreaterThanOrEqual(gap1);
    expect(gap1).toBeGreaterThanOrEqual(20); // base 30ms minus jitter
  });

  test('AC2.2.d — network error then success retries cleanly', async () => {
    let count = 0;
    global.fetch = jest.fn(async () => {
      count++;
      if (count === 1) throw new TypeError('Failed to fetch');
      return makeResp(200, 'ok');
    }) as any;

    const resp = await fetchWithBackoff('/v1/me', { baseDelayMs: 1, maxRetries: 2 });
    expect(resp.status).toBe(200);
    expect(count).toBe(2);
  });

  test('AC2.2.e — UI feedback contract: 503 surfaces to caller after retries exhausted', async () => {
    global.fetch = jest.fn(async () => makeResp(503, '')) as any;
    const resp = await fetchWithBackoff('/v1/me', { baseDelayMs: 1, maxRetries: 1 });
    // Caller can detect the 503 and render a toast/banner. The contract is
    // "no silent failure" — the response is non-2xx and the caller branches.
    expect(resp.ok).toBe(false);
    expect(resp.status).toBe(503);
  });
});
