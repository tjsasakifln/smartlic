-- ============================================================================
-- PREDINT-001: RPC predict_contract_expiry
-- Wave 0 for Predictive Intelligence EPIC (#1260)
--
-- Purpose:
--   Analyzes pncp_supplier_contracts to identify contracts whose end date
--   is approaching (30/60/90 day windows), signaling republication
--   opportunities. Returns per-contract probability scores + aggregated
--   stats in a single scalar JSON document (bypasses PostgREST max_rows).
--
-- Parameters:
--   p_uf          VARCHAR(2)   — optional UF filter (case-insensitive)
--   p_setor       TEXT         — optional sector filter (setor_classificado)
--   p_janela_dias INTEGER      — prediction window in days (default 90)
--   p_limit       INTEGER      — max contracts returned (default 100)
--
-- Returns: json
--   {
--     "contracts": [{
--       "orgao_nome": "...",
--       "orgao_uf": "DF",
--       "objeto": "...",
--       "valor_total": 1500000.00,
--       "data_fim_vigencia": "2026-08-15",
--       "dias_ate_fim": 77,
--       "fornecedor_atual": "EMPRESA X LTDA",
--       "fornecedor_cnpj": "XX.XXX.XXX/0001-XX",
--       "categoria": "tecnologia",
--       "probabilidade_republicacao": 0.85,
--       "recorrencia_historica": 3
--     }],
--     "stats": {
--       "total_contratos_janela": 245,
--       "valor_total_sob_risco": 150000000.00,
--       "orgaos_afetados": 42
--     }
--   }
--
-- Probability logic:
--   f(recorrencia_historica, orgao_recorrencia_score, valor_base)
--   - recorrencia_historica: how many times same org had contracts in last 5y
--   - orgao_recorrencia_score: org recurrence relative to most active org
--   - valor_base: contracts with non-zero value get a baseline boost
--
-- Pattern: SCALAR JSON RETURN (bypasses PostgREST max_rows=1000)
-- Reference: supabase/migrations/20260509172143_data_cap_001_orgao_top_contracts_rpc.sql
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- Step 1: Add columns needed for expiry prediction (idempotent)
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE pncp_supplier_contracts
  ADD COLUMN IF NOT EXISTS data_fim_vigencia DATE,
  ADD COLUMN IF NOT EXISTS setor_classificado TEXT,
  ADD COLUMN IF NOT EXISTS data_publicacao DATE;

-- ────────────────────────────────────────────────────────────────────────────
-- Step 2: Auxiliary indexes for expiry queries
-- ────────────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_psc_data_fim_vigencia
  ON pncp_supplier_contracts(data_fim_vigencia)
  WHERE data_fim_vigencia IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_psc_expiry_uf_setor
  ON pncp_supplier_contracts(uf, data_fim_vigencia)
  WHERE data_fim_vigencia IS NOT NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- Step 3: RPC function
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.predict_contract_expiry(
    p_uf          TEXT DEFAULT NULL,
    p_setor       TEXT DEFAULT NULL,
    p_janela_dias INTEGER DEFAULT 90,
    p_limit       INTEGER DEFAULT 100
)
RETURNS json
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH
  -- Step 1: Find contracts with approaching end date
  expiry_window AS (
    SELECT
      c.orgao_nome,
      c.uf                                                AS orgao_uf,
      c.objeto_contrato                                   AS objeto,
      c.valor_global                                      AS valor_total,
      c.data_fim_vigencia,
      c.nome_fornecedor                                   AS fornecedor_atual,
      c.ni_fornecedor                                     AS fornecedor_cnpj,
      c.setor_classificado                                AS categoria,
      c.orgao_cnpj
    FROM pncp_supplier_contracts c
    WHERE c.is_active = TRUE
      AND c.data_fim_vigencia IS NOT NULL
      AND c.data_fim_vigencia >= CURRENT_DATE
      AND c.data_fim_vigencia <= (CURRENT_DATE + p_janela_dias)
      AND (p_uf IS NULL OR c.uf = upper(p_uf))
      AND (p_setor IS NULL OR c.setor_classificado = p_setor)
  ),
  -- Step 2: Compute recurrence metrics per contract
  contract_metrics AS (
    SELECT
      e.*,
      -- recorrencia_historica: count of contracts for same org/setor in 5 years
      COALESCE(
        (SELECT COUNT(*)::int
         FROM pncp_supplier_contracts h
         WHERE h.is_active = TRUE
           AND h.orgao_cnpj = e.orgao_cnpj
           AND (e.categoria IS NULL OR h.setor_classificado = e.categoria)
           AND h.data_assinatura >= (CURRENT_DATE - INTERVAL '5 years')::date
        ), 0
      ) AS recorrencia_historica,
      -- orgao_recorrencia_score: how active the org is (0..1 scale)
      -- computed as: org_contracts / max_org_contracts (relative index)
      COALESCE(
        (SELECT COUNT(*)::numeric
         FROM pncp_supplier_contracts h
         WHERE h.is_active = TRUE AND h.orgao_cnpj = e.orgao_cnpj
        ) / NULLIF(
          (SELECT MAX(cnt) FROM (
            SELECT COUNT(*) AS cnt
            FROM pncp_supplier_contracts
            WHERE is_active = TRUE
            GROUP BY orgao_cnpj
          ) tops),
        0), 0
      ) AS orgao_recorrencia_score,
      -- dias_ate_fim: days remaining until contract end
      (e.data_fim_vigencia - CURRENT_DATE) AS dias_ate_fim
    FROM expiry_window e
  ),
  -- Step 3: Compute probability score [0.05, 0.95] for each contract
  with_probability AS (
    SELECT
      m.*,
      GREATEST(0.05, LEAST(0.95,
        -- Factor 1: recorrencia_historica (up to 0.35)
        LEAST(m.recorrencia_historica::numeric / 30.0, 0.35) +
        -- Factor 2: orgao_recorrencia_score (up to 0.30)
        LEAST(m.orgao_recorrencia_score * 0.30, 0.30) +
        -- Factor 3: base value factor (0.15 for valued contracts, 0.05 otherwise)
        CASE
          WHEN m.valor_total IS NOT NULL AND m.valor_total > 0
               AND m.dias_ate_fim <= p_janela_dias / 2
          THEN 0.20
          WHEN m.valor_total IS NOT NULL AND m.valor_total > 0
          THEN 0.15
          ELSE 0.05
        END
      )) AS probabilidade_republicacao
    FROM contract_metrics m
  ),
  -- Step 4: Order by probability DESC, urgency (days left) ASC, limit results
  ranked AS (
    SELECT *
    FROM with_probability
    ORDER BY probabilidade_republicacao DESC, dias_ate_fim ASC, valor_total DESC NULLS LAST
    LIMIT p_limit
  )
  -- Step 5: Assemble final JSON payload
  SELECT json_build_object(
    'contracts', COALESCE(
      (SELECT json_agg(
        json_build_object(
          'orgao_nome',                    r.orgao_nome,
          'orgao_uf',                      r.orgao_uf,
          'objeto',                        r.objeto,
          'valor_total',                   r.valor_total,
          'data_fim_vigencia',             r.data_fim_vigencia::text,
          'dias_ate_fim',                  r.dias_ate_fim,
          'fornecedor_atual',              r.fornecedor_atual,
          'fornecedor_cnpj',               r.fornecedor_cnpj,
          'categoria',                     r.categoria,
          'probabilidade_republicacao',    ROUND(r.probabilidade_republicacao::numeric, 2)::float8,
          'recorrencia_historica',         r.recorrencia_historica
        )
        ORDER BY r.probabilidade_republicacao DESC, r.dias_ate_fim ASC
      ) FROM ranked r),
      '[]'::json
    ),
    'stats', (
      SELECT json_build_object(
        'total_contratos_janela',   COALESCE(COUNT(*)::int, 0),
        'valor_total_sob_risco',    COALESCE(SUM(valor_total)::numeric, 0),
        'orgaos_afetados',          COALESCE(COUNT(DISTINCT orgao_cnpj)::int, 0)
      ) FROM expiry_window
    )
  );
$$;

-- ────────────────────────────────────────────────────────────────────────────
-- Step 4: Grant permissions (public data — same as other contracts RPCs)
-- ────────────────────────────────────────────────────────────────────────────

GRANT EXECUTE ON FUNCTION public.predict_contract_expiry(TEXT, TEXT, INTEGER, INTEGER)
  TO anon, authenticated, service_role;

-- ────────────────────────────────────────────────────────────────────────────
-- Step 5: Documentation
-- ────────────────────────────────────────────────────────────────────────────

COMMENT ON FUNCTION public.predict_contract_expiry(TEXT, TEXT, INTEGER, INTEGER) IS
  'PREDINT-001: Predict contract republication probability based on approaching end dates. '
  'Returns JSON {contracts: [...], stats: {total_contratos_janela, valor_total_sob_risco, orgaos_afetados}}. '
  'Wave 0 for Predictive Intelligence EPIC (#1260).';
