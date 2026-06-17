# Data Dictionary — SmartLic Database Schema

**Ultima atualizacao:** 2026-06-17
**Fonte:** `supabase/migrations/` (source of truth)
**Total de tabelas:** 95

Catalogo completo de todas as tabelas gerenciadas via Supabase Migrations. Organizado por dominio funcional
com definicoes de colunas, constraints e status RLS.

**Convencoes:**
- `[NOVO 2026-{mes}]` = tabela adicionada nos ultimos 3 meses (Mar-Jun 2026)
- `[NOVO]` = coluna adicionada a tabela pre-existente no mesmo periodo
- RLS = Row Level Security habilitado (controle de acesso por linha)

## Sumario de Tabelas

| Dominio | Tabela | Cols | Criada em | RLS | Descricao |
|---------|--------|------|-----------|-----|----------|
| **Core Identity** | `profiles` | 43 | 001_profiles_and_sessions | SIM | Tabela central de identidade do usuario. Vinculada ao Supabase Auth. Armazena perfil, plano, permissoes e estado da assinatura. |
| | `plans` | 18 | 001_profiles_and_sessions | SIM | Catalogo de planos de assinatura. Define tiers (Free, Pro, Consultoria) com precos, feature flags e cotas. |
| | `plan_features` | 8 | 009_create_plan_features | SIM | Mapeamento de funcionalidades por plano. Conecta recursos (booleano, limite numerico) a tiers. |
| | `plans_audit` [NOVO Mai 2026] | 8 | 2026-05-09 | SIM | Log de auditoria de alteracoes no catalogo de planos (trigger-based). |
| | `user_subscriptions` | 15 | 001_profiles_and_sessions | SIM | Estado atual da assinatura do usuario. Vincula Stripe subscription ID ao plano e periodo. |
| | `plan_billing_periods` | 12 | 029_single_plan_model | SIM | Mapeamento de ciclos de cobranca por plano (mensal, semestral, anual) com Stripe price IDs. |
| | `admin_roles` [NOVO Jun 2026] | 4 | 2026-06-15 | SIM | Concessao de papeis administrativos. Controla acesso a endpoints /admin, gestao de cobranca e config. |
| | `user_oauth_tokens` | 9 | 013_google_oauth_tokens | SIM | Armazenamento seguro de tokens OAuth para integracoes com APIs de terceiros. |
| **Auth & Security** | `auth_attempts` [NOVO Abr 2026] | 5 | 2026-04-28 | SIM | Log de tentativas de autenticacao. Detecta forca bruta e rate limiting. |
| | `mfa_recovery_codes` | 5 | 2026-02-28 | SIM | Codigos de recuperacao MFA (uso unico). Fallback para autenticacao multifator. |
| | `mfa_recovery_attempts` | 4 | 2026-02-28 | SIM | Log de uso de codigos de recuperacao MFA para auditoria de seguranca. |
| | `audit_events` | 8 | 023_audit_events | SIM | Log de auditoria do sistema. Eventos de seguranca (login, mudanca de papel, acesso a dados). |
| | `login_activity` [NOVO Jun 2026] | 3 | 2026-06-04 | SIM | Log de atividade de login. Registra timestamps, IP e user-agent para monitoramento. |
| | `api_keys` [NOVO Jun 2026] | 7 | 2026-06-02 | SIM | Gerenciamento de chaves de API para desenvolvedores. Chaves hasheadas com escopos e limites. |
| **Search & Discovery** | `search_sessions` | 25 | 001_profiles_and_sessions | SIM | Log de sessoes de busca do usuario. Registra consultas, filtros, resultados e status. |
| | `search_state_transitions` | 9 | 2026-02-21 | SIM | Maquina de estado de sessoes de busca. Transicoes: pending -> processing -> complete/error. |
| | `search_results_cache` | 20 | 026_search_results_cache | SIM | Cache L2 de resultados de busca. Metadados com TTL para re-consulta rapida. |
| | `search_results_store` [NOVO Mar 2026] | 8 | 2026-03-03 | SIM | Armazenamento persistente de resultados completos de busca. Payloads arquivados para recuperacao assincrona. |
| | `pncp_raw_bids` [NOVO Mar 2026] | 26 | 2026-03-26 | SIM | Tabela central de ingestao de licitacoes do PNCP. ~1.5M linhas, 400d de retencao. |
| | `saved_filter_presets` [NOVO Abr 2026] | 6 | 2026-04-09 | SIM | Presets de filtros de busca salvos pelo usuario. Reutilizacao de combinacoes complexas. |
| **Supplier Data** | `pncp_supplier_contracts` [NOVO Abr 2026] | 21 | 2026-04-09 | SIM | Contratos de fornecedores. Dados de contratos adjudicados do PNCP para inteligencia competitiva. |
| | `enriched_entities` [NOVO Abr 2026] | 4 | 2026-04-10 | SIM | Entidades enriquecidas. Metadados adicionais de fontes externas para orgaos e fornecedores. |
| | `cnae_setores` [NOVO Mai 2026] | 4 | 2026-05-05 | SIM | Mapeamento CNAE para setores SmartLic. Codigos CNAE para as 20 categorias setoriais. |
| | `cnae_setor_mapping` [NOVO Mai 2026] | 8 | 2026-05-11 | SIM | Mapeamento extendido CNAE-setor com scoring de confianca e status de validacao. |
| | `indice_municipal` [NOVO Abr 2026] | 16 | 2026-04-11 | SIM | Indices municipais de contratacao. Indicadores pre-computados por municipio para benchmarking. |
| | `classification_feedback` [NOVO Mar 2026] | 14 | 2026-03-08 | SIM | Feedback do usuario sobre classificacao setorial da IA. Correcoes para melhoria do modelo. |
| **Billing & Revenue** | `monthly_quota` | 6 | 002_monthly_quota | SIM | Cota mensal de consultas por usuario. Controla limite de chamadas de API por periodo de cobranca. |
| | `stripe_webhook_events` | 6 | 010_stripe_webhook_events | SIM | Log de eventos webhook do Stripe. Idempotencia e auditoria de eventos de pagamento. |
| | `reconciliation_log` | 8 | 2026-02-28 | SIM | Log de reconciliacao de cobranca Stripe-banco de dados. |
| | `billing_reconciliation_runs` [NOVO Abr 2026] | 11 | 2026-04-28 | SIM | Log de execucao automatica de reconciliacao de cobranca. |
| | `admin_billing_audit_log` [NOVO Abr 2026] | 12 | 2026-04-28 | SIM | Trilha de auditoria de operacoes administrativas de cobranca. Reembolsos, ajustes, cambios de plano. |
| | `api_subscriptions` [NOVO Jun 2026] | 11 | 2026-06-06 | SIM | Planos de assinatura de API. Define tiers, rate limits, cotas e precos de API. |
| | `api_usage_records` [NOVO Jun 2026] | 7 | 2026-06-06 | SIM | Registros de uso de API. Contagem de chamadas por chave e periodo para cobranca metered. |
| | `api_metered_billing_cron_log` [NOVO Jun 2026] | 7 | 2026-06-06 | nao | Log de execucao cron de cobranca metered de API. |
| | `digital_products` [NOVO Mai 2026] | 12 | 2026-05-31 | SIM | Catalogo de produtos digitais avulsos. Relatorios, datasets e conteudo premium fora de assinatura. |
| **Alerts & Notifications** | `alerts` | 9 | 2026-02-27 | SIM | Alertas de licitacao definidos pelo usuario. Criterios configurados para notificacao de novas oportunidades. |
| | `alert_preferences` | 7 | 2026-02-26 | SIM | Preferencias de notificacao de alertas. Canais (email, in-app) e frequencia. |
| | `alert_runs` | 6 | 2026-02-28 | SIM | Log de execucao de alertas. Registro de cada gatilho com contagem de resultados e status. |
| | `alert_sent_items` | 4 | 2026-02-27 | SIM | Log de entregas de notificacao de alertas. Itens individuais enviados por evento. |
| | `user_alerts` [NOVO Jun 2026] | 9 | 2026-06-17 | SIM | Alertas gerados para o usuario. Categoria, severidade e acao. Ciclo de leitura/dismiss. |
| | `user_alert_preferences` [NOVO Jun 2026] | 7 | 2026-06-17 | SIM | Configuracao de canais e frequencia de alertas por usuario. |
| | `competitive_alerts` [NOVO Jun 2026] | 7 | 2026-06-12 | SIM | Alertas de inteligencia competitiva. Notifica vitorias de concorrentes e atividade de mercado. |
| | `predictive_alerts` [NOVO Jun 2026] | 10 | 2026-06-12 | SIM | Alertas preditivos gerados por ML. Previsoes de oportunidades futuras. |
| | `email_tracking_events` [NOVO Jun 2026] | 7 | 2026-06-06 | SIM | Eventos de email do Resend. Entrega, abertura, clique, bounce, reclamação. |
| **Organizations & Teams** | `organizations` [NOVO Mar 2026] | 9 | 2026-03-01 | SIM | Contas multi-tenant. Agrupa usuarios em organizacoes para acesso em equipe. |
| | `organization_members` [NOVO Mar 2026] | 6 | 2026-03-01 | SIM | Mapeamento de membros da organizacao. Vincula perfis a organizacoes com papeis. |
| | `workspace_watchlists` [NOVO Mai 2026] | 9 | 2026-05-31 | SIM | Watchlists colaborativas de licitacoes. Equipes monitoram oportunidades juntas. |
| | `workspace_watchlist_matches` [NOVO Mai 2026] | 6 | 2026-05-31 | SIM | Matches de watchlist com licitacoes. Vincula notices aos criterios da watchlist. |
| | `workspace_timeline` [NOVO Jun 2026] | 12 | 2026-06-01 | SIM | Linha do tempo de atividades do workspace. Log sequencial para auditoria da equipe. |
| | `workspace_war_rooms` [NOVO Jun 2026] | 8 | 2026-06-02 | SIM | Salas de decisao go/no-go. Espacos para analise colaborativa de editais. |
| | `workspace_war_room_members` [NOVO Jun 2026] | 6 | 2026-06-02 | SIM | Membros da war room com permissoes. Vincula perfis a war rooms. |
| | `workspace_war_room_log` [NOVO Jun 2026] | 7 | 2026-06-02 | SIM | Log de decisoes e atividades da war room. Decisoes, votos e comentarios. |
| | `workspace_documents` [NOVO Jun 2026] | 14 | 2026-06-02 | SIM | Documentos do workspace para preparacao de propostas. RFP, templates, propostas. |
| **Leads & CRM** | `leads` [NOVO Abr 2026] | 18 | 2026-04-07 | SIM | Leads de vendas e marketing. Inbound de multiplos canais com dados de qualificacao. |
| | `lead_captures` [NOVO Mai 2026] | 7 | 2026-05-12 | SIM | Captura de leads de paginas de marketing. Atribuicao de fonte e dados de contato. |
| | `referrals` [NOVO Abr 2026] | 7 | 2026-04-05 | SIM | Indicacoes de usuarios. Status e recompensas. |
| | `report_leads` [NOVO Abr 2026] | 8 | 2026-04-05 | SIM | Relatorios e exportacoes de leads. Criterios de filtro e metadados de exportacao. |
| | `founding_leads` [NOVO Abr 2026] | 15 | 2026-04-20 | SIM | Leads do programa de membros fundadores. Convite-based com status. |
| | `founding_policy` [NOVO Abr 2026] | 14 | 2026-04-28 | SIM | Politica do programa de membros fundadores. Regras, beneficios e expiracao. |
| | `founding_policy_audit_log` [NOVO Mai 2026] | 7 | 2026-05-07 | SIM | Auditoria de mudancas na politica de fundadores. Estado anterior/posterior. |
| | `partners` [NOVO Mar 2026] | 10 | 2026-03-01 | SIM | Contas de parceiros/afiliados. Consultores, revendedores e canais. |
| | `partner_referrals` [NOVO Mar 2026] | 8 | 2026-03-01 | SIM | Indicacoes de parceiros. Status, comissao e conversao. |
| | `consultant_clients` [NOVO Jun 2026] | 5 | 2026-06-12 | SIM | Vinculo consultor-cliente. Contas de consultoria a perfis de clientes gerenciados. |
| | `consultant_shares` [NOVO Jun 2026] | 6 | 2026-06-12 | SIM | Recursos compartilhados por consultores. Relatorios e analises compartilhados com clientes. |
| **Intelligence Reports** | `intel_report_purchases` [NOVO Mai 2026] | 9 | 2026-05-05 | SIM | Compras de relatorios de inteligencia avulsos. |
| | `shared_analyses` [NOVO Abr 2026] | 15 | 2026-04-05 | SIM | Analises compartilhadas. Links publicos/privados para visualizacao de analises. |
| | `monthly_report_subscriptions` [NOVO Jun 2026] | 6 | 2026-06-12 | SIM | Assinaturas de relatorios mensais automaticos. Entrega programada de relatorios setoriais. |
| **User Engagement** | `messages` | 8 | 012_create_messages | SIM | Mensagens entre usuarios. Sistema interno de comunicacao para colaboracao em equipe. |
| | `conversations` | 9 | 012_create_messages | SIM | Threads de conversa entre usuarios. Agrupa mensagens em topicos. |
| | `user_sector_affinity` [NOVO Jun 2026] | 6 | 2026-06-04 | SIM | Preferencia setorial do usuario. Aprende interacao com setores para recomendacoes. |
| | `user_lifecycle` [NOVO Jun 2026] | 3 | 2026-06-04 | SIM | Maquina de estado do ciclo de vida do usuario. Trial, active, at_risk, churned, reinstated. |
| | `user_lifecycle_events` [NOVO Jun 2026] | 5 | 2026-06-04 | SIM | Historico de eventos do ciclo de vida. Transicoes com fonte e timestamp. |
| | `user_email_actions` [NOVO Abr 2026] | 4 | 2026-04-30 | SIM | Acoes de usuario via email. Links de confirmacao, unsubscribe, magic links. |
| | `trial_email_log` | 14 | 2026-02-24 | SIM | Log de emails de trial. Disparo de ativacao e lembretes. |
| | `trial_email_dlq` [NOVO Abr 2026] | 13 | 2026-04-10 | SIM | Fila de emails de trial com falha. Para retry e investigacao. |
| | `trial_exit_surveys` [NOVO Abr 2026] | 5 | 2026-04-11 | SIM | Pesquisas de saida do trial. Feedback de cancelamento. |
| | `trial_extensions` [NOVO Abr 2026] | 5 | 2026-04-07 | SIM | Extensoes de trial concedidas por admin. Motivo, duracao e auditoria. |
| | `export_time_saved_survey` [NOVO Abr 2026] | 9 | 2026-04-28 | SIM | Pesquisa de tempo economizado. Estimativas de economia do usuario. |
| | `post_purchase_sequences` [NOVO Mai 2026] | 15 | 2026-05-31 | SIM | Sequencias pos-compra. Emails/in-app apos eventos de compra. |
| **SEO & Analytics** | `seo_metrics` [NOVO Abr 2026] | 11 | 2026-04-07 | SIM | Metricas de SEO. Performance pagina-a-pagina incluindo rankings e trafego. |
| | `gsc_metrics` [NOVO Abr 2026] | 11 | 2026-04-22 | SIM | Dados do Google Search Console. Impressoes, clicks, CTR e posicao. |
| | `seo_coverage_manifest` [NOVO Mai 2026] | 6 | 2026-05-10 | SIM | Cobertura de geracao de paginas SEO. Monitoramento de paginas programaticas. |
| **Network Intelligence** | `network_events_agg` [NOVO Mai 2026] | 8 | 2026-05-31 | SIM | Dados agregados de eventos da rede de contratacao. Pre-computado para dashboards. |
| | `network_events_agg_weekly` [NOVO Jun 2026] | 9 | 2026-06-12 | SIM | Agregacoes semanais de eventos da rede. Sumarios para performance de dashboard. |
| | `subcontract_interests` [NOVO Jun 2026] | 5 | 2026-06-12 | SIM | Sinais de interesse em subcontratacao. Registro de interesse do usuario. |
| | `subcontract_opportunities` [NOVO Jun 2026] | 15 | 2026-06-12 | SIM | Marketplace de oportunidades de subcontratacao. Criterios de matching. |
| **Operations** | `health_checks` | 5 | 2026-02-28 | SIM | Resultados de health checks do sistema. Sondas periodicas para monitoramento. |
| | `incidents` | 7 | 2026-02-28 | SIM | Log de incidentes do sistema. Anomalias e falhas detectadas. |
| | `app_config` [NOVO Abr 2026] | 5 | 2026-04-28 | SIM | Configuracao runtime da aplicacao. Feature flags, manutencao e settings. |
| | `ingestion_checkpoints` [NOVO Mar 2026] | 12 | 2026-03-26 | SIM | Checkpoints de ingestao PNCP. Progresso por UF/modalidade para crawl resume. |
| | `ingestion_runs` [NOVO Mar 2026] | 15 | 2026-03-26 | SIM | Log de execucao de ingestao PNCP. Timing, linhas processadas e status. |
| | `integrations_webhooks` [NOVO Jun 2026] | 11 | 2026-06-17 | SIM | Endpoints de webhook para integracao externa. URLs registradas para eventos em tempo real. |
| | `data_deletion_requests` [NOVO Jun 2026] | 10 | 2026-06-15 | SIM | Solicitacoes de exclusao de dados LGPD. Workflow completo com verificacao de identidade. |
| **Legacy** | `google_sheets_exports` | 8 | 014_google_sheets_exports | SIM | Exportacoes para Google Sheets. Jobs de exportacao para relatorios integrados. |

