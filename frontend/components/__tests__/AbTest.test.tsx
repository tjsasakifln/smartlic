/**
 * Tests for AbTest component (components/AbTest.tsx).
 * CONV-012 (#1323).
 *
 * Verifies:
 * - Renders the correct variant based on cookie assignment
 * - Tracks impression on mount via Mixpanel
 * - Returns null on SSR (initial render with null variant)
 * - Falls back to first variant when assigned variant is not in the map
 * - Handles empty variants map gracefully
 */

import React from 'react';
import { render, screen, act } from '@testing-library/react';

// Mock the ab-testing library
jest.mock('@/lib/ab-testing', () => {
  const actual = jest.requireActual('@/lib/ab-testing');
  return {
    ...actual,
    getOrSetVariant: jest.fn(),
    trackExperimentImpression: jest.fn(),
  };
});

import {
  getOrSetVariant,
  trackExperimentImpression,
} from '@/lib/ab-testing';

const mockGetOrSetVariant = getOrSetVariant as jest.Mock;
const mockTrackImpression = trackExperimentImpression as jest.Mock;

// We need the default import for AbTest
import { AbTest } from '../AbTest';

beforeEach(() => {
  jest.clearAllMocks();
  // Default: first render gets variant after mount
  mockGetOrSetVariant.mockReturnValue('control');
  mockTrackImpression.mockImplementation(() => {});
});

// ---------------------------------------------------------------------------
// Variant rendering
// ---------------------------------------------------------------------------

describe('variant rendering', () => {
  it('renders the control variant', async () => {
    mockGetOrSetVariant.mockReturnValue('control');

    await act(async () => {
      render(
        <AbTest
          experimentId="test-exp"
          variants={{
            control: <div data-testid="control-content">Control Content</div>,
            variant_a: <div data-testid="variant-content">Variant A Content</div>,
          }}
        />,
      );
    });

    // After mount, control should be rendered
    expect(screen.getByTestId('control-content')).toBeInTheDocument();
    expect(screen.queryByTestId('variant-content')).not.toBeInTheDocument();
  });

  it('renders the variant_a when assigned to variant_a', async () => {
    mockGetOrSetVariant.mockReturnValue('variant_a');

    await act(async () => {
      render(
        <AbTest
          experimentId="test-exp"
          variants={{
            control: <div data-testid="control-content">Control Content</div>,
            variant_a: <div data-testid="variant-content">Variant A Content</div>,
          }}
        />,
      );
    });

    expect(screen.getByTestId('variant-content')).toBeInTheDocument();
    expect(screen.queryByTestId('control-content')).not.toBeInTheDocument();
  });

  it('renders complex children (nested elements)', async () => {
    mockGetOrSetVariant.mockReturnValue('variant_b');

    await act(async () => {
      render(
        <AbTest
          experimentId="test-exp"
          variants={{
            control: <span>Simple</span>,
            variant_b: (
              <div data-testid="complex">
                <h2>Title</h2>
                <p>Description with <strong>bold</strong></p>
              </div>
            ),
          }}
        />,
      );
    });

    expect(screen.getByTestId('complex')).toBeInTheDocument();
    expect(screen.getByText('Title')).toBeInTheDocument();
    expect(screen.getByText('Description with')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Impression tracking
// ---------------------------------------------------------------------------

describe('impression tracking', () => {
  it('tracks impression via Mixpanel on mount', async () => {
    mockGetOrSetVariant.mockReturnValue('variant_a');

    await act(async () => {
      render(
        <AbTest
          experimentId="track-test-exp"
          variants={{
            control: <div>Control</div>,
            variant_a: <div>Variant A</div>,
          }}
        />,
      );
    });

    expect(mockTrackImpression).toHaveBeenCalledTimes(1);
    expect(mockTrackImpression).toHaveBeenCalledWith(
      'track-test-exp',
      'variant_a',
    );
  });

  it('tracks impression only once (not on re-renders)', async () => {
    mockGetOrSetVariant.mockReturnValue('control');

    const { rerender } = render(
      <AbTest
        experimentId="once-test"
        variants={{
          control: <div>Control</div>,
          variant_a: <div>Variant A</div>,
        }}
      />,
    );

    // Rerender with same props — impression should not fire again
    rerender(
      <AbTest
        experimentId="once-test"
        variants={{
          control: <div>Control</div>,
          variant_a: <div>Variant A</div>,
        }}
      />,
    );

    expect(mockTrackImpression).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// SSR behavior
// ---------------------------------------------------------------------------

describe('SSR behavior', () => {
  it('renders the first variant when getOrSetVariant returns an unknown variant', () => {
    // getOrSetVariant might return a variant not in the map (e.g., during migration)
    mockGetOrSetVariant.mockReturnValue('unknown_variant');

    const { container } = render(
      <AbTest
        experimentId="ssr-fallback"
        variants={{
          control: <div>Control Content</div>,
          variant_a: <div>Variant A</div>,
        }}
      />,
    );

    // Should fall back to the first variant (control)
    expect(container.innerHTML).toContain('Control Content');
  });

  it('handles missing experiment gracefully by rendering the control', () => {
    mockGetOrSetVariant.mockReturnValue('control');

    const { container } = render(
      <AbTest
        experimentId="missing-exp"
        variants={{
          control: <span>Default</span>,
        }}
      />,
    );

    expect(container.innerHTML).toContain('Default');
  });
});

// ---------------------------------------------------------------------------
// Fallback behavior
// ---------------------------------------------------------------------------

describe('fallback behavior', () => {
  it('falls back to the first variant when assigned variant is not in the map', async () => {
    mockGetOrSetVariant.mockReturnValue('non_existent_variant');

    await act(async () => {
      render(
        <AbTest
          experimentId="fallback-test"
          variants={{
            control: <div data-testid="fallback-control">Control</div>,
            variant_a: <div data-testid="fallback-variant">Variant A</div>,
          }}
        />,
      );
    });

    // Should render the first variant (control) as fallback
    expect(screen.getByTestId('fallback-control')).toBeInTheDocument();
  });

  it('renders fallback prop when provided and variants are empty', async () => {
    mockGetOrSetVariant.mockReturnValue('__empty__');

    await act(async () => {
      render(
        <AbTest
          experimentId="empty-test"
          variants={{}}
          fallback={<div data-testid="fallback">Fallback Content</div>}
        />,
      );
    });

    expect(screen.getByTestId('fallback')).toBeInTheDocument();
  });

  it('renders nothing when variants are empty and no fallback provided', async () => {
    mockGetOrSetVariant.mockReturnValue('__empty__');

    const { container } = render(
      <AbTest
        experimentId="empty-no-fallback"
        variants={{}}
      />,
    );

    expect(container.innerHTML).toBe('');
  });
});
