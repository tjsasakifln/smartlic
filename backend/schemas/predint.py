"""PREDINT-024: Pydantic models for predictive alert CRUD routes."""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class PredictiveAlertCreate(BaseModel):
    sector_id: str = Field(..., min_length=1, max_length=60)
    alert_type: str = Field(..., pattern=r"^(volume_spike|new_opportunity|recurrence|deadline_approaching)$")
    threshold_value: float = Field(default=0.0, ge=0)
    uf: Optional[str] = Field(None, min_length=2, max_length=2)

class PredictiveAlertUpdate(BaseModel):
    sector_id: Optional[str] = Field(None, min_length=1, max_length=60)
    alert_type: Optional[str] = Field(None, pattern=r"^(volume_spike|new_opportunity|recurrence|deadline_approaching)$")
    threshold_value: Optional[float] = Field(None, ge=0)
    uf: Optional[str] = Field(None, min_length=2, max_length=2)
    enabled: Optional[bool] = None

class PredictiveAlertResponse(BaseModel):
    id: str; user_id: str; sector_id: str; alert_type: str
    threshold_value: float; uf: Optional[str] = None; enabled: bool
    last_triggered_at: Optional[str] = None; created_at: str; updated_at: str

class PredictiveAlertListResponse(BaseModel):
    alerts: list[PredictiveAlertResponse]; total: int

def row_to_alert_response(row: dict) -> PredictiveAlertResponse:
    return PredictiveAlertResponse(
        id=row["id"], user_id=row["user_id"], sector_id=row["sector_id"],
        alert_type=row["alert_type"],
        threshold_value=float(row.get("threshold_value", 0)),
        uf=row.get("uf"), enabled=row.get("enabled", True),
        last_triggered_at=row.get("last_triggered_at"),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )
