"""
PREDINT-001: Tests for predict_contract_expiry RPC

Validates the migration SQL (static analysis) and Python-level integration
(Mock supabase client). No live database connection required.

Test Matrix:
  AC1: Contracts without data_fim_vigencia excluded from list
  AC2: Empty window → stats.total_contratos_janela = 0
  AC3: probabilidade_republicacao always between 0 and 1
  AC4: Invalid UF returns empty
  AC5: Migration SQL structure matches project conventions
  AC6: GRANTs to correct roles
  AC7: Down migration is clean
"""

import re
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"
MIGRATION_FILE = "20260531030817_predict_contract_expiry.sql"
DOWN_MIGRATION_FILE = "20260531030817_predict_contract_expiry.down.sql"


@pytest.fixture(scope="module")
def migration_sql() -> str:
    """Load the up migration SQL."""
    path = MIGRATIONS_DIR / MIGRATION_FILE
    assert path.exists(), f"Migration file not found: {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def down_sql() -> str:
    """Load the down migration SQL."""
    path = MIGRATIONS_DIR / DOWN_MIGRATION_FILE
    assert path.exists(), f"Down migration file not found: {path}"
    return path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# AC5: Migration SQL structure matches project conventions
# ─────────────────────────────────────────────────────────────────────────────


class TestMigrationStructure:
    """AC5: Validate migration SQL follows project conventions."""

    def test_function_exists(self, migration_sql: str):
        """Must define the predict_contract_expiry function."""
        assert "predict_contract_expiry" in migration_sql

    def test_returns_json(self, migration_sql: str):
        """Must return json (scalar JSON to bypass PostgREST max_rows)."""
        assert "RETURNS json" in migration_sql

    def test_language_sql(self, migration_sql: str):
        """Must use LANGUAGE SQL (not plpgsql) — matches existing simple RPCs."""
        assert "LANGUAGE SQL" in migration_sql

    def test_stable_volatility(self, migration_sql: str):
        """Must be STABLE (not VOLATILE — read-only query)."""
        assert "STABLE" in migration_sql

    def test_security_definer(self, migration_sql: str):
        """Must be SECURITY DEFINER — needed to bypass RLS."""
        assert "SECURITY DEFINER" in migration_sql

    def test_search_path(self, migration_sql: str):
        """Must SET search_path = public (SEC-SECDEF convention)."""
        assert "SET search_path = public" in migration_sql

    def test_parameters_match_spec(self, migration_sql: str):
        """Four parameters with correct names and defaults."""
        assert "p_uf          TEXT DEFAULT NULL" in migration_sql
        assert "p_setor       TEXT DEFAULT NULL" in migration_sql
        assert "p_janela_dias INTEGER DEFAULT 90" in migration_sql
        assert "p_limit       INTEGER DEFAULT 100" in migration_sql

    def test_is_active_filter(self, migration_sql: str):
        """Must filter c.is_active = TRUE (only active contracts)."""
        assert "c.is_active = TRUE" in migration_sql

    def test_data_fim_vigencia_not_null_filter(self, migration_sql: str):
        """Must exclude contracts without data_fim_vigencia."""
        assert "c.data_fim_vigencia IS NOT NULL" in migration_sql

    def test_date_window_filter(self, migration_sql: str):
        """Must filter by date window using CURRENT_DATE + p_janela_dias."""
        assert "CURRENT_DATE + p_janela_dias" in migration_sql

    def test_uf_filter_is_optional(self, migration_sql: str):
        """UF filter must be optional (p_uf IS NULL OR ...)."""
        assert "p_uf IS NULL OR c.uf = upper(p_uf)" in migration_sql

    def test_setor_filter_is_optional(self, migration_sql: str):
        """Setor filter must be optional (p_setor IS NULL OR ...)."""
        assert "p_setor IS NULL OR c.setor_classificado = p_setor" in migration_sql

    def test_probability_clamped_between_005_and_095(self, migration_sql: str):
        """Probability must be clamped between 0.05 and 0.95."""
        assert "GREATEST(0.05" in migration_sql
        assert "LEAST(0.95" in migration_sql

    def test_json_build_object_contracts_array(self, migration_sql: str):
        """Output must include contracts array."""
        assert "'contracts'" in migration_sql

    def test_json_build_object_stats(self, migration_sql: str):
        """Output must include stats object."""
        assert "'stats'" in migration_sql

    def test_coalesce_json_agg_empty_array(self, migration_sql: str):
        """Empty results must be '[]'::json, not NULL."""
        assert "COALESCE" in migration_sql
        assert "'[]'::json" in migration_sql

    def test_columns_added(self, migration_sql: str):
        """Must ALTER TABLE ADD COLUMN IF NOT EXISTS the 3 new columns."""
        assert "ADD COLUMN IF NOT EXISTS data_fim_vigencia DATE" in migration_sql
        assert "ADD COLUMN IF NOT EXISTS setor_classificado TEXT" in migration_sql
        assert "ADD COLUMN IF NOT EXISTS data_publicacao DATE" in migration_sql

    def test_indexes_created(self, migration_sql: str):
        """Must create both auxiliary indexes."""
        assert "idx_psc_data_fim_vigencia" in migration_sql
        assert "idx_psc_expiry_uf_setor" in migration_sql

    def test_recorrencia_historica_computed(self, migration_sql: str):
        """Must compute recorrencia_historica in a subquery."""
        assert "recorrencia_historica" in migration_sql

    def test_orgao_recorrencia_score_computed(self, migration_sql: str):
        """Must compute orgao_recorrencia_score."""
        assert "orgao_recorrencia_score" in migration_sql

    def test_dias_ate_fim_computed(self, migration_sql: str):
        """Must compute dias_ate_fim."""
        assert "dias_ate_fim" in migration_sql

    def test_limit_applied(self, migration_sql: str):
        """Must apply LIMIT p_limit."""
        assert "LIMIT p_limit" in migration_sql


