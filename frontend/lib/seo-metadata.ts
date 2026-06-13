/**
 * Safe metadata fetch wrapper — prevents ``generateMetadata`` from crashing
 * on transient backend errors (5xx / network / timeout).
 *
 * Background (ADR-SEO-001 / SEO-FE-ISR-001 #1038):
 *   Many programmatic ISR pages deliberately re-throw 5xx errors to preserve
 *   the last-good cached HTML.  The same fetcher is also called from
 *   ``generateMetadata`` where there is no error boundary — Next.js App Router
 *   does NOT wrap ``generateMetadata`` with ``error.tsx``.  A re-thrown 5xx
 *   inside metadata therefore produces a bare 500 Internal Server Error with
 *   no friendly UI, no Sentry context, and a poisoned ISR cache slot.
 *
 *   This wrapper swallows every exception so metadata never crashes.  The page
 *   body still gets the original 5xx (and either falls back to the previous
 *   ISR cache or shows the segment ``error.tsx`` boundary).
 *
 * Usage:
 *   export async function generateMetadata({ params }: Props): Promise<Metadata> {
 *     const { slug } = await params;
 *     const data = await safeMetadataFetch(() => fetchMyData(slug), null);
 *     if (!data) return { title: 'Fallback title' };
 *     return { title: data.title, description: data.description };
 *   }
 *
 * CAVEAT:
 *   Metadata will be stale (last-good title / fallback) during backend
 *   outages.  This is intentional — better than serving a 500.  Googlebot
 *   treats a 200 with slightly-dated metadata as a transient signal; it treats
 *   a 500 as a hard removal signal and drops the URL from the index.
 */

export async function safeMetadataFetch<T>(
  fetcher: () => Promise<T>,
  fallback: T,
): Promise<T> {
  try {
    return await fetcher();
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.warn(
      `[safeMetadataFetch] using fallback metadata: ${message.slice(0, 200)}`,
    );
    return fallback;
  }
}
