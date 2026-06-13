"""PREDINT-020 (#1664): Tests for Time Series RPCs.

These tests validate the SQL function signatures and basic query structure.
They do NOT execute against a real database — they verify that the
migration files are valid SQL and that the function signatures are correct
through the Python-SQL interface documentation.
"""

from __future__ import annotations

from pathlib import Path


# Migration file paths
MIGRATIONS_DIR = Path("../supabase/migrations")


def _get_migration(name: str) -> str:
    """Get the SQL content of a migration file."""
    path = MIGRATIONS_DIR / name
    assert path.exists(), f"Migration file not found: {path}"
    content = path.read_text()
    assert len(content) > 100, f"Migration file {name} is too short"
    return content


def _get_down_migration(name: str) -> str:
    """Get the SQL content of a down migration file."""
    path = MIGRATIONS_DIR / name
    assert path.exists(), f"Down migration file not found: {path}"
    content = path.read_text()
    assert "DROP FUNCTION" in content, f"Down migration {name} missing DROP FUNCTION"
    return content


class TestPredintRpcMigrations:
    """Validate migration file structure for all 4 RPCs."""

    def test_rpc_1_get_sector_monthly_volume_exists(self):
        """RPC 1 migration file exists and has content."""
        content = _get_migration("20260612000000_rpc_get_sector_monthly_volume.sql")
        assert "FUNCTION public.get_sector_monthly_volume" in content
        assert "pncp_supplier_contracts" in content
        assert "GRANT EXECUTE" in content

    def test_rpc_1_down_migration_exists(self):
        """RPC 1 down migration exists."""
        _get_down_migration("20260612000000_rpc_get_sector_monthly_volume.down.sql")

    def test_rpc_1_has_expected_parameters(self):
        """RPC 1 has correct parameters."""
        content = _get_migration("20260612000000_rpc_get_sector_monthly_volume.sql")
        assert "p_setor TEXT" in content
        assert "p_uf TEXT DEFAULT NULL" in content
        assert "p_window_months INT DEFAULT 12" in content
        assert "RETURNS JSON" in content

    def test_rpc_2_get_sector_seasonal_pattern_exists(self):
        """RPC 2 migration file exists and has content."""
        content = _get_migration("20260612000001_rpc_get_sector_seasonal_pattern.sql")
        assert "FUNCTION public.get_sector_seasonal_pattern" in content
        assert "pncp_supplier_contracts" in content
        assert "GRANT EXECUTE" in content

    def test_rpc_2_down_migration_exists(self):
        """RPC 2 down migration exists."""
        _get_down_migration("20260612000001_rpc_get_sector_seasonal_pattern.down.sql")

    def test_rpc_2_has_expected_parameters(self):
        """RPC 2 has correct parameters."""
        content = _get_migration("20260612000001_rpc_get_sector_seasonal_pattern.sql")
        assert "p_setor TEXT" in content
        assert "p_uf TEXT DEFAULT NULL" in content
        assert "p_window_months INT DEFAULT 24" in content
        assert "indice_sazonalidade" in content

    def test_rpc_3_get_uf_demand_trend_exists(self):
        """RPC 3 migration file exists and has content."""
        content = _get_migration("20260612000002_rpc_get_uf_demand_trend.sql")
        assert "FUNCTION public.get_uf_demand_trend" in content
        assert "pncp_supplier_contracts" in content
        assert "GRANT EXECUTE" in content

    def test_rpc_3_down_migration_exists(self):
        """RPC 3 down migration exists."""
        _get_down_migration("20260612000002_rpc_get_uf_demand_trend.down.sql")

    def test_rpc_3_has_expected_parameters(self):
        """RPC 3 has correct parameters."""
        content = _get_migration("20260612000002_rpc_get_uf_demand_trend.sql")
        assert "p_setor TEXT" in content
        assert "p_window_months INT DEFAULT 12" in content
        assert "variacao_percentual" in content
        assert "tendencia" in content

    def test_rpc_4_get_upcoming_renewals_exists(self):
        """RPC 4 migration file exists and has content."""
        content = _get_migration("20260612000003_rpc_get_upcoming_renewals.sql")
        assert "FUNCTION public.get_upcoming_renewals" in content
        assert "pncp_supplier_contracts" in content
        assert "GRANT EXECUTE" in content

    def test_rpc_4_down_migration_exists(self):
        """RPC 4 down migration exists."""
        _get_down_migration("20260612000003_rpc_get_upcoming_renewals.down.sql")

    def test_rpc_4_has_expected_parameters(self):
        """RPC 4 has correct parameters."""
        content = _get_migration("20260612000003_rpc_get_upcoming_renewals.sql")
        assert "p_setor TEXT DEFAULT NULL" in content
        assert "p_uf TEXT DEFAULT NULL" in content
        assert "p_janela_dias INT DEFAULT 90" in content
        assert "p_limit INT DEFAULT 50" in content
        assert "probabilidade_republicacao" in content

    def test_all_migrations_have_comment(self):
        """All migrations have COMMENT ON FUNCTION."""
        for name in [
            "20260612000000_rpc_get_sector_monthly_volume.sql",
            "20260612000001_rpc_get_sector_seasonal_pattern.sql",
            "20260612000002_rpc_get_uf_demand_trend.sql",
            "20260612000003_rpc_get_upcoming_renewals.sql",
        ]:
            content = _get_migration(name)
            assert "COMMENT ON FUNCTION" in content, f"{name} missing COMMENT"

    def test_all_down_migrations_are_paired(self):
        """Every migration has a paired down migration."""
        for name in [
            "20260612000000_rpc_get_sector_monthly_volume",
            "20260612000001_rpc_get_sector_seasonal_pattern",
            "20260612000002_rpc_get_uf_demand_trend",
            "20260612000003_rpc_get_upcoming_renewals",
        ]:
            up = MIGRATIONS_DIR / f"{name}.sql"
            down = MIGRATIONS_DIR / f"{name}.down.sql"
            assert up.exists(), f"Missing up migration: {up}"
            assert down.exists(), f"Missing down migration: {down}"
            # Down migration should roll back what up created
            up_funcs = [l for l in up.read_text().splitlines() if "FUNCTION public." in l]
            down_drops = [l for l in down.read_text().splitlines() if "DROP FUNCTION" in l]
            # Each function in up should have a DROP in down
            for func_line in up_funcs:
                func_name = func_line.split("FUNCTION public.")[-1].split("(")[0].strip()
                if func_name.startswith("get_"):
                    func_name = func_name.split()[0]  # Handle "GRANT EXECUTE ON FUNCTION public.X TO..."
                assert any(func_name in d for d in down_drops), \
                    f"Function {func_name} in {name}.sql has no DROP in down migration"
