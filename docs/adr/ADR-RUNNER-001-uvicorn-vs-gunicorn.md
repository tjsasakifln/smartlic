# ADR-RUNNER-001: Uvicorn vs Gunicorn — Application Server Runner

**Status:** Accepted (2026-04-27)
**Date:** 2026-04-27
**Owners:** @architect, @dev

## Context

O SmartLic backend (FastAPI) precisa de um application server HTTP que atenda
requisitos de concorrencia, estabilidade com OpenSSL TLS e compatibilidade com
o ambiente Railway (proxy com ~120s de hard timeout).

### Histórico — CRIT-083 (Gunicorn prefork)

Desde o inicio do projeto, o runner padrao era **Gunicorn** com workers
prefork (`os.fork`). Esta configuracao apresentou um bug intermitente de
producao:

- **Sintoma:** SIGSEGV (segmentation fault) em POST requests com corpo nao
  trivial. GET requests funcionavam normalmente; POST crashavam o worker.
- **Causa raiz:** `cryptography>=46` utiliza OpenSSL C bindings que nao sao
  fork-safe. Quando o Gunicorn faz `os.fork()` para criar workers, o estado
  interno do OpenSSL (RNG, locks, session cache) fica corrompido no processo
  filho. O crash ocorre durante o TLS handshake em requests que disparam
  escrita SSL (POST), mas nao em GET (leitura).
- **Impacto:** Workers morriam silenciosamente, causando 502/503 para o
  cliente e outage de ~30min ate recuperacao completa do container Railway.

Gunicorn foi configurado com `timeout=180` (env `GUNICORN_TIMEOUT`) e
`keep-alive=75` (env `GUNICORN_KEEP_ALIVE`), mas a estabilidade do worker
ficou comprometida independentemente destes parametros.

## Alternatives Considered

1. **Gunicorn + `cryptography` downgrade** — reverter `cryptography` para
   versao pre-46 que nao usava OpenSSL lock. Rejeitado: dependencia nao pode
   ficar presa em versao antiga por razoes de seguranca.

2. **Gunicorn + `preload_app=False` + lazy import** — tentativa de contornar
   o fork corrompido. Nao resolveu: o dano do `os.fork()` ocorre no momento
   do fork, independente de quando as bibliotecas sao importadas.

3. **Uvicorn com `multiprocessing.spawn()`** — Uvicorn nativamente usa
   `multiprocessing.spawn()` em vez de `os.fork()` quando `--workers > 1`.
   `spawn()` cria um novo processo Python interpretador do zero, evitando
   qualquer estado corrompido do OpenSSL.

4. **Uvicorn single-worker + `asyncio` puro** — funcional mas sem
   concorrencia real para multiplas requests simultaneas. Descartado por
   limitacao de throughput.

## Decision

Adotar **Uvicorn** como unico runner suportado, com as seguintes
configuracoes:

```
RUNNER=uvicorn                          # Forcado em start.sh
WEB_CONCURRENCY=2                       # Workers (1 quando colocated)
--limit-max-requests 50000              # Memory budget rotation (~24h)
--timeout-graceful-shutdown 120         # Alinhado com Railway draining
--timeout-keep-alive 75                 # > Railway proxy 60s
```

### Mecanismo

- Uvicorn usa `multiprocessing.spawn()` do Python 3.12 para criar workers.
  Cada worker e um processo novo, limpo, sem herdar estado de OpenSSL do
  processo pai.
- `--limit-max-requests` rotaciona workers apos ~50000 requests (configuravel
  via `GUNICORN_MAX_REQUESTS`, default 50000), prevenindo degradacao gradual
  por memory leak ou fragmentacao.
- `--timeout-graceful-shutdown=120` alinha com o `drainingSeconds=120` do
  Railway, permitindo dreno suave sem matar requests em andamento.
- Gunicorn foi deprecado em `start.sh`: se `RUNNER=gunicorn`, o script
  falha com erro explicito. O binario do Gunicorn nao e mais instalado.

### Route-level timeout (RES-BE-016 AC4)

Complementar ao Uvicorn, um middleware de timeout assincrono foi adicionado
em `backend/pipeline/budget.py::_run_with_budget`:

- Timeout por rota: 60s (`ROUTE_TIMEOUT_S`), configravel via env var.
- Retorna 503 + `Retry-After: 5` antes do Railway matar a request em 120s.
- SSE, health checks e webhooks sao isentos via prefix list.
- Se `ROUTE_TIMEOUT_S=0`, o middleware e desabilitado sem deploy.

Este middleware garante que o event loop nunca fique travado alem de 60s,
mesmo que o Uvicorn worker continue vivo.

## Consequences

### Positivas

1. **SIGSEGV eliminado.** Nenhum crash por fork do OpenSSL desde a migracao
   (CRIT-084 ativo).
2. **Workers estaveis.** Uvicorn roda continuamente sem crash, exceto
   rotacao normal por `--limit-max-requests`.
3. **Rollback rapido.** Basta setar `ROUTE_TIMEOUT_S=0` para desabilitar o
   middleware de timeout sem deploy.
4. **Configuracao simples.** Uvicorn usa os mesmos env vars do Gunicorn
   (`WEB_CONCURRENCY`, `GUNICORN_MAX_REQUESTS`, `GUNICORN_KEEP_ALIVE`),
   entao a migracao foi transparente para o time de operacoes.

### Negativas

1. **`spawn()` e mais lento que `fork()`.** Cada worker demora ~2-3s para
   iniciar vs ~0.5s com fork. Aceitavel: workers raramente reiniciam.
2. **Consumo de memoria ligeiramente maior.** `spawn()` nao compartilha
   paginas COW (copy-on-write) como `fork()`. Compensado pelo
   `--limit-max-requests` que mantem o RSS sob controle.
3. **Gunicorn staging validation (AC1) nao executada.** Se `cryptography`
   eventualmente remover a restricao de fork em versoes futuras, reavaliar
   antes de reverter para Gunicorn.

### Re-validacao

- Se `cryptography` documentar suporte a fork em future release, executar
  AC1 staging test (Gunicorn + carga de POST) antes de considerar rollback.
- Monitor: `rate(smartlic_route_timeout_total[1h]) > 10` indica rotas nao
  cobertas por `_run_with_budget`.

## Referencias

- `backend/start.sh` — script de entrypoint, RUNNER forcado para uvicorn
- `.claude/rules/critical-impl-notes.md` secao "Runner History (CRIT-083 -
  CRIT-084 - RES-BE-016)"
- Railway docs: `drainingSeconds=120`, hard timeout ~120s
- `cryptography` CHANGELOG: OpenSSL fork-safety notice >= 46.0.0
