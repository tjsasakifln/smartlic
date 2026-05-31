"""Tests for NETINT-002 — RPC network_sector_migration (Issue #1284).

Validates the migration SQL through static analysis:
  - Migration file structure (UP + DOWN)
  - RPC function signature, security attributes, and grants
  - Column addition (setor_classificado)
  - CTE structure (baseline_sectors, active_cnpjs, window_contracts, new_entrants)
  - Output JSON shape
  - Input validation
  - Edge cases: crescimento_percentual >= 0, empty tendencias

No live DB connection needed. Follows the pattern from test_debt03_rpc_security_audit.py.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

MIGRATION_TIMESTAMP = "20260531200000"
UP_FILE = f"{MIGRATION_TIMESTAMP}_network_sector_migration.sql"
DOWN_FILE = f"{MIGRATION_TIMESTAMP}_network_sector_migration.down.sql"


def load_migration(filename: str) -> str:
    """Load a migration SQL file from the supabase migrations directory."""
    path = MIGRATIONS_DIR / filename
    assert path.exists(), f"Migration not found: {path}"
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# AC: File Structure
# ═══════════════════════════════════════════════════════════════════════════


class TestMigrationFileStructure:
    """AC: Migration files exist and have correct structure."""

    def test_up_migration_exists(self):
        """UP migration file must exist."""
        assert (MIGRATIONS_DIR / UP_FILE).exists(), (
            f"UP migration file {UP_FILE} not found"
        )

    def test_down_migration_exists(self):
        """DOWN migration file must exist."""
        assert (MIGRATIONS_DIR / DOWN_FILE).exists(), (
            f"DOWN migration file {DOWN_FILE} not found"
        )

    def test_up_contains_begin_commit(self):
        """UP migration is wrapped in BEGIN / COMMIT (comments precede BEGIN)."""
        sql = load_migration(UP_FILE)
        assert "BEGIN;" in sql
        assert sql.strip().endswith("COMMIT;")

    def test_down_removes_rpc_without_error(self):
        """DOWN migration drops the function using IF EXISTS."""
        sql = load_migration(DOWN_FILE)
        assert "DROP FUNCTION IF EXISTS public.network_sector_migration" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Column Addition
# ═══════════════════════════════════════════════════════════════════════════


class TestColumnAddition:
    """AC: setor_classificado column is added to pncp_supplier_contracts."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_adds_setor_classificado_column(self, sql):
        """Migration adds setor_classificado TEXT column."""
        assert "ADD COLUMN IF NOT EXISTS setor_classificado TEXT" in sql

    def test_column_is_nullable(self, sql):
        """Column is nullable — no NOT NULL constraint."""
        assert "setor_classificado TEXT" in sql
        # Verify we don't impose NOT NULL on the new column
        add_stmt = sql[sql.find("ADD COLUMN"):sql.find("ADD COLUMN") + 200]
        assert "NOT NULL" not in add_stmt, (
            "setor_classificado must be nullable (backfill from external pipeline)"
        )

    def test_has_composite_index(self, sql):
        """Migration creates a composite index on (setor_classificado, data_assinatura DESC)."""
        assert "CREATE INDEX IF NOT EXISTS idx_psc_setor_data" in sql
        assert "setor_classificado, data_assinatura DESC" in sql

    def test_index_is_partial(self, sql):
        """Index is partial: WHERE setor_classificado IS NOT NULL AND is_active = TRUE."""
        assert "WHERE setor_classificado IS NOT NULL AND is_active = TRUE" in sql

    def test_has_column_comment(self, sql):
        """Column has a descriptive COMMENT."""
        assert "COMMENT ON COLUMN" in sql
        assert "setor_classificado" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Function Signature
# ═══════════════════════════════════════════════════════════════════════════


class TestFunctionSignature:
    """AC: RPC function has correct signature and security attributes."""

    FUNCTION_NAME = "public.network_sector_migration"

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def _function_block(self, sql: str) -> str:
        """Extract the function definition block."""
        start = sql.find(f"CREATE OR REPLACE FUNCTION {self.FUNCTION_NAME}")
        assert start >= 0, "Function definition not found"
        end = sql.find("$$;", start)
        assert end >= 0, "Function body end not found"
        return sql[start:end + 3]

    def test_creates_or_replaces_function(self, sql):
        """Uses CREATE OR REPLACE FUNCTION."""
        assert f"CREATE OR REPLACE FUNCTION {self.FUNCTION_NAME}" in sql

    def test_returns_json(self, sql):
        """Returns JSON type (not JSONB)."""
        assert "RETURNS JSON" in sql

    def test_language_plpgsql(self, sql):
        """Uses LANGUAGE plpgsql for procedural logic."""
        assert "LANGUAGE plpgsql" in sql

    def test_stable_volatility(self, sql):
        """Declared STABLE (read-only, no transaction impact)."""
        assert "STABLE" in sql

    def test_security_definer(self, sql):
        """Uses SECURITY DEFINER (runs with owner privileges)."""
        assert "SECURITY DEFINER" in sql

    def test_search_path_sanitized(self, sql):
        """Sets search_path to public, pg_temp (SEC-SECDEF-001/002)."""
        assert "SET search_path = public, pg_temp" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Input Parameters
