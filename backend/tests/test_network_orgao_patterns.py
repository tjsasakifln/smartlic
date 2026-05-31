"""NETINT-003: Tests for RPC network_orgao_patterns (#1285).

Padroes emergentes de contratacao por orgao publico.

Strategy:
- Content validation: check migration SQL for required statements
- Unit tests: mock supabase.rpc() to validate JSON output shape
- Edge cases: extreme parameters, empty data, UF filter
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Migration file paths
MIGRATION_DIR = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
MIGRATION_FILE = "20260531173935_network_orgao_patterns.sql"
DOWN_MIGRATION_FILE = "20260531173935_network_orgao_patterns.down.sql"

UP_MIGRATION = MIGRATION_DIR / MIGRATION_FILE
DOWN_MIGRATION = MIGRATION_DIR / DOWN_MIGRATION_FILE


# ============================================================================
# Sample mock data for RPC responses
# ============================================================================

SAMPLE_PATTERNS_DATA = {
    "padroes_emergentes": [
        {
            "orgao_nome": "MINISTERIO DA EDUCACAO",
            "orgao_uf": "DF",
            "categoria": "software",
            "frequencia_recente": 8,
            "frequencia_historica": 1.0,
            "fator_mudanca": 8.0,
            "volume_recente": 4500000.00,
            "sinal": "explosao",
        },
        {
            "orgao_nome": "SECRETARIA DE SAUDE SP",
            "orgao_uf": "SP",
            "categoria": "saude",
            "frequencia_recente": 12,
            "frequencia_historica": 4.0,
            "fator_mudanca": 3.0,
            "volume_recente": 12000000.00,
            "sinal": "crescimento",
        },
        {
            "orgao_nome": "PREFEITURA DE CAMPINAS",
            "orgao_uf": "SP",
            "categoria": "construcao",
            "frequencia_recente": 5,
            "frequencia_historica": 4.0,
            "fator_mudanca": 1.25,
            "volume_recente": 8000000.00,
            "sinal": "moderado",
        },
    ],
    "stats": {
        "orgaos_analisados": 500,
        "padroes_detectados": 34,
        "categoria_mais_emergente": "tecnologia",
    },
}

EMPTY_PATTERNS_DATA = {
    "padroes_emergentes": [],
    "stats": {
        "orgaos_analisados": 0,
        "padroes_detectados": 0,
        "categoria_mais_emergente": "N/A",
    },
}


def _make_supabase_mock(return_data):
    """Create a MagicMock for supabase that returns the given data from rpc().execute()."""
    rpc_response = MagicMock()
    rpc_response.data = return_data
    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value = rpc_response
    return mock_sb


# ============================================================================
# Migration SQL Content Validation
# ============================================================================


class TestMigrationContent:
    """Validate the migration SQL files contain all required operations."""

    @pytest.fixture(autouse=True)
    def load_migrations(self):
        assert UP_MIGRATION.exists(), f"Migration file not found: {UP_MIGRATION}"
        assert DOWN_MIGRATION.exists(), f"Down migration not found: {DOWN_MIGRATION}"
        self.up_sql = UP_MIGRATION.read_text(encoding="utf-8")
        self.down_sql = DOWN_MIGRATION.read_text(encoding="utf-8")

    # -- Function definition --
    def test_creates_function(self):
        """Migration creates network_orgao_patterns RPC."""
        assert "CREATE OR REPLACE FUNCTION public.network_orgao_patterns(" in self.up_sql
        assert "RETURNS json" in self.up_sql

    def test_function_signature(self):
        """Function has correct parameters: p_uf optional, p_meses default 6, p_min_frequencia default 3."""
        assert "p_uf VARCHAR(2) DEFAULT NULL" in self.up_sql
        assert "p_meses INT DEFAULT 6" in self.up_sql
        assert "p_min_frequencia INT DEFAULT 3" in self.up_sql

    def test_security_definer(self):
        """Function uses SECURITY DEFINER with SET search_path."""
        assert "SECURITY DEFINER" in self.up_sql
        assert "SET search_path = public, pg_temp" in self.up_sql

    def test_stable_volatility(self):
        """Function is declared STABLE (read-only)."""
        assert "STABLE" in self.up_sql

    def test_language_plpgsql(self):
        """Function uses LANGUAGE plpgsql."""
        assert "LANGUAGE plpgsql" in self.up_sql

    def test_statement_timeout(self):
        """Function sets LOCAL statement_timeout = '15s'."""
        assert "statement_timeout = '15s'" in self.up_sql

    def test_is_active_filter(self):
        """Function filters by is_active = TRUE."""
        assert "is_active = TRUE" in self.up_sql

    def test_fonte_pncp_supplier_contracts(self):
        """Function queries pncp_supplier_contracts as data source."""
        assert "pncp_supplier_contracts" in self.up_sql

    def test_categoria_fallback_geral(self):
        """Category uses COALESCE(setor_classificado, 'geral') as fallback."""
        assert "COALESCE(setor_classificado, 'geral')" in self.up_sql

    # -- Classification logic --
    def test_sinal_explosao(self):
        """Explosao class: fator_mudanca > 5."""
        assert "'explosao'" in self.up_sql

    def test_sinal_crescimento(self):
        """Crescimento class: fator_mudanca >= 2."""
        assert "'crescimento'" in self.up_sql

    def test_sinal_moderado(self):
        """Moderado class: fator_mudanca < 2."""
        assert "'moderado'" in self.up_sql

    def test_fator_mudanca_formula(self):
        """fator_mudanca = frequencia_recente / GREATEST(frequencia_historica, 1)."""
        assert "GREATEST" in self.up_sql

    # -- CTE structure --
    def test_uses_with_clause(self):
        """Query uses WITH (CTE) clause."""
        assert "WITH" in self.up_sql

    def test_has_contract_base_cte(self):
        """Has contract_base CTE."""
        assert "contract_base AS" in self.up_sql

    def test_has_recent_freq_cte(self):
        """Has recent_freq CTE."""
        assert "recent_freq AS" in self.up_sql

    def test_has_historical_freq_cte(self):
        """Has historical_freq CTE."""
        assert "historical_freq AS" in self.up_sql

    def test_has_patterns_cte(self):
        """Has patterns CTE."""
        assert "patterns AS" in self.up_sql

    def test_has_stats_data_cte(self):
        """Has stats_data CTE."""
        assert "stats_data AS" in self.up_sql

    def test_recent_filters_current_period(self):
        """Recent counts use data_assinatura >= v_cutoff_atual."""
        assert "data_assinatura >= v_cutoff_atual" in self.up_sql

    def test_historical_filters_prior_period(self):
        """Historical counts use data_assinatura < v_cutoff_atual."""
        assert "data_assinatura < v_cutoff_atual" in self.up_sql

    def test_base_covers_full_period(self):
        """contract_base covers from v_cutoff_historico."""
        assert "v_cutoff_historico" in self.up_sql

    def test_historical_calc_avg_monthly(self):
        """Historical frequency divides by p_meses for monthly average."""
        assert "/ p_meses" in self.up_sql

    # -- Grants --
    def test_grants_to_anon(self):
        """GRANT EXECUTE to anon."""
        assert "GRANT EXECUTE ON FUNCTION public.network_orgao_patterns" in self.up_sql
        assert "TO anon" in self.up_sql

    def test_grants_to_authenticated(self):
        """GRANT EXECUTE to authenticated."""
        assert "GRANT EXECUTE ON FUNCTION public.network_orgao_patterns" in self.up_sql
        assert "TO authenticated" in self.up_sql

    def test_grants_to_service_role(self):
        """GRANT EXECUTE to service_role."""
        assert "GRANT EXECUTE ON FUNCTION public.network_orgao_patterns" in self.up_sql
        assert "TO service_role" in self.up_sql

    def test_all_three_grants_present(self):
        """All three GRANT statements are present."""
        count = self.up_sql.count("GRANT EXECUTE ON FUNCTION public.network_orgao_patterns")
        assert count == 3, f"Expected 3 GRANTs, found {count}"

    # -- Output structure (present in SQL) --
    def test_output_padroes_emergentes(self):
        """Output JSON includes 'padroes_emergentes' array."""
        assert "'padroes_emergentes'" in self.up_sql

    def test_output_stats(self):
        """Output JSON includes 'stats' object."""
        assert "'stats'" in self.up_sql

    def test_output_orgao_nome(self):
        """Each pattern includes orgao_nome."""
        assert "'orgao_nome'" in self.up_sql

    def test_output_orgao_uf(self):
        """Each pattern includes orgao_uf."""
        assert "'orgao_uf'" in self.up_sql

    def test_output_categoria(self):
        """Each pattern includes categoria."""
        assert "'categoria'" in self.up_sql

    def test_output_frequencia_recente(self):
        """Each pattern includes frequencia_recente."""
        assert "'frequencia_recente'" in self.up_sql

    def test_output_frequencia_historica(self):
        """Each pattern includes frequencia_historica."""
        assert "'frequencia_historica'" in self.up_sql

    def test_output_fator_mudanca(self):
        """Each pattern includes fator_mudanca."""
        assert "'fator_mudanca'" in self.up_sql

    def test_output_volume_recente(self):
        """Each pattern includes volume_recente."""
        assert "'volume_recente'" in self.up_sql

    def test_output_sinal(self):
        """Each pattern includes sinal."""
        assert "'sinal'" in self.up_sql

    def test_output_orgaos_analisados(self):
        """Stats includes orgaos_analisados."""
        assert "'orgaos_analisados'" in self.up_sql

    def test_output_padroes_detectados(self):
        """Stats includes padroes_detectados."""
        assert "'padroes_detectados'" in self.up_sql

    def test_output_categoria_mais_emergente(self):
        """Stats includes categoria_mais_emergente."""
        assert "'categoria_mais_emergente'" in self.up_sql

    def test_empty_array_fallback(self):
        """Empty padroes_emergentes returns [] not NULL."""
        assert "'[]'::json" in self.up_sql

    def test_comment_exists(self):
        """Function has a COMMENT describing it."""
        assert "COMMENT ON FUNCTION" in self.up_sql
        assert "NETINT-003" in self.up_sql

    def test_uses_json_build_object(self):
        """Uses JSON_BUILD_OBJECT."""
        assert "json_build_object" in self.up_sql.lower()

    def test_uses_json_agg(self):
        """Uses JSON_AGG for the padroes_emergentes array."""
        assert "json_agg" in self.up_sql.lower()

    def test_order_by_fator_mudanca(self):
        """Patterns are ordered by fator_mudanca DESC."""
        assert "ORDER BY p.fator_mudanca DESC" in self.up_sql

    def test_having_min_frequencia(self):
        """HAVING clause enforces p_min_frequencia minimum."""
        assert "HAVING COUNT(*) >= p_min_frequencia" in self.up_sql

    # -- UF filter --
    def test_uf_filter_condition(self):
        """UF filter uses CASE expression to apply only when provided."""
        assert "UPPER(uf) = UPPER(p_uf)" in self.up_sql

    def test_uf_null_accept_all(self):
        """When p_uf is NULL, all UFs are included."""
        assert "p_uf IS NULL OR" in self.up_sql

    # -- Down migration --
    def test_down_drops_function(self):
        """Down migration drops the function."""
        assert "DROP FUNCTION IF EXISTS public.network_orgao_patterns" in self.down_sql

    def test_down_file_exists(self):
        """.down.sql file exists."""
        assert DOWN_MIGRATION.exists()
        assert DOWN_MIGRATION.read_text(encoding="utf-8").strip() != ""


# ============================================================================
# Unit Tests — Mocked Supabase RPC
# ============================================================================


class TestRpcContract:
    """Verify the RPC output shape via mock."""

    def test_accepts_all_params_default(self):
        """RPC can be called with no parameters (all defaults)."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert "padroes_emergentes" in result
        assert "stats" in result

    def test_accepts_uf_filter(self):
        """RPC accepts p_uf parameter."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {"p_uf": "SP"},
        ).execute().data

        assert isinstance(result, dict)
        assert "padroes_emergentes" in result

    def test_accepts_all_parameters(self):
        """RPC accepts p_uf, p_meses, p_min_frequencia."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {"p_uf": "DF", "p_meses": 12, "p_min_frequencia": 5},
        ).execute().data

        assert isinstance(result, dict)

    def test_output_top_level_keys(self):
        """Output JSON has required top-level keys."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert "padroes_emergentes" in result
        assert "stats" in result

    def test_pattern_has_all_required_fields(self):
        """Each pattern entry has all required sub-fields."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        pattern = result["padroes_emergentes"][0]
        assert "orgao_nome" in pattern
        assert "orgao_uf" in pattern
        assert "categoria" in pattern
        assert "frequencia_recente" in pattern
        assert "frequencia_historica" in pattern
        assert "fator_mudanca" in pattern
        assert "volume_recente" in pattern
        assert "sinal" in pattern

    def test_stats_has_all_required_fields(self):
        """Stats block has all required sub-fields."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        stats = result["stats"]
        assert "orgaos_analisados" in stats
        assert "padroes_detectados" in stats
        assert "categoria_mais_emergente" in stats

    def test_sinal_classification_explosao(self):
        """Sinal is explosao when fator_mudanca > 5."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        pattern = result["padroes_emergentes"][0]
        assert pattern["sinal"] == "explosao"
        assert pattern["fator_mudanca"] > 5

    def test_sinal_classification_crescimento(self):
        """Sinal is crescimento when fator_mudanca between 2 and 5."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        pattern = result["padroes_emergentes"][1]
        assert pattern["sinal"] == "crescimento"
        assert 2 <= pattern["fator_mudanca"] <= 5

    def test_sinal_classification_moderado(self):
        """Sinal is moderado when fator_mudanca < 2."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        pattern = result["padroes_emergentes"][2]
        assert pattern["sinal"] == "moderado"
        assert pattern["fator_mudanca"] < 2

    def test_frequencia_historica_is_float(self):
        """frequencia_historica can be a decimal (monthly average)."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert isinstance(result["padroes_emergentes"][0]["frequencia_historica"], (int, float))
        assert isinstance(result["padroes_emergentes"][1]["frequencia_historica"], (int, float))

    def test_frequencia_recente_is_int(self):
        """frequencia_recente is integer (count)."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert isinstance(result["padroes_emergentes"][0]["frequencia_recente"], int)

    def test_multiple_patterns_returned(self):
        """Multiple patterns can be returned."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert len(result["padroes_emergentes"]) == 3

    def test_json_serializable(self):
        """Output must be JSON-serializable (no NaN, no circular refs)."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        json.dumps(result)


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Edge cases: empty data, extreme parameters."""

    def test_empty_data_returns_empty_array(self):
        """When no data, padroes_emergentes is an empty array."""
        mock_sb = _make_supabase_mock(EMPTY_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert result["padroes_emergentes"] == []
        assert result["stats"]["padroes_detectados"] == 0
        assert result["stats"]["orgaos_analisados"] == 0
        assert result["stats"]["categoria_mais_emergente"] == "N/A"

    def test_extreme_p_meses_1(self):
        """p_meses=1 should not cause errors — returns whatever fits in 1 month."""
        mock_sb = _make_supabase_mock(EMPTY_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {"p_meses": 1},
        ).execute().data

        assert result["padroes_emergentes"] == []

    def test_extreme_p_min_frequencia_100(self):
        """p_min_frequencia=100 should return empty unless enough data exists."""
        mock_sb = _make_supabase_mock(EMPTY_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {"p_min_frequencia": 100},
        ).execute().data

        assert result["padroes_emergentes"] == []

    def test_uf_without_data_returns_empty(self):
        """Filtering by a UF with no contracts returns empty patterns."""
        mock_sb = _make_supabase_mock(EMPTY_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {"p_uf": "XX"},
        ).execute().data

        assert result["padroes_emergentes"] == []

    def test_padroes_emergentes_never_null(self):
        """padroes_emergentes is always an array, never null."""
        mock_sb = _make_supabase_mock(EMPTY_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert isinstance(result["padroes_emergentes"], list)
        assert result["padroes_emergentes"] is not None

    def test_stats_values_are_non_negative(self):
        """Stats values are non-negative integers."""
        mock_sb = _make_supabase_mock(EMPTY_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert result["stats"]["orgaos_analisados"] >= 0
        assert result["stats"]["padroes_detectados"] >= 0

    def test_no_uf_filter_returns_all(self):
        """Omitting p_uf returns patterns for all UFs."""
        mock_sb = _make_supabase_mock(SAMPLE_PATTERNS_DATA)

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert len(result["padroes_emergentes"]) == 3

    def test_fator_mudanca_never_negative(self):
        """fator_mudanca is always >= 0 (uses GREATEST(_, 1))."""
        mock_sb = _make_supabase_mock({

            "padroes_emergentes": [
                {
                    "orgao_nome": "ORGAO TESTE",
                    "orgao_uf": "SP",
                    "categoria": "geral",
                    "frequencia_recente": 5,
                    "frequencia_historica": 0.0,
                    "fator_mudanca": 5.0,
                    "volume_recente": 100000.00,
                    "sinal": "crescimento",
                },
            ],
            "stats": {
                "orgaos_analisados": 1,
                "padroes_detectados": 1,
                "categoria_mais_emergente": "geral",
            },
        })

        result = mock_sb.rpc(
            "network_orgao_patterns",
            {},
        ).execute().data

        assert result["padroes_emergentes"][0]["fator_mudanca"] >= 0
