/**
 * safeFetch + fetchWithBudget — observable fetch wrappers with Sentry instrumentation.
 *
 * PSEO-P1-2048: Two-Tier ISR Error Strategy.
 *   Centraliza todo error handling de ISR no fetchWithBudget unificado.
 *   Elimina as estrategias B (programmatic/types.ts) e C (paginas inline).
 *
 * Estrategia two-tier de throwOn5xx:
 *   - Durante build (SSG/next build): 5xx → retorna null/fallback.
 *     Nao existe cache ISR para proteger — throw quebraria o build.
 *   - Durante ISR runtime: 5xx → throw Error.
 *     O Next.js preserva o ultimo cache bom (stale-while-revalidate) e
 *     tenta novamente na proxima requisicao.
 *
 * Retry-After (PSEO-P1-2048): quando backend retorna 503 + header Retry-After,
 *   o safeFetch codifica o header no erro, e fetchWithBudget extrai, espera e
 *   retenta antes do backoff exponencial padrao.
 *
 * FOUND-SCALE-002: foundation para SEN-FE-002 (consolidacao) + SEN-FE-003 (SSG decouple).
 * Generaliza o pattern proven em `frontend/app/sitemap.ts::fetchSitemapJson` (STORY-SEO-001 +
 * SEN-BE-007) para uso em qualquer SSG/ISR fetch fora do sitemap.
 *
 * Memory references:
 *   - feedback_frontend_sentry_silent_buildtime — 0 events em 24h apesar de sitemap-4=0
 *     em prod; observability gap blind durante outage.
 *   - feedback_build_hammers_backend_cascade — SSG 4146 pages sem timeout/abort saturou
 *     backend hobby DB pool; AbortSignal.timeout obrigatorio.
 *   - feedback_isr_fetch_cache_alignment_next16 — `revalidate=N` + `cache: 'no-store'`
 *     quebra SSG; usar `next: { revalidate: N }`.
 */
import * as Sentry from '@sentry/nextjs';
import { ssgFetchLimiter } from '@/lib/concurrency';

export type SafeFetchOutcome =
  | 'success'
  | 'http_error'
  | 'timeout'
  | 'network_error';

export interface SafeFetchOptions extends RequestInit {
  /** Sentry tag for this call site (e.g. "cnpj-profile", "orgao-list"). */
  label?: string;
  /** Timeout in ms (default 15000ms). */
  timeout?: number;
  /**
   * PSEO-P1-2048: Two-tier throwOn5xx.
   *
   * When true, HTTP 5xx responses throw an Error during ISR runtime instead of
   * returning null. During build (SSG), 5xx returns null — no ISR cache exists
   * to protect.
   *
   * Use in ISR pages so transient backend errors preserve last-good cached page
   * (stale-while-revalidate) rather than caching an empty state.
   */
  throwOn5xx?: boolean;
}

/**
 * PSEO-P1-2048: Detecta se estamos em build (next build) ou ISR runtime.
 *
 * Movido de lib/programmatic/types.ts (era `IS_BUILD_PHASE` constante) para
 * centralizar a logica em safe-fetch.ts.
 *
 * Estrategia de deteccao:
 *   1. NEXT_PHASE env var — definida pelo Next.js CLI no processo principal.
 *      Pode nao propagar para worker processes de geracao estatica.
 *   2. process.argv[1] fallback — workers de build do Next.js vem de
 *      next/dist/build/ ou next/dist/compiled/. Workers de ISR runtime usam
 *      next/dist/server/ (excluidos).
 */
export function isBuildPhase(): boolean {
  if (typeof process === 'undefined') return false;
  if (
    process.env.NEXT_PHASE === 'phase-production-build' ||
    process.env.NEXT_PHASE === 'phase-development-build'
  ) {
    return true;
  }
  const execPath = process.argv[1] || '';
  if (
    execPath.includes('next/dist/build') ||
    execPath.includes('next/dist/compiled')
  ) {
    return true;
  }
  return false;
}

const RETRY_AFTER_PATTERN = /retry-after=(\d+)/;

/** Extrai Retry-After de uma mensagem de erro (setada por safeFetch ao lancar 5xx). */
function extractRetryAfter(errorMessage: string): number | null {
  const match = errorMessage.match(RETRY_AFTER_PATTERN);
  return match ? parseInt(match[1], 10) : null;
}

/**
 * Fetch wrapper com AbortSignal timeout, Sentry exception capture, e breadcrumb
 * estruturado. Returns null on any failure (HTTP error, timeout, network error).
 *
 * Comportamento de retorno (PSEO-P1-2048):
 *   - 2xx: Response
 *   - 4xx: null (+ Sentry warning, exceto 404 — NETINT-002)
 *   - 5xx + throwOn5xx=false (default): null (+ Sentry warning)
 *   - 5xx + throwOn5xx=true + BUILD: null (nao quebra o build)
 *   - 5xx + throwOn5xx=true + ISR: throw Error (com Retry-After opcional)
 *   - Timeout / network error: null (+ Sentry exception)
 *
 * Para fetch tipado com retry/fallback, use {@link fetchWithBudget}.
 */
