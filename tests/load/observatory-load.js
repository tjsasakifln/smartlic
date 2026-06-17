/**
 * Issue #1968: k6 load test — cenário 2: 500 usuários simultâneos em /observatorio/[slug]
 *
 * Testa páginas ISR (Incremental Static Regeneration) do observatório setorial.
 * O objetivo é validar a eficácia do cache: ISR deve servir páginas em <500ms
 * após o primeiro hit, mesmo sob 500 VUs concorrentes.
 *
 * Profile:
 *   - Ramp-up   : 2 min (50 -> 500 VUs)
 *   - Sustain   : 5 min at 500 VUs
 *   - Ramp-down : 30 s (500 -> 0 VUs)
 *
 * Thresholds:
 *   - http_req_duration p(95) < 2000 ms
 *   - http_req_failed   rate  < 5%
 *
 * Run local:
 *   k6 run tests/load/observatory-load.js \
 *     --env FRONTEND_URL=http://localhost:3000
 *
 * Smoke:
 *   k6 run tests/load/observatory-load.js --env SMOKE=1 --vus 1 --duration 10s
 *
 * CI:
 *   k6 run tests/load/observatory-load.js \
 *     --env FRONTEND_URL=https://smartlic.tech \
 *     --tag testid=$(date +%F)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const FRONTEND_URL = __ENV.FRONTEND_URL || __ENV.BASE_URL || 'http://localhost:3000';
const SMOKE = __ENV.SMOKE === '1' || __ENV.SMOKE === 'true';

// Custom metrics
// Note: k6 automatically computes all percentiles (p50/p90/p95/p99) from a single Trend metric.
const obsErrors = new Rate('obs_errors');
const obsLatency = new Trend('obs_latency_ms', true);
const obsCacheHit = new Rate('obs_cache_hit');

/**
 * Lista de slugs do observatório setorial.
 * Cada slug corresponde a uma página ISR: /observatorio/{slug}
 * A diversidade de slugs garante que o teste não acerte apenas uma página em cache.
 */
const SLUGS = [
  'construcao-civil',
  'tecnologia-da-informacao',
  'saude',
  'educacao',
  'limpeza-e-conservacao',
  'vigilancia-e-seguranca',
  'transporte',
  'alimentacao',
  'obras',
  'consultoria',
  'energia',
  'meio-ambiente',
  'seguros',
  'comunicacao',
  'servicos-financeiros',
  'seguranca-do-trabalho',
  'juridico',
  'engenharia',
  'logistica',
  'publicidade',
];

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

export const options = SMOKE
  ? {
      vus: 1,
      duration: '10s',
      thresholds: {
        http_req_failed: ['rate<0.5'], // smoke is permissive
      },
    }
  : {
      scenarios: {
        observatory: {
          executor: 'ramping-vus',
          startVUs: 50,
          stages: [
            { target: 500, duration: '2m' },   // ramp-up: 50 -> 500 VUs
            { target: 500, duration: '5m' },   // sustain: 500 VUs
            { target: 0, duration: '30s' },    // ramp-down
          ],
          gracefulRampDown: '30s',
        },
      },
      thresholds: {
        http_req_duration: ['p(95)<2000'],
        http_req_failed: ['rate<0.05'],
        obs_errors: ['rate<0.05'],
      },
    };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pickSlug() {
  return SLUGS[Math.floor(Math.random() * SLUGS.length)];
}

// ---------------------------------------------------------------------------
// Default VU function
// ---------------------------------------------------------------------------

export default function () {
  const slug = pickSlug();
  const url = `${FRONTEND_URL}/observatorio/${slug}`;
  const params = {
    headers: {
      'Cache-Control': 'no-cache',
    },
    tags: { endpoint: 'observatorio', slug: slug, testid: __ENV.TEST_ID || 'local' },
    timeout: '15s',
  };

  const res = http.get(url, params);

  obsLatency.add(res.timings.duration);

  // Heuristic for cache hit detection
  // Next.js ISR returns X-Cache or x-cache header (e.g. "HIT", "MISS", "STALE")
  const cacheHeader = (res.headers['X-Cache'] || res.headers['x-cache'] || '').toLowerCase();
  obsCacheHit.add(cacheHeader.includes('hit') || cacheHeader.includes('stale'));

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'has html body': (r) => r.body && r.body.length > 1000,
    'response time < 5s': (r) => r.timings.duration < 5000,
  });

  obsErrors.add(!ok);

  if (SMOKE) {
    sleep(1);
  }
}
