"""PREDINT-024: ARQ daily job that evaluates predictive alerts and sends notifications."""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from collections import defaultdict
import os

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://smartlic.tech")

logger = logging.getLogger(__name__)
_PREDICTIVE_ALERT_LOCK_KEY = "smartlic:predictive:alerts:lock"
_PREDICTIVE_ALERT_LOCK_TTL = 30 * 60
_MAX_ALERTS_TO_EVALUATE = 100

def mask_user_id(uid: str) -> str:
    return uid[:8] + "..." if uid else "unknown"

async def predictive_alert_job(ctx: dict) -> dict:
    import time as _time
    start = _time.time()
    redis = ctx.get("redis")
    lock_acquired = False
    if redis:
        try:
            lock_acquired = await redis.set(_PREDICTIVE_ALERT_LOCK_KEY, datetime.now(timezone.utc).isoformat(), nx=True, ex=_PREDICTIVE_ALERT_LOCK_TTL)
            if not lock_acquired: return {"status": "skipped", "reason": "lock_held"}
        except Exception as e: logger.warning(f"Redis lock check failed: {e}")
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        alerts_result = await sb_execute(sb.table("predictive_alerts").select("*").eq("enabled", True).limit(_MAX_ALERTS_TO_EVALUATE))
        alerts = alerts_result.data or []
        logger.info(f"Evaluating {len(alerts)} predictive alerts")
        if not alerts: return {"status": "ok", "alerts_evaluated": 0, "events_fired": 0}

        alerts_by_sector = defaultdict(list)
        for a in alerts: alerts_by_sector[a["sector_id"]].append(a)
        total_events = 0; events_by_user = defaultdict(list)

        for sector_id, sector_alerts in alerts_by_sector.items():
            try:
                rr = await sb_execute(sb.rpc("predictive_recorrencia", {"p_sector_id": sector_id, "p_meses_projecao": 3}))
                predictions = rr.data or []
            except Exception as e:
                logger.warning(f"Failed query for sector {sector_id}: {e}")
                continue
            if not predictions: continue

            for alert in sector_alerts:
                aid = alert["id"]; uid = alert["user_id"]
                threshold = float(alert.get("threshold_value", 0))
                a_uf = alert.get("uf"); a_type = alert["alert_type"]
                matching = []
                for pred in predictions:
                    if a_uf and pred.get("uf", "") != a_uf: continue
                    if float(pred.get("valor_estimado", 0)) < threshold: continue
                    if a_type == "volume_spike" and float(pred.get("variacao_anual", 0)) < 0.15: continue
                    if a_type == "recurrence" and float(pred.get("indice_recorrencia", 0)) < 0.5: continue
                    if a_type == "deadline_approaching" and int(pred.get("meses_ate_publicacao", 12)) > 2: continue
                    matching.append(pred)
                if not matching: continue

                for pred in matching[:5]:
                    event = {"alert_id": aid, "user_id": uid, "sector_id": sector_id, "alert_type": a_type, "uf": a_uf,
                             "mensagem": f"Nova oportunidade prevista para {pred.get('mes_estimado','')}: {pred.get('objeto_previsto','Nova oportunidade')} — {pred.get('orgao','Orgao nao identificado')}",
                             "valor_estimado": float(pred.get("valor_estimado", 0)),
                             "mes_estimado": pred.get("mes_estimado", ""), "confidence": float(pred.get("confidence", 0))}
                    events_by_user[uid].append(event)
                    total_events += 1

                try:
                    await sb_execute(sb.table("predictive_alerts").update({"last_triggered_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()}).eq("id", aid))
                except Exception as e: logger.warning(f"Failed update last_triggered_at: {e}")

        emails_sent = 0
        for uid, events in events_by_user.items():
            if not events: continue
            try:
                pr = await sb_execute(sb.table("profiles").select("email, full_name").eq("id", uid).single())
                email = pr.data.get("email", ""); name = pr.data.get("full_name", "Usuario")
                if not email: continue
                from email_service import send_email_async
                html = _render_digest(name, events)
                await send_email_async(to=email, subject=f"SmartLic — {len(events)} oportunidades previstas", html=html)
                emails_sent += 1
            except Exception as e: logger.warning(f"Failed send email to user {mask_user_id(uid)}: {e}")

        elapsed = _time.time() - start
        logger.info(f"Predictive alert job done: {len(alerts)} alerts, {total_events} events, {emails_sent} emails in {elapsed:.1f}s")
        return {"status": "ok", "alerts_evaluated": len(alerts), "events_fired": total_events, "emails_sent": emails_sent, "elapsed_seconds": round(elapsed, 1)}
    except Exception as e:
        logger.error(f"Predictive alert job failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        if lock_acquired and redis:
            try: await redis.delete(_PREDICTIVE_ALERT_LOCK_KEY)
            except: pass

def _render_digest(user_name: str, events: list[dict]) -> str:
    items = ""
    for ev in events[:10]:
        valor = f"R$ {ev['valor_estimado']:,.0f}".replace(",", ".")
        items += f"<tr><td style='padding:12px 16px;border-bottom:1px solid #e5e7eb;'><p style='margin:0 0 4px;font-size:14px;color:#111827;'>{ev['mensagem']}</p><p style='margin:0;font-size:12px;color:#6b7280;'>Valor: {valor} | Confianca: {ev.get('confidence',0):.0f}%{' | UF: '+ev.get('uf','') if ev.get('uf') else ''}</p></td></tr>"
    return f"""<!DOCTYPE html><html lang="pt-BR"><body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"><table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;"><tr><td align="center" style="padding:24px 16px;"><table width="600" cellpadding="0" cellspacing="0" style="background-color:#fff;border-radius:8px;overflow:hidden;"><tr><td style="padding:32px 24px 16px;text-align:center;background-color:#1a73e8;"><h1 style="margin:0;font-size:20px;color:#fff;">Oportunidades Previstas</h1><p style="margin:8px 0 0;font-size:14px;color:#fff;opacity:0.9;">Ola, {user_name}</p></td></tr><tr><td style="padding:24px;"><p style="margin:0 0 16px;font-size:14px;color:#374151;">Com base em analise preditiva, identificamos oportunidades que devem surgir nos proximos meses:</p><table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:6px;">{items}</table></td></tr><tr><td style="padding:16px 24px 24px;text-align:center;"><a href="{FRONTEND_URL}/radar" style="display:inline-block;padding:10px 24px;background-color:#1a73e8;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;">Ver no Radar</a></td></tr><tr><td style="padding:16px 24px;text-align:center;border-top:1px solid #e5e7eb;"><p style="margin:0;font-size:11px;color:#9ca3af;">SmartLic — Plataforma de Inteligencia em Licitacoes Publicas</p></td></tr></table></td></tr></table></body></html>"""