# ═══════════════════════════════════════════════════════════════════════════


class TestInputParameters:
    """AC: RPC accepts correct input parameters with defaults."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_accepts_p_setor(self, sql):
        """Accepts optional p_setor TEXT with NULL default."""
        assert "p_setor TEXT DEFAULT NULL" in sql

    def test_accepts_p_uf(self, sql):
        """Accepts optional p_uf VARCHAR with NULL default."""
        assert "p_uf VARCHAR(2) DEFAULT NULL" in sql

    def test_accepts_p_meses(self, sql):
        """Accepts p_meses INT with default 12."""
        assert "p_meses INT DEFAULT 12" in sql

    def test_validates_p_meses_range(self, sql):
        """Validates p_meses is between 1 and 24."""
        assert "p_meses < 1 OR p_meses > 24" in sql
        assert "RAISE EXCEPTION" in sql

    def test_validates_p_uf_format(self, sql):
        """Validates p_uf is a 2-letter state code."""
        assert "!~ '^[A-Z]{2}$'" in sql or "~ '^[A-Z]{2}$'" in sql

    def test_rejects_empty_p_setor(self, sql):
        """Rejects empty p_setor string."""
        assert "p_setor cannot be empty" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: CTE Structure
# ═══════════════════════════════════════════════════════════════════════════


class TestCTEStructure:
    """AC: RPC uses CTEs for baseline-vs-window comparison."""

    REQUIRED_CTES = [
        "baseline_sectors",
        "active_cnpjs",
        "window_contracts",
        "new_entrants",
        "historical",
        "tendencias_agg",
    ]

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_uses_with_clause(self, sql):
        """Query uses WITH (CTE) clause."""
        assert "WITH" in sql

    def test_all_required_ctes_present(self, sql):
        """All required CTEs (baseline_sectors, active_cnpjs, window_contracts,
        new_entrants, historical, tendencias_agg) are defined."""
        for cte in self.REQUIRED_CTES:
            assert cte in sql, f"Required CTE '{cte}' not found in function body"

    def test_baseline_filters_date_before_window(self, sql):
        """Baseline excludes the analysis window (data_assinatura < v_window_start)."""
        assert "data_assinatura < v_window_start" in sql

    def test_window_filters_current_period(self, sql):
        """Window includes only data_assinatura >= v_window_start."""
        assert "data_assinatura >= v_window_start" in sql

    def test_new_entrant_not_exists_in_baseline(self, sql):
        """New entrant detection uses NOT EXISTS against baseline_sectors."""
        assert "NOT EXISTS" in sql
        assert "baseline_sectors" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Grants
# ═══════════════════════════════════════════════════════════════════════════


class TestGrants:
    """AC: GRANT EXECUTE to anon, authenticated, service_role."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_grant_to_anon(self, sql):
        """GRANT EXECUTE to anon."""
        assert "GRANT EXECUTE ON FUNCTION public.network_sector_migration" in sql
        assert "TO anon" in sql

    def test_grant_to_authenticated(self, sql):
        """GRANT EXECUTE to authenticated."""
        assert "GRANT EXECUTE ON FUNCTION public.network_sector_migration" in sql
        assert "TO authenticated" in sql

    def test_grant_to_service_role(self, sql):
        """GRANT EXECUTE to service_role."""
        assert "GRANT EXECUTE ON FUNCTION public.network_sector_migration" in sql
        assert "TO service_role" in sql

    def test_all_three_grants_present(self, sql):
        """All three GRANT statements are present."""
        count = sql.count("GRANT EXECUTE ON FUNCTION public.network_sector_migration")
        assert count == 3, f"Expected 3 GRANTs, found {count}"


# ═══════════════════════════════════════════════════════════════════════════
# AC: Output JSON Structure
# ═══════════════════════════════════════════════════════════════════════════


class TestOutputJSON:
    """AC: Output JSON has correct structure with all required fields."""

    REQUIRED_FIELDS = [
        "setor_referencia",
        "tendencias",
        "stats",
    ]
    TREND_FIELDS = [
        "setor_destino",
        "novos_entrantes",
        "crescimento_percentual",
        "ufs_principais",
        "ticket_medio_setor_destino",
        "sinal",
    ]
    STATS_FIELDS = [
        "periodo_analise",
        "total_migracoes_detectadas",
        "setores_mais_quentes",
    ]

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_root_fields(self, sql):
        """JSON root has setor_referencia, tendencias, stats."""
        for field in self.REQUIRED_FIELDS:
            assert field in sql, f"Required root field '{field}' not found"

    def test_trend_fields(self, sql):
        """Each trend entry has all required sub-fields."""
        for field in self.TREND_FIELDS:
            assert field in sql, f"Required trend field '{field}' not found"

    def test_stats_fields(self, sql):
        """Stats block has all required sub-fields."""
        for field in self.STATS_FIELDS:
            assert field in sql, f"Required stats field '{field}' not found"

    def test_uses_json_build_object(self, sql):
        """Uses JSON_BUILD_OBJECT (not jsonb_build_object) since RETURNS JSON."""
        assert "JSON_BUILD_OBJECT" in sql

    def test_tendencias_empty_array_fallback(self, sql):
        """Empty tendencias returns [] not NULL."""
        assert "'[]'::JSON" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Business Logic Constraints
