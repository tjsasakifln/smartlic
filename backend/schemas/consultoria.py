"""CONSULT-001: Pydantic models for Consultant Seats feature."""

from typing import Optional
from pydantic import BaseModel, Field


class ConsultantClientCreate(BaseModel):
    client_email: str = Field(..., min_length=1, max_length=320)


class ConsultantClientResponse(BaseModel):
    id: str
    consultant_id: str
    client_id: Optional[str] = None
    client_email: Optional[str] = None
    status: str
    created_at: str


class ConsultantClientListResponse(BaseModel):
    clients: list[ConsultantClientResponse]
    total: int
    active_count: int


class ConsultantShareCreate(BaseModel):
    resource_type: str = Field(..., pattern=r"^(busca|pipeline|analise)$")
    resource_id: str = Field(..., min_length=1)


class ConsultantShareResponse(BaseModel):
    id: str
    consultant_id: str
    client_id: str
    resource_type: str
    resource_id: str
    shared_at: str


class ConsultantInviteResponse(BaseModel):
    invite_url: str
    expires_at: str


class InviteClientRequest(BaseModel):
    client_email: str = Field(..., min_length=1, max_length=320)
