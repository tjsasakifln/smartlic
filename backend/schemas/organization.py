"""Organization schemas — RBAC-ORG-001.

Defines the canonical OrgRole enum used by both the FastAPI dependency
(`backend/dependencies/org_auth.py`) and the route handlers in
`backend/routes/organizations.py`.

Hierarchy (ordinal, low → high privilege):
    viewer (0) < member (1) < owner (2)

A user is authorized for endpoint with min_role=X iff user.role.level >= X.level.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrgRole(str, Enum):
    """Organization role enum.

    Stored as TEXT in `organization_members.role` with CHECK constraint
    enforcing one of these three values.
    """

    VIEWER = "viewer"
    MEMBER = "member"
    OWNER = "owner"

    @property
    def level(self) -> int:
        """Ordinal hierarchy level (higher = more privileged)."""
        return _ROLE_LEVELS[self]

    def __ge__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, OrgRole):
            return self.level >= other.level
        return NotImplemented

    def __gt__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, OrgRole):
            return self.level > other.level
        return NotImplemented

    def __le__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, OrgRole):
            return self.level <= other.level
        return NotImplemented

    def __lt__(self, other: object) -> bool:  # type: ignore[override]
        if isinstance(other, OrgRole):
            return self.level < other.level
        return NotImplemented


_ROLE_LEVELS: dict[OrgRole, int] = {
    OrgRole.VIEWER: 0,
    OrgRole.MEMBER: 1,
    OrgRole.OWNER: 2,
}


class OrganizationMember(BaseModel):
    """A row from `organization_members` joined with the auth context.

    Returned by `require_org_role()` so handlers can read role/org_id
    without an extra DB lookup.
    """

    model_config = ConfigDict(from_attributes=True)

    org_id: str
    user_id: str
    role: OrgRole
    invited_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None


class TransferOwnershipRequest(BaseModel):
    """POST /v1/organizations/{org_id}/transfer-ownership body."""

    target_user_id: str = Field(..., description="The member to promote to owner")
    confirm: bool = Field(False, description="Must be true; UI 2-step confirmation")


class UpdateMemberRoleRequest(BaseModel):
    """PATCH /v1/organizations/{org_id}/members/{user_id}/role body."""

    role: OrgRole


class OrganizationAuditLogEntry(BaseModel):
    """A single row from `organization_audit_log`."""

    id: str
    org_id: str
    actor_user_id: str
    target_user_id: Optional[str] = None
    action: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    created_at: datetime


class OrganizationAuditLogResponse(BaseModel):
    """GET /v1/organizations/{org_id}/audit-log response."""

    entries: list[OrganizationAuditLogEntry]
    total: int
    limit: int
    offset: int
