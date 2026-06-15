"""Tests for STORY-224 Track 3: Authorization module tests.

Tests admin and master access control, role checking with retry logic, and environment-based admin overrides.

Covers:
- AC19: require_admin rejects non-admin users (403)
- AC20: require_admin accepts users in ADMIN_USER_IDS env var
- AC21: _check_user_roles() retry logic (1 retry, 0.3s delay)

Related Files:
- backend/authorization.py: _get_admin_ids, _check_user_roles, _is_admin, _has_master_access, _get_master_quota_info
"""

import time
import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException


UUID_A = "550e8400-e29b-41d4-a716-446655440000"
UUID_B = "3422b448-2460-4fd2-9183-8000de6f8343"
UUID_C = "4f6a3cb7-1c5d-4e9a-bbde-a8c4a2a9d01a"


class TestGetAdminIds:
    """Test _get_admin_ids() UUID validation and normalization."""

    def test_empty_env_returns_empty_set(self, monkeypatch):
        """Empty ADMIN_USER_IDS returns empty set."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from authorization import _get_admin_ids

        result = _get_admin_ids()

        assert result == set()

    def test_single_valid_uuid(self, monkeypatch):
        """Single valid UUID is accepted."""
        monkeypatch.setenv("ADMIN_USER_IDS", UUID_A)
        from authorization import _get_admin_ids

        result = _get_admin_ids()

        assert result == {UUID_A}

    def test_multiple_valid_uuids(self, monkeypatch):
        """Multiple comma-separated valid UUIDs are parsed."""
        monkeypatch.setenv("ADMIN_USER_IDS", f"{UUID_A},{UUID_B},{UUID_C}")
        from authorization import _get_admin_ids

        result = _get_admin_ids()

        assert result == {UUID_A, UUID_B, UUID_C}

    def test_whitespace_handling(self, monkeypatch):
        """Whitespace around UUIDs is stripped."""
        monkeypatch.setenv("ADMIN_USER_IDS", f"  {UUID_A}  ,  {UUID_B}  ")
        from authorization import _get_admin_ids

        result = _get_admin_ids()

        assert result == {UUID_A, UUID_B}

    def test_case_normalization(self, monkeypatch):
        """UUIDs are normalized to lowercase."""
        monkeypatch.setenv("ADMIN_USER_IDS", UUID_A.upper())
        from authorization import _get_admin_ids

        result = _get_admin_ids()

        assert result == {UUID_A.lower()}

    def test_empty_items_ignored(self, monkeypatch):
        """Empty items from multiple commas are ignored."""
        monkeypatch.setenv("ADMIN_USER_IDS", f"{UUID_A},,,{UUID_B},,")
        from authorization import _get_admin_ids

        result = _get_admin_ids()

        assert result == {UUID_A, UUID_B}

    def test_missing_env_var(self, monkeypatch):
        """Missing ADMIN_USER_IDS env var returns empty set."""
        monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
        from authorization import _get_admin_ids

        result = _get_admin_ids()

        assert result == set()

    def test_invalid_uuid_rejected(self, monkeypatch):
        """Non-UUID strings are rejected and not added to the set."""
        monkeypatch.setenv("ADMIN_USER_IDS", "not-a-uuid,admin-user-123")
        from authorization import _get_admin_ids

        result = _get_admin_ids()

        assert result == set()

    def test_mixed_valid_invalid_uuids(self, monkeypatch):
        """Valid UUIDs accepted, invalid ones silently dropped."""
        monkeypatch.setenv("ADMIN_USER_IDS", f"{UUID_A},not-a-uuid,{UUID_B},bad")
        from authorization import _get_admin_ids

        result = _get_admin_ids()

        assert result == {UUID_A, UUID_B}

    def test_invalid_uuid_logs_warning(self, monkeypatch, caplog):
        """Invalid UUIDs emit a warning log."""
        import logging
        monkeypatch.setenv("ADMIN_USER_IDS", "invalid-id")
        from authorization import _get_admin_ids

        with caplog.at_level(logging.WARNING, logger="authorization"):
            _get_admin_ids()

        assert any("Invalid admin ID" in r.message for r in caplog.records)


class TestCheckUserRoles:
    """Test _check_user_roles() with Supabase integration."""

    @pytest.mark.asyncio
    async def test_admin_user(self):
        """User with is_admin=true returns (True, True)."""
        from authorization import _check_user_roles

        mock_response = Mock()
        mock_response.data = {"is_admin": True, "plan_type": "free_trial"}

        mock_execute = Mock(return_value=mock_response)
        mock_single = Mock(return_value=Mock(execute=mock_execute))
        mock_eq = Mock(return_value=Mock(single=mock_single))
        mock_select = Mock(return_value=Mock(eq=mock_eq))
        mock_table = Mock(return_value=Mock(select=mock_select))

        mock_sb = Mock(table=mock_table)

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            is_admin, is_master = await _check_user_roles("admin-user-id")

        assert is_admin is True
        assert is_master is True  # Admin implies master

    @pytest.mark.asyncio
    async def test_master_user(self):
        """User with plan_type='master' returns (False, True)."""
        from authorization import _check_user_roles

        mock_response = Mock()
        mock_response.data = {"is_admin": False, "plan_type": "master"}

        mock_execute = Mock(return_value=mock_response)
        mock_single = Mock(return_value=Mock(execute=mock_execute))
        mock_eq = Mock(return_value=Mock(single=mock_single))
        mock_select = Mock(return_value=Mock(eq=mock_eq))
        mock_table = Mock(return_value=Mock(select=mock_select))

        mock_sb = Mock(table=mock_table)

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            is_admin, is_master = await _check_user_roles("master-user-id")

        assert is_admin is False
        assert is_master is True

    @pytest.mark.asyncio
    async def test_regular_user(self):
        """Regular user (is_admin=false, plan_type!='master') returns (False, False)."""
        from authorization import _check_user_roles

        mock_response = Mock()
        mock_response.data = {"is_admin": False, "plan_type": "free_trial"}

        mock_execute = Mock(return_value=mock_response)
        mock_single = Mock(return_value=Mock(execute=mock_execute))
        mock_eq = Mock(return_value=Mock(single=mock_single))
        mock_select = Mock(return_value=Mock(eq=mock_eq))
        mock_table = Mock(return_value=Mock(select=mock_select))

        mock_sb = Mock(table=mock_table)

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            is_admin, is_master = await _check_user_roles("regular-user-id")

        assert is_admin is False
        assert is_master is False

    @pytest.mark.asyncio
    async def test_profile_not_found(self):
        """Profile not found (data=None) returns (False, False)."""
        from authorization import _check_user_roles

        mock_response = Mock()
        mock_response.data = None

        mock_execute = Mock(return_value=mock_response)
        mock_single = Mock(return_value=Mock(execute=mock_execute))
        mock_eq = Mock(return_value=Mock(single=mock_single))
        mock_select = Mock(return_value=Mock(eq=mock_eq))
        mock_table = Mock(return_value=Mock(select=mock_select))

        mock_sb = Mock(table=mock_table)

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            is_admin, is_master = await _check_user_roles("nonexistent-user")

        assert is_admin is False
        assert is_master is False

    @pytest.mark.asyncio
    async def test_is_admin_column_missing_fallback(self):
        """If is_admin column doesn't exist, fallback to plan_type only."""
        from authorization import _check_user_roles

        # First attempt: is_admin column missing (raises exception)
        # Second attempt: fallback to just plan_type (succeeds)
        mock_response_fallback = Mock()
        mock_response_fallback.data = {"plan_type": "master"}

        mock_execute_fallback = Mock(return_value=mock_response_fallback)
        mock_single_fallback = Mock(return_value=Mock(execute=mock_execute_fallback))
        mock_eq_fallback = Mock(return_value=Mock(single=mock_single_fallback))
        Mock(return_value=Mock(eq=mock_eq_fallback))

        # First select() with is_admin raises
        # Second select() without is_admin succeeds
        call_count = {"count": 0}

        def mock_select_side_effect(*args):
            call_count["count"] += 1
            if call_count["count"] == 1:
                # First call: is_admin + plan_type
                raise Exception("Column is_admin does not exist")
            else:
                # Second call: plan_type only
                return Mock(eq=mock_eq_fallback)

        mock_table = Mock(return_value=Mock(select=Mock(side_effect=mock_select_side_effect)))
        mock_sb = Mock(table=mock_table)

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            is_admin, is_master = await _check_user_roles("user-id")

        # Should fallback to plan_type only
        assert is_admin is False
        assert is_master is True

    @pytest.mark.asyncio
    async def test_retry_on_first_failure(self):
        """AC21: Retry logic - first failure triggers 0.3s delay + retry."""
        from authorization import _check_user_roles

        # First call: raises exception AFTER the inner try/except (e.g., at profile.data access)
        # Second call: succeeds
        mock_response_success = Mock()
        mock_response_success.data = {"is_admin": False, "plan_type": "free_trial"}

        attempts = []

        def mock_get_supabase_side_effect():
            attempts.append(1)
            if len(attempts) == 1:
                # First attempt - fail at get_supabase() level (outer exception)
                raise Exception("Transient database connection error")
            else:
                # Second attempt - succeed
                mock_execute = Mock(return_value=mock_response_success)
                mock_single = Mock(return_value=Mock(execute=mock_execute))
                mock_eq = Mock(return_value=Mock(single=mock_single))
                mock_select = Mock(return_value=Mock(eq=mock_eq))
                mock_table = Mock(return_value=Mock(select=mock_select))
                return Mock(table=mock_table)

        start_time = time.time()

        with patch("supabase_client.get_supabase", side_effect=mock_get_supabase_side_effect):
            is_admin, is_master = await _check_user_roles("retry-user-id")

        elapsed = time.time() - start_time

        # Should have retried after ~0.3s
        assert elapsed >= 0.25  # Allow some tolerance
        assert len(attempts) == 2  # Two attempts
        assert is_admin is False
        assert is_master is False

    @pytest.mark.asyncio
    async def test_failure_after_two_attempts(self):
        """AC21: After 2 failed attempts, returns (False, False)."""
        from authorization import _check_user_roles

        attempts = []

        def mock_get_supabase_side_effect():
            attempts.append(1)
            # Always fail
            raise Exception("Persistent database connection error")

        with patch("supabase_client.get_supabase", side_effect=mock_get_supabase_side_effect):
            is_admin, is_master = await _check_user_roles("failure-user-id")

        # Should return (False, False) after 2 attempts
        assert is_admin is False
        assert is_master is False
        assert len(attempts) == 2

    @pytest.mark.asyncio
    async def test_admin_with_master_plan_type(self):
        """Admin with plan_type='master' still returns (True, True)."""
        from authorization import _check_user_roles

        mock_response = Mock()
        mock_response.data = {"is_admin": True, "plan_type": "master"}

        mock_execute = Mock(return_value=mock_response)
        mock_single = Mock(return_value=Mock(execute=mock_execute))
        mock_eq = Mock(return_value=Mock(single=mock_single))
        mock_select = Mock(return_value=Mock(eq=mock_eq))
        mock_table = Mock(return_value=Mock(select=mock_select))
        mock_sb = Mock(table=mock_table)

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            is_admin, is_master = await _check_user_roles("admin-master-user")

        assert is_admin is True
        assert is_master is True