## Novas Tabelas (Marco — Junho 2026)

Tabelas adicionadas nos ultimos 3 meses. Marcadas com `[NOVO 2026-{mes}]` na secao detalhada.

| Tabela | Cols | Criada em | Dominio | Descricao |
|--------|------|-----------|---------|-----------|
| `admin_billing_audit_log` | 12 | 2026-04-28 | Billing & Revenue | Trilha de auditoria de operacoes administrativas de cobranca. Reembolsos, ajustes, cambios de plano. |
| `admin_roles` | 4 | 2026-06-15 | Core Identity | Concessao de papeis administrativos. Controla acesso a endpoints /admin, gestao de cobranca e config. |
| `api_keys` | 7 | 2026-06-02 | Auth & Security | Gerenciamento de chaves de API para desenvolvedores. Chaves hasheadas com escopos e limites. |
| `api_metered_billing_cron_log` | 7 | 2026-06-06 | Billing & Revenue | Log de execucao cron de cobranca metered de API. |
| `api_subscriptions` | 11 | 2026-06-06 | Billing & Revenue | Planos de assinatura de API. Define tiers, rate limits, cotas e precos de API. |
| `api_usage_records` | 7 | 2026-06-06 | Billing & Revenue | Registros de uso de API. Contagem de chamadas por chave e periodo para cobranca metered. |
| `app_config` | 5 | 2026-04-28 | Operations | Configuracao runtime da aplicacao. Feature flags, manutencao e settings. |
| `auth_attempts` | 5 | 2026-04-28 | Auth & Security | Log de tentativas de autenticacao. Detecta forca bruta e rate limiting. |
| `billing_reconciliation_runs` | 11 | 2026-04-28 | Billing & Revenue | Log de execucao automatica de reconciliacao de cobranca. |
| `classification_feedback` | 14 | 2026-03-08 | Supplier Data | Feedback do usuario sobre classificacao setorial da IA. Correcoes para melhoria do modelo. |
| `cnae_setor_mapping` | 8 | 2026-05-11 | Supplier Data | Mapeamento extendido CNAE-setor com scoring de confianca e status de validacao. |
| `cnae_setores` | 4 | 2026-05-05 | Supplier Data | Mapeamento CNAE para setores SmartLic. Codigos CNAE para as 20 categorias setoriais. |
| `competitive_alerts` | 7 | 2026-06-12 | Alerts & Notifications | Alertas de inteligencia competitiva. Notifica vitorias de concorrentes e atividade de mercado. |
| `consultant_clients` | 5 | 2026-06-12 | Leads & CRM | Vinculo consultor-cliente. Contas de consultoria a perfis de clientes gerenciados. |
| `consultant_shares` | 6 | 2026-06-12 | Leads & CRM | Recursos compartilhados por consultores. Relatorios e analises compartilhados com clientes. |
| `data_deletion_requests` | 10 | 2026-06-15 | Operations | Solicitacoes de exclusao de dados LGPD. Workflow completo com verificacao de identidade. |
| `digital_products` | 12 | 2026-05-31 | Billing & Revenue | Catalogo de produtos digitais avulsos. Relatorios, datasets e conteudo premium fora de assinatura. |
| `email_tracking_events` | 7 | 2026-06-06 | Alerts & Notifications | Eventos de email do Resend. Entrega, abertura, clique, bounce, reclamação. |
| `enriched_entities` | 4 | 2026-04-10 | Supplier Data | Entidades enriquecidas. Metadados adicionais de fontes externas para orgaos e fornecedores. |
| `export_time_saved_survey` | 9 | 2026-04-28 | User Engagement | Pesquisa de tempo economizado. Estimativas de economia do usuario. |
| `founding_leads` | 15 | 2026-04-20 | Leads & CRM | Leads do programa de membros fundadores. Convite-based com status. |
| `founding_policy` | 14 | 2026-04-28 | Leads & CRM | Politica do programa de membros fundadores. Regras, beneficios e expiracao. |
| `founding_policy_audit_log` | 7 | 2026-05-07 | Leads & CRM | Auditoria de mudancas na politica de fundadores. Estado anterior/posterior. |
| `gsc_metrics` | 11 | 2026-04-22 | SEO & Analytics | Dados do Google Search Console. Impressoes, clicks, CTR e posicao. |
| `indice_municipal` | 16 | 2026-04-11 | Supplier Data | Indices municipais de contratacao. Indicadores pre-computados por municipio para benchmarking. |
| `ingestion_checkpoints` | 12 | 2026-03-26 | Operations | Checkpoints de ingestao PNCP. Progresso por UF/modalidade para crawl resume. |
| `ingestion_runs` | 15 | 2026-03-26 | Operations | Log de execucao de ingestao PNCP. Timing, linhas processadas e status. |
| `integrations_webhooks` | 11 | 2026-06-17 | Operations | Endpoints de webhook para integracao externa. URLs registradas para eventos em tempo real. |
| `intel_report_purchases` | 9 | 2026-05-05 | Intelligence Reports | Compras de relatorios de inteligencia avulsos. |
| `lead_captures` | 7 | 2026-05-12 | Leads & CRM | Captura de leads de paginas de marketing. Atribuicao de fonte e dados de contato. |
| `leads` | 18 | 2026-04-07 | Leads & CRM | Leads de vendas e marketing. Inbound de multiplos canais com dados de qualificacao. |
| `login_activity` | 3 | 2026-06-04 | Auth & Security | Log de atividade de login. Registra timestamps, IP e user-agent para monitoramento. |
| `monthly_report_subscriptions` | 6 | 2026-06-12 | Intelligence Reports | Assinaturas de relatorios mensais automaticos. Entrega programada de relatorios setoriais. |
| `network_events_agg` | 8 | 2026-05-31 | Network Intelligence | Dados agregados de eventos da rede de contratacao. Pre-computado para dashboards. |
| `network_events_agg_weekly` | 9 | 2026-06-12 | Network Intelligence | Agregacoes semanais de eventos da rede. Sumarios para performance de dashboard. |
| `organization_members` | 6 | 2026-03-01 | Organizations & Teams | Mapeamento de membros da organizacao. Vincula perfis a organizacoes com papeis. |
| `organizations` | 9 | 2026-03-01 | Organizations & Teams | Contas multi-tenant. Agrupa usuarios em organizacoes para acesso em equipe. |
| `partner_referrals` | 8 | 2026-03-01 | Leads & CRM | Indicacoes de parceiros. Status, comissao e conversao. |
| `partners` | 10 | 2026-03-01 | Leads & CRM | Contas de parceiros/afiliados. Consultores, revendedores e canais. |
| `plans_audit` | 8 | 2026-05-09 | Core Identity | Log de auditoria de alteracoes no catalogo de planos (trigger-based). |
| `pncp_raw_bids` | 26 | 2026-03-26 | Search & Discovery | Tabela central de ingestao de licitacoes do PNCP. ~1.5M linhas, 400d de retencao. |
| `pncp_supplier_contracts` | 21 | 2026-04-09 | Supplier Data | Contratos de fornecedores. Dados de contratos adjudicados do PNCP para inteligencia competitiva. |
| `post_purchase_sequences` | 15 | 2026-05-31 | User Engagement | Sequencias pos-compra. Emails/in-app apos eventos de compra. |
| `predictive_alerts` | 10 | 2026-06-12 | Alerts & Notifications | Alertas preditivos gerados por ML. Previsoes de oportunidades futuras. |
| `referrals` | 7 | 2026-04-05 | Leads & CRM | Indicacoes de usuarios. Status e recompensas. |
| `report_leads` | 8 | 2026-04-05 | Leads & CRM | Relatorios e exportacoes de leads. Criterios de filtro e metadados de exportacao. |
| `saved_filter_presets` | 6 | 2026-04-09 | Search & Discovery | Presets de filtros de busca salvos pelo usuario. Reutilizacao de combinacoes complexas. |
| `search_results_store` | 8 | 2026-03-03 | Search & Discovery | Armazenamento persistente de resultados completos de busca. Payloads arquivados para recuperacao assincrona. |
| `seo_coverage_manifest` | 6 | 2026-05-10 | SEO & Analytics | Cobertura de geracao de paginas SEO. Monitoramento de paginas programaticas. |
| `seo_metrics` | 11 | 2026-04-07 | SEO & Analytics | Metricas de SEO. Performance pagina-a-pagina incluindo rankings e trafego. |
| `shared_analyses` | 15 | 2026-04-05 | Intelligence Reports | Analises compartilhadas. Links publicos/privados para visualizacao de analises. |
| `subcontract_interests` | 5 | 2026-06-12 | Network Intelligence | Sinais de interesse em subcontratacao. Registro de interesse do usuario. |
| `subcontract_opportunities` | 15 | 2026-06-12 | Network Intelligence | Marketplace de oportunidades de subcontratacao. Criterios de matching. |
| `trial_email_dlq` | 13 | 2026-04-10 | User Engagement | Fila de emails de trial com falha. Para retry e investigacao. |
| `trial_exit_surveys` | 5 | 2026-04-11 | User Engagement | Pesquisas de saida do trial. Feedback de cancelamento. |
| `trial_extensions` | 5 | 2026-04-07 | User Engagement | Extensoes de trial concedidas por admin. Motivo, duracao e auditoria. |
| `user_alert_preferences` | 7 | 2026-06-17 | Alerts & Notifications | Configuracao de canais e frequencia de alertas por usuario. |
| `user_alerts` | 9 | 2026-06-17 | Alerts & Notifications | Alertas gerados para o usuario. Categoria, severidade e acao. Ciclo de leitura/dismiss. |
| `user_email_actions` | 4 | 2026-04-30 | User Engagement | Acoes de usuario via email. Links de confirmacao, unsubscribe, magic links. |
| `user_lifecycle` | 3 | 2026-06-04 | User Engagement | Maquina de estado do ciclo de vida do usuario. Trial, active, at_risk, churned, reinstated. |
| `user_lifecycle_events` | 5 | 2026-06-04 | User Engagement | Historico de eventos do ciclo de vida. Transicoes com fonte e timestamp. |
| `user_sector_affinity` | 6 | 2026-06-04 | User Engagement | Preferencia setorial do usuario. Aprende interacao com setores para recomendacoes. |
| `workspace_documents` | 14 | 2026-06-02 | Organizations & Teams | Documentos do workspace para preparacao de propostas. RFP, templates, propostas. |
| `workspace_timeline` | 12 | 2026-06-01 | Organizations & Teams | Linha do tempo de atividades do workspace. Log sequencial para auditoria da equipe. |
| `workspace_war_room_log` | 7 | 2026-06-02 | Organizations & Teams | Log de decisoes e atividades da war room. Decisoes, votos e comentarios. |
| `workspace_war_room_members` | 6 | 2026-06-02 | Organizations & Teams | Membros da war room com permissoes. Vincula perfis a war rooms. |
| `workspace_war_rooms` | 8 | 2026-06-02 | Organizations & Teams | Salas de decisao go/no-go. Espacos para analise colaborativa de editais. |
| `workspace_watchlist_matches` | 6 | 2026-05-31 | Organizations & Teams | Matches de watchlist com licitacoes. Vincula notices aos criterios da watchlist. |
| `workspace_watchlists` | 9 | 2026-05-31 | Organizations & Teams | Watchlists colaborativas de licitacoes. Equipes monitoram oportunidades juntas. |

## Novas Colunas em Tabelas Existentes

Colunas adicionadas via `ALTER TABLE ADD COLUMN` em tabelas pre-existentes (Mar-Jun 2026).

- `alerts.tracked_orgaos` (`TEXT[]`) — adicionada em 2026-06-04
- `alerts.tracked_fornecedores` (`TEXT[]`) — adicionada em 2026-06-04
- `audit_events.is_active` (`BOOLEAN`) — adicionada em 2026-04-15
- `conversations.first_response_at` (`timestamptz`) — adicionada em 2026-03-01
- `incidents.updated_at` (`TIMESTAMPTZ`) — adicionada em 2026-03-09
- `pipeline_items.search_id` (`TEXT`) — adicionada em 2026-03-15
- `plan_billing_periods.updated_at` (`TIMESTAMPTZ`) — adicionada em 2026-03-09
- `plan_billing_periods.stripe_product_id` (`TEXT`) — adicionada em 2026-04-28
- `plan_billing_periods.last_forward_synced_at` (`TIMESTAMPTZ`) — adicionada em 2026-04-28
- `plan_billing_periods.last_reverse_synced_at` (`TIMESTAMPTZ`) — adicionada em 2026-04-28
- `plan_billing_periods.is_archived` (`BOOLEAN`) — adicionada em 2026-04-28
- `plans.display_name` (`text`) — adicionada em 2026-05-09
- `plans.monthly_quota` (`int`) — adicionada em 2026-05-09
- `plans.capabilities` (`jsonb`) — adicionada em 2026-05-09
- `plans.version` (`int`) — adicionada em 2026-05-09
- `plans.updated_by` (`uuid`) — adicionada em 2026-05-09
- `profiles.referred_by_partner_id` (`UUID`) — adicionada em 2026-03-01
- `profiles.trial_conversion_emails_enabled` (`boolean`) — adicionada em 2026-04-06
- `profiles.timezone` (`TEXT`) — adicionada em 2026-04-07
- `profiles.deleted_at` (`timestamptz`) — adicionada em 2026-04-14
- `profiles.deleted_reason` (`text`) — adicionada em 2026-04-14
- `profiles.migrated_to` (`uuid`) — adicionada em 2026-04-14
- `profiles.cnae_primary` (`TEXT`) — adicionada em 2026-04-20
- `profiles.stripe_default_pm_id` (`TEXT`) — adicionada em 2026-04-20
- `profiles.force_mfa_enrollment_until` (`TIMESTAMPTZ`) — adicionada em 2026-04-28
- `profiles.is_founder` (`BOOLEAN`) — adicionada em 2026-05-07
- `profiles.founder_since` (`TIMESTAMPTZ`) — adicionada em 2026-05-07
- `profiles.founder_offer_version` (`TEXT`) — adicionada em 2026-05-07
- `profiles.founder_checkout_source` (`TEXT`) — adicionada em 2026-05-07
- `profiles.consulting_discount_pct` (`INT`) — adicionada em 2026-05-07
- `profiles.founder_public_listing_consent` (`BOOLEAN`) — adicionada em 2026-05-10
- `profiles.founder_listing_display_name` (`TEXT`) — adicionada em 2026-05-10
- `profiles.founder_company_logo_url` (`TEXT`) — adicionada em 2026-05-10
- `profiles.founder_consent_changed_at` (`TIMESTAMPTZ`) — adicionada em 2026-05-10
- `profiles.allow_network_analytics` (`BOOLEAN`) — adicionada em 2026-05-31
- `profiles.last_login_at` (`TIMESTAMPTZ`) — adicionada em 2026-06-04
- `profiles.login_count` (`INTEGER`) — adicionada em 2026-06-04
- `profiles.api_tier` (`TEXT`) — adicionada em 2026-06-06
- `profiles.admin_roles` (`text[]`) — adicionada em 2026-06-16
- `search_results_cache.expires_at` (`TIMESTAMPTZ`) — adicionada em 2026-06-08
- `search_state_transitions.user_id` (`UUID`) — adicionada em 2026-03-08
- `trial_email_log.delivery_status` (`TEXT`) — adicionada em 2026-04-24
- `trial_email_log.delivered_at` (`TIMESTAMPTZ`) — adicionada em 2026-04-24
- `trial_email_log.bounced_at` (`TIMESTAMPTZ`) — adicionada em 2026-04-24
- `trial_email_log.complained_at` (`TIMESTAMPTZ`) — adicionada em 2026-04-24
- `trial_email_log.failed_at` (`TIMESTAMPTZ`) — adicionada em 2026-04-24
- `trial_email_log.bounce_reason` (`TEXT`) — adicionada em 2026-04-24


