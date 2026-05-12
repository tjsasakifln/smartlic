# Intel Reports — One-Time Report Purchase Module

> Gerado pelo **Reversa Writer** em 2026-05-12
> Source-of-truth: `backend/routes/intel_reports.py`, `backend/schemas/intel_report.py`, `backend/services/billing.py:create_intel_report_checkout`, `backend/jobs/queue/jobs.py`, `backend/pdf_generator_intel_report.py`, `backend/pdf_generator_sector_uf_report.py`, `backend/webhooks/handlers/_registry.py`, migrations `20260505*`

## Overview

Intel Reports permitem que usuários pagantes comprem relatórios one-time sobre fornecedores ou mercados. O fluxo é: Stripe Checkout → Webhook → ARQ Worker PDF → Storage → Email.

### Produtos

| Produto | Preço | Descrição | RPC Backend | PDF Generator |
|---------|-------|-----------|-------------|---------------|
| `cnpj` (INTEL-REPORT-001) | R$197 | Raio-X do Concorrente — análise de histórico de contratos de um CNPJ | `cnpj_supplier_intel(p_cnpj, p_window_months)` | `pdf_generator_intel_report.py` (8-12pp) |
| `sector_uf` (INTEL-REPORT-002) | R$147 | Relatório de Mercado Setor/UF — análise agregada de contratos por setor+UF | `sector_uf_intel(p_sector, p_keywords, p_uf, p_window_months)` | `pdf_generator_sector_uf_report.py` |

## Arquitetura do Fluxo

```
User → POST /intel-reports/checkout → Stripe Checkout Session (created)
  ├─ Redirect → Stripe hosted checkout page
  │
  └─ Stripe → checkout.session.completed (webhook)
       └─ Handler: intel_report_purchases.status = "generating"
            └─ ARQ Worker: _generate_intel_report_pdf()
                 ├─ cnpj: RPC → LLM narrative → ReportLab PDF → Upload Storage
                 └─ sector_uf: RPC → ReportLab PDF → Upload Storage
                      └─ Update intel_report_purchases.status = "ready", pdf_url signed URL
                           └─ Resend email with download link
```

## Endpoints

| Método | Rota | Request → Response | Propósito |
|--------|------|-------------------|-----------|
| POST | `/v1/intel-reports/checkout` | `IntelReportCheckoutRequest` → `IntelReportCheckoutResponse` | Criar sessão de checkout Stripe |
| GET | `/v1/intel-reports/` | → `list[IntelReportPurchase]` | Listar compras do usuário |
| GET | `/v1/intel-reports/{purchase_id}` | → `IntelReportStatusResponse` | Poll status da compra |
| GET | `/v1/intel-reports/{purchase_id}/download` | → `application/pdf` (StreamingResponse) | Baixar PDF |

### Schema da tabela `intel_report_purchases`

Vide `_reversa_sdd/data-master.md §11.3` para colunas completas. Destaques:

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | `uuid PK` | |
| `user_id` | `uuid FK → auth.users` | owner (CASCADE) |
| `product_type` | `text` | `cnpj` ou `sector_uf` |
| `entity_key` | `text` | CNPJ digits-only ou `setor:UF` |
| `stripe_payment_intent_id` | `text UNIQUE` | idempotency vs Stripe webhook |
| `status` | `text CHECK` | `pending → generating → ready \| failed \| refunded` |
| `pdf_url` | `text` | Signed URL Supabase Storage (30d expiry) |

**Indexes:** `idx_irp_user_id (user_id, created_at DESC)`, `idx_irp_stripe_pi (stripe_payment_intent_id)`, `idx_irp_status (status, created_at DESC)`

## RPCs PostgreSQL

| RPC | Retorna | Descrição |
|-----|---------|-----------|
| `cnpj_supplier_intel(p_cnpj, p_window_months=36)` | `jsonb` | Agrega contratos do CNPJ do DataLake — top fornecedores, série temporal, modalidades, top órgãos, data primeiro/último contrato |
| `count_cnpj_contracts(p_cnpj)` | `int` | Pre-check: COUNT rápido via index — bloqueia compra se <5 contratos (evita refund) |
| `sector_uf_intel(p_sector, p_keywords[], p_uf, p_window_months=24)` | `jsonb` | Agrega contratos por setor+UF: total, avg/median/P90 ticket, top fornecedores, distribuição modalidade, série temporal |

**Security:** Todas SECURITY DEFINER + `SET search_path = public, pg_temp` + `SET LOCAL statement_timeout = '15s'`. GRANT `service_role` only.

