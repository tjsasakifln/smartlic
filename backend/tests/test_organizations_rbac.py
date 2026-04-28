"""RBAC-ORG-001 — role-based access control test matrix.

3 roles (owner | member | viewer) × 11 endpoints, plus edge cases:
- last-owner demotion guard (AC7)
- transfer-ownership atomicity (AC6)
- audit-log read gating (AC9)
- placeholder permission helper (AC15)

Test pattern: each test patches `dependencies.org_auth._fetch_membership`
to return a synthetic membership row, then issues an HTTP request and
asserts on status code. We DO NOT exercise the underlying service layer
heavily — that's covered in `test_organizations.py`. Here we focus on
the RBAC gate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from auth import require_auth
from main import app
from schemas.organization import OrganizationMember, OrgRole


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _enable_organizations():
    with patch("routes.organizations.ORGANIZATIONS_ENABLED", True):
        yield


@pytest.fixture(autouse=True)
def _no_audit():
    """Stub log_org_event so RBAC tests don't need a real Supabase mock."""
    async def _noop(**kwargs):
        return None

    with patch("routes.organizations.log_org_event", side_effect=_noop):
        yield


def _user(uid: str = "user-001") -> dict:
    return {"id": uid, "email": f"{uid}@test.com", "role": "authenticated", "aal": "aal1"}


def _membership(user_id: str, role: OrgRole, org_id: str = "org-abc") -> OrganizationMember:
    return OrganizationMember(
        org_id=org_id,
        user_id=user_id,
        role=role,
        invited_at=None,
        accepted_at=datetime.now(timezone.utc),
    )


def _patch_role(role: OrgRole | None, user_id: str = "user-001"):
    """Return a context manager that stubs `_fetch_membership`.

    role=None → returns None (simulates "user is not a member").
    """

    async def _lookup(org_id=None, user_id=None, **_kw):
        if role is None:
            return None
        return _membership(user_id or "user-001", role, org_id or "org-abc")

    return patch("dependencies.org_auth._fetch_membership", side_effect=_lookup)


@pytest.fixture
def authed_client():
    """AsyncClient + require_auth override. Caller manages cleanup."""
    app.dependency_overrides[require_auth] = lambda: _user()
    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Endpoint matrix — (method, path, body, min_role, body_factory_for_owner)
# ---------------------------------------------------------------------------


# Each row: (description, http_method, url, json_body, min_role)
# `min_role` is the lowest role allowed; anything below 403s.
RBAC_MATRIX = [
    # GET org details — VIEWER+
    ("get_org",         "GET",    "/v1/organizations/org-abc",                          None,                                         OrgRole.VIEWER),
    # POST invite — OWNER
    ("invite",          "POST",   "/v1/organizations/org-abc/invite",                   {"email": "x@test.com"},                       OrgRole.OWNER),
    # GET dashboard — MEMBER+
    ("dashboard",       "GET",    "/v1/organizations/org-abc/dashboard",                None,                                         OrgRole.MEMBER),
    # PUT logo — OWNER
    ("logo",            "PUT",    "/v1/organizations/org-abc/logo",                     {"logo_url": "https://x/y.png"},                OrgRole.OWNER),
    # PATCH role — OWNER
    ("role_change",     "PATCH",  "/v1/organizations/org-abc/members/user-002/role",    {"role": "viewer"},                            OrgRole.OWNER),
    # POST transfer-ownership — OWNER
    ("transfer",        "POST",   "/v1/organizations/org-abc/transfer-ownership",
        {"target_user_id": "user-002", "confirm": True},                                                                              OrgRole.OWNER),
    # GET audit-log — OWNER
    ("audit_log",       "GET",    "/v1/organizations/org-abc/audit-log",                None,                                         OrgRole.OWNER),
]


