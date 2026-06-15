# Registro de Operacoes de Tratamento de Dados Pessoais (ROPA)

**Empresa:** CONFENGE Avaliacoes e Inteligencia Artificial LTDA
**Produto:** SmartLic (https://smartlic.tech)
**Documento:** ROPA conforme Lei Geral de Protecao de Dados (LGPD) - Art. 37
**Data de criacao:** 2026-06-15
**Ultima revisao:** 2026-06-15
**Responsavel:** DPO / Equipe de Engenharia

---

## 1. Identificacao do Controlador

| Campo | Valor |
|-------|-------|
| Empresa | CONFENGE Avaliacoes e Inteligencia Artificial LTDA |
| Produto | SmartLic |
| URL | https://smartlic.tech |
| Natureza | Controlador |
| Encarregado (DPO) | Tiago Sasaki (tiago.sasaki@gmail.com) |

---

## 2. Base Legal Aplicavel

| Base Legal | Aplicacao |
|------------|-----------|
| Art. 7o, I - Consentimento | Coleta de dados no cadastro (signup); aceite dos Termos de Uso e Politica de Privacidade |
| Art. 7o, IX - Legitimo Interesse | Operacao do servico (busca de licitacoes, classificacao IA, analise de viabilidade); melhorias de produto; seguranca |
| Art. 7o, II - Obrigacao Legal | Retencao de notas fiscais e registros de pagamento (obrigacao fiscal); registros de auditoria |
| Art. 7o, V - Execucao de Contrato | Prestacao do servico contratado pelo assinante (planos Pro, Consultoria) |

---

## 3. Inventario de Operacoes de Tratamento

### 3.1 Criacao de Conta (Signup)

| Campo | Detalhe |
|-------|---------|
| **Dados pessoais** | Email, nome, senha (hash), CPF/CNPJ (opcional), CNAE primario (opcional), UFs de interesse (opcional), aceite ToS |
| **Finalidade** | Criacao e autenticacao de conta do usuario |
| **Base legal** | Art. 7o, I (consentimento) + Art. 7o, V (execucao de contrato) |
| **Armazenamento** | Supabase: `auth.users` (email, senha hash), `profiles` (nome, CPF/CNPJ, CNAE, UFs) |
| **Retencao** | Indeterminado enquanto a conta estiver ativa; 30 dias apos soft-delete (anonimizacao) |
| **Compartilhamento** | Resend (email de confirmacao), Supabase Auth (autenticacao) |
| **Categoria de titulares** | Usuarios cadastrados (pessoas fisicas e juridicas) |

### 3.2 Busca de Licitacoes (Operacao do Servico)

| Campo | Detalhe |
|-------|---------|
| **Dados pessoais** | Historicos de busca (termos, filtros, setores, UFs, datas), ID do usuario |
| **Finalidade** | Execucao do servico contratado: buscar, classificar e analisar licitacoes |
| **Base legal** | Art. 7o, IX (legitimo interesse - funcionamento do servico) + Art. 7o, V (execucao de contrato) |
| **Armazenamento** | Supabase: `search_history`, `search_results_cache`, `analytics_events`; Redis: cache efemero (4h TTL) |
| **Retencao** | Historico de buscas: enquanto a conta estiver ativa; cache: 24h (Supabase) / 4h (Redis); 30 dias apos delecao |
| **Compartilhamento** | OpenAI API (GPT-4.1-nano) - classificacao setorial e resumos executivos (dados anonimizados, sem PII identificavel) |
| **Categoria de titulares** | Usuarios cadastrados |

### 3.3 Processamento de Pagamento

| Campo | Detalhe |
|-------|---------|
| **Dados pessoais** | Nome, email, endereco de cobranca (facultativo), dados de pagamento (processados pelo Stripe - SmartLic NAO armazena dados de cartao) |
| **Finalidade** | Cobranca de assinaturas mensais/semestrais/anuais e planos vitalicios (founding) |
| **Base legal** | Art. 7o, V (execucao de contrato) + Art. 7o, II (obrigacao fiscal - retencao de registros de faturamento) |
| **Armazenamento** | Stripe: registros de pagamento e assinatura; Supabase: `profiles.plan_type`, `subscription_status` |
| **Retencao** | Stripe: enquanto a conta existir + periodo fiscal obrigatorio; SmartLic: enquanto a conta estiver ativa |
| **Compartilhamento** | Stripe Inc. (processador de pagamento) - sujeito a legislacao internacional (EUA), com clausulas contratuais padrao (SCCs) |
| **Categoria de titulares** | Assinantes (pessoas fisicas e juridicas) |

### 3.4 Comunicacao por Email

| Campo | Detalhe |
|-------|---------|
| **Dados pessoais** | Email do usuario |
| **Finalidade** | Emails transacionais (confirmacao de cadastro, recuperacao de senha, notificacoes de editais, alertas) e emails de marketing (digest semanal, com opt-out) |
| **Base legal** | Art. 7o, I (consentimento - marketing) + Art. 7o, V (execucao de contrato - emails transacionais) |
| **Armazenamento** | Resend (logs de envio), Supabase: `email_logs`, `unsubscribe_tokens` |
| **Retencao** | Logs de envio: 90 dias; preferencias de unsubscribe: indeterminado |
| **Compartilhamento** | Resend Inc. (servico de email) |
| **Categoria de titulares** | Usuarios cadastrados, leads (capturados via landing page) |

### 3.5 Analytics e Melhoria do Produto

| Campo | Detalhe |
|-------|---------|
| **Dados pessoais** | ID do usuario, acoes na plataforma (paginas visitadas, funcionalidades usadas, duracoes), user-agent, IP anonimizado |
| **Finalidade** | Melhoria continua do produto, entendimento do comportamento do usuario, deteccao de erros |
| **Base legal** | Art. 7o, IX (legitimo interesse) |
| **Armazenamento** | Mixpanel, Sentry, Prometheus |
| **Retencao** | Mixpanel: 12 meses; Sentry: 90 dias; Prometheus: 7 dias |
| **Compartilhamento** | Mixpanel Inc. (analytics), Sentry (error tracking) - ambos com SCCs |
| **Categoria de titulares** | Usuarios cadastrados |

### 3.6 Monitoramento e Seguranca

| Campo | Detalhe |
|-------|---------|
| **Dados pessoais** | IP, user-agent, headers HTTP, logs de requisicao (sem PII), ID do usuario autenticado |
| **Finalidade** | Seguranca da plataforma, deteccao de abuso, rate limiting, auditoria |
| **Base legal** | Art. 7o, IX (legitimo interesse - protecao do servico) + Art. 7o, II (obrigacao legal - registros de acesso) |
| **Armazenamento** | Redis (rate limiter - efemero, TTL minutos); Supabase: `audit_logs`; Sentry: logs de erro |
| **Retencao** | Rate limiter: minutos / horas; audit_logs: 90 dias; Sentry: 90 dias |
| **Compartilhamento** | Sentry (error tracking) |
| **Categoria de titulares** | Usuarios cadastrados e visitantes nao autenticados (paginas publicas) |

### 3.7 Tratamento por IA (Classificacao Setorial)

| Campo | Detalhe |
|-------|---------|
| **Dados pessoais** | Nenhum - apenas texto do edital (dados publicos governamentais) e nome do setor selecionado |
| **Finalidade** | Classificacao de relevancia setorial dos editais usando GPT-4.1-nano (OpenAI) |
| **Base legal** | Art. 7o, IX (legitimo interesse) |
| **Armazenamento** | OpenAI API - sem retencao (configuracao `store: false`); Supabase: resultados de classificacao |
| **Retencao** | OpenAI: sem retencao; Supabase: enquanto o resultado da busca existir |
| **Compartilhamento** | OpenAI (processamento de texto de licitacoes - dados governamentais publicos) |
| **Categoria de titulares** | Nao se aplica (dados de editais publicos) |

---

## 4. Fluxo de Exclusao de Dados (LGPD Art. 18)

### 4.1 Fluxo do Titular (Double Opt-Out)

O fluxo implementado segue o padrao **double opt-out**, documentado em `backend/routes/data_deletion.py`:

1. **Solicitacao** - O titular acessa `/conta` e clica em "Excluir minha conta" (`POST /v1/me/request-deletion`)
2. **Email de confirmacao** - Um email com token unico (HMAC-SHA256 + pepper) eh enviado ao email cadastrado
3. **Confirmacao** - O titular clica no link do email ou insere o token (`POST /v1/me/confirm-deletion`)
4. **Anonimizacao** - O perfil eh anonimizado (soft-delete):
   - Email: `deleted_{hash}@anonymous`
   - Nome: "Usuario Excluido"
   - Phone: vazio
   - CPF/CNPJ: null
   - UFs: lista vazia
   - `deleted_at` registrado com timestamp
5. **Retencao pos-delecao** - 30 dias (soft-delete) para recuperacao em caso de engano
6. **Anonimizacao final** - Apos 30 dias, `deleted_at` vira flag de purge fisico

### 4.2 Fluxo Administrativo

- `DELETE /v1/me/admin/{user_id}` - Admin pode forcar exclusao direta (bypass double opt-out)
- `POST /v1/me/cancel-deletion` - Titular pode cancelar solicitacao pendente

### 4.3 Tabelas Afetadas pela Exclusao

| Tabela | Acao | Prazo |
|--------|------|-------|
| `auth.users` | Desativar ou anonimizar | Imediato (soft-delete) |
| `profiles` | Anonimizar PII | Imediato (soft-delete) |
| `data_deletion_requests` | Manter registro | Indeterminado (auditoria) |
| `search_history` | Anonimizar (remover user_id) | Imediato |
| `pipeline_items` | Anonimizar (remover user_id) | Imediato |
| `search_results_cache` | Anonimizar ou remover entradas | Imediato |
| `analytics_events` | Anonimizar (remover user_id) | Imediato |

---

## 5. Medidas de Seguranca

| Medida | Descricao |
|--------|-----------|
| Criptografia em repouso | Supabase PostgreSQL: criptografia em disco (SSD encriptado); Redis: sem dados persistentes com PII |
| Criptografia em transito | TLS 1.3 em todas as comunicacoes externas (API, frontend, Webhooks) |
| Autenticacao | JWT com 3 estrategias (JWKS ES256 > PEM > HS256), validacao L1 LRU 60s + L2 Redis 5min |
| Autorizacao | RLS (Row Level Security) no Supabase + validacao explicita `.eq("user_id")` em todas as queries |
| Rate limiting | Redis token bucket: 10 req/min busca, 5 req/5min auth, 3 req/10min signup |
| Log sanitization | `log_sanitizer.py` mascara PII em logs (Issue #168) |
| HMAC tokens | Tokens de confirmacao de delecao usam HMAC-SHA256 com pepper (`LGPD_DELETION_SECRET`) |
| Segregacao de processos | Web + Worker separados via `PROCESS_TYPE`; Redis como barramento |

---

## 6. Compartilhamento com Terceiros

| Terceiro | Dados Compartilhados | Finalidade | Jurisdicao | Base Legal para Transferencia |
|----------|----------------------|------------|------------|-------------------------------|
| Stripe Inc. | Nome, email, valor, status de assinatura | Processamento de pagamentos | EUA | SCCs (Clausulas Contratuais Padrao) |
| Resend Inc. | Email | Envio de emails transacionais e marketing | EUA | SCCs |
| OpenAI | Texto de editais publicos (sem PII) | Classificacao IA (GPT-4.1-nano) | EUA | Dados anonimizados - Art. 12 LGPD |
| Sentry (Functional Software Inc.) | IP, user-agent, stack traces (sem PII) | Error tracking e monitoramento | EUA | SCCs |
| Mixpanel Inc. | ID de usuario, acoes, IP anonimizado | Analytics de produto | EUA | SCCs |
| Supabase | Todos os dados transacionais | Banco de dados e autenticacao | EUA (multi-regiao) | SCCs |
| Upstash / Railway | Dados de cache (Redis) | Cache efemero, filas | EUA | SCCs |

---

## 7. Direitos dos Titulares (LGPD Art. 18)

| Direito | Como Exercer | Prazo de Atendimento |
|---------|-------------|----------------------|
| Confirmacao de tratamento | GET `/v1/me` - dashboard da conta | Imediato (self-service) |
| Acesso aos dados | GET `/v1/me/export` - exportacao JSON/CSV | Imediato (self-service) |
| Correcao de dados | PATCH `/v1/me` - atualizar perfil | Imediato (self-service) |
| Exclusao de dados | POST `/v1/me/request-deletion` | Token via email em 24h; anonimizacao apos confirmacao |
| Portabilidade | GET `/v1/me/export` - formato estruturado | Imediato (self-service) |
| Revogacao de consentimento | Ajustar preferencias em `/conta` ou solicitar exclusao | Imediato |
| Informacao sobre compartilhamento | Este documento + Politica de Privacidade | Disponivel publicamente |
| Oposicao a tratamento | Email para tiago.sasaki@gmail.com | 15 dias uteis |

---

## 8. Retention Schedule

| Categoria de Dados | Periodo de Retencao | Acao Apos Prazo |
|--------------------|---------------------|-----------------|
| Perfil do usuario (ativo) | Indeterminado (enquanto a conta existir) | - |
| Historico de buscas | Enquanto a conta existir | Anonimizar apos delecao |
| Cache de resultados | 24h (Supabase) / 4h (Redis) | Purge automatico (pg_cron) |
| Logs de auditoria | 90 dias | Purge fisico |
| Logs de erro (Sentry) | 90 dias | Purge automatico |
| Analytics (Mixpanel) | 12 meses | Purge automatico |
| Dados anonimizados (pos-delecao) | 30 dias | Purge fisico completo |
| Registros de pagamento (Stripe) | Indeterminado (obrigacao fiscal) | - |
| Tokens de unsubscribe | Indeterminado | - |

---

## 9. Aprovacao e Historico

| Versao | Data | Alteracao | Responsavel |
|--------|------|-----------|-------------|
| 1.0 | 2026-06-15 | Versao inicial do ROPA SmartLic | Equipe de engenharia |
