"""Tests for backend/roles.py — admin role definitions and env-based resolution.

#1778: Granular admin roles — role definitions, MASTER_USER_IDS parsing,
ADMIN_ROLES parsing, and legacy ADMIN_USER_IDS fallback.
"""

from roles import (
    AdminRole,
    get_master_ids,
    parse_admin_roles,
    get_legacy_admin_ids,
    get_user_roles_from_env,
)


UUID_M = "550e8400-e29b-41d4-a716-446655440000"  # master
UUID_A = "550e8400-e29b-41d4-a716-446655440001"  # admin (dashboard)
UUID_B = "550e8400-e29b-41d4-a716-446655440002"  # admin (user_manager, billing)
UUID_C = "550e8400-e29b-41d4-a716-446655440003"  # regular user


class TestAdminRole:
    """AdminRole enum has correct values."""

    def test_roles_defined(self):
        """All five roles are defined."""
        assert AdminRole.DASHBOARD.value == "dashboard"
        assert AdminRole.USER_MANAGER.value == "user_manager"
        assert AdminRole.BILLING.value == "billing"
        assert AdminRole.DATA_ACCESS.value == "data_access"
        assert AdminRole.MASTER.value == "master"


class TestGetMasterIds:
    """MASTER_USER_IDS env var parsing."""

    def test_empty_env_returns_empty(self, monkeypatch):
        monkeypatch.setenv("MASTER_USER_IDS", "")
        assert get_master_ids() == set()

    def test_single_valid_uuid(self, monkeypatch):
        monkeypatch.setenv("MASTER_USER_IDS", UUID_M)
        assert get_master_ids() == {UUID_M}

    def test_multiple_uuids(self, monkeypatch):
        monkeypatch.setenv("MASTER_USER_IDS", f"{UUID_M},{UUID_A}")
        assert get_master_ids() == {UUID_M, UUID_A}

    def test_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("MASTER_USER_IDS", f"  {UUID_M}  ,  {UUID_A}  ")
        assert get_master_ids() == {UUID_M, UUID_A}

    def test_invalid_uuid_rejected(self, monkeypatch):
        monkeypatch.setenv("MASTER_USER_IDS", "not-a-uuid,admin-user-123")
        assert get_master_ids() == set()

    def test_mixed_valid_and_invalid(self, monkeypatch):
        monkeypatch.setenv("MASTER_USER_IDS", f"invalid,{UUID_M},bad")
        assert get_master_ids() == {UUID_M}

    def test_missing_env(self, monkeypatch):
        monkeypatch.delenv("MASTER_USER_IDS", raising=False)
        assert get_master_ids() == set()


class TestParseAdminRoles:
    """ADMIN_ROLES env var parsing."""

    def test_empty_env_returns_empty(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ROLES", "")
        assert parse_admin_roles() == {}

    def test_single_user_single_role(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_A}:dashboard")
        result = parse_admin_roles()
        assert result == {UUID_A: {"dashboard"}}

    def test_single_user_multiple_roles(self, monkeypatch):
        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_A}:dashboard,user_manager")
        result = parse_admin_roles()
        assert result == {UUID_A: {"dashboard", "user_manager"}}

    def test_multiple_users(self, monkeypatch):
        monkeypatch.setenv(
            "ADMIN_ROLES",
            f"{UUID_A}:dashboard,user_manager;{UUID_B}:data_access,billing",
        )
        result = parse_admin_roles()
        assert result[UUID_A] == {"dashboard", "user_manager"}
        assert result[UUID_B] == {"data_access", "billing"}

    def test_unknown_role_skipped(self, monkeypatch, caplog):
        caplog.set_level("WARNING")
        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_A}:dashboard,super_admin")
        result = parse_admin_roles()
        assert result == {UUID_A: {"dashboard"}}
        assert any("Unknown role" in r.message for r in caplog.records)

    def test_invalid_uuid_skipped(self, monkeypatch, caplog):
        caplog.set_level("WARNING")
        monkeypatch.setenv("ADMIN_ROLES", f"invalid:data_access;{UUID_B}:dashboard")
        result = parse_admin_roles()
        assert UUID_B in result
        assert result[UUID_B] == {"dashboard"}
        assert any("Invalid user ID" in r.message for r in caplog.records)

    def test_missing_colon_skipped(self, monkeypatch, caplog):
        caplog.set_level("WARNING")
        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_A}:dashboard;no_colon_entry")
        result = parse_admin_roles()
        assert result == {UUID_A: {"dashboard"}}
        assert any("missing colon" in r.message.lower() for r in caplog.records)

    def test_role_name_validation(self, monkeypatch):
        """Only known AdminRole values are accepted."""
        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_A}:dashboard,user_manager,BILLING")
        result = parse_admin_roles()
        # "BILLING" is uppercase, not in enum — should be skipped
        assert result[UUID_A] == {"dashboard", "user_manager"}


