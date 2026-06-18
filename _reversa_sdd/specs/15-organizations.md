# Spec: Multi-Tenant Organizations

> Spec executavel do modelo multi-tenant para organizacoes (consultoria/agency multi-user).
> Cobre: definicao de roles, propagacao de org_id, modelo de faturamento, isolamento RLS e plano de migracao.
> Gerado em 2026-06-17 a partir do codigo fonte + decisoes arquiteturais (ADR-ORG-MT-001).

## Component
- **ID**: `organizations`
- **Path**: `backend/routes/organizations.py`, `backend/services/organization_service.py`, `backend/dependencies/org_auth.py`, `backend/schemas/parity.py` (classes `Organization*`), `backend/config/features.py` (flag `ORGANIZATIONS_ENABLED`)
- **Schema**: `supabase/migrations/20260301100000_create_organizations.sql`, `supabase/migrations/20260501000000_rbac_org_001_role_viewer.sql`
- **Status**: PARCIAL -- 8 endpoints implementados, propagacao de dados NAO implementada, faturamento por org NAO implementado

## Purpose

Permitir que contas do tipo Consultoria (plano `smartlic_consultoria`) operem com multiplos usuarios sob uma mesma organizacao, com isolamento de dados, hierarquia de permissoes e faturamento consolidado por organizacao (nao por usuario).

## Roles

### Hierarquia (3 niveis)

| Role   | Rank | Permissoes                                                                                                 | Gerenciamento                                      |
|--------|------|------------------------------------------------------------------------------------------------------------|----------------------------------------------------|
| `owner`  | 3    | Controle total: CRUD organizacao, convidar/remover membros, dashboard consolidado, alterar logo, gerenciar faturamento, configurar plano | Atribuido ao criar org; transferivel (futuro); 1 por org |
| `member` | 2    | Acesso pleno da organizacao: pipeline, buscas, exportacoes, mensagens, relatorios                          | Convidado pelo owner                               |
| `viewer` | 1    | Acesso somente leitura: visualizar pipeline, resultados de busca, dashboard; sem criar buscas ou exportar  | Convidado pelo owner                               |

### Aplicacao Atual (codigo)

- `OrgRole` enum em `dependencies/org_auth.py`: `OWNER=3`, `MEMBER=2`, `VIEWER=1`
- `require_org_role(min_role)` retorna FastAPI dependency que extrai `org_id` do path param e valida rank
- Usado atualmente em: GET org, POST invite, DELETE member, GET dashboard, PUT logo
- **GAP:** viewer ainda nao tem comportamento diferenciado de member na camada de RLS -- ambos veem os mesmos dados

### Regras de Negocio

1. **Um owner por org** -- `organization_members` UNIQUE(org_id, user_id) + CHECK role IN ('owner','member','viewer')
2. **Owner nao pode ser removido** -- `remove_member` bloqueia `role == 'owner'`
3. **Invitacoes pendentes** -- `accepted_at IS NULL` = pendente; aceite via `accept_invite`
4. **Owner auto-aceito** -- ao criar org, owner e inserido com `accepted_at = NOW()`
5. **Limite de membros** -- `max_members` (default 5) verificado em `invite_member`

## org_id Propagation

### Estado Atual

`org_id` **NAO** esta propagado nas tabelas de dados do usuario. Cada uma dessas tabelas pertence ao usuario individual (`user_id`), nao a organizacao:

| Tabela               | Tem org_id? | Isolamento atual |
|----------------------|-------------|------------------|
| `pipeline_items`     | NAO         | `user_id`        |
| `search_sessions`    | NAO         | `user_id`        |
| `search_results_cache` | NAO       | `user_id`        |
| `messages`           | NAO         | `user_id`        |
| `exports`            | NAO         | `user_id`        |
| `saved_searches`     | NAO         | `user_id`        |
| `feedback`           | NAO         | `user_id`        |

O dashboard de organizacao (`get_org_dashboard`) contorna isso agregando manualmente por `user_id` dos membros -- fazendo queries N+1 sobre `search_sessions`.

### Estado Desejado (Fase 2)

Adicionar coluna `org_id UUID REFERENCES organizations(id)` nas tabelas de dados:

