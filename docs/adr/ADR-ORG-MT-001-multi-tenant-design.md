# ADR-ORG-MT-001: Multi-Tenant Design for Organizations

**Status:** Accepted
**Date:** 2026-06-17
**Issue:** #1963 (P1 Multi-tenant organizations spec)
**Owners:** @architect, @dev
**Related:** ADR-ORG-RBAC (docs/adr/org-rbac.md), STORY-322, RBAC-ORG-001, ADR-RLS-MANDATORY-001

---

## Context

SmartLic possui tabelas `organizations` e `organization_members` desde STORY-322 (2026-03-01). Existem 8 endpoints em `routes/organizations.py` para CRUD de organizacao, convite de membros e dashboard. O RBAC foi implementado (RBAC-ORG-001 com roles owner/member/viewer) e documentado no ADR-ORG-RBAC.

**Porem, o modelo multi-tenant esta incompleto em 3 dimensoes:**

1. **org_id nao propagado** -- `pipeline_items`, `search_sessions`, `messages`, `saved_searches` e demais tabelas de dados pertencem ao usuario individual (`user_id`). Nao ha coluna `org_id` nessas tabelas. O dashboard de organizacao faz agregacao N+1 por `user_id` dos membros.

2. **Faturamento por usuario, nao por org** -- Cada usuario tem seu proprio `plan_type`, `stripe_customer_id` e subscription. O campo `organizations.plan_type` existe mas nunca e usado para faturamento. Um plano Consultoria com 5 membros paga 5x o valor individual.

3. **Sem plano de migracao** -- Usuarios existentes sao single-player. Quando criam ou entram em uma org, nao ha mecanismo para migrar seus dados, subscription ou preferencias.

Sem estas 3 dimensoes, o produto nao pode ser usado como uma plataforma multi-usuario real para consultorias e agencias -- o principal caso de uso do plano `smartlic_consultoria`.

## Decision

### Decisao 1: org_id propagation via Application Layer (Fase 2)

Adicionar coluna `org_id UUID REFERENCES organizations(id)` nas tabelas de dados transacionais. O preenchimento sera feito via **application layer** (middleware ou helper), nao via trigger de banco.

**Por que application layer:**
- Triggers de banco sao silenciosos -- o codigo da aplicacao nao sabe que o `org_id` foi preenchido, podendo causar inconsistencias de cache ou logging
- A logica de "qual org o usuario pertence?" ja existe em `quota_atomic.py` (`_lookup_user_org`)
- Consistency: o mesmo codigo que insere o recurso decide o `org_id`, garantindo que cache, auditoria e notificacoes estejam alinhados
- Triggers seriam uma segunda fonte de verdade para a mesma regra de negocio

**Tabelas afetadas:**

| Tabela | Prioridade | Justificativa |
|--------|-----------|---------------|
| `pipeline_items` | P0 | Kanban compartilhado e a principal superficie de retencao |
| `search_sessions` | P0 | Buscas e o coracao do produto; dashboard de org precisa disso |
| `saved_searches` | P1 | Buscas salvas devem ser visiveis para a equipe |
| `messages` | P1 | Mensagens de suporte InMail sao por usuario, mas org pode querer visibilidade |
| `exports` | P2 | Exportacoes podem ser compartilhadas |
| `feedback` | P2 | Feedback de classificacao pode ser revisto pela equipe |

**Exclusoes intencionais:**
- `search_results_cache` -- cache e ephemeral e nao carrega semantica de propriedade. Manter por `user_id`.
- `pncp_raw_bids`, `pncp_supplier_contracts` -- dados publicos de licitacao. Nao sao propriedade do usuario.

### Decisao 2: Billing por Organizacao (Fase 3)

**Cada organizacao tem uma unica subscription Stripe.** O owner gerencia o plano. Todos os membros compartilham a quota mensal da org.

**Por que per-org e nao per-user:**
- Alinhamento com valor percebido: consultorias compram um plano para a equipe, nao por pessoa
- Simplicidade de gestao: 1 fatura, 1 subscription, 1 ciclo de cobranca
- Preco previsivel: o custo por assento e uma divisao simples do plano
- Stripe ja suporta: podemos usar `stripe_customer_id` na tabela `organizations`

**Impacto no codigo:**
- `quota_atomic.py` ja tem `_lookup_user_org` -- estender para fazer `check_and_increment_quota_atomic(org_id, ...)` quando `org_id` presente
- Webhooks Stripe que atualmente atualizam `profiles.plan_type` devem tambem (ou em vez disso) atualizar `organizations.plan_type`
- `profiles.plan_type` mantido para compatibilidade com usuarios single-player

### Decisao 3: RLS por org_id (Fase 2)

Cada tabela com `org_id` recebe 3 politicas RLS:

1. **SELECT:** `org_id IS NULL OR org_id IN (orgs do usuario)` -- membro ve dados da org + proprios
2. **INSERT:** `org_id IS NULL OR org_id IN (orgs com role owner/member)` -- viewer NAO pode criar
3. **DELETE:** `org_id IS NULL OR org_id IN (orgs com role owner)` -- apenas owner deleta dados da org

