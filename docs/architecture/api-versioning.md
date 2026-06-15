# API Versioning Strategy

## Politica Atual

Todas as rotas da API sao prefixadas com `/v1/` atraves do registro centralizado
em `backend/startup/routes.py`. O padrao e:

```python
# startup/routes.py::register_routes()
for r in _v1_routers:
    app.include_router(r, prefix="/v1")
```

### Excecoes ao Prefixo `/v1/`

| Rota | Prefixo | Justificativa |
|------|---------|---------------|
| `/health/live`, `/health/ready` | Raiz (`/`) | Probes de container (Railway) -- nao mudam |
| `/webhooks/stripe` | Raiz (`/`) | DEBT-324: configuracao fixa no Stripe Dashboard |
| `/api/founders/*` | `/api/` | Issue #1002: landing page + SEO, fora do ciclo API |
| `/api/founders/hall/*` | `/api/` | Issue #1008: listing publico + consentimento LGPD |
| `/api/checkout/*` | `/api/` | CONV-005b-2: caminho generico para frontend |
| `/api/email/*` | `/api/` | DIGEST-005: sem auth, acessiveis de email clients |
| `/v1/admin/*` (auto-prefixados) | `/v1/admin/` | 5 routers admin que se prefixam internamente |

### Contagem de Endpoints

- **65 routers registrados**, sendo 60 em `_v1_routers`
- **187 endpoints** no total
- **~69 routers em `routes/`**, 65 registrados ativamente

---

## Compromisso de Backward Compatibility

### Regras

1. **Campos novos em responses:** Adicionar campos opcionais `?` em schemas
   Pydantic existentes e nunca remover campos existentes.
2. **Parametros de query:** Novos parametros devem ter valores default que
   mantem o comportamento existente.
3. **Metodo HTTP:** Nunca mudar o metodo de um endpoint existente
   (ex: `GET /v1/search/:id` nao se torna `POST /v1/search/:id`).
4. **Path params:** Nunca renomear ou remover path params existentes.
5. **Headers:** Headers de request existentes nunca sao exigidos como
   obrigatorios se antes eram opcionais.
6. **Erros:** Estrutura de erro (`detail`, `status_code`) e estavel. Novos
   campos de erro devem ser adicionados como opcionais.

### O que NÃO e breaking change

- Adicionar novo endpoint
- Adicionar campo opcional em response (clientes ignoram campos desconhecidos)
- Adicionar query parameter opcional com default seguro
- Alterar mensagens de erro (desde que o formato permaneca)
- Corrigir bug que fazia endpoint retornar dados incorretos
- Melhorar performance (nao afeta contrato)

### O que E breaking change

- Remover ou renomear endpoint
- Remover campo de response
- Tornar campo opcional em obrigatorio
- Mudar tipo de campo (ex: `string` -> `integer`)
- Mudar codigo de status HTTP
- Alterar estrutura de request body
- Mudar fluxo de autenticacao

---

## Quando Criar `/v2/`

### Gatilhos para `/v2/`

Uma nova versao `/v2/` deve ser criada quando **pelo menos um** dos seguintes
cenarios ocorrer:

1. **Mudanca no schema de dados:** O formato de um recurso central (ex: busca,
   licitacao, usuario) precisa ser alterado de forma incompativel.
2. **Mudanca no fluxo de autenticacao:** Novo mecanismo de auth incompativel
   com o atual (ex: migrar de JWT para OAuth 2.1 com不同 scopes).
3. **Remocao de funcionalidade:** Um endpoint precisa ser removido por razao
   legal, de seguranca ou arquitetural.
4. **Reestruturacao de recursos:** URL paths precisam ser reestruturados
   (ex: `GET /v1/licitacoes/:id` -> `GET /v2/tenders/:id`).

### Nao sao gatilhos para `/v2/`

- Adicao de novos endpoints (use `/v1/` normalmente)
- Campos opcionais em responses existentes
- Correcoes de bug
- Melhorias de performance ou confiabilidade
- Mudancas internas de implementacao sem reflexo no contrato

### Estrategia de Migracao para `/v2/`