## Referencia Detalhada de Tabelas

Colunas, tipos, nulabilidade, defaults, chaves e comentarios extraidos das migrations SQL.

### `profiles`

**Criada em:** 001_profiles_and_sessions (`001_profiles_and_sessions`)
**RLS:** Sim
**Colunas:** 43
**Dominio:** Core Identity

Tabela central de identidade do usuario. Vinculada ao Supabase Auth. Armazena perfil, plano, permissoes e estado da assinatura.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `-` | PK | auth.users(id) |  |
| 2 | `email` | `text` | NOT NULL | `-` |  | - |  |
| 3 | `full_name` | `text` | NULL | `-` |  | - |  |
| 4 | `company` | `text` | NULL | `-` |  | - |  |
| 5 | `plan_type` | `text` | NOT NULL | `-` |  | - | Current plan ID (free_trial, smartlic_pro, consultoria, etc). Synced from Stripe webhooks. Used as fallback when Supabase CB is open. Must match plans.id. |
| 6 | `avatar_url` | `text` | NULL | `-` |  | - |  |
| 7 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 8 | `updated_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 9 | `is_admin` | `boolean` | NOT NULL | `-` |  | - | True for system administrators who can manage users via /admin/* endpoints |
| 10 | `sector` | `TEXT` | NULL | `-` |  | - | User business sector (vestuario, alimentos, informatica, etc. or custom text) |
| 11 | `phone_whatsapp` | `TEXT` | NULL | `-` |  | - | Brazilian phone number (10-11 digits, no formatting) |
| 12 | `whatsapp_consent` | `BOOLEAN` | NULL | `-` |  | - | User consented to receive promotional Email and WhatsApp messages |
| 13 | `whatsapp_consent_at` | `TIMESTAMPTZ` | NULL | `-` |  | - | Timestamp when user gave consent (LGPD audit trail) |
| 14 | `context_data` | `jsonb` | NULL | `-` |  | - | Business context from onboarding wizard (STORY-247). Schema: {ufs_atuacao, faixa_valor_min, faixa_valor_max, porte_empresa, modalidades_interesse, palavras_chave, experiencia_licitacoes} |
| 15 | `subscription_status` | `TEXT` | NULL | `-` |  | - |  |
| 16 | `trial_expires_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 17 | `subscription_end_date` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 18 | `email_unsubscribed` | `BOOLEAN` | NULL | `-` |  | - |  |
| 19 | `email_unsubscribed_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 20 | `marketing_emails_enabled` | `BOOLEAN` | NOT NULL | `-` |  | - | STORY-310 AC5: User opt-out for marketing/trial emails |
| 21 | `referred_by_partner_id` [NOVO] | `UUID` | NULL | `-` |  | partners(id) |  |
| 22 | `trial_conversion_emails_enabled` [NOVO] | `boolean` | NULL | `-` |  | - | Controls critical trial deadline/conversion emails (Day 7/10/13/16). Separate from marketing_emails_enabled. |
| 23 | `timezone` [NOVO] | `TEXT` | NULL | `-` |  | - | IANA timezone identifier for timezone-aware email scheduling |
| 24 | `deleted_at` [NOVO] | `timestamptz` | NULL | `-` |  | - | STORY-2.8: soft-delete timestamp. NULL = active profile.  |
| 25 | `deleted_reason` [NOVO] | `text` | NULL | `-` |  | - | STORY-2.8: free-text reason for soft-delete  |
| 26 | `migrated_to` [NOVO] | `uuid` | NULL | `-` |  | public.profiles(id) | STORY-2.8: when a profile is merged into another (dedup), this points  |
| 27 | `cnae_primary` [NOVO] | `TEXT` | NULL | `-` |  | - | STORY-BIZ-002: primary CNAE of the profile company, in XX.YY-Z/NN or  |
| 28 | `stripe_default_pm_id` [NOVO] | `TEXT` | NULL | `-` |  | - | STORY-CONV-003a: Stripe PaymentMethod ID attached to the Customer and  |
| 29 | `force_mfa_enrollment_until` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | MFA-EXT-001: hard-enforce MFA enrollment until this timestamp. NULL means no time-bounded enforcement (admin/master/consultoria use plan-based logic). Set by (a) consultoria backfill (14d), (b) bruteforce trigger (7d). Reset by daily auth_cleanup cron after expiry. |
| 30 | `is_founder` [NOVO] | `BOOLEAN` | NOT NULL | `-` |  | - | TRUE if user purchased the v2 lifetime one-time Plano Fundadores (R$997).  |
| 31 | `founder_since` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | Timestamp of checkout.session.completed event for lifetime purchase. |
| 32 | `founder_offer_version` [NOVO] | `TEXT` | NULL | `-` |  | - | Offer version string from checkout metadata (e.g.  |
| 33 | `founder_checkout_source` [NOVO] | `TEXT` | NULL | `-` |  | - | utm_source or checkout source param from founding checkout metadata. |
| 34 | `consulting_discount_pct` [NOVO] | `INT` | NULL | `-` |  | - | Consultoria discount % granted to this founder (default 50 for v2_lifetime).  |
| 35 | `founder_public_listing_consent` [NOVO] | `BOOLEAN` | NOT NULL | `-` |  | - | LGPD opt-in flag (issue #1008). TRUE = user consented to public listing on /fundadores/hall. Default FALSE. |
| 36 | `founder_listing_display_name` [NOVO] | `TEXT` | NULL | `-` |  | - | Optional display name on /fundadores/hall. Falls back to razao_social or generic label when null. |
| 37 | `founder_company_logo_url` [NOVO] | `TEXT` | NULL | `-` |  | - | Optional company logo URL shown on /fundadores/hall. |
| 38 | `founder_consent_changed_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | Timestamp of the last consent toggle. Used as a lightweight LGPD audit trail. |
| 39 | `allow_network_analytics` [NOVO] | `BOOLEAN` | NULL | `-` |  | - | NETINT-001: Consentimento LGPD para coleta anonima.  |
| 40 | `last_login_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | LIFECYCLE-001: Timestamp do último login bem-sucedido do usuário.  |
| 41 | `login_count` [NOVO] | `INTEGER` | NOT NULL | `-` |  | - | LIFECYCLE-001: Contador total de logins bem-sucedidos.  |
| 42 | `api_tier` [NOVO] | `TEXT` | NULL | `-` |  | - | API-SELF-004: Current API tier for self-service API key users. NULL means no API subscription. |
| 43 | `admin_roles` [NOVO] | `text[]` | NULL | `-` |  | - | Granular admin roles (#1912). Values: admin:users, admin:billing, admin:cache, admin:partners, admin:seo, admin:ops, admin:compliance, admin:super |

### `plans`

**Criada em:** 001_profiles_and_sessions (`001_profiles_and_sessions`)
**RLS:** Sim
**Colunas:** 18
**Dominio:** Core Identity

Catalogo de planos de assinatura. Define tiers (Free, Pro, Consultoria) com precos, feature flags e cotas.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `text` | NOT NULL | `-` | PK | - |  |
| 2 | `name` | `text` | NOT NULL | `-` |  | - |  |
| 3 | `description` | `text` | NULL | `-` |  | - |  |
| 4 | `max_searches` | `int` | NULL | `-` |  | - |  |
| 5 | `price_brl` | `numeric(10,2)` | NOT NULL | `0` |  | - |  |
| 6 | `duration_days` | `int` | NULL | `-` |  | - |  |
| 7 | `stripe_price_id` | `text` | NULL | `-` |  | - | DEPRECATED (DEBT-017/DB-014): Legacy column. Use stripe_price_id_monthly/semiannual/annual or plan_billing_periods.stripe_price_id instead. Kept as fallback in billing.py checkout flow. Remove after billing code migration. |
| 8 | `is_active` | `boolean` | NOT NULL | `true` |  | - |  |
| 9 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 10 | `stripe_price_id_monthly` | `TEXT` | NULL | `-` |  | - | Stripe monthly price ID. Production values set by migrations.  |
| 11 | `stripe_price_id_annual` | `TEXT` | NULL | `-` |  | - | Stripe annual price ID. See stripe_price_id_monthly comment for setup instructions. |
| 12 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `-` |  | - | Timestamp of last plan metadata update. Useful for cache invalidation and change tracking. |
| 13 | `stripe_price_id_semiannual` | `TEXT` | NULL | `-` |  | - | Stripe semiannual price ID. See stripe_price_id_monthly comment for setup instructions. |
| 14 | `display_name` [NOVO] | `text` | NULL | `-` |  | - |  |
| 15 | `monthly_quota` [NOVO] | `int` | NULL | `-` |  | - | Monthly request quota; mirrors max_searches. Kept distinct so #192 spec is auditable. |
| 16 | `capabilities` [NOVO] | `jsonb` | NULL | `-` |  | - | JSONB plan limits: max_history_days, allow_excel, allow_pipeline, max_requests_per_month, max_requests_per_min, max_summary_tokens, priority. Source of truth for runtime quota enforcement (TD-GTM-003 #192). |
| 17 | `version` [NOVO] | `int` | NOT NULL | `-` |  | - | Monotonically incremented on capability change. Used by clients to detect changes without polling. |
| 18 | `updated_by` [NOVO] | `uuid` | NULL | `-` |  | auth.users(id) |  |

### `plan_features`

**Criada em:** 009_create_plan_features (`009_create_plan_features`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Core Identity

Mapeamento de funcionalidades por plano. Conecta recursos (booleano, limite numerico) a tiers.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `SERIAL` | NOT NULL | `-` | PK | - |  |
| 2 | `plan_id` | `TEXT` | NOT NULL | `-` |  | public.plans(id) | References plans.id (consultor_agil, maquina, sala_guerra) |
| 3 | `billing_period` | `VARCHAR(10)` | NOT NULL | `-` |  | - | monthly or annual |
| 4 | `feature_key` | `VARCHAR(100)` | NOT NULL | `-` |  | - | Feature identifier (early_access, proactive_search, etc) |
| 5 | `enabled` | `BOOLEAN` | NOT NULL | `true` |  | - |  |
| 6 | `metadata` | `JSONB` | NULL | `'{}'::jsonb` |  | - | Optional feature-specific configuration |
| 7 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 8 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |

### `plans_audit` [NOVO Mai 2026]

**Criada em:** 2026-05-09 (`20260509011633_plans_capabilities_table`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Core Identity

Log de auditoria de alteracoes no catalogo de planos (trigger-based).

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `full` | `history INSERT/UPDATE/DELETE` | NULL | `-` |  | - |  |
| 2 | `id` | `bigserial` | NOT NULL | `-` | PK | - |  |
| 3 | `plan_id` | `text` | NULL | `-` |  | - |  |
| 4 | `operation` | `text` | NOT NULL | `-` |  | - |  |
| 5 | `old_value` | `jsonb` | NULL | `-` |  | - |  |
| 6 | `new_value` | `jsonb` | NULL | `-` |  | - |  |
| 7 | `changed_by` | `uuid` | NULL | `-` |  | - |  |
| 8 | `changed_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |

### `user_subscriptions`

**Criada em:** 001_profiles_and_sessions (`001_profiles_and_sessions`)
**RLS:** Sim
**Colunas:** 15
**Dominio:** Core Identity

Estado atual da assinatura do usuario. Vincula Stripe subscription ID ao plano e periodo.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `uuid` | NOT NULL | `-` |  | public.profiles(id) |  |
| 3 | `plan_id` | `text` | NOT NULL | `-` |  | public.plans(id) |  |
| 4 | `credits_remaining` | `int` | NULL | `-` |  | - |  |
| 5 | `starts_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 6 | `expires_at` | `timestamptz` | NULL | `-` |  | - |  |
| 7 | `stripe_subscription_id` | `text` | NULL | `-` |  | - |  |
| 8 | `stripe_customer_id` | `text` | NULL | `-` |  | - |  |
| 9 | `is_active` | `boolean` | NOT NULL | `true` |  | - |  |
| 10 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 11 | `billing_period` | `VARCHAR(10)` | NOT NULL | `-` |  | - | Billing cycle: monthly or annual |
| 12 | `annual_benefits` | `JSONB` | NOT NULL | `-` |  | - | JSON object storing annual-exclusive benefits |
| 13 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `-` |  | - | Timestamp of last subscription update. Critical for audit trails and debugging. |
| 14 | `subscription_status` | `TEXT` | NULL | `-` |  | - | Stripe subscription status enum: active, past_due, canceled, trialing, incomplete, incomplete_expired, unpaid, paused. Maps to profiles.plan_type via webhook sync — both must agree for correct quota enforcement. |
| 15 | `first_failed_at` | `TIMESTAMPTZ` | NULL | `-` |  | - | STORY-309: Timestamp of first payment failure for dunning sequence tracking |

### `plan_billing_periods`

**Criada em:** 029_single_plan_model (`029_single_plan_model`)
**RLS:** Sim
**Colunas:** 12
**Dominio:** Core Identity

Mapeamento de ciclos de cobranca por plano (mensal, semestral, anual) com Stripe price IDs.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `plan_id` | `TEXT` | NOT NULL | `-` |  | public.plans(id) |  |
| 3 | `billing_period` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `price_cents` | `INTEGER` | NOT NULL | `-` |  | - |  |
| 5 | `discount_percent` | `INTEGER` | NULL | `0` |  | - |  |
| 6 | `stripe_price_id` | `TEXT` | NULL | `-` |  | - | Stripe price ID for this billing period. Source of truth for checkout.  |
| 7 | `created_at` | `TIMESTAMPTZ` | NULL | `NOW()` |  | - |  |
| 8 | `updated_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 9 | `stripe_product_id` [NOVO] | `TEXT` | NULL | `-` |  | - | Denormalised Stripe product id (price -> product). Populated by webhook  |
| 10 | `last_forward_synced_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | BILL-SYNC-001: timestamp of the last Stripe -> DB sync (any of  |
| 11 | `last_reverse_synced_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | BILL-SYNC-001: timestamp of the last DB -> Stripe push performed by  |
| 12 | `is_archived` [NOVO] | `BOOLEAN` | NOT NULL | `-` |  | - | Soft-delete flag for Stripe price.deleted. Archived rows are filtered  |

### `admin_roles` [NOVO Jun 2026]

**Criada em:** 2026-06-15 (`20260615000001_admin_roles`)
**RLS:** Sim
**Colunas:** 4
**Dominio:** Core Identity

