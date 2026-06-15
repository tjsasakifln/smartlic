# Python 3.13 Migration Plan — GIL removal + JIT

**Issue:** #1880
**Status:** Planning
**Target Staging:** Q3 2026
**Target Production:** Q4 2026

---

## 1. Motivation

Python 3.13 introduz duas mudancas significativas para aplicacoes como o SmartLic:

| Feature | PEP | Status | Impacto Estimado |
|---------|-----|---------|-----------------|
| **GIL removal (free-threaded mode)** | PEP 703 | Experimental (`--disable-gil`) | 10-30% throughput em workloads I/O-bound |
| **JIT compiler** | PEP 744 | Experimental | 5-15% em loops CPU-bound |
| **Improved bytecode** | — | Standard | ~10% interpreter speedup |

### 1.1 Por que migrar agora

1. **Performance gratuita:** Benchmarks preliminares mostram 10-20% de melhoria sem alteracao de codigo
2. **Seguranca:** 3.12 EOL previsto para ~2028 — migration gradual evita corrida no final do ciclo
3. **Free-threading:** FastAPI/async workloads sao I/O-bound — GIL removal pode desbloquear throughput significativo em workers single-thread
4. **Ecosystem readiness:** Maio/2026 — major packages (FastAPI, Pydantic, httpx, cryptography) ja possuem wheels para 3.13

### 1.2 Riscos

1. **C extensions:** cryptography, numpy, scikit-learn, psutil, prometheus-client — todos com bindings C que podem quebrar
2. **GIL removal e experimental:** cryptography C bindings nao sao thread-safe sem GIL — `--disable-gil` requer validacao especifica
3. **Railway images:** Python 3.13 slim precisam estar disponiveis no Docker Hub oficial
4. **Rollback:** Sem `--disable-gil`, 3.13 e quase 100% retrocompativel — rollback e trivial (trocar tag da imagem)

---

## 2. Dependency Compatibility Analysis

### 2.1 Core Dependencies

| Dependencia | Versao | C Ext? | Wheels 3.13? | Notas |
|-------------|--------|--------|-------------|-------|
| `fastapi` | 0.137.0 | Nao | Sim | Pure Python |
| `uvicorn` | 0.49.0 | Nao | Sim | Pure Python |
| `pydantic` | 2.13.4 | Rust (pydantic-core) | Sim | wheels disponiveis desde 3.13 beta |
| `starlette` | 0.52.1 | Nao | Sim | Pure Python |
| `httpx` | 0.28.1 | Nao | Sim | Pure Python |
| `cryptography` | >=46.0.6 | **Sim** (OpenSSL) | Sim | wheels 3.13 disponiveis — testar fork-safety |
| `numpy` | >=2.4.6 | **Sim** (C) | Sim | wheels desde numpy 2.1 |
| `scikit-learn` | >=1.9.0 | **Sim** (C/Cython) | Sim | wheels disponiveis |
| `pandas` | >=3.0.3 | **Sim** (C/Cython) | Sim | wheels disponiveis |
| `psutil` | >=5.9.8 | **Sim** (C) | Sim | wheels desde 5.9.7 |
| `prometheus-client` | >=0.25.0 | **Sim** (C) | Sim | wheels 3.13 desde 0.24 |
| `supabase` | 2.31.0 | Nao | Sim | Pure Python wrapper |
| `redis` | 5.3.1 | Nao | Sim | Pure Python |
| `openai` | 1.109.1 | Nao | Sim | Pure Python + httpx |
| `sentry-sdk` | 2.62.0 | Nao | Sim | Pure Python |
| `arq` | >=0.28.0 | Nao | Sim | Pure Python |
| `stripe` | 11.6.0 | Nao | Sim | Pure Python |

### 2.2 Blocker Assessment

