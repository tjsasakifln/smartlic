# Service Level Agreements (SLAs) — SmartLic

**Versao:** 1.0
**Criado:** 2026-06-17
**Owner:** @devops
**Issue:** #1958
**Proxima revisao trimestral:** 2026-09-17

---

## Sumario

1. [Escopo e Definicoes](#1-escopo-e-definicoes)
2. [Uptime SLAs](#2-uptime-slas)
3. [Latencia SLAs](#3-latencia-slas)
4. [Recovery Point Objective (RPO)](#4-recovery-point-objective-rpo)
5. [Recovery Time Objective (RTO)](#5-recovery-time-objective-rto)
6. [Exclusoes e Creditos](#6-exclusoes-e-creditos)
7. [Public Status Dashboard](#7-public-status-dashboard)
8. [Prometheus Alert Rules](#8-prometheus-alert-rules)
9. [Revisao Trimestral](#9-revisao-trimestral)
10. [Referencias](#10-referencias)

---

## 1. Escopo e Definicoes

### 1.1 Servicos Cobertos

| Servico | Descricao | URL Base |
|---------|-----------|----------|
| **SmartLic App (Composite)** | Experiencia completa do usuario (frontend + API + banco) | `https://smartlic.tech` |
| **API (/v1/)** | Endpoints REST da API publica e autenticada | `https://api.smartlic.tech/v1/` |
| **SEO Pages** | Paginas programaticas publicas (observatorio, sitemaps, blog) | `https://smartlic.tech/observatorio/...`, `https://smartlic.tech/blog/...` |

### 1.2 Definicoes

| Termo | Definicao |
|-------|-----------|
| **Downtime** | Periodo em que o servico retorna HTTP 5xx ou nao responde por mais de 1 minuto consecutivo, conforme verificado por probes externos (UptimeRobot/BetterStack) a cada 5 minutos. |
| **Disponibilidade Mensal** | `(total_minutos_no_mes - minutos_de_downtime) / total_minutos_no_mes * 100` |
| **Janela de Medicao** | Rolling window de 30 dias corridos, exceto para latencia (7 dias). |
| **Horario Comercial** | Dias uteis das 8h as 18h horario de Brasilia (BRT). |
| **Erro** | Resposta HTTP com codigo 5xx (exceto 503 de rate limiting intencional documentado). |
| **Incidente SEV1** | Indisponibilidade total de um servico por > 5 minutos consecutivos. |
| **Incidente SEV2** | Degradacao parcial (latencia > 2x p95 target, erro > 5%) por > 15 minutos. |
| **Manutencao Programada** | Janela de ate 2 horas, notificada com 48h de antecedencia via status page e email. Nao conta como downtime. |

### 1.3 Relacao com SLOs Internos

Os SLAs contratuais abaixo referenciam SLOs (Service Level Objectives) internos definidos em `docs/architecture/error-budget-slo.md`. Enquanto SLOs sao metas aspiracionais que o time de engenharia persegue, SLAs sao compromissos contratuais com clientes. SLAs sao **estritamente iguais ou menos agressivos** que os SLOs correspondentes.

---

## 2. Uptime SLAs

### 2.1 Tabela de Uptime por Servico

| Servico | SLA Mensal | Downtime Maximo/mes | SLO Correspondente | Notas |
|---------|-----------|---------------------|--------------------|-------|
| **SmartLic App (Composite)** | **99.5%** | 3.6 horas | 99.5% (#1802) | Experiencia completa do usuario |
| **API (/v1/)** | **99.9%** | 43.2 minutos | 99.5% (#1802) | Endpoints REST. SLA mais alto por atender integracoes de parceiros |
| **SEO Pages** | **99.0%** | 7.2 horas | N/A | Paginas publicas (ISR, servem stale sob degradacao) |

### 2.2 Justificativa dos Valores

| Servico | Raciocinio |
|---------|------------|
| **SmartLic App (99.5%)** | Alinhado com o SLO existente para o estagio pre-revenue beta. Downtime de 3.6h/mes e aceitavel para usuarios B2G que usam a plataforma para analise, nao para operacoes em tempo real. |
| **API (99.9%)** | A API e consumida por integracoes e automacoes de parceiros, que dependem de disponibilidade consistente. O upgrade de 99.5% para 99.9% reflete que o backend tem health checks, circuit breakers e fallbacks que previnem downtime prolongado. |
| **SEO Pages (99.0%)** | Paginas programaticas servem conteudo estatico via ISR com `revalidate=3600`. Em caso de indisponibilidade do backend, pages continuam servindo conteudo stale. O SLA reflete essa resiliencia intrinseca. |

### 2.3 Uptime Historico para Referencia

| Mes | App | API | SEO Pages | Notas |
|-----|-----|-----|-----------|-------|
| 2026-04 | ~99.72% | ~99.85% | ~99.9% | CRIT-080/083/084, outage de 3 dias parcial |
| 2026-05 | ~99.93% | ~99.95% | ~99.95% | Estabilizacao pos-RES-BE |
| 2026-06 (ate dia 17) | ~99.97% | ~99.98% | ~99.98% | Operacao normal |

> **Nota:** Os valores historicos sao estimados com base em metricas disponiveis. A medicao precisa com probes externos (UptimeRobot) comecou em producao plena a partir de maio/2026.

---

## 3. Latencia SLAs

### 3.1 Tabela de Latencia por Endpoint

| Endpoint | Descricao | p95 | p99 | Janela | SLO Correspondente |
|----------|-----------|-----|-----|--------|-------------------|
| `POST /buscar` | Pipeline completo de busca multi-fonte | < 5s | < 20s | 7 dias | < 500ms (DataLake) — SLO interno exclui fallback live-API |
| `GET /buscar-progress/{id}` | SSE de progresso de busca | < 200ms | < 500ms | 7 dias | N/A |
| `GET /pipeline` | Listagem do Kanban de oportunidades | < 500ms | < 2s | 7 dias | N/A |
| `POST/PATCH/DELETE /pipeline` | CRUD de itens no pipeline | < 1s | < 3s | 7 dias | N/A |
| `GET /dashboard` | Dashboard de analytics | < 2s | < 5s | 7 dias | N/A |
| `GET /dashboard/*` | Endpoints especificos de analytics | < 1s | < 3s | 7 dias | N/A |
| `GET /observatorio/[slug]` | Pagina publica de observatorio | < 500ms | < 2s | 7 dias | N/A |
| `GET /health/live` | Liveness probe | < 50ms | < 100ms | 7 dias | N/A |
| `GET /health/ready` | Readiness probe | < 500ms | < 2s | 7 dias | N/A |

### 3.2 Metodo de Medicao

A latencia de cada endpoint e medida pelo histograma Prometheus `smartlic_http_response_duration_seconds` com labels `method`, `route`, `status_class`. O p95/p99 e calculado via:

```promql
# p95 por endpoint
histogram_quantile(0.95,
  sum(rate(smartlic_http_response_duration_seconds_bucket{route="/buscar"}[7d]))
  by (le)
)

# p99 por endpoint
histogram_quantile(0.99,
  sum(rate(smartlic_http_response_duration_seconds_bucket{route="/buscar"}[7d]))
  by (le)
)
```

Endpoints sem metrica dedicada usam o histograma generico `smartlic_search_duration_seconds` (busca) ou `smartlic_http_response_duration_seconds` (demais).

### 3.3 Notas sobre Latencia de Busca

- **Pesquisa via DataLake (caso normal, ~95% das buscas):** Latencia p95 < 100ms (conforme SLO #1802). O SLA de 5s p95 cobre o cenario com fallback para APIs live (PNCP/PCP/ComprasGov), que ocorre quando o DataLake retorna 0 resultados.
- **SSE timeout:** O streaming SSE tem body timeout de 0 (desabilitado) e heartbeat a cada 15s. A latencia p95 de 5s se refere ao tempo ate o primeiro resultado, nao a duracao total do stream.

---

## 4. Recovery Point Objective (RPO)

### 4.1 Tabela de RPO por Categoria de Dados

| Categoria | RPO | Mecanismo | Dependencia |
|-----------|-----|-----------|-------------|
| **Dados de Busca** (cache + historico) | 24h | Snapshot diario Supabase + reconstrucao via DataLake | Supabase daily backup |
| **Dados de Usuario** (auth, perfis, preferencias) | 1h | Point-in-Time Recovery (PITR) via Supabase | Plano Pro (PITR ativado) |
| **Dados de Faturamento** (assinaturas, cobrancas) | 1h | PITR + Stripe como source of truth complementar | Supabase PITR + Stripe API |
| **Dados de Ingestao** (pncp_raw_bids, supplier_contracts) | 24h | Reingestao a partir das fontes originais (PNCP, PCP, ComprasGov) | APIs externas disponiveis |
| **Cache Redis** | 0 | Dados efemeros reconstruiveis a partir de fontes primarias | N/A |
| **Codigo Fonte** | 0 | Git distribuido (GitHub + clones locais) | N/A |

### 4.2 Matriz de Risco

| Categoria | RPO Atual | RPO Desejavel | Custo para Melhoria | Prioridade |
|-----------|-----------|---------------|---------------------|------------|
| Dados de Busca | 24h | 1h | Upgrade PITR Supabase (ja incluso no plano Pro) | Alta |
| Dados de Usuario | 1h | 1h | Ja atingido | — |
| Dados de Faturamento | 1h | 5min | Stripe webhook replay + idempotency keys | Media |
| Dados de Ingestao | 24h | 1h | PITR para raw_bids + reingestao automatizada | Baixa |

> **Nota:** O RPO de 1h para dados de usuario e faturamento depende da ativacao do PITR no Supabase. O snapshot diario (padrao do plano Pro) oferece RPO de 24h. Vide `docs/architecture/backup-dr-strategy.md` para detalhes.

---

## 5. Recovery Time Objective (RTO)

### 5.1 Tabela de RTO por Servico

| Servico | RTO | Mecanismo de Recuperacao | Dependencia |
|---------|-----|--------------------------|-------------|
| **Backend API** (Railway web) | 2h | `railway redeploy` + restore de snapshot DB se necessario | Railway CLI + GitHub |
| **Frontend** (Next.js SSR) | 2h | `railway redeploy` + rebuild automatico | Railway CLI |
| **Worker** (ARQ jobs) | 2h | `railway redeploy` (worker separado) | Railway CLI |
| **Banco de Dados** (Supabase) | 4h | Restore de snapshot + reaplicacao de migrations | Supabase Dashboard/CLI |
| **Redis** (cache + queue) | 30min | Provisionamento automatico via Railway (Upstash Redis) | Railway add-on |
| **Full System** (todos os componentes) | 4h | Recuperacao coordenada de todos os componentes | Sequencial: DB -> Backend -> Worker -> Frontend |

### 5.2 Matriz de Melhoria

| Servico | RTO Atual | RTO Desejavel | Custo para Melhoria | Prioridade |
|---------|-----------|---------------|---------------------|------------|
| Backend API | 2h | 30min | Infra-as-code + auto-scaling Railway | Media |
| Frontend | 2h | 30min | Mesmo que backend | Media |
| Worker | 2h | 30min | Mesmo que backend | Media |
| Banco de Dados | 4h | 1h | PITR + replicacao cross-region | Alta |
| Redis | 30min | 5min | Redis cluster gerenciado | Baixa |

### 5.3 Procedimento de Recuperacao

Procedimento detalhado em `docs/runbooks/incident-response.md` e `docs/architecture/backup-dr-strategy.md`.

Sumario:

```
Incidente SEV1 detectado
  └── 0-5min: Triagem (verificar Railway / Supabase / health)
  └── 5-15min: Decisao de recovery (restore DB vs redeploy)
  └── 15-120min (RTO backend/frontend/worker):
      ├── Se DB intacto: railway redeploy --service bidiq-backend -y
      └── Se DB corrompido:
          ├── Restore snapshot Supabase (via Dashboard)
          ├── Reaplicar migrations pendentes
          └── railway redeploy --service bidiq-backend -y
  └── 120-240min (RTO full system):
      └── Verificacao de integridade + health checks
```

---

## 6. Exclusoes e Creditos

### 6.1 Exclusoes (nao contam como downtime)

1. **Manutencao Programada:** Janelas de ate 2h, notificadas com 48h de antecedencia.
2. **Problemas em Dependencias Externas:** Downtime de provedores terceiros (Supabase Cloud, Railway, Stripe, OpenAI, Resend) que afetem o SmartLic.
3. **Acoes do Cliente:** Erros causados por configuracao incorreta do cliente, uso alem dos limites do plano, ou acoes maliciosas.
4. **Forca Maior:** Eventos fora do controle razoavel da CONFENGE (desastres naturais, guerra, ataques DDoS, restricoes legais).
5. **Beta / Pre-Release:** Features marcadas como "beta" ou "preview" estao excluidas de SLA ate promocao para GA.
6. **Rate Limiting:** Respostas HTTP 429 por excesso de requisicoes nao contam como downtime.
7. **Degradacao de Funcionalidades Nao-Criticas:** Falhas em funcionalidades acessiveis (ex: exportacao Excel, Google Sheets) que nao afetam a busca e analise de editais.

### 6.2 Politica de Creditos

Para clientes pagantes (planos Pro, Consultoria), aplica-se a seguinte politica de creditos mensais:

| Disponibilidade no Mes | Credito | Aplicacao |
|-----------------------|---------|-----------|
| >= 99.9% | Nenhum | Operacao normal |
| 99.5% - 99.9% | 10% do valor mensal | Proximo ciclo de faturamento |
| 99.0% - 99.5% | 25% do valor mensal | Proximo ciclo de faturamento |
| < 99.0% | 50% do valor mensal | Proximo ciclo de faturamento |

**Requisitos para solicitacao de credito:**
1. Cliente deve abrir ticket de suporte em ate 7 dias corridos do final do mes de faturamento
2. CONFENGE verificara o downtime usando registros de probes externos (UptimeRobot/BetterStack)
3. Credito maximo limitado a 50% do valor mensal do plano
4. Credito nao e cumulativo entre meses
5. Clientes no trial gratuito nao fazem jus a creditos

### 6.3 Excecao para Planos Gratuitos / Trial

Usuarios em trial gratuito nao tem direito a creditos de SLA. A disponibilidade para estes usuarios e "melhor esforco" (best-effort), conforme os ToS.

---

## 7. Public Status Dashboard

### 7.1 Recomendacao: BetterStack Status Page (gratuito)

**Stack escolhida:** BetterStack (free tier) — alternativa moderna ao UptimeRobot com status page integrada.

| Recurso | BetterStack Free | UptimeRobot Free |
|---------|-----------------|-----------------|
| Monitors | 10 | 50 |
| Intervalo | 1 min | 5 min |
| Status page customizada | Sim (subdominio `smartlic.betterstack.com`) | Nao (URL compartilhada) |
| SSL monitoring | Sim | Sim |
| Incidentes + comunicados | Sim | Nao |
| API | Sim | Limitada |

### 7.2 Monitors Sugeridos

| Monitor | URL | Tipo | Justificativa |
|---------|-----|------|---------------|
| SmartLic App | `https://smartlic.tech/health/live` | HTTP | Liveness do app completo |
| SmartLic API | `https://api.smartlic.tech/v1/health` | HTTP | API endpoint |
| SmartLic Readiness | `https://smartlic.tech/health/ready` | HTTP | Readiness com dependencias |
| SSL Certificate | `https://smartlic.tech` | SSL | Expiracao de certificado |
| Frontend Login | `https://smartlic.tech/login` | HTTP | SSR disponivel |

### 7.3 URL da Status Page

```
https://smartlic.instatus.com/  (ou betterstack.com)
```

A status page deve exibir:
- **Uptime historico** (7d, 30d, 90d) para cada servico monitorado
- **Incidentes ativos** com descricao e ETA
- **Incidentes passados** com post-mortem resumido
- **Manutencoes programadas** futuras
- **Subscribe to updates** via email

### 7.4 Incident Lifecycle

```
Deteccao (probe fail ou alerta Sentry)
  → CRIADO: Incidente registrado em `incidents` table
  → INVESTIGANDO: Notificacao na status page + runbook consultado
  → IDENTIFICADO: Causa raiz determinada, ETA publicado
  → MONITORANDO: Fix aplicado, monitorando por N minutos
  → RESOLVIDO: Status page atualizado, post-mortem iniciado
```

---

## 8. Prometheus Alert Rules

As regras de alerta Prometheus para violacao de SLA estao definidas em `docs/operations/prometheus-sla-alerts.yml`.

### 8.1 Regras de Alerta por SLA

| Regra | Expressao | Severidade | Acao | Runbook |
|-------|-----------|------------|------|---------|
| **AppUptimeBelowSLA** | `smartlic_uptime_pct_30d < 99.5` | CRITICAL | Notificar admin + status page | `docs/runbooks/incident-response.md` |
| **APILatencyP95Busca** | `histogram_quantile(0.95, ...) > 5` | WARNING | Investigar pipeline / DataLake | `docs/runbooks/general-outage.md` |
| **APILatencyP99Busca** | `histogram_quantile(0.99, ...) > 20` | CRITICAL | Time budget waterfall analysis | `docs/runbooks/incident-response.md` |
| **PipelineLatencyP95** | `p95 pipeline > 500ms` | WARNING | Verificar queries Supabase | `docs/runbooks/general-outage.md` |
| **DashboardLatencyP95** | `p95 dashboard > 2s` | WARNING | Verificar analytics queries | `docs/runbooks/general-outage.md` |
| **ObservatorioLatencyP95** | `p95 observatorio > 500ms` | WARNING | Verificar queries SEO | `docs/runbooks/general-outage.md` |
| **ErrorRateAboveSLA** | `5xx rate > 1%` | CRITICAL | Investigar erros no Sentry | `docs/runbooks/incident-response.md` |
| **ErrorBudgetExhausted** | `error_budget_consumed > 90%` | WARNING | Iniciar procedimento de freeze | `docs/architecture/error-budget-slo.md` |

### 8.2 Configuracao de Alertas Sentry (complementar)

Os SLAs de latencia e erro sao monitorados via Sentry Metric Alerts como fallback:

| Alerta Sentry | Condicao | SLA Violado |
|---------------|----------|-------------|
| Search Latency Spike | p95 search > 5s por 5 min | Latencia /buscar |
| Pipeline Wedge | `smartlic_pipeline_budget_exceeded_total` > 2/5min | Uptime (indireto) |
| High 5xx Rate | `rate(http_responses_5xx) > 10/min` | Error Rate |
| Route Timeout | `smartlic_route_timeout_total` > 10/h | Latencia + Error Rate |

---

## 9. Revisao Trimestral

### 9.1 Calendario de Revisao

| Revisao | Data | Owner | Foco |
|---------|------|-------|------|
| Q3 2026 | 2026-09-17 | @devops | Validar targets vs historico real do trimestre |
| Q4 2026 | 2026-12-17 | @devops | Ajustar para pos-lancamento (se aplicavel) |
| Q1 2027 | 2027-03-17 | @devops | Revisao anual com stakeholders |

### 9.2 Template de Revisao

Cada revisao trimestral deve produzir um relatorio respondendo:

1. **Uptime:** O SLA de 99.5% (App) foi atingido? Se nao, quantos desvios e por que?
2. **Latencia:** Os p95/p99 por endpoint ficaram dentro do alvo? Quais endpoints precisam de revisao?
3. **RPO/RTO:** Ocorreu algum incidente que testou RPO ou RTO? Os alvos foram suficientes?
4. **Status Page:** A status page esta sendo utilizada pelos clientes? Metricas de visualizacao?
5. **Alertas:** As regras de alerta Prometheus dispararam? Houve falso-positivos?
6. **Error Budget:** O error budget mensal foi respeitado? Houve esgotamento?
7. **Melhorias:** Sugestoes de melhoria para o proximo trimestre.

### 9.3 Gatilhos para Revisao Extraordinaria

- Esgotamento do error budget (> 100% consumido)
- Incidente SEV1 com duracao > RTO
- Mudanca significativa na arquitetura (ex: migracao de provedor de infra)
- Adocao de novos clientes enterprise com requisitos contratuais especificos
- Mudanca no plano de hospedagem (ex: upgrade de plano Supabase)

---

## 10. Referencias

| Documento | Caminho | Relacao |
|-----------|---------|---------|
| Error Budget e SLOs | `docs/architecture/error-budget-slo.md` | SLOs internos que embasam os SLAs |
| Backup e Disaster Recovery | `docs/architecture/backup-dr-strategy.md` | RPO/RTO detalhados por componente |
| Monitoring & Alerting Setup | `docs/architecture/monitoring-setup.md` | Stack de observabilidade |
| Incident Response Runbook | `docs/runbooks/incident-response.md` | Procedimento de resposta a incidentes |
| General Outage Runbook | `docs/runbooks/general-outage.md` | Procedimento para outages gerais |
| Prometheus SLA Alerts | `docs/operations/prometheus-sla-alerts.yml` | Regras de alerta para violacao de SLA |
| Backend Metrics | `backend/metrics.py` | Definicao de todas as metricas Prometheus |
| SLO Dashboard API | `backend/routes/slo.py` | Endpoint admin de compliance de SLO |
| SLIs Definition | `backend/slo.py` | Implementacao dos SLIs |
| Architecture Patterns | `.claude/rules/architecture-patterns.md` | Pattern de 3 camadas de dados |
| ADR-5 (Error Budget) | `docs/architecture/adr-plan-capabilities.md` | Decisoes de design do error budget |

---

**Versao:** 1.0
**Criado:** 2026-06-17
**Owner:** @devops
**Proxima revisao trimestral:** 2026-09-17
**Issue:** #1958
