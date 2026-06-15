# Plano de Load & Stress Testing — SmartLic

**Issue:** [#1796](https://github.com/tjsasakifln/SmartLic/issues/1796)
**Prioridade:** P1
**Ferramenta:** k6 (Grafana) — gratuito, open source
**Data:** 2026-06-15

## 1. Objetivo

Determinar limites operacionais do SmartLic antes do lançamento v1.0, garantindo que o sistema suporte a carga esperada sem degradação.

## 2. Metodologia

### 2.1 Ferramenta: k6

**Por que k6:**
- Scripts em JavaScript (curva de aprendizado zero para devs JS/TS)
- Open source, sem limitação de VUs no plano gratuito
- Métricas detalhadas (p50/p95/p99, taxa de erro, throughput)
- Integração nativa com CI (GitHub Actions)
- Sem dependência de Java (diferente do JMeter)

### 2.2 Tipos de Teste

| Tipo | Script | Objetivo |
|------|--------|----------|
| **Load test** | `k6-search-load.js` | Comportamento sob carga esperada |
| **Stress test** | `k6-stress-test.js` | Encontrar breaking point |
| **Soak test** | `k6-stress-test.js` (sustained) | Detectar memory leaks |
| **CI smoke** | Modo leve (10 VUs, 2min) | Regressão semanal |

## 3. Endpoints Críticos

| Endpoint | Método | Peso no Teste | Prioridade |
|----------|--------|:---:|:---:|
| `/api/v1/buscar` | POST | 70% | 🔴 Crítica |
| `/api/v1/pipeline` | GET | 15% | 🟡 Alta |
| `/api/v1/search/stats` | GET | 15% | 🟢 Média |

## 4. Targets de Performance

| Métrica | Target | Condição |
|---------|:---:|---------|
| p95 latência (busca) | < 2s | 100 VUs simultâneos |
| p99 latência (busca) | < 5s | 100 VUs simultâneos |
| Error rate | < 1% | Carga normal (até 100 VUs) |
| Error rate | < 5% | Pico (até 500 VUs) |
| Throughput | > 50 req/s | 100 VUs |
| Memory | Estável | 30min de carga sustentada |
| Recuperação | < 2min | Após pico de stress |

## 5. Cenários de Teste

### 5.1 Cenário 1: Dia Típico

- 50 VUs (≈500 usuários ativos)
- Duração: 10 minutos
- Expectativa: p95 < 1s, erro rate < 1%

### 5.2 Cenário 2: Pico de Acesso

- 250 VUs (≈2,500 usuários ativos)
- Duração: 15 minutos
- Expectativa: p95 < 2s, erro rate < 3%

### 5.3 Cenário 3: Lançamento

- 500 VUs (≈5,000 usuários ativos)
- Duração: 10 minutos
- Expectativa: p95 < 3s, erro rate < 5%

### 5.4 Cenário 4: Memory Leak

- 250 VUs sustentados por 30 minutos
- Expectativa: p95 estável (não cresce > 50% ao longo do teste)

## 6. Procedimento de Teste

### 6.1 Preparação

1. Confirmar que staging está funcional
2. Verificar que banco staging tem dados de teste
3. Configurar alertas para não disparar com carga de teste
4. Avisar time no Slack #engineering

### 6.2 Execução

```bash
cd SmartLic
k6 run tests/load/k6-search-load.js
```

### 6.3 Análise

1. Coletar métricas do sumário do k6
2. Cruzar com métricas do Railway (CPU/RAM)
3. Cruzar com métricas do Supabase (conexões, query time)
4. Documentar limites encontrados

## 7. CI Semanal

Workflow `.github/workflows/load-test-weekly.yml`:

- **Quando:** Domingo 03:00 UTC
- **Modo:** Leve (10 VUs, 2 minutos)
- **Target:** Staging
- **Gate:** Falha se p95 > 3s ou error rate > 10%
- **Notificação:** Job summary no GitHub Actions

## 8. Relatório Template

```markdown
# Load Test Report — [DATA]

## Resumo
- Data: YYYY-MM-DD
- VUs máximos: N
- Duração: X min
- Throughput máximo: Y req/s
- Breaking point: Z VUs (error rate > 5%)

## Latência
| Métrica | Busca | Pipeline | Stats |
|---------|:-----:|:--------:|:-----:|
| p50 | Xms | Xms | Xms |
| p95 | Xms | Xms | Xms |
| p99 | Xms | Xms | Xms |

## Recursos (Pico)
- CPU Railway: X%
- RAM Railway: X MB
- Conexões DB: N
- Redis hit rate: X%

## Conclusão
- Sistema suporta X usuários simultâneos com p95 < 2s
- Breaking point: Y VUs
- Memory leak: Não detectado / Detectado (ver ação)
- Recomendações: [lista]

## Ações
- [ ] [Ação 1]
- [ ] [Ação 2]
```

## 9. Referências

- [k6 Documentation](https://k6.io/docs/)
- [k6 Scenarios](https://k6.io/docs/using-k6/scenarios/)
- [Railway Metrics](https://docs.railway.com/reference/metrics)

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