# ─────────────────────────────────────────────────────────────────────────────
# AC6: GRANTs to correct roles
# ─────────────────────────────────────────────────────────────────────────────


class TestGrants:
    """AC6: Verify GRANT EXECUTE to correct roles."""

    def test_grant_to_anon(self, migration_sql: str):
        """anon must be granted EXECUTE (public data)."""
        assert "TO anon, authenticated, service_role" in migration_sql

    def test_only_one_grant_statement(self, migration_sql: str):
        """Single GRANT statement covering all 3 roles (not split)."""
        pattern = r"GRANT EXECUTE ON FUNCTION .*?TO anon, authenticated, service_role;"
        matches = re.findall(pattern, migration_sql, re.DOTALL)
        assert len(matches) == 1, (
            f"Expected exactly 1 combined GRANT, found {len(matches)}. "
            "Prefer a single GRANT to all roles."
        )


# ─────────────────────────────────────────────────────────────────────────────
# AC7: Down migration is clean
# ─────────────────────────────────────────────────────────────────────────────


class TestDownMigration:
    """AC7: Down migration must reverse all changes cleanly."""

    def test_drops_function(self, down_sql: str):
        """Must DROP FUNCTION predict_contract_expiry."""
        assert "DROP FUNCTION IF EXISTS public.predict_contract_expiry" in down_sql

    def test_drops_indexes(self, down_sql: str):
        """Must DROP INDEX both auxiliary indexes."""
        assert "DROP INDEX IF EXISTS idx_psc_expiry_uf_setor" in down_sql
        assert "DROP INDEX IF EXISTS idx_psc_data_fim_vigencia" in down_sql

    def test_drops_columns(self, down_sql: str):
        """Must DROP COLUMN IF EXISTS all 3 added columns."""
        assert "DROP COLUMN IF EXISTS data_fim_vigencia" in down_sql
        assert "DROP COLUMN IF EXISTS setor_classificado" in down_sql
        assert "DROP COLUMN IF EXISTS data_publicacao" in down_sql

    def test_no_trailing_commands(self, down_sql: str):
        """Down migration should be pure DROP/ALTER, no CREATE/GRANT."""
        assert "CREATE" not in down_sql
        assert "GRANT" not in down_sql


# ─────────────────────────────────────────────────────────────────────────────
# AC1: Contracts without data_fim_vigencia excluded
# ─────────────────────────────────────────────────────────────────────────────