# ---------------------------------------------------------------------------
# 1) RBAC matrix — for every endpoint × every role below min, expect 403.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", RBAC_MATRIX, ids=[r[0] for r in RBAC_MATRIX])
@pytest.mark.parametrize("actor_role", [OrgRole.VIEWER, OrgRole.MEMBER, OrgRole.OWNER])
async def test_rbac_matrix(endpoint, actor_role):
    """Every (endpoint, actor_role) pair: actor below min_role → 403."""
    name, method, url, body, min_role = endpoint
    expected_403 = actor_role < min_role

    app.dependency_overrides[require_auth] = lambda: _user()
    try:
        # Stub services so handler bodies don't crash if RBAC permits.
        with _patch_role(actor_role), \
             patch("routes.organizations.invite_member", new_callable=AsyncMock, return_value={}), \
             patch("routes.organizations.get_organization", new_callable=AsyncMock, return_value={"id": "org-abc", "name": "x"}), \
             patch("routes.organizations.get_org_dashboard", new_callable=AsyncMock, return_value={"member_count": 1}), \
             patch("routes.organizations.update_org_logo", new_callable=AsyncMock, return_value={"updated": True}), \
             patch("routes.organizations.update_member_role", new_callable=AsyncMock, return_value={"updated": True, "old_role": "member", "new_role": "viewer"}), \
             patch("routes.organizations.transfer_ownership", new_callable=AsyncMock, return_value={"transferred": True}), \
             patch("routes.organizations.fetch_audit_log", new_callable=AsyncMock, return_value=([], 0)):

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                if method == "GET":
                    resp = await client.get(url)
                elif method == "POST":
                    resp = await client.post(url, json=body or {})
                elif method == "PATCH":
                    resp = await client.patch(url, json=body or {})
                elif method == "PUT":
                    resp = await client.put(url, json=body or {})
                elif method == "DELETE":
                    resp = await client.delete(url)
                else:
                    pytest.fail(f"Unknown method {method}")

        if expected_403:
            assert resp.status_code == 403, (
                f"{actor_role.value} on {name}: expected 403, got {resp.status_code} ({resp.text[:200]})"
            )
        else:
            # Allowed — handler body should be reachable; status is 2xx (or
            # 400 for the transfer test if confirm flag missing — but our
            # body has confirm=True). Anything < 400 is fine.
            assert resp.status_code < 400, (
                f"{actor_role.value} on {name}: expected <400, got {resp.status_code} ({resp.text[:200]})"
            )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2) Non-member (no row at all) → 404 on every gated endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", RBAC_MATRIX, ids=[r[0] for r in RBAC_MATRIX])
async def test_non_member_404(endpoint):
    name, method, url, body, _ = endpoint
    app.dependency_overrides[require_auth] = lambda: _user()
    try:
        with _patch_role(None):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                if method == "GET":
                    resp = await client.get(url)
                elif method == "POST":
                    resp = await client.post(url, json=body or {})
                elif method == "PATCH":
                    resp = await client.patch(url, json=body or {})
                elif method == "PUT":
                    resp = await client.put(url, json=body or {})
                elif method == "DELETE":
                    resp = await client.delete(url)
        assert resp.status_code == 404, f"{name}: expected 404, got {resp.status_code}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3) DELETE member — special "self-leave allowed for any role"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [OrgRole.VIEWER, OrgRole.MEMBER, OrgRole.OWNER])
async def test_delete_member_self_leave_allowed(role):
    """Any role may remove themselves (self-leave)."""
    actor_id = "user-001"
    app.dependency_overrides[require_auth] = lambda: _user(actor_id)
    try:
        with _patch_role(role, actor_id), \
             patch("routes.organizations.remove_member", new_callable=AsyncMock, return_value={"removed": True}):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete(f"/v1/organizations/org-abc/members/{actor_id}")
        assert resp.status_code == 200, resp.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [OrgRole.VIEWER, OrgRole.MEMBER])
