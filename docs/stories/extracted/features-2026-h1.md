# User Stories — Features 2026 H1

> Extraidas do codigo fonte em 2026-06-17
> 8 features: RBAC granular, Circuit breaker admin, Data retention admin, Log level por sessao, Billing services, Dedup engine v2, Filter LLM zero-match, Webhook integrations
> Formato: "As a [role], I want [goal] so that [benefit]"

---

## US-RBAC-01 — Admin Roles Granulares

**Como** administrador do SmartLic
**Quero** conceder permissoes especificas (users, billing, cache, partners, seo, ops, compliance, super) para cada admin
**Para que** eu possa delegar tarefas administrativas sem dar acesso irrestrito a todo o sistema.

**Criterios de aceitacao:**
- 8 roles definidas: admin:users, admin:billing, admin:cache, admin:partners, admin:seo, admin:ops, admin:compliance, admin:super
- Cada endpoint admin verifica a role especifica antes de autorizar
- admin:super herda implicitamente todas as outras roles
- Roles armazenadas em `profiles.admin_roles` (jsonb)
- Compatibilidade retroativa com `is_admin` booleano legado
- 403 Forbidden com mensagem clara quando role insuficiente

## US-RBAC-02 — Verificacao de Role por Endpoint

**Como** desenvolvedor do SmartLic
**Quero** usar `require_admin_role("admin:billing")` como dependency em rotas admin
**Para que** a seguranca seja declarativa e consistente em toda a base de codigo.

**Criterios de aceitacao:**
- `require_admin_role(role)` retorna um FastAPI `Depends` viavel
- Roles desconhecidas lancam `ValueError`
- Consulta a `profiles.admin_roles` via Supabase com fallback silencioso para lista vazia
- Role admin:users disponivel como `require_admin_users`, admin:billing como `require_admin_billing`, etc.

---

## US-CB-01 — Monitorar Circuit Breakers

**Como** administrador de operacoes
**Quero** consultar o estado em tempo real de todos os circuit breakers do sistema (PNCP, PCP, ComprasGov, BrasilAPI, IBGE)
**Para que** eu possa diagnosticar rapidamente degradacoes em fontes de dados externas.

**Criterios de aceitacao:**
- Endpoint `GET /v1/admin/circuit-breakers` protegido por role admin:ops
- Resposta inclui: estado atual (closed/open/half-open), contagem de falhas, duracao da abertura, configuracao
- Fallback graceful com `{"circuit_breakers": {}, "error": msg}` em caso de falha
- Log warning quando a consulta falha

## US-CB-02 — Diagnosticar Degradacao de Fonte

**Como** engenheiro de plataforma
**Quero** saber qual fonte de dados esta degradada e ha quanto tempo
**Para que** eu possa priorizar correcao sem precisar accessar logs ou dashboards separados.

**Criterios de aceitacao:**
- Estado individual por fonte (PNCP, PCP, ComprasGov, BrasilAPI, IBGE)
- Metrica de duracao da degradacao (ha quanto tempo o CB esta aberto)
- Contagem de falhas desde a ultima transicao para open

---

## US-DR-01 — Monitorar Purge de Dados

**Como** administrador de operacoes
**Quero** inspecionar o ultimo ciclo de purge de dados por tabela (trial_email_log, messages, ingestion_checkpoints)
**Para que** eu possa verificar se a retencao de dados esta funcionando conforme configurado.

**Criterios de aceitacao:**
- Endpoint `GET /v1/admin/data-retention/status` protegido por role admin
- Retorna por tabela: ultimo purge timestamp, linhas purgadas, status (success/failed)
- Totais agregados: total de linhas purgadas, duracao do ultimo ciclo
- Fallback graceful quando Redis esta indisponivel
- Dados lidos de Redis escritos pelo cron `data_retention.py`, TTL 7 dias

## US-DR-02 — Verificar Cronograma de Retencao

**Como** Compliance Officer
**Quero** verificar se os dados estao sendo purgados dentro dos prazos de retencao definidos
**Para que** eu garanta conformidade com a politica de retencao de dados da empresa.

