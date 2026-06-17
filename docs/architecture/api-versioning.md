# Política de Versionamento de API — SmartLic

**Issues:** [#1808](https://github.com/tjsasakifln/SmartLic/issues/1808) |
[#1918](https://github.com/tjsasakifln/SmartLic/issues/1918)
**Prioridade:** P1 (API Hygiene — 1918) / P2 (Policy — 1808)
**Versão Atual:** v1
**Data:** 2026-06-16

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

### 3.1.1 X-API-Version Header (Issue #1918)

Toda resposta da API inclui os seguintes headers para identificar a versão atual:

```http
HTTP/1.1 200 OK
X-API-Version: v1
X-API-Deprecated: false
```

- **`X-API-Version`**: Versão atual da API (`v1`). Reflete o prefixo URI (`/v1/*`).
- **`X-API-Deprecated`**: `false` enquanto a versão está ativa. Torna-se `true` quando v(N+1) é lançada e v(N) entra na janela de depreciação.

Quando v1 entrar em depreciação:
- `X-API-Deprecated: true`
- `Sunset: <ISO-8601>` adicionado
- `Deprecation: true` adicionado (RFC 8594)

Implementado por `APIVersionHeaderMiddleware` em `backend/middleware.py`.

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

### 5.2 GitHub Actions Workflow (`.github/workflows/api-schema-check.yml`)

Executa em PRs que tocam `backend/schemas/`, `backend/routes/`, ou `backend/main.py`:

1. Extrai OpenAPI schema do branch do PR e do target (`main`).
2. Compara schemas via `scripts/check-api-breaking.sh`.
3. Se breaking change detectado:
   - Posta comentário no PR com detalhes da mudança.
   - Exige justificativa do autor (não bloqueante — warning).
   - Verifica se novo router `/v2/*` foi criado (recomendação).
4. Se sem breaking changes: ✅ aprovado.

### 5.3 Migration Policy

- **v1 → v2**: Novas funcionalidades SEMPRE em `/v1/*` primeiro. `/v2/*` só é criado quando há breaking change.
- **Coexistência**: v1 e v2 podem coexistir. Clientes existentes continuam em v1 até migrarem.
- **Remoção**: Endpoints removidos em v2 devem ser listados no changelog com justificativa.

## 6. Versionamento de Tipos Frontend

Tipos TypeScript são gerados automaticamente do schema OpenAPI:

```bash
npm --prefix frontend run generate:api-types
```

Arquivo gerado: `frontend/app/api-types.generated.ts` (NÃO editar manualmente)

### 6.1 Version-Aware Types (Issue #1918)

O schema OpenAPI inclui a versão no objeto `info`:

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "SmartLic API",
    "version": "v1"
  }
}
```

Isso garante que os tipos gerados pelo `openapi-typescript` são associados à versão correta. Quando v2 for criada, um novo schema com `info.version: "v2"` será gerado.

### 6.2 Verificação de Drift

O CI gate `api-types-check.yml` verifica automaticamente se `api-types.generated.ts` está sincronizado com o schema OpenAPI. Breaking changes no schema são detectados pelo `api-schema-check.yml`.

## 7. Referências

- [Stripe API Versioning](https://stripe.com/docs/api/versioning)
- [FastAPI Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Check API Breaking Script](../../scripts/check-api-breaking.sh)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
