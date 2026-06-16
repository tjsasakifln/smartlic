"""SupportSlaLoop — Support SLA breach monitoring (STORY-353)."""
import os
import logging
from datetime import datetime, timezone

from config import MESSAGES_ENABLED, SUPPORT_SLA_ALERT_THRESHOLD_HOURS, SUPPORT_SLA_CHECK_INTERVAL_SECONDS
from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)


class SupportSlaLoop(BaseCronLoop):
    """Monitor unanswered support messages and alert on SLA breaches.

    Runs every SUPPORT_SLA_CHECK_INTERVAL_SECONDS and checks for conversations
    without a first response that have exceeded the SLA threshold in business
    hours.  Sends a summary alert email to ADMIN_EMAIL.
    """

    name = "support_sla"
    interval_seconds = SUPPORT_SLA_CHECK_INTERVAL_SECONDS
    initial_delay = 60.0
    error_retry_seconds = 300.0

    async def run_once(self) -> dict:
        if not MESSAGES_ENABLED:
            return {"checked": 0, "breached": 0, "alerted": 0, "disabled": True}

        try:
            from supabase_client import get_supabase, sb_execute
            from business_hours import calculate_business_hours
            from metrics import SUPPORT_PENDING_MESSAGES

            sb = get_supabase()
            now = datetime.now(timezone.utc)
            result = await sb_execute(
                sb.table("conversations").select("id, user_id, subject, category, created_at")
                .is_("first_response_at", "null").neq("status", "resolvido")
                .order("created_at", desc=False)
            )
            conversations = result.data or []
            SUPPORT_PENDING_MESSAGES.set(len(conversations))
            if not conversations:
                return {"checked": 0, "breached": 0, "alerted": 0}

            breached = []
            for conv in conversations:
                from dateutil.parser import isoparse
                elapsed_hours = calculate_business_hours(isoparse(conv["created_at"]), now)
                if elapsed_hours >= SUPPORT_SLA_ALERT_THRESHOLD_HOURS:
                    breached.append({
                        "id": conv["id"], "subject": conv["subject"],
                        "category": conv["category"], "elapsed_hours": elapsed_hours,
                        "created_at": conv["created_at"],
                    })

            alerted = 0
            if breached:
                admin_email = os.getenv("ADMIN_EMAIL", "tiago.sasaki@gmail.com")
                try:
                    from email_service import send_email_async
                    items_html = "".join(
                        f"<tr><td>{b['subject']}</td><td>{b['category']}</td>"
                        f"<td>{b['elapsed_hours']:.1f}h</td><td>{b['created_at'][:16]}</td></tr>"
                        for b in breached
                    )
                    html = f"""<h2>Alerta de SLA de Suporte</h2>
<p>{len(breached)} mensagem(ns) sem resposta excederam {SUPPORT_SLA_ALERT_THRESHOLD_HOURS}h uteis.</p>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
<tr style="background:#f0f0f0;"><th>Assunto</th><th>Categoria</th><th>Horas uteis</th><th>Criada em</th></tr>
{items_html}</table>
<p>Acesse <a href="https://smartlic.tech/mensagens">SmartLic Mensagens</a> para responder.</p>"""
                    send_email_async(
                        to=admin_email,
                        subject=f"[SLA] {len(breached)} mensagem(ns) sem resposta > {SUPPORT_SLA_ALERT_THRESHOLD_HOURS}h",
                        html=html,
                        tags=[{"name": "category", "value": "sla_alert"}],
                    )
                    alerted = len(breached)
                except Exception as e:
                    logger.error("STORY-353: SLA alert email failed: %s", e)

            logger.info("STORY-353: checked=%d breached=%d alerted=%d", len(conversations), len(breached), alerted)
            return {"checked": len(conversations), "breached": len(breached), "alerted": alerted}
        except Exception as e:
            err_name = type(e).__name__
            err_str = str(e)
            if "CircuitBreaker" in err_name or "ConnectionError" in err_name or "ConnectError" in err_str or "PGRST205" in err_str:
                logger.warning("STORY-353 SLA skipped (Supabase unavailable): %s", e)
            else:
                logger.error("STORY-353 SLA error: %s", e, exc_info=True)
            return {"checked": 0, "breached": 0, "alerted": 0, "error": str(e)}