**Criterios de aceitacao:**
- Status por tabela com timestamp do ultimo purge
- Visualizacao clara de sucesso/falha por ciclo
- Capacidade de detectar ciclos que nao rodaram dentro do esperado

---

## US-LL-01 — Alterar Nivel de Log em Runtime

**Como** engenheiro de plataforma
**Quero** alterar o nivel de log de um modulo especifico (ex: ingestion) sem restartar o servidor
**Para que** eu possa debuggar problemas em producao sem impacto aos usuarios.

**Criterios de aceitacao:**
- Endpoint `POST /v1/admin/log-level` protegido por role admin:ops
- Body: `{level: "DEBUG"|"INFO"|"WARNING"|"ERROR", logger: "ingestion"|"*", ttl_seconds: 300}`
- Suporta root logger (`*`) e loggers especificos (ex: `ingestion`, `filter`, `auth`)
- TTL configuravel em segundos para auto-reversao ao nivel original
- Background task (asyncio) verifica expiracao a cada 30s

## US-LL-02 — Listar Loggers Modificados

**Como** engenheiro de plataforma
**Quero** consultar quais loggers estao com nivel alterado, por quem e ha quanto tempo
**Para que** eu nao esqueca de reverter alteracoes temporarias de debug.

**Criterios de aceitacao:**
- Endpoint `GET /v1/admin/log-level` retorna lista de loggers modificados
- Response inclui: logger, nivel original, nivel atual, user_id que alterou, timestamp, TTL restante
- Visivel apenas para admins com role admin:ops

---

## US-BL-01 — Gerenciar Assinatura

**Como** usuario pagante do SmartLic
**Quero** gerenciar minha assinatura (upgrade, downgrade, cancelar, ver status)
**Para que** eu possa adequar o plano as necessidades da minha empresa sem falar com suporte.

**Criterios de aceitacao:**
- `POST /v1/checkout` cria Stripe Checkout Session para upgrade
- `POST /v1/billing-portal` gera link para Stripe Customer Portal
- `GET /v1/subscription/status` retorna status atual e proxima cobranca
- Cancelamento respeita periodo vigente (sem reembolso parcial)
- Stripe lida com proration automaticamente
- 3 dias de grace period apos expiracao antes de downgrade

## US-BL-02 — Receber Notificacoes de Faturamento

**Como** usuario pagante
**Quero** receber email quando minha fatura for paga com sucesso ou quando o pagamento falhar
**Para que** eu possa agir rapidamente se houver problema com meu metodo de pagamento.

**Criterios de aceitacao:**
- Webhook `invoice.payment_succeeded` envia email de confirmacao
- Webhook `invoice.payment_failed` envia email de alerta com link para atualizar metodo de pagamento
- Webhook `customer.subscription.trial_will_end` envia lembrete 3 dias antes
- Todos os webhooks tem signature validation Stripe

## US-BL-03 — Visualizar Planos e Precos

**Como** visitante do site
**Quero** ver os planos disponiveis com precos e capacidades
**Para que** eu possa decidir qual plano atende minhas necessidades antes de criar conta.

**Criterios de aceitacao:**
- `GET /v1/plans` retorna lista publica de planos
- Cada plano mostra: nome, preco, capacidades (historico, excel, pipeline, quota)
- Planos: free_trial (14d gratis), smartlic_pro (R$397/mes), founding_member (R$197/mes), consultoria (R$997/mes)

---

## US-DD-01 — Deduplicar Resultados Multi-Fonte

**Como** usuario buscando editais
**Quero** ver resultados consolidados sem duplicatas quando a mesma licitacao aparece em PNCP, PCP e ComprasGov
**Para que** eu nao perca tempo analisando o mesmo edital varias vezes.

**Criterios de aceitacao:**
- 5 layers de dedup rodam em sequencia
- source_id exact dedup (mesmo PNCP ID)
- dedup_key exact dedup cross-source (vence por prioridade: PNCP > PCP > ComprasGov)
- Fuzzy Jaccard dedup toggle via `DEDUP_FUZZY_ENABLED`
- Campos enriquecidos do duplicado: valor_estimado, modalidade, orgao, objeto
- Zero falso-positivo em fuzzy dedup (threshold configuravel)