class TestIsAdmin:
    """Test _is_admin() fast path and Supabase fallback."""

    @pytest.mark.asyncio
    async def test_via_env_var_fast_path(self, monkeypatch):
        """AC20: User in ADMIN_USER_IDS env var returns True (no DB call)."""
        monkeypatch.setenv("ADMIN_USER_IDS", f"{UUID_A},{UUID_B}")
        from authorization import is_admin as _is_admin

        with patch("authorization.check_user_roles") as mock_check:
            result = await _is_admin(UUID_A)

        assert result is True
        # Should NOT have called Supabase
        mock_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_via_env_var_case_insensitive(self, monkeypatch):
        """Env var match is case-insensitive (UUID normalized to lowercase)."""
        monkeypatch.setenv("ADMIN_USER_IDS", UUID_A.upper())
        from authorization import is_admin as _is_admin

        with patch("authorization.check_user_roles") as mock_check:
            result = await _is_admin(UUID_A)

        assert result is True
        mock_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_via_supabase(self, monkeypatch):
        """User not in env var but is_admin=true in Supabase returns True."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from authorization import is_admin as _is_admin

        with patch("authorization.check_user_roles", return_value=(True, True)):
            result = await _is_admin("db-admin-user")

        assert result is True

    @pytest.mark.asyncio
    async def test_not_admin(self, monkeypatch):
        """User not in env var and is_admin=false in Supabase returns False."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from authorization import is_admin as _is_admin

        with patch("authorization.check_user_roles", return_value=(False, False)):
            result = await _is_admin("regular-user")

        assert result is False


