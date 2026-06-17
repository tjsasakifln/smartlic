/**
 * Issue #1968: k6 load test — cenário 1: 50 usuários simultâneos em /buscar
 *
 * Profile:
 *   - Ramp-up   : 2 min (5 -> 50 VUs)
 *   - Sustain   : 5 min at 50 VUs
 *   - Ramp-down : 30 s (50 -> 0 VUs)
 *
 * Thresholds:
 *   - http_req_duration p(95) < 3000 ms
 *   - http_req_failed   rate  < 2%
 *
 * Auth: JWTs loaded from tests/load/fixtures/jwts.json (path overridable
 *       via JWTS_PATH env var).
 *
 * Run local:
 *   k6 run tests/load/search-load.js \
 *     --env BACKEND_URL=https://smartlic-backend-staging.up.railway.app
 *
 * Smoke:
 *   k6 run tests/load/search-load.js --env SMOKE=1 --vus 1 --duration 10s
 *
 * CI:
 *   k6 run tests/load/search-load.js \
 *     --env BACKEND_URL=https://smartlic-backend-staging.up.railway.app \
 *     --tag testid=$(date +%F)
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Rate, Trend } from 'k6/metrics';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const BACKEND_URL = __ENV.BACKEND_URL || __ENV.BASE_URL || 'http://localhost:8000';
const JWTS_PATH = __ENV.JWTS_PATH || './fixtures/jwts.json';
const SMOKE = __ENV.SMOKE === '1' || __ENV.SMOKE === 'true';

// Custom metrics
// Note: k6 automatically computes all percentiles (p50/p90/p95/p99) from a single Trend metric.
const searchErrors = new Rate('search_errors');
const searchLatency = new Trend('search_latency_ms', true);

// ---------------------------------------------------------------------------
// JWT fixture loading (SharedArray keeps it out of per-VU memory)
// ---------------------------------------------------------------------------

const jwts = new SharedArray('jwts', function () {
  try {
    // eslint-disable-next-line no-undef
    const raw = open(JWTS_PATH);
    const parsed = JSON.parse(raw);
    const tokens = Array.isArray(parsed.tokens) ? parsed.tokens : [];
    if (tokens.length === 0) {
      throw new Error('no tokens in fixture');
    }
    return tokens;
  } catch (err) {
    if (!SMOKE) {
      throw new Error(
        `Failed to load JWTs from ${JWTS_PATH}: ${err.message}. ` +
          `See tests/load/README.md for how to generate the fixture.`
      );
    }
    return ['smoke-placeholder-jwt'];
  }
});

// Search payload variants to diversify the load
const SEARCH_PAYLOADS = [
  { ufs: ['SP', 'RJ'],           setor_id: 'construcao_civil',           modo_busca: 'abertas', pagina: 1, itens_por_pagina: 20 },
  { ufs: ['MG'],                 setor_id: 'tecnologia_da_informacao',   modo_busca: 'abertas', pagina: 1, itens_por_pagina: 20 },
  { ufs: ['SP', 'MG', 'RJ'],     setor_id: 'saude',                      modo_busca: 'todas',   pagina: 1, itens_por_pagina: 20 },
  { ufs: ['SP'],                 setor_id: 'educacao',                   modo_busca: 'abertas', pagina: 1, itens_por_pagina: 10 },
  { ufs: ['RS', 'SC', 'PR'],     setor_id: 'limpeza_e_conservacao',      modo_busca: 'todas',   pagina: 2, itens_por_pagina: 20 },
  { ufs: ['BA', 'PE'],           setor_id: 'saude',                      modo_busca: 'abertas', pagina: 1, itens_por_pagina: 20 },
  { ufs: ['SP', 'RJ', 'MG', 'RS'], setor_id: 'vigilancia_e_seguranca',  modo_busca: 'todas',   pagina: 1, itens_por_pagina: 10 },
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
        search: {
          executor: 'ramping-vus',
          startVUs: 5,
          stages: [
            { target: 50, duration: '2m' },   // ramp-up: 5 -> 50 VUs
            { target: 50, duration: '5m' },   // sustain: 50 VUs
            { target: 0, duration: '30s' },   // ramp-down
          ],
          gracefulRampDown: '30s',
        },
      },
      thresholds: {
        http_req_duration: ['p(95)<3000'],
        http_req_failed: ['rate<0.02'],
        search_errors: ['rate<0.02'],
      },
    };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Returns a 10-day window ending today in YYYY-MM-DD (UTC-safe).
 */
function recentDateRange() {
  const today = new Date();
  const end = today.toISOString().slice(0, 10);
  const start = new Date(today.getTime() - 10 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  return { data_inicial: start, data_final: end };
}

function buildPayload() {
  const base = SEARCH_PAYLOADS[Math.floor(Math.random() * SEARCH_PAYLOADS.length)];
  const { data_inicial, data_final } = recentDateRange();
  return JSON.stringify({ ...base, data_inicial, data_final });
}

function pickToken() {
  const token = jwts[Math.floor(Math.random() * jwts.length)];
  if (__ENV.AUTH_TOKEN) return __ENV.AUTH_TOKEN;
  return token;
}

// ---------------------------------------------------------------------------
// Default VU function
// ---------------------------------------------------------------------------

export default function () {
  const token = pickToken();
  const payload = buildPayload();
  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    tags: { endpoint: 'search', testid: __ENV.TEST_ID || 'local' },
    timeout: '30s',
  };

  const res = http.post(`${BACKEND_URL}/buscar`, payload, params);

  searchLatency.add(res.timings.duration);

  const ok = check(res, {
    'status is 200 or 202': (r) => r.status === 200 || r.status === 202,
    'has response body': (r) => r.body && r.body.length > 0,
  });

  searchErrors.add(!ok);

  if (SMOKE) {
    sleep(1);
  }
}
