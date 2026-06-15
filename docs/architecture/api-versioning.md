# Política de Versionamento de API — SmartLic

**Issue:** [#1808](https://github.com/tjsasakifln/SmartLic/issues/1808)
**Prioridade:** P2
**Versão Atual:** v1
**Data:** 2026-06-15

## 1. Esquema de Versionamento

### 1.1 URL-Based Versioning

```
/api/v1/buscar
/api/v2/buscar
```

Versão é prefixo da URL. Clientes sempre especificam a versão explicitamente.

### 1.2 Regra de Ouro

> **Nova versão da API só é criada quando há breaking change.** Mudanças compatíveis são feitas na versão atual.

## 2. Definição de Breaking Change

### 2.1 NÃO é Breaking Change ✅

- Adicionar novo campo na resposta
- Adicionar novo endpoint
- Adicionar novo parâmetro de query opcional
- Adicionar novo valor em enum
- Mudar mensagem de erro (texto)
- Mudar ordem de campos (clientes devem ser tolerantes)
- Adicionar novo header de resposta

### 2.2 É Breaking Change ❌

- Remover campo da resposta
- Mudar tipo de campo (ex: `string` → `number`)
- Mudar nome de campo
- Remover endpoint
- Mudar URL do endpoint
- Tornar obrigatório um parâmetro que era opcional
- Mudar formato de data/hora
- Remover valor de enum
- Mudar código de status HTTP de sucesso (ex: 200 → 201)
- Mudar semântica de parâmetro existente

### 2.3 Zona Cinzenta ⚠️ (avaliar caso a caso)

- Mudar comportamento de validação (mais restritivo)
- Mudar rate limit
- Adicionar autenticação a endpoint público
- Mudar paginação default

## 3. Depreciação (Deprecation)

### 3.1 Headers HTTP

Quando um endpoint ou campo é depreciado, adicionar headers:

```http
HTTP/1.1 200 OK
Deprecation: true
Sunset: Sat, 31 Dec 2026 23:59:59 GMT
```

### 3.2 Sunset Policy

| Marco | Prazo | Ação |
|-------|:---:|-------|
| **Anúncio** | D-180 | Headers Deprecation/Sunset adicionados |
| **Aviso 1** | D-90 | Email para usuários da API |
| **Aviso 2** | D-30 | Email de urgência |
| **Sunset** | D-Day | Versão antiga retornará `410 Gone` |

**Política:** v(N-1) mantida por **6 meses** após lançamento de vN.

## 4. Comunicação com Clientes

| Canal | Público | Quando |
|-------|---------|--------|
| **Headers HTTP** | Clientes da API | Imediato (automático) |
| **Changelog** | Desenvolvedores | `/api/docs/changelog` |
| **Email** | Admins de conta | 90 dias antes do sunset |
| **In-app banner** | Usuários logados | 60 dias antes do sunset |

## 5. CI Gate — Breaking Change Detection

### 5.1 OpenAPI Schema Comparison

```bash
./scripts/check-api-breaking.sh main feature/nova-versao
```

Script compara campos removidos, tipos alterados, endpoints removidos.

### 5.2 GitHub Actions

Incluir no CI para PRs que tocam `backend/schemas/` ou `backend/routes/`.

## 6. Versionamento de Tipos Frontend

Tipos TypeScript são gerados automaticamente:

```bash
npm --prefix frontend run generate:api-types
```

Arquivo gerado: `frontend/app/api-types.generated.ts` (NÃO editar manualmente)

## 7. Referências

- [Stripe API Versioning](https://stripe.com/docs/api/versioning)
- [FastAPI Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Check API Breaking Script](../../scripts/check-api-breaking.sh)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
