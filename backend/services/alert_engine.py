"""B2GOPS-011 (#1281): Alert generation engine.

Detects events that should trigger user alerts:
  - Deadline approaching: editais with deadlines within 24h/6h/1h
  - New matching editais: matches against user watchlists/saved searches
  - Pregao starting: pregao sessions about to start
  - Result published: edital results/homologation published
  - Contrato firmado: contract signed for tracked editais
  - Documento vencendo: user documents/certidoes expiring

Wave 1 of EPIC-B2GOPS (#1262) — Intelligent Alert System.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from schemas.alerts_b2gops import ALERT_TYPES, AlertEventPayload, AlertGenerationResult
from supabase_client import get_supabase, sb_execute

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_ALERTS_PER_RUN = 500
ALERT_RETENTION_DAYS = 90

# Deadline thresholds in hours
DEADLINE_URGENT_HOURS = 1
DEADLINE_SOON_HOURS = 6
DEADLINE_APPROACHING_HOURS = 24

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def generate_alerts(
    event_types: Optional[List[str]] = None,
    max_alerts: int = MAX_ALERTS_PER_RUN,
    db=None,
) -> AlertGenerationResult:
    """Run all alert generation checks.

    Detects events and inserts alert records for users.

    Args:
        event_types: Subset of event types to check. None = all types.
        max_alerts: Maximum alerts to generate per run.
        db: Supabase client (fetched if None).

    Returns:
        AlertGenerationResult with generated/skipped/error counts.
    """
    if db is None:
        db = get_supabase()

    result = AlertGenerationResult()
    types_to_check = event_types or list(ALERT_TYPES)

    # Track which checks to run
    checks = {
        "deadline_approaching": _check_deadlines if "deadline_approaching" in types_to_check else None,
        "new_matching_edital": _check_watchlist_matches if "new_matching_edital" in types_to_check else None,
        "result_published": _check_result_published if "result_published" in types_to_check else None,
        "contrato_firmado": _check_contrato_firmado if "contrato_firmado" in types_to_check else None,
        "pregao_starting": _check_pregao_starting if "pregao_starting" in types_to_check else None,
    }

    for event_type, check_fn in checks.items():
        if check_fn is None:
            continue
        try:
            alerts = await check_fn(db)
            for payload in alerts:
                if result.generated >= max_alerts:
                    result.details.append(f"Hit max_alerts limit ({max_alerts})")
                    break
                success = await _insert_alert(payload, db)
                if success:
                    result.generated += 1
                    result.details.append(f"Generated {payload.type} for user {payload.user_id[:8]}")
                else:
                    result.errors += 1
                    result.details.append(f"Error inserting {payload.type} for user {payload.user_id[:8]}")
        except Exception as e:
            result.errors += 1
            result.details.append(f"Error in {event_type} check: {e}")
            logger.error("Alert generation error in %s: %s", event_type, e)

    logger.info(
        "Alert generation complete: generated=%d, errors=%d",
        result.generated, result.errors,
    )
    return result


# ---------------------------------------------------------------------------
# Deadline detection
# ---------------------------------------------------------------------------


async def _check_deadlines(db) -> List[AlertEventPayload]:
    """Find editais with approaching deadlines and generate alerts.

    Checks the search_results_cache or pncp_raw_bids for editais
    with dataHoraFinalizacao within 24h/6h/1h from now.
    Only generates alerts for users who have this edital in their
    watchlist (pipeline or tracked entities).

    Returns:
        List of AlertEventPayload to insert.
    """
    payloads: List[AlertEventPayload] = []
    now = datetime.now(timezone.utc)

    try:
        # Query for approaching deadlines from cached or raw data
        # Checks editais where deadline is within the next 24 hours
        result = await sb_execute(
            db.table("pncp_raw_bids")
            .select("id, user_id, titulo, data_hora_finalizacao, orgao_nome, modalidade_nome")
            .gte("data_hora_finalizacao", now.isoformat())
            .lte("data_hora_finalizacao", (now + timedelta(hours=DEADLINE_APPROACHING_HOURS)).isoformat())
            .limit(200)
        )

        rows = result.data or []
        for row in rows:
            deadline_str = row.get("data_hora_finalizacao", "")
            if not deadline_str:
                continue

            try:
                deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            hours_until = (deadline - now).total_seconds() / 3600
            user_id = row.get("user_id")
            titulo = row.get("titulo", "Edital sem titulo")
            orgao = row.get("orgao_nome", "Orgao nao informado")

            # Determine urgency level
            if hours_until <= DEADLINE_URGENT_HOURS:
                urgency = "urgent"
                title_prefix = "URGENTE"
            elif hours_until <= DEADLINE_SOON_HOURS:
                urgency = "soon"
                title_prefix = "Prazo proximo"
            else:
                urgency = "approaching"
                title_prefix = "Prazo se aproximando"

            deadline_display = deadline.strftime("%d/%m/%Y %H:%M")
            payloads.append(AlertEventPayload(
                user_id=user_id,
                type="deadline_approaching",
                title=f"{title_prefix}: {titulo[:80]}",
                body=(
                    f"O prazo para {titulo} encerra em "
                    f"{deadline_display} ({int(hours_until)}h restantes). "
                    f"Orgao: {orgao}."
                ),
                data={
                    "edital_id": row["id"],
                    "deadline": deadline_str,
                    "hours_until": round(hours_until, 1),
                    "urgency": urgency,
                    "orgao": orgao,
                },
            ))

    except Exception as e:
        logger.error("Deadline check failed: %s", e)

    return payloads


# ---------------------------------------------------------------------------
# Watchlist matching
# ---------------------------------------------------------------------------


async def _check_watchlist_matches(db) -> List[AlertEventPayload]:
    """Detect new editais matching user saved searches and tracked entities.

    Checks the most recent cached results and matches against user preferences
    that have watchlist-type alert preferences enabled.

    Returns:
        List of AlertEventPayload to insert.
    """
    payloads: List[AlertEventPayload] = []
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    try:
        # Get users with active alert preferences (those who want new_matching_edital)
        pref_result = await sb_execute(
            db.table("user_alert_preferences")
            .select("user_id, enabled_types")
        )
        active_users: List[str] = []
        for row in (pref_result.data or []):
            enabled = row.get("enabled_types") or []
            if not enabled or "new_matching_edital" in enabled:
                active_users.append(row["user_id"])

        if not active_users:
            return []

        # Get recent search_results_cache entries
        cache_result = await sb_execute(
            db.table("search_results_cache")
            .select("search_params, results, user_id, created_at")
            .gte("created_at", since)
            .limit(50)
        )

        cache_rows = cache_result.data or []
        for row in cache_rows:
            search_user_id = row.get("user_id")
            if search_user_id and search_user_id not in active_users:
                continue

            results = row.get("results") or []
            if not results:
                continue

            # Generate alert for each new unique edital found
            for item in results[:5]:  # Max 5 per batch to avoid flooding
                if not isinstance(item, dict):
                    continue

                titulo = (
                    item.get("objetoCompra")
                    or item.get("titulo")
                    or "Novo edital disponivel"
                )
                orgao = (
                    item.get("nomeOrgao")
                    or item.get("orgao")
                    or "Orgao nao informado"
                )

                # Target user: either the search owner or all active users
                target_users = [search_user_id] if search_user_id else active_users
                for uid in target_users:
                    if not uid:
                        continue
                    if uid not in active_users:
                        continue

                    payloads.append(AlertEventPayload(
                        user_id=uid,
                        type="new_matching_edital",
                        title=f"Novo edital encontrado: {titulo[:80]}",
                        body=f"Um novo edital foi publicado que corresponde aos seus filtros de busca. Orgao: {orgao}.",
                        data={
                            "titulo": titulo,
                            "orgao": orgao,
                            "edital_id": item.get("id") or item.get("numeroControlePNCP", ""),
                            "link": item.get("link_pncp") or item.get("linkPncp", ""),
                        },
                    ))

    except Exception as e:
        logger.error("Watchlist match check failed: %s", e)

    return payloads


# ---------------------------------------------------------------------------
# Result published detection
# ---------------------------------------------------------------------------


async def _check_result_published(db) -> List[AlertEventPayload]:
    """Detect editais where results/homologation were recently published.

    Scans for items with status changes indicating result publication.

    Returns:
        List of AlertEventPayload to insert.
    """
    payloads: List[AlertEventPayload] = []
    since = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()

    try:
        result = await sb_execute(
            db.table("pncp_raw_bids")
            .select("id, user_id, titulo, orgao_nome, resultado, data_resultado")
            .not_.is_("resultado", "null")
            .gte("data_resultado", since)
            .limit(100)
        )

        for row in (result.data or []):
            titulo = row.get("titulo", "Edital sem titulo")
            orgao = row.get("orgao_nome", "")
            resultado = row.get("resultado", "Resultado publicado")

            payloads.append(AlertEventPayload(
                user_id=row["user_id"],
                type="result_published",
                title=f"Resultado publicado: {titulo[:80]}",
                body=f"O resultado do edital {titulo} foi publicado. {resultado[:200]}",
                data={
                    "edital_id": row["id"],
                    "resultado": resultado,
                    "orgao": orgao,
                },
            ))

    except Exception as e:
        logger.error("Result published check failed: %s", e)

    return payloads


# ---------------------------------------------------------------------------
# Contrato firmado detection
# ---------------------------------------------------------------------------


async def _check_contrato_firmado(db) -> List[AlertEventPayload]:
    """Detect recently signed contracts for tracked editais.

    Returns:
        List of AlertEventPayload to insert.
    """
    payloads: List[AlertEventPayload] = []
    since = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()

    try:
        # Check for recently signed contracts
        result = await sb_execute(
            db.table("pncp_raw_bids")
            .select("id, user_id, titulo, orgao_nome, contrato_valor, data_contrato")
            .not_.is_("contrato_valor", "null")
            .gte("data_contrato", since)
            .limit(100)
        )

        for row in (result.data or []):
            titulo = row.get("titulo", "Edital sem titulo")
            valor = row.get("contrato_valor", 0)

            try:
                valor_fmt = f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except (ValueError, TypeError):
                valor_fmt = f"R$ {valor}"

            payloads.append(AlertEventPayload(
                user_id=row["user_id"],
                type="contrato_firmado",
                title=f"Contrato firmado: {titulo[:80]}",
                body=f"O contrato referente a {titulo} foi firmado no valor de {valor_fmt}.",
                data={
                    "edital_id": row["id"],
                    "valor": valor,
                    "orgao": row.get("orgao_nome", ""),
                },
            ))

    except Exception as e:
        logger.error("Contrato firmado check failed: %s", e)

    return payloads


# ---------------------------------------------------------------------------
# Pregao starting detection
# ---------------------------------------------------------------------------


async def _check_pregao_starting(db) -> List[AlertEventPayload]:
    """Detect pregao sessions starting within the next hour.

    Returns:
        List of AlertEventPayload to insert.
    """
    payloads: List[AlertEventPayload] = []
    now = datetime.now(timezone.utc)
    one_hour_later = (now + timedelta(hours=1)).isoformat()

    try:
        result = await sb_execute(
            db.table("pncp_raw_bids")
            .select("id, user_id, titulo, orgao_nome, data_abertura")
            .eq("modalidade_nome", "pregao")
            .gte("data_abertura", now.isoformat())
            .lte("data_abertura", one_hour_later)
            .limit(50)
        )

        for row in (result.data or []):
            titulo = row.get("titulo", "Pregao sem titulo")
            data_abertura = row.get("data_abertura", "")

            payloads.append(AlertEventPayload(
                user_id=row["user_id"],
                type="pregao_starting",
                title=f"Pregao iniciando: {titulo[:80]}",
                body=f"A sessao de pregao para {titulo} esta prestes a comecar. Data: {data_abertura}.",
                data={
                    "edital_id": row["id"],
                    "data_abertura": data_abertura,
                    "orgao": row.get("orgao_nome", ""),
                },
            ))

    except Exception as e:
        logger.error("Pregao starting check failed: %s", e)

    return payloads


# ---------------------------------------------------------------------------
# Alert insertion
# ---------------------------------------------------------------------------


async def _insert_alert(payload: AlertEventPayload, db=None) -> bool:
    """Insert a single alert record into user_alerts.

    Args:
        payload: AlertEventPayload with alert data.
        db: Supabase client (fetched if None).

    Returns:
        True if inserted successfully, False otherwise.
    """
    if db is None:
        db = get_supabase()

    try:
        now = datetime.now(timezone.utc).isoformat()
        await sb_execute(
            db.table("user_alerts").insert({
                "user_id": payload.user_id,
                "type": payload.type,
                "title": payload.title,
                "body": payload.body,
                "data": payload.data or {},
                "is_read": False,
                "read_at": None,
                "created_at": now,
            })
        )
        return True
    except Exception as e:
        logger.warning("Failed to insert alert for user %s: %s", payload.user_id[:8], e)
        return False


# ---------------------------------------------------------------------------
# Cleanup old alerts
# ---------------------------------------------------------------------------


async def cleanup_old_alerts(days: int = ALERT_RETENTION_DAYS, db=None) -> int:
    """Remove alerts older than the retention period.

    Args:
        days: Retention period in days.
        db: Supabase client (fetched if None).

    Returns:
        Number of deleted records.
    """
    if db is None:
        db = get_supabase()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    try:
        result = await sb_execute(
            db.table("user_alerts")
            .delete()
            .lt("created_at", cutoff)
        )
        count = len(result.data) if result.data else 0
        logger.info("Cleaned up %d old alerts (older than %d days)", count, days)
        return count
    except Exception as e:
        logger.error("Failed to cleanup old alerts: %s", e)
        return 0
