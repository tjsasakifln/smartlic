-- ============================================================================
-- COMPINT-003: RPC competitor_shadow_network — rede de parceiros do concorrente
-- Issue: #1274
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Wave 0 RPC for Competitive Intelligence EPIC (#1261). Analyzes
--   pncp_supplier_contracts + pncp_raw_bids to detect co-occurrence patterns
--   between the target competitor and other suppliers. Identifies:
--     - Consórcios recorrentes (multiple consortium bids together)
--     - Co-participantes frequentes (same bids, same lots)
--     - Possíveis subcontratações (indirect links)
--
--   Output (scalar JSON, bypasses PostgREST max_rows=1000):
--     {
--       "cnpj_raiz": "XXXXXXXXXXXXXX",
--       "nome_raiz": "EMPRESA X LTDA",
--       "shadow_network": [...],
--       "stats": {...},
--       "grafo": {"nodes": [...], "edges": [...]}
--     }
--
--   SECURITY DEFINER + SET search_path = public, pg_temp per
--   SEC-SECDEF-001/002 (feedback_secdef_search_path_trap).
--   GRANT to anon, authenticated, service_role — dados de contrato são públicos.
-- ============================================================================

-- Auxiliary index: numero_controle_pncp é a chave de junção para co-ocorrências
CREATE INDEX IF NOT EXISTS idx_psc_pncp_fornecedor
    ON pncp_supplier_contracts(numero_controle_pncp, ni_fornecedor)
    WHERE is_active = TRUE;

CREATE OR REPLACE FUNCTION public.competitor_shadow_network(
    p_cnpj TEXT,
    p_anos INT DEFAULT 5,
    p_min_co_occurrences INT DEFAULT 2
)
RETURNS json
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_cnpj_clean        text;
    v_cutoff_date       date;
    v_nome_raiz         text;
    v_result            json;

    -- Shadow network array
    v_shadow_network    json;

    -- Stats
    v_total_parceiros   int := 0;
    v_consorcios_detect int := 0;
    v_co_part_freq      int := 0;
    v_grau_rede         int := 0;
    v_densidade_rede    float8 := 0.0;

    -- Graph
    v_nodes             json;
    v_edges             json;
BEGIN
    -- ── Defesa em profundidade: timeout local de 15s
    SET LOCAL statement_timeout = '15s';

    -- ── Normalizar CNPJ: dígitos apenas, 14 caracteres
    v_cnpj_clean := regexp_replace(COALESCE(p_cnpj, ''), '[^0-9]', '', 'g');
    IF length(v_cnpj_clean) <> 14 THEN
        RAISE EXCEPTION 'CNPJ invalido: deve conter 14 digitos apos normalizacao, obtido %', length(v_cnpj_clean)
            USING HINT = 'Forneca um CNPJ de 14 digitos (apenas numeros)';
    END IF;

    IF p_anos IS NULL OR p_anos < 1 OR p_anos > 50 THEN
        RAISE EXCEPTION 'parametro invalido: p_anos deve estar entre 1 e 50';
    END IF;

    IF p_min_co_occurrences IS NULL OR p_min_co_occurrences < 1 THEN
        RAISE EXCEPTION 'parametro invalido: p_min_co_occurrences deve ser >= 1';
    END IF;

    v_cutoff_date := (CURRENT_DATE - (p_anos || ' years')::INTERVAL)::DATE;

    -- ── Nome do CNPJ raiz
    SELECT COALESCE(MAX(nome_fornecedor), '') INTO v_nome_raiz
    FROM public.pncp_supplier_contracts
    WHERE ni_fornecedor = v_cnpj_clean
      AND is_active = TRUE
      AND data_assinatura >= v_cutoff_date;

    -- ── Se não encontrou contratos, retornar objeto zerado
    IF v_nome_raiz = '' THEN
        RETURN json_build_object(
            'cnpj_raiz', v_cnpj_clean,
            'nome_raiz', '',
            'shadow_network', '[]'::json,
            'stats', json_build_object(
                'total_parceiros', 0,
                'consorcios_detectados', 0,
                'co_participantes_frequentes', 0,
                'grau_rede', 0,
                'densidade_rede', 0.0
            ),
            'grafo', json_build_object(
                'nodes', '[]'::json,
                'edges', '[]'::json
            )
        );
    END IF;

    -- ── Shadow Network: detectar co-ocorrências via PNCP ID
    WITH
    -- PNCP IDs onde o CNPJ raiz aparece
    target_pncp AS (
        SELECT DISTINCT numero_controle_pncp
        FROM public.pncp_supplier_contracts
        WHERE ni_fornecedor = v_cnpj_clean
          AND is_active = TRUE
          AND data_assinatura >= v_cutoff_date
          AND numero_controle_pncp IS NOT NULL
          AND numero_controle_pncp <> ''
    ),
    -- PNCP IDs compartilhados: onde raiz E parceiro aparecem juntos
    -- (um PNCP ID com ambos os fornecedores)
    shadow_candidates AS (
        SELECT
            sc.ni_fornecedor                        AS partner_cnpj,
            MAX(sc.nome_fornecedor)                  AS partner_nome,
            COUNT(DISTINCT sc.numero_controle_pncp)  AS editais_juntos
        FROM public.pncp_supplier_contracts sc
        INNER JOIN target_pncp tp ON sc.numero_controle_pncp = tp.numero_controle_pncp
        WHERE sc.ni_fornecedor <> v_cnpj_clean
          AND sc.is_active = TRUE
          AND sc.data_assinatura >= v_cutoff_date
        GROUP BY sc.ni_fornecedor
        HAVING COUNT(DISTINCT sc.numero_controle_pncp) >= p_min_co_occurrences
    ),
    -- Detalhamento: consórcios e co-ocorrências por parceiro
    partner_details AS (
        SELECT
            sc.ni_fornecedor                                                   AS partner_cnpj,
            COUNT(*)                                                           AS co_ocorrencias_total,
            COUNT(DISTINCT sc.numero_controle_pncp)                            AS editais_juntos,
            -- Consórcio por nome: nome_fornecedor contendo CONSORCIO
            COUNT(DISTINCT CASE
                WHEN sc.nome_fornecedor ~* 'consorcio|consórcio'
                THEN sc.numero_controle_pncp
                ELSE NULL
            END)                                                               AS consorcios_nome,
            -- Consórcio estrutural: >1 parceiro no mesmo PNCP ID (além do raiz)
            COUNT(DISTINCT CASE
                WHEN EXISTS (
                    SELECT 1 FROM public.pncp_supplier_contracts sc2
                    WHERE sc2.numero_controle_pncp = sc.numero_controle_pncp
                      AND sc2.is_active = TRUE
                      AND sc2.ni_fornecedor NOT IN (v_cnpj_clean, sc.ni_fornecedor)
                )
                THEN sc.numero_controle_pncp
                ELSE NULL
            END)                                                               AS consorcios_estruturais,
            -- Categoria principal: setor mais frequente no objeto_contrato
            (
                SELECT COALESCE(
                    (SELECT t.cat FROM (
                        SELECT
                            CASE
                                WHEN sc2.objeto_contrato ~* 'construcao|engenharia|reforma|edificacao|obra|pavimentacao|rodovia' THEN 'engenharia'
                                WHEN sc2.objeto_contrato ~* 'tecnologia|software|informatica|sistema|digital|ti|tecnológica' THEN 'tecnologia'
                                WHEN sc2.objeto_contrato ~* 'saude|medico|hospitalar|farmaceutico|medicamento|hospital' THEN 'saude'
                                WHEN sc2.objeto_contrato ~* 'educacao|ensino|treinamento|curso|capacitacao|escola' THEN 'educacao'
                                WHEN sc2.objeto_contrato ~* 'consultoria|assessoria|auditoria|parecer|consultoria' THEN 'consultoria'
                                WHEN sc2.objeto_contrato ~* 'limpeza|higienizacao|asseio|conservacao|faxina' THEN 'limpeza'
                                WHEN sc2.objeto_contrato ~* 'alimentacao|refeicao|merenda|nutricao|alimento' THEN 'alimentacao'
                                WHEN sc2.objeto_contrato ~* 'transporte|logistica|frota|veiculo|locomocao' THEN 'transporte'
                                WHEN sc2.objeto_contrato ~* 'seguranca|vigilancia|monitoramento|protecao' THEN 'seguranca'
                            END AS cat
                        FROM public.pncp_supplier_contracts sc2
                        WHERE sc2.ni_fornecedor = sc.ni_fornecedor
                          AND sc2.is_active = TRUE
                          AND sc2.data_assinatura >= v_cutoff_date
                          AND sc2.objeto_contrato IS NOT NULL
                    ) t
                    WHERE t.cat IS NOT NULL
                    GROUP BY t.cat
                    ORDER BY COUNT(*) DESC
                    LIMIT 1),
                    'outros'
                )
            ) AS categoria_principal
        FROM public.pncp_supplier_contracts sc
        INNER JOIN shadow_candidates sc_cand ON sc.ni_fornecedor = sc_cand.partner_cnpj
        INNER JOIN target_pncp tp ON sc.numero_controle_pncp = tp.numero_controle_pncp
        WHERE sc.is_active = TRUE
          AND sc.data_assinatura >= v_cutoff_date
        GROUP BY sc.ni_fornecedor
    ),
    -- Calcular forca_vinculo e tipo_vinculo para cada parceiro
    max_stats AS (
        SELECT
            GREATEST(MAX(co_ocorrencias_total), 1)::float8 AS max_co,
            COUNT(*)::float8                                 AS total_partners
        FROM partner_details
    ),
    enriched_partners AS (
        SELECT
            pd.partner_cnpj,
            MAX(pd.partner_nome)                             AS partner_nome,
            MAX(pd.co_ocorrencias_total)                     AS co_ocorrencias_total,
            MAX(pd.editais_juntos)                           AS editais_juntos,
            MAX(pd.consorcios_nome + pd.consorcios_estruturais) AS consorcios,
            MAX(pd.categoria_principal)                      AS categoria_principal,
            ROUND(LEAST(1.0, (
                -- forca_vinculo: weighted score (0 to 1)
                -- co-occurrence contribution (50%)
                (MAX(pd.co_ocorrencias_total)::float8 / GREATEST(MAX(ms.max_co), 1)) * 0.50
                +
                -- consortium contribution (30%)
                LEAST(
                    (MAX(pd.consorcios_nome + pd.consorcios_estruturais))::float8
                    / GREATEST(MAX(pd.editais_juntos), 1),
                    1.0
                ) * 0.30
                +
                -- category consistency bonus (20%)
                CASE WHEN MAX(pd.categoria_principal) <> 'outros' THEN 0.20 ELSE 0.0 END
            )), 4)::float8                               AS forca_vinculo,
            CASE
                WHEN MAX(pd.consorcios_nome + pd.consorcios_estruturais) > 2 THEN 'consorcio_recorrente'
                WHEN MAX(pd.co_ocorrencias_total) > 5 THEN 'co_participante_frequente'
                ELSE 'possivel_subcontratacao'
            END                                           AS tipo_vinculo
        FROM partner_details pd, max_stats ms
        GROUP BY pd.partner_cnpj
    )
    SELECT COALESCE(json_agg(
        json_build_object(
            'cnpj',             ep.partner_cnpj,
            'nome',             ep.partner_nome,
            'co_ocorrencias',   ep.co_ocorrencias_total,
            'editais_juntos',   ep.editais_juntos,
            'consorcios',       ep.consorcios,
            'categoria_principal', ep.categoria_principal,
            'forca_vinculo',    ep.forca_vinculo,
            'tipo_vinculo',     ep.tipo_vinculo
        )
        ORDER BY ep.forca_vinculo DESC, ep.co_ocorrencias_total DESC
    ), '[]'::json) INTO v_shadow_network
    FROM enriched_partners ep;

    -- ── Stats
    SELECT
        COALESCE(COUNT(*), 0)::int,
        COALESCE(SUM(CASE WHEN ep.consorcios > 0 THEN 1 ELSE 0 END), 0)::int,
        COALESCE(SUM(CASE WHEN ep.tipo_vinculo = 'co_participante_frequente' THEN 1 ELSE 0 END), 0)::int
    INTO
        v_total_parceiros,
        v_consorcios_detect,
        v_co_part_freq
    FROM enriched_partners ep;

    v_grau_rede := v_total_parceiros;
    v_densidade_rede := CASE
        WHEN v_total_parceiros > 1 THEN ROUND(LEAST(1.0, v_grau_rede::float8 / (v_total_parceiros * (v_total_parceiros - 1))), 4)
        ELSE 0.0
    END;

    -- ── Graph: nodes + edges
    SELECT
        COALESCE(
            json_agg(
                json_build_object('cnpj', v_cnpj_clean, 'nome', v_nome_raiz, 'grupo', 'raiz')
            ) || COALESCE(
                (SELECT json_agg(
                    json_build_object('cnpj', ep2.partner_cnpj, 'nome', ep2.partner_nome, 'grupo', 'parceiro')
                ) FROM enriched_partners ep2),
                '[]'::json
            ),
            '[]'::json
        )
    INTO v_nodes;

    SELECT COALESCE(json_agg(
        json_build_object(
            'source', v_cnpj_clean,
            'target', ep3.partner_cnpj,
            'peso',   ep3.forca_vinculo,
            'tipo',   ep3.tipo_vinculo
        )
        ORDER BY ep3.forca_vinculo DESC
    ), '[]'::json) INTO v_edges
    FROM enriched_partners ep3;

    -- ── Montar resultado final
    v_result := json_build_object(
        'cnpj_raiz', v_cnpj_clean,
        'nome_raiz', v_nome_raiz,
        'shadow_network', v_shadow_network,
        'stats', json_build_object(
            'total_parceiros',         v_total_parceiros,
            'consorcios_detectados',   v_consorcios_detect,
            'co_participantes_frequentes', v_co_part_freq,
            'grau_rede',               v_grau_rede,
            'densidade_rede',          v_densidade_rede
        ),
        'grafo', json_build_object(
            'nodes', v_nodes,
            'edges', v_edges
        )
    );

    RETURN v_result;
END;
$$;

-- Permite chamada pública — dados de contrato do PNCP são públicos
GRANT EXECUTE ON FUNCTION public.competitor_shadow_network(TEXT, INT, INT)
    TO anon, authenticated, service_role;

COMMENT ON FUNCTION public.competitor_shadow_network(TEXT, INT, INT) IS
    'COMPINT-003: Build competitor shadow network from pncp_supplier_contracts. '
    'Returns scalar JSON with shadow_network, stats, and grafo sections. '
    'Parameters: p_cnpj (14-digit CNPJ), p_anos (analysis window in years, default 5), '
    'p_min_co_occurrences (minimum co-occurrences, default 2).';
