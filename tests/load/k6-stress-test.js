/**
 * k6 Stress Test — SmartLic Breaking Point
 *
 * Encontra ponto de saturação do backend aumentando VUs progressivamente.
 * Sustenta carga por 30 minutos para detectar memory leaks.
 *
 * Uso:
 *   k6 run tests/load/k6-stress-test.js
 *   k6 run --vus 100 --duration 30m tests/load/k6-stress-test.js
 *
 * Objetivo: Encontrar VUs máximos antes de error rate > 5%
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const searchLatency = new Trend('stress_search_latency', true);

const BASE_URL = __ENV.BASE_URL || 'https://staging.smartlic.tech';
const API_BASE = `${BASE_URL}/api/v1`;

const SEARCH_TERMS = [
  'construção civil', 'tecnologia da informação', 'limpeza',
  'vigilância', 'material de escritório', 'consultoria',
  'transporte', 'alimentação', 'obras', 'saúde',
];

export const options = {
  stages: [
    // Fase 1: Aquecimento
    { duration: '2m', target: 10 },

    // Fase 2: Carga moderada
    { duration: '3m', target: 50 },

    // Fase 3: Carga alta
    { duration: '5m', target: 100 },

    // Fase 4: Carga muito alta
    { duration: '5m', target: 250 },

    // Fase 5: Stress máximo
    { duration: '5m', target: 500 },

    // Fase 6: Sustentação prolongada (detecta memory leaks)
    { duration: '10m', target: 250 },

    // Fase 7: Recuperação
    { duration: '3m', target: 50 },
    { duration: '2m', target: 10 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    'errors': ['rate<0.10'],          // Até 10% tolerado em stress
    'http_req_duration': ['p(99)<5000'], // p99 < 5s mesmo sob stress
  },
  thresholds_abort_on_fail: true,
};

export default function () {
  const termo = SEARCH_TERMS[Math.floor(Math.random() * SEARCH_TERMS.length)];

  const params = {
    headers: { 'Content-Type': 'application/json' },
    timeout: '30s',
  };

  // Intercalar busca pesada e leve
  if (Math.random() < 0.7) {
    // 70%: Busca (pesada)
    const start = Date.now();
    const res = http.post(
      `${API_BASE}/buscar`,
      JSON.stringify({
        termo: termo,
        uf: 'SP',
        pagina: 1,
        resultados_por_pagina: 20,
      }),
      params
    );
    searchLatency.add(Date.now() - start);

    check(res, {
      'buscar status 200': (r) => r.status === 200,
    }) || errorRate.add(1);

    sleep(1);
  } else if (Math.random() < 0.5) {
    // 15%: Stats (leve)
    const res = http.get(`${API_BASE}/search/stats`, params);
    check(res, { 'stats status 200': (r) => r.status === 200 }) || errorRate.add(1);
    sleep(0.5);
  } else {
    // 15%: Pipeline (média)
    const res = http.get(`${API_BASE}/pipeline`, params);
    check(res, { 'pipeline status 200': (r) => r.status === 200 }) || errorRate.add(1);
    sleep(1);
  }
}

export function handleSummary(data) {
  const m = data.metrics;

  console.log('\n========================================');
  console.log('  SMARTLIC STRESS TEST — BREAKING POINT');
  console.log('========================================\n');

  console.log('Latência (POST /buscar):');
  console.log(`  p50: ${m.stress_search_latency?.values?.med?.toFixed(0) || 'N/A'}ms`);
  console.log(`  p95: ${m.stress_search_latency?.values?.['p(95)']?.toFixed(0) || 'N/A'}ms`);
  console.log(`  p99: ${m.stress_search_latency?.values?.['p(99)']?.toFixed(0) || 'N/A'}ms`);

  console.log('\nThroughput máximo:');
  console.log(`  req/s: ${m.http_reqs?.values?.rate?.toFixed(1) || 'N/A'}`);

  console.log('\nConcorrência máxima:');
  console.log(`  VUs: ${m.vus_max?.values?.max || 'N/A'}`);

  console.log('\nError Rate final:');
  console.log(`  ${((m.errors?.values?.rate || 0) * 100).toFixed(1)}%`);

  console.log('\nDuração total:');
  console.log(`  ${((data.state?.testRunDurationMs || 0) / 1000 / 60).toFixed(1)} min`);

  // Memory leak check: se p95 cresce >50% na fase sustentada vs inicial
  console.log('\nMemory Leak Check:');
  console.log('  Comparar p95 fase inicial vs fase sustentada.');
  console.log('  Se p95 cresce >50%: possível memory leak.');

  console.log('\n========================================\n');

  return {
    'tests/load/results/stress-summary.json': JSON.stringify(data, null, 2),
  };
}