Concessao de papeis administrativos. Controla acesso a endpoints /admin, gestao de cobranca e config.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `user_id` | `UUID` | NOT NULL | `-` | PK | profiles(id) |  |
| 2 | `roles` | `TEXT[]` | NOT NULL | `'{}'` |  | - | Array of role strings, e.g. {dashboard,user_manager} |
| 3 | `granted_by` | `UUID` | NULL | `-` |  | profiles(id) | User ID of the admin who granted these roles |
| 4 | `granted_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - | Timestamp when roles were granted |

### `user_oauth_tokens`

**Criada em:** 013_google_oauth_tokens (`013_google_oauth_tokens`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** Core Identity

Armazenamento seguro de tokens OAuth para integracoes com APIs de terceiros.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `provider` | `VARCHAR(50)` | NOT NULL | `-` |  | - |  |
| 4 | `access_token` | `TEXT` | NOT NULL | `-` |  | - | AES-256 encrypted access token. NEVER log this value in plaintext. Used to authenticate API calls to OAuth provider. |
| 5 | `refresh_token` | `TEXT` | NULL | `-` |  | - | AES-256 encrypted refresh token. Used to obtain new access tokens when expired. May be NULL for some OAuth flows. |
| 6 | `expires_at` | `TIMESTAMPTZ` | NOT NULL | `-` |  | - | Timestamp when access_token expires (UTC). Backend automatically refreshes using refresh_token before expiration. |
| 7 | `scope` | `TEXT` | NOT NULL | `-` |  | - | OAuth scopes granted by user. For Google Sheets: "https://www.googleapis.com/auth/spreadsheets" |
| 8 | `created_at` | `TIMESTAMPTZ` | NULL | `NOW()` |  | - |  |
| 9 | `updated_at` | `TIMESTAMPTZ` | NULL | `NOW()` |  | - |  |

### `auth_attempts` [NOVO Abr 2026]

**Criada em:** 2026-04-28 (`20260428100500_auth_attempts_tracking`)
**RLS:** Sim
**Colunas:** 5
**Dominio:** Auth & Security

Log de tentativas de autenticacao. Detecta forca bruta e rate limiting.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `user_id` | `UUID` | NOT NULL | `-` | PK | auth.users(id) |  |
| 2 | `consecutive_failures` | `INTEGER` | NOT NULL | `0` |  | - | Count of consecutive password failures. Reset to 0 on successful login or after 24h idle (last_failure_at). |
| 3 | `last_failure_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 4 | `last_success_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 5 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |

### `mfa_recovery_codes`

**Criada em:** 2026-02-28 (`20260228160000_add_mfa_recovery_codes`)
**RLS:** Sim
**Colunas:** 5
**Dominio:** Auth & Security

Codigos de recuperacao MFA (uso unico). Fallback para autenticacao multifator.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `code_hash` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `used_at` | `TIMESTAMPTZ` | NULL | `NULL` |  | - |  |
| 5 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |

### `mfa_recovery_attempts`

**Criada em:** 2026-02-28 (`20260228160000_add_mfa_recovery_codes`)
**RLS:** Sim
**Colunas:** 4
**Dominio:** Auth & Security

Log de uso de codigos de recuperacao MFA para auditoria de seguranca.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `attempted_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |
| 4 | `success` | `BOOLEAN` | NOT NULL | `false NOT NULL` |  | - |  |

### `audit_events`

