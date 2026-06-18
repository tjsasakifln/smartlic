# Runbook: Redis Connection Failure

**Versao:** 1.0
**Criado:** 2026-06-17
**Owner:** @devops
**Severidade tipica:** SEV2 (pode escalar SEV1 se prolongado)
**Referencia:** `incident-response.md` secao 3.3

---

## 1. Sintomas

### Alertas
- Metrica: `smartlic_redis_available=0`
- Sentry: erro `Redis connection failed` ou `ConnectionRefusedError`
- Railway log: `Cannot connect to Redis at ...:6379: Connection refused`
- ARQ worker parou de processar jobs
- Rate limiting parou de funcionar (todas requests passam)

### Comportamento Observado
```bash
# Redis gauge = 0
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_redis_available'
# Output: smartlic_redis_available 0

# Fallback duration tracking
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_redis_fallback_duration_seconds'
```

### Impacto no Sistema

| Componente | Com Redis | Sem Redis (degradado) |
|------------|-----------|----------------------|
| Cache L1 | Redis-backed (multi-worker) | InMemoryCache (per-process, sem shared state) |
| Rate Limiter | Token bucket funcional | Fail-open (todas requests passam) |
| Circuit Breaker | Estado persistente entre workers | Reseta para CLOSED em cada worker |
| ARQ Queue | Processamento assincrono | Jobs rodam inline (mais lentos) |
| SSE State | Estado compartilhado entre workers | Estado por worker (inconsistencias) |
| Session Cache | Sessoes em Redis | Fallback para cookie/supabase |

---

## 2. Diagnostico

### 2.1 Testar Conectividade

```bash
# Test PING via Railway run
railway run --service bidiq-backend python3 -c "
import asyncio, os
from redis import asyncio as aioredis
async def main():
    r = aioredis.from_url(os.environ['REDIS_URL'])
    print(await r.ping())
asyncio.run(main())
"

# Se PONG: Redis esta vivo, problema pode ser no pool do backend
# Se erro: Redis esta offline ou URL esta incorreta
```

### 2.2 Verificar URL do Redis

```bash
# URL esta configurada?
railway variables --service bidiq-backend | grep REDIS_URL

# Se Upstash: verificar se URL comeca com rediss:// (TLS)
# Se Railway addon: verificar se o servico Redis esta rodando
```

### 2.3 Verificar Upstash Dashboard (se aplicavel)

```bash
# Upstash console URL (salva em .env ou password manager)
# https://console.upstash.com/redis → Database → Usage & Limits

# Verificar:
# - Database size (excedeu quota gratuita?)
# - Daily bandwidth (excedeu limite?)
# - Command rate (estourou RPS?)
```

### 2.4 Verificar Railway Redis Addon (se aplicavel)

```bash
# Verificar se o servico Redis esta rodando
railway status

# Logs do servico Redis
railway logs --service redis --tail | tail -20
```

### 2.5 Verificar Circuit Breakers Impactados

```bash
# Estado dos circuit breakers
curl -s https://api.smartlic.tech/health/ready | jq '.checks'

# Todos os CBs rodam em estado transiente (resetados = CLOSED)
# Isso PODe causar requests a APIs instaveis se Redis ficar offline
```

---

## 3. Causas Comuns

| Causa | Indicador | Acao |
|-------|-----------|------|
| Upstash quota excedida | Dashboard mostra 100% usage | Fazer upgrade ou reduzir TTL |
| Railway Redis crashou | Service mostra CRASHED | Restartar servico |
| Network partition | Railway para Redis addon perdeu conectividade | Aguardar ou redeploy |
| URL expirou / foi rotacionada | `REDIS_URL` antiga nao funciona | Atualizar env var |
| TLS mismatch | Erro `handshake failed` | Usar `rediss://` em vez de `redis://` |

---

## 4. Mitigacao

### 4.1 Nenhuma acao imediata (degradacao graciosa)

O sistema tem **degradacao graciosa** para Redis offline. Nao requer acao imediata em horario de baixa carga. Componentes continuam funcionando com InMemoryCache fallback.

**Monitorar:**
- `smartlic_redis_fallback_duration_seconds` — se > 30 min, considerar acao
- Memoria do backend (InMemoryCache cresce sem Redis)
- Error rate geral

### 4.2 Se Upstash: Verificar e fazer upgrade

