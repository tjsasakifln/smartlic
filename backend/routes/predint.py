"""PREDINT-024: Predictive alert CRUD routes."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from auth import require_auth
from log_sanitizer import mask_user_id
from schemas.predint import (
    PredictiveAlertCreate, PredictiveAlertUpdate,
    PredictiveAlertListResponse, PredictiveAlertResponse,
    row_to_alert_response,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predint", tags=["predint"])
_MAX_ALERTS_PER_USER = 50

async def _get_sb():
    from supabase_client import get_supabase, sb_execute
    return get_supabase(), sb_execute

async def _verify_ownership(alert_id: str, user_id: str, sb):
    from supabase_client import sb_execute
    result = await sb_execute(sb.table("predictive_alerts").select("*").eq("id", alert_id).eq("user_id", user_id))
    if not result.data or len(result.data) == 0:
        raise HTTPException(status_code=404, detail="Alerta preditivo nao encontrado.")
    return result.data[0]

@router.post("/alerts", status_code=201, response_model=PredictiveAlertResponse)
async def create_predictive_alert(body: PredictiveAlertCreate, user: dict = Depends(require_auth)):
    user_id = user["id"]; sb, sb_exec = await _get_sb()
    count_r = await sb_exec(sb.table("predictive_alerts").select("id", count="exact").eq("user_id", user_id))
    if (count_r.count or 0) >= _MAX_ALERTS_PER_USER:
        raise HTTPException(status_code=409, detail=f"Limite de {_MAX_ALERTS_PER_USER} alertas preditivos atingido.")
    now = datetime.now(timezone.utc).isoformat()
    insert_data = {
        "user_id": user_id, "sector_id": body.sector_id.strip(),
        "alert_type": body.alert_type, "threshold_value": body.threshold_value,
        "uf": body.uf.strip().upper() if body.uf else None,
        "enabled": True, "created_at": now, "updated_at": now,
    }
    try:
        result = await sb_exec(sb.table("predictive_alerts").insert(insert_data))
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=500, detail="Falha ao criar alerta preditivo.")
        logger.info(f"Predictive alert created for user {mask_user_id(user_id)}: sector={body.sector_id!r}")
        return row_to_alert_response(result.data[0])
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error creating predictive alert: {e}")
        raise HTTPException(status_code=500, detail="Erro ao criar alerta preditivo.")

@router.get("/alerts", response_model=PredictiveAlertListResponse)
async def list_predictive_alerts(enabled_only: bool = False, user: dict = Depends(require_auth)):
    user_id = user["id"]; sb, sb_exec = await _get_sb()
    try:
        query = sb.table("predictive_alerts").select("*").eq("user_id", user_id).order("created_at", desc=True)
        if enabled_only: query = query.eq("enabled", True)
        result = await sb_exec(query)
        alerts = [row_to_alert_response(r) for r in (result.data or [])]
        return PredictiveAlertListResponse(alerts=alerts, total=len(alerts))
    except Exception as e:
        logger.error(f"Error listing predictive alerts: {e}")
        raise HTTPException(status_code=500, detail="Erro ao listar alertas preditivos.")

@router.patch("/alerts/{alert_id}", response_model=PredictiveAlertResponse)
async def update_predictive_alert(alert_id: str, body: PredictiveAlertUpdate, user: dict = Depends(require_auth)):
    user_id = user["id"]; sb, sb_exec = await _get_sb()
    await _verify_ownership(alert_id, user_id, sb)
    payload: dict = {}
    if body.sector_id is not None: payload["sector_id"] = body.sector_id.strip()
    if body.alert_type is not None: payload["alert_type"] = body.alert_type
    if body.threshold_value is not None: payload["threshold_value"] = body.threshold_value
    if body.uf is not None: payload["uf"] = body.uf.strip().upper() if body.uf else None
    if body.enabled is not None: payload["enabled"] = body.enabled
    if not payload: raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        result = await sb_exec(sb.table("predictive_alerts").update(payload).eq("id", alert_id).eq("user_id", user_id))
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Alerta preditivo nao encontrado.")
        return row_to_alert_response(result.data[0])
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error updating predictive alert: {e}")
        raise HTTPException(status_code=500, detail="Erro ao atualizar alerta preditivo.")

@router.delete("/alerts/{alert_id}")
async def delete_predictive_alert(alert_id: str, user: dict = Depends(require_auth)):
    user_id = user["id"]; sb, sb_exec = await _get_sb()
    try:
        result = await sb_exec(sb.table("predictive_alerts").delete().eq("id", alert_id).eq("user_id", user_id))
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Alerta preditivo nao encontrado.")
        logger.info(f"Predictive alert {alert_id[:8]}... deleted for user {mask_user_id(user_id)}")
        return {"success": True, "message": "Alerta preditivo removido com sucesso."}
    except HTTPException: raise
    except Exception as e:
        logger.error(f"Error deleting predictive alert: {e}")
        raise HTTPException(status_code=500, detail="Erro ao remover alerta preditivo.")
