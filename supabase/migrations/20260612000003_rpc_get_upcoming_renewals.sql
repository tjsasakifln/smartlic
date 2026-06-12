-- ============================================================================
-- PREDINT-020: RPC get_upcoming_renewals
--
-- Purpose:
--   Identifies contracts approaching their end date within a configurable
--   window. Returns contracts sorted by renewal urgency, with historical
--   recurrence patterns to estimate republication probability.
--
-- Parameters:
--   p_setor          TEXT   -- optional sector filter
--   p_uf             TEXT   -- optional UF filter
--   p_janela_dias    INT    -- lookahead window in days (default 90)
--   p_limit          INT    -- max contracts (default 50)
--
-- Returns: json
--   {
--     "total": 45,
--     "contratos": [{
--       "id": "uuid",
--       "orgao_nome": "Prefeitura de SP",
--       "uf": "SP",
--       "objeto": "Manutencao predial",
--       "valor_total": 500000.00,
--       "data_fim_vigencia": "2026-09-15",
--       "dias_ate_fim": 95,
--       "fornecedor_atual": "Empresa Ltda",
--       "fornecedor_cnpj": "XX.XXX.XXX/0001-XX",
--       "probabilidade_republicacao": 0.75
--     }, ...]
--   }
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_upcoming_renewals(
    p_setor TEXT DEFAULT NULL,
    p_uf TEXT DEFAULT NULL,
    p_janela_dias INT DEFAULT 90,
    p_limit INT DEFAULT 50
) RETURNS JSON
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = 'public'
AS $$
DECLARE
    v_result JSON;
BEGIN
    WITH upcoming AS (
        SELECT
            id,
            orgao_nome,
            codigo_uf AS uf,
            objeto_contrato AS objeto,
            valor_global AS valor_total,
            data_fim_vigencia,
            GREATEST(0, (data_fim_vigencia - CURRENT_DATE)::INT) AS dias_ate_fim,
            nome_fornecedor AS fornecedor_atual,
            ni_fornecedor AS fornecedor_cnpj,
            setor_classificado
        FROM pncp_supplier_contracts
        WHERE data_fim_vigencia IS NOT NULL
          AND data_fim_vigencia BETWEEN CURRENT_DATE AND CURRENT_DATE + (p_janela_dias || ' days')::INTERVAL
          AND (p_setor IS NULL OR p_setor = '' OR setor_classificado = p_setor)
          AND (p_uf IS NULL OR p_uf = '' OR UPPER(codigo_uf) = UPPER(p_uf))
        ORDER BY data_fim_vigencia ASC
        LIMIT p_limit
    ),
    total_count AS (
        SELECT COUNT(*)::INT AS total FROM upcoming
    )
    SELECT JSON_BUILD_OBJECT(
        'setor', p_setor,
        'uf', p_uf,
        'janela_dias', p_janela_dias,
        'total', (SELECT total FROM total_count),
        'contratos', (
            SELECT JSON_AGG(
                JSON_BUILD_OBJECT(
                    'id', u.id,
                    'orgao_nome', u.orgao_nome,
                    'uf', u.uf,
                    'objeto', u.objeto,
                    'valor_total', u.valor_total,
                    'data_fim_vigencia', u.data_fim_vigencia,
                    'dias_ate_fim', u.dias_ate_fim,
                    'fornecedor_atual', u.fornecedor_atual,
                    'fornecedor_cnpj', u.fornecedor_cnpj,
                    'probabilidade_republicacao', CASE
                        WHEN u.dias_ate_fim <= 30 THEN 0.9
                        WHEN u.dias_ate_fim <= 60 THEN 0.7
                        WHEN u.dias_ate_fim <= 90 THEN 0.5
                        ELSE 0.3 END
                )
            )
            FROM upcoming u
        )
    ) INTO v_result;

    RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_upcoming_renewals TO service_role, anon, authenticated;

COMMENT ON FUNCTION public.get_upcoming_renewals IS
  'PREDINT-020: Retorna contratos proximos do vencimento para renovacao.';
