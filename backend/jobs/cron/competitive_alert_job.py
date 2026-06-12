"""COMPINT-012 (#1666): Competitive Alert ARQ job — detection + email digest.

Scans competitor watchlists stored in competitive_alerts table and detects
new activity (new contracts, new UFs, new agencies) for monitored CNPJs.

Runs 3x/day via ARQ cron (08/14/20 UTC). Sends weekly email digest on
Mondays via Resend.

Design:
  - Reads enabled alerts from competitive_alerts grouped by competitor_cnpj
  - Queries pncp_supplier_contracts for new activity (last 24h for daily,
    last 7d for weekly digest)
  - Stores detected events back into competitive_alerts.metadata
  - Weekly digest aggregates last 7 days and sends HTML email via Resend
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

_WEEKLY_DIGEST_WEEKDAY = 0  # Monday
_WEEKLY_DIGEST_HOUR_UTC = 11  # 08:00 BRT


async def run_competitive_alert_detection() -> dict:
    """ARQ job: check for new competitor activity and store events.

    Runs 3x/day (08/14/20 UTC). For each enabled alert, checks if the
    competitor has new contracts since the last check.

    Returns a summary dict with counts for monitoring.
    """
    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        now = datetime.now(timezone.utc)

        # Fetch all enabled alerts
        alerts_resp = await sb_execute(
            sb.table("competitive_alerts")
            .select("*")
            .eq("enabled", True)
        )
        alerts = alerts_resp.data or []
        if not alerts:
            return {"processed": 0, "reason": "no_alerts"}

        # Group by competitor CNPJ to batch queries
        by_cnpj: dict[str, list[dict]] = defaultdict(list)
        for alert in alerts:
            cnpj = alert.get("competitor_cnpj", "")
            if cnpj:
                by_cnpj[cnpj].append(alert)

        events_found = 0
        since_24h = (now - timedelta(hours=26)).strftime("%Y-%m-%d")

        for cnpj, cnpj_alerts in by_cnpj.items():
            try:
                # Get supplier's recent contracts (last 26h)
                contracts_resp = await sb_execute(
                    sb.table("pncp_supplier_contracts")
                    .select("ni_fornecedor, nome_fornecedor, data_assinatura, "
                            "valor_global, uf, orgao_nome, orgao_cnpj")
                    .eq("ni_fornecedor", cnpj)
                    .eq("is_active", True)
                    .gte("data_assinatura", since_24h)
                )
                contracts = contracts_resp.data or []
                if not contracts:
                    continue

                # Update metadata for each alert with new events
                for alert in cnpj_alerts:
                    alert_id = alert.get("id")
                    existing_meta = alert.get("metadata", {}) or {}
                    tracked_ids = set(existing_meta.get("tracked_contract_ids", []))

                    # Filter new contracts not yet tracked
                    new_events = []
                    for c in contracts:
                        contract_key = (
                            f"{c.get('data_assinatura', '')}_{c.get('orgao_cnpj', '')}"
                        )
                        if contract_key not in tracked_ids:
                            new_events.append({
                                "contract_key": contract_key,
                                "valor": float(c.get("valor_global", 0) or 0),
                                "orgao": c.get("orgao_nome", ""),
                                "uf": c.get("uf", ""),
                                "data": c.get("data_assinatura", ""),
                            })
                            tracked_ids.add(contract_key)

                    if new_events:
                        events_found += len(new_events)
                        # Update metadata with new tracked IDs
                        updated_meta = dict(existing_meta)
                        updated_meta["tracked_contract_ids"] = list(tracked_ids)
                        updated_meta["last_check"] = now.isoformat()
                        if "recent_events" not in updated_meta:
                            updated_meta["recent_events"] = []
                        updated_meta["recent_events"].extend(new_events)
                        # Keep only last 50 events
                        updated_meta["recent_events"] = updated_meta[
                            "recent_events"
                        ][-50:]

                        await sb_execute(
                            sb.table("competitive_alerts")
                            .update({"metadata": updated_meta})
                            .eq("id", alert_id),
                            category="write",
                        )
            except Exception as exc:
                logger.warning(
                    "Competitive alert detection failed for CNPJ %s: %s",
                    cnpj, exc,
                )
                continue

        return {
            "processed": len(alerts),
            "events_found": events_found,
            "unique_cnpjs": len(by_cnpj),
        }
    except Exception as exc:
        logger.error("Competitive alert detection failed: %s", exc)
        return {"processed": 0, "events_found": 0, "error": str(exc)}


async def run_competitive_alert_weekly_digest() -> dict:
    """ARQ weekly cron job: aggregate alerts and send email digest.

    Runs Mondays 11:00 UTC (08:00 BRT). For each user with enabled alerts,
    compiles a weekly summary and sends HTML email via Resend.
    """
    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        now = datetime.now(timezone.utc)
        since_7d = (now - timedelta(days=7)).isoformat()

        # Fetch all enabled alerts
        alerts_resp = await sb_execute(
            sb.table("competitive_alerts")
            .select("*, profiles!inner(email, nome)")
            .eq("enabled", True)
        )
        rows = alerts_resp.data or []
        if not rows:
            return {"sent": 0, "reason": "no_alerts"}

        # Group by user
        by_user: dict[str, dict] = {}
        for row in rows:
            uid = row.get("user_id", "")
            if uid not in by_user:
                profile = row.get("profiles", {}) or {}
                by_user[uid] = {
                    "email": profile.get("email", ""),
                    "nome": profile.get("nome", ""),
                    "events": [],
                }
            meta = row.get("metadata", {}) or {}
            recent = meta.get("recent_events", []) or []
            for ev in recent:
                if ev.get("data", "") >= since_7d[:10]:
                    by_user[uid]["events"].append({
                        **ev,
                        "competitor_cnpj": row.get("competitor_cnpj", ""),
                        "alert_type": row.get("alert_type", "new_contract"),
                    })

        sent_count = 0
        for uid, data in by_user.items():
            if not data["events"] or not data["email"]:
                continue
            try:
                await _send_digest_email(
                    email=data["email"],
                    nome=data["nome"],
                    events=data["events"],
                )
                sent_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to send weekly digest to %s: %s",
                    data["email"], exc,
                )

        return {"sent": sent_count, "total_users": len(by_user)}
    except Exception as exc:
        logger.error("Competitive weekly digest failed: %s", exc)
        return {"sent": 0, "error": str(exc)}


async def _send_digest_email(
    email: str,
    nome: str,
    events: list[dict],
) -> None:
    """Send weekly competitive alert digest via Resend."""
    from email_service import send_email

    event_rows = ""
    for ev in events[:20]:  # Max 20 events per digest
        valor = ev.get("valor", 0)
        valor_str = (
            f"R$ {valor:,.0f}".replace(",", ".")
            if valor
            else "Valor não informado"
        )
        event_rows += f"""
        <tr>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                {ev.get('competitor_cnpj', '')}
            </td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                {ev.get('alert_type', 'new_contract')}
            </td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                {ev.get('orgao', '-')}
            </td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                {valor_str}
            </td>
            <td style="padding:8px;border-bottom:1px solid #eee;">
                {ev.get('uf', '-')}
            </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
    <div style="background:#1a365d;color:white;padding:20px;text-align:center;">
        <h2>Seus alertas da semana</h2>
        <p>Atualização de concorrentes monitorados</p>
    </div>
    <div style="padding:20px;">
        <p>Olá {nome.split()[0] if nome else 'usuário'},</p>
        <p>
            Nos últimos 7 dias, detectamos {len(events)} atividade(s)
            nos concorrentes que você monitora:
        </p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0;">
            <thead>
                <tr style="background:#f7fafc;">
                    <th style="padding:8px;text-align:left;">CNPJ</th>
                    <th style="padding:8px;text-align:left;">Tipo</th>
                    <th style="padding:8px;text-align:left;">Órgão</th>
                    <th style="padding:8px;text-align:left;">Valor</th>
                    <th style="padding:8px;text-align:left;">UF</th>
                </tr>
            </thead>
            <tbody>
                {event_rows}
            </tbody>
        </table>
        <p style="color:#718096;font-size:12px;">
            Acesse o SmartLic para ver os detalhes completos.
        </p>
    </div>
    <div style="background:#f7fafc;padding:16px;text-align:center;font-size:12px;color:#a0aec0;">
        <p>SmartLic — Inteligência em Licitações Públicas</p>
        <p>
            <a href="https://smartlic.tech/alerts/competitors"
               style="color:#4299e1;text-decoration:none;">
                Gerenciar alertas
            </a>
        </p>
    </div>
</body>
</html>"""

    await send_email(
        to=email,
        subject="SmartLic — Seus alertas da semana",
        html=html,
    )


async def start_competitive_alert_task() -> list:
    """Register competitive alert ARQ cron jobs.

    Returns list of cron configs for the ARQ worker.
    """
    try:
        from arq.cron import cron as _arq_cron
    except ImportError:
        logger.warning("arq not available — competitive alert cron not registered")
        return []

    return [
        _arq_cron(
            run_competitive_alert_detection,
            hour={8, 14, 20},
            minute=0,
            timeout=600,
            description="COMPINT-012: Competitive alert detection (3x/day)",
        ),
        _arq_cron(
            run_competitive_alert_weekly_digest,
            weekday={_WEEKLY_DIGEST_WEEKDAY},
            hour={_WEEKLY_DIGEST_HOUR_UTC},
            minute=0,
            timeout=300,
            description="COMPINT-012: Weekly competitive alert digest",
        ),
    ]
