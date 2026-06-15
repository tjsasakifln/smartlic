# Politica de Rate Limiting

## Visao Geral

O SmartLic implementa rate limiting em **3 camadas** para proteger APIs internas contra abuso, garantir fairness entre usuarios e evitar sobrecarga de fontes externas (PNCP, PCP, ComprasGov).

As camadas sao independentes e cumulativas:

1. **FlexibleRateLimiter** — FastAPI dependency para endpoints (per-user/per-IP, redis + in-memory fallback)
2. **RedisRateLimiter** — Token bucket compartilhado entre workers para requisicoes a fontes externas (PNCP/PCP)
3. **Tiered Rate Limiter** — Isolamento bot vs humano com buckets Redis separados

---

## Camada 1: FlexibleRateLimiter (Endpoints)

### Tipo

**Janela fixa com window-bucketing.** Requisicoes sao agrupadas em janelas de tempo fixas (ex: 60s, 300s). Cada bucket conta requisicoes + timestamp de criacao.

### Implementacao

```
backend/rate_limiter.py -> FlexibleRateLimiter
```

- Redis: `INCR` + `EXPIRE` (atomico, distribuido entre workers)
- Fallback: dict em memoria com LRU eviction (ate 10.000 entradas)
- Cleanup proativo: a cada 60s remove entradas expiradas

### Configuracoes Default

| Config | Env Var | Default | Uso |
|--------|---------|---------|-----|
| Busca endpoints | `SEARCH_RATE_LIMIT_PER_MINUTE` | 10 req/min | `/buscar`, `/buscar-progress` |
| Login / auth | `AUTH_RATE_LIMIT_PER_5MIN` | 5 req/5min | `/auth/login`, `/auth/check` |
| Signup | `SIGNUP_RATE_LIMIT_PER_10MIN` | 3 req/10min | `/auth/signup`, `/auth/email` |
| Checkout | (hardcoded) | 10 req/min | `/checkout/*` |
| MFA verify | (hardcoded) | 5 req/15min | `/auth/mfa/verify` |
| Calculadora | (hardcoded) | 60 req/min | `/calculadora` |
| Founders endpoints | (hardcoded) | 60 req/min | `/founders/*` |
| Founders Hall | (hardcoded) | 20 req/min | `/founders-hall/register` |

### Comportamento Quando Limite Excedido

- **HTTP 429** `Too Many Requests`
- Response body JSON:
  ```json
  {
    "detail": "Limite de requisicoes excedido. Tente novamente em {retry_after} segundos.",
    "retry_after_seconds": <int>,
    "correlation_id": "<uuid>"
  }
  ```
- **Headers HTTP** em toda resposta (sucesso e erro):
  - `X-RateLimit-Limit` — maximo de requisicoes permitidas na janela
  - `X-RateLimit-Remaining` — requisicoes restantes na janela
  - `X-RateLimit-Reset` — timestamp Unix de quando a janela atual expira
  - `Retry-After` — (apenas 429) segundos ate poder tentar novamente

### Chaveamento (Keying)

- Usuario autenticado: `user:{user_id}` (extraido do JWT `sub` claim sem verificacao — usado apenas para rate limit)
- Usuario nao autenticado: `ip:{client_ip}` (via `X-Forwarded-For` ou `request.client.host`)

### Feature Flag

Rate limiting pode ser desabilitado globalmente via:

```
RATE_LIMITING_ENABLED=false
```

Quando desabilitado, `require_rate_limit` retorna sem verificar. Default: `true`.

---

## Camada 2: RedisRateLimiter (Fontes Externas)

### Tipo

**Token bucket compartilhado via Redis.** Cada fonte externa (PNCP, PCP) tem seu proprio bucket com `max_tokens` e `refill_rate`. Implementado com Lua script atomico para garantir consistencia entre workers Gunicorn.

### Implementacao

```
backend/rate_limiter.py -> RedisRateLimiter
```

Redis keys:
- `rate_limiter:{name}:bucket` — HASH `{tokens, last_refill}`
- `rate_limiter:{name}:requests_count` — INT (contagem do minuto atual)

### Instancias

