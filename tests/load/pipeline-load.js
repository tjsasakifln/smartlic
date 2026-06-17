/**
 * Issue #1968: k6 load test — cenário 3: 20 usuários simultâneos em /v1/pipeline
 *
 * Profile:
 *   - Ramp-up   : 1 min (2 -> 20 VUs)
 *   - Sustain   : 3 min at 20 VUs
 *   - Ramp-down : 30 s (20 -> 0 VUs)
 *
 * Operações:
 *   - POST /v1/pipeline  (criar item no pipeline) — ~60% das requisições
 *   - PATCH /v1/pipeline/{id} (atualizar status) — ~40% das requisições
 *
 * Cada VU mantém seu próprio conjunto de IDs criados, evitando contenção.
 *
 * Thresholds:
 *   - http_req_duration p(95) < 2000 ms
 *   - http_req_failed   rate  < 5%
 *
 * Auth: JWTs loaded from tests/load/fixtures/jwts.json.
 *
 * Run local:
 *   k6 run tests/load/pipeline-load.js \
 *     --env BACKEND_URL=https://smartlic-backend-staging.up.railway.app
 *
 * Smoke:
 *   k6 run tests/load/pipeline-load.js --env SMOKE=1 --vus 1 --duration 10s
 *
 * CI:
 *   k6 run tests/load/pipeline-load.js \
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
// Note: pipeline_create_latency and pipeline_update_latency are separate Trends
// for CREATE vs UPDATE breakdown; k6 computes percentiles automatically.
const pipelineErrors = new Rate('pipeline_errors');
const pipelineLatency = new Trend('pipeline_latency_ms', true);
const pipelineCreateLatency = new Trend('pipeline_create_latency_ms', true);
const pipelineUpdateLatency = new Trend('pipeline_update_latency_ms', true);

// ---------------------------------------------------------------------------
// JWT fixture loading
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

// Statuses for PATCH updates
const STATUSES = [
  'em_andamento',
  'analise_viabilidade',
  'proposta_enviada',
  'vencido',
  'ganho',
];

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

export const options = SMOKE
  ? {
      vus: 1,
      duration: '10s',
      thresholds: {
        http_req_failed: ['rate<0.5'],
      },
    }
  : {
      scenarios: {
        pipeline: {
          executor: 'ramping-vus',
          startVUs: 2,
          stages: [
            { target: 20, duration: '1m' },   // ramp-up: 2 -> 20 VUs
            { target: 20, duration: '3m' },   // sustain: 20 VUs
            { target: 0, duration: '30s' },   // ramp-down
          ],
          gracefulRampDown: '30s',
        },
      },
      thresholds: {
        http_req_duration: ['p(95)<2000'],
        http_req_failed: ['rate<0.05'],
        pipeline_errors: ['rate<0.05'],
      },
    };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function recentDateRange() {
  const today = new Date();
  const end = today.toISOString().slice(0, 10);
  const start = new Date(today.getTime() - 10 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  return { data_inicial: start, data_final: end };
}

function pickToken() {
  const token = jwts[Math.floor(Math.random() * jwts.length)];
  if (__ENV.AUTH_TOKEN) return __ENV.AUTH_TOKEN;
  return token;
}

// Per-VU storage for created pipeline IDs (each VU has its own list)
// This avoids cross-VU race conditions on PATCH operations.
const createdIds = [];

// ---------------------------------------------------------------------------
// Default VU function
// ---------------------------------------------------------------------------

export default function () {
  const token = pickToken();
  const baseHeaders = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };

  // Decide operation: 60% CREATE, 40% UPDATE (only if we have IDs)
  const shouldPatch = createdIds.length > 0 && Math.random() < 0.4;

  if (shouldPatch) {
    // ---- PATCH: update pipeline item status ----
    const id = createdIds[Math.floor(Math.random() * createdIds.length)];
    const status = STATUSES[Math.floor(Math.random() * STATUSES.length)];
    const url = `${BACKEND_URL}/v1/pipeline/${id}`;
    const payload = JSON.stringify({ status });

    const patchParams = {
      headers: baseHeaders,
      tags: { endpoint: 'pipeline_update', testid: __ENV.TEST_ID || 'local' },
      timeout: '10s',
    };

    const start = Date.now();
    const res = http.patch(url, payload, patchParams);
    const elapsed = Date.now() - start;

    pipelineUpdateLatency.add(elapsed);
    pipelineLatency.add(elapsed);

    const ok = check(res, {
      'PATCH pipeline status is 200': (r) => r.status === 200,
      'PATCH pipeline has body': (r) => r.body && r.body.length > 0,
    });

    pipelineErrors.add(!ok);
  } else {
    // ---- POST: create pipeline item ----
    // First do a quick search to find a real bid ID for the pipeline item.
    // This makes the test more realistic — users add actual bids to their pipeline.
    const { data_inicial, data_final } = recentDateRange();
    const searchPayload = JSON.stringify({
      ufs: ['SP'],
      data_inicial,
      data_final,
      setor_id: 'construcao_civil',
      modo_busca: 'abertas',
      pagina: 1,
      itens_por_pagina: 5,
    });

    const searchRes = http.post(`${BACKEND_URL}/buscar`, searchPayload, {
      headers: baseHeaders,
      timeout: '15s',
    });

    if (searchRes.status !== 200 && searchRes.status !== 202) {
      // Search failure is not a pipeline error — fall through to fallback creation below
      // (bidId stays null, which triggers the fallback path)
    }

    // Extract a bid ID from search results
    let bidId = null;
    try {
      const body = JSON.parse(searchRes.body);
      const items = body.resultados || body.itens || body.data || body.items || [];
      if (items.length > 0) {
        bidId = items[0].id || items[0].licitacao_id || items[0].processo_id || items[0].external_id;
      }
    } catch (e) {
      // JSON parse errors are acceptable under load
    }

    let pipelineUrl;
    let payload;

    if (bidId) {
      // Real bid found — add to pipeline
      pipelineUrl = `${BACKEND_URL}/v1/pipeline`;
      payload = JSON.stringify({
        licitacao_id: bidId,
        status: 'em_andamento',
        observacoes: 'Adicionado por load test k6',
      });
    } else {
      // Fallback: create pipeline item with explicit data
      pipelineUrl = `${BACKEND_URL}/v1/pipeline`;
      payload = JSON.stringify({
        titulo: `Pipeline Load Test VU ${__VU} - ${Date.now()}`,
        orgao: 'Orgao Teste',
        uf: 'SP',
        setor: 'construcao_civil',
        status: 'em_andamento',
        observacoes: 'Criado por load test k6',
      });
    }

    const postParams = {
      headers: baseHeaders,
      tags: { endpoint: 'pipeline_create', testid: __ENV.TEST_ID || 'local' },
      timeout: '10s',
    };

    const start = Date.now();
    const res = http.post(pipelineUrl, payload, postParams);
    const elapsed = Date.now() - start;

    pipelineCreateLatency.add(elapsed);
    pipelineLatency.add(elapsed);

    const ok = check(res, {
      'POST pipeline status is 200 or 201': (r) => r.status === 200 || r.status === 201,
      'POST pipeline has body': (r) => r.body && r.body.length > 0,
    });

    pipelineErrors.add(!ok);

    // Store the created ID for future PATCH operations
    if (ok) {
      try {
        const body = JSON.parse(res.body);
        const newId = body.id || body.pipeline_id;
        if (newId) {
          createdIds.push(newId);
          // Keep the list bounded to avoid unbounded growth
          if (createdIds.length > 50) {
            createdIds.shift();
          }
        }
      } catch (e) {
        // ignore parse errors
      }
    }
  }

  if (SMOKE) {
    sleep(1);
  }
}
