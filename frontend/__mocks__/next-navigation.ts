/**
 * Mock for next/navigation module.
 * Used by IntentRouter/IntentTrail tests.
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const jestFn = (typeof jest !== 'undefined' ? jest.fn : () => {}) as any;

export function useSearchParams(): URLSearchParams {
  return new URLSearchParams();
}

export function useRouter() {
  return {
    push: jestFn,
    replace: jestFn,
    prefetch: jestFn,
    back: jestFn,
    forward: jestFn,
  };
}

export function usePathname(): string {
  return '/';
}

export function useParams(): Record<string, string> {
  return {};
}

export function notFound(): void {
  // noop
}

export function redirect(): void {
  // noop
}
