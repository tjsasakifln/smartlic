/**
 * GAP-005: SSE heartbeat timeout detection + polling fallback.
 *
 * Tests that useSearchSSE:
 * 1. Listens for heartbeat named events
 * 2. Detects missing heartbeats after 33s timeout
 * 3. Falls back to HTTP polling
 * 4. Tries periodic reconnection
 * 5. Recovers when heartbeat returns
 */

import { renderHook, act } from '@testing-library/react';

// ---- Mock modules BEFORE importing hooks ----

jest.mock('../hooks/useAnalytics', () => ({
  useAnalytics: () => ({ trackEvent: jest.fn() }),
}));

jest.mock('../app/components/AuthProvider', () => ({
  useAuth: () => ({
    session: { access_token: 'test-token' },
    loading: false,
  }),
}));

jest.mock('../hooks/useQuota', () => ({
  useQuota: () => ({ refresh: jest.fn() }),
}));

jest.mock('../hooks/useSavedSearches', () => ({
  useSavedSearches: () => ({
    saveNewSearch: jest.fn(),
    isMaxCapacity: false,
  }),
}));

jest.mock('../lib/searchStatePersistence', () => ({
  saveSearchState: jest.fn(),
  restoreSearchState: jest.fn(() => null),
}));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

jest.mock('../lib/utils/correlationId', () => ({
  getCorrelationId: () => 'test-corr-id',
  logCorrelatedRequest: jest.fn(),
}));

import { MockEventSource } from './utils/mock-event-source';
import { useSearchSSE, SSE_HEARTBEAT_TIMEOUT_MS, SSE_RECONNECT_INTERVAL_MS, SSE_POLLING_INTERVAL_MS } from '../hooks/useSearchSSE';

describe('GAP-005: Heartbeat Fallback', () => {
  const originalConsoleWarn = console.warn;
  const originalConsoleInfo = console.info;
  let mockFetch: jest.Mock;

  beforeAll(() => {
    console.warn = jest.fn();
    console.info = jest.fn();
  });

  afterAll(() => {
    console.warn = originalConsoleWarn;
    console.info = originalConsoleInfo;
  });

  beforeEach(() => {
    jest.useFakeTimers();
    mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'running', progress: 50 }),
    });
    global.fetch = mockFetch;
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  test('AC1: heartbeat event resets the heartbeat timer', () => {
    const { result } = renderHook(() =>
      useSearchSSE({
        searchId: 'test-search-hb-001',
        enabled: true,
        authToken: 'test-token',
      })
    );

    // Open EventSource
    act(() => {
      MockEventSource.instances[0].simulateOpen();
    });

    expect(result.current.heartbeatFallbackActive).toBe(false);

    // Advance almost to timeout, send heartbeat
    act(() => {
      jest.advanceTimersByTime(SSE_HEARTBEAT_TIMEOUT_MS - 1000);
    });

    // Send heartbeat using the named event helper
    act(() => {
      MockEventSource.instances[0].simulateMessage({}, { event: 'heartbeat' });
    });

    // Advance past original timeout — heartbeat reset the timer, so still OK
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    expect(result.current.heartbeatFallbackActive).toBe(false);
  });

  test('AC2: missing heartbeat for 33s triggers polling fallback', () => {
    const { result } = renderHook(() =>
      useSearchSSE({
        searchId: 'test-search-hb-002',
        enabled: true,
        authToken: 'test-token',
      })
    );

    // Open EventSource
    act(() => {
      MockEventSource.instances[0].simulateOpen();
    });

    // Advance past heartbeat timeout without sending heartbeat
    act(() => {
      jest.advanceTimersByTime(SSE_HEARTBEAT_TIMEOUT_MS + 1000);
    });

    expect(result.current.heartbeatFallbackActive).toBe(true);
    expect(console.warn).toHaveBeenCalledWith(
      expect.stringContaining('heartbeat perdido')
    );
  });

  test('AC3: polling uses /api/v1/buscar/{id}/state endpoint', () => {
    const { result } = renderHook(() =>
      useSearchSSE({
        searchId: 'test-search-hb-003',
        enabled: true,
        authToken: 'test-token',
      })
    );

    // Open EventSource
    act(() => {
      MockEventSource.instances[0].simulateOpen();
    });

    // Trigger heartbeat timeout
    act(() => {
      jest.advanceTimersByTime(SSE_HEARTBEAT_TIMEOUT_MS + 1000);
    });

    expect(result.current.heartbeatFallbackActive).toBe(true);

    // Advance polling interval to trigger first poll fetch
    act(() => {
      jest.advanceTimersByTime(SSE_POLLING_INTERVAL_MS);
    });

    // Should have called the specific state endpoint
    const pollUrl = mockFetch.mock.calls.find(
      (call: unknown[]) => typeof call[0] === 'string' && (call[0] as string).includes('/api/v1/buscar/')
    );
    expect(pollUrl).toBeTruthy();
    expect((pollUrl?.[0] as string)).toContain('/api/v1/buscar/');
    expect((pollUrl?.[0] as string)).toContain('/state');
  });

  test('AC4: periodic reconnection attempts every 15s when EventSource closed in fallback', () => {
    renderHook(() =>
      useSearchSSE({
        searchId: 'test-search-hb-004',
        enabled: true,
        authToken: 'test-token',
      })
    );

    // Open EventSource
    act(() => {
      MockEventSource.instances[0].simulateOpen();
    });

    // Simulate EventSource closing (as if an error occurred)
    act(() => {
      MockEventSource.instances[0].close();
    });

    // Trigger heartbeat timeout — activates fallback and starts reconnection interval
    act(() => {
      jest.advanceTimersByTime(SSE_HEARTBEAT_TIMEOUT_MS + 1000);
    });

    const beforeReconnect = MockEventSource.instances.length;

    // Advance by reconnect interval — new EventSource should be created
    act(() => {
      jest.advanceTimersByTime(SSE_RECONNECT_INTERVAL_MS);
    });

    // More EventSource instances should have been created by periodic reconnect
    expect(MockEventSource.instances.length).toBeGreaterThan(beforeReconnect);
  });

  test('AC5: heartbeat returns via simulateMessage -> stops polling and fallback', () => {
    const { result } = renderHook(() =>
      useSearchSSE({
        searchId: 'test-search-hb-005',
        enabled: true,
        authToken: 'test-token',
      })
    );

    // Open EventSource
    act(() => {
      MockEventSource.instances[0].simulateOpen();
    });

    // Trigger heartbeat timeout -> fallback activated
    act(() => {
      jest.advanceTimersByTime(SSE_HEARTBEAT_TIMEOUT_MS + 1000);
    });

    expect(result.current.heartbeatFallbackActive).toBe(true);

    // Now simulate a heartbeat coming back using simulateMessage
    act(() => {
      MockEventSource.instances[0].simulateMessage({}, { event: 'heartbeat' });
    });

    // Fallback should be deactivated
    expect(result.current.heartbeatFallbackActive).toBe(false);
    expect(console.info).toHaveBeenCalledWith(
      expect.stringContaining('polling fallback desativado')
    );
  });
});
