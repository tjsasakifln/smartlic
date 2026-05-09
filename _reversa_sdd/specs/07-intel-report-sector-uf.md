# Spec: Intel Report — RPC `sector_uf_intel`

> Spec executável (SDD) para INTEL-REPORT-002 v0.2 — Panorama Setorial × UF.
> Confiança: 🟢 CONFIRMADO (código shipped via PR #826).
> Story: `INTEL-REPORT-002-V02-SPEC-001` · Reversa anchor: `review-report.md §10.1`.

## Component

- **ID**: `intel-report-sector-uf-rpc`
- **Tipo**: PostgreSQL function (RPC) — `SECURITY DEFINER`, `service_role` only.
- **Path**: `supabase/migrations/20260508120000_sector_uf_intel_rpc.sql` (migration UP) + `.down.sql` (rollback STORY-6.2).
- **Função**: `public.sector_uf_intel(p_sector TEXT, p_keywords TEXT[], p_uf TEXT, p_window_months INTEGER DEFAULT 24) RETURNS JSONB`.

## Purpose

Agrega `pncp_supplier_contracts` (~2M+ linhas, 400d) por **setor (via keywords no `objeto_contrato`) × UF × janela temporal**, retornando JSONB único pronto para alimentar `pdf_generator_sector_uf_report.py` (`generate_sector_uf_report`). Backbone do produto one-time **R$147,00** Stripe Checkout — pagamento → ARQ job → PDF → Storage signed URL → email Resend.

Como `pncp_supplier_contracts` **não possui coluna `setor`**, a filtragem é feita por `objeto_contrato ILIKE '%keyword%'` sobre o array `p_keywords` (mesma abordagem de `count_contracts_by_setor_uf` SEO-471 — ver migration linhas 13-15).

## Inputs

| Parâmetro | Tipo | Default | Validação |
|-----------|------|---------|-----------|
| `p_sector` | `TEXT` | (none) | Label do setor — incluído no payload final como `sector`. Não usado para filtro. |
| `p_keywords` | `TEXT[]` | (none) | **Obrigatório**, não-vazio. `RAISE EXCEPTION 'p_keywords must be a non-empty array'` se nulo/vazio. Resolvido em Python via `sectors.get_sector(sector_id).keywords` em `pdf_generator_sector_uf_report.py:670-671`. |
| `p_uf` | `TEXT` | (none) | Normalizado para 2 letras maiúsculas via `upper(regexp_replace(..., '[^A-Za-z]', '', 'g'))`. `RAISE EXCEPTION 'invalid uf: must be 2-letter state code after normalization'` se length ≠ 2. |
| `p_window_months` | `INTEGER` | `24` | Range `[1, 240]`. `RAISE EXCEPTION 'invalid window: p_window_months must be between 1 and 240'`. |

## Output Schema (JSONB)

Retorna single JSONB object — PostgREST embrulha em lista de 1 elemento (handle em `_fetch_rpc_data` linhas 617-623):

| Campo | Tipo | Origem |
|-------|------|--------|
| `sector` | `string` | `COALESCE(p_sector, '')` |
| `uf` | `string` | UF normalizada (2 letras upper) |
| `window_months` | `integer` | `p_window_months` echo |
| `window_start` | `date` | `CURRENT_DATE - (p_window_months \|\| ' months')::INTERVAL` |
| `total_contracts` | `bigint` | `COUNT(*)` em `pncp_supplier_contracts WHERE is_active=TRUE AND uf = v_uf_clean AND data_assinatura >= v_window_start AND EXISTS keyword match` |
| `total_value` | `numeric` | `COALESCE(SUM(valor_global), 0)` |
| `avg_ticket` | `numeric` | `COALESCE(AVG(valor_global), 0)` |
| `median_ticket` | `numeric` | `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY valor_global)` |
| `p90_ticket` | `numeric` | `PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY valor_global)` |
| `data_primeiro_contrato` | `date` | `MIN(data_assinatura)` |
| `data_ultimo_contrato` | `date` | `MAX(data_assinatura)` |
| `top_fornecedores` | `array[20]` | `[{ni_fornecedor, nome_fornecedor, count, valor_total, avg_ticket}]` ordenado por `valor_total DESC NULLS LAST`, agrupado por `ni_fornecedor`. |
| `distribuicao_esfera` | `array` | `[{esfera, count, valor_total}]` agrupado por `COALESCE(esfera, '?')`. **Nota** (linha 137-138): `pncp_supplier_contracts` não tem coluna `modalidade` — `esfera` (F/E/M/D) é proxy. |
| `serie_temporal` | `array` | `[{mes 'YYYY-MM', count, valor_total}]` zero-fill via `generate_series` mês a mês. |
| `top_orgaos` | `array[10]` | `[{orgao_cnpj, orgao_nome, count, valor_total}]` ordenado por valor. |
| `top_objetos` | `array[10]` | `[{objeto_resumo, count, valor_total}]` — `objeto_resumo = LEFT(COALESCE(NULLIF(TRIM(objeto_contrato), ''), '(sem objeto)'), 80)`. |
| `generated_at` | `timestamptz` | `NOW()` |

## SQL Definition Reference

Source-of-truth: [`supabase/migrations/20260508120000_sector_uf_intel_rpc.sql`](../../supabase/migrations/20260508120000_sector_uf_intel_rpc.sql) (linhas 33-274). Rollback: `.down.sql` paired (STORY-6.2 mandatory).

## Performance Characteristics

- **Statement timeout local**: `SET LOCAL statement_timeout = '15s'` (linha 64) — defesa em profundidade vs `statement_timeout` Supabase-wide (15s service_role floor — ver `reference_supabase_service_role_no_timeout_default`).
- **Single-pass headline metrics**: contagem + soma + avg + percentis + min/max em uma única SELECT (linhas 83-106). Demais agregações (top_fornecedores, top_orgaos etc.) são SELECTs separados — todas filtradas pelo mesmo predicate compound `(is_active, uf, data_assinatura, EXISTS keyword)`.
- **Zero-fill temporal**: `generate_series(date_trunc('month', window_start), date_trunc('month', CURRENT_DATE), '1 month')` LEFT JOIN agg — garante todos os meses no intervalo, mesmo sem contratos.
- **Índices relevantes em `pncp_supplier_contracts`**: `is_active`, `uf`, `data_assinatura`, `ni_fornecedor`, `orgao_cnpj`. Filtro `EXISTS (SELECT 1 FROM unnest(p_keywords) WHERE objeto_contrato ILIKE '%kw%')` é seq scan sobre subset filtrado por UF+window — aceitável p/ janela 24m default.
- **p95 latency target**: <15s (statement_timeout floor). Job ARQ tem `asyncio.wait_for(timeout=90)` em `jobs/queue/jobs.py:147` — folga 6× para PDF + upload + email.
- **Throughput esperado**: <1 chamada/min em produção (gated por Stripe webhook `checkout.session.completed`).

## Permission Boundary

```sql
REVOKE ALL ON FUNCTION public.sector_uf_intel(TEXT, TEXT[], TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.sector_uf_intel(TEXT, TEXT[], TEXT, INTEGER) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.sector_uf_intel(TEXT, TEXT[], TEXT, INTEGER) TO service_role;
```

- **`SECURITY DEFINER` + `SET search_path = public, pg_temp`** (linhas 41-42) — mandatory por SEC-SECDEF-001/002 (memory `feedback_secdef_search_path_trap`).
- **`service_role` only** — payload liberado apenas pós-pagamento, via backend ARQ worker (`backend/jobs/queue/jobs.py:_generate_sector_uf_report_pdf`).
- **Ownership check** acontece upstream em `routes/intel_reports.py` (`/v1/intel-reports/{purchase_id}/download` — RLS storage path `{user_id}/{purchase_id}.pdf`, ver `migration 20260507110000_create_intel_reports_bucket.sql`).

## Invariants

1. **No invention** — apenas campos retornados existem na tabela `pncp_supplier_contracts`. Modalidade ausente é declarada explicitamente (linha 137: "`pncp_supplier_contracts não possui coluna modalidade`").
2. **Idempotente** — mesmos inputs em `t1` e `t2` (com `t2 - t1 < 1d`) produzem deltas só nos contratos novos do dia (data crawl 3×/sem em `mon/wed/fri 06 UTC`).
3. **Sem mutação** — função read-only (`LANGUAGE plpgsql SECURITY DEFINER` mas sem `INSERT/UPDATE/DELETE`).
4. **UF normalization deterministic** — `upper(regexp_replace(p_uf, '[^A-Za-z]', '', 'g'))` strip de tudo non-alpha; `'sp'`, `'SP'`, `'S.P.'`, `'sP '` todos convergem para `'SP'`.

## Functional Requirements

- **FR-1**: `sector_uf_intel('limpeza', ARRAY['limpeza','higienizacao','conservacao'], 'SP', 24)` retorna JSONB com 16 campos top-level.
- **FR-2**: `top_fornecedores` ordenado por `valor_total DESC NULLS LAST`, máximo 20 entries.
- **FR-3**: `top_orgaos` ordenado por `valor_total DESC NULLS LAST`, máximo 10 entries.
- **FR-4**: `top_objetos` ordenado por `count DESC, valor_total DESC NULLS LAST`, máximo 10 entries.
- **FR-5**: `serie_temporal` cobre todos os meses entre `window_start` e mês corrente — zero-fill garantido.
- **FR-6**: Empty result (zero contratos no recorte) → todos os agregados retornam `0` ou `[]`, sem RAISE.

## Non-Functional Requirements

- **NFR-1**: Latência p95 <15s (statement_timeout local).
- **NFR-2**: Permission gate — somente `service_role` executa.
- **NFR-3**: `SET search_path = public, pg_temp` — anti-trap SEC-SECDEF.
- **NFR-4**: Validação eager dos 3 inputs antes de scan da tabela (fail-fast).

## Constraints

- **CON-1**: `p_keywords` é mandatory non-empty — sem keywords, EXISTS subquery degenera para sempre `FALSE`, causando contagem zero (proteção via RAISE).
- **CON-2**: `p_uf` precisa colapsar para 2 letras alpha — RAISE em UFs inválidas.
- **CON-3**: `p_window_months` `[1, 240]` — janela 240m = 20 anos, supera retention 400d mas não falha (apenas amplia `window_start`).
- **CON-4**: PostgREST embrulha JSONB scalar em lista — handler Python deve unwrap (`_fetch_rpc_data` linhas 617-623).

## Acceptance Criteria

- **AC-1**: RPC instalada em produção pós-`supabase db push` (CRIT-050 auto-apply em `deploy.yml`).
- **AC-2**: Chamada autenticada como `service_role` retorna `{sector, uf, total_contracts, ...}` em <15s.
- **AC-3**: Chamada como `anon`/`authenticated` retorna `permission denied for function sector_uf_intel`.
- **AC-4**: Inputs inválidos (UF length ≠ 2, keywords vazio, window fora `[1,240]`) → RAISE EXCEPTION com mensagem específica.
- **AC-5**: PostgREST schema cache reload (`NOTIFY pgrst, 'reload schema'`) após push — ver migration auto-apply em `deploy.yml`.

## Errors

| Mensagem | Trigger |
|----------|---------|
| `p_keywords must be a non-empty array` | `p_keywords IS NULL OR array_length(p_keywords, 1) IS NULL` |
| `invalid uf: must be 2-letter state code after normalization` | `length(v_uf_clean) <> 2` |
| `invalid window: p_window_months must be between 1 and 240` | `p_window_months NULL OR <1 OR >240` |
| `permission denied for function sector_uf_intel` | Caller is anon/authenticated (sem GRANT) |
| `canceling statement due to statement timeout` | Query >15s (statement_timeout local) |

## Code Traceability

- **Migration UP**: `supabase/migrations/20260508120000_sector_uf_intel_rpc.sql` (284 LOC)
- **Migration DOWN**: `supabase/migrations/20260508120000_sector_uf_intel_rpc.down.sql`
- **Caller Python**: `backend/pdf_generator_sector_uf_report.py:_fetch_rpc_data` (linhas 599-630)
- **ARQ orchestrator**: `backend/jobs/queue/jobs.py:_generate_sector_uf_report_pdf` (linhas 125-134)
- **Sub-spec PDF generator**: [`07b-intel-pdf-generator.md`](./07b-intel-pdf-generator.md)
- **Companion spec product surface**: [`13-intel-reports.spec.md`](./13-intel-reports.spec.md)
- **Tests indireto**: `backend/tests/test_sector_uf_intel_pdf.py` (34 testes — `TestGenerateSectorUfReport::test_rpc_called_with_correct_params` linha 337 valida assinatura).

## Dependencies

- `pncp_supplier_contracts` (ingestão por `backend/ingestion/contracts_crawler.py` 3×/semana mon/wed/fri).
- `backend/sectors_data.yaml` — keywords resolvidas em Python via `sectors.get_sector(sector_id).keywords` antes da chamada RPC.
- `service_role` Supabase JWT — backend `supabase_client.get_supabase()` com env `SUPABASE_SERVICE_ROLE_KEY`.
- `statement_timeout=15s` Supabase floor para service_role (memory `reference_supabase_service_role_no_timeout_default`).
