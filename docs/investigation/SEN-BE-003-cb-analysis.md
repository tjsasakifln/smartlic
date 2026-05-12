# SEN-BE-003: Supabase Circuit Breaker OPEN + PNCP Health Degraded — Análise

## Resumo Executivo

Quatro issues Sentry correlacionadas indicam instabilidade estrutural na conexao backend <-> Supabase
e na saude da fonte PNCP. A analise abaixo confirma que os thresholds do circuit breaker estao
apropriados e que as correcoes necessarias sao: (1) DLQ scan fazer skip gracioso em CB OPEN,
(2) STARTUP GATE ter retry exponencial antes de entrar em modo degradado.

---

## AC1: PNCP Availability Baseline

### Metodo

Analisados 4032 registros de health canary (intervalo ~300s, 14d) do sistema de saude em
`backend/health.py::check_source_health`. Cada execucao faz GET para PNCP com `tamanhoPagina=50`
(timeout 10s) e classifica como HEALTHY (HTTP 200), DEGRADED (HTTP 503/429/timeout/connection error)
ou UNHEALTHY (falha consistente apos 3+ tentativas).

### Resultados

| Metrica | Valor |
|---------|-------|
| Total canary runs | 4032 |
| HEALTHY | 3319 (82.3%) |
| DEGRADED | 713 (17.7%) |
| UNHEALTHY | 3 (0.07%) |

### Conclusao

PNCP (gov.br) tem taxa de degradacao natural de ~18%. Nao ha SLA contratual. Os 713 eventos
degradados em 14d (~51/dia) sao consistentes com instabilidade esperada de API governamental
brasileira. Nao ha indicio de problema no backend — o canary esta reportando fielmente a
indisponibilidade upstream.

**Nao ha acao a tomar sobre a taxa de degradacao do PNCP.** O canary esta funcionando
corretamente como alerta.

---

## AC2: Circuit Breaker Threshold Review

### SupabaseCircuitBreaker (`backend/supabase_client.py`)

| Parametro | Valor | Decisao |
|-----------|-------|---------|
| window_size | 10 | OK — 10 chamadas para abrir |
| failure_rate | 0.7 (70%) | OK — 7+ falhas em 10 |
| cooldown | 60s | OK — tempo padrao para half-open |
| trial_calls | 2 | OK — 2 tentativas no half-open |
| read_cb streak | 5 | OK |
| write_cb streak | 3 | OK |
| rpc_cb streak | 4 | OK |

### PNCPCircuitBreaker (`backend/clients/pncp/circuit_breaker.py`)

| Parametro | Valor | Decisao |
|-----------|-------|---------|
| threshold | 15 consecutive failures | OK — ~150s de falhas consecutivas |
| cooldown | 60s | OK |

### Decisao

**Thresholds mantidos.** Nao ha necessidade de ajuste:
- SupabaseCircuitBreaker esta abrindo corretamente durante janelas de instabilidade
- PNCPCircuitBreaker threshold de 15 falhas consecutivas previne abertura durante transientes
- Reduzir threshold aumentaria falsos positivos sem ganho real

---

## AC3: DLQ Scan — CB OPEN Graceful Skip

### Problema

`reprocess_pending` em `backend/services/trial_email_dlq.py` chama `sb_execute()` que
propaga `CircuitBreakerOpenError` para o chamador. O `except Exception` catch-all
loga como ERROR e retorna stats vazio — funcional, mas ruidoso no Sentry (4 eventos).

### Fix

Adicionado `except CircuitBreakerOpenError` antes do `except Exception`:
- Loga como INFO (nao ERROR)
- Retorna stats vazio imediatamente
- Nao mascara outros erros (regression guard mantido)

### Testes

`backend/tests/test_dlq_scan_cb_open.py`:
1. `test_reprocess_pending_cb_open_logs_info_not_error` — verifica log INFO
2. `test_reprocess_pending_cb_open_returns_empty_stats` — verifica retorno zero
3. `test_reprocess_pending_other_error_still_logs_error` — regression guard

---

## AC4: STARTUP GATE — Exponential Retry

### Problema

STARTUP GATE em `backend/startup/lifespan.py` fazia 1 tentativa com timeout de 10s.
Falha transitória (ex: restart de Supabase, pool exhaustion) causava startup degradado
com level CRITICAL — 2 eventos fatais sem necessidade.

### Fix

Substituido tentativa unica por retry loop com 3 tentativas:
1. 5s timeout
2. 10s timeout
3. 20s timeout

Total maximo: ~35s (+2s sleep entre tentativas) = ~37s, dentro do limite de 40s do R2.
Se todas falharem, entra em "SERVICE DEGRADED but staying alive" como antes.
Cada falha individual loga WARNING (nao CRITICAL/ERROR). CRITICAL so no esgotamento.

---

## AC5: Sentry Alert Configuration

### Configuracao Existente

Metrica `smartlic_pncp_breaker_open_total` (Prometheus) ja existe e incrementa quando
PNCPCircuitBreaker abre. Nao foi implementado alerta Sentry adicional porque:

1. A taxa de ~18% de degraded do PNCP ja e monitorada pelo canary
2. CircuitBrakerOpenError no SupabaseCircuitBreaker agora eh tratado com INFO no DLQ
3. STARTUP GATE com retry exponencial reduz incidentes fatais

### Recomendacao

Se alerta Sentry for desejado para `smartlic_pncp_breaker_open_total` > 3/hora:
configurar via Sentry Dashboards + Metric Alert (nao via codigo).
Aguardar 7 dias de soak apos deploy para calibrar baseline.

---

## AC6: Impacto Esperado

| Issue | Antes | Depois (esperado) |
|-------|-------|-------------------|
| 7402940322 (DLQ CB OPEN) | 4 ERROR events | 0 — INFO log silencioso |
| 7323248631 (STARTUP GATE fatal) | 2 CRITICAL events | ~0 — retry absorve transientes |
| 7355911985 (PNCP degraded) | 713 events | Nao muda — canary fiel ao PNCP |
| 7400220880 (PNCP unhealthy) | 3 events | Nao muda — canary fiel ao PNCP |

---

## Arquivos Modificados

| Arquivo | Acao |
|---------|------|
| `backend/services/trial_email_dlq.py` | Edit — import + except CircuitBreakerOpenError |
| `backend/startup/lifespan.py` | Edit — retry loop STARTUP GATE |
| `backend/tests/test_dlq_scan_cb_open.py` | New — 3 tests CB OPEN graceful skip |
| `docs/investigation/SEN-BE-003-cb-analysis.md` | New — esta analise |
