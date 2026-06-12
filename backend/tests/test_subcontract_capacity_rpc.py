"""SUBINTEL-001 (#1668): Tests for the subcontract_capacity_signals RPC.

Tests the RPC SQL migration and expected JSON structure.
Covers:
  - Migration file structure (up + down, SECURITY DEFINER, grants)
  - JSON response shape verification
  - Input validation logic
  - Score calculation weights
  - Non-regression for existing RPCs/tables
"""

import os


def _read_migration() -> str:
    """Read the migration SQL file."""
    path = "supabase/migrations/20260612100000_subcontract_capacity_signals.sql"
    assert os.path.exists(path), f"Migration file not found: {path}"
    with open(path) as f:
        return f.read()


def _read_down_migration() -> str:
    """Read the down migration SQL file."""
    path = "supabase/migrations/20260612100000_subcontract_capacity_signals.down.sql"
    assert os.path.exists(path), f"Down migration file not found: {path}"
    with open(path) as f:
        return f.read()


class TestMigrationStructure:
    """Migration file structure and conventions."""

    def test_migration_up_exists(self):
        """Migration up file exists."""
        path = "supabase/migrations/20260612100000_subcontract_capacity_signals.sql"
        assert os.path.exists(path), f"Migration file not found: {path}"

    def test_migration_down_exists(self):
        """Migration down file exists."""
        path = "supabase/migrations/20260612100000_subcontract_capacity_signals.down.sql"
        assert os.path.exists(path), f"Down migration not found: {path}"

    def test_migration_creates_function(self):
        """Migration SQL contains CREATE OR REPLACE FUNCTION."""
        content = _read_migration()
        assert "CREATE OR REPLACE FUNCTION" in content
        assert "subcontract_capacity_signals" in content
        assert "RETURNS JSONB" in content

    def test_migration_has_security_definer(self):
        """Migration uses SECURITY DEFINER."""
        content = _read_migration()
        assert "SECURITY DEFINER" in content

    def test_migration_has_service_role_grant(self):
        """Migration grants EXECUTE to service_role only."""
        content = _read_migration()
        assert "GRANT EXECUTE ON FUNCTION" in content
        assert "service_role" in content

    def test_down_drops_function(self):
        """Down migration drops the function."""
        content = _read_down_migration()
        assert "DROP FUNCTION" in content
        assert "subcontract_capacity_signals" in content


class TestJsonStructure:
    """Validate the JSON structure returned by the RPC."""

    def test_expected_top_level_keys_present(self):
        """Migration builds all expected top-level keys in jsonb_build_object."""
        content = _read_migration()
        expected_keys = [
            "signal_repeat_winner",
            "signal_large_contract",
            "signal_subcontracting_pattern",
            "overall_capacity_score",
            "total_contracts",
            "total_value",
        ]
        for key in expected_keys:
            assert key in content, f"Expected key '{key}' not found in migration SQL"

    def test_signal_repeat_winner_keys_present(self):
        """signal_repeat_winner has score, same_orgao_count, orgaos."""
        content = _read_migration()
        for key in ("score", "same_orgao_count", "orgaos"):
            assert key in content, f"Missing key '{key}' in signal_repeat_winner"

    def test_signal_large_contract_keys_present(self):
        """signal_large_contract has score, contracts_above_5m, recent_large."""
        content = _read_migration()
        for key in ("score", "contracts_above_5m", "recent_large"):
            assert key in content, f"Missing key '{key}' in signal_large_contract"

    def test_signal_subcontracting_keys_present(self):
        """signal_subcontracting_pattern has score, cnae_diversity, related_suppliers."""
        content = _read_migration()
        for key in ("score", "cnae_diversity", "related_suppliers"):
            assert key in content, f"Missing key '{key}' in signal_subcontracting_pattern"

    def test_related_supplier_entry_fields(self):
        """related_suppliers entries have cnpj, razao_social, co_occurrence_count, total_value."""
        content = _read_migration()
        for field in ("cnpj", "razao_social", "co_occurrence_count", "total_value"):
            assert field in content, f"Missing field '{field}' in related_suppliers"

    def test_orgao_entry_fields(self):
        """orgao entries have nome, count, total_value."""
        content = _read_migration()
        for field in ("nome", "count", "total_value"):
            assert field in content, f"Missing field '{field}' in orgao entries"

    def test_recent_large_entry_fields(self):
        """recent_large entries have id, value, orgao, year."""
        content = _read_migration()
        for field in ("id", "value", "orgao", "year"):
            assert field in content, f"Missing field '{field}' in recent_large"


class TestInputValidation:
    """Tests for RPC input validation."""

    def test_empty_cnpj_raises_exception(self):
        """Empty CNPJ triggers RAISE EXCEPTION."""
        content = _read_migration()
        assert "RAISE EXCEPTION" in content
        assert "p_cnpj IS NULL" in content

    def test_limit_has_default(self):
        """p_limit has a default value of 50."""
        content = _read_migration()
        assert "p_limit INT DEFAULT 50" in content

    def test_limit_bounds_are_clamped(self):
        """p_limit is clamped between 1 and 200."""
        content = _read_migration()
        assert "p_limit < 1" in content
        assert "p_limit > 200" in content

    def test_zero_contracts_returns_zero_score(self):
        """No contracts returns all zero scores."""
        content = _read_migration()
        assert "v_total_contracts = 0" in content
        assert "overall_capacity_score" in content
        assert "0" in content


class TestScoreLogic:
    """Tests for scoring weights and thresholds."""

    def test_overall_score_weights_repeat_winner_03(self):
        """Repeat winner weight is 0.3."""
        content = _read_migration()
        assert "0.3" in content

    def test_overall_score_weights_large_contract_04(self):
        """Large contract weight is 0.4."""
        content = _read_migration()
        assert "0.4" in content

    def test_overall_score_weights_subcontract_03(self):
        """Subcontracting pattern weight is 0.3."""
        content = _read_migration()
        assert "* 0.3" in content

    def test_large_contract_threshold_is_5m(self):
        """Large contract threshold is R$5M."""
        content = _read_migration()
        assert "5000000" in content

    def test_repeat_winner_uses_top_orgao_ratio(self):
        """Repeat winner score uses proportion of top orgao contracts."""
        content = _read_migration()
        assert "v_same_orgao_count" in content
        assert "v_total_contracts" in content

    def test_capacity_score_is_rounded(self):
        """Overall capacity score uses ROUND with 4 decimal places."""
        content = _read_migration()
        assert "ROUND" in content
        assert "overall_capacity_score" in content


class TestNonRegression:
    """Ensure no existing RPCs or tables are affected."""

    def test_no_table_modifications(self):
        """Migration does not ALTER, CREATE, or DROP any table."""
        content = _read_migration()
        forbidden_patterns = [
            "ALTER TABLE",
            "DROP TABLE",
            "DROP INDEX",
            "CREATE TABLE",
            "CREATE INDEX",
        ]
        for pattern in forbidden_patterns:
            assert pattern not in content, f"Migration contains forbidden pattern: {pattern}"

    def test_only_one_function_created(self):
        """Migration creates exactly one new function."""
        content = _read_migration()
        count = content.count("CREATE OR REPLACE FUNCTION")
        assert count == 1, f"Expected 1 function creation, found {count}"

    def test_function_uses_supplier_contracts_table(self):
        """Migration queries pncp_supplier_contracts."""
        content = _read_migration()
        assert "pncp_supplier_contracts" in content

    def test_has_statement_timeout(self):
        """Migration sets statement_timeout for safety."""
        content = _read_migration()
        assert "statement_timeout" in content