**Criada em:** 023_audit_events (`023_audit_events`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Auth & Security

Log de auditoria do sistema. Eventos de seguranca (login, mudanca de papel, acesso a dados).

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `timestamp` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 3 | `event_type` | `text` | NOT NULL | `-` |  | - | Event category. Valid types: auth.login, auth.logout, auth.signup,  |
| 4 | `actor_id_hash` | `text` | NULL | `-` |  | - | SHA-256 hash of the acting user ID, truncated to 16 hex chars. NULL for system events. |
| 5 | `target_id_hash` | `text` | NULL | `-` |  | - | SHA-256 hash of the target user ID, truncated to 16 hex chars. NULL when not applicable. |
| 6 | `details` | `jsonb` | NULL | `-` |  | - |  |
| 7 | `ip_hash` | `text` | NULL | `-` |  | - | SHA-256 hash of the client IP address, truncated to 16 hex chars. NULL when unavailable. |
| 8 | `is_active` [NOVO] | `BOOLEAN` | NOT NULL | `-` |  | - | Soft-delete flag for LGPD/GDPR erasure requests.  |

### `login_activity` [NOVO Jun 2026]

**Criada em:** 2026-06-04 (`20260604135553_add_login_tracking`)
**RLS:** Sim
**Colunas:** 3
**Dominio:** Auth & Security

Log de atividade de login. Registra timestamps, IP e user-agent para monitoramento.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | public.profiles(id) | FK para profiles(id). Identifica o usuário que realizou o login. |
| 3 | `logged_in_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - | Timestamp do evento de login. Default now(). |

### `api_keys` [NOVO Jun 2026]

**Criada em:** 2026-06-02 (`20260602000002_create_api_keys`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Auth & Security

Gerenciamento de chaves de API para desenvolvedores. Chaves hasheadas com escopos e limites.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | profiles(id) |  |
| 3 | `key_hash` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `name` | `TEXT` | NOT NULL | `''` |  | - |  |
| 5 | `revoked_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 6 | `last_used_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 7 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `search_sessions`

**Criada em:** 001_profiles_and_sessions (`001_profiles_and_sessions`)
**RLS:** Sim
**Colunas:** 25
**Dominio:** Search & Discovery

Log de sessoes de busca do usuario. Registra consultas, filtros, resultados e status.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `uuid` | NOT NULL | `-` |  | public.profiles(id) |  |
| 3 | `sectors` | `text[]` | NOT NULL | `-` |  | - |  |
| 4 | `ufs` | `text[]` | NOT NULL | `-` |  | - |  |
| 5 | `data_inicial` | `date` | NOT NULL | `-` |  | - |  |
| 6 | `data_final` | `date` | NOT NULL | `-` |  | - |  |
| 7 | `custom_keywords` | `text[]` | NULL | `-` |  | - |  |
| 8 | `total_raw` | `int` | NOT NULL | `0` |  | - |  |
| 9 | `total_filtered` | `int` | NOT NULL | `0` |  | - |  |
| 10 | `valor_total` | `numeric(14,2)` | NULL | `0` |  | - | Sum of opportunity values in BRL. Widened from NUMERIC(14,2) to NUMERIC(18,2)  |
| 11 | `resumo_executivo` | `text` | NULL | `-` |  | - |  |
| 12 | `destaques` | `text[]` | NULL | `-` |  | - |  |
| 13 | `excel_storage_path` | `text` | NULL | `-` |  | - |  |
| 14 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 15 | `search_id` | `UUID` | NULL | `-` |  | - | UUID linking session to SSE progress tracker, ARQ jobs, and cache entries. Optional for backward compatibility. |
| 16 | `status` | `TEXT` | NOT NULL | `-` |  | - | Session lifecycle: created → processing → completed|failed|timed_out|cancelled |
| 17 | `error_message` | `TEXT` | NULL | `-` |  | - | Human-readable error description (max 500 chars) |
| 18 | `error_code` | `TEXT` | NULL | `-` |  | - | Machine-readable: sources_unavailable, timeout, filter_error, llm_error, db_error, quota_exceeded, unknown |
| 19 | `started_at` | `TIMESTAMPTZ` | NOT NULL | `-` |  | - | When user initiated the search |
| 20 | `completed_at` | `TIMESTAMPTZ` | NULL | `-` |  | - | When processing finished (success or failure) |
| 21 | `duration_ms` | `INTEGER` | NULL | `-` |  | - | Total processing time in milliseconds |
| 22 | `pipeline_stage` | `TEXT` | NULL | `-` |  | - | Last pipeline stage reached: validate, prepare, execute, filter, enrich, generate, persist |
| 23 | `raw_count` | `INTEGER` | NULL | `-` |  | - | Items fetched before filtering |
| 24 | `response_state` | `TEXT` | NULL | `-` |  | - | Data quality: live, cached, degraded, empty_failure |
| 25 | `failed_ufs` | `TEXT[]` | NULL | `-` |  | - | List of UF codes that failed to fetch (CRIT-004 AC3) |

### `search_state_transitions`

**Criada em:** 2026-02-21 (`20260221100002_create_search_state_transitions`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** Search & Discovery

Maquina de estado de sessoes de busca. Transicoes: pending -> processing -> complete/error.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `search_id` | `UUID` | NOT NULL | `-` |  | - | UUID correlating with search_sessions.search_id. No FK constraint because search_sessions.search_id is nullable and not unique (retries share IDs). App-layer integrity enforced in search_state_manager.py. Orphan cleanup via pg_cron retention job (DEBT-017/DB-050). |
| 3 | `from_state` | `TEXT` | NULL | `-` |  | - | Previous state (NULL for initial CREATED) |
| 4 | `to_state` | `TEXT` | NOT NULL | `-` |  | - | New state after transition |
| 5 | `stage` | `TEXT` | NULL | `-` |  | - | Pipeline stage that triggered the transition |
| 6 | `details` | `JSONB` | NULL | `'{}'` |  | - | Arbitrary metadata (JSON) for the transition |
| 7 | `duration_since_previous_ms` | `INTEGER` | NULL | `-` |  | - | Milliseconds since previous transition |
| 8 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 9 | `user_id` [NOVO] | `UUID` | NULL | `-` |  | public.profiles(id) |  |

### `search_results_cache`

**Criada em:** 026_search_results_cache (`026_search_results_cache`)
**RLS:** Sim
**Colunas:** 20
**Dominio:** Search & Discovery

Cache L2 de resultados de busca. Metadados com TTL para re-consulta rapida.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `params_hash` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `search_params` | `JSONB` | NOT NULL | `-` |  | - |  |
| 5 | `results` | `JSONB` | NOT NULL | `-` |  | - |  |
| 6 | `total_results` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 7 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |
| 8 | `sources_json` | `JSONB` | NOT NULL | `-` |  | - | GTM-FIX-010 AC5r: Which sources contributed to this cache entry (e.g. ["PNCP","PORTAL_COMPRAS"]) |
| 9 | `fetched_at` | `TIMESTAMPTZ` | NOT NULL | `-` |  | - | GTM-FIX-010: When the live fetch was executed (for TTL calculations) |
| 10 | `last_success_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 11 | `last_attempt_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 12 | `fail_streak` | `INTEGER` | NOT NULL | `-` |  | - |  |
| 13 | `degraded_until` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 14 | `coverage` | `JSONB` | NULL | `-` |  | - |  |
| 15 | `fetch_duration_ms` | `INTEGER` | NULL | `-` |  | - |  |
| 16 | `priority` | `TEXT` | NOT NULL | `-` |  | - |  |
| 17 | `access_count` | `INTEGER` | NOT NULL | `-` |  | - |  |
| 18 | `last_accessed_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 19 | `params_hash_global` | `TEXT` | NULL | `-` |  | - | GTM-ARCH-002: Hash of (setor, ufs, data_inicio, data_fim) for cross-user cache sharing |
| 20 | `expires_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | GAP-003: Cache entry expiry timestamp. Set to created_at + CACHE_STALE_HOURS (24h) at write time.  |

### `search_results_store` [NOVO Mar 2026]

**Criada em:** 2026-03-03 (`20260303100000_create_search_results_store`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Search & Discovery

Armazenamento persistente de resultados completos de busca. Payloads arquivados para recuperacao assincrona.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `search_id` | `UUID` | NOT NULL | `-` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `results` | `JSONB` | NOT NULL | `-` |  | - |  |
| 4 | `sector` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `ufs` | `TEXT[]` | NULL | `-` |  | - |  |
| 6 | `total_filtered` | `INT` | NULL | `0` |  | - |  |
| 7 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 8 | `expires_at` | `TIMESTAMPTZ` | NULL | `now() + INTERVAL '24 hours'` |  | - | DEBT-100/DB-NEW-03: Cleaned up daily by pg_cron job cleanup-expired-search-results (4:00 UTC) |

### `pncp_raw_bids` [NOVO Mar 2026]

**Criada em:** 2026-03-26 (`20260326000000_datalake_raw_bids`)
**RLS:** Sim
**Colunas:** 26
**Dominio:** Search & Discovery

Tabela central de ingestao de licitacoes do PNCP. ~1.5M linhas, 400d de retencao.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `pncp_id` | `TEXT` | NOT NULL | `-` | PK | - |  |
| 2 | `objeto_compra` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `valor_total_estimado` | `NUMERIC(18,2)` | NULL | `-` |  | - |  |
| 4 | `modalidade_id` | `INTEGER` | NOT NULL | `-` |  | - |  |
| 5 | `modalidade_nome` | `TEXT` | NULL | `-` |  | - |  |
| 6 | `situacao_compra` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `esfera_id` | `TEXT` | NULL | `-` |  | - |  |
| 8 | `uf` | `TEXT` | NOT NULL | `-` |  | - |  |
| 9 | `municipio` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `codigo_municipio_ibge` | `TEXT` | NULL | `-` |  | - |  |
| 11 | `orgao_razao_social` | `TEXT` | NULL | `-` |  | - |  |
| 12 | `orgao_cnpj` | `TEXT` | NULL | `-` |  | - |  |
| 13 | `unidade_nome` | `TEXT` | NULL | `-` |  | - |  |
| 14 | `data_publicacao` | `TIMESTAMPTZ` | NULL | `-` |  | - | STORY-2.12 (2026-04-14): NULL rows backfilled to (ingested_at - 1 day).  |
| 15 | `data_abertura` | `TIMESTAMPTZ` | NULL | `-` |  | - | STORY-2.12 (2026-04-14): NULL rows backfilled to data_publicacao when possible.  |
| 16 | `data_encerramento` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 17 | `link_sistema_origem` | `TEXT` | NULL | `-` |  | - |  |
| 18 | `link_pncp` | `TEXT` | NULL | `-` |  | - |  |
| 19 | `content_hash` | `TEXT` | NOT NULL | `-` |  | - | SHA-256 hash of mutable fields. Used by upsert_pncp_raw_bids for change detection. |
| 20 | `ingested_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 21 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 22 | `source` | `TEXT` | NOT NULL | `'pncp'` |  | - |  |
| 23 | `crawl_batch_id` | `TEXT` | NULL | `-` |  | - | Soft reference to ingestion_runs.crawl_batch_id.  |
| 24 | `is_active` | `BOOLEAN` | NOT NULL | `true` |  | - | DEBT-05/AC4: MANTER — Flag de staging para purge pipeline.  |
| 25 | `tsv` [NOVO] | `TSVECTOR` | NULL | `-` |  | - | Pre-computed to_tsvector(portuguese, objeto_compra). Maintained by trigger.  |
| 26 | `embedding` [NOVO] | `VECTOR(256)` | NULL | `-` |  | - | Semantic embedding via text-embedding-3-small (dimensions=256).  |

### `saved_filter_presets` [NOVO Abr 2026]

**Criada em:** 2026-04-09 (`20260409000000_debt06_saved_filter_presets`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** Search & Discovery

Presets de filtros de busca salvos pelo usuario. Reutilizacao de combinacoes complexas.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `uuid` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `name` | `text` | NOT NULL | `-` |  | - |  |
| 4 | `filters_json` | `jsonb` | NOT NULL | `-` |  | - |  |
| 5 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 6 | `updated_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |

### `pncp_supplier_contracts` [NOVO Abr 2026]

**Criada em:** 2026-04-09 (`20260409100000_pncp_supplier_contracts`)
**RLS:** Sim
**Colunas:** 21
**Dominio:** Supplier Data

Contratos de fornecedores. Dados de contratos adjudicados do PNCP para inteligencia competitiva.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `BIGSERIAL` | NOT NULL | `-` | PK | - |  |
| 2 | `numero_controle_pncp` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `ni_fornecedor` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `nome_fornecedor` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `orgao_cnpj` | `TEXT` | NULL | `-` |  | - |  |
| 6 | `orgao_nome` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `uf` | `TEXT` | NULL | `-` |  | - |  |
| 8 | `municipio` | `TEXT` | NULL | `-` |  | - |  |
| 9 | `esfera` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `valor_global` | `NUMERIC(18, 2)` | NULL | `-` |  | - |  |
| 11 | `data_assinatura` | `DATE` | NULL | `-` |  | - |  |
| 12 | `objeto_contrato` | `TEXT` | NULL | `-` |  | - |  |
| 13 | `content_hash` | `TEXT` | NOT NULL | `-` |  | - |  |
| 14 | `is_active` | `BOOLEAN` | NOT NULL | `TRUE` |  | - |  |
| 15 | `ingested_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 16 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 17 | `data_fim_vigencia` [NOVO] | `DATE` | NULL | `-` |  | - | PREDINT-002: Contract end date for recurrence interval calculation |
| 18 | `setor_classificado` [NOVO] | `TEXT` | NULL | `-` |  | - | NETINT-002: Setor classificado do contrato. Nullable — populado por pipeline externo. |
| 19 | `data_publicacao` [NOVO] | `DATE` | NULL | `-` |  | - |  |
| 20 | `nr_contrato` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 21 | `ano` [NOVO] | `INTEGER` | NULL | `-` |  | - |  |

### `enriched_entities` [NOVO Abr 2026]

**Criada em:** 2026-04-10 (`20260410120000_enriched_entities`)
**RLS:** Sim
**Colunas:** 4
**Dominio:** Supplier Data

Entidades enriquecidas. Metadados adicionais de fontes externas para orgaos e fornecedores.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `entity_type` | `TEXT` | NOT NULL | `-` |  | - | Tipo:  |
| 2 | `entity_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `data` | `JSONB` | NOT NULL | `'{}'` |  | - | Payload JSONB: razao_social, cnae, simples_nacional, enderecos,  |
| 4 | `enriched_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `cnae_setores` [NOVO Mai 2026]

**Criada em:** 2026-05-05 (`20260505113807_cnae_setores_table`)
**RLS:** Sim
**Colunas:** 4
**Dominio:** Supplier Data

Mapeamento CNAE para setores SmartLic. Codigos CNAE para as 20 categorias setoriais.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `codigo_cnae` | `text` | NOT NULL | `-` | PK | - | 4-digit IBGE CNAE prefix (e.g. "4781"). Matches the prefix extraction  |
| 2 | `setor` | `text` | NOT NULL | `-` |  | - | SmartLic sector id (e.g. "engenharia"). Must match an id in  |
| 3 | `descricao` | `text` | NULL | `-` |  | - |  |
| 4 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |

### `cnae_setor_mapping` [NOVO Mai 2026]

**Criada em:** 2026-05-11 (`20260511120000_cnae_setor_mapping`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Supplier Data

Mapeamento extendido CNAE-setor com scoring de confianca e status de validacao.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `cnae_code` | `TEXT` | NOT NULL | `-` | PK | - | CNAE 4-digit prefix (e.g. "4120"). Source of truth: IBGE CNAE 2.3. |
| 2 | `setor_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `confidence` | `NUMERIC(3, 2)` | NOT NULL | `1.00` |  | - | Confidence score 0.00-1.00. 1.00 = exact match curated. |
| 4 | `fallback_setor_id` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `notes` | `TEXT` | NULL | `-` |  | - | Free-text audit trail. Soft-delete uses notes =  |
| 6 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 7 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 8 | `updated_by` | `UUID` | NULL | `-` |  | auth.users(id) |  |

### `indice_municipal` [NOVO Abr 2026]

**Criada em:** 2026-04-11 (`20260411120000_create_indice_municipal`)
**RLS:** Sim
**Colunas:** 16
**Dominio:** Supplier Data

Indices municipais de contratacao. Indicadores pre-computados por municipio para benchmarking.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `municipio_nome` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `municipio_ibge_code` | `TEXT` | NULL | `-` |  | - |  |
| 4 | `uf` | `CHAR(2)` | NOT NULL | `-` |  | - |  |
| 5 | `periodo` | `TEXT` | NOT NULL | `-` |  | - |  |
| 6 | `score_total` | `NUMERIC(5,2)` | NULL | `-` |  | - |  |
| 7 | `score_volume_publicacao` | `NUMERIC(5,2)` | NULL | `-` |  | - |  |
| 8 | `score_eficiencia_temporal` | `NUMERIC(5,2)` | NULL | `-` |  | - |  |
| 9 | `score_diversidade_mercado` | `NUMERIC(5,2)` | NULL | `-` |  | - |  |
| 10 | `score_transparencia_digital` | `NUMERIC(5,2)` | NULL | `-` |  | - |  |
| 11 | `score_consistencia` | `NUMERIC(5,2)` | NULL | `-` |  | - |  |
| 12 | `total_editais` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 13 | `ranking_nacional` | `INTEGER` | NULL | `-` |  | - |  |
| 14 | `ranking_uf` | `INTEGER` | NULL | `-` |  | - |  |
| 15 | `percentil` | `INTEGER` | NULL | `-` |  | - |  |
| 16 | `calculado_em` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |

### `classification_feedback` [NOVO Mar 2026]

**Criada em:** 2026-03-08 (`20260308200000_debt002_bridge_backend_migrations`)
**RLS:** Sim
**Colunas:** 14
**Dominio:** Supplier Data

Feedback do usuario sobre classificacao setorial da IA. Correcoes para melhoria do modelo.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `search_id` | `UUID` | NOT NULL | `-` |  | - |  |
| 4 | `bid_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `setor_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 6 | `user_verdict` | `TEXT` | NOT NULL | `-` |  | - |  |
| 7 | `reason` | `TEXT` | NULL | `-` |  | - |  |
| 8 | `category` | `TEXT` | NULL | `-` |  | - |  |
| 9 | `bid_objeto` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `bid_valor` | `DECIMAL` | NULL | `-` |  | - |  |
| 11 | `bid_uf` | `TEXT` | NULL | `-` |  | - |  |
| 12 | `confidence_score` | `INTEGER` | NULL | `-` |  | - |  |
| 13 | `relevance_source` | `TEXT` | NULL | `-` |  | - |  |
| 14 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `monthly_quota`

**Criada em:** 002_monthly_quota (`002_monthly_quota`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** Billing & Revenue

Cota mensal de consultas por usuario. Controla limite de chamadas de API por periodo de cobranca.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `month_year` | `VARCHAR(7)` | NOT NULL | `-` |  | - | Month key in YYYY-MM format for lazy reset logic |
| 4 | `searches_count` | `INT` | NOT NULL | `0` |  | - | Number of searches performed in this month |
| 5 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 6 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `stripe_webhook_events`

**Criada em:** 010_stripe_webhook_events (`010_stripe_webhook_events`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** Billing & Revenue

Log de eventos webhook do Stripe. Idempotencia e auditoria de eventos de pagamento.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `VARCHAR(255)` | NOT NULL | `-` | PK | - | Stripe event ID (evt_xxx). Primary key for idempotency. |
| 2 | `type` | `VARCHAR(100)` | NOT NULL | `-` |  | - | Stripe event type (e.g., customer.subscription.updated, invoice.payment_succeeded) |
| 3 | `processed_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 4 | `payload` | `JSONB` | NULL | `-` |  | - | Full Stripe event object (JSONB). Used for debugging and compliance. |
| 5 | `status` | `VARCHAR(20)` | NOT NULL | `-` |  | - |  |
| 6 | `received_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |

### `reconciliation_log`

**Criada em:** 2026-02-28 (`20260228140000_add_reconciliation_log`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Billing & Revenue

Log de reconciliacao de cobranca Stripe-banco de dados.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `run_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 3 | `total_checked` | `INT` | NOT NULL | `0` |  | - |  |
| 4 | `divergences_found` | `INT` | NOT NULL | `0` |  | - |  |
| 5 | `auto_fixed` | `INT` | NOT NULL | `0` |  | - |  |
| 6 | `manual_review` | `INT` | NOT NULL | `0` |  | - |  |
| 7 | `duration_ms` | `INT` | NOT NULL | `0` |  | - |  |
| 8 | `details` | `JSONB` | NULL | `'[]'::jsonb` |  | - |  |

### `billing_reconciliation_runs` [NOVO Abr 2026]

**Criada em:** 2026-04-28 (`20260428101100_billing_reconciliation_runs`)
**RLS:** Sim
**Colunas:** 11
**Dominio:** Billing & Revenue

Log de execucao automatica de reconciliacao de cobranca.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `started_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 3 | `finished_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 4 | `status` | `TEXT` | NOT NULL | `-` |  | - | running | completed | failed | skipped |
| 5 | `dry_run` | `BOOLEAN` | NOT NULL | `FALSE` |  | - | When true the cron only logs differences and never mutates DB or Stripe. |
| 6 | `rows_checked` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 7 | `drifts_detected` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 8 | `drifts_fixed` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 9 | `drifts_manual` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 10 | `drift_report` | `JSONB` | NULL | `-` |  | - | JSON array of drift descriptors:  |
| 11 | `error_message` | `TEXT` | NULL | `-` |  | - |  |

### `admin_billing_audit_log` [NOVO Abr 2026]

**Criada em:** 2026-04-28 (`20260428101200_admin_billing_audit_log`)
**RLS:** Sim
**Colunas:** 12
**Dominio:** Billing & Revenue

Trilha de auditoria de operacoes administrativas de cobranca. Reembolsos, ajustes, cambios de plano.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `plan_billing_period_id` | `UUID` | NULL | `-` |  | - |  |
| 3 | `plan_id` | `TEXT` | NULL | `-` |  | - |  |
| 4 | `billing_period` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `action` | `TEXT` | NOT NULL | `-` |  | - | reverse_sync_create_price | reverse_sync_archive_price |  |
| 6 | `old_stripe_price_id` | `TEXT` | NULL | `-` |  | - | Stripe price id active before the operation (NULL on first sync). |
| 7 | `new_stripe_price_id` | `TEXT` | NULL | `-` |  | - | Stripe price id active after the operation (NULL on archive-only / failed). |
| 8 | `actor_user_id` | `UUID` | NULL | `-` |  | auth.users(id) |  |
| 9 | `actor_email` | `TEXT` | NULL | `-` |  | - | Denormalised admin email at time of mutation. Survives auth.users  |
| 10 | `note` | `TEXT` | NULL | `-` |  | - |  |
| 11 | `payload` | `JSONB` | NULL | `-` |  | - |  |
| 12 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `api_subscriptions` [NOVO Jun 2026]

**Criada em:** 2026-06-06 (`20260606120000_create_api_subscriptions`)
**RLS:** Sim
**Colunas:** 11
**Dominio:** Billing & Revenue

Planos de assinatura de API. Define tiers, rate limits, cotas e precos de API.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | public.profiles(id) |  |
| 3 | `tier` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `status` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `stripe_subscription_id` | `TEXT` | NULL | `-` |  | - |  |
| 6 | `stripe_customer_id` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `current_period_start` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 8 | `current_period_end` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 9 | `canceled_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 10 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 11 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `api_usage_records` [NOVO Jun 2026]

**Criada em:** 2026-06-06 (`20260606120000_create_api_subscriptions`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Billing & Revenue

Registros de uso de API. Contagem de chamadas por chave e periodo para cobranca metered.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `api_key_id` | `UUID` | NOT NULL | `-` |  | public.api_keys(id) |  |
| 3 | `user_id` | `UUID` | NOT NULL | `-` |  | public.profiles(id) |  |
| 4 | `month` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `request_count` | `INT` | NOT NULL | `0` |  | - |  |
| 6 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 7 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `api_metered_billing_cron_log` [NOVO Jun 2026]

**Criada em:** 2026-06-06 (`20260606120000_create_api_subscriptions`)
**RLS:** Nao
**Colunas:** 7
**Dominio:** Billing & Revenue

Log de execucao cron de cobranca metered de API.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `run_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 3 | `month` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `records_updated` | `INT` | NOT NULL | `0` |  | - |  |
| 5 | `total_requests` | `INT` | NOT NULL | `0` |  | - |  |
| 6 | `errors` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `status` | `TEXT` | NOT NULL | `-` |  | - |  |

### `digital_products` [NOVO Mai 2026]

**Criada em:** 2026-05-31 (`20260531143640_digital_products`)
**RLS:** Sim
**Colunas:** 12
**Dominio:** Billing & Revenue

Catalogo de produtos digitais avulsos. Relatorios, datasets e conteudo premium fora de assinatura.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `sku` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `name` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `description` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `price_brl` | `INTEGER` | NOT NULL | `-` |  | - |  |
| 6 | `stripe_product_id` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `stripe_price_id` | `TEXT` | NULL | `-` |  | - |  |
| 8 | `preview_config` | `JSONB` | NULL | `'{}'` |  | - |  |
| 9 | `delivery_config` | `JSONB` | NULL | `'{}'` |  | - |  |
| 10 | `upsell_product_id` | `UUID` | NULL | `-` |  | digital_products(id) |  |
| 11 | `active` | `BOOLEAN` | NULL | `true` |  | - |  |
| 12 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `alerts`

**Criada em:** 2026-02-27 (`20260227100000_create_alerts`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** Alerts & Notifications

Alertas de licitacao definidos pelo usuario. Criterios configurados para notificacao de novas oportunidades.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | profiles(id) |  |
| 3 | `name` | `TEXT` | NOT NULL | `''` |  | - |  |
| 4 | `filters` | `JSONB` | NOT NULL | `'{}'::jsonb` |  | - | JSONB: {setor, ufs[], valor_min, valor_max, keywords[]} |
| 5 | `active` | `BOOLEAN` | NOT NULL | `true` |  | - |  |
| 6 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |
| 7 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |
| 8 | `tracked_orgaos` [NOVO] | `TEXT[]` | NOT NULL | `-` |  | - | ENTITY-001: CNPJ list of public agencies (orgaos) to track within this alert. Each entry must be 14 digits. |
| 9 | `tracked_fornecedores` [NOVO] | `TEXT[]` | NOT NULL | `-` |  | - | ENTITY-001: CNPJ list of suppliers (fornecedores) to track within this alert. Each entry must be 14 digits. |

### `alert_preferences`

**Criada em:** 2026-02-26 (`20260226100000_alert_preferences`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Alerts & Notifications

Preferencias de notificacao de alertas. Canais (email, in-app) e frequencia.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | profiles(id) |  |
| 3 | `frequency` | `alert_frequency` | NOT NULL | `'daily'` |  | - | DIGEST-001 — Frequency for digest emails: daily, twice_weekly (mon+thu), weekly (mon), none. |
| 4 | `enabled` | `BOOLEAN` | NOT NULL | `true` |  | - |  |
| 5 | `last_digest_sent_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 6 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |
| 7 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |

### `alert_runs`

**Criada em:** 2026-02-28 (`20260228100000_add_alert_runs`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** Alerts & Notifications

Log de execucao de alertas. Registro de cada gatilho com contagem de resultados e status.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `alert_id` | `UUID` | NOT NULL | `-` |  | alerts(id) |  |
| 3 | `run_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |
| 4 | `items_found` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 5 | `items_sent` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 6 | `status` | `TEXT` | NOT NULL | `'pending'` |  | - | Run outcome: matched, no_results, no_match, all_deduped, error |

### `alert_sent_items`

**Criada em:** 2026-02-27 (`20260227100000_create_alerts`)
**RLS:** Sim
**Colunas:** 4
**Dominio:** Alerts & Notifications

Log de entregas de notificacao de alertas. Itens individuais enviados por evento.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `alert_id` | `UUID` | NOT NULL | `-` |  | alerts(id) |  |
| 3 | `item_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `sent_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |

### `user_alerts` [NOVO Jun 2026]

**Criada em:** 2026-06-17 (`20260617120000_user_alerts`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** Alerts & Notifications

Alertas gerados para o usuario. Categoria, severidade e acao. Ciclo de leitura/dismiss.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `type` | `TEXT` | NOT NULL | `-` |  | - | Alert event type: new_matching_edital, deadline_approaching, pregao_starting, result_published, contrato_firmado, documento_vencendo |
| 4 | `title` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `body` | `TEXT` | NULL | `-` |  | - |  |
| 6 | `data` | `JSONB` | NULL | `'{}'::jsonb` |  | - | JSON payload with related entity IDs, URLs, metadata |
| 7 | `is_read` | `BOOLEAN` | NULL | `false` |  | - | Read/unread status for badge counting |
| 8 | `read_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 9 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `user_alert_preferences` [NOVO Jun 2026]

**Criada em:** 2026-06-17 (`20260617120000_user_alerts`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Alerts & Notifications

Configuracao de canais e frequencia de alertas por usuario.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `user_id` | `UUID` | NOT NULL | `-` | PK | auth.users(id) |  |
| 2 | `channels` | `JSONB` | NULL | `'{"in_app": true}'::jsonb` |  | - | Enabled channels (e.g. {"in_app": true, "email": true}) |
| 3 | `enabled_types` | `TEXT[]` | NULL | `'{}'::text[]` |  | - | Whitelist of enabled alert types. Empty = all enabled. |
| 4 | `quiet_hours` | `JSONB` | NULL | `'{"start": null` |  | - | Quiet hours config {"start": "22:00", "end": "07:00"} or null |
| 5 | `end":` | `null}'::jsonb` | NULL | `-` |  | - |  |
| 6 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 7 | `updated_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `competitive_alerts` [NOVO Jun 2026]

**Criada em:** 2026-06-12 (`20260612100000_competitive_alerts`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Alerts & Notifications

Alertas de inteligencia competitiva. Notifica vitorias de concorrentes e atividade de mercado.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `competitor_cnpj` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `alert_type` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `metadata` | `JSONB` | NULL | `'{}'::jsonb` |  | - |  |
| 6 | `enabled` | `BOOLEAN` | NULL | `true` |  | - |  |
| 7 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `predictive_alerts` [NOVO Jun 2026]

**Criada em:** 2026-06-12 (`20260612000003_create_predictive_alerts`)
**RLS:** Sim
**Colunas:** 10
**Dominio:** Alerts & Notifications

Alertas preditivos gerados por ML. Previsoes de oportunidades futuras.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `sector_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `alert_type` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `threshold_value` | `DECIMAL` | NOT NULL | `0 CHECK (threshold_value >= 0)` |  | - |  |
| 6 | `uf` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `enabled` | `BOOLEAN` | NOT NULL | `true` |  | - |  |
| 8 | `last_triggered_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 9 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 10 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `email_tracking_events` [NOVO Jun 2026]

**Criada em:** 2026-06-06 (`20260606040000_create_email_tracking_events`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Alerts & Notifications

Eventos de email do Resend. Entrega, abertura, clique, bounce, reclamação.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `tracking_id` | `UUID` | NOT NULL | `-` |  | - |  |
| 3 | `event_type` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `user_id` | `UUID` | NULL | `-` |  | public.profiles(id) |  |
| 5 | `digest_frequency` | `TEXT` | NULL | `'daily'` |  | - |  |
| 6 | `metadata` | `JSONB` | NULL | `'{}'::jsonb` |  | - |  |
| 7 | `created_at` | `TIMESTAMPTZ` | NULL | `NOW()` |  | - |  |

### `organizations` [NOVO Mar 2026]

**Criada em:** 2026-03-01 (`20260301100000_create_organizations`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** Organizations & Teams

Contas multi-tenant. Agrupa usuarios em organizacoes para acesso em equipe.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `name` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `logo_url` | `TEXT` | NULL | `-` |  | - |  |
| 4 | `owner_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) | User who created and owns the organization (cannot be deleted while org exists) |
| 5 | `max_members` | `INT` | NOT NULL | `5` |  | - | Maximum number of members allowed (enforced at application level) |
| 6 | `plan_type` | `TEXT` | NOT NULL | `'consultoria'` |  | - | Billing plan type for the organization |
| 7 | `stripe_customer_id` | `TEXT` | NULL | `-` |  | - |  |
| 8 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 9 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |

### `organization_members` [NOVO Mar 2026]

**Criada em:** 2026-03-01 (`20260301100000_create_organizations`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** Organizations & Teams

Mapeamento de membros da organizacao. Vincula perfis a organizacoes com papeis.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `org_id` | `UUID` | NOT NULL | `-` |  | public.organizations(id) |  |
| 3 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 4 | `role` | `TEXT` | NOT NULL | `-` |  | - | Role within org: owner (full control, rank 3), member (team access, rank 2), viewer (read-only, rank 1) |
| 5 | `invited_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - | Timestamp when invitation was sent |
| 6 | `accepted_at` | `TIMESTAMPTZ` | NULL | `-` |  | - | Timestamp when invitation was accepted; NULL means pending |

### `workspace_watchlists` [NOVO Mai 2026]

**Criada em:** 2026-05-31 (`20260531175520_workspace_watchlists`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** Organizations & Teams

Watchlists colaborativas de licitacoes. Equipes monitoram oportunidades juntas.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `nome` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `descricao` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `filtros` | `JSONB` | NOT NULL | `'{}'` |  | - |  |
| 6 | `alertas_ativos` | `BOOLEAN` | NULL | `true` |  | - |  |
| 7 | `frequencia_alerta` | `TEXT` | NULL | `'daily' CHECK (frequencia_alerta IN ('daily', 'weekly', 'instant'))` |  | - |  |
| 8 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 9 | `updated_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `workspace_watchlist_matches` [NOVO Mai 2026]

**Criada em:** 2026-05-31 (`20260531175520_workspace_watchlists`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** Organizations & Teams

Matches de watchlist com licitacoes. Vincula notices aos criterios da watchlist.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `watchlist_id` | `UUID` | NOT NULL | `-` |  | public.workspace_watchlists(id) |  |
| 3 | `licitacao_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `fonte` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `status` | `TEXT` | NULL | `'unread' CHECK (status IN ('unread', 'archived', 'dismissed'))` |  | - |  |
| 6 | `matched_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `workspace_timeline` [NOVO Jun 2026]

**Criada em:** 2026-06-01 (`20260601000002_workspace_timeline`)
**RLS:** Sim
**Colunas:** 12
**Dominio:** Organizations & Teams

Linha do tempo de atividades do workspace. Log sequencial para auditoria da equipe.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `licitacao_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `licitacao_fonte` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `evento` | `TEXT` | NOT NULL | `-` |  | - |  |
| 6 | `data_evento` | `DATE` | NOT NULL | `-` |  | - |  |
| 7 | `data_prevista` | `DATE` | NULL | `-` |  | - |  |
| 8 | `responsavel` | `TEXT` | NULL | `-` |  | - |  |
| 9 | `notas` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `status` | `TEXT` | NOT NULL | `'pendente' CHECK (status IN ('pendente', 'concluido', 'atrasado'))` |  | - |  |
| 11 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 12 | `updated_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `workspace_war_rooms` [NOVO Jun 2026]

**Criada em:** 2026-06-02 (`20260602000000_workspace_war_rooms`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Organizations & Teams

Salas de decisao go/no-go. Espacos para analise colaborativa de editais.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `licitacao_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `licitacao_fonte` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `status` | `TEXT` | NULL | `'preparacao' CHECK (status IN ('preparacao', 'em_andamento', 'concluida'))` |  | - |  |
| 6 | `notas_rapidas` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 8 | `updated_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `workspace_war_room_members` [NOVO Jun 2026]

**Criada em:** 2026-06-02 (`20260602000000_workspace_war_rooms`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** Organizations & Teams

Membros da war room com permissoes. Vincula perfis a war rooms.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `workspace_war_room_id` | `UUID` | NOT NULL | `-` |  | workspace_war_rooms(id) |  |
| 3 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 4 | `papel` | `TEXT` | NOT NULL | `'membro' CHECK (papel IN ('lider', 'documentacao', 'lances', 'juridico', 'observador', 'membro'))` |  | - |  |
| 5 | `ativo` | `BOOLEAN` | NULL | `true` |  | - |  |
| 6 | `joined_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `workspace_war_room_log` [NOVO Jun 2026]

**Criada em:** 2026-06-02 (`20260602000000_workspace_war_rooms`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Organizations & Teams

Log de decisoes e atividades da war room. Decisoes, votos e comentarios.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `war_room_id` | `UUID` | NOT NULL | `-` |  | workspace_war_rooms(id) |  |
| 3 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 4 | `acao` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `descricao` | `TEXT` | NOT NULL | `-` |  | - |  |
| 6 | `metadados` | `JSONB` | NULL | `'{}'` |  | - |  |
| 7 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `workspace_documents` [NOVO Jun 2026]

**Criada em:** 2026-06-02 (`20260602214104_workspace_documents`)
**RLS:** Sim
**Colunas:** 14
**Dominio:** Organizations & Teams

Documentos do workspace para preparacao de propostas. RFP, templates, propostas.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `licitacao_id` | `TEXT` | NULL | `-` |  | - |  |
| 4 | `licitacao_fonte` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `nome` | `TEXT` | NOT NULL | `-` |  | - |  |
| 6 | `tipo` | `TEXT` | NOT NULL | `-` |  | - |  |
| 7 | `tamanho_bytes` | `BIGINT` | NULL | `-` |  | - |  |
| 8 | `mime_type` | `TEXT` | NULL | `-` |  | - |  |
| 9 | `storage_path` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `status` | `TEXT` | NULL | `'ativo' CHECK (status IN ('ativo', 'vencido', 'arquivado'))` |  | - |  |
| 11 | `data_validade` | `DATE` | NULL | `-` |  | - |  |
| 12 | `tags` | `TEXT[]` | NULL | `-` |  | - |  |
| 13 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 14 | `updated_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `leads` [NOVO Abr 2026]

**Criada em:** 2026-04-07 (`20260407300000_leads`)
**RLS:** Sim
**Colunas:** 18
**Dominio:** Leads & CRM

Leads de vendas e marketing. Inbound de multiplos canais com dados de qualificacao.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `email` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `source` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `setor` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `uf` | `TEXT` | NULL | `-` |  | - |  |
| 6 | `captured_at` | `TIMESTAMPTZ` | NULL | `NOW()` |  | - |  |
| 7 | `nome` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 8 | `empresa` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 9 | `cnpj` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 10 | `telefone` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 11 | `modalidade_interesse` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 12 | `mensagem` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 13 | `utm_source` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 14 | `utm_campaign` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 15 | `referer_path` [NOVO] | `TEXT` | NULL | `-` |  | - |  |
| 16 | `email_sent_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | #1691: Timestamp quando o lead magnet foi enviado. NULL = pendente. |
| 17 | `email_message_id` [NOVO] | `TEXT` | NULL | `-` |  | - | #1691: Resend message ID para rastreamento de entrega/bounce. |
| 18 | `email_status` [NOVO] | `TEXT` | NULL | `-` |  | - | #1691: Status do envio: pending, sent, failed, bounced, quota_exceeded. |

### `lead_captures` [NOVO Mai 2026]

**Criada em:** 2026-05-12 (`20260512220000_lead_captures`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Leads & CRM

Captura de leads de paginas de marketing. Atribuicao de fonte e dados de contato.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `email` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `sector` | `TEXT` | NULL | `-` |  | - |  |
| 4 | `source` | `TEXT` | NOT NULL | `-` |  | - | Conversion point identifier: lead_magnet_1, lead_magnet_2, lead_magnet_3, newsletter, exit_intent, seo_banner |
| 5 | `origin_url` | `TEXT` | NULL | `-` |  | - | Page URL where the user converted |
| 6 | `metadata` | `JSONB` | NULL | `-` |  | - |  |
| 7 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `referrals` [NOVO Abr 2026]

**Criada em:** 2026-04-05 (`20260405100000_referrals`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Leads & CRM

Indicacoes de usuarios. Status e recompensas.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `referrer_user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `referred_user_id` | `UUID` | NULL | `-` |  | auth.users(id) |  |
| 4 | `code` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `status` | `TEXT` | NOT NULL | `-` |  | - | pending=code issued; signed_up=referred user signed up; converted=paid subscription; credited=referrer month credited |
| 6 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 7 | `converted_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |

### `report_leads` [NOVO Abr 2026]

**Criada em:** 2026-04-05 (`20260405120000_report_leads`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Leads & CRM

Relatorios e exportacoes de leads. Criterios de filtro e metadados de exportacao.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `email` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `empresa` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `cargo` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `newsletter_opt_in` | `BOOLEAN` | NOT NULL | `false` |  | - |  |
| 6 | `source` | `TEXT` | NOT NULL | `'panorama-2026-t1'` |  | - | Identifier of the report / campaign. Allows multi-report reuse of the same table. |
| 7 | `ip_hash` | `TEXT` | NULL | `-` |  | - | First 16 chars of SHA-256 of client IP — abuse signal only, not PII. |
| 8 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `founding_leads` [NOVO Abr 2026]

**Criada em:** 2026-04-20 (`20260420000001_create_founding_leads`)
**RLS:** Sim
**Colunas:** 15
**Dominio:** Leads & CRM

Leads do programa de membros fundadores. Convite-based com status.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `email` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `nome` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `cnpj` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `razao_social` | `TEXT` | NULL | `-` |  | - |  |
| 6 | `motivo` | `TEXT` | NOT NULL | `-` |  | - |  |
| 7 | `stripe_customer_id` | `TEXT` | NULL | `-` |  | - |  |
| 8 | `ip_address` | `TEXT` | NULL | `-` |  | - |  |
| 9 | `user_agent` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 11 | `completed_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 12 | `welcome_sent_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | STORY-791: Timestamp when founders welcome email was sent. NULL = not sent yet.  |
| 13 | `checkout_source` [NOVO] | `TEXT` | NULL | `-` |  | - | STORY-791: UTM source or src param from checkout URL (e.g. "email", "landing", "direct"). |
| 14 | `offer_version` [NOVO] | `TEXT` | NULL | `-` |  | - | STORY-791: Offer version from Stripe metadata (e.g. "v2_lifetime").  |
| 15 | `magic_link_sent_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | FOUND-CRIT-003: timestamp when the Supabase magic-link invite was sent to a  |

### `founding_policy` [NOVO Abr 2026]

**Criada em:** 2026-04-28 (`20260428100000_founding_canonical_policy`)
**RLS:** Sim
**Colunas:** 14
**Dominio:** Leads & CRM

Politica do programa de membros fundadores. Regras, beneficios e expiracao.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `INT` | NOT NULL | `1 CHECK (id = 1)` | PK | - |  |
| 2 | `seat_limit` | `INT` | NOT NULL | `-` |  | - | Hard cap for founding seats. 50 per BIZ-FOUND-002 ADR. Updates require admin. |
| 3 | `deadline_at` | `TIMESTAMPTZ` | NOT NULL | `-` |  | - | Cutoff after which checkout is rejected with 410 Gone. 2026-05-30 23:59:59-03:00. |
| 4 | `discount_pct` | `INT` | NOT NULL | `-` |  | - | Lifetime discount in percent (50). Mirrors Stripe coupon for audit only — Stripe is source of truth. |
| 5 | `coupon_code` | `TEXT` | NOT NULL | `-` |  | - | Stripe coupon id (FOUNDING_LIFETIME). Set up via scripts/create_founding_lifetime_coupon.py. |
| 6 | `active` | `BOOLEAN` | NOT NULL | `TRUE` |  | - | Hard kill switch. FALSE => block all checkouts even before cap/deadline. |
| 7 | `paused_at` | `TIMESTAMPTZ` | NULL | `-` |  | - | Soft pause toggle from admin UI. Distinct from active=false (operational vs structural disable). |
| 8 | `paused_by` | `UUID` | NULL | `-` |  | auth.users(id) |  |
| 9 | `paused_reason` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 11 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 12 | `offer_mode` [NOVO] | `TEXT` | NOT NULL | `-` |  | - | BIZ-FOUND-002 v2: offer type — lifetime (one-time payment) or subscription. |
| 13 | `price_brl_cents` [NOVO] | `INT` | NOT NULL | `-` |  | - | BIZ-FOUND-002 v2: price in BRL cents for one-time lifetime offer. 99700 = R$997. |
| 14 | `consulting_discount_pct` [NOVO] | `INT` | NOT NULL | `-` |  | - | BIZ-FOUND-002 v2: lifetime discount % on consulting tier for founding members. Default 50%. |

### `founding_policy_audit_log` [NOVO Mai 2026]

**Criada em:** 2026-05-07 (`20260507120000_founding_policy_audit_log`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Leads & CRM

Auditoria de mudancas na politica de fundadores. Estado anterior/posterior.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `changed_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 3 | `changed_by` | `UUID` | NULL | `-` |  | auth.users(id) |  |
| 4 | `field_name` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `old_value` | `JSONB` | NULL | `-` |  | - |  |
| 6 | `new_value` | `JSONB` | NULL | `-` |  | - |  |
| 7 | `reason` | `TEXT` | NULL | `-` |  | - |  |

### `partners` [NOVO Mar 2026]

**Criada em:** 2026-03-01 (`20260301200000_create_partners`)
**RLS:** Sim
**Colunas:** 10
**Dominio:** Leads & CRM

Contas de parceiros/afiliados. Consultores, revendedores e canais.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `name` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `slug` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `contact_email` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `contact_name` | `TEXT` | NULL | `-` |  | - |  |
| 6 | `stripe_coupon_id` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `revenue_share_pct` | `NUMERIC(5,2)` | NULL | `25.00` |  | - |  |
| 8 | `status` | `TEXT` | NULL | `'active' CHECK (status IN ('active', 'inactive', 'pending'))` |  | - |  |
| 9 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 10 | `updated_at` [NOVO] | `TIMESTAMPTZ` | NOT NULL | `-` |  | - |  |

### `partner_referrals` [NOVO Mar 2026]

**Criada em:** 2026-03-01 (`20260301200000_create_partners`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Leads & CRM

Indicacoes de parceiros. Status, comissao e conversao.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `partner_id` | `UUID` | NOT NULL | `-` |  | partners(id) |  |
| 3 | `referred_user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 4 | `signup_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 5 | `converted_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 6 | `churned_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 7 | `monthly_revenue` | `NUMERIC(10,2)` | NULL | `-` |  | - |  |
| 8 | `revenue_share_amount` | `NUMERIC(10,2)` | NULL | `-` |  | - |  |

### `consultant_clients` [NOVO Jun 2026]

**Criada em:** 2026-06-12 (`20260612024920_consultant_seats`)
**RLS:** Sim
**Colunas:** 5
**Dominio:** Leads & CRM

Vinculo consultor-cliente. Contas de consultoria a perfis de clientes gerenciados.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `consultant_id` | `UUID` | NOT NULL | `-` |  | public.profiles(id) | The consultant (Consultoria subscriber) |
| 3 | `client_id` | `UUID` | NOT NULL | `-` |  | public.profiles(id) | The client (free-tier user) |
| 4 | `status` | `TEXT` | NOT NULL | `'active' CHECK (status IN ('active', 'revoked'))` |  | - | active | revoked |
| 5 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `consultant_shares` [NOVO Jun 2026]

**Criada em:** 2026-06-12 (`20260612024920_consultant_seats`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** Leads & CRM

Recursos compartilhados por consultores. Relatorios e analises compartilhados com clientes.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `consultant_id` | `UUID` | NOT NULL | `-` |  | public.profiles(id) |  |
| 3 | `client_id` | `UUID` | NOT NULL | `-` |  | public.profiles(id) |  |
| 4 | `resource_type` | `TEXT` | NOT NULL | `-` |  | - | Resource type: busca, pipeline, analise |
| 5 | `resource_id` | `UUID` | NOT NULL | `-` |  | - | UUID of the shared resource |
| 6 | `shared_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `intel_report_purchases` [NOVO Mai 2026]

**Criada em:** 2026-05-05 (`20260505113800_intel_reports_schema`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** Intelligence Reports

Compras de relatorios de inteligencia avulsos.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `product_type` | `TEXT` | NOT NULL | `-` |  | - | Tipo de relatório (ex.: cnpj_raio_x). Permite expansão futura sem schema change. |
| 4 | `entity_key` | `TEXT` | NOT NULL | `-` |  | - | Chave da entidade analisada — para cnpj_raio_x é o CNPJ (digits-only). |
| 5 | `stripe_payment_intent_id` | `TEXT` | NULL | `-` |  | - | Idempotency key contra Stripe webhook. UNIQUE evita double-fulfillment. |
| 6 | `status` | `TEXT` | NOT NULL | `-` |  | - | Lifecycle: pending → generating → ready | failed | refunded. |
| 7 | `pdf_url` | `TEXT` | NULL | `-` |  | - |  |
| 8 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 9 | `expires_at` | `TIMESTAMPTZ` | NOT NULL | `(NOW() + INTERVAL '30 days')` |  | - |  |

### `shared_analyses` [NOVO Abr 2026]

**Criada em:** 2026-04-05 (`20260405000000_shared_analyses`)
**RLS:** Sim
**Colunas:** 15
**Dominio:** Intelligence Reports

Analises compartilhadas. Links publicos/privados para visualizacao de analises.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `hash` | `VARCHAR(12)` | NOT NULL | `-` |  | - |  |
| 3 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 4 | `bid_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `bid_title` | `TEXT` | NOT NULL | `-` |  | - |  |
| 6 | `bid_orgao` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `bid_uf` | `TEXT` | NULL | `-` |  | - |  |
| 8 | `bid_valor` | `NUMERIC` | NULL | `-` |  | - |  |
| 9 | `bid_modalidade` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `viability_score` | `INTEGER` | NOT NULL | `-` |  | - |  |
| 11 | `viability_level` | `TEXT` | NOT NULL | `-` |  | - |  |
| 12 | `viability_factors` | `JSONB` | NOT NULL | `'{}'::jsonb` |  | - |  |
| 13 | `view_count` | `INTEGER` | NULL | `0` |  | - |  |
| 14 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 15 | `expires_at` | `TIMESTAMPTZ` | NULL | `(now() + INTERVAL '30 days')` |  | - |  |

### `monthly_report_subscriptions` [NOVO Jun 2026]

**Criada em:** 2026-06-12 (`20260612030219_monthly_report_subscriptions`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** Intelligence Reports

Assinaturas de relatorios mensais automaticos. Entrega programada de relatorios setoriais.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | public.profiles(id) |  |
| 3 | `sector_id` | `TEXT` | NOT NULL | `-` |  | - | Sector ID from sectors_data.yaml |
| 4 | `status` | `TEXT` | NOT NULL | `'active' CHECK (status IN ('active', 'canceled', 'past_due'))` |  | - | active | canceled | past_due |
| 5 | `stripe_sub_id` | `TEXT` | NULL | `-` |  | - | Stripe subscription ID for billing |
| 6 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `messages`

**Criada em:** 012_create_messages (`012_create_messages`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** User Engagement

Mensagens entre usuarios. Sistema interno de comunicacao para colaboracao em equipe.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `conversation_id` | `uuid` | NOT NULL | `-` |  | conversations(id) |  |
| 3 | `sender_id` | `uuid` | NOT NULL | `-` |  | profiles(id) |  |
| 4 | `body` | `text` | NOT NULL | `-` |  | - |  |
| 5 | `is_admin_reply` | `boolean` | NOT NULL | `false` |  | - |  |
| 6 | `read_by_user` | `boolean` | NOT NULL | `false` |  | - |  |
| 7 | `read_by_admin` | `boolean` | NOT NULL | `false` |  | - |  |
| 8 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |

### `conversations`

**Criada em:** 012_create_messages (`012_create_messages`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** User Engagement

Threads de conversa entre usuarios. Agrupa mensagens em topicos.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `uuid` | NOT NULL | `-` |  | profiles(id) |  |
| 3 | `subject` | `text` | NOT NULL | `-` |  | - |  |
| 4 | `category` | `text` | NOT NULL | `-` |  | - |  |
| 5 | `status` | `text` | NOT NULL | `'aberto' CHECK (status IN ('aberto', 'respondido', 'resolvido'))` |  | - |  |
| 6 | `last_message_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 7 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 8 | `updated_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 9 | `first_response_at` [NOVO] | `timestamptz` | NULL | `-` |  | - |  |

### `user_sector_affinity` [NOVO Jun 2026]

**Criada em:** 2026-06-04 (`20260604135548_create_user_sector_affinity`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** User Engagement

Preferencia setorial do usuario. Aprende interacao com setores para recomendacoes.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `user_id` | `UUID` | NOT NULL | `-` |  | profiles(id) | FK para profiles — user that owns this affinity score. |
| 2 | `sector_id` | `VARCHAR` | NOT NULL | `-` |  | - | Identificador do setor (ex.: tecnologia, saude, educacao). |
| 3 | `affinity_score` | `NUMERIC(3,2)` | NOT NULL | `0.5` |  | - | Pontuacao de afinidade entre 0.0 (nenhuma) e 1.0 (maxima). Default 0.5 (neutro). |
| 4 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 5 | `muted` [NOVO] | `BOOLEAN` | NOT NULL | `-` |  | - | FEEDBACK-005 — Whether this sector is muted by the user. Muted sectors have affinity_score forced to 0.0 but are never removed. |
| 6 | `pre_mute_score` [NOVO] | `NUMERIC(3,2)` | NULL | `-` |  | - | FEEDBACK-005 — Affinity score before muting. Restored when the user un-mutes. NULL when not muted. |

### `user_lifecycle` [NOVO Jun 2026]

**Criada em:** 2026-06-04 (`20260604170000_user_lifecycle`)
**RLS:** Sim
**Colunas:** 3
**Dominio:** User Engagement

Maquina de estado do ciclo de vida do usuario. Trial, active, at_risk, churned, reinstated.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `user_id` | `UUID` | NOT NULL | `-` | PK | public.profiles(id) |  |
| 2 | `lifecycle` | `public.user_lifecycle_state` | NOT NULL | `-` |  | - |  |
| 3 | `computed_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |

### `user_lifecycle_events` [NOVO Jun 2026]

**Criada em:** 2026-06-04 (`20260604170000_user_lifecycle`)
**RLS:** Sim
**Colunas:** 5
**Dominio:** User Engagement

Historico de eventos do ciclo de vida. Transicoes com fonte e timestamp.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `GEN_RANDOM_UUID()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | public.profiles(id) |  |
| 3 | `previous_lifecycle` | `public.user_lifecycle_state` | NULL | `-` |  | - |  |
| 4 | `new_lifecycle` | `public.user_lifecycle_state` | NOT NULL | `-` |  | - |  |
| 5 | `changed_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |

### `user_email_actions` [NOVO Abr 2026]

**Criada em:** 2026-04-30 (`20260430120000_user_email_actions`)
**RLS:** Sim
**Colunas:** 4
**Dominio:** User Engagement

Acoes de usuario via email. Links de confirmacao, unsubscribe, magic links.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `BIGSERIAL` | NOT NULL | `-` | PK | - |  |
| 2 | `email` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `action_type` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now() NOT NULL` |  | - |  |

### `trial_email_log`

**Criada em:** 2026-02-24 (`20260224100000_trial_email_log`)
**RLS:** Sim
**Colunas:** 14
**Dominio:** User Engagement

Log de emails de trial. Disparo de ativacao e lembretes.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `email_type` | `TEXT` | NOT NULL | `-` |  | - | One of: midpoint, expiring, last_day, expired |
| 4 | `sent_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 5 | `email_number` | `INTEGER` | NULL | `-` |  | - | STORY-321: Sequential email number (1-6) in the trial sequence |
| 6 | `opened_at` | `TIMESTAMPTZ` | NULL | `-` |  | - | STORY-310 AC11: Timestamp when email was opened (Resend webhook) |
| 7 | `clicked_at` | `TIMESTAMPTZ` | NULL | `-` |  | - | STORY-310 AC11: Timestamp when email CTA was clicked (Resend webhook) |
| 8 | `resend_email_id` | `TEXT` | NULL | `-` |  | - | STORY-310 AC11: Resend email ID for webhook correlation |
| 9 | `delivery_status` [NOVO] | `TEXT` | NULL | `-` |  | - | Current Resend delivery state: queued|sent|delivered|opened|clicked|bounced|complained|delivery_delayed|failed. NULL = tracking not yet populated (Resend webhook not configured before 2026-04-24). |
| 10 | `delivered_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | Timestamp from email.delivered Resend webhook event. |
| 11 | `bounced_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | Timestamp from email.bounced Resend webhook event. |
| 12 | `complained_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | Timestamp from email.complained Resend webhook event (user marked as spam). |
| 13 | `failed_at` [NOVO] | `TIMESTAMPTZ` | NULL | `-` |  | - | Timestamp from email.failed Resend webhook event. |
| 14 | `bounce_reason` [NOVO] | `TEXT` | NULL | `-` |  | - | Human-readable bounce category from Resend payload (e.g. hard, soft, mailbox_full). |

### `trial_email_dlq` [NOVO Abr 2026]

**Criada em:** 2026-04-10 (`20260410132000_story418_trial_email_dlq`)
**RLS:** Sim
**Colunas:** 13
**Dominio:** User Engagement

Fila de emails de trial com falha. Para retry e investigacao.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `uuid` | NOT NULL | `-` |  | public.profiles(id) |  |
| 3 | `email_address` | `text` | NOT NULL | `-` |  | - |  |
| 4 | `email_type` | `text` | NOT NULL | `-` |  | - |  |
| 5 | `email_number` | `integer` | NOT NULL | `-` |  | - |  |
| 6 | `payload` | `jsonb` | NOT NULL | `'{}'::jsonb` |  | - |  |
| 7 | `attempts` | `integer` | NOT NULL | `0` |  | - |  |
| 8 | `last_error` | `text` | NULL | `-` |  | - |  |
| 9 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 10 | `next_retry_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 11 | `reprocessed_at` | `timestamptz` | NULL | `-` |  | - |  |
| 12 | `reprocessed_count` | `integer` | NOT NULL | `0` |  | - |  |
| 13 | `abandoned_at` | `timestamptz` | NULL | `-` |  | - |  |

### `trial_exit_surveys` [NOVO Abr 2026]

**Criada em:** 2026-04-11 (`20260411000000_trial_exit_surveys`)
**RLS:** Sim
**Colunas:** 5
**Dominio:** User Engagement

Pesquisas de saida do trial. Feedback de cancelamento.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `reason` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `reason_text` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `trial_extensions` [NOVO Abr 2026]

**Criada em:** 2026-04-07 (`20260407000000_trial_extensions`)
**RLS:** Sim
**Colunas:** 5
**Dominio:** User Engagement

Extensoes de trial concedidas por admin. Motivo, duracao e auditoria.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `condition` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `days_added` | `INT` | NOT NULL | `-` |  | - |  |
| 5 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `export_time_saved_survey` [NOVO Abr 2026]

**Criada em:** 2026-04-28 (`20260428100600_export_time_saved_survey`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** User Engagement

Pesquisa de tempo economizado. Estimativas de economia do usuario.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `search_id` | `TEXT` | NULL | `-` |  | - | Search session correlation id (matches search_sessions.id when available) |
| 4 | `export_id` | `TEXT` | NULL | `-` |  | - | Export job/download identifier — correlate with download events |
| 5 | `export_type` | `TEXT` | NOT NULL | `-` |  | - | excel | pdf | sheets |
| 6 | `bid_count` | `INTEGER` | NULL | `-` |  | - | Number of bids included in the export (denominator for per-bid calibration) |
| 7 | `estimated_manual_hours` | `NUMERIC(5,2)` | NOT NULL | `-` |  | - | User-reported manual-equivalent hours (range [0.1, 50]) |
| 8 | `free_text` | `TEXT` | NULL | `-` |  | - | "How would you have done this before?" — optional, capped 2000 chars |
| 9 | `submitted_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |

### `post_purchase_sequences` [NOVO Mai 2026]

**Criada em:** 2026-05-31 (`20260531210000_post_purchase_sequences`)
**RLS:** Sim
**Colunas:** 15
**Dominio:** User Engagement

Sequencias pos-compra. Emails/in-app apos eventos de compra.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `purchase_id` | `UUID` | NOT NULL | `-` |  | - | FK para intel_report_purchases — purchase que originou a sequencia. |
| 3 | `product_sku` | `TEXT` | NOT NULL | `-` |  | - | SKU do produto digital comprado (ex.: fornecedores-vencedores, relatorio-oportunidade). |
| 4 | `user_id` | `UUID` | NOT NULL | `-` |  | - |  |
| 5 | `stage` | `TEXT` | NOT NULL | `-` |  | - |  |
| 6 | `email_sent_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 7 | `email_opened_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 8 | `cta_clicked_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 9 | `upsell_converted` | `BOOLEAN` | NULL | `false` |  | - |  |
| 10 | `next_sequence_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 11 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 12 | `updated_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 13 | `status` | `TEXT` | NOT NULL | `-` |  | - |  |
| 14 | `sequence_steps` | `JSONB` | NOT NULL | `'[]'` |  | - | Array JSONB com steps: [{"step":"delivery","offset_hours":0,"template_id":"...","sent_at":null,"opened_at":null}, ...] |
| 15 | `current_step` | `INTEGER` | NOT NULL | `0` |  | - | Indice do step atual (0-based). Avancado pelo ARQ job apos envio. |

### `seo_metrics` [NOVO Abr 2026]

**Criada em:** 2026-04-07 (`20260407400000_seo_metrics`)
**RLS:** Sim
**Colunas:** 11
**Dominio:** SEO & Analytics

Metricas de SEO. Performance pagina-a-pagina incluindo rankings e trafego.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `BIGINT GENERATED ALWAYS AS IDENTITY` | NOT NULL | `-` | PK | - |  |
| 2 | `date` | `DATE` | NOT NULL | `-` |  | - |  |
| 3 | `source` | `TEXT` | NOT NULL | `'gsc'` |  | - |  |
| 4 | `impressions` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 5 | `clicks` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 6 | `ctr` | `NUMERIC(6,4)` | NOT NULL | `0` |  | - |  |
| 7 | `avg_position` | `NUMERIC(6,2)` | NOT NULL | `0` |  | - |  |
| 8 | `pages_indexed` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 9 | `top_queries` | `JSONB` | NOT NULL | `'[]'::jsonb` |  | - |  |
| 10 | `top_pages` | `JSONB` | NOT NULL | `'[]'::jsonb` |  | - |  |
| 11 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `gsc_metrics` [NOVO Abr 2026]

**Criada em:** 2026-04-22 (`20260422120000_create_gsc_metrics`)
**RLS:** Sim
**Colunas:** 11
**Dominio:** SEO & Analytics

Dados do Google Search Console. Impressoes, clicks, CTR e posicao.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `BIGSERIAL` | NOT NULL | `-` | PK | - |  |
| 2 | `date` | `DATE` | NOT NULL | `-` |  | - |  |
| 3 | `query` | `TEXT` | NULL | `-` |  | - |  |
| 4 | `page` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `country` | `TEXT` | NULL | `'BRA'` |  | - |  |
| 6 | `device` | `TEXT` | NULL | `-` |  | - |  |
| 7 | `clicks` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 8 | `impressions` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 9 | `ctr` | `NUMERIC(6,5)` | NOT NULL | `0` |  | - |  |
| 10 | `position` | `NUMERIC(8,3)` | NOT NULL | `0` |  | - |  |
| 11 | `fetched_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |

### `seo_coverage_manifest` [NOVO Mai 2026]

**Criada em:** 2026-05-10 (`20260510160000_seo_coverage_manifest`)
**RLS:** Sim
**Colunas:** 6
**Dominio:** SEO & Analytics

Cobertura de geracao de paginas SEO. Monitoramento de paginas programaticas.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `entity_type` | `text` | NOT NULL | `-` |  | - |  |
| 3 | `slug` | `text` | NOT NULL | `-` |  | - |  |
| 4 | `coverage_status` | `text` | NOT NULL | `-` |  | - |  |
| 5 | `bid_count` | `integer` | NULL | `0` |  | - |  |
| 6 | `last_updated` | `timestamptz` | NULL | `now()` |  | - |  |

### `network_events_agg` [NOVO Mai 2026]

**Criada em:** 2026-05-31 (`20260531232239_network_events_agg`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Network Intelligence

Dados agregados de eventos da rede de contratacao. Pre-computado para dashboards.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `evento_tipo` | `TEXT` | NOT NULL | `-` |  | - | Tipo do evento: search_query, sector_view, org_view, cnpj_lookup, discount_view, migration_view, competitor_view |
| 3 | `dimensao_tipo` | `TEXT` | NOT NULL | `-` |  | - | Tipo da dimensao: setor, uf, modalidade, orgao, municipio |
| 4 | `dimensao_valor` | `TEXT` | NOT NULL | `-` |  | - | Valor da dimensao (ex: "saude", "SP", "pregao") — nunca PII |
| 5 | `periodo` | `DATE` | NOT NULL | `-` |  | - | Data do evento (agregacao diaria) |
| 6 | `contagem` | `INTEGER` | NULL | `1` |  | - | Contagem de eventos neste periodo — incremental via UPSERT |
| 7 | `metadados` | `JSONB` | NULL | `'{}'::jsonb` |  | - | Metadados adicionais: {"setores": [], "ufs": [], "modalidades": []}. NUNCA user_id, cnpj, email, ip. |
| 8 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `network_events_agg_weekly` [NOVO Jun 2026]

**Criada em:** 2026-06-12 (`20260612100000_network_events_agg_weekly`)
**RLS:** Sim
**Colunas:** 9
**Dominio:** Network Intelligence

Agregacoes semanais de eventos da rede. Sumarios para performance de dashboard.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `evento_tipo` | `TEXT` | NOT NULL | `-` |  | - | Tipo do evento: search_query, sector_view, org_view, cnpj_lookup, discount_view, migration_view, competitor_view |
| 3 | `dimensao_tipo` | `TEXT` | NOT NULL | `-` |  | - | Tipo da dimensao: setor, uf, modalidade, orgao, municipio |
| 4 | `dimensao_valor` | `TEXT` | NOT NULL | `-` |  | - | Valor da dimensao (ex: "saude", "SP", "pregao") — nunca PII |
| 5 | `semana_inicio` | `DATE` | NOT NULL | `-` |  | - | Data de inicio da semana (segunda-feira) — ISO week start |
| 6 | `contagem` | `INTEGER` | NULL | `1` |  | - | Contagem agregada de eventos na semana — soma dos registros diarios |
| 7 | `metadados` | `JSONB` | NULL | `'{}'::jsonb` |  | - | Metadados merged da semana: {"setores": [], "ufs": [], "modalidades": []}. NUNCA user_id, cnpj, email, ip. |
| 8 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 9 | `updated_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `subcontract_interests` [NOVO Jun 2026]

**Criada em:** 2026-06-12 (`20260612022146_subcontract_marketplace`)
**RLS:** Sim
**Colunas:** 5
**Dominio:** Network Intelligence

Sinais de interesse em subcontratacao. Registro de interesse do usuario.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `opportunity_id` | `UUID` | NOT NULL | `-` |  | subcontract_opportunities(id) |  |
| 3 | `user_id` | `UUID` | NOT NULL | `-` |  | profiles(id) |  |
| 4 | `message` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |

### `subcontract_opportunities` [NOVO Jun 2026]

**Criada em:** 2026-06-12 (`20260612022146_subcontract_marketplace`)
**RLS:** Sim
**Colunas:** 15
**Dominio:** Network Intelligence

Marketplace de oportunidades de subcontratacao. Criterios de matching.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `contract_id` | `UUID` | NULL | `-` |  | pncp_supplier_contracts(id) | FK para pncp_supplier_contracts — contrato original que gerou a oportunidade |
| 3 | `winner_cnpj` | `TEXT` | NOT NULL | `-` |  | - | CNPJ do vencedor do contrato original |
| 4 | `winner_name` | `TEXT` | NULL | `-` |  | - | Nome razao social do vencedor |
| 5 | `sector` | `TEXT` | NULL | `-` |  | - |  |
| 6 | `value` | `DECIMAL(15,2)` | NULL | `-` |  | - |  |
| 7 | `services_needed` | `TEXT[]` | NULL | `'{}'` |  | - | Lista de servicos/especialidades necessarias para subcontratacao |
| 8 | `status` | `TEXT` | NOT NULL | `-` |  | - | Status: open (disponivel), matched (interesse em andamento), closed (fechado/arquivado) |
| 9 | `uf` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `municipio` | `TEXT` | NULL | `-` |  | - |  |
| 11 | `orgao_nome` | `TEXT` | NULL | `-` |  | - |  |
| 12 | `objeto` | `TEXT` | NULL | `-` |  | - |  |
| 13 | `discovery_reason` | `TEXT` | NULL | `-` |  | - | Resumo textual da heuristica que identificou esta oportunidade |
| 14 | `created_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 15 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |

### `health_checks`

**Criada em:** 2026-02-28 (`20260228150000_add_health_checks_table`)
**RLS:** Sim
**Colunas:** 5
**Dominio:** Operations

Resultados de health checks do sistema. Sondas periodicas para monitoramento.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `overall_status` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `sources_json` | `JSONB` | NOT NULL | `'{}'` |  | - |  |
| 4 | `components_json` | `JSONB` | NOT NULL | `'{}'` |  | - |  |
| 5 | `latency_ms` | `INTEGER` | NULL | `-` |  | - |  |

### `incidents`

**Criada em:** 2026-02-28 (`20260228150001_add_incidents_table`)
**RLS:** Sim
**Colunas:** 7
**Dominio:** Operations

Log de incidentes do sistema. Anomalias e falhas detectadas.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid() PRIMARY KEY` | PK | - |  |
| 2 | `started_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 3 | `resolved_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 4 | `status` | `TEXT` | NOT NULL | `'ongoing' CHECK (status IN ('ongoing', 'resolved'))` |  | - |  |
| 5 | `affected_sources` | `TEXT[]` | NOT NULL | `'{}'` |  | - |  |
| 6 | `description` | `TEXT` | NOT NULL | `''` |  | - |  |
| 7 | `updated_at` [NOVO] | `TIMESTAMPTZ` | NOT NULL | `-` |  | - |  |

### `app_config` [NOVO Abr 2026]

**Criada em:** 2026-04-28 (`20260428100700_app_config_table`)
**RLS:** Sim
**Colunas:** 5
**Dominio:** Operations

Configuracao runtime da aplicacao. Feature flags, manutencao e settings.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `key` | `TEXT` | NOT NULL | `-` | PK | - | Snake_case identifier; stable contract for backend reads |
| 2 | `value` | `JSONB` | NOT NULL | `-` |  | - | JSONB payload — supports scalars, arrays, objects |
| 3 | `description` | `TEXT` | NULL | `-` |  | - | Human-readable explanation of what this config controls |
| 4 | `updated_at` | `TIMESTAMPTZ` | NOT NULL | `NOW()` |  | - |  |
| 5 | `updated_by` | `UUID` | NULL | `-` |  | auth.users(id) | Admin user that last mutated this row (audit trail) |

### `ingestion_checkpoints` [NOVO Mar 2026]

**Criada em:** 2026-03-26 (`20260326000000_datalake_raw_bids`)
**RLS:** Sim
**Colunas:** 12
**Dominio:** Operations

Checkpoints de ingestao PNCP. Progresso por UF/modalidade para crawl resume.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `BIGINT GENERATED ALWAYS AS IDENTITY` | NOT NULL | `-` | PK | - |  |
| 2 | `source` | `TEXT` | NOT NULL | `'pncp'` |  | - |  |
| 3 | `uf` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `modalidade_id` | `INTEGER` | NOT NULL | `-` |  | - |  |
| 5 | `last_date` | `DATE` | NOT NULL | `-` |  | - |  |
| 6 | `last_page` | `INTEGER` | NULL | `1` |  | - | Last successfully fetched page number (1-indexed). Resume from last_page + 1. |
| 7 | `records_fetched` | `INTEGER` | NULL | `0` |  | - |  |
| 8 | `status` | `TEXT` | NOT NULL | `-` |  | - |  |
| 9 | `error_message` | `TEXT` | NULL | `-` |  | - |  |
| 10 | `started_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 11 | `completed_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 12 | `crawl_batch_id` | `TEXT` | NOT NULL | `-` |  | - | Foreign-key reference to ingestion_runs.crawl_batch_id (not enforced for perf). |

### `ingestion_runs` [NOVO Mar 2026]

**Criada em:** 2026-03-26 (`20260326000000_datalake_raw_bids`)
**RLS:** Sim
**Colunas:** 15
**Dominio:** Operations

Log de execucao de ingestao PNCP. Timing, linhas processadas e status.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `BIGINT GENERATED ALWAYS AS IDENTITY` | NOT NULL | `-` | PK | - |  |
| 2 | `crawl_batch_id` | `TEXT` | NOT NULL | `-` |  | - |  |
| 3 | `run_type` | `TEXT` | NOT NULL | `-` |  | - |  |
| 4 | `status` | `TEXT` | NOT NULL | `-` |  | - |  |
| 5 | `started_at` | `TIMESTAMPTZ` | NOT NULL | `now()` |  | - |  |
| 6 | `completed_at` | `TIMESTAMPTZ` | NULL | `-` |  | - |  |
| 7 | `total_fetched` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 8 | `inserted` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 9 | `updated` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 10 | `unchanged` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 11 | `errors` | `INTEGER` | NOT NULL | `0` |  | - |  |
| 12 | `ufs_completed` | `TEXT[]` | NULL | `-` |  | - |  |
| 13 | `ufs_failed` | `TEXT[]` | NULL | `-` |  | - |  |
| 14 | `duration_s` | `NUMERIC(10,1)` | NULL | `-` |  | - |  |
| 15 | `metadata` | `JSONB` | NOT NULL | `'{}'` |  | - | Freeform JSONB for worker version, config snapshot, trigger source, etc. |

### `integrations_webhooks` [NOVO Jun 2026]

**Criada em:** 2026-06-17 (`20260617000000_integrations_webhooks`)
**RLS:** Sim
**Colunas:** 11
**Dominio:** Operations

Endpoints de webhook para integracao externa. URLs registradas para eventos em tempo real.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `channel` | `TEXT` | NOT NULL | `-` |  | - | Notification channel: slack, teams, or email |
| 4 | `label` | `TEXT` | NULL | `-` |  | - |  |
| 5 | `webhook_url` | `TEXT` | NULL | `-` |  | - | Incoming webhook URL for Slack/Teams channels |
| 6 | `email_target` | `TEXT` | NULL | `-` |  | - | Target email address for email channel |
| 7 | `events` | `TEXT[]` | NULL | `'{}'` |  | - | Array of event types to notify for: new_edital, deadline_24h, deadline_6h, deadline_1h, pregao_started, result_published |
| 8 | `is_active` | `BOOLEAN` | NULL | `true` |  | - |  |
| 9 | `last_triggered_at` | `TIMESTAMPTZ` | NULL | `-` |  | - | Timestamp of last notification sent (used for rate limiting) |
| 10 | `created_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |
| 11 | `updated_at` | `TIMESTAMPTZ` | NULL | `now()` |  | - |  |

### `data_deletion_requests` [NOVO Jun 2026]

**Criada em:** 2026-06-15 (`20260615130000_data_deletion_requests`)
**RLS:** Sim
**Colunas:** 10
**Dominio:** Operations

Solicitacoes de exclusao de dados LGPD. Workflow completo com verificacao de identidade.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `uuid` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `uuid` | NOT NULL | `-` |  | public.profiles(id) |  |
| 3 | `status` | `text` | NOT NULL | `-` |  | - |  |
| 4 | `requested_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |
| 5 | `confirmed_at` | `timestamptz` | NULL | `-` |  | - |  |
| 6 | `completed_at` | `timestamptz` | NULL | `-` |  | - |  |
| 7 | `cancelled_at` | `timestamptz` | NULL | `-` |  | - |  |
| 8 | `deletion_token` | `text` | NULL | `-` |  | - |  |
| 9 | `reason` | `text` | NULL | `''` |  | - |  |
| 10 | `created_at` | `timestamptz` | NOT NULL | `now()` |  | - |  |

### `google_sheets_exports`

**Criada em:** 014_google_sheets_exports (`014_google_sheets_exports`)
**RLS:** Sim
**Colunas:** 8
**Dominio:** Legacy

Exportacoes para Google Sheets. Jobs de exportacao para relatorios integrados.

| # | Coluna | Tipo | Nulo | Default | PK | FK | Comentario |
|---|--------|------|------|---------|----|----|-----------|
| 1 | `id` | `UUID` | NOT NULL | `gen_random_uuid()` | PK | - |  |
| 2 | `user_id` | `UUID` | NOT NULL | `-` |  | auth.users(id) |  |
| 3 | `spreadsheet_id` | `VARCHAR(255)` | NOT NULL | `-` |  | - | Google Sheets spreadsheet ID (from URL: docs.google.com/spreadsheets/d/{spreadsheet_id}) |
| 4 | `spreadsheet_url` | `TEXT` | NOT NULL | `-` |  | - | Full shareable URL to the Google Sheets spreadsheet. Used to re-open exports. |
| 5 | `search_params` | `JSONB` | NOT NULL | `-` |  | - | JSONB snapshot of search parameters used for this export. Example: {"ufs": ["SP", "RJ"], "dataInicial": "2026-01-01", "setor": "Vestuário e Uniformes"}. Enables search reproducibility and analytics. |
| 6 | `total_rows` | `INT` | NOT NULL | `-` |  | - | Number of licitações exported to this spreadsheet. Used for usage analytics and quota tracking. |
| 7 | `created_at` | `TIMESTAMPTZ` | NULL | `NOW()` |  | - |  |
| 8 | `last_updated_at` | `TIMESTAMPTZ` | NULL | `NOW()` |  | - | Timestamp of last update to this spreadsheet (for "update existing spreadsheet" mode). Differs from created_at for updated exports. |