# ═══════════════════════════════════════════════════════════════════════════


class TestBusinessLogic:
    """AC: Business logic invariants."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_crescimento_percentual_never_negative(self, sql):
        """crescimento_percentual uses CASE with ELSE 0 — never negative."""
        assert "CASE" in sql
        assert "WHEN t.total_historicos > 0" in sql
        assert "ELSE 0" in sql

    def test_sinal_logic_exists(self, sql):
        """sinal is calculated as 'alta' (>10%) or 'estavel' (<=10%)."""
        assert "sinal" in sql
        assert "'alta'" in sql
        assert "'estavel'" in sql

    def test_uses_coalesce_for_empty_data(self, sql):
        """COALESCE wraps JSON_AGG to handle empty result sets."""
        assert "COALESCE(" in sql

    def test_excludes_reference_sector_from_tendencias(self, sql):
        """When p_setor provided, reference sector is excluded from tendencias."""
        assert "t.sector_id <> p_setor" in sql or "sector_id <> p_setor" in sql

    def test_statement_timeout_set(self, sql):
        """Sets LOCAL statement_timeout = '15s' for defense."""
        assert "SET LOCAL statement_timeout = '15s'" in sql

    def test_filter_is_active(self, sql):
        """All queries filter by is_active = TRUE."""
        count = sql.count("is_active = TRUE")
        assert count >= 3, (
            f"Expected is_active = TRUE in at least 3 CTEs, found {count}"
        )

    def test_baseline_span_24_months(self, sql):
        """Baseline starts from 24 months before today."""
        assert "INTERVAL '24 months'" in sql


# ═══════════════════════════════════════════════════════════════════════════
# AC: Edge Cases
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """AC: Edge cases handled correctly.

    Validated through static analysis of SQL patterns.
    """

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_no_setor_classificado_returns_empty(self, sql):
        """When no setor_classificado data exists, tendencias is empty array.
        Verified by COALESCE + '[]'::JSON pattern."""
        assert "'[]'::JSON" in sql

    def test_uf_filter_optional(self, sql):
        """UF filter is applied only when provided (v_uf_clean IS NULL OR)."""
        assert "v_uf_clean IS NULL OR uf = v_uf_clean" in sql

    def test_window_start_dynamic(self, sql):
        """Analysis window is calculated from p_meses parameter."""
        assert "v_window_start" in sql

    def test_total_migracoes_is_sum(self, sql):
        """total_migracoes_detectadas is SUM of novos_entrantes across sectors."""
        block = sql[sql.find("total_migracoes_detectadas"):
                    sql.find("total_migracoes_detectadas") + 200]
        assert "SUM" in block

    def test_setores_mais_quentes_limited_to_3(self, sql):
        """setores_mais_quentes is limited to top 3."""
        assert "LIMIT 3" in sql

    def test_ufs_principais_limited_to_3(self, sql):
        """ufs_principais within each trend is limited to top 3."""
        # Count LIMIT 3 occurrences — at least one for ufs_principais + setores_mais_quentes
        assert sql.count("LIMIT 3") >= 2


# ═══════════════════════════════════════════════════════════════════════════
# AC: Sanity — No raw CNPJ exposure
# ═══════════════════════════════════════════════════════════════════════════


class TestPrivacy:
    """AC: Output is aggregated — never exposes individual CNPJ."""

    @pytest.fixture(scope="class")
    def sql(self):
        return load_migration(UP_FILE)

    def test_no_ni_fornecedor_in_output(self, sql):
        """The output JSON does not include individual CNPJ (ni_fornecedor) fields."""
        # Check the JSON_BUILD_OBJECT calls for all fields
        json_builds = re.findall(r"JSON_BUILD_OBJECT\s*\((.*?)\)", sql, re.DOTALL)
        for jbo in json_builds:
            assert "ni_fornecedor" not in jbo, (
                f"Output JSON contains individual ni_fornecedor: {jbo[:100]}..."
            )

    def test_aggregated_counts_only(self, sql):
        """Output uses COUNT(DISTINCT), SUM, AVG — never raw rows."""
        assert "COUNT(DISTINCT" in sql
        assert "SUM" in sql
        assert "AVG" in sql
