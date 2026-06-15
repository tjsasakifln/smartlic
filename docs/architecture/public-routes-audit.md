# Auditoria de Rotas Publicas do Backend SmartLic

**Data:** 2026-06-15
**Propósito:** Catalogar e classificar todas as rotas publicas (sem autenticacao JWT) do backend FastAPI, por categoria, com metrica de rate limit e finalidade.
**Total de arquivos de rota:** 114 (65 registrados no startup/routes.py)
**Total estimado de endpoints publicos:** ~130+ (de ~303 endpoints totais)
**~8300 LOC** nas rotas SEO programmaticas publicas.

---

## Sumario Executivo

| Categoria | Qtd Rotas | Exige Auth | Rate Limit | Criticidade |
|-----------|-----------|------------|------------|-------------|
| **Health / Probes** | 11 | Nao | Nao | Alta - vital para Railway |
| **Auth (signup, login, MFA)** | 10 | Nao (parcial) | 5/5min, 3/10min | Alta - superficie de ataque |
| **Stripe Webhook** | 1 | Nao (signature HMAC) | Nao | Critica - billing |
| **SEO Programmatic** | ~60-70 | Nao | 60/min IP (maioria) | Alta - inbound organico |
| **Observatorio** | 2 | Nao | 60/min IP | Media |
| **Blog / Stats** | 9 | Nao | 60/min IP | Media |
| **Sitemap** | 5-7 | Nao | 60/min IP | Media - indexacao |
| **Lead Capture** | 2 | Nao | 60/min IP | Baixa |
| **Comparador / Calculadora** | 3 | Nao | 60/min IP | Baixa |
| **Email Tracking** | 4 | Nao (token HMAC) | Nao | Baixa - necessario |
| **Compartilhamento** | 1 | Nao (hash-only) | Nao | Baixa |
| **Trial Emails (webhook)** | 1 | Nao (HMAC verify) | Nao | Media |
| **Public Feature Flags** | 1 | Opcional (auth melhora) | 60/min IP | Baixa |
| **Intel / Vitrine Publica** | ~15 | Nao (maioria) | 60/min IP | Media |
| **Admin (public-readable)** | 1 | Nao | Nao | Alta - requer atencao |

---

## 1. Health / Probes (Container Probes)