```sql
ALTER TABLE pipeline_items      ADD COLUMN org_id UUID REFERENCES public.organizations(id);
ALTER TABLE search_sessions     ADD COLUMN org_id UUID REFERENCES public.organizations(id);
ALTER TABLE messages            ADD COLUMN org_id UUID REFERENCES public.organizations(id);
ALTER TABLE saved_searches      ADD COLUMN org_id UUID REFERENCES public.organizations(id);
```

**Regras de propagacao:**

1. **Ao criar recurso:** se usuario tem membership ativa (`accepted_at IS NOT NULL`), preencher `org_id` automaticamente (via trigger ou application layer)
2. **Ao consultar:** membros da mesma organizacao veem recursos uns dos outros (via RLS `org_id = ANY(member_org_ids)`)
3. **Viewer:** ve apenas dados de outros membros (read-only), sem criar/excluir
4. **Member:** ve e cria dados da organizacao
5. **Owner:** controle total, incluindo exclusao de dados de outros membros
6. **Usuario sem org:** comportamento atual (single-player, sem org_id)

### Gatilhos de Preenchimento

Opcao A (recomendada) -- **Application layer**: middleware ou helper que, apos autenticacao, injeta `org_id` nos inserts se o usuario tem membership ativa.

Opcao B -- **PostgreSQL trigger**: `BEFORE INSERT` em cada tabela que busca a org do usuario. Mais performatico mas menos flexivel.

### Impacto em Queries Existentes

Para usuarios sem org (single-player), `org_id = NULL` e as queries existentes continuam funcionando sem alteracao. Para usuarios com org, adicionar filtro `WHERE org_id = <current_org_id>` nas queries de listagem.

## Billing Model

### Estado Atual

Faturamento e **por usuario**: cada usuario tem seu proprio `plan_type` e `stripe_customer_id`. O `plan_type` da organizacao em `organizations.plan_type` existe mas NAO e usado para faturamento.

A funcao `quota_atomic.py` ja tem logica incipiente de `org_id`:
- `_lookup_user_org` busca a organizacao do usuario
- `check_and_increment_quota_atomic` aceita `org_id`
- Mas o fluxo de quota ainda nao diferencia faturamento individual vs organizacional

### Estado Desejado (Fase 3)

1. **Plano da organizacao = fonte de verdade** para todos os membros
2. **Um Stripe subscription por organizacao** (nao por usuario)
3. **Seats:** `organizations.seats_used <= organizations.max_members`
4. **Mudanca de plano:** owner altera plano da org, que afeta todos os membros
5. **Quota:** contador consolidado por org (nao por usuario)
   - `check_and_increment_quota_atomic(org_id, max_quota)` quando org_id presente
   - Fallback para `user_id` quando sem org

### Matriz de Capabilities por Plano

| Capability    | Single-player (free_trial/pro) | Organization (consultoria) |
|---------------|-------------------------------|---------------------------|
| Buscas/mes    | Individual                    | Consolidado por org       |
| Pipeline      | Individual                    | Compartilhado entre membros |
| Exportacoes   | Individual                    | Qualquer membro pode exportar |
| Membros       | 1                             | max_members (5 default)   |
| Faturamento   | Por usuario                   | Por org (1 subscription)  |

### Transicao de Billing

Usuarios existentes do plano Consultoria que criarem organizacao:
- Conta individual existente vira membro da org
- Subscription Stripe migrada da conta individual para a org
- `profiles.plan_type` mantido para compatibilidade mas `organizations.plan_type` passa a ser fonte de verdade

## Data Isolation (RLS)

### Estado Atual

RLS existe apenas nas tabelas `organizations` e `organization_members`:
- Members veem a organizacao e seus membros (politicas atualizadas pelo RBAC-ORG-001)
- Service role tem acesso total

### Estado Desejado (Fase 2)

Para cada tabela de dados com `org_id`, adicionar politica RLS:

