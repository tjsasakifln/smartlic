"""Tests for RBAC Granular Phase 1."""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException

ADMIN_UUID = "550e8400-e29b-41d4-a716-446655440000"
REGULAR_UUID = "550e8400-e29b-41d4-a716-446655440001"
ADMIN_USER = {"id": ADMIN_UUID, "email": "admin@example.com", "role": "authenticated"}

class TestHasAdminRole:
    def test_specific(self):
        from rbac_granular import has_admin_role
        assert has_admin_role(["admin:users"], "admin:users")
    def test_super_all(self):
        from rbac_granular import has_admin_role
        assert has_admin_role(["admin:super"], "admin:users")
    def test_wrong(self):
        from rbac_granular import has_admin_role
        assert not has_admin_role(["admin:billing"], "admin:users")

class TestRequireAdminRole:
    def test_valid(self):
        from rbac_granular import require_admin_role
        for r in ["admin:users","admin:billing","admin:cache","admin:partners","admin:seo","admin:ops","admin:compliance","admin:super"]:
            assert callable(require_admin_role(r))
    def test_invalid(self):
        from rbac_granular import require_admin_role
        with pytest.raises(ValueError): require_admin_role("admin:nonexistent")

class TestCrossRoleAccess:
    ALL = ["admin:users","admin:billing","admin:cache","admin:partners","admin:seo","admin:ops","admin:compliance","admin:super"]
    def _app(self, role):
        from fastapi import FastAPI, Depends; from auth import require_auth; from rbac_granular import require_admin_role
        app = FastAPI()
        @app.get("/admin/x")
        async def ep(u=Depends(require_admin_role(role))): return {"ok": True}
        app.dependency_overrides[require_auth] = lambda: ADMIN_USER
        return app
    def _ms(self, roles):
        m = Mock(); m2 = Mock(); m2.execute.return_value = Mock(data={"admin_roles": roles})
        m.table.return_value.select.return_value.eq.return_value.single.return_value = m2
        return patch("supabase_client.get_supabase", return_value=m)
    @pytest.mark.parametrize("r", ALL)
    def test_own(self, r):
        from fastapi.testclient import TestClient
        with self._ms([r]): assert TestClient(self._app(r)).get("/admin/x").status_code == 200
    def test_super_all(self):
        from fastapi.testclient import TestClient
        for t in self.ALL:
            with self._ms(["admin:super"]): assert TestClient(self._app(t)).get("/admin/x").status_code == 200
    @pytest.mark.parametrize("u,t", [("admin:users","admin:billing"),("admin:billing","admin:users")])
    def test_cross(self, u, t):
        from fastapi.testclient import TestClient
        with self._ms([u]): assert TestClient(self._app(t)).get("/admin/x").status_code == 403

class TestGetProfileAdminRoles:
    @pytest.mark.asyncio
    async def test_ok(self):
        from rbac_granular import get_profile_admin_roles
        m = Mock(); m2 = Mock(); m2.execute.return_value = Mock(data={"admin_roles": ["admin:users"]})
        m.table.return_value.select.return_value.eq.return_value.single.return_value = m2
        with patch("supabase_client.get_supabase", return_value=m):
            assert await get_profile_admin_roles(ADMIN_UUID) == ["admin:users"]
    @pytest.mark.asyncio
    async def test_err(self):
        from rbac_granular import get_profile_admin_roles
        m = Mock(); m2 = Mock(); m2.execute.side_effect = Exception("x")
        m.table.return_value.select.return_value.eq.return_value.single.return_value = m2
        with patch("supabase_client.get_supabase", return_value=m):
            assert await get_profile_admin_roles(ADMIN_UUID) == []
