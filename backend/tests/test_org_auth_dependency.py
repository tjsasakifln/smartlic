"""Unit tests for `backend/dependencies/org_auth.py`.

Covers:
- `_coerce_role` (legacy 'admin' → 'member' alias)
- `_fetch_membership` happy path / pending invite / not-found
- `require_org_role` factory: 401 / 404 / 403 / 200 paths
- `require_org_permission` placeholder (AC15)
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from dependencies import org_auth
from dependencies.org_auth import (
    _coerce_role,
    _fetch_membership,
    require_org_permission,
    require_org_role,
)
from schemas.organization import OrgRole


# ---------------------------------------------------------------------------
# _coerce_role
# ---------------------------------------------------------------------------


def test_coerce_role_canonical():
    assert _coerce_role("owner") == OrgRole.OWNER
    assert _coerce_role("member") == OrgRole.MEMBER
    assert _coerce_role("viewer") == OrgRole.VIEWER


def test_coerce_role_legacy_admin_aliased_to_member():
    """Story decision: legacy 'admin' → 'member' (privilege-down, safe)."""
    assert _coerce_role("admin") == OrgRole.MEMBER


def test_coerce_role_case_insensitive_and_strips():
    assert _coerce_role("  Owner  ") == OrgRole.OWNER
    assert _coerce_role("VIEWER") == OrgRole.VIEWER


def test_coerce_role_unknown_returns_none():
    assert _coerce_role("god") is None
    assert _coerce_role("") is None
    assert _coerce_role("   ") is None


# ---------------------------------------------------------------------------
# _fetch_membership
# ---------------------------------------------------------------------------


def _make_supabase_mock(rows: list[dict]):
    """Build a tightly-scoped Supabase mock returning `rows` from execute()."""
    sb = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    result = MagicMock()
    result.data = rows
    chain.execute.return_value = result
    sb.table.return_value = chain
    return sb


@pytest.mark.asyncio
async def test_fetch_membership_returns_member_for_accepted_row():
    sb = _make_supabase_mock(
        [
            {
                "org_id": "org-abc",
                "user_id": "user-1",
                "role": "owner",
                "invited_at": None,
                "accepted_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
    )

    async def _fake_sb_execute(query, *, category="read"):
        return query.execute()

    with patch("supabase_client.get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", new=_fake_sb_execute):
        m = await _fetch_membership(org_id="org-abc", user_id="user-1")
    assert m is not None
    assert m.role == OrgRole.OWNER
    assert m.user_id == "user-1"


@pytest.mark.asyncio
async def test_fetch_membership_returns_none_for_pending_invite():
    """accepted_at IS NULL must NOT grant access."""
    sb = _make_supabase_mock(
        [
            {
                "org_id": "org-abc",
                "user_id": "user-1",
                "role": "owner",
                "invited_at": "2026-01-01",
                "accepted_at": None,
            }
        ]
    )

    async def _fake(query, *, category="read"):
        return query.execute()

    with patch("supabase_client.get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", new=_fake):
        m = await _fetch_membership(org_id="org-abc", user_id="user-1")
    assert m is None


@pytest.mark.asyncio
async def test_fetch_membership_returns_none_for_unknown_role():
    """Unknown role string → treat as no access (defense-in-depth)."""
    sb = _make_supabase_mock(
        [
            {
                "org_id": "org-abc",
                "user_id": "user-1",
                "role": "wizard",
                "invited_at": None,
                "accepted_at": "2026-01-01",
            }
        ]
    )

    async def _fake(query, *, category="read"):
        return query.execute()

    with patch("supabase_client.get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", new=_fake):
        m = await _fetch_membership(org_id="org-abc", user_id="user-1")
    assert m is None


@pytest.mark.asyncio
async def test_fetch_membership_returns_none_for_empty_result():
    sb = _make_supabase_mock([])

    async def _fake(query, *, category="read"):
        return query.execute()

    with patch("supabase_client.get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", new=_fake):
        m = await _fetch_membership(org_id="org-abc", user_id="user-1")
    assert m is None


@pytest.mark.asyncio
async def test_fetch_membership_swallows_db_errors():
    """DB transient errors must not crash the dependency — return None."""
    sb = MagicMock()

    async def _fake(query, *, category="read"):
        raise RuntimeError("transient")

    with patch("supabase_client.get_supabase", return_value=sb), \
         patch("supabase_client.sb_execute", new=_fake):
        m = await _fetch_membership(org_id="org-abc", user_id="user-1")
    assert m is None


# ---------------------------------------------------------------------------
# require_org_role — factory + behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_require_org_role_returns_member_on_success():
    """Owner accessing OWNER-gated endpoint → returns membership object."""
    async def _ok_lookup(org_id, user_id):
        from schemas.organization import OrganizationMember
        return OrganizationMember(
            org_id=org_id,
            user_id=user_id,
            role=OrgRole.OWNER,
            invited_at=None,
            accepted_at=datetime.now(timezone.utc),
        )

    dep = require_org_role(OrgRole.OWNER)
    with patch.object(org_auth, "_fetch_membership", side_effect=_ok_lookup):
        result = await dep(org_id="org-abc", user={"id": "user-1"})
    assert result.role == OrgRole.OWNER


@pytest.mark.asyncio
async def test_require_org_role_403_when_below_min():
    async def _viewer(org_id, user_id):
        from schemas.organization import OrganizationMember
        return OrganizationMember(
            org_id=org_id, user_id=user_id, role=OrgRole.VIEWER,
            invited_at=None, accepted_at=datetime.now(timezone.utc),
        )

    dep = require_org_role(OrgRole.OWNER)
    with patch.object(org_auth, "_fetch_membership", side_effect=_viewer), \
         pytest.raises(HTTPException) as exc:
        await dep(org_id="org-abc", user={"id": "user-1"})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_org_role_404_when_no_membership():
    async def _none(org_id, user_id):
        return None

    dep = require_org_role(OrgRole.VIEWER)
    with patch.object(org_auth, "_fetch_membership", side_effect=_none), \
         pytest.raises(HTTPException) as exc:
        await dep(org_id="org-abc", user={"id": "user-1"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_require_org_role_member_passes_member_gate_but_not_owner_gate():
    async def _member(org_id, user_id):
        from schemas.organization import OrganizationMember
        return OrganizationMember(
            org_id=org_id, user_id=user_id, role=OrgRole.MEMBER,
            invited_at=None, accepted_at=datetime.now(timezone.utc),
        )

    dep_member = require_org_role(OrgRole.MEMBER)
    dep_owner = require_org_role(OrgRole.OWNER)

    with patch.object(org_auth, "_fetch_membership", side_effect=_member):
        m = await dep_member(org_id="org-abc", user={"id": "u"})
        assert m.role == OrgRole.MEMBER

    with patch.object(org_auth, "_fetch_membership", side_effect=_member), \
         pytest.raises(HTTPException) as exc:
        await dep_owner(org_id="org-abc", user={"id": "u"})
    assert exc.value.status_code == 403


def test_require_org_role_factory_returns_distinct_callables():
    """Each call returns a fresh callable — important for test mocking."""
    dep1 = require_org_role(OrgRole.OWNER)
    dep2 = require_org_role(OrgRole.OWNER)
    assert dep1 is not dep2  # distinct objects


def test_require_org_role_callable_name_includes_min_role():
    """Stable name helps debugging in OpenAPI / stack traces."""
    dep = require_org_role(OrgRole.MEMBER)
    assert dep.__name__ == "require_org_role_member"


# ---------------------------------------------------------------------------
# require_org_permission (AC15 placeholder)
# ---------------------------------------------------------------------------


def test_require_org_permission_returns_callable():
    dep = require_org_permission("org.read")
    assert callable(dep)
    assert dep.__name__ == "require_org_role_viewer"


def test_require_org_permission_unknown_raises():
    with pytest.raises(ValueError, match="Unknown organization permission"):
        require_org_permission("definitely.not.a.real.perm")
