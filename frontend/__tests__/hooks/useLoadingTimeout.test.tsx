/**
 * UX-309: useLoadingTimeout Hook Tests
 *
 * Tests:
 * - AC1: Timeout fires after the specified duration
 * - AC2: Normal flows (<5s) complete without timeout
 * - AC3: Reset function clears timeout state
 * - AC4: Disabled hook does not fire timeout
 * - AC5: timeLeft decreases correctly
 */

import { renderHook, act } from '@testing-library/react';
import { useLoadingTimeout } from '../../hooks/useLoadingTimeout';

describe('useLoadingTimeout', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  // AC1: Timeout fires after the specified duration
  describe('AC1: Timeout fires after specified duration', () => {
    it('should set timedOut=true after timeoutMs elapses', () => {
      const onTimeout = jest.fn();
      const { result } = renderHook(() =>
        useLoadingTimeout({ timeoutMs: 5000, onTimeout })
      );

      expect(result.current.timedOut).toBe(false);
      expect(result.current.timeLeft).toBe(5000);

      // Advance time nearly to timeout
      act(() => { jest.advanceTimersByTime(4000); });
      expect(result.current.timedOut).toBe(false);
      expect(result.current.timeLeft).toBe(1000);

      // Advance past timeout
      act(() => { jest.advanceTimersByTime(1000); });
      expect(result.current.timedOut).toBe(true);
      expect(result.current.timeLeft).toBe(0);
      expect(onTimeout).toHaveBeenCalledTimes(1);
    });

    it('should fire timeout after the default 30s', () => {
      const { result } = renderHook(() => useLoadingTimeout());

      act(() => { jest.advanceTimersByTime(29999); });
      expect(result.current.timedOut).toBe(false);

      act(() => { jest.advanceTimersByTime(1); });
      expect(result.current.timedOut).toBe(true);
    });
  });

  // AC2: Normal flows (<5s) complete without timeout
  describe('AC2: Normal flows complete without timeout', () => {
    it('should not fire timeout for flows under 5s when loading finishes', () => {
      const { result, unmount } = renderHook(() =>
        useLoadingTimeout({ timeoutMs: 30000 })
      );

      // Simulate normal flow: loading finishes within 5s
      act(() => { jest.advanceTimersByTime(5000); });
      expect(result.current.timedOut).toBe(false);

      // Unmount (simulating component unmount when loading completes)
      unmount();
      // No exception = pass
    });

    it('should reset when loading finishes and restarts later', () => {
      const { result, rerender } = renderHook(
        ({ enabled }) => useLoadingTimeout({ timeoutMs: 10000, enabled }),
        { initialProps: { enabled: true } }
      );

      // Loading is in progress
      act(() => { jest.advanceTimersByTime(3000); });
      expect(result.current.timedOut).toBe(false);

      // Loading completes
      rerender({ enabled: false });
      expect(result.current.timedOut).toBe(false);

      // Loading restarts
      rerender({ enabled: true });
      expect(result.current.timedOut).toBe(false);
      expect(result.current.timeLeft).toBe(10000);
    });
  });

  // AC3: Reset function clears timeout state
  describe('AC3: Reset function clears timeout state', () => {
    it('should reset timedOut and timeLeft after timeout fires', () => {
      const { result } = renderHook(() =>
        useLoadingTimeout({ timeoutMs: 5000 })
      );

      // Advance to timeout
      act(() => { jest.advanceTimersByTime(5000); });
      expect(result.current.timedOut).toBe(true);
      expect(result.current.timeLeft).toBe(0);

      // Reset
      act(() => { result.current.reset(); });
      expect(result.current.timedOut).toBe(false);
      expect(result.current.timeLeft).toBe(5000);
    });

    it('should restart the countdown after reset', () => {
      const { result } = renderHook(() =>
        useLoadingTimeout({ timeoutMs: 10000 })
      );

      act(() => { jest.advanceTimersByTime(8000); });
      expect(result.current.timeLeft).toBe(2000);

      act(() => { result.current.reset(); });
      expect(result.current.timeLeft).toBe(10000);

      act(() => { jest.advanceTimersByTime(5000); });
      expect(result.current.timedOut).toBe(false);
    });
  });

  // AC4: Disabled hook does not fire timeout
  describe('AC4: Disabled hook does not fire timeout', () => {
    it('should not fire timeout when enabled is false', () => {
      const onTimeout = jest.fn();
      const { result } = renderHook(() =>
        useLoadingTimeout({ timeoutMs: 5000, enabled: false, onTimeout })
      );

      act(() => { jest.advanceTimersByTime(10000); });
      expect(result.current.timedOut).toBe(false);
      expect(result.current.timeLeft).toBe(5000);
      expect(onTimeout).not.toHaveBeenCalled();
    });
  });

  // AC5: timeLeft decreases correctly
  describe('AC5: timeLeft decreases correctly', () => {
    it('should show decreasing timeLeft every second', () => {
      const { result } = renderHook(() =>
        useLoadingTimeout({ timeoutMs: 10000 })
      );

      act(() => { jest.advanceTimersByTime(1000); });
      expect(result.current.timeLeft).toBe(9000);

      act(() => { jest.advanceTimersByTime(4000); });
      expect(result.current.timeLeft).toBe(5000);

      act(() => { jest.advanceTimersByTime(5000); });
      expect(result.current.timeLeft).toBe(0);
    });
  });
});
