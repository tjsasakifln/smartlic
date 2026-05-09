"""RBAC-ORG-002 AC4: Cross-tenant access tests.

Complement to ``test_rbac_org.py`` (which covers the role-rank matrix on a single
org). This suite verifies that a user authenticated against one organization
cannot read or mutate resources of a *different* organization — even if they
hold a high-rank role in their own org.

Threat model
------------

User Alice is OWNER of org A. User Bob is OWNER of org B. The risk being tested
is: Alice attempts to invoke endpoints with ``{org_id} = org B`` (id-injection).

The implementation contract (RBAC-ORG-001 + ADR ``docs/adr/org-rbac.md``):

- ``require_org_role(min_role)`` queries ``organization_members`` with
  ``.eq("org_id", path_org_id).eq("user_id", caller_id).not_.is_("accepted_at", "null")``.
- If no row exists (i.e. caller is not an accepted member of *that* org), a
  403 is raised — NOT 404. 403 prevents timing-leak enumeration of valid org
  ids; 404 would whisper "this org does not exist" vs "you are not in it".

This file asserts the 403 contract for each org-scoped endpoint and the
deny-via-pending-invite case.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient, Response

from auth import require_auth
from main import app

_ORG_AUTH_GET_SUPABASE = "dependencies.org_auth.get_supabase"
_ORG_SVC_GET_SUPABASE = "services.organization_service.get_supabase"

# Caller is owner of org A.
ORG_A = "org-aaa-0001"
# Target is org B (different).
ORG_B = "org-bbb-0002"
TARGET_UID = "user-target-001"

USER_ALICE_OWNS_A = {
    "id": "user-alice-owner-of-a",
    "email": "alice@orga.test",
    "role": "authenticated",
    "aal": "aal1",
}


@pytest.fixture(autouse=True)
def _enable_organizations() -> Generator[None, None, None]:
    with patch("routes.organizations.ORGANIZATIONS_ENABLED", True):
        yield


def _mock_auth_sb_no_membership() -> MagicMock:
    """Supabase mock returning empty data — caller is NOT a member of the org."""
    sb = MagicMock()
    tbl = MagicMock()
    res = MagicMock()
    res.data = []  # not in this org → 403
    tbl.select.return_value = tbl
    tbl.eq.return_value = tbl
    tbl.not_.is_.return_value = tbl
    tbl.limit.return_value = tbl
    tbl.execute.return_value = res
    sb.table.return_value = tbl
    return sb


def _mock_auth_sb_pending_invite() -> MagicMock:
    """Membership row exists but ``accepted_at`` is NULL — pending invite.

    The dependency adds ``.not_.is_("accepted_at", "null")`` to the query,
    so the row is filtered out server-side and ``data`` is empty.
    """
    return _mock_auth_sb_no_membership()


async def _call(
    method: str,
    path: str,
    *,
    auth_sb_factory,
    json_body=None,
) -> Response:
    """Execute one HTTP request as Alice (owner of org A) with a custom dep mock."""
    app.dependency_overrides[require_auth] = lambda: USER_ALICE_OWNS_A
    try:
        with patch(_ORG_AUTH_GET_SUPABASE, return_value=auth_sb_factory()):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                kwargs = {"json": json_body} if json_body is not None else {}
                return await getattr(c, method)(path, **kwargs)
    finally:
        app.dependency_overrides.clear()


# ── Cross-tenant access — caller is owner of A, attempts to reach B ─────────


class TestCrossTenantNotMember:
    """Alice (OWNER of org A) attempts to access org B (where she has no row).

    All five role-gated endpoints must return 403 (not 404, not 200).
    """

    @pytest.mark.asyncio
    async def test_get_org_b_returns_403_not_404(self):
        """GET /v1/organizations/{B} from owner of A → 403.

        Uses 403 (not 404) to avoid leaking valid-org-id existence.
        """
        resp = await _call(
            "get", f"/v1/organizations/{ORG_B}",
            auth_sb_factory=_mock_auth_sb_no_membership,
        )
        assert resp.status_code == 403
        # Confirm the body is the access-denied message, not "not found"
        assert "membro" in resp.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_invite_to_org_b_returns_403(self):
        """POST /v1/organizations/{B}/invite from owner of A → 403."""
        resp = await _call(
            "post", f"/v1/organizations/{ORG_B}/invite",
            auth_sb_factory=_mock_auth_sb_no_membership,
            json_body={"email": "victim@orgb.test"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_remove_org_b_member_returns_403(self):
        """DELETE /v1/organizations/{B}/members/{uid} from owner of A → 403."""
        resp = await _call(
            "delete", f"/v1/organizations/{ORG_B}/members/{TARGET_UID}",
            auth_sb_factory=_mock_auth_sb_no_membership,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_dashboard_org_b_returns_403(self):
        """GET /v1/organizations/{B}/dashboard from owner of A → 403."""
        resp = await _call(
            "get", f"/v1/organizations/{ORG_B}/dashboard",
            auth_sb_factory=_mock_auth_sb_no_membership,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_logo_org_b_returns_403(self):
        """PUT /v1/organizations/{B}/logo from owner of A → 403."""
        resp = await _call(
            "put", f"/v1/organizations/{ORG_B}/logo",
            auth_sb_factory=_mock_auth_sb_no_membership,
            json_body={"logo_url": "https://malicious.test/owned.png"},
        )
        assert resp.status_code == 403


class TestCrossTenantPendingInvite:
    """Caller has a *pending* (un-accepted) membership row in org B.

    The ``require_org_role`` dependency filters by ``accepted_at NOT NULL`` so
    pending invites must NOT bypass enforcement.
    """

    @pytest.mark.asyncio
    async def test_pending_invite_does_not_grant_access(self):
        """GET /v1/organizations/{B} with pending invite → 403."""
        resp = await _call(
            "get", f"/v1/organizations/{ORG_B}",
            auth_sb_factory=_mock_auth_sb_pending_invite,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_pending_invite_cannot_invite_others(self):
        """POST /v1/organizations/{B}/invite with pending invite → 403."""
        resp = await _call(
            "post", f"/v1/organizations/{ORG_B}/invite",
            auth_sb_factory=_mock_auth_sb_pending_invite,
            json_body={"email": "another@orgb.test"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_pending_invite_cannot_view_dashboard(self):
        """GET /v1/organizations/{B}/dashboard with pending invite → 403."""
        resp = await _call(
            "get", f"/v1/organizations/{ORG_B}/dashboard",
            auth_sb_factory=_mock_auth_sb_pending_invite,
        )
        assert resp.status_code == 403


class TestCrossTenantStatusIs403NotLeak:
    """Verify the 403-vs-404 contract for negative cases.

    A 404 leaks information ("this org does not exist") and breaks the
    LGPD-aligned guarantee that org existence is hidden from non-members.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method,path,body",
        [
            ("get", f"/v1/organizations/{ORG_B}", None),
            ("post", f"/v1/organizations/{ORG_B}/invite", {"email": "x@x.com"}),
            ("delete", f"/v1/organizations/{ORG_B}/members/{TARGET_UID}", None),
            ("get", f"/v1/organizations/{ORG_B}/dashboard", None),
            ("put", f"/v1/organizations/{ORG_B}/logo", {"logo_url": "https://x/l.png"}),
        ],
    )
    async def test_non_member_consistently_403_never_404(
        self, method: str, path: str, body
    ):
        """Every role-gated endpoint returns 403 (never 404) for non-member."""
        resp = await _call(
            method, path,
            auth_sb_factory=_mock_auth_sb_no_membership,
            json_body=body,
        )
        assert resp.status_code == 403, (
            f"{method.upper()} {path} returned {resp.status_code}; "
            f"403 is required (404 would leak org existence)."
        )


