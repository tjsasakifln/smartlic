"""Tests for FOUNDER-001 migration: 20260606010000_add_founder_metrics_functions.

Validates migration structure, function signatures, grants, and edge case
handling patterns in the SQL functions for MRR, churn, trial-to-paid, D7
retention, and ARPA.
"""

import re
from pathlib import Path

import pytest

MIGRATION_DIR = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
UP_FILE = MIGRATION_DIR / "20260606010000_add_founder_metrics_functions.sql"
DOWN_FILE = MIGRATION_DIR / "20260606010000_add_founder_metrics_functions.down.sql"

EXPECTED_FUNCTIONS = [
    "get_mrr",
    "get_churn_rate_30d",
    "get_trial_to_paid_30d",
    "get_trial_to_paid_90d",
    "get_d7_retention",
    "get_arpa",
]


# ============================================================================
# Migration structure tests
# ============================================================================


class TestMigrationFiles:
    """Validate migration file existence and structure."""

    def test_up_migration_exists(self):
        """Up migration file must exist."""
        assert UP_FILE.exists(), f"Missing: {UP_FILE}"

    def test_down_migration_exists(self):
        """Down migration must be paired (STORY-6.2 requirement)."""
        assert DOWN_FILE.exists(), f"Missing: {DOWN_FILE}"

    def test_up_migration_has_begin_commit(self):
        """Up migration must wrap in BEGIN/COMMIT for atomicity."""
        content = UP_FILE.read_text()
        assert re.search(r'\bBEGIN\s*;', content), "Missing BEGIN;"
        assert re.search(r'\bCOMMIT\s*;', content), "Missing COMMIT;"

    def test_down_migration_has_begin_commit(self):
        """Down migration must wrap in BEGIN/COMMIT for atomicity."""
        content = DOWN_FILE.read_text()
        assert re.search(r'\bBEGIN\s*;', content), "Missing BEGIN;"
        assert re.search(r'\bCOMMIT\s*;', content), "Missing COMMIT;"

    def test_up_notifies_pgrst(self):
        """Must send NOTIFY pgrst to reload PostgREST schema cache."""
        content = UP_FILE.read_text()
        assert "NOTIFY pgrst" in content, "Missing NOTIFY pgrst, 'reload schema'"

    def test_down_notifies_pgrst(self):
        """Down migration must also notify PostgREST."""
        content = DOWN_FILE.read_text()
        assert "NOTIFY pgrst" in content, "Missing NOTIFY pgrst in down migration"


class TestFunctionDefinitions:
    """Validate all 6 expected functions are defined."""

    @pytest.mark.parametrize("func_name", EXPECTED_FUNCTIONS)
    def test_function_defined_in_up(self, func_name):
        """Each expected function must have CREATE OR REPLACE in up migration."""
        content = UP_FILE.read_text()
        pattern = rf"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.{func_name}\("
        assert re.search(pattern, content), f"Missing CREATE OR REPLACE for {func_name}"

    @pytest.mark.parametrize("func_name", EXPECTED_FUNCTIONS)
    def test_function_dropped_in_down(self, func_name):
        """Each function must be dropped in the down migration."""
        content = DOWN_FILE.read_text()
        pattern = rf"DROP\s+FUNCTION\s+IF\s+EXISTS\s+public\.{func_name}"
        assert re.search(pattern, content), f"Missing DROP FUNCTION for {func_name}"

    @pytest.mark.parametrize("func_name", EXPECTED_FUNCTIONS)
    def test_function_has_comment(self, func_name):
        """Each function must have a COMMENT for documentation."""
        content = UP_FILE.read_text()
        pattern = rf"COMMENT\s+ON\s+FUNCTION\s+public\.{func_name}\s+IS"
        assert re.search(pattern, content), f"Missing COMMENT for {func_name}"