class TestGetLegacyAdminIds:
    """Legacy ADMIN_USER_IDS env var parsing."""

    def test_empty_env_returns_empty(self, monkeypatch):
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        assert get_legacy_admin_ids() == set()

    def test_single_valid_uuid(self, monkeypatch):
        monkeypatch.setenv("ADMIN_USER_IDS", UUID_A)
        assert get_legacy_admin_ids() == {UUID_A}

    def test_invalid_uuid_rejected(self, monkeypatch):
        monkeypatch.setenv("ADMIN_USER_IDS", "not-a-uuid")
        assert get_legacy_admin_ids() == set()

    def test_mixed_valid_and_invalid(self, monkeypatch):
        monkeypatch.setenv("ADMIN_USER_IDS", f"invalid,{UUID_A},bad,{UUID_B}")
        assert get_legacy_admin_ids() == {UUID_A, UUID_B}


class TestGetUserRolesFromEnv:
    """Role resolution from env vars with proper priority order."""

    def test_master_gets_all_roles(self, monkeypatch):
        """MASTER_USER_IDS gets all roles (highest priority)."""
        monkeypatch.setenv("MASTER_USER_IDS", UUID_M)
        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_M}:dashboard")
        monkeypatch.setenv("ADMIN_USER_IDS", UUID_M)

        roles = get_user_roles_from_env(UUID_M)
        # Master gets ALL roles, not just "dashboard"
        assert roles == {"dashboard", "user_manager", "billing", "data_access", "master"}

    def test_admin_roles_mapping(self, monkeypatch):
        """ADMIN_ROLES provides explicit role mapping."""
        monkeypatch.setenv("MASTER_USER_IDS", "")
        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_A}:dashboard,user_manager")
        monkeypatch.setenv("ADMIN_USER_IDS", f"{UUID_A}")

        roles = get_user_roles_from_env(UUID_A)
        assert roles == {"dashboard", "user_manager"}

    def test_legacy_admin_gets_dashboard(self, monkeypatch):
        """Legacy ADMIN_USER_IDS gets DASHBOARD only (minimum privilege)."""
        monkeypatch.setenv("MASTER_USER_IDS", "")
        monkeypatch.setenv("ADMIN_ROLES", "")
        monkeypatch.setenv("ADMIN_USER_IDS", UUID_A)

        roles = get_user_roles_from_env(UUID_A)
        assert roles == {"dashboard"}

    def test_regular_user_gets_none(self, monkeypatch):
        """Regular user returns None (no roles)."""
        monkeypatch.setenv("MASTER_USER_IDS", "")
        monkeypatch.setenv("ADMIN_ROLES", "")
        monkeypatch.setenv("ADMIN_USER_IDS", "")

        roles = get_user_roles_from_env("regular-user-id")
        assert roles is None

    def test_master_priority_over_admin_roles(self, monkeypatch):
        """Even if ADMIN_ROLES has fewer roles, master still gets all."""
        monkeypatch.setenv("MASTER_USER_IDS", UUID_A)
        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_A}:dashboard")
        monkeypatch.setenv("ADMIN_USER_IDS", "")

        roles = get_user_roles_from_env(UUID_A)
        assert roles == {"dashboard", "user_manager", "billing", "data_access", "master"}

    def test_case_insensitive_uuid(self, monkeypatch):
        """UUID matching is case-insensitive."""
        monkeypatch.setenv("MASTER_USER_IDS", UUID_M.upper())
        monkeypatch.setenv("ADMIN_ROLES", "")
        monkeypatch.setenv("ADMIN_USER_IDS", "")

        roles = get_user_roles_from_env(UUID_M.lower())
        assert roles is not None
