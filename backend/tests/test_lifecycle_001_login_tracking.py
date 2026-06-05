"""Tests for LIFECYCLE-001 (#1426): login tracking migration + Pydantic schema.

Validates:
  1. Migration SQL contract (columns, table, index, RLS, grants)
  2. Down migration reverses everything properly
  3. UserProfileResponse includes last_login_at and login_count fields

These tests are purely static/contract validation — they do NOT connect to
a live database.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

import pytest
from pydantic import ValidationError

# Paths relative to repo root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIGRATIONS_DIR = os.path.join(REPO_ROOT, "supabase", "migrations")

MIGRATION_FILE = "20260604135553_add_login_tracking.sql"
DOWN_FILE = "20260604135553_add_login_tracking.down.sql"

# Expected columns for profiles additions
PROFILES_NEW_COLUMNS = ["last_login_at", "login_count"]

# Expected columns for login_activity
LOGIN_ACTIVITY_COLUMNS = ["id", "user_id", "logged_in_at"]

# Policy names
POLICY_NAMES = [
    "login_activity_select_own",
    "login_activity_service_select",
    "login_activity_service_insert",
    "login_activity_service_update",
    "login_activity_service_delete",
]

# Down policy names (for down migration)
DOWN_POLICY_NAMES = [
    "login_activity_select_own",
    "login_activity_service_select",
    "login_activity_service_insert",
    "login_activity_service_update",
    "login_activity_service_delete",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_migration(filename: str) -> str:
    """Load a migration file from supabase/migrations/."""
    path = os.path.join(MIGRATIONS_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Migration file not found: {path}")
    with open(path, encoding="utf-8") as f:
        return f.read()


def _assert_sql_contains(sql: str, pattern: str) -> None:
    """Assert that the SQL contains a specific pattern (case-insensitive)."""
    assert re.search(pattern, sql, re.IGNORECASE), (
        f"Expected pattern not found in SQL: {pattern}"
    )


def _assert_sql_not_contains(sql: str, pattern: str) -> None:
    """Assert that the SQL does NOT contain a specific pattern."""
    assert not re.search(pattern, sql, re.IGNORECASE), (
        f"Unexpected pattern found in SQL: {pattern}"
    )


# ---------------------------------------------------------------------------
# Migration Contract Tests
# ---------------------------------------------------------------------------


class TestMigrationContract:
    """Validates the migration SQL contract: file existence, columns, RLS, etc."""

    def test_migration_file_exists(self):
        """Up migration file must exist."""
        path = os.path.join(MIGRATIONS_DIR, MIGRATION_FILE)
        assert os.path.exists(path), f"Missing up migration: {MIGRATION_FILE}"

    def test_down_file_exists(self):
        """Down migration file must exist (STORY-6.2 paired requirement)."""
        path = os.path.join(MIGRATIONS_DIR, DOWN_FILE)
        assert os.path.exists(path), f"Missing down migration: {DOWN_FILE}"

    def test_profiles_add_last_login_at(self):
        """Migration must add last_login_at column to profiles."""
        sql = _load_migration(MIGRATION_FILE)
        expected = "ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ"
        _assert_sql_contains(sql, expected)

    def test_profiles_add_login_count(self):
        """Migration must add login_count column to profiles with DEFAULT 0."""
        sql = _load_migration(MIGRATION_FILE)
        expected = "ADD COLUMN IF NOT EXISTS login_count INTEGER NOT NULL DEFAULT 0"
        _assert_sql_contains(sql, expected)

    def test_login_activity_table_created(self):
        """Migration must create login_activity table."""
        sql = _load_migration(MIGRATION_FILE)
        expected = "CREATE TABLE IF NOT EXISTS public.login_activity"
        _assert_sql_contains(sql, expected)

    def test_login_activity_all_columns(self):
        """login_activity must have all expected columns."""
        sql = _load_migration(MIGRATION_FILE)
        for col in LOGIN_ACTIVITY_COLUMNS:
            assert col in sql, f"Column '{col}' not found in login_activity table"

    def test_login_activity_user_id_fk(self):
        """login_activity.user_id must reference profiles(id) ON DELETE CASCADE."""
        sql = _load_migration(MIGRATION_FILE)
        expected = r"REFERENCES\s+public\.profiles\(\s*id\s*\)\s+ON\s+DELETE\s+CASCADE"
        _assert_sql_contains(sql, expected)

    def test_login_activity_user_id_not_null(self):
        """login_activity.user_id must be NOT NULL."""
        sql = _load_migration(MIGRATION_FILE)
        _assert_sql_contains(sql, r"user_id\s+UUID\s+NOT\s+NULL")

    def test_login_activity_logged_in_at_not_null(self):
        """login_activity.logged_in_at must be NOT NULL with DEFAULT now()."""
        sql = _load_migration(MIGRATION_FILE)
        _assert_sql_contains(sql, r"logged_in_at\s+TIMESTAMPTZ\s+NOT\s+NULL\s+DEFAULT\s+now\(\)")

    def test_index_created(self):
        """Migration must create composite index on (user_id, logged_in_at)."""
        sql = _load_migration(MIGRATION_FILE)
        expected = r"CREATE INDEX IF NOT EXISTS idx_login_activity_user_date"
        _assert_sql_contains(sql, expected)
        expected = r"ON\s+public\.login_activity\s*\(\s*user_id\s*,\s*logged_in_at\s*\)"
        _assert_sql_contains(sql, expected)

    def test_rls_enabled(self):
        """Migration must enable RLS on login_activity."""
        sql = _load_migration(MIGRATION_FILE)
        expected = "ALTER TABLE public.login_activity ENABLE ROW LEVEL SECURITY"
        _assert_sql_contains(sql, expected)

    def test_rls_select_own_policy(self):
        """Migration must create SELECT policy for authenticated users."""
        sql = _load_migration(MIGRATION_FILE)
        _assert_sql_contains(sql, r"login_activity_select_own")
        _assert_sql_contains(sql, r"auth\.uid\(\)\s*=\s*user_id")

    def test_rls_service_policies(self):
        """Migration must create service_role policies for all operations."""
        sql = _load_migration(MIGRATION_FILE)
        _assert_sql_contains(sql, r"login_activity_service_select")
        _assert_sql_contains(sql, r"login_activity_service_insert")
        _assert_sql_contains(sql, r"login_activity_service_update")
        _assert_sql_contains(sql, r"login_activity_service_delete")

    def test_authenticated_grant(self):
        """Migration must grant SELECT to authenticated role."""
        sql = _load_migration(MIGRATION_FILE)
        expected = "GRANT SELECT ON public.login_activity TO authenticated"
        _assert_sql_contains(sql, expected)

    def test_service_role_grant(self):
        """Migration must grant ALL to service_role."""
        sql = _load_migration(MIGRATION_FILE)
        expected = "GRANT ALL ON public.login_activity TO service_role"
        _assert_sql_contains(sql, expected)

    def test_pgrst_notify(self):
        """Migration must notify PostgREST to reload schema."""
        sql = _load_migration(MIGRATION_FILE)
        _assert_sql_contains(sql, r"NOTIFY\s+pgrst,\s*'reload schema'")

    def test_begin_commit_wrapping(self):
        """Migration must use BEGIN/COMMIT wrapping."""
        sql = _load_migration(MIGRATION_FILE)
        assert "BEGIN;" in sql, "Migration must contain BEGIN;"
        assert "COMMIT;" in sql, "Migration must contain COMMIT;"

    def test_no_rpc_in_up(self):
        """Up migration should not create RPCs (not in scope of LIFECYCLE-001)."""
        sql = _load_migration(MIGRATION_FILE)
        _assert_sql_not_contains(sql, r"CREATE\s+(OR\s+REPLACE\s+)?FUNCTION")

    def test_comments_on_columns(self):
        """Migration must have COMMENT statements for the new columns and table."""
        sql = _load_migration(MIGRATION_FILE)
        _assert_sql_contains(sql, r"COMMENT ON COLUMN public.profiles.last_login_at")
        _assert_sql_contains(sql, r"COMMENT ON COLUMN public.profiles.login_count")
        _assert_sql_contains(sql, r"COMMENT ON COLUMN public.login_activity.user_id")
        _assert_sql_contains(sql, r"COMMENT ON COLUMN public.login_activity.logged_in_at")
        _assert_sql_contains(sql, r"COMMENT ON TABLE\s+public.login_activity")
        _assert_sql_contains(sql, r"COMMENT ON INDEX\s+public.idx_login_activity_user_date")


# ---------------------------------------------------------------------------
# Down Migration Tests
# ---------------------------------------------------------------------------


class TestDownMigration:
    """Validates the down migration reverses everything properly."""

    def test_down_begin_commit(self):
        """Down migration must use BEGIN/COMMIT wrapping."""
        sql = _load_migration(DOWN_FILE)
        assert "BEGIN;" in sql, "Down migration must contain BEGIN;"
        assert "COMMIT;" in sql, "Down migration must contain COMMIT;"

    def test_down_drops_rls_policies(self):
        """Down migration must drop all RLS policies."""
        sql = _load_migration(DOWN_FILE)
        for policy in DOWN_POLICY_NAMES:
            expected = f'DROP POLICY IF EXISTS "{policy}" ON public.login_activity'
            assert expected in sql, f"Missing DROP POLICY for '{policy}'"

    def test_down_drops_index(self):
        """Down migration must drop the composite index."""
        sql = _load_migration(DOWN_FILE)
        expected = "DROP INDEX IF EXISTS public.idx_login_activity_user_date"
        assert expected in sql, "Missing DROP INDEX statement"

    def test_down_drops_table(self):
        """Down migration must drop login_activity table with CASCADE."""
        sql = _load_migration(DOWN_FILE)
        expected = "DROP TABLE IF EXISTS public.login_activity CASCADE"
        assert expected in sql, "Missing DROP TABLE ... CASCADE statement"

    def test_down_revokes_grants(self):
        """Down migration must revoke grants."""
        sql = _load_migration(DOWN_FILE)
        _assert_sql_contains(sql, r"REVOKE ALL ON public.login_activity FROM authenticated")
        _assert_sql_contains(sql, r"REVOKE ALL ON public.login_activity FROM service_role")

    def test_down_drops_columns(self):
        """Down migration must drop last_login_at and login_count from profiles."""
        sql = _load_migration(DOWN_FILE)
        _assert_sql_contains(sql, r"DROP COLUMN IF EXISTS last_login_at")
        _assert_sql_contains(sql, r"DROP COLUMN IF EXISTS login_count")

    def test_down_pgrst_notify(self):
        """Down migration must notify PostgREST."""
        sql = _load_migration(DOWN_FILE)
        _assert_sql_contains(sql, r"NOTIFY\s+pgrst,\s*'reload schema'")

    def test_down_order_operations(self):
        """Down migration must drop policies before table, and table before columns."""
        sql = _load_migration(DOWN_FILE)
        policy_idx = sql.index("DROP POLICY")
        index_idx = sql.index("DROP INDEX")
        table_idx = sql.index("DROP TABLE")
        column_idx = sql.index("DROP COLUMN")
        assert policy_idx < table_idx, "Policies must be dropped before table"
        assert index_idx < table_idx, "Index must be dropped before table"
        assert table_idx < column_idx, "Table must be dropped before columns"


# ---------------------------------------------------------------------------
# Pydantic Schema Tests
# ---------------------------------------------------------------------------


class TestUserProfileResponseSchema:
    """Validates that UserProfileResponse includes login tracking fields."""

    def test_user_profile_response_has_last_login_at(self):
        """UserProfileResponse must have last_login_at field."""
        from schemas.user import UserProfileResponse

        assert "last_login_at" in UserProfileResponse.model_fields, (
            "UserProfileResponse missing 'last_login_at'"
        )
        field = UserProfileResponse.model_fields["last_login_at"]
        assert field.default is None, "last_login_at should default to None"

    def test_user_profile_response_has_login_count(self):
        """UserProfileResponse must have login_count field."""
        from schemas.user import UserProfileResponse

        assert "login_count" in UserProfileResponse.model_fields, (
            "UserProfileResponse missing 'login_count'"
        )
        field = UserProfileResponse.model_fields["login_count"]
        assert field.default == 0, "login_count should default to 0"
        assert field.annotation is int, "login_count should be int"

    def test_user_profile_response_login_count_ge_zero(self):
        """login_count must be >= 0 (ge=0 constraint)."""
        from schemas.user import UserProfileResponse

        json_schema = UserProfileResponse.model_json_schema()
        props = json_schema.get("properties", {})
        login_count_schema = props.get("login_count", {})
        assert login_count_schema.get("minimum", None) == 0, (
            "login_count should have minimum=0 in JSON schema"
        )

    def test_user_profile_response_login_count_validates_non_negative(self):
        """UserProfileResponse must raise ValidationError for negative login_count."""
        from schemas.user import UserProfileResponse

        with pytest.raises(ValidationError):
            UserProfileResponse(
                user_id="test-uuid",
                email="test@example.com",
                plan_id="consultor_agil",
                plan_name="Consultor Agil",
                capabilities={"max_history_days": 365},
                quota_used=0,
                quota_remaining=10,
                quota_reset_date="2026-07-01T00:00:00Z",
                subscription_status="active",
                login_count=-1,
            )

    def test_user_profile_response_partial_data(self):
        """UserProfileResponse should work without login tracking fields."""
        from schemas.user import UserProfileResponse

        profile = UserProfileResponse(
            user_id="test-uuid",
            email="test@example.com",
            plan_id="consultor_agil",
            plan_name="Consultor Agil",
            capabilities={"max_history_days": 365},
            quota_used=5,
            quota_remaining=5,
            quota_reset_date="2026-07-01T00:00:00Z",
            subscription_status="active",
        )
        assert profile.last_login_at is None, "last_login_at should default to None"
        assert profile.login_count == 0, "login_count should default to 0"

    def test_user_profile_response_with_login_data(self):
        """UserProfileResponse should accept login tracking fields."""
        from schemas.user import UserProfileResponse

        now = datetime.now()
        profile = UserProfileResponse(
            user_id="test-uuid",
            email="test@example.com",
            plan_id="consultor_agil",
            plan_name="Consultor Agil",
            capabilities={"max_history_days": 365},
            quota_used=5,
            quota_remaining=5,
            quota_reset_date="2026-07-01T00:00:00Z",
            subscription_status="active",
            last_login_at=now,
            login_count=42,
        )
        assert profile.last_login_at == now
        assert profile.login_count == 42

    def test_user_profile_response_json_serializable(self):
        """UserProfileResponse with login fields must be JSON-serializable."""
        from schemas.user import UserProfileResponse

        now = datetime.now()
        profile = UserProfileResponse(
            user_id="test-uuid",
            email="test@example.com",
            plan_id="consultor_agil",
            plan_name="Consultor Agil",
            capabilities={"max_history_days": 365},
            quota_used=5,
            quota_remaining=5,
            quota_reset_date="2026-07-01T00:00:00Z",
            subscription_status="active",
            last_login_at=now,
            login_count=42,
        )
        serialized = profile.model_dump(mode="json")
        assert serialized["login_count"] == 42
        assert serialized["last_login_at"] is not None
        assert isinstance(serialized["last_login_at"], str)