Arquivo: `backend/routes/health_core.py` (4 endpoints)
Arquivo: `backend/routes/health.py` (9 endpoints, alguns com auth opcional)

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/health/live` | GET | Liveness probe do Railway (retorna 200 se o processo esta vivo) | Nao |
| `/health/ready` | GET | Readiness probe (Redis + Supabase + Cache) | Nao |
| `/health` | GET | Health check completo com status de fontes | Nao |
| `/sources/health` | GET | Status individual de cada fonte de dados (PNCP, PCP, ComprasGov) | Nao |
| `/api/status/incidents` | GET | Incidentes recentes de downtime | Nao |
| `/api/status/uptime-history` | GET | Historico de uptime | Nao |
| `/api/status/cache-health` | GET | Status de saude do cache (hit rate, TTL) | Nao |
| `/v1/status/*` (variantes) | GET | Diversos endpoints de status | Nao |

**Nota:** Alguns endpoints em `health.py` usam `require_auth_optional` - sao publicos mas enriquecem resposta para usuarios autenticados.

---

## 2. Autenticacao (Publica por Design)

Arquivos: `auth_check.py`, `auth_email.py`, `auth_signup.py`, `auth_oauth.py`, `mfa.py`

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/auth/check-email` | POST | Verificar se email ja esta cadastrado | 5/5min |
| `/v1/auth/check` | GET | Verificar status de autenticacao do token | Nao |
| `/v1/auth/signup` | POST | Criar nova conta | 3/10min |
| `/v1/auth/signup/resend-confirmation` | POST | Reenviar email de confirmacao | 3/10min |
| `/v1/auth/validate-signup-email` | POST | Validar email no signup | 3/10min |
| `/v1/auth/login` | POST | Login com email e senha | 5/5min |
| `/v1/auth/forgot-password` | POST | Recuperacao de senha | 5/5min |
| `/v1/auth/reset-password` | POST | Redefinir senha com token | 5/5min |
| `/api/auth/google` | GET/POST | Login com Google OAuth | 5/5min |
| `/api/auth/google/callback` | GET | Callback do Google OAuth | Nao |
| `/v1/auth/status` | GET | Status MFA do usuario | Nao |
| `/v1/mfa/send-recovery-codes` | POST | Enviar codigos de recuperacao MFA | 3/10min |

---

## 3. Webhooks (Assinatura HMAC / Stripe Signature)

| Path | Metodo | Proposito | Autenticacao | Rate Limit |
|------|--------|-----------|-------------|------------|
| `/webhooks/stripe` | POST | 12 eventos de billing Stripe (checkout, subscription, invoice, founding) | Stripe-Signature HMAC | Nao |
| `/v1/trial-emails/webhook` | POST | Webhook interno para disparo de trial emails | HMAC verify | Nao |

---

## 4. SEO Programmatic (Rotas Publicas de Conteudo)

Arquivos: ~30 arquivos em `backend/routes/*_publicos.py`, `observatorio.py`, `blog_stats.py`, sitemaps, `sectors_public.py`, `stats_public.py`, e rotas de inteligencia publica.

### 4.1 Observatorio

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/observatorio/stats` | GET | Estatisticas do observatorio de licitacoes | 60/min IP |
| `/v1/observatorio/raio-x/{id}` | GET | Raio-X detalhado de entidade (setor, municipio, orgao) | 60/min IP |

### 4.2 Blog / Stats

Arquivo: `blog_stats.py` (1466 LOC - maior arquivo de rota publica)

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/blog/stats/contratos/{setor}` | GET | Stats de contratos por setor | 60/min IP |
| `/v1/blog/stats/contratos/{setor}/{uf}` | GET | Stats de contratos por setor + UF | 60/min IP |
| `/v1/blog/stats/licitacoes/{setor}` | GET | Stats de licitacoes por setor | 60/min IP |
| `/v1/blog/stats/licitacoes/{setor}/{uf}` | GET | Stats de licitacoes por setor + UF | 60/min IP |
| `/v1/blog/stats/panorama/{setor}` | GET | Panorama setorial | 60/min IP |
| `/v1/blog/stats/panorama/{setor}/{uf}` | GET | Panorama setorial + UF | 60/min IP |
| `/v1/blog/stats/programmatic/{setor}` | GET | Conteudo programatico SEO | 60/min IP |
| `/v1/blog/stats/programmatic/{setor}/{uf}` | GET | Conteudo programatico SEO + UF | 60/min IP |
| `/v1/blog/stats/cidade/{cidade}` | GET | Stats por cidade | 60/min IP |

### 4.3 Empresa / Fornecedores

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/empresa/{cnpj}` | GET | Dados publicos de empresa/fornecedor | 60/min IP |
| `/v1/empresa/autocomplete` | GET | Autocomplete de empresas | 60/min IP |

### 4.4 Orgaos Publicos

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/orgao/{slug}` | GET | Dados publicos de orgao governamental | 60/min IP |

### 4.5 Contratos Publicos

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/contratos/{setor}` | GET | Contratos por setor (listagem SEO) | 60/min IP |
| `/v1/contratos/{setor}/{uf}` | GET | Contratos por setor + UF | 60/min IP |
| `/v1/contratos/orgao/{cnpj}` | GET | Contratos de orgao especifico | 60/min IP |
| `/v1/contratos/fornecedor/{cnpj}` | GET | Contratos de fornecedor especifico | 60/min IP |

### 4.6 Dados Publicos

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/dados-publicos/search` | GET | Busca publica de dados de licitacao | 60/min IP |

### 4.7 Municipios

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/municipios/{slug}` | GET | Dados publicos municipais | 60/min IP |
| `/v1/municipios/autocomplete` | GET | Autocomplete de municipios | 60/min IP |

### 4.8 Itens Publicos

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/itens/{setor}` | GET | Itens de licitacao por setor | 60/min IP |
| `/v1/itens/{setor}/{uf}` | GET | Itens por setor + UF | 60/min IP |

### 4.9 Compliance

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/compliance/{cnpj}` | GET | Dados de compliance de empresa | 60/min IP |

### 4.10 Indice Municipal

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/indice-municipal/{municipio_uf}` | GET | Scoring municipal (IBGE + indicadores) | 60/min IP |
| `/v1/indice-municipal/dimensoes` | GET | Dimensoes do indice municipal | 60/min IP |
| `/v1/indice-municipal/top` | GET | Top municipios por indice | 60/min IP |

### 4.11 Alertas Publicos

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/alertas/{setor}/{uf}` | GET | Pre-visualizacao publica de alertas de editais | 60/min IP |

### 4.12 Setores

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/setores` | GET | Lista de setores disponiveis | 60/min IP |
| `/v1/setores/{setor_id}` | GET | Detalhe de setor especifico | 60/min IP |
| `/v1/setores/stats` | GET | Estatisticas agregadas por setor | 60/min IP |

### 4.13 Stats Publicos

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/stats/public` | GET | Estatisticas publicas da plataforma | 60/min IP |

---

## 5. Sitemaps (Indexacao SEO)

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/sitemap-cnpjs.xml` | GET | Sitemap de CNPJs/fornecedores (~2M+ rows) | 60/min IP |
| `/sitemap-cnpjs/{page}.xml` | GET | Paginacao do sitemap de CNPJs | 60/min IP |
| `/sitemap-orgaos.xml` | GET | Sitemap de orgaos publicos | 60/min IP |
| `/sitemap-orgaos/{page}.xml` | GET | Paginacao do sitemap de orgaos | 60/min IP |
| `/sitemap-licitacoes.xml` | GET | Sitemap de licitacoes | 60/min IP |
| `/sitemap-licitacoes/{page}.xml` | GET | Paginacao do sitemap de licitacoes | 60/min IP |
| `/sitemap-licitacoes-do-dia.xml` | GET | Sitemap diario de licitacoes | 60/min IP |

---

## 6. Ferramentas Publicas

### 6.1 Calculadora

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/calculadora/tce` | GET | Calculadora TCE (estimativa de custos) | 60/min IP |

### 6.2 Comparador

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/comparador/buscar` | GET | Busca comparativa de licitacoes | 60/min IP |
| `/v1/comparador/bids` | GET | Comparacao de lances | 60/min IP |

---

## 7. Lead Capture / Landing Page

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/lead-capture` | POST | Captura de lead da landing page | 60/min IP |
| `/v1/lead-magnet/lp-sei` | POST | Lead magnet especifico (LP SEI) | 60/min IP |

---

## 8. Email Tracking (DIGEST-005)

Arquivo: `email_tracking.py`

| Path | Metodo | Proposito | Autenticacao |
|------|--------|-----------|-------------|
| `/api/email/open/{tracking_id}` | GET | Pixel de rastreio de abertura de email | Token HMAC no tracking_id |
| `/api/email/click/{tracking_id}` | GET | Redirecionamento de clique em email | Token HMAC no tracking_id |
| `/api/email/unsubscribe` | POST | Descadastro de emails marketing | Token HMAC |
| `/api/email/unsubscribe-page` | GET | Pagina de confirmacao de unsubscribe | Token HMAC |

---

## 9. Compartilhamento

| Path | Metodo | Proposito | Autenticacao |
|------|--------|-----------|-------------|
| `/v1/share/analise/{hash}` | GET | Visualizar analise compartilhada | Nao (hash-only) |

---

## 10. Intel / Vitrine Publica

Arquivos: `competitive_intel.py`, `intel_vitrine.py`, `widget_compint.py`, `subcontract_intel.py`, `network_intel.py`, `intel_tasting.py`, `pseo_data.py`, `pseo_intel_feed.py`

| Path | Metodo | Proposito | Rate Limit |
|------|--------|-----------|------------|
| `/v1/competitive-intel` | GET | Inteligencia competitiva publica | 60/min IP |
| `/v1/competitive-intel/{setor}` | GET | Intel competitiva por setor | 60/min IP |
| `/v1/intel-vitrine` | GET | Vitrine de inteligencia publica | 60/min IP |
| `/v1/intel-vitrine/{id}` | GET | Detalhe de item da vitrine | 60/min IP |
| `/v1/widget-compint` | GET | Widget de intel competitiva | 60/min IP |
| `/v1/widget-compint/{id}` | GET | Detalhe do widget | 60/min IP |
| `/v1/subcontract-intel` | GET | Intel de subcontratacao | 60/min IP |
| `/v1/network-intel` | GET | Intel de rede de fornecedores | 60/min IP |
| `/v1/intel-tasting` | GET | Amostra de inteligencia (tasting) | 60/min IP |
| `/v1/pseo-data` | GET | Dados programaticos SEO | 60/min IP |
| `/v1/pseo-data/{id}` | GET | Detalhe de dado programatico | 60/min IP |
| `/v1/pseo/feed` | GET | Feed de dados PSEO | 60/min IP |
| `/v1/score` | GET | Scoring publico de empresas | 60/min IP |
| `/v1/score/{cnpj}` | GET | Score de empresa especifica | 60/min IP |
| `/v1/products` | GET | Listagem publica de produtos | 60/min IP |

---

## 11. Feature Flags Publicas

| Path | Metodo | Proposito | Rate Limit | Nota |
|------|--------|-----------|------------|------|
| `/v1/feature-flags` | GET | Feature flags publicas (experimentos ativos) | 60/min IP | Autenticacao opcional (se auth, enriquece resposta) |
| `/v1/experiments` | GET | Experimentos A/B ativos | 60/min IP | Requer auth |

---

## 12. Outras Rotas Publicas Relevantes

| Path | Metodo | Proposito | Autenticacao | Rate Limit |
|------|--------|-----------|-------------|------------|
| `/v1/plans` | GET | Listagem de planos e precos | Nao | Nao |
| `/v1/api/search` | GET | Busca via API Key (auth alternativa) | API Key header | 60/min |
| `/v1/survey` | POST | Pesquisa de satisfacao (publica link) | Nao (parcial) | Nao |
| `/v1/daily-digest` | GET | Digest diario publico | Nao | 60/min IP |
| `/v1/weekly-digest` | GET | Digest semanal publico | Nao | 60/min IP |
| `/v1/relatorio-2026-t1` | GET | Relatorio periodico publico | Nao | 60/min IP |
| `/v1/seasonal-calendar/predict` | GET | Calendario sazonal de licitacoes | Nao | 60/min IP |
| `/v1/seo-coverage-manifest` | GET | Manifesto de cobertura SEO | Nao | 60/min IP |
| `/v1/founders` | GET | Disponibilidade dos founders (landing page) | Nao | Nao |
| `/v1/founders/hall` | GET | Hall dos founders (listagem publica) | Nao | Nao |
| `/v1/checkout/session/{session_id}` | GET | Status de sessao de checkout | Nao (session_id) | Nao |
| `/v1/metrics` | GET | Metricas publicas (Prometheus) | Nao | Nao |
| `/v1/notifications` | GET | Notificacoes publicas | Nao | Nao |

---

## 13. Categorias de Rate Limit

| Tipo | Limite | Janela | Metodo | Implementacao |
|------|--------|--------|--------|---------------|
| Auth (signup) | 3 | 10 minutos | Redis token bucket | `AUTH_RATE_LIMIT_PER_10MIN` |
| Auth (login) | 5 | 5 minutos | Redis token bucket | `AUTH_RATE_LIMIT_PER_5MIN` |
| SEO / Publico (IP) | 60 | 1 minuto | In-memory (public_rate_limit.py) | `rate_limit_public(limit_unauth=60)` |
| SEO / Autenticado | 600 | 1 minuto | In-memory | `rate_limit_public(limit_auth=600)` |
| Busca | 10 | 1 minuto | Redis token bucket | `SEARCH_RATE_LIMIT_PER_MINUTE` |
| Bot (crawler) | 10 | 1 minuto | User-agent detect | `BOT_RATE_LIMIT_PER_MINUTE` |
| Humano | 60 | 1 minuto | IP + cookie | `HUMAN_RATE_LIMIT_PER_MINUTE` |
| SSE reconexao | 10 | 60 segundos | Redis | `SSE_RECONNECT_RATE_LIMIT` |

---

## 14. Resumo por Arquivo (Public Routes Only)

| Arquivo | LOC | Endpoints Publicos | Categoria |
|---------|-----|-------------------|-----------|
| `blog_stats.py` | 1466 | 9 | Blog / SEO |
| `contratos_publicos.py` | 973 | 4 | SEO Contratos |
| `competitive_intel.py` | 759 | 7 | Intel Publica |
| `observatorio.py` | 706 | 2 | Observatorio |
| `empresa_publica.py` | 689 | 1 | SEO Empresa |
| `municipios_publicos.py` | 644 | 2 | SEO Municipios |
| `itens_publicos.py` | 566 | 2 | SEO Itens |
| `orgao_publico.py` | 519 | 1 | SEO Orgaos |
| `intel_vitrine.py` | 453 | 2 | Intel Publica |
| `stats_public.py` | 453 | 1 | Stats Publicos |
| `widget_compint.py` | 447 | 2 | Intel Publica |
| `sitemap_cnpjs.py` | 406 | 2 | Sitemap |
| `pseo_data.py` | 396 | 2 | PSEO |
| `sectors_public.py` | 367 | 3 | Setores |
| `sitemap_orgaos.py` | 360 | 2 | Sitemap |
| `sitemap_licitacoes.py` | 335 | 2 | Sitemap |
| `daily_digest.py` | 311 | 2 | Digest |
| `compliance_publicos.py` | 311 | 1 | SEO Compliance |
| `pseo_intel_feed.py` | 298 | 1 | PSEO Feed |
| `indice_municipal.py` | 290 | 3 | Indice Municipal |
| `weekly_digest.py` | 282 | 2 | Digest |
| `intel_tasting.py` | 282 | 1 | Intel Tasting |
| `dados_publicos.py` | 282 | 1 | Dados Publicos |
| `subcontract_intel.py` | 271 | 1 | Intel Subcontratacao |
| `sitemap_licitacoes_do_dia.py` | 208 | 1 | Sitemap |
| `comparador.py` | 189 | 2 | Ferramentas |
| `seo_coverage_manifest.py` | 172 | 1 | SEO |
| `lead_magnet.py` | 162 | 1 | Lead Capture |
| `alertas_publicos.py` | 149 | 1 | SEO Alertas |
| `lead_capture.py` | 280 | 1 | Lead Capture |
| `calculadora.py` | 145 | 1 | Ferramentas |
| `network_intel.py` | 34 | 1 | Intel Publica |
| `health.py` | 371 | 9 | Health |
| `health_core.py` | 432 | 4 | Health |
| `email_tracking.py` | 318 | 4 | Email Tracking |
| `auth_*.py` (4 files) | ~1321 | 10 | Auth |
| `plans.py` | 139 | 1 | Plans |
| `products.py` | 148 | 1 | Products |
| `founding.py` | 658 | 4 | Founding |
| `relatorio.py` | 148 | 1 | Relatorios |
| `seasonal_calendar.py` | 123 | 1 | Calendario |
| `metrics_api.py` | 139 | 3 | Metrics |
| `notifications.py` | 74 | 2 | Notificacoes |
| `network_events.py` | 218 | 2 | Eventos |
| **Total** | **~16300** | **~130+** | |

---

## 15. Observacoes e Riscos

1. **Endpoints health sem rate limit** - Essencial para Railway probes, mas podem ser usados para fingerprinting.
2. **Auth endpoints com rate limit baixo** - 3/10min para signup, 5/5min para login - mitigam brute force.
3. **SEO endpoints com rate limit de 60/min/IP** - Suficiente para Googlebot, mas protege contra scraping abusivo. O rate limit diferencia bot vs human via user-agent.
4. **Stripe webhook sem rate limit** - Aceitavel pois a autenticacao eh via Stripe-Signature HMAC, que eh imutavel e nao forcavel.
5. **Rotas de intel publica** - Conteudo agregado e anonimizado, sem PII ou dados de usuarios individuais.
6. **Sitemaps com paginacao** - Sitemaps de CNPJs (2M+ registros) sao paginados para evitar timeout e sobrecarga.
7. **Falta de rate limit em alguns endpoints** - `/v1/plans`, `/v1/founders`, `/v1/checkout/session/{session_id}` - risco baixo por serem endpoints leves e sem efeito colateral.