1. Criar `_v2_routers` em paralelo a `_v1_routers` em `startup/routes.py`
2. Manter `/v1/` ativo por no minimo 6 meses apos o lancamento de `/v2/`
3. Clientes `/v1/` recebem header `Warning: 299 - "This API version will be
   deprecated. Migrate to /v2/ by YYYY-MM-DD"`
4. `/v2/` deve ser uma copia limpa, sem dependencia interna de routers `/v1/`
5. Schemas Pydantic do `/v2/` vivem em `backend/schemas/v2/` separados

---

## Deprecation Policy

### Timeline

| Fase | Acao | Duracao |
|------|------|---------|
| **Announcement** | Header de warning + changelog entry | Dia 0 |
| **Migration period** | `/v1/` e `/v2/` convivem, clientes migram | 3-6 meses |
| **Soft deprecation** | `/v1/` retorna `410 Gone` com link para `/v2/` | 1 mes |
| **Hard removal** | Codigo do `/v1/` removido do codebase | Apos soft deprecation |

### Comunicacao

1. **Changelog:** `CHANGELOG.md` deve listar todas as breaking changes planejadas
2. **OpenAPI schema:** O schema `/v1/` deve conter `deprecated: true` no JSON
   gerado
3. **Email:** Clientes integrados via API recebem email 30 dias antes da
   deprecation
4. **Header de resposta:** Respostas de `/v1/` incluem:
   ```http
   Warning: 299 - "v1 is deprecated. Migrate to v2 by 2026-12-31"
   ```

### Excecoes

- Endpoints de health check (`/health/*`) nunca sao versionados
- Stripe webhooks (`/webhooks/stripe`) nunca sao versionados
- SEO programmatic (`/api/founders/*`, `/api/checkout/*`) seguem ciclo proprio
- Endpoints admin (`/v1/admin/*`) seguem deprecation acelerada (aviso 30 dias)

---

## OpenAPI Schema como Contrato

### Geracao

O schema OpenAPI e gerado automaticamente a partir dos decoradores FastAPI
(`response_model=`) e schemas Pydantic.

```bash
# Gerar schema localmente
curl http://localhost:8000/openapi.json > openapi.json
```

### Snapshot e CI

O arquivo `backend/tests/snapshots/openapi_schema.diff.json` rastreia mudancas
no schema OpenAPI entre versoes. O CI valida que o schema gerado corresponde
ao commitado em `frontend/app/api-types.generated.ts`.

### Tipoas TypeScript

O schema OpenAPI alimenta a geracao de tipos TypeScript:

```bash
npm --prefix frontend run generate:api-types
```

**Regras:**
- Todo endpoint exposto ao frontend DEVE declarar `response_model=` no decorator
  da rota
- Tipos gerados sao salvos em `frontend/app/api-types.generated.ts` (NAO editar
  manualmente)
- `frontend/app/types.ts` re-exporta tipos gerados com nomes amigaveis
- CI falha se o arquivo gerado divergir do que o backend produziria

### Canario de Schema (PNCP)

O arquivo `backend/contracts/schemas/pncp_search_response.schema.json` serve
como JSON Schema canario para respostas da API PNCP. Se o payload divergir
do schema, o canario (STORY-4.5) dispara alerta no Sentry.

---

## Registro de Rotas

Todas as rotas sao registradas em `backend/startup/routes.py`:

```python
def register_routes(app: FastAPI) -> None:
    # Health core em / (fora de versao)
    app.include_router(health_core_router)
    # API routers em /v1/
    for r in _v1_routers:
        app.include_router(r, prefix="/v1")
    # Routers auto-prefixados
    app.include_router(admin_trace_router)
    app.include_router(admin_cron_router)
    # ...
    # Webhooks em / (configuracao fixa Stripe)
    app.include_router(stripe_webhook_router)
```

Para adicionar uma nova rota:
1. Criar arquivo em `backend/routes/`
2. Adicionar a `_v1_routers` em `startup/routes.py`
3. Declarar `response_model=` no decorator
4. Registrar schemas Pydantic em `backend/schemas/`
5. Executar `npm run generate:api-types` para atualizar tipos do frontend
