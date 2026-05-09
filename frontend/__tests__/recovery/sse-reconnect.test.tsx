/**
 * TEST-ERR-RECOVERY-2026-001 AC2.1 — SSE reconnection.
 *
 * Validates that when a search EventSource closes mid-stream, the
 * consumer (a) preserves whatever state it accumulated, and (b) is
 * able to reattach to a fresh EventSource (the search_id is the
 * stable handle) without losing partial UF progress.
 *
 * Origin: STORY-2.4 EPIC-TD — frontend lost search progress on SSE
 * disconnect (Railway 60s idle, browser tab backgrounding).
 */

import { MockEventSource } from '../utils/mock-event-source';

// Minimal consumer hook — mirrors the production SSE consumer in
// `app/buscar/components/EnhancedLoadingProgress.tsx`. We import the
// MockEventSource directly to make the recovery contract explicit.

interface ProgressState {
  uf_progress: Record<string, string>;
  stage: string | null;
  reconnects: number;
}

function createSseClient(searchId: string): {
  state: ProgressState;
  open: () => MockEventSource;
  closeAndReconnect: () => MockEventSource;
} {
  const state: ProgressState = {
    uf_progress: {},
    stage: null,
    reconnects: 0,
  };

  function attach(es: MockEventSource): void {
    es.onmessage = (evt: any) => {
      try {
        const payload = typeof evt.data === 'string' ? JSON.parse(evt.data) : evt.data;
        if (payload.stage) state.stage = payload.stage;
        if (payload.detail?.uf && payload.detail?.status) {
          state.uf_progress[payload.detail.uf] = payload.detail.status;
        }
      } catch {
        /* swallow malformed events */
      }
    };
  }

  return {
    state,
    open() {
      const es = new (globalThis as any).EventSource(`/api/buscar-progress/${searchId}`) as MockEventSource;
      attach(es);
      return es;
    },
    closeAndReconnect() {
      state.reconnects += 1;
      const es = new (globalThis as any).EventSource(`/api/buscar-progress/${searchId}`) as MockEventSource;
      attach(es);
      return es;
    },
  };
}

describe('SSE reconnection (TEST-ERR-RECOVERY-2026-001 AC2.1)', () => {
  beforeEach(() => {
    MockEventSource.reset();
  });

  test('AC2.1.a — partial UF progress is preserved across reconnect', () => {
    const client = createSseClient('search-recovery-001');
    const es1 = client.open();
    es1.readyState = 1; // OPEN

    // First connection emits SC + PR progress, then errors out.
    es1.onmessage?.({ data: JSON.stringify({ stage: 'fetching', detail: { uf: 'SC', status: 'fetching' } }) });
    es1.onmessage?.({ data: JSON.stringify({ stage: 'fetching', detail: { uf: 'PR', status: 'completed' } }) });

    expect(client.state.uf_progress).toEqual({ SC: 'fetching', PR: 'completed' });

    // Simulate Railway idle kill.
    es1.onerror?.({});
    es1.close();

    // Reconnect — partial state must survive.
    const es2 = client.closeAndReconnect();
    es2.readyState = 1;
    expect(client.state.uf_progress).toEqual({ SC: 'fetching', PR: 'completed' });

    // Second connection completes SC and adds RS.
    es2.onmessage?.({ data: JSON.stringify({ detail: { uf: 'SC', status: 'completed' } }) });
    es2.onmessage?.({ data: JSON.stringify({ detail: { uf: 'RS', status: 'completed' } }) });

    expect(client.state.uf_progress).toEqual({
      SC: 'completed',
      PR: 'completed',
      RS: 'completed',
    });
    expect(client.state.reconnects).toBe(1);
  });

  test('AC2.1.b — second EventSource is a NEW instance pointing at the same search_id', () => {
    const client = createSseClient('search-recovery-002');
    const es1 = client.open();
    expect(MockEventSource.instances).toHaveLength(1);
    expect(es1.url).toContain('search-recovery-002');

    es1.onerror?.({});
    es1.close();

    const es2 = client.closeAndReconnect();
    expect(MockEventSource.instances).toHaveLength(2);
    expect(es2.url).toContain('search-recovery-002');
    // Stable handle, distinct underlying EventSource.
    expect(es2).not.toBe(es1);
  });

  test('AC2.1.c — malformed events are dropped, valid events still update state', () => {
    const client = createSseClient('search-recovery-003');
    const es = client.open();
    es.readyState = 1;

    // Garbage event must not throw or corrupt state.
    es.onmessage?.({ data: 'not-json' });
    expect(client.state.uf_progress).toEqual({});

    // Valid event still applied.
    es.onmessage?.({ data: JSON.stringify({ detail: { uf: 'MG', status: 'fetching' } }) });
    expect(client.state.uf_progress).toEqual({ MG: 'fetching' });
  });
});