```bash
# Acessar console Upstash
# https://console.upstash.com/redis

# Acoes:
# 1. Verificar se database esta paused (free tier)
# 2. Verificar bandwidth usado
# 3. Se necessario: upgrade de plano ou limpar chaves antigas

# Limpar chaves expiradas via CLI
railway run --service bidiq-backend python3 -c "
import asyncio, os
from redis import asyncio as aioredis
async def main():
    r = aioredis.from_url(os.environ['REDIS_URL'])
    info = await r.info('memory')
    print(f'Memory used: {info[\"used_memory_human\"]}')
    # Forcar limpeza de chaves expiradas
    deleted = await r.execute_command('MEMORY PURGE')
    print(f'Memory purge: {deleted}')
asyncio.run(main())
"
```

### 4.3 Se Railway Addon: Restartar servico Redis

```bash
# Restartar servico Redis no Railway
railway redeploy --service redis -y

# Ou se nao houver servico separado, restartar o backend tambem
railway redeploy --service bidiq-backend -y
```

### 4.4 Se prolongado (> 30 min): Aumentar InMemoryCache

```bash
# Sem Redis, InMemoryCache precisa de mais espaco
railway variables set INMEMORY_CACHE_MAX_ENTRIES=20000 --service bidiq-backend
railway variables set INMEMORY_CACHE_TTL_SECONDS=300 --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

### 4.5 Emergency: Desabilitar rate limiting (fail-open)

Ja e o comportamento atual. Verificar se nao ha abuso:

```bash
# Monitorar requests por IP
railway logs --service bidiq-backend --tail | grep -E "429|rate.limit|too many"
```

**Gatilho SEV1:** Redis offline > 45 min COM pico de uso (InMemoryCache overflow + rate limit desabilitado + concurrencia alta).

---

## 5. Resolucao

### 5.1 Verificar Redis disponivel novamente

```bash
# Ping test
railway run --service bidiq-backend python3 -c "
import asyncio, os
from redis import asyncio as aioredis
async def main():
    r = aioredis.from_url(os.environ['REDIS_URL'])
    print(await r.ping())
asyncio.run(main())
"

# Gauge
curl -s https://api.smartlic.tech/metrics | grep 'smartlic_redis_available'
```

### 5.2 Se metrics ainda mostram 0, restart forcado

```bash
railway redeploy --service bidiq-backend -y
```

### 5.3 Verificar comportamento pos-restauracao

```bash
# Cache warming: primeiras requests podem ser lentas
# Rate limiting deve voltar a funcionar
# Circuit breakers devem manter estado

# Verificar health
curl -s https://api.smartlic.tech/health/ready | jq '.ready'
```

### 5.4 Apos resolucao: Reverter alteracoes emergenciais

Se alterou `INMEMORY_CACHE_MAX_ENTRIES` ou `INMEMORY_CACHE_TTL_SECONDS`:

```bash
railway variables set INMEMORY_CACHE_MAX_ENTRIES=10000 --service bidiq-backend
railway variables set INMEMORY_CACHE_TTL_SECONDS=60 --service bidiq-backend
railway redeploy --service bidiq-backend -y
```

---

## 6. Prevencao

### Monitoramento
- Gauge: `smartlic_redis_available` — P1 alert se = 0 por > 5 min
- Gauge: `smartlic_redis_fallback_duration_seconds` — alert se > 30 min
- Latencia: `smartlic_redis_latency_ms` — alert se > 100ms p95

### Upstash (se aplicavel)
- Configurar alerta de quota no dashboard Upstash
- Monitorar `used_memory` vs `max_memory` semanalmente
- Manter TTL de chaves curto (< 1h para cache, < 15min para rate limit)

### Railway Addon
- Configurar health check no servico Redis
- Monitorar logs de erro do Redis

### Arquitetura
- InMemoryCache deve ser configurado para suportar fallback prolongado
- Circuit breakers devem ter fallback para CLOSED state seguro
- Rate limiter deve ter fallback com limitacao conservadora (ex: 100 req/min mesmo sem Redis)

---

## 7. Referencias

- `incident-response.md` secao 3.3 — Playbook resumido Redis Offline
- `docs/architecture/redis-failure-modes.md` — Analise de modos de falha Redis
- `backend/cache/` — Implementacao InMemoryCache + RedisCache
- `backend/middleware/rate_limit.py` — Rate limiter com fallback
- Upstash Status: https://status.upstash.com
- Railway Status: https://status.railway.app