```sql
-- Exemplo: pipeline_items
CREATE POLICY "Org members can view org pipeline items"
  ON pipeline_items
  FOR SELECT
  USING (
    org_id IS NULL  -- single-player: visivel apenas para o owner
    OR org_id IN (
      SELECT om.org_id FROM organization_members om
      WHERE om.user_id = auth.uid() AND om.accepted_at IS NOT NULL
    )
  );

CREATE POLICY "Org members can insert org pipeline items"
  ON pipeline_items
  FOR INSERT
  WITH CHECK (
    org_id IS NULL
    OR org_id IN (
      SELECT om.org_id FROM organization_members om
      WHERE om.user_id = auth.uid()
        AND om.role IN ('owner', 'member')
        AND om.accepted_at IS NOT NULL
    )
  );
```

### Principio de Isolamento

1. **Single-player (org_id = NULL):** visivel apenas para o `user_id` dono do registro (politica existente)
2. **Multi-tenant (org_id = preenchido):** visivel para todos os membros da org (com restricao de role para write)
3. **Cross-org invisivel:** um membro da Organizacao A NAO pode ver dados da Organizacao B
4. **Owner tem controle total:** pode ler, escrever e deletar dados de qualquer membro da org

## Migration Plan: Single-Player para Multi-Tenant

### Premissas

1. Usuarios existentes do plano Consultoria (`plan_type = 'consultoria'`) sao candidatos naturais para adocao de organizacao
2. Usuarios `free_trial` e `smartlic_pro` continuam como single-player ate criarem ou serem convidados a uma org
3. A migracao e **opt-in** -- ninguem e automaticamente colocado em uma organizacao sem acao explicita

### Passos

#### Fase 0: Feature Flag (JA EXISTE)

`ORGANIZATIONS_ENABLED` controla se as rotas de organizacao estao disponiveis. Default: false.

#### Fase 1: Criacao de Organizacao (JA EXISTE)

Usuario existente cria org via `POST /v1/organizations`:
- Owner inserido automaticamente
- Convites enviados por email
- Aceite via `POST /v1/organizations/{org_id}/accept`

#### Fase 2: Propagacao de org_id + RLS (NAO EXISTE)

1. Adicionar coluna `org_id` nas tabelas de dados (ALTER TABLE)
2. Criar RLS policies para as tabelas
3. Backfill: script `backfill_org_id.py` que, para cada org, associa registros existentes dos membros a org_id
4. Atualizar queries de listagem para incluir `org_id` no WHERE

#### Fase 3: Billing por Org (NAO EXISTE)

1. Modificar `services/billing.py` para suportar subscription por org
2. Migrar subscriptions existentes de plano Consultoria para a org
3. Atualizar `quota_atomic.py` para usar org_id como primary key de quota
4. Dashboard de faturamento consolida por org

#### Fase 4: Default Org (NAO EXISTE, FUTURO)

Quando o modelo estiver maduro:
- Criar organizacao automatica para todo novo usuario do plano Consultoria
- Eventualmente, estender para todos os planos pagos (cada conta = organizacao de 1 pessoa)

### Rollback

Cada fase tem rollback:
- **Fase 2:** DROP COLUMN org_id nas tabelas, DROP POLICY, reverter queries
- **Fase 3:** Manter subscriptions por usuario como fallback, flag `BILLING_PER_ORG_ENABLED`

## Endpoints Existentes (8)

| Metodo | Rota                                           | Auth            | Role Minima | Descricao                  |
|--------|------------------------------------------------|-----------------|-------------|----------------------------|
| GET    | `/v1/organizations/me`                         | require_auth    | --          | Retorna org do usuario logado |
| POST   | `/v1/organizations`                            | require_auth    | --          | Criar organizacao (virar owner) |
| GET    | `/v1/organizations/{org_id}`                   | require_auth    | member      | Detalhes da organizacao    |
| POST   | `/v1/organizations/{org_id}/invite`            | require_auth    | owner       | Convidar membro            |
| POST   | `/v1/organizations/{org_id}/accept`            | require_auth    | --          | Aceitar convite            |
| DELETE | `/v1/organizations/{org_id}/members/{user_id}` | require_auth    | owner       | Remover membro             |
| GET    | `/v1/organizations/{org_id}/dashboard`         | require_auth    | owner       | Dashboard consolidado      |
| PUT    | `/v1/organizations/{org_id}/logo`              | require_auth    | owner       | Atualizar logo             |

### Paridade Rotas-Responses