class TestCrossTenantOrgIdInjection:
    """Path-param injection: caller attempts to mutate via crafted org_id.

    These tests confirm that the org_id from the URL is ALWAYS the source of
    truth for the membership check — never the caller's "home org" inferred
    from auth claims.
    """

    @pytest.mark.asyncio
    async def test_owner_of_a_cannot_dashboard_b_via_path_injection(self):
        """Owner of A crafts a request with B's id in the path — must 403.

        Asserts the dependency uses the **path** ``org_id``, not a cached or
        inferred value.
        """
        # Mock returns no row for org B even though Alice is owner of A.
        resp = await _call(
            "get", f"/v1/organizations/{ORG_B}/dashboard",
            auth_sb_factory=_mock_auth_sb_no_membership,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_of_a_cannot_remove_b_member_via_path_injection(self):
        """Owner of A tries to remove a member from B by crafting the path."""
        resp = await _call(
            "delete", f"/v1/organizations/{ORG_B}/members/{TARGET_UID}",
            auth_sb_factory=_mock_auth_sb_no_membership,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_owner_of_a_cannot_change_b_logo(self):
        """Owner of A tries to change B's logo by id injection."""
        resp = await _call(
            "put", f"/v1/organizations/{ORG_B}/logo",
            auth_sb_factory=_mock_auth_sb_no_membership,
            json_body={"logo_url": "https://attacker.test/defaced.png"},
        )
        assert resp.status_code == 403
