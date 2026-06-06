"""API Key schemas for self-service key management (API-SELF-001)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    """Request body for POST /v1/api-keys."""

    name: str = Field(..., min_length=1, max_length=100)


class ApiKeyResponse(BaseModel):
    """Public representation of an API key (no plaintext, no hash)."""

    id: str
    name: str
    created_at: datetime
    last_used_at: Optional[datetime] = None


class ApiKeyCreated(BaseModel):
    """Returned ONCE after creation — includes plaintext key."""

    id: str
    name: str
    plaintext_key: str
    created_at: datetime
    message: str = "Guarde esta chave agora. Ela não será exibida novamente."