| Blocker? | Dependency | Motivo |
|----------|-----------|--------|
| Nao | `cryptography` | Wheels 3.13 disponiveis; mesmo risco SIGSEGV de sempre (CRIT-083) |
| Nao | `numpy`/`scikit-learn` | Wheels 3.13 disponiveis (numpy 2.1+, sklearn 1.5+) |
| Nao | `psutil` | Wheels 3.13 desde 5.9.7 |
| Nao | Qualquer pure-Python | Nao ha risco de C extension |

**Conclusao:** Zero blockers identificados para Python 3.13 sem `--disable-gil`. Todas as dependencias com C extensions possuem wheels para 3.13.

### 2.3 Free-threaded mode (`--disable-gil`)

| Package | Thread-safe sem GIL? | Notas |
|---------|---------------------|-------|
| `cryptography` | Nao confirmado | OpenSSL bindings podem ter race conditions (CRIT-083) |
| `numpy` | Parcial | Array operations OK, C extensions questionaveis |
| `scikit-learn` | Nao confirmado | ThreadPool internos podem conflitar |
| Pure Python | Sim | GIL removal e transparente para pure-Python |

**Recomendacao:** Iniciar migracao **sem** `--disable-gil`. Adotar free-threaded mode apenas apos validacao extensiva em staging (Q1 2027+).

---

## 3. Benchmark Results

> Resultados a serem preenchidos apos execucao de `scripts/benchmark-python-version.sh`.

### 3.1 Test Suite

| Metrica | Python 3.12 | Python 3.13 | Diferenca |
|---------|-------------|-------------|-----------|
| Test duration | — | — | — |
| Tests passed | — | — | — |
| Tests failed | 0 (baseline) | — | — |
| Coverage | — | — | — |

### 3.2 Latencia (endpoints-chave)

| Endpoint | 3.12 p50 | 3.12 p95 | 3.13 p50 | 3.13 p95 | Diferenca |
|----------|---------|---------|---------|---------|-----------|
| `GET /health/live` | — | — | — | — | — |
| `POST /buscar` (datalake) | — | — | — | — | — |
| `GET /v1/pipeline` | — | — | — | — | — |

### 3.3 Memory

| Metrica | Python 3.12 | Python 3.13 | Diferenca |
|---------|-------------|-------------|-----------|
| Peak RSS (test suite) | — | — | — |
| Process memory (idle) | — | — | — |

---

## 4. Migration Steps

### 4.1 Pre-Migration (Q2 2026 — corrente)

