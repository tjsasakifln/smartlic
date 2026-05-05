-- ============================================================================
-- UP: cnpj_supplier_intel_rpc — RPCs de agregação para Raio-X do Concorrente
-- Date: 2026-05-05
-- Issue: #628
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Pipeline INTEL-REPORT-001 (R$197): DataLake → RPC → LLM → PDF → Stripe → email.
--   Esta migration entrega o passo 2 (RPC). Todas as agregações operam sobre
--   `pncp_supplier_contracts` (~2M+ rows; index `idx_psc_ni_fornecedor` existente).
--
--   Duas RPCs:
--     1. `count_cnpj_contracts(p_cnpj)` — pre-check rápido para gate de checkout
--        (bloquear compra se < 5 contratos, evitar refund por falta de dados).
--     2. `cnpj_supplier_intel(p_cnpj, p_window_months default 36)` — payload
--        completo (JSONB) consumido pelo backend para gerar PDF via ReportLab.
--
--   SECURITY DEFINER + `SET search_path = public, pg_temp` é mandatory por
--   memory `feedback_secdef_search_path_trap` (SEC-SECDEF-001/002 audit).
--   GRANT só a service_role — payload sensível (analytics agregadas) só é
--   liberado pós-pagamento confirmado pelo backend.
-- ============================================================================

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- RPC 1: count_cnpj_contracts(p_cnpj text) RETURNS INT
-- Pre-check usado no checkout. Lightweight: COUNT com index idx_psc_ni_fornecedor.
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.count_cnpj_contracts(p_cnpj TEXT)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_count INTEGER;
    v_clean TEXT;
BEGIN
    -- Normalize: digits only, defensive
    v_clean := regexp_replace(COALESCE(p_cnpj, ''), '[^0-9]', '', 'g');
    IF length(v_clean) <> 14 THEN
        RETURN 0;
    END IF;

    -- Cap statement timeout dentro da função (consistente com service_role
    -- statement_timeout=15s setado em outra migration; defesa em profundidade).
    SET LOCAL statement_timeout = '15s';

    SELECT COUNT(*)::INTEGER
      INTO v_count
      FROM public.pncp_supplier_contracts
     WHERE ni_fornecedor = v_clean
       AND is_active = TRUE;

    RETURN COALESCE(v_count, 0);
END;
$$;

COMMENT ON FUNCTION public.count_cnpj_contracts(TEXT) IS
    'INTEL-REPORT-001 — Pre-check de quantidade de contratos para CNPJ. Backend bloqueia checkout se < 5.';