export async function safeFetch(
  url: string,
  options: SafeFetchOptions = {},
): Promise<Response | null> {
  const { label = url, timeout = 15000, throwOn5xx = false, ...init } = options;
  const startedAt = Date.now();
  let outcome: SafeFetchOutcome = 'success';
  let statusCode = 0;

  try {
    // SSG build-time concurrency gate: max 6 parallel backend requests
    // previne o cascade timeout quando "next build" renderiza 4146+ paginas
    // simultaneamente (feedback_build_hammers_backend_cascade).
    const resp = await ssgFetchLimiter.run(() =>
      fetch(url, {
        ...init,
        signal: AbortSignal.timeout(timeout),
      }),
    );
    statusCode = resp.status;
    if (!resp.ok) {
      outcome = 'http_error';
      // NETINT-002 fix: 404 is expected for SEO programmatic pages — slugs
      // in sitemaps may not yet have data in the datalake. The page renders
      // <EmptyStateSEO> with noindex, so there is nothing to alert on.
      // Suppress Sentry noise (3012 events/14d from orgao-stats + cnpj-perfil).
      if (resp.status !== 404) {
        Sentry.captureMessage(`safeFetch ${label} HTTP ${resp.status}`, {
          level: 'warning',
          tags: { fetch_label: label, fetch_outcome: 'http_error' },
          contexts: { fetch: { url, status: resp.status } },
        });
      }
      // PSEO-P1-2048: Two-tier throwOn5xx — verifica build phase antes de decidir.
      if (throwOn5xx && resp.status >= 500) {
        if (isBuildPhase()) {
          // Build / SSG: retorna null em vez de throw.
          // Nao ha cache ISR a proteger — throw quebraria o build.
          return null;
        }
        // ISR runtime: throw para preservar stale cache.
        // Inclui Retry-After na mensagem para fetchWithBudget processar.
        const retryAfter = resp.headers.get('Retry-After');
        const raSuffix = retryAfter ? `:retry-after=${retryAfter}` : '';
        throw new Error(`safeFetch_5xx:${label}:${resp.status}${raSuffix}`);
      }
      return null;
    }
    return resp;
  } catch (err) {
    // PSEO-P1-2048: os throws intencionais de 5xx propagam para que
    // fetchWithBudget possa extrair Retry-After e decidir sobre retry.
    if (err instanceof Error && err.message.startsWith('safeFetch_5xx:')) {
      throw err;
    }
    const errName = (err as Error)?.name || '';
    outcome =
      errName === 'TimeoutError' || errName === 'AbortError'
        ? 'timeout'
        : 'network_error';
    Sentry.captureException(err, {
      tags: { fetch_label: label, fetch_outcome: outcome },
      contexts: { fetch: { url } },
    });
    return null;
  } finally {
    Sentry.addBreadcrumb({
      category: 'fetch',
      message: `safeFetch ${label}`,
      level: outcome === 'success' ? 'info' : 'warning',
      data: {
        fetch_outcome: outcome,
        status_code: statusCode,
        latency_ms: Date.now() - startedAt,
        url,
      },
    });
  }
}

export interface FetchBudgetOptions<T> {
  /** Timeout per attempt in ms (default 10000ms). */
  timeout?: number;
  /** Retry count after first failure (default 1 — total 2 attempts). */
  retries?: number;
  /** Fallback value if all attempts fail (default null). */
  fallback?: T | null;
  /** Next.js ISR revalidate window in seconds (default 3600). */
  revalidate?: number;
  /** Sentry tag (default url). */
  label?: string;
  /**
   * PSEO-P1-2048: Two-tier throwOn5xx.
   *
   * When true, HTTP 5xx responses re-throw after all retries during ISR runtime
   * (preserving last-good stale-while-revalidate cache). During build (SSG), 5xx
   * returns `fallback` instead.
   *
   * Compatível com Retry-After: se backend retornar 503 + Retry-After, espera
   * os segundos indicados e retenta antes do backoff exponencial.
   */
  throwOn5xx?: boolean;
  /**
   * Optional response shape transformer. Receives parsed JSON, must return
   * the typed value or throw on shape mismatch.
   */
  extract?: (data: unknown) => T;
}

