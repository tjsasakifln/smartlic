"""Webhook integration CRUD — B2GOPS-015 (#1522).

Endpoints:
    POST   /v1/integrations/webhooks         — create a new webhook
    GET    /v1/integrations/webhooks         — list user's webhooks
    PATCH  /v1/integrations/webhooks/{id}    — update a webhook
    DELETE /v1/integrations/webhooks/{id}    — delete a webhook
    POST   /v1/integrations/webhooks/{id}/test  — send test notification
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from auth import require_auth
from schemas.integrations import (
    WebhookChannel,
    WebhookCreate,
    WebhookEvent,
    WebhookResponse,
    WebhookTestResponse,
    WebhookUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_id(user: dict) -> str:
    return user.get("sub") or user.get("id", "")


def _webhook_to_response(row: dict) -> WebhookResponse:
    """Convert a DB row dict to a WebhookResponse schema."""
    events_raw = row.get("events", []) or []
    events = []
    for e in events_raw:
        try:
            events.append(WebhookEvent(e))
        except ValueError:
            logger.warning("Unknown webhook event in DB: %s", e)

    return WebhookResponse(
        id=row.get("id", ""),
        channel=WebhookChannel(row.get("channel", "email")),
        label=row.get("label"),
        webhook_url=row.get("webhook_url"),
        email_target=row.get("email_target"),
        events=events,
        is_active=row.get("is_active", True),
        last_triggered_at=row.get("last_triggered_at"),
        created_at=row.get("created_at", _now_iso()),
    )


def _validate_webhook_create(body: WebhookCreate) -> None:
    """Validate that the required fields are present for the chosen channel."""
    if body.channel in (WebhookChannel.slack, WebhookChannel.teams):
        if not body.webhook_url:
            raise HTTPException(
                status_code=422,
                detail=f"webhook_url is required for {body.channel.value} channel",
            )
    elif body.channel == WebhookChannel.email:
        if not body.email_target:
            raise HTTPException(
                status_code=422,
                detail="email_target is required for email channel",
            )


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.post("/webhooks", response_model=WebhookResponse, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    user: dict = Depends(require_auth),
):
    """Create a new webhook integration (Slack, Teams, or Email)."""
    _validate_webhook_create(body)

    uid = _user_id(user)
    events_str = [e.value for e in body.events]

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("integrations_webhooks")
            .insert({
                "user_id": uid,
                "channel": body.channel.value,
                "label": body.label,
                "webhook_url": body.webhook_url,
                "email_target": body.email_target,
                "events": events_str,
            })
            .select("*"),
            category="write",
        )
    except Exception as exc:
        logger.error("Failed to create webhook: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao criar webhook")

    row = result.data[0] if result.data else {}
    logger.info(
        "Webhook created for user %s (channel=%s, id=%s)",
        uid[:8], body.channel.value, row.get("id", "")[:8],
    )
    return _webhook_to_response(row)


@router.get("/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(user: dict = Depends(require_auth)):
    """List all webhooks for the authenticated user."""
    uid = _user_id(user)

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("integrations_webhooks")
            .select("*")
            .eq("user_id", uid)
            .order("created_at", desc=True)
        )
    except Exception as exc:
        logger.error("Failed to list webhooks: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao listar webhooks")

    return [_webhook_to_response(r) for r in (result.data or [])]


@router.patch("/webhooks/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: UUID,
    body: WebhookUpdate,
    user: dict = Depends(require_auth),
):
    """Update a webhook configuration."""
    uid = _user_id(user)

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()

        # Verify ownership
        check = await sb_execute(
            sb.table("integrations_webhooks")
            .select("id, user_id")
            .eq("id", str(webhook_id))
            .limit(1)
        )
        if not check.data:
            raise HTTPException(status_code=404, detail="Webhook não encontrado")

        row = check.data[0]
        if row.get("user_id") != uid:
            raise HTTPException(
                status_code=403,
                detail="Você não tem permissão para modificar este webhook",
            )

        # Build update payload
        update_data = {}
        if body.label is not None:
            update_data["label"] = body.label
        if body.webhook_url is not None:
            update_data["webhook_url"] = body.webhook_url
        if body.email_target is not None:
            update_data["email_target"] = body.email_target
        if body.events is not None:
            update_data["events"] = [e.value for e in body.events]
        if body.is_active is not None:
            update_data["is_active"] = body.is_active
        update_data["updated_at"] = _now_iso()

        result = await sb_execute(
            sb.table("integrations_webhooks")
            .update(update_data)
            .eq("id", str(webhook_id))
            .eq("user_id", uid)
            .select("*"),
            category="write",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to update webhook %s: %s", str(webhook_id)[:8], exc)
        raise HTTPException(status_code=500, detail="Erro ao atualizar webhook")

    updated = result.data[0] if result.data else {}
    logger.info(
        "Webhook %s updated for user %s",
        str(webhook_id)[:8], uid[:8],
    )
    return _webhook_to_response(updated)


@router.delete("/webhooks/{webhook_id}", status_code=204, response_model=None)
async def delete_webhook(
    webhook_id: UUID,
    user: dict = Depends(require_auth),
):
    """Delete a webhook integration."""
    uid = _user_id(user)

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()

        # Verify ownership
        check = await sb_execute(
            sb.table("integrations_webhooks")
            .select("id, user_id")
            .eq("id", str(webhook_id))
            .limit(1)
        )
        if not check.data:
            raise HTTPException(status_code=404, detail="Webhook não encontrado")

        row = check.data[0]
        if row.get("user_id") != uid:
            raise HTTPException(
                status_code=403,
                detail="Você não tem permissão para excluir este webhook",
            )

        await sb_execute(
            sb.table("integrations_webhooks")
            .delete()
            .eq("id", str(webhook_id))
            .eq("user_id", uid),
            category="write",
        )

        logger.info("Webhook %s deleted by user %s", str(webhook_id)[:8], uid[:8])

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete webhook %s: %s", str(webhook_id)[:8], exc)
        raise HTTPException(status_code=500, detail="Erro ao excluir webhook")


@router.post("/webhooks/{webhook_id}/test", response_model=WebhookTestResponse)
async def test_webhook(
    webhook_id: UUID,
    user: dict = Depends(require_auth),
):
    """Send a test notification to verify the webhook configuration."""
    uid = _user_id(user)

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()

        # Fetch webhook
        check = await sb_execute(
            sb.table("integrations_webhooks")
            .select("*")
            .eq("id", str(webhook_id))
            .limit(1)
        )
        if not check.data:
            raise HTTPException(status_code=404, detail="Webhook não encontrado")

        webhook = check.data[0]
        if webhook.get("user_id") != uid:
            raise HTTPException(
                status_code=403,
                detail="Você não tem permissão para testar este webhook",
            )

        # Send test notification (bypass rate limiting for test)

        test_payload = {
            "title": "🔔 Teste de Notificação SmartLic",
            "description": (
                "Esta é uma notificação de teste para verificar "
                "a configuração do seu webhook."
            ),
            "url": "https://smartlic.tech/conta/integracoes",
            "color": "#4CAF50",
        }

        # Force dispatch without rate limit check for tests
        channel = webhook.get("channel", "")
        success = False
        target: Optional[str] = None

        if channel == "slack":
            from services.webhook_dispatcher import _send_slack

            success = await _send_slack(
                webhook.get("webhook_url", ""), "test", test_payload,
            )
            target = webhook.get("webhook_url", "")[:50]
        elif channel == "teams":
            from services.webhook_dispatcher import _send_teams

            success = await _send_teams(
                webhook.get("webhook_url", ""), "test", test_payload,
            )
            target = webhook.get("webhook_url", "")[:50]
        elif channel == "email":
            from services.webhook_dispatcher import _send_email

            success = await _send_email(
                webhook.get("email_target", ""), "test", test_payload,
            )
            target = webhook.get("email_target", "")

        if not success:
            raise HTTPException(
                status_code=502,
                detail="Falha ao enviar notificação de teste. Verifique a URL do webhook.",
            )

        return WebhookTestResponse(
            message="Notificação de teste enviada com sucesso",
            channel=WebhookChannel(channel),
            target=target,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to test webhook %s: %s", str(webhook_id)[:8], exc)
        raise HTTPException(status_code=500, detail="Erro ao testar webhook")