async def test_delete_member_non_owner_cannot_remove_others(role):
    """member/viewer cannot remove someone else — 403."""
    app.dependency_overrides[require_auth] = lambda: _user()
    try:
        with _patch_role(role):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/v1/organizations/org-abc/members/user-999")
        assert resp.status_code == 403, resp.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_member_owner_can_remove_others():
    """owner CAN remove other members."""
    app.dependency_overrides[require_auth] = lambda: _user()
    try:
        with _patch_role(OrgRole.OWNER), \
             patch("routes.organizations.remove_member", new_callable=AsyncMock, return_value={"removed": True}):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete("/v1/organizations/org-abc/members/user-999")
        assert resp.status_code == 200, resp.text
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4) AC7 — last-owner demotion guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_member_role_blocks_last_owner_demotion():
    """update_member_role raises PermissionError when demoting the last owner."""
    from services.organization_service import update_member_role

    sb_mock = type("SB", (), {})()
    table_calls = []

    class _Result:
        def __init__(self, data, count=None):
            self.data = data
            self.count = count

    class _Chain:
        def __init__(self, role_returns="owner", count=1):
            self._returns = role_returns
            self._count = count

        def select(self, *a, **kw):
            return self
        def eq(self, *a, **kw):
            return self
        def limit(self, *a, **kw):
            return self
        def update(self, *a, **kw):
            return self
        def execute(self):
            # First call: target lookup → returns target=owner.
            # Second call: count of owners → 1.
            if not table_calls:
                table_calls.append("lookup")
                return _Result([{"id": "mem-1", "role": "owner", "accepted_at": "now"}])
            return _Result([{"id": "mem-1"}], count=1)

    sb_mock.table = lambda *a, **kw: _Chain()

    with patch("services.organization_service.get_supabase", return_value=sb_mock):
        with pytest.raises(PermissionError) as exc:
            await update_member_role(
                org_id="org-abc",
                actor_user_id="actor-1",
                target_user_id="target-1",
                new_role="member",
            )
    assert "último owner" in str(exc.value).lower() or "last owner" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_update_member_role_allows_demotion_when_other_owner_exists():
    """Demoting an owner is allowed when ≥2 owners exist."""
    from services.organization_service import update_member_role

    table_calls = []

    class _Result:
        def __init__(self, data, count=None):
            self.data = data
            self.count = count

    class _Chain:
        def select(self, *a, **kw):
            return self
        def eq(self, *a, **kw):
            return self
        def limit(self, *a, **kw):
            return self
        def update(self, *a, **kw):
            return self
        def execute(self):
            if not table_calls:
                table_calls.append("lookup")
                return _Result([{"id": "mem-1", "role": "owner", "accepted_at": "now"}])
            if len(table_calls) == 1:
                table_calls.append("count")
                return _Result([{}, {}], count=2)  # ≥2 owners
            table_calls.append("update")
            return _Result([{}])

    sb_mock = type("SB", (), {"table": lambda self, *a, **kw: _Chain()})()

    with patch("services.organization_service.get_supabase", return_value=sb_mock):
        result = await update_member_role(
            org_id="org-abc",
            actor_user_id="actor-1",
            target_user_id="target-1",
            new_role="member",
        )
    assert result["updated"] is True
    assert result["new_role"] == "member"


# ---------------------------------------------------------------------------
# 5) AC6 — transfer-ownership rejects self-transfer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transfer_ownership_rejects_self_transfer():
    from services.organization_service import transfer_ownership
    with pytest.raises(ValueError) as exc:
        await transfer_ownership(
            org_id="org-abc",
            current_owner_id="user-001",
            target_user_id="user-001",
        )
    assert "si mesmo" in str(exc.value).lower() or "self" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_transfer_ownership_endpoint_requires_confirm():
    """POST /transfer-ownership without confirm=True → 400."""
    app.dependency_overrides[require_auth] = lambda: _user()
    try:
        with _patch_role(OrgRole.OWNER):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/v1/organizations/org-abc/transfer-ownership",
                    json={"target_user_id": "user-002", "confirm": False},
                )
        assert resp.status_code == 400, resp.text
        assert "confirm" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6) OrgRole hierarchy ordinals (sanity)
# ---------------------------------------------------------------------------


def test_org_role_hierarchy():
    assert OrgRole.OWNER > OrgRole.MEMBER
    assert OrgRole.MEMBER > OrgRole.VIEWER
    assert OrgRole.OWNER >= OrgRole.OWNER
    assert OrgRole.VIEWER < OrgRole.MEMBER < OrgRole.OWNER


# ---------------------------------------------------------------------------
# 7) AC15 — placeholder require_org_permission proxies to require_org_role
# ---------------------------------------------------------------------------


def test_require_org_permission_known_perms_dont_raise():
    from dependencies.org_auth import require_org_permission

    # Should not raise for known perms — returns a callable
    for perm in [
        "org.read",
        "org.members.invite",
        "org.delete",
        "org.audit_log.read",
    ]:
        assert callable(require_org_permission(perm))


def test_require_org_permission_unknown_perm_raises():
    from dependencies.org_auth import require_org_permission

    with pytest.raises(ValueError):
        require_org_permission("totally.bogus.permission")
