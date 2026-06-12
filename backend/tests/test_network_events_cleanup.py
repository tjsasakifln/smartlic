"""Tests for NETINT-007 — network_events cleanup ARQ cron job (Issue #1677).

Validates:
  - Migration file structure (UP + DOWN)
  - Job logic (aggregation, prune, error isolation)
  - Config defaults
  - Edge cases (empty table, no records to prune, error isolation)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

MIGRATION_TIMESTAMP = "20260612100000"
UP_FILE = f"{MIGRATION_TIMESTAMP}_network_events_agg_weekly.sql"
DOWN_FILE = f"{MIGRATION_TIMESTAMP}_network_events_agg_weekly.down.sql"


def load_migration(filename: str) -> str:
    """Load a migration SQL file from the supabase migrations directory."""
    path = MIGRATIONS_DIR / filename
    assert path.exists(), f"Migration not found: {path}"
    return path.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# Migration Structure Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMigrationFileStructure:
    """AC: Migration files exist and have correct structure."""

    def test_up_migration_exists(self):
        """UP migration file must exist."""
        assert (MIGRATIONS_DIR / UP_FILE).exists()
        assert (MIGRATIONS_DIR / UP_FILE).stat().st_size > 0

    def test_down_migration_exists(self):
        """DOWN migration file must exist."""
        assert (MIGRATIONS_DIR / DOWN_FILE).exists()
        assert (MIGRATIONS_DIR / DOWN_FILE).stat().st_size > 0

    def test_up_contains_begin_commit(self):
        """UP migration is wrapped in BEGIN / COMMIT."""
        sql = load_migration(UP_FILE)
        assert "BEGIN;" in sql
        assert sql.strip().endswith("COMMIT;")

    def test_up_creates_weekly_table(self):
        """UP migration creates network_events_agg_weekly."""
        sql = load_migration(UP_FILE)
        assert "CREATE TABLE IF NOT EXISTS public.network_events_agg_weekly" in sql

    def test_up_has_unique_constraint(self):
        sql = load_migration(UP_FILE)
        assert "network_events_agg_weekly_unique" in sql

    def test_down_drops_table(self):
        sql = load_migration(DOWN_FILE)
        assert "DROP TABLE IF EXISTS public.network_events_agg_weekly" in sql

    def test_down_drops_policies(self):
        sql = load_migration(DOWN_FILE)
        assert "DROP POLICY IF EXISTS" in sql


# ═══════════════════════════════════════════════════════════════════════════
# Config defaults
# ═══════════════════════════════════════════════════════════════════════════


class TestCleanupConfig:
    """AC: Config defaults are reasonable for production."""

    def test_retention_days_default(self):
        import config.features as f
        assert f.NETWORK_EVENTS_RETENTION_DAYS == 365

    def test_agg_window_days_default(self):
        import config.features as f
        assert f.NETWORK_EVENTS_AGG_WINDOW_DAYS == 7

    def test_weekly_retention_days_default(self):
        import config.features as f
        assert f.NETWORK_EVENTS_WEEKLY_RETENTION_DAYS == 730

    def test_cleanup_hour_default(self):
        import config.features as f
        assert f.NETWORK_EVENTS_CLEANUP_HOUR == 3

    def test_cleanup_enabled_default(self):
        import config.features as f
        assert f.NETWORK_EVENTS_CLEANUP_ENABLED is True


# ═══════════════════════════════════════════════════════════════════════════
# Job logic tests
# ═══════════════════════════════════════════════════════════════════════════


def _make_async_exec(data_val=None, exception=None):
    """Return a chain MagicMock with an async execute() method."""
    chain = MagicMock()
    exec_fn = AsyncMock()
    resp = MagicMock()
    resp.data = data_val
    exec_fn.return_value = resp
    if exception:
        exec_fn.side_effect = exception
    chain.execute = exec_fn
    # Support chaining like .lt().gt() etc
    chain.select = MagicMock(return_value=chain)
    chain.lt = MagicMock(return_value=chain)
    chain.delete = MagicMock(return_value=chain)
    chain.upsert = MagicMock(return_value=chain)
    chain.order = MagicMock(return_value=chain)
    chain.limit = MagicMock(return_value=chain)
    chain.eq = MagicMock(return_value=chain)
    chain.gte = MagicMock(return_value=chain)
    return chain


def _make_db_mock():
    """Create a mock Supabase client with async-capable table methods."""
    db = MagicMock()

    def _table_side_effect(name):
        chain = _make_async_exec(data_val=[])
        return chain

    db.table.side_effect = _table_side_effect
    return db


class TestCleanupJob:
    """AC: Job handles various states correctly."""

    @patch("jobs.cron.network_events_cleanup.get_supabase")
    async def test_empty_table_no_error(self, mock_get_supabase):
        """AC: Job does not fail on empty table."""
        db = _make_db_mock()
        db.table.return_value.execute = AsyncMock(return_value=MagicMock(data=[]))
        mock_get_supabase.return_value = db

        from jobs.cron.network_events_cleanup import aggregate_and_cleanup_network_events
        result = await aggregate_and_cleanup_network_events({})

        assert result["weekly_aggregated"] == 0
        assert result["daily_pruned"] == 0
        assert result["weekly_pruned"] == 0
        assert result["error"] is None

    @patch("jobs.cron.network_events_cleanup.get_supabase")
    @patch.dict("os.environ", {"NETWORK_EVENTS_CLEANUP_ENABLED": "false"}, clear=False)
    async def test_disabled_via_config(self, mock_get_supabase):
        """AC: Job is a no-op when disabled."""
        from jobs.cron.network_events_cleanup import aggregate_and_cleanup_network_events
        result = await aggregate_and_cleanup_network_events({})

        assert result["error"] is None
        assert result["weekly_aggregated"] == 0
        mock_get_supabase.assert_not_called()

    @patch("jobs.cron.network_events_cleanup.get_supabase")
    async def test_error_isolation_step1_fails_step2_runs(self, mock_get_supabase):
        """AC: Error in step 1 does not block step 2."""
        db = MagicMock()

        # Step 1 select throws
        chain1 = _make_async_exec(exception=Exception("DB error"))
        # Step 2 delete succeeds
        chain2 = _make_async_exec(data_val=[{"id": "1"}], exception=None)

        call_count = [0]

        def _table_side(name):
            c = call_count[0]
            call_count[0] += 1
            if c == 0:
                return chain1  # select for aggregation (fails)
            return chain2  # delete (succeeds)

        db.table.side_effect = _table_side
        mock_get_supabase.return_value = db

        from jobs.cron.network_events_cleanup import aggregate_and_cleanup_network_events
        result = await aggregate_and_cleanup_network_events({})

        assert result["weekly_aggregated"] == 0
        assert result["error"] is not None
        assert "Weekly aggregation failed" in result["error"]
        # prune still happened
        assert result["daily_pruned"] == 1