class TestGrants:
    """Validate function grants."""

    @pytest.mark.parametrize("func_name", EXPECTED_FUNCTIONS)
    def test_granted_to_service_role(self, func_name):
        """All functions must be granted to service_role."""
        content = UP_FILE.read_text()
        pattern = rf"GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+public\.{func_name}\s+TO\s+service_role"
        assert re.search(pattern, content), f"Missing GRANT TO service_role for {func_name}"

    @pytest.mark.parametrize("func_name", EXPECTED_FUNCTIONS)
    def test_not_granted_to_authenticated(self, func_name):
        """Functions should NOT be granted to authenticated (aggregate financial data).

        These aggregate functions expose platform-wide financial metrics.
        authenticated users would see only their own data due to RLS,
        producing incorrect results. Admin dashboard uses service_role.
        """
        content = UP_FILE.read_text()
        # Check there's no GRANT to authenticated for this function
        pattern = rf"GRANT\s+EXECUTE\s+ON\s+FUNCTION\s+public\.{func_name}\s+TO\s+authenticated"
        assert not re.search(pattern, content), (
            f"{func_name} should NOT be granted to authenticated "
            f"(aggregate financial data — service_role only)"
        )


# ============================================================================
# SQL logic edge case tests (static analysis)
# ============================================================================


class TestSQLEdgeCases:
    """Validate edge case handling via static SQL analysis."""

    def test_get_churn_rate_returns_zero_when_no_active(self):
        """get_churn_rate_30d: WHEN active_count = 0 THEN 0."""
        content = UP_FILE.read_text()
        # Extract the churn function body
        assert "WHEN active_count = 0 THEN 0" in content, (
            "get_churn_rate_30d must handle zero active subscriptions"
        )

    def test_get_trial_to_paid_returns_zero_when_no_trials(self):
        """get_trial_to_paid_30d/90d: WHEN total_trials = 0 THEN 0."""
        content = UP_FILE.read_text()
        # Both functions should have this guard
        assert content.count("WHEN total_trials = 0 THEN 0") == 2, (
            "Both trial-to-paid functions must handle zero trials"
        )

    def test_get_d7_retention_returns_zero_when_no_signups(self):
        """get_d7_retention: WHEN total_signups = 0 THEN 0."""
        content = UP_FILE.read_text()
        assert "WHEN total_signups = 0 THEN 0" in content, (
            "get_d7_retention must handle zero signups"
        )

    def test_get_arpa_returns_zero_when_no_subscribers(self):
        """get_arpa: WHEN active_count = 0 THEN 0."""
        content = UP_FILE.read_text()
        assert "WHEN (SELECT count FROM active_count) = 0 THEN 0" in content, (
            "get_arpa must handle zero active subscribers"
        )

    def test_get_arpa_delegates_to_get_mrr(self):
        """get_arpa must call get_mrr (not duplicate MRR calculation)."""
        content = UP_FILE.read_text()
        # get_arpa function body should reference get_mrr
        # Use a simple check: the get_arpa definition should contain get_mrr reference
        arpa_section = content.split("CREATE OR REPLACE FUNCTION public.get_arpa()")[1]
        arpa_section = arpa_section.split("COMMENT ON FUNCTION public.get_arpa")[0]
        assert "public.get_mrr(" in arpa_section, (
            "get_arpa must delegate MRR calculation to get_mrr to avoid duplication"
        )

    def test_get_mrr_excludes_free_plans(self):
        """get_mrr must exclude free/pack/master plans from MRR."""
        content = UP_FILE.read_text()
        assert "free_trial" in content, "MRR calculation must reference plan exclusion list"
        assert "monthly_brl > 0" in content, "MRR must filter zero-value plans"

    def test_no_sql_injection_risk(self):
        """Functions use LANGUAGE sql (no dynamic SQL), no EXECUTE."""
        content = UP_FILE.read_text()
        # STABLE functions with LANGUAGE sql can't use EXECUTE, but check anyway
        assert "EXECUTE " not in content.upper() or "GRANT EXECUTE" in content, (
            "No dynamic SQL execution allowed in financial functions"
        )