REVOKE ALL ON FUNCTION public.count_cnpj_contracts(TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.count_cnpj_contracts(TEXT) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.count_cnpj_contracts(TEXT) TO service_role;

-- ────────────────────────────────────────────────────────────────────────────
-- RPC 2: cnpj_supplier_intel(p_cnpj text, p_window_months int DEFAULT 36)
-- Retorna JSONB com agregações completas. Janela padrão 36 meses.
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.cnpj_supplier_intel(
    p_cnpj           TEXT,
    p_window_months  INTEGER DEFAULT 36
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_clean         TEXT;
    v_window_start  DATE;
    v_result        JSONB;

    v_total_count       BIGINT;
    v_total_value       NUMERIC;
    v_avg_ticket        NUMERIC;
    v_data_primeiro     DATE;
    v_data_ultimo       DATE;

    v_top_orgaos        JSONB;
    v_top_objetos       JSONB;
    v_distribuicao_uf   JSONB;
    v_distribuicao_esfera JSONB;
    v_serie_temporal    JSONB;
    v_raw_contracts     JSONB;
BEGIN
    -- Defesa em profundidade: timeout local de 15s.
    -- Casa com service_role statement_timeout=15s + Railway 120s proxy.
    SET LOCAL statement_timeout = '15s';

    -- Validate inputs
    v_clean := regexp_replace(COALESCE(p_cnpj, ''), '[^0-9]', '', 'g');
    IF length(v_clean) <> 14 THEN
        RAISE EXCEPTION 'invalid cnpj: must be 14 digits after normalization';
    END IF;

    IF p_window_months IS NULL OR p_window_months < 1 OR p_window_months > 240 THEN
        RAISE EXCEPTION 'invalid window: p_window_months must be between 1 and 240';
    END IF;

    v_window_start := (CURRENT_DATE - (p_window_months || ' months')::INTERVAL)::DATE;

    -- ──────────────────────────────────────────────────────────────────────
    -- Headline metrics (single pass)
    -- ──────────────────────────────────────────────────────────────────────
    SELECT
        COUNT(*)::BIGINT,
        COALESCE(SUM(valor_global), 0)::NUMERIC,
        COALESCE(AVG(valor_global), 0)::NUMERIC,
        MIN(data_assinatura),
        MAX(data_assinatura)
      INTO
        v_total_count,
        v_total_value,
        v_avg_ticket,
        v_data_primeiro,
        v_data_ultimo
      FROM public.pncp_supplier_contracts
     WHERE ni_fornecedor = v_clean
       AND is_active = TRUE
       AND data_assinatura >= v_window_start;

    -- ──────────────────────────────────────────────────────────────────────
    -- Top 10 órgãos compradores (por valor, com count + valor_total)
    -- ──────────────────────────────────────────────────────────────────────
    SELECT COALESCE(
             jsonb_agg(entry ORDER BY (entry->>'valor_total')::NUMERIC DESC, (entry->>'count')::BIGINT DESC),
             '[]'::JSONB
           )
      INTO v_top_orgaos
      FROM (
        SELECT jsonb_build_object(
                   'orgao_cnpj',  orgao_cnpj,
                   'orgao_nome',  orgao_nome,
                   'count',       count,
                   'valor_total', valor_total
               ) AS entry
          FROM (
            SELECT orgao_cnpj,
                   MAX(orgao_nome)             AS orgao_nome,
                   COUNT(*)::BIGINT            AS count,
                   COALESCE(SUM(valor_global), 0)::NUMERIC AS valor_total
              FROM public.pncp_supplier_contracts
             WHERE ni_fornecedor = v_clean
               AND is_active = TRUE
               AND data_assinatura >= v_window_start
               AND orgao_cnpj IS NOT NULL
             GROUP BY orgao_cnpj
             ORDER BY valor_total DESC, count DESC
             LIMIT 10
          ) t
      ) sub;

    -- ──────────────────────────────────────────────────────────────────────
    -- Top 10 objetos (agrupados pelos primeiros 80 chars do objeto_contrato,
    -- por frequência)
    -- ──────────────────────────────────────────────────────────────────────
    SELECT COALESCE(
             jsonb_agg(entry ORDER BY (entry->>'count')::BIGINT DESC, (entry->>'valor_total')::NUMERIC DESC),
             '[]'::JSONB
           )
      INTO v_top_objetos
      FROM (
        SELECT jsonb_build_object(
                   'objeto_resumo', objeto_resumo,
                   'count',         count,
                   'valor_total',   valor_total
               ) AS entry
          FROM (
            SELECT LEFT(COALESCE(NULLIF(TRIM(objeto_contrato), ''), '(sem objeto)'), 80) AS objeto_resumo,
                   COUNT(*)::BIGINT                AS count,
                   COALESCE(SUM(valor_global), 0)::NUMERIC AS valor_total
              FROM public.pncp_supplier_contracts
             WHERE ni_fornecedor = v_clean
               AND is_active = TRUE
               AND data_assinatura >= v_window_start
             GROUP BY LEFT(COALESCE(NULLIF(TRIM(objeto_contrato), ''), '(sem objeto)'), 80)
             ORDER BY count DESC, valor_total DESC
             LIMIT 10
          ) t
      ) sub;

    -- ──────────────────────────────────────────────────────────────────────
    -- Distribuição por UF
    -- ──────────────────────────────────────────────────────────────────────
    SELECT COALESCE(jsonb_agg(entry ORDER BY (entry->>'valor_total')::NUMERIC DESC), '[]'::JSONB)
      INTO v_distribuicao_uf
      FROM (
        SELECT jsonb_build_object(
                   'uf',          COALESCE(uf, '??'),
                   'count',       COUNT(*)::BIGINT,
                   'valor_total', COALESCE(SUM(valor_global), 0)::NUMERIC
               ) AS entry
          FROM public.pncp_supplier_contracts
         WHERE ni_fornecedor = v_clean
           AND is_active = TRUE
           AND data_assinatura >= v_window_start
         GROUP BY COALESCE(uf, '??')
      ) t;

    -- ──────────────────────────────────────────────────────────────────────
    -- Distribuição por esfera (F/E/M/D)
    -- ──────────────────────────────────────────────────────────────────────
    SELECT COALESCE(jsonb_object_agg(esfera_label, payload), '{}'::JSONB)
      INTO v_distribuicao_esfera
      FROM (
        SELECT COALESCE(esfera, '?')               AS esfera_label,
               jsonb_build_object(
                   'count',       COUNT(*)::BIGINT,
                   'valor_total', COALESCE(SUM(valor_global), 0)::NUMERIC
               )                                    AS payload
          FROM public.pncp_supplier_contracts
         WHERE ni_fornecedor = v_clean
           AND is_active = TRUE
           AND data_assinatura >= v_window_start
         GROUP BY COALESCE(esfera, '?')
      ) t;

    -- ──────────────────────────────────────────────────────────────────────
    -- Série temporal (por mês, dentro da janela)
    -- ──────────────────────────────────────────────────────────────────────
    SELECT COALESCE(jsonb_agg(entry ORDER BY entry->>'mes'), '[]'::JSONB)
      INTO v_serie_temporal
      FROM (
        SELECT jsonb_build_object(
                   'mes',         to_char(date_trunc('month', data_assinatura), 'YYYY-MM'),
                   'count',       COUNT(*)::BIGINT,
                   'valor_total', COALESCE(SUM(valor_global), 0)::NUMERIC
               ) AS entry
          FROM public.pncp_supplier_contracts
         WHERE ni_fornecedor = v_clean
           AND is_active = TRUE
           AND data_assinatura >= v_window_start
           AND data_assinatura IS NOT NULL
         GROUP BY date_trunc('month', data_assinatura)
      ) t;

    -- ──────────────────────────────────────────────────────────────────────
    -- Últimos 50 contratos (raw para narrativa do PDF)
    -- ──────────────────────────────────────────────────────────────────────
    SELECT COALESCE(jsonb_agg(entry ORDER BY entry->>'data_assinatura' DESC NULLS LAST), '[]'::JSONB)
      INTO v_raw_contracts
      FROM (
        SELECT jsonb_build_object(
                   'numero_controle_pncp', numero_controle_pncp,
                   'orgao_nome',           orgao_nome,
                   'uf',                   uf,
                   'municipio',            municipio,
                   'valor_global',         valor_global,
                   'data_assinatura',      data_assinatura,
                   'objeto_contrato',      objeto_contrato
               ) AS entry
          FROM public.pncp_supplier_contracts
         WHERE ni_fornecedor = v_clean
           AND is_active = TRUE
           AND data_assinatura >= v_window_start
         ORDER BY data_assinatura DESC NULLS LAST
         LIMIT 50
      ) t;

    -- ──────────────────────────────────────────────────────────────────────
    -- Assemble final payload
    -- ──────────────────────────────────────────────────────────────────────
    v_result := jsonb_build_object(
        'cnpj',                   v_clean,
        'window_months',          p_window_months,
        'window_start',           v_window_start,
        'total_contracts',        v_total_count,
        'total_value',            v_total_value,
        'avg_ticket',             v_avg_ticket,
        'data_primeiro_contrato', v_data_primeiro,
        'data_ultimo_contrato',   v_data_ultimo,
        'top_orgaos',             v_top_orgaos,
        'top_objetos',            v_top_objetos,
        'distribuicao_uf',        v_distribuicao_uf,
        'distribuicao_esfera',    v_distribuicao_esfera,
        'serie_temporal',         v_serie_temporal,
        'raw_contracts',          v_raw_contracts,
        'generated_at',           NOW()
    );

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.cnpj_supplier_intel(TEXT, INTEGER) IS
    'INTEL-REPORT-001 — Agregações sobre pncp_supplier_contracts para gerar PDF Raio-X do Concorrente. SECURITY DEFINER, service_role only.';

REVOKE ALL ON FUNCTION public.cnpj_supplier_intel(TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.cnpj_supplier_intel(TEXT, INTEGER) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.cnpj_supplier_intel(TEXT, INTEGER) TO service_role;

COMMIT;