## Stripe Checkout

`POST /v1/intel-reports/checkout` em `backend/services/billing.py`:

1. Valida `product_type` e `entity_key` (CNPJ digits-only para `cnpj`, formato `setor:UF` para `sector_uf`)
2. Pre-check: `count_cnpj_contracts(p_cnpj)` ≥ 5 (apenas `cnpj` type)
3. Cria sessão Stripe com `mode=payment`, `line_items` com `price_data` inline (sem Price ID pre-criado)
4. Insere registro em `intel_report_purchases` com `status='pending'`, `stripe_session_id` vinculado
5. Retorna `{checkout_url, session_id}`

## Webhook Processing

`checkout.session.completed` (em `webhooks/handlers/checkout.py`):

1. Verifica se `metadata.product_type` está presente (marcador Intel Report)
2. Atualiza `intel_report_purchases.status = 'generating'`, salva `stripe_payment_intent_id`
3. Dispara ARQ job `generate_intel_report_pdf` (queue `intel_report_job`)

## ARQ Worker (`backend/jobs/queue/jobs.py`)

`_generate_intel_report_pdf(purchase_id, user_id, product_type, entity_key)`:

1. **Produto `cnpj`:** chama RPC `cnpj_supplier_intel` → `generate_cnpj_report(data)` → ReportLab 8-12pp PDF
2. **Produto `sector_uf`:** chama RPC `sector_uf_intel` → `generate_sector_uf_report(db, entity_key)` → ReportLab PDF
3. Upload para Supabase Storage bucket `intel-reports` (signed URL 30d)
4. Atualiza `intel_report_purchases.status = 'ready'`, salva `pdf_url`
5. Envia email de confirmação com link download

### Falha e Refund

- Falha no worker: `status = 'failed'`. Usuário vê no frontend, pode contactar suporte.
- Refund (manual via Stripe Dashboard): `status = 'refunded'`. Relatório fica acessível até signed URL expirar (30d), mas sem re-gerar.

## PDF Generators

### `cnpj` — `pdf_generator_intel_report.py`

- 8-12 páginas A4, ReportLab
- Conteúdo: header empresa, sumário executivo, top contratos (tabela), distribuição por modalidade, série temporal (gráfico textual), top órgãos contratantes, análise de viabilidade
- Cores brand: dark blue `#1B3A5C`, medium blue `#2C5F8A`, light blue `#E8F0FE`

### `sector_uf` — `pdf_generator_sector_uf_report.py`

- Relatório de mercado agregado por setor+UF
- Conteúdo: total de contratos, valor médio/P50/P90, top fornecedores, distribuição modalidade, top órgãos, série temporal

## Storage

Bucket `intel-reports` (privado, Supabase Storage). Signed URLs geradas pelo worker, 30d expiry. Rota `/download` faz proxy: `GET signed_url` → `StreamingResponse`.

## Dependências

| Módulo | Relação |
|--------|---------|
| `services/billing.py` | Stripe checkout session creation |
| `webhooks/handlers/checkout.py` | Stripe webhook fulfillment |
| `jobs/queue/jobs.py` | ARQ background PDF generation |
| `pdf_generator_intel_report.py` | CNPJ PDF layout |
| `pdf_generator_sector_uf_report.py` | Sector/UF PDF layout |
| `schemas/intel_report.py` | Pydantic request/response schemas |
| `routes/intel_reports.py` | FastAPI router (4 endpoints) |
| Supabase Storage `intel-reports` bucket | PDF hosting |

## Métricas Prometheus

- `smartlic_intel_report_checkout_total{product_type}` (counter)
- `smartlic_intel_report_worker_duration_seconds{product_type}` (histogram)
- `smartlic_intel_report_storage_upload_bytes` (histogram)

## Lacunas

- 🔴 Refund flow é manual (admin via Stripe Dashboard) — story `INTEL-FAIL-REFUND-001` no backlog
- 🔴 `sector_uf` PDF generator foi implementado como stub em `_generate_sector_uf_report_pdf` com `try/except NotImplementedError` — gerador real pode não estar completo
- 🟡 LLM narrative usado apenas no produto `cnpj` (via `gerar_resumo` em `llm.py`); `sector_uf` não tem narrativa LLM
- 🟢 Pre-check `count_cnpj_contracts ≥ 5` protege contra compras sem dados disponíveis

---

*Atualizado em 2026-05-12 (DOC-COVERAGE-002)*
