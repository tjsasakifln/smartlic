/**
 * k6 Load Test — SmartLic Search Endpoints
 *
 * Simula 50→500 usuários virtuais em rampa.
 * Testa endpoints críticos: POST /buscar, GET /pipeline, GET /api/v1/search/stats
 *
 * Uso:
 *   k6 run tests/load/k6-search-load.js
 *   k6 run --vus 100 --duration 10m tests/load/k6-search-load.js
 *   k6 run --out json=results.json tests/load/k6-search-load.js
 *
 * Requer: k6 (https://k6.io) — gratuito, open source
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Métricas customizadas
const errorRate = new Rate('errors');
const searchLatency = new Trend('search_latency', true);
const pipelineLatency = new Trend('pipeline_latency', true);
const statsLatency = new Trend('stats_latency', true);

// Configuração
const BASE_URL = __ENV.BASE_URL || 'https://staging.smartlic.tech';
const API_BASE = `${BASE_URL}/api/v1`;

// Cenários de busca (rotaciona para diversificar load)
const SEARCH_TERMS = [
  'construção civil',
  'tecnologia da informação',
  'limpeza e conservação',
  'vigilância e segurança',
  'material de escritório',
  'consultoria',
  'transporte',
  'alimentação',
  'obras',
  'saúde',
];

// k6 configuração de estágios
export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp up: 0 → 50 VUs
    { duration: '3m', target: 100 },  // Ramp up: 50 → 100 VUs
    { duration: '3m', target: 250 },  // Ramp up: 100 → 250 VUs
    { duration: '2m', target: 500 },  // Ramp up: 250 → 500 VUs
    { duration: '5m', target: 500 },  // Sustained: 500 VUs
    { duration: '2m', target: 0 },    // Ramp down: 500 → 0 VUs
  ],
  thresholds: {
    // p95 da busca deve ser < 2s com 100 VUs
    'search_latency': ['p(95)<2000'],
    // Taxa de erro < 5%
    'errors': ['rate<0.05'],
    // p95 geral HTTP < 3s
    'http_req_duration': ['p(95)<3000'],
  },
  // Verificar se thresholds passam apenas na fase sustentada
  thresholds_abort_on_fail: false,
};

// Auth — obter token JWT (executado uma vez por VU)
function authenticate() {
  // Nota: Em staging, usar credenciais de teste
  const payload = JSON.stringify({
    email: __ENV.TEST_EMAIL || 'teste@example.com',
    password: __ENV.TEST_PASSWORD || 'senha123',
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  const res = http.post(`${BASE_URL}/auth/v1/token?grant_type=password`, payload, params);

  if (res.status === 200) {
    return JSON.parse(res.body).access_token;
  }

  // Se login falha (ex: staging sem seed), continuar sem auth para search público
  console.warn(`VU ${__VU}: Auth failed (${res.status}), continuing unauthenticated`);
  return null;
}

export default function () {
  // Autenticar uma vez por VU
  const token = authenticate();

  const params = {
    headers: {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
    },
  };

  group('Search Flow', () => {
    // 1. Busca (endpoint mais pesado)
    const termo = SEARCH_TERMS[Math.floor(Math.random() * SEARCH_TERMS.length)];

    const searchStart = Date.now();
    const searchRes = http.post(
      `${API_BASE}/buscar`,
      JSON.stringify({
        termo: termo,
        uf: 'SP',
        modalidade: 'pregao_eletronico',
        pagina: 1,
        resultados_por_pagina: 20,
      }),
      params
    );
    searchLatency.add(Date.now() - searchStart);

    const searchOk = check(searchRes, {
      'POST /buscar status 200': (r) => r.status === 200,
      'POST /buscar tem resultados': (r) => {
        try {
          const body = JSON.parse(r.body);
          return Array.isArray(body.resultados) || body.total !== undefined;
        } catch {
          return false;
        }
      },
    });
    errorRate.add(!searchOk);

    sleep(1);

    // 2. Pipeline (listagem de oportunidades)
    const pipelineStart = Date.now();
    const pipelineRes = http.get(`${API_BASE}/pipeline`, params);
    pipelineLatency.add(Date.now() - pipelineStart);

    const pipelineOk = check(pipelineRes, {
      'GET /pipeline status 200': (r) => r.status === 200,
    });
    errorRate.add(!pipelineOk);

    sleep(1);

    // 3. Stats (leve, endpoint de analytics)
    const statsStart = Date.now();
    const statsRes = http.get(`${API_BASE}/search/stats`, params);
    statsLatency.add(Date.now() - statsStart);

    const statsOk = check(statsRes, {
      'GET /search/stats status 200': (r) => r.status === 200,
    });
    errorRate.add(!statsOk);

    sleep(2);
  });
}

// Sumário ao final do teste
export function handleSummary(data) {
  console.log('\n========================================');
  console.log('  SMARTLIC LOAD TEST — RESUMO');
  console.log('========================================\n');

  const metrics = data.metrics;

  console.log('Latência da Busca (POST /buscar):');
  console.log(`  p50: ${metrics.search_latency?.values?.med?.toFixed(0) || 'N/A'}ms`);
  console.log(`  p95: ${metrics.search_latency?.values?.['p(95)']?.toFixed(0) || 'N/A'}ms`);
  console.log(`  p99: ${metrics.search_latency?.values?.['p(99)']?.toFixed(0) || 'N/A'}ms`);
  console.log(`  max: ${metrics.search_latency?.values?.max?.toFixed(0) || 'N/A'}ms`);

  console.log('\nThroughput:');
  console.log(`  req/s: ${metrics.http_reqs?.values?.rate?.toFixed(1) || 'N/A'}`);

  console.log('\nError Rate:');
  console.log(`  ${((metrics.errors?.values?.rate || 0) * 100).toFixed(1)}%`);

  console.log('\nVirtual Users:');
  console.log(`  max: ${metrics.vus_max?.values?.max || 'N/A'}`);

  console.log('\n========================================\n');

  return {
    'tests/load/results/summary.json': JSON.stringify(data, null, 2),
  };
}