## US-DD-02 — Manter Qualidade de Dados

**Como** engenheiro de dados
**Quero** configurar thresholds de fuzzy dedup e monitorar taxa de merge
**Para que** eu possa ajustar o equilibrio entre recall e precisao na deduplicacao.

**Criterios de aceitacao:**
- Feature flag `DEDUP_FUZZY_ENABLED` para toggle on/off
- Threshold `DEDUP_FUZZY_THRESHOLD` via env var
- Metricas Prometheus: `DEDUP_FIELDS_MERGED` por campo, `DEDUP_FUZZY_HITS`
- Stopwords PT-BR (230 termos) para limpeza de texto antes do Jaccard

---

## US-ZM-01 — Classificar Zero-Match por IA

**Como** usuario de um setor especifico
**Quero** que licitacoes sem keywords exatas sejam avaliadas por IA para decidir se sao relevantes
**Para que** eu nao perca oportunidades que usam terminologia diferente da minha busca.

**Criterios de aceitacao:**
- Items com 0% keyword density sao enviados para classificacao LLM batch
- GPT-4.1-nano decide YES/NO para cada item
- Ate 20 itens por chamada LLM
- Items YES sao reintroduzidos no pipeline como `source: llm_zero_match`
- Se count mismatch entre items enviados e respostas -> rejeita TODOS (zero-noise rule)
- Cache 2-tier: L1 LRU 5000 + L2 Redis

## US-ZM-02 — Configurar Fallback de Classificacao

**Como** administrador do sistema
**Quero** configurar se items zero-match sem classificacao LLM vao para PENDING_REVIEW ou sao rejeitados
**Para que** eu possa equilibrar recall (nao perder oportunidades) vs precisao (nao poluir resultados).

**Criterios de aceitacao:**
- Feature flag `LLM_ZERO_MATCH_ENABLED` (default true) liga/desliga o modulo
- Feature flag `LLM_FALLBACK_PENDING_ENABLED` (default true) controla fallback
- Quando true: items sem classificacao vao para PENDING_REVIEW
- Quando false: items sem classificacao sao rejeitados
- Cache de classificacoes (LRU + Redis) evita re-classificar o mesmo item

---

## US-WH-01 — Integrar Webhooks de Pagamento

**Como** plataforma SmartLic
**Quero** receber e processar webhooks do Stripe para eventos de checkout, subscription e invoice
**Para que** o ciclo de vida de assinaturas seja atualizado automaticamente sem intervencao manual.

**Criterios de aceitacao:**
- 12 eventos Stripe tratados: checkout.session.completed, customer.subscription.created/updated/deleted/trial_will_end, invoice.payment_succeeded/failed/payment_action_required, checkout.session.async_payment_succeeded/failed/expired
- Signature validation via `stripe.Webhook.construct_event` (rejeita webhooks forjados)
- Idempotencia via `INSERT ... ON CONFLICT DO NOTHING` em `stripe_webhook_events`
- Timeout de 30s por handler (`asyncio.wait_for`)
- Audit trail completo em `stripe_webhook_events`

## US-WH-02 — Estender Webhooks para Novos Recursos

**Como** desenvolvedor
**Quero** adicionar novos handlers de webhook sem modificar o dispatcher central
**Para que** o sistema seja extensivel e facil de manter.

**Criterios de aceitacao:**
- Dispatcher thin router em `webhooks/stripe.py` — apenas validacao + roteamento
- Handlers organizados por recurso em `webhooks/handlers/` (checkout.py, subscription.py, invoice.py, api_checkout.py, founding.py, stripe_product_price.py)
- Handler base (`_base.py`) com helpers compartilhados
- Registry (`_registry.py`) para mapeamento evento -> handler
- Stuck recovery: eventos `processing` >5min -> log WARN + retoma processamento