- [x] Issue #1880 criada com plano
- [ ] Dockerfile atualizado com `ARG PYTHON_VERSION` (PR #1880)
- [ ] Script de benchmark criado (`scripts/benchmark-python-version.sh`)
- [ ] Benchmark executado em ambiente de staging
- [ ] Resultados documentados neste relatorio

### 4.2 Staging Validation (Q3 2026 — Julho/Agosto)

1. **Build 3.13 image:** `docker build --build-arg PYTHON_VERSION=3.13 -t smartlic-backend-py313 backend/`
2. **Deploy para staging Railway:** Usar `railway up` com service separado ou variavel `BUILD_ARGS`
3. **Executar test suite completo:** `pytest --timeout=30 -v`
4. **Validar health checks:** `/health/live`, `/health/ready` endpoints
5. **Monitorar Sentry:** 24h sem erros novos
6. **Benchmark comparativo:** Rodar `scripts/benchmark-python-version.sh`
7. **Pipeline funcional:** Executar 3 buscas reais (datalake + multi-source)
8. **Rollback test:** Reverter para 3.12 image via Railway dashboard

**Criterio de GO:** 0 test failures, 0 new Sentry errors, latency nao degradada

### 4.3 Gradual Rollout (Q3-Q4 2026)

```
Semana 1-2: Staging Railway (servico nao critico)
Semana 3-4: Worker ARQ apenas (separado do web)
Semana 5-6: Web + Worker (staging completo)
Semana 7-8: Canary — 10% do trafego web
Semana 9+: Full production (Q4 2026)
```

### 4.4 Production Migration (Q4 2026)

1. **Dia 1:** Atualizar Railway `BUILD_ARGS` para `PYTHON_VERSION=3.13` no worker
2. **Dia 3:** Se sem erros, atualizar web service
3. **Dia 7:** Remover override — tornar 3.13 o default (alterar `ARG PYTHON_VERSION=3.13` no Dockerfile)
4. **Dia 14:** Remover codigo de compatibilidade 3.12 (se houver)

### 4.5 Rollback Plan

| Cenario | Acao | Tempo |
|---------|------|-------|
| Test failure | Reverter Railway build arg para `PYTHON_VERSION=3.12` | 5 min |
| Sentry error novo | Reverter + investigar causa raiz | 1h |
| Latencia degradada | Reverter + benchmark comparativo | 30 min |
| SIGSEGV (CRIT-083-like) | Reverter + fixar cryptography version | 15 min |
| Railway image unavailable | Usar imagem alternativa (`python:3.13-bookworm`) | 10 min |

---

## 5. Dockerfile Changes (PR #1880)

```dockerfile
# Antes:
FROM python:3.12-slim

# Depois:
ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim
```

Build com Python 3.13:

```bash
docker build --build-arg PYTHON_VERSION=3.13 -t smartlic-backend-py313 backend/
```

Railway deploy com Python 3.13:

```bash
railway variables set BUILD_ARGS="PYTHON_VERSION=3.13"
railway up
```

---

## 6. Timeline

| Marco | Data Alvo | Responsavel | Dependencias |
|-------|-----------|-------------|-------------|
| Plano de migracao | 2026-06-15 | @architect | — |
| Dockerfile multi-version | 2026-06-15 | @dev | — |
| Benchmark script | 2026-06-15 | @dev | — |
| Benchmark execucao | 2026-07-01 | @qa | Railway staging |
| Staging validation | 2026-08-01 | @dev + @qa | Benchmark OK |
| Worker ARQ 3.13 | 2026-09-01 | @devops | Staging GO |
| Web 3.13 (canary) | 2026-10-01 | @devops | Worker OK |
| Full production | 2026-11-01 | @devops | Canary OK |
| 3.13 como default | 2026-12-01 | @devops | Producao estavel |
| Free-threaded eval | 2027-Q1 | @architect | 3.13 estavel |

---

## 7. Risks and Mitigations

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| cryptography SEM compativel 3.13 | Baixa | Alto | Testar em staging antes de prod |
| numpy wheel ausente 3.13 | Baixa | Medio | numpy 2.4+ ja tem wheels |
| Railway imagem 3.13 atrasada | Media | Medio | Usar python:3.13-bookworm alternativo |
| GIL removal quebra C extensions | Alta (sem --disable-gil) | N/A | Nao usaremos free-threaded em 2026 |
| Sentry SDK incompativel | Baixa | Baixo | sentry-sdk pure Python |
| ARQ/redis driver incompativel | Baixa | Medio | Testar worker separadamente |
| Regression de performance | Baixa | Baixo | Reverter — sem custo de rollback |

---

## 8. GO/NO-GO Checklist

- [ ] Test suite 100% passing em 3.13
- [ ] `pip check` sem conflitos
- [ ] Nenhum Sentry error novo apos 24h staging
- [ ] Latencia p50/p95 nao degradada (ou melhora documentada)
- [ ] Memory RSS dentro do limite (<= 500MB)
- [ ] Docker build 3.13 bem-sucedido
- [ ] Rollback testado e funcional
- [ ] Worker ARQ operacional com 3.13
- [ ] Web endpoints funcionais (health, buscar, pipeline)
- [ ] Frontend integracao testada (Pydantic -> TypeScript types)

---

*Documento mantido em `docs/architecture/python-3.13-migration.md`*
*Ultima atualizacao: 2026-06-15*
*Issue: #1880*
