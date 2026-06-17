# Load Test Report — SmartLic (2026-06)

**Issue:** [#1968](https://github.com/tjsasakifln/SmartLic/issues/1968)
**Ferramenta:** [k6](https://k6.io) (Grafana) — gratuito, open source
**Scripts:** `tests/load/{search-load,observatory-load,pipeline-load,spike-test}.js`

---

## 1. Resumo dos Cenários

| # | Cenário | VUs | Ramp-up | Sustain | Endpoint | Prioridade |
|:-:|---------|:---:|:-------:|:-------:|----------|:----------:|
| 1 | Carga típica de busca | 5 -> 50 | 2 min | 5 min | `POST /buscar` | Critica |
| 2 | ISR cache — observatorio | 50 -> 500 | 2 min | 5 min | `GET /observatorio/[slug]` | Alta |
| 3 | Pipeline CRUD | 2 -> 20 | 1 min | 3 min | `POST/PATCH /v1/pipeline` | Alta |
| 4 | Spike (pico repentino) | 10 -> 200 | 30 s | 1 min | `POST /buscar` | Media |

## 2. Thresholds

| Cenário | p95 | Error Rate | Notas |
|---------|:---:|:----------:|-------|
| Search | < 3000 ms | < 2% | Rampa suave, carga esperada |
| Observatory | < 2000 ms | < 5% | ISR deve servir rapido; 500 VUs testam cache |
| Pipeline | < 2000 ms | < 5% | CRUD operations, baixo volume |
| Spike | < 5000 ms | < 10% | Tolerancia maior devido a carga abrupta |

## 3. Resultados (preencher apos execucao)

### 3.1 Search Load

| Metrica | Valor | Threshold | Status |
|---------|:-----:|:---------:|:------:|
| p95 latencia | ___ ms | < 3000 ms | :---: |
| p99 latencia | ___ ms | — | :---: |
| Error rate | ___ % | < 2% | :---: |
| Throughput | ___ req/s | — | :---: |
| VUs maximo | 50 | — | :---: |

### 3.2 Observatory Load

| Metrica | Valor | Threshold | Status |
|---------|:-----:|:---------:|:------:|
| p95 latencia | ___ ms | < 2000 ms | :---: |
| p99 latencia | ___ ms | — | :---: |
| Error rate | ___ % | < 5% | :---: |
| Cache hit rate | ___ % | — | :---: |
| Throughput | ___ req/s | — | :---: |
| VUs maximo | 500 | — | :---: |

### 3.3 Pipeline Load

| Metrica | Valor | Threshold | Status |
|---------|:-----:|:---------:|:------:|
| p95 latencia (create) | ___ ms | < 2000 ms | :---: |
| p95 latencia (update) | ___ ms | < 2000 ms | :---: |
| Error rate | ___ % | < 5% | :---: |
| Throughput | ___ req/s | — | :---: |
| VUs maximo | 20 | — | :---: |

### 3.4 Spike Test

| Metrica | Valor | Threshold | Status |
|---------|:-----:|:---------:|:------:|
| p95 latencia | ___ ms | < 5000 ms | :---: |
| p99 latencia | ___ ms | — | :---: |
| Error rate | ___ % | < 10% | :---: |
| Throughput (pico) | ___ req/s | — | :---: |
| VUs maximo | 200 | — | :---: |
| Tempo de recuperacao | ___ s | — | :---: |

## 4. Metricas de Infraestrutura (Pico)

| Recurso | Valor | Notas |
|---------|:-----:|-------|
| CPU Railway (backend) | ___ % | Coletar do dashboard Railway |
| RAM Railway (backend) | ___ MB | Coletar do dashboard Railway |
| Conexoes DB (Supabase) | ___ | Coletar do dashboard Supabase |
| Redis hit rate | ___ % | Coletar do Redis INFO |
| Railway 120s timeout hits | ___ | Verificar logs de 503 |

## 5. Analise

### 5.1 Gargalos Identificados

- _(preencher apos execucao)_

### 5.2 Comportamento sob Carga

- _(preencher apos execucao)_

### 5.3 Memory Leak Check

Comparar p95 da fase inicial vs fase sustentada:
- Inicio: ___ ms
- Final: ___ ms
- Diferenca: ___ % (alerta se > 20%)

## 6. Recomendacoes

- [ ] _(preencher apos execucao)_

## 7. Historico de Execucoes

| Data | Run ID | Resultado | Observacoes |
|------|:------:|:---------:|-------------|
| ___ | ___ | ___ | ___ |

---

## Apendice A: Como Executar

```bash
# Todos os cenarios contra staging
k6 run tests/load/search-load.js --env BACKEND_URL=https://smartlic-backend-staging.up.railway.app
k6 run tests/load/observatory-load.js --env FRONTEND_URL=https://staging.smartlic.tech
k6 run tests/load/pipeline-load.js --env BACKEND_URL=https://smartlic-backend-staging.up.railway.app
k6 run tests/load/spike-test.js --env BACKEND_URL=https://smartlic-backend-staging.up.railway.app

# Smoke test (validacao rapida)
k6 run tests/load/search-load.js --env SMOKE=1 --vus 1 --duration 10s
```

## Apendice B: Configuracao

Ver `tests/load/config.json` para thresholds compartilhados e
`tests/load/fixtures/jwts.json.example` para template de fixture JWT.

---

_Ultima atualizacao: 2026-06-17_