Usuarios single-player (`org_id = NULL`) continuam protegidos pelas politicas existentes baseadas em `user_id`.

### Decisao 4: Migracao Opt-In (todas as fases)

Nenhum usuario existente e automaticamente colocado em uma organizacao. A migracao e sempre iniciada por acao do usuario:

1. Usuario cria org via `POST /v1/organizations`
2. Convida membros por email
3. Aceitacao do convite vincula o usuario a org
4. Dados criados ANTES da membership continuam com `org_id = NULL` (single-player)
5. Dados criados DEPOIS da membership recebem `org_id` automaticamente

**Backfill:** script `backfill_org_id.py` para associar registros existentes a `org_id` quando o owner optar.

**Rollback:** cada ALTER TABLE tem `.down.sql` correspondente (DROP COLUMN + DROP POLICY).

## Consequences

### Positivas

1. **Produto completo para Consultoria:** usuarios de uma org compartilham pipeline, buscas e resultados
2. **Faturamento previsivel:** 1 subscription por org, custo claro
3. **Isolamento LGPD:** RLS garante que dados da Org A nao vazam para Org B
4. **Backwards compatible:** usuarios single-player continuam funcionando sem alteracao
5. **Rollback viavel:** cada fase tem `.down.sql` e feature flag

### Negativas

1. **Complexidade de migracao:** usuarios que criarem org precisarao decidir sobre backfill de dados existentes
2. **Quota compartilhada:** um membro pode consumir toda a quota mensal da org, afetando os demais (mitigacao: alertas de quota no dashboard + notificacao ao owner)
3. **Stripe migration:** subscriptions existentes de usuarios Consultoria precisam ser migradas para a org -- operacao delicada que requer comunicacao com o cliente
4. **Carga cognitiva extra:** cada nova tabela que precisar de `org_id` no futuro exigira ALTER TABLE + RLS + consistent

### Implementacao Detalhada

- **Spec completo:** `_reversa_sdd/specs/15-organizations.md`
- **Schema:** Supabase migrations com `.sql` + `.down.sql`
- **org_id propagation:** middleware em `dependencies/org_context.py` (analogo a `require_org_role` mas para injecao de dados)
- **RLS:** migrations sequenciais (uma por tabela)
- **Billing:** modificacao em `services/billing.py`, `quota/quota_atomic.py` e webhooks Stripe
- **Feature flags:** `ORGANIZATIONS_ENABLED` (existente) + `BILLING_PER_ORG_ENABLED` (Fase 3)

## Alternatives Considered

### Alternativa 1: Triggers de Banco para org_id

**Proposta:** Usar `BEFORE INSERT` trigger em cada tabela para buscar `org_id` do usuario automaticamente.

**Rejeitada porque:**
- Trigger opera fora do contexto da aplicacao -- sem acesso a cache, logging estruturado ou rollback consistente
- Se o trigger falhar (ex: query lenta em `organization_members`), o INSERT falha silenciosamente
- Dificil de debugar: o erro aparece no log do banco, nao no da aplicacao
- Triggers sao invisiveis para desenvolvedores que olham so o codigo Python

### Alternativa 2: 2-Tier Role (owner + member apenas)

**Proposta:** Remover `viewer`, simplificar para owner/member.

**Rejeitada porque:**
- ADR-ORG-RBAC ja documentou a decisao de 3-tier para cobrir casos de uso reais:
  - Clientes da consultoria que precisam apenas visualizar resultados
  - Estagiarios ou auditors que nao devem poder criar/modificar dados
- RBAC-ORG-001 ja implementou `viewer` com CHECK constraint e RLS
- Remover agora seria rework sem ganho proporcional

### Alternativa 3: Billing Misto (por org + por user extra)

**Proposta:** Plano base para a org + custo adicional por member extra (ex: R$50/mes por member adicional apos os 2 primeiros).

**Rejeitada para Fase 1 porque:**
- Stripe `max_members` + proration e complexo de implementar corretamente
- Preco unico por org simplifica a comunicacao com o cliente
- Pode ser revisitado como Feature v2 se houver demanda de mercado

### Alternativa 4: Default Org Automatica para Todos

**Proposta:** Criar uma organizacao automatica para cada usuario no momento do signup.

**Rejeitada porque:**
- Quebra o modelo atual onde usuario single-player nao tem `org_id`
- Adiciona complexidade desnecessaria para 95% dos usuarios que sao individuais (free_trial e pro)
- Melhor abordagem: Fase 4 (futuro) para plano Consultoria, nunca para free_trial

## Revision

Este ADR e canonico ate que uma das decisoes seja alterada. Cada Fase (2, 3, 4) pode ser revisitada independentemente com novo ADR. A hierarquia de roles (owner/member/viewer) e coberta pelo ADR-ORG-RBAC separado.