/**
 * Typed JSON fetch wrapper com retry, fallback, Sentry observability, e
 * two-tier ISR error strategy.
 *
 * PSEO-P1-2048: Two-tier throwOn5xx integrado.
 *   - Build (SSG): 5xx retorna `fallback` — nunca quebra o build.
 *   - ISR runtime: 5xx throws apos exaurir retries — preserva stale cache.
 *   - Retry-After: 503 + header Retry-After → espera e retenta.
 *
 * Defaults to Next.js ISR-friendly cache: `next: { revalidate: 3600 }`.
 * NEVER pass `cache: 'no-store'` in conjunction with `revalidate` — quebra SSG
 * (memory `feedback_isr_fetch_cache_alignment_next16`).
 *
 * @example
 *   // ISR page com throwOn5xx: true — 5xx preserva stale cache
 *   const profile = await fetchWithBudget<Profile>(
 *     `${getBackendUrl()}/v1/empresa/${cnpj}/perfil-b2g`,
 *     { timeout: 10000, retries: 1, fallback: null, label: 'cnpj-profile', throwOn5xx: true }
 *   );
 *
 * @example
 *   // Pagina sem ISR (ou build-only) — throwOn5xx false (default)
 *   const data = await fetchWithBudget<Data>(
 *     `${url}/data`,
 *     { timeout: 5000, retries: 0, fallback: defaultData }
 *   );
 */
export async function fetchWithBudget<T>(
  url: string,
  opts: FetchBudgetOptions<T> = {},
): Promise<T | null> {
  const {
    timeout = 10000,
    retries = 1,
    fallback = null,
    revalidate = 3600,
    label = url,
    throwOn5xx = false,
    extract,
  } = opts;

  const totalAttempts = retries + 1;

  for (let attempt = 1; attempt <= totalAttempts; attempt++) {
    const attemptLabel = attempt === 1 ? label : `${label}-retry-${attempt - 1}`;

    let resp: Response | null = null;
    try {
      resp = await safeFetch(url, {
        label: attemptLabel,
        timeout,
        throwOn5xx, // safeFetch agora verifica isBuildPhase() internamente
        next: { revalidate },
      });
    } catch (err) {
      // safeFetch lancou — ISR 5xx. Verifica Retry-After antes de propagar.
      if (err instanceof Error && throwOn5xx && !isBuildPhase()) {
        const retryAfter = extractRetryAfter(err.message);
        if (retryAfter !== null && attempt < totalAttempts) {
          // Retry-After presente e ainda ha tentativas: espera e retenta
          const waitMs = Math.min(retryAfter * 1000, 30000);
          console.warn(
            `[fetchWithBudget] ${label} 503 + Retry-After ${retryAfter}s, attempt ${attempt}/${totalAttempts}, waiting ${waitMs}ms`,
          );
          await new Promise((resolve) => setTimeout(resolve, waitMs));
          continue;
        }
        // Sem Retry-After ou ultima tentativa: propaga o erro para ISR preservar stale cache
        Sentry.addBreadcrumb({
          category: 'fetch',
          message: `fetchWithBudget rethrow ${label} attempt ${attempt}/${totalAttempts}`,
          level: 'error',
          data: { url, attempt, total_attempts: totalAttempts, error: err.message },
        });
        throw err;
      }
      // Build phase or error not from 5xx: log, continua retry
      Sentry.captureException(err, {
        tags: { fetch_label: attemptLabel, fetch_outcome: 'fetch_throw' },
        contexts: { fetch: { url } },
      });
    }

    if (resp !== null) {
      // PSEO-P1-2048: safeFetch pode retornar Response em 5xx durante build
      // (throwOn5xx=true + isBuildPhase()). Tratamos como falha de retry.
      if (!resp.ok && resp.status >= 500) {
        if (attempt < totalAttempts) {
          const backoffMs = 2000 * 2 ** (attempt - 1);
          await new Promise((resolve) => setTimeout(resolve, backoffMs));
          continue;
        }
        // Ultima tentativa: two-tier decision
        if (throwOn5xx && !isBuildPhase()) {
          throw new Error(`fetchWithBudget_5xx:${label}:${resp.status}`);
        }
        Sentry.captureMessage(`fetchWithBudget_5xx_fallback_${label}_${resp.status}`, {
          level: 'warning',
          tags: { fetch_label: label, fetch_outcome: '5xx_build_fallback' },
          contexts: { fetch: { url, status: resp.status, total_attempts: totalAttempts } },
        });
        return fallback;
      }

      // Success (2xx, 4xx treated as valid responses) — parse JSON
      try {
        const data = (await resp.json()) as unknown;
        return extract ? extract(data) : (data as T);
      } catch (err) {
        // JSON parse error — treat as failure attempt.
        Sentry.captureException(err, {
          tags: { fetch_label: attemptLabel, fetch_outcome: 'parse_error' },
          contexts: { fetch: { url } },
        });
      }
    }

    if (attempt < totalAttempts) {
      // Exponential backoff: 2s, 4s, 8s, ...
      const backoffMs = 2000 * 2 ** (attempt - 1);
      await new Promise((resolve) => setTimeout(resolve, backoffMs));
    }
  }

  Sentry.captureMessage(`fetchWithBudget_exhausted_${label}`, {
    level: 'warning',
    tags: { fetch_label: label, fetch_outcome: 'budget_exhausted' },
    contexts: { fetch: { url, total_attempts: totalAttempts } },
  });
  return fallback;
}