| Instancia | `name` | `max_tokens` | `refill_rate` | Uso |
|-----------|--------|--------------|---------------|-----|
| `pncp_rate_limiter` | `pncp` | 10 | 10.0/s | Requisicoes a API PNCP |
| `pcp_rate_limiter` | `pcp` | 5 | 5.0/s | Requisicoes a API PCP v2 |

### Comportamento

- `acquire(timeout=5.0)`: Tenta adquirir um token com backoff exponencial (50ms inicial, max 500ms)
- Retorna `True` se adquiriu ou Redis indisponivel (fail-open)
- Retorna `False` se excedeu timeout sem conseguir token
- Prometheus: stats disponiveis via `get_stats()` para health endpoint

---

## Camada 3: Tiered Rate Limiter (Bot vs Humano)

### Tipo

**Janela fixa com buckets Redis isolados.** Classifica o User-Agent do cliente e aplica limites diferentes para bots (Googlebot, Bingbot, etc.) e humanos.

### Implementacao

```
backend/rate_limiter.py -> check_rate_limit_tiered()
```

### Configuracoes

| Config | Env Var | Default | Descricao |
|--------|---------|---------|-----------|
| Bot tier | `BOT_RATE_LIMIT_PER_MINUTE` | 10 req/min | Googlebot, Bingbot, etc. |
| Human tier | `HUMAN_RATE_LIMIT_PER_MINUTE` | 60 req/min | Navegadores reais |

Redis keys:
- `rl:bot:{identifier}:{minute}`
- `rl:human:{identifier}:{minute}`

### Motivacao

**Memory: project_backend_outage_2026_04_29_stage5** — Uma onda do Googlebot saturou os endpoints `perfil`, `orgao`, `contratos_publicos` consumindo todo o quota de um bucket compartilhado. O isolamento de tiers previne esse modo de falha.

---

## SSE Connection Tracker

### Limite de Conexoes Simultaneas

| Config | Env Var | Default |
|--------|---------|---------|
| Max conexoes por usuario | `SSE_MAX_CONNECTIONS` | 3 |
| Reconexoes permitidas | `SSE_RECONNECT_RATE_LIMIT` | 10 |
| Janela de reconexao | `SSE_RECONNECT_WINDOW_SECONDS` | 60s |

### Implementacao

Rastreador em memoria com `asyncio.Lock` que conta conexoes ativas por `user_id`. Bloqueia nova conexao quando o limite e excedido. Libera slot ao desconectar.

---

## Arquivos Relevantes

| Arquivo | Proposito |
|---------|-----------|
| `backend/rate_limiter.py` | Todas as 3 camadas de rate limiting |
| `backend/config/features.py` | Feature flag `RATE_LIMITING_ENABLED` |
| `backend/routes/auth_signup.py` | Uso de `require_rate_limit` em auth |
| `backend/routes/checkout.py` | Uso de `require_rate_limit` em checkout |
| `backend/routes/mfa.py` | Uso de `require_rate_limit` em MFA |
| `backend/tests/test_rate_limiting.py` | Testes de rate limiting |
| `backend/tests/security/test_rate_limit_bypass.py` | Testes de bypass |

---

## Env Vars (Resumo)

| Variavel | Default | Camada |
|----------|---------|--------|
| `SEARCH_RATE_LIMIT_PER_MINUTE` | 10 | Flexible (busca) |
| `AUTH_RATE_LIMIT_PER_5MIN` | 5 | Flexible (auth) |
| `SIGNUP_RATE_LIMIT_PER_10MIN` | 3 | Flexible (signup) |
| `SSE_MAX_CONNECTIONS` | 3 | SSE |
| `SSE_RECONNECT_RATE_LIMIT` | 10 | SSE |
| `SSE_RECONNECT_WINDOW_SECONDS` | 60 | SSE |
| `RATE_LIMITING_ENABLED` | true | Global |
| `BOT_RATE_LIMIT_PER_MINUTE` | 10 | Tiered |
| `HUMAN_RATE_LIMIT_PER_MINUTE` | 60 | Tiered |

Para desabilitar rate limiting em desenvolvimento: `RATE_LIMITING_ENABLED=false`