class TestHasMasterAccess:
    """Test _has_master_access() for admin/master privilege checking."""

    @pytest.mark.asyncio
    async def test_via_env_admin(self, monkeypatch):
        """User in ADMIN_USER_IDS has master access (no DB call)."""
        monkeypatch.setenv("ADMIN_USER_IDS", UUID_A)
        from authorization import has_master_access as _has_master_access

        with patch("authorization.check_user_roles") as mock_check:
            result = await _has_master_access(UUID_A)

        assert result is True
        mock_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_via_db_admin(self, monkeypatch):
        """User with is_admin=true in Supabase has master access."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from authorization import has_master_access as _has_master_access

        with patch("authorization.check_user_roles", return_value=(True, True)):
            result = await _has_master_access("db-admin")

        assert result is True

    @pytest.mark.asyncio
    async def test_via_db_master_plan_type(self, monkeypatch):
        """User with plan_type='master' has master access."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from authorization import has_master_access as _has_master_access

        with patch("authorization.check_user_roles", return_value=(False, True)):
            result = await _has_master_access("master-plan-user")

        assert result is True

    @pytest.mark.asyncio
    async def test_regular_user(self, monkeypatch):
        """Regular user (not admin, not master) returns False."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from authorization import has_master_access as _has_master_access

        with patch("authorization.check_user_roles", return_value=(False, False)):
            result = await _has_master_access("regular-user")

        assert result is False


class TestGetMasterQuotaInfo:
    """Test _get_master_quota_info() returns sala_guerra plan."""

    def test_admin_label(self):
        """Admin user gets 'SmartLic Pro (Admin)' label."""
        from authorization import _get_master_quota_info

        quota_info = _get_master_quota_info(is_admin=True)

        assert quota_info.allowed is True
        assert quota_info.plan_id == "sala_guerra"
        assert quota_info.plan_name == "SmartLic Pro (Admin)"
        assert quota_info.quota_remaining == 999999

    def test_master_label(self):
        """Master user gets 'SmartLic Pro (Master)' label."""
        from authorization import _get_master_quota_info

        quota_info = _get_master_quota_info(is_admin=False)

        assert quota_info.allowed is True
        assert quota_info.plan_id == "sala_guerra"
        assert quota_info.plan_name == "SmartLic Pro (Master)"
        assert quota_info.quota_remaining == 999999

    def test_returns_correct_plan_id(self):
        """Returns sala_guerra plan_id (highest tier)."""
        from authorization import _get_master_quota_info

        quota_info = _get_master_quota_info(is_admin=False)

        assert quota_info.plan_id == "sala_guerra"

    def test_unlimited_quota(self):
        """Master quota is effectively unlimited."""
        from authorization import _get_master_quota_info

        quota_info = _get_master_quota_info(is_admin=True)

        assert quota_info.quota_used == 0
        assert quota_info.quota_remaining == 999999

    def test_capabilities_included(self):
        """Returns sala_guerra capabilities."""
        from authorization import _get_master_quota_info

        quota_info = _get_master_quota_info(is_admin=True)

        assert quota_info.capabilities is not None
        # sala_guerra has the most permissive capabilities (dict format)
        assert "allow_excel" in quota_info.capabilities
        assert quota_info.capabilities["allow_excel"] is True


class TestRequireAdmin:
    """Test require_admin dependency (AC19, AC20)."""

    @pytest.mark.asyncio
    async def test_rejects_non_admin_with_403(self, monkeypatch):
        """AC19: require_admin raises 403 for non-admin users."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from admin import require_admin

        mock_user = {"id": "regular-user", "email": "user@example.com"}

        with patch("admin._is_admin_from_supabase", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(user=mock_user)

        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail.lower() or "forbidden" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_accepts_user_in_env_var(self, monkeypatch):
        """AC20: require_admin accepts users in ADMIN_USER_IDS env var."""
        # Use valid UUID v4 format (admin.py validates this)
        admin_uuid = "550e8400-e29b-41d4-a716-446655440000"
        monkeypatch.setenv("ADMIN_USER_IDS", admin_uuid)
        from admin import require_admin

        mock_user = {"id": admin_uuid, "email": "admin@example.com"}

        # No patch needed - env var fast path doesn't call Supabase
        result = await require_admin(user=mock_user)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_accepts_db_admin(self, monkeypatch):
        """require_admin accepts user with is_admin=true in Supabase."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from admin import require_admin

        mock_user = {"id": "db-admin", "email": "dbadmin@example.com"}

        with patch("admin._is_admin_from_supabase", return_value=True):
            result = await require_admin(user=mock_user)

        assert result == mock_user

    @pytest.mark.asyncio
    async def test_rejects_unauthenticated_user(self, monkeypatch):
        """require_admin raises AttributeError when user is None (because require_auth dependency should handle this)."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from admin import require_admin

        # require_admin expects user from require_auth dependency
        # If user is None, it will raise AttributeError trying to call user.get()
        # In real usage, require_auth dependency raises 401 before require_admin runs
        with pytest.raises(AttributeError):
            await require_admin(user=None)

    @pytest.mark.asyncio
    async def test_error_message_is_clear(self, monkeypatch):
        """require_admin error message mentions admin access required."""
        monkeypatch.setenv("ADMIN_USER_IDS", "")
        from admin import require_admin

        mock_user = {"id": "regular-user"}

        with patch("admin._is_admin_from_supabase", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await require_admin(user=mock_user)

        detail = exc_info.value.detail.lower()
        assert "admin" in detail or "forbidden" in detail or "acesso negado" in detail or "restrito" in detail


class TestGetUserRoles:
    """Test get_user_roles() with env-based and DB-based resolution."""

    @pytest.mark.asyncio
    async def test_master_gets_all_roles_from_env(self, monkeypatch):
        """MASTER_USER_IDS returns all roles (no DB call)."""
        from authorization import get_user_roles

        monkeypatch.setenv("MASTER_USER_IDS", UUID_A)

        with patch("supabase_client.get_supabase") as mock_sb:
            roles = await get_user_roles(UUID_A)

        assert len(roles) == 5  # All five roles
        assert "dashboard" in roles
        assert "user_manager" in roles
        assert "billing" in roles
        assert "data_access" in roles
        assert "master" in roles
        mock_sb.assert_not_called()

    @pytest.mark.asyncio
    async def test_admin_roles_from_env(self, monkeypatch):
        """ADMIN_ROLES returns explicit roles."""
        from authorization import get_user_roles

        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_A}:dashboard,user_manager")
        monkeypatch.setenv("ADMIN_USER_IDS", "")

        with patch("supabase_client.get_supabase") as mock_sb:
            roles = await get_user_roles(UUID_A)

        assert roles == {"dashboard", "user_manager"}
        mock_sb.assert_not_called()

    @pytest.mark.asyncio
    async def test_legacy_admin_gets_dashboard(self, monkeypatch):
        """ADMIN_USER_IDS (legacy) returns DASHBOARD only."""
        from authorization import get_user_roles

        monkeypatch.setenv("ADMIN_USER_IDS", UUID_A)
        monkeypatch.setenv("MASTER_USER_IDS", "")
        monkeypatch.setenv("ADMIN_ROLES", "")

        with patch("supabase_client.get_supabase") as mock_sb:
            roles = await get_user_roles(UUID_A)

        assert roles == {"dashboard"}
        mock_sb.assert_not_called()

    @pytest.mark.asyncio
    async def test_fallback_to_db(self, monkeypatch):
        """When env vars are empty, falls back to admin_roles table."""
        from authorization import get_user_roles

        monkeypatch.setenv("ADMIN_USER_IDS", "")
        monkeypatch.setenv("MASTER_USER_IDS", "")
        monkeypatch.setenv("ADMIN_ROLES", "")

        mock_response = Mock()
        mock_response.data = {"roles": ["user_manager", "billing"]}

        mock_execute = Mock(return_value=mock_response)
        mock_single = Mock(return_value=Mock(execute=mock_execute))
        mock_eq = Mock(return_value=Mock(single=mock_single))
        mock_select = Mock(return_value=Mock(eq=mock_eq))
        mock_table = Mock(return_value=Mock(select=mock_select))
        mock_sb = Mock(table=mock_table)

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            roles = await get_user_roles(UUID_B)

        assert roles == {"user_manager", "billing"}

    @pytest.mark.asyncio
    async def test_regular_user_returns_empty(self, monkeypatch):
        """Regular user (no roles anywhere) returns empty set."""
        from authorization import get_user_roles

        monkeypatch.setenv("ADMIN_USER_IDS", "")
        monkeypatch.setenv("MASTER_USER_IDS", "")
        monkeypatch.setenv("ADMIN_ROLES", "")

        mock_response = Mock()
        mock_response.data = None

        mock_execute = Mock(return_value=mock_response)
        mock_single = Mock(return_value=Mock(execute=mock_execute))
        mock_eq = Mock(return_value=Mock(single=mock_single))
        mock_select = Mock(return_value=Mock(eq=mock_eq))
        mock_table = Mock(return_value=Mock(select=mock_select))
        mock_sb = Mock(table=mock_table)

        with patch("supabase_client.get_supabase", return_value=mock_sb):
            roles = await get_user_roles("regular-user")

        assert roles == set()

    @pytest.mark.asyncio
    async def test_db_error_returns_empty(self, monkeypatch):
        """DB error during admin_roles lookup returns empty set (graceful)."""
        from authorization import get_user_roles

        monkeypatch.setenv("ADMIN_USER_IDS", "")
        monkeypatch.setenv("MASTER_USER_IDS", "")
        monkeypatch.setenv("ADMIN_ROLES", "")

        with patch("supabase_client.get_supabase", side_effect=Exception("DB down")):
            roles = await get_user_roles("any-user")

        assert roles == set()


class TestRequireRole:
    """Test require_role() dependency factory."""

    @pytest.mark.asyncio
    async def test_allows_user_with_required_role(self, monkeypatch):
        """User with required role passes the check."""
        from authorization import require_role

        monkeypatch.setenv("ADMIN_ROLES", f"{UUID_A}:data_access")

        checker = require_role("data_access", "master")
        mock_user = {"id": UUID_A}

        result = await checker(user=mock_user)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_allows_master_any_role(self, monkeypatch):
        """Master user passes any role check."""
        from authorization import require_role

        monkeypatch.setenv("MASTER_USER_IDS", UUID_A)

        checker = require_role("user_manager")  # User only has MASTER, not USER_MANAGER
        mock_user = {"id": UUID_A}

        result = await checker(user=mock_user)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_rejects_user_without_role(self, monkeypatch):
        """User without any roles gets 403."""
        from authorization import require_role

        monkeypatch.setenv("ADMIN_USER_IDS", "")

        checker = require_role("data_access")
        mock_user = {"id": "regular-user"}

        with patch("authorization.get_user_roles", return_value=set()):
            with pytest.raises(HTTPException) as exc_info:
                await checker(user=mock_user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_rejects_wrong_role(self, monkeypatch):
        """User with wrong role gets 403."""
        from authorization import require_role

        checker = require_role("billing")
        mock_user = {"id": UUID_A}

        with patch("authorization.get_user_roles", return_value={"dashboard"}):
            with pytest.raises(HTTPException) as exc_info:
                await checker(user=mock_user)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_shorthand_require_data_access(self, monkeypatch):
        """require_data_access works correctly."""
        from authorization import require_data_access

        mock_user = {"id": UUID_A}

        with patch("authorization.get_user_roles", return_value={"data_access"}):
            result = await require_data_access(user=mock_user)
            assert result == mock_user

        with patch("authorization.get_user_roles", return_value={"dashboard"}):
            with pytest.raises(HTTPException):
                await require_data_access(user=mock_user)

    @pytest.mark.asyncio
    async def test_shorthand_require_user_manager(self, monkeypatch):
        """require_user_manager works correctly."""
        from authorization import require_user_manager

        mock_user = {"id": UUID_A}

        with patch("authorization.get_user_roles", return_value={"user_manager"}):
            result = await require_user_manager(user=mock_user)
            assert result == mock_user

        with patch("authorization.get_user_roles", return_value={"dashboard"}):
            with pytest.raises(HTTPException):
                await require_user_manager(user=mock_user)