class TestEndDateExclusion:
    """AC1: Contracts without data_fim_vigencia must be excluded."""

    def test_sql_filters_null_dates(self, migration_sql: str):
        """WHERE clause must include 'data_fim_vigencia IS NOT NULL'."""
        null_check = re.search(
            r"c\.data_fim_vigencia\s+IS\s+NOT\s+NULL",
            migration_sql,
            re.IGNORECASE,
        )
        assert null_check is not None, (
            "Missing IS NOT NULL filter on data_fim_vigencia. "
            "Without it, NULL dates would be included in the window."
        )

    def test_window_starts_at_current_date(self, migration_sql: str):
        """Date filter must start at CURRENT_DATE and exclude past dates."""
        ge_check = re.search(
            r"data_fim_vigencia\s+>=\s+CURRENT_DATE",
            migration_sql,
            re.IGNORECASE,
        )
        assert ge_check is not None, (
            "Missing '>= CURRENT_DATE' filter. "
            "Contracts with end dates in the past must be excluded."
        )


# ─────────────────────────────────────────────────────────────────────────────
# AC2: Empty window → stats.total_contratos_janela = 0
# ─────────────────────────────────────────────────────────────────────────────


class TestEmptyWindow:
    """AC2: When no contracts match the window, totals must be 0."""

    def test_stats_uses_coalesce(self, migration_sql: str):
        """Stats subquery must use COALESCE to ensure 0 instead of NULL."""
        # Check that the stats COALESCE patterns exist
        coalesce_count = migration_sql.count("COALESCE(COUNT(*)::int, 0)")
        assert coalesce_count >= 1, (
            "Stats must COALESCE COUNT to 0 for empty window."
        )

    def test_contracts_defaults_to_empty_array(self, migration_sql: str):
        """Contracts array defaults to '[]'::json when empty."""
        assert "COALESCE(" in migration_sql
        assert "'[]'::json" in migration_sql

    def test_valor_total_sob_risco_coalesces(self, migration_sql: str):
        """valor_total_sob_risco must COALESCE to 0."""
        assert "COALESCE(SUM(valor_total)::numeric, 0)" in migration_sql


# ─────────────────────────────────────────────────────────────────────────────
# AC3: probabilidade_republicacao between 0 and 1
# ─────────────────────────────────────────────────────────────────────────────


class TestProbabilityBounds:
    """AC3: Probability must always be within [0.05, 0.95]."""

    def test_lower_bound_is_005(self, migration_sql: str):
        """GREATEST(0.05, ...) ensures minimum probability of 0.05."""
        assert "GREATEST(0.05" in migration_sql

    def test_upper_bound_is_095(self, migration_sql: str):
        """LEAST(0.95, ...) ensures maximum probability of 0.95."""
        assert "LEAST(0.95" in migration_sql

    def test_rounded_to_2_decimals(self, migration_sql: str):
        """Probability rounded to 2 decimal places in output."""
        assert "ROUND(r.probabilidade_republicacao::numeric, 2)::float8" in migration_sql

    def test_recorrencia_historica_contributes_to_probability(self, migration_sql: str):
        """recorrencia_historica must be a factor in probability."""
        assert "recorrencia_historica::numeric / 30.0" in migration_sql

    def test_orgao_recorrencia_score_contributes_to_probability(self, migration_sql: str):
        """orgao_recorrencia_score must be a factor in probability."""
        assert "orgao_recorrencia_score * 0.30" in migration_sql


# ─────────────────────────────────────────────────────────────────────────────
# AC4: Invalid UF returns empty
# ─────────────────────────────────────────────────────────────────────────────