Todas as responses usam `_PermissiveBase` (schemas em `backend/schemas/parity.py`):
- `OrganizationResponse` -- id, name, owner_id, plan_id, seats_used, created_at
- `OrganizationMembershipResponse` -- organization_id, role, organization
- `OrganizationInviteResponse` -- invite_id, invite_token, invite_url, expires_at
- `OrganizationAcceptResponse` -- organization_id, role, success
- `OrganizationMemberRemovedResponse` -- success, removed_user_id
- `OrganizationDashboardResponse` -- organization_id, members_count, seats_used, pipeline_count, searches_30d
- `OrganizationLogoUpdatedResponse` -- success, logo_url

### Endpoints Futuros

| Metodo | Rota                                           | Role     | Descricao                                          |
|--------|------------------------------------------------|----------|----------------------------------------------------|
| PATCH  | `/v1/organizations/{org_id}`                   | owner    | Atualizar config (max_members, nome)               |
| GET    | `/v1/organizations/{org_id}/billing`           | owner    | Resumo de faturamento e subscription               |
| POST   | `/v1/organizations/{org_id}/transfer`          | owner    | Transferir ownership                               |
| GET    | `/v1/organizations/{org_id}/members`           | member   | Listar membros (substituto do GET org)             |
| POST   | `/v1/organizations/{org_id}/leave`             | member, viewer | Sair da organizacao                         |

## Schema Overview

### organizations

| Coluna             | Tipo        | Default           | Notas                                                |
|--------------------|-------------|-------------------|------------------------------------------------------|
| id                 | UUID        | gen_random_uuid() | PK                                                   |
| name               | TEXT        | --                | Nome da organizacao                                  |
| logo_url           | TEXT        | NULL              | URL do logo no storage                               |
| owner_id           | UUID        | --                | FK `auth.users(id)` ON DELETE RESTRICT               |
| max_members        | INT         | 5                 | Limite de membros                                    |
| plan_type          | TEXT        | 'consultoria'     | Plano de faturamento                                 |
| stripe_customer_id | TEXT        | NULL              | Stripe customer ID                                   |
| created_at         | TIMESTAMPTZ | NOW()             | --                                                   |
| updated_at         | TIMESTAMPTZ | NOW()             | Auto-update via trigger                              |

### organization_members

| Coluna      | Tipo        | Default           | Notas                                                   |
|-------------|-------------|-------------------|---------------------------------------------------------|
| id          | UUID        | gen_random_uuid() | PK                                                      |
| org_id      | UUID        | --                | FK `organizations(id)` ON DELETE CASCADE                |
| user_id     | UUID        | --                | FK `auth.users(id)` ON DELETE CASCADE                   |
| role        | TEXT        | 'member'          | CHECK: owner, member, viewer                            |
| invited_at  | TIMESTAMPTZ | NOW()             | Quando o convite foi enviado                            |
| accepted_at | TIMESTAMPTZ | NULL              | NULL = pendente                                         |

UNIQUE(org_id, user_id)

## Dependencies

- **auth.py**: `require_auth` (JWT authentication) -- pre-requisito para todas as rotas
- **dependencies/org_auth.py**: `require_org_role(min_role)` -- extrai org_id do path e valida rank
- **services/organization_service.py**: logica de negocio (criar, convidar, aceitar, remover, dashboard)
- **supabase_client**: acesso ao banco
- **config/features.py**: `ORGANIZATIONS_ENABLED` feature flag
- **schemas/parity.py**: Pydantic models (respostas das rotas)

## Invariants

1. **Route ordering:** `/organizations/me` deve vir ANTES de `/organizations/{org_id}` (FastAPI path matching)
2. **Feature flag:** `ORGANIZATIONS_ENABLED=false` por default; todas as rotas retornam 404 se desabilitado
3. **PGRST205 guard:** erros de schema (tabela inexistente) retornam HTTP 503, nao 500
4. **Org limit:** `invite_member` verifica `current_members.count < max_members`
5. **Owner protecao:** `remove_member` bloqueia remocao do owner
6. **Duplicidade:** UNIQUE(org_id, user_id) impede convites duplicados
7. **Auto-aceite:** owner inserido com `accepted_at = NOW()` -- nao precisa aceitar convite
8. **Single-player vs org:** usuarios sem membership continuam operando no modelo atual (sem org_id)
