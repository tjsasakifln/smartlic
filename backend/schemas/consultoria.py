"""CONSULT-001: Pydantic models for Consultant Seats feature.

Models for managing consultant-client relationships and resource sharing
in the Consultoria plan (R$997/mes).
"""

from typing import Optional

from pydantic import BaseModel, Field


class ConsultantClientCreate(BaseModel):
    """Request to invite a client (generates invite link)."""

    client_email: str = Field(..., min_length=1, max_length=320)


class ConsultantClientResponse(BaseModel):
    """Response model for a consultant-client relationship."""

    id: str
    consultant_id: str
    client_id: Optional[str] = None
    client_email: Optional[str] = None
    status: str
    created_at: str


class ConsultantClientListResponse(BaseModel):
    """Wrapper for list of consultant clients."""

    clients: list[ConsultantClientResponse]
    total: int
    active_count: int


class ConsultantShareCreate(BaseModel):
    """Request to share a resource with a client."""

    resource_type: str = Field(..., pattern=r"^(busca|pipeline|analise)$")
    resource_id: str = Field(..., min_length=1)


class ConsultantShareResponse(BaseModel):
    """Response model for a shared resource."""

    id: str
    consultant_id: str
    client_id: str
    resource_type: str
    resource_id: str
    shared_at: str


class ConsultantInviteResponse(BaseModel):
    """Response with invite link details."""

    invite_url: str
    expires_at: str


class InviteClientRequest(BaseModel):
    """Request payload for inviting a client by email."""

    client_email: str = Field(..., min_length=1, max_length=320)
