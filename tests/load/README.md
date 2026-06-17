# Testes de Carga — SmartLic

**Ferramenta:** [k6](https://k6.io) (Grafana) — gratuito, open source, JavaScript

## 1. Instalação

```bash
# Linux (Debian/Ubuntu)
sudo apt-get install k6

# macOS
brew install k6

# Windows (Chocolatey)
choco install k6

# Ou via Docker
docker pull grafana/k6
```

## 2. Scripts Disponíveis

| Script | Objetivo | Duração | VUs Máx |
|--------|----------|:---:|:---:|
| `k6-search-load.js` | Load test progressivo (legado) | ~17 min | 500 |
| `k6-stress-test.js` | Stress test + breaking point (legado) | ~36 min | 500 |
| `buscar.k6.js` | Load test — POST /buscar com arrival-rate | ~5.5 min | 50 RPS |
| `dashboard.k6.js` | Load test — GET /analytics | ~5.5 min | 100 RPS |
| `sse.k6.js` | Load test — SSE /buscar-progress | 5 min | 50 conexões |
| `search-load.js` | Load test — POST /buscar (50 VUs, rampa 5→50) | ~7.5 min | 50 |
| `observatory-load.js` | Load test — ISR /observatorio/[slug] (500 VUs) | ~7.5 min | 500 |
| `pipeline-load.js` | Load test — POST/PATCH /v1/pipeline (20 VUs) | ~4.5 min | 20 |
| `spike-test.js` | Spike test — 10→200 VUs em 30s | ~2.5 min | 200 |

## 3. Como Executar

### 3.1 Scripts Legados

```bash
k6 run tests/load/k6-search-load.js
BASE_URL=https://localhost:8000 k6 run tests/load/k6-search-load.js
```

### 3.2 Scripts Modernos (JWT fixtures)

```bash
# Garanta que tests/load/fixtures/jwts.json existe (ver jwts.json.example)
k6 run tests/load/search-load.js --env BACKEND_URL=https://smartlic-backend-staging.up.railway.app
k6 run tests/load/pipeline-load.js --env BACKEND_URL=https://smartlic-backend-staging.up.railway.app
k6 run tests/load/spike-test.js --env BACKEND_URL=https://smartlic-backend-staging.up.railway.app

# Frontend ISR
k6 run tests/load/observatory-load.js --env FRONTEND_URL=https://staging.smartlic.tech
```

### 3.3 Smoke Test (Validação Rápida)

Todos os scripts modernos suportam modo SMOKE:

```bash
k6 run tests/load/search-load.js --env SMOKE=1 --vus 1 --duration 10s
k6 run tests/load/observatory-load.js --env SMOKE=1 --vus 1 --duration 10s
k6 run tests/load/pipeline-load.js --env SMOKE=1 --vus 1 --duration 10s
k6 run tests/load/spike-test.js --env SMOKE=1 --vus 1 --duration 10s
```

### 3.4 CI Tagging

```bash
k6 run tests/load/search-load.js --tag testid=$(date +%F)
```

### 3.5 Auth via AUTH_TOKEN (alternativa)

```bash
k6 run tests/load/search-load.js --env AUTH_TOKEN=<seu-jwt-aqui>
```

### 3.6 Modo CI (Leve)

```bash
k6 run --duration 2m --vus 10 tests/load/k6-search-load.js
```

## 4. Métricas Coletadas

| Métrica | Descrição | Target |
|---------|-----------|:---:|
| **p50 latency** | Mediana da latência | < 500ms |
| **p95 latency** | 95º percentil | < 2s (busca com 100 VUs) |
| **p99 latency** | 99º percentil | < 5s |
| **Throughput** | Requisições/segundo | > 50 req/s |
| **Error Rate** | % de respostas não-200 | < 5% |

## 5. Sinais de Problema

| Sintoma | Possível Causa |
|---------|---------------|
| p95 > 2s com 100 VUs | Bottleneck no banco ou Redis |
| Erro rate > 5% com < 200 VUs | Rate limit ou timeout |
| p95 cresce ao longo do teste | Memory leak |
| Erro 502/503 | Worker saturado |
| Erro 504 | Timeout upstream (OpenAI, PNCP) |

## 6. Capacity Planning

| VUs | Usuários Simultâneos | Interpretação |
|:---:|:---:|---|
| 50 | ~500 ativos | Carga leve |
| 100 | ~1,000 ativos | Carga moderada |
| 250 | ~2,500 ativos | Carga alta |
| 500 | ~5,000 ativos | Pico de uso |

*Estimativa: 1 VU ≈ 10 usuários reais (com think time)*

## 7. CI Semanal

### Workflow Legado

`.github/workflows/load-test-weekly.yml`:
- Domingo 03:00 UTC
- 10 VUs, 2 minutos
- Target: staging
- Falha se p95 > 3s ou error rate > 10%

### Workflow Issue #1968

`.github/workflows/load-test-schedule.yml`:
- Sabado 06:00 UTC
- Todos os 4 cenários (search, observatory, pipeline, spike)
- Non-blocking (thresholds breached são informativos, não bloqueiam)
- Resultados exportados como artifact (30 dias de retencao)

## 8. Referências

- [k6 Docs](https://k6.io/docs/)
- [Load Testing Plan](../docs/performance/load-testing-plan.md)

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