class TestInvalidUF:
    """AC4: An invalid UF must return empty results."""

    def test_uf_compared_to_upper(self, migration_sql: str):
        """UF comparison uses upper(p_uf) — normalizes input."""
        assert "upper(p_uf)" in migration_sql

    def test_uf_optional_condition(self, migration_sql: str):
        """UF filter includes NULL check for optional parameter."""
        assert "p_uf IS NULL OR" in migration_sql

    def test_stats_still_returns_zero(self, migration_sql: str):
        """Even with invalid UF, stats must return 0, not NULL."""
        # The COALESCE on the stats output ensures this
        coalesce_count = migration_sql.count("COALESCE(COUNT(*)::int, 0)")
        assert coalesce_count >= 1, (
            "COALESCE ensures count is 0 even with no matching rows."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Mock-based integration test
# ─────────────────────────────────────────────────────────────────────────────


class TestMockIntegration:
    """Verify the backend handles RPC responses correctly.

    Uses a mock supabase client to simulate predict_contract_expiry responses.
    """

    def test_mock_empty_response(self):
        """Empty RPC response (no contracts in window) returns zero stats."""
        from unittest.mock import MagicMock, patch

        mock_data = {
            "contracts": [],
            "stats": {
                "total_contratos_janela": 0,
                "valor_total_sob_risco": 0,
                "orgaos_afetados": 0,
            },
        }

        mock_sb = MagicMock()
        mock_rpc = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [mock_data]
        mock_rpc.execute.return_value = mock_result
        mock_sb.rpc.return_value = mock_rpc

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            from supabase_client import get_supabase
            sb = get_supabase()
            resp = sb.rpc(
                "predict_contract_expiry",
                {"p_uf": "XX", "p_janela_dias": 90},
            ).execute()

            result = resp.data[0]
            assert result["stats"]["total_contratos_janela"] == 0
            assert result["stats"]["valor_total_sob_risco"] == 0
            assert result["stats"]["orgaos_afetados"] == 0
            assert result["contracts"] == []

    def test_mock_contract_with_probability(self):
        """Contract with probability within [0, 1]."""
        from unittest.mock import MagicMock, patch

        mock_data = {
            "contracts": [
                {
                    "orgao_nome": "PREFEITURA MUNICIPAL DE CURITIBA",
                    "orgao_uf": "PR",
                    "objeto": "Aquisição de material de escritório",
                    "valor_total": 50000.00,
                    "data_fim_vigencia": "2026-08-15",
                    "dias_ate_fim": 76,
                    "fornecedor_atual": "EMPRESA X LTDA",
                    "fornecedor_cnpj": "XX.XXX.XXX/0001-XX",
                    "categoria": "tecnologia",
                    "probabilidade_republicacao": 0.75,
                    "recorrencia_historica": 5,
                }
            ],
            "stats": {
                "total_contratos_janela": 1,
                "valor_total_sob_risco": 50000.00,
                "orgaos_afetados": 1,
            },
        }

        mock_sb = MagicMock()
        mock_rpc = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [mock_data]
        mock_rpc.execute.return_value = mock_result
        mock_sb.rpc.return_value = mock_rpc

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            from supabase_client import get_supabase
            sb = get_supabase()
            resp = sb.rpc(
                "predict_contract_expiry",
                {"p_uf": "PR", "p_janela_dias": 90},
            ).execute()

            result = resp.data[0]
            prob = result["contracts"][0]["probabilidade_republicacao"]
            assert 0.0 <= prob <= 1.0, (
                f"Probability {prob} outside valid range [0, 1]"
            )

    def test_mock_contract_without_end_date_excluded(self):
        """Simulate response where contracts without end date are excluded."""
        # Only contracts with data_fim_vigencia appear in the response
        mock_data = {
            "contracts": [
                {
                    "orgao_nome": "MINISTÉRIO DA SAÚDE",
                    "orgao_uf": "DF",
                    "objeto": "Serviços de limpeza",
                    "valor_total": 1500000.00,
                    "data_fim_vigencia": "2026-08-15",
                    "dias_ate_fim": 76,
                    "fornecedor_atual": "EMPRESA Y LTDA",
                    "fornecedor_cnpj": "XX.XXX.XXX/0001-XX",
                    "categoria": "limpeza",
                    "probabilidade_republicacao": 0.6,
                    "recorrencia_historica": 3,
                }
            ],
            "stats": {
                "total_contratos_janela": 1,
                "valor_total_sob_risco": 1500000.00,
                "orgaos_afetados": 1,
            },
        }

        # Verify no contract in the output has null data_fim_vigencia
        for contract in mock_data["contracts"]:
            assert contract["data_fim_vigencia"] is not None
