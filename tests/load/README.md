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
| `k6-search-load.js` | Load test progressivo | ~17 min | 500 |
| `k6-stress-test.js` | Stress test + breaking point | ~36 min | 500 |

## 3. Como Executar

### 3.1 Load Test (Staging)

```bash
k6 run tests/load/k6-search-load.js
BASE_URL=https://localhost:8000 k6 run tests/load/k6-search-load.js
```

### 3.2 Stress Test (Staging)

```bash
k6 run tests/load/k6-stress-test.js
```

### 3.3 Modo CI (Leve)

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

Workflow `.github/workflows/load-test-weekly.yml`:
- Domingo 03:00 UTC
- 10 VUs, 2 minutos
- Target: staging
- Falha se p95 > 3s ou error rate > 10%

## 8. Referências

- [k6 Docs](https://k6.io/docs/)
- [Load Testing Plan](../docs/performance/load-testing-plan.md)

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
