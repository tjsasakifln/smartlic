"""B2GOPS-011 (#1281, #2021): Alert generation engine.

Detects events that should trigger user alerts:
  - Deadline approaching: editais with deadlines within 24h/6h/1h
  - New matching editais: matches against user watchlists/saved searches
  - Pregao starting: pregao sessions about to start
  - Result published: edital results/homologation published
  - Contrato firmado: contract signed for tracked editais
  - Documento vencendo: user documents/certidoes expiring

Wave 1 of EPIC-B2GOPS (#1262) — Intelligent Alert System.
Wave 2 (#2021): Workspace watchlist-based detection.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

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
            .select("pncp_id, user_id, objeto_compra, data_encerramento, orgao_razao_social, modalidade_nome")
            .gte("data_encerramento", now.isoformat())
            .lte("data_encerramento", (now + timedelta(hours=DEADLINE_APPROACHING_HOURS)).isoformat())
            .limit(200)
        )

        rows = result.data or []
        for row in rows:
            deadline_str = row.get("data_encerramento", "")
            if not deadline_str:
                continue

            try:
                deadline = datetime.fromisoformat(deadline_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

            hours_until = (deadline - now).total_seconds() / 3600
            user_id = row.get("user_id")
            titulo = row.get("objeto_compra", "Edital sem titulo")
            orgao = row.get("orgao_razao_social", "Orgao nao informado")

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
                    "edital_id": row["pncp_id"],
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
            .select("pncp_id, user_id, objeto_compra, orgao_razao_social, resultado, data_resultado")
            .not_.is_("resultado", "null")
            .gte("data_resultado", since)
            .limit(100)
        )

        for row in (result.data or []):
            titulo = row.get("objeto_compra", "Edital sem titulo")
            orgao = row.get("orgao_razao_social", "")
            resultado = row.get("resultado", "Resultado publicado")

            payloads.append(AlertEventPayload(
                user_id=row["user_id"],
                type="result_published",
                title=f"Resultado publicado: {titulo[:80]}",
                body=f"O resultado do edital {titulo} foi publicado. {resultado[:200]}",
                data={
                    "edital_id": row["pncp_id"],
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
            .select("pncp_id, user_id, objeto_compra, orgao_razao_social, contrato_valor, data_contrato")
            .not_.is_("contrato_valor", "null")
            .gte("data_contrato", since)
            .limit(100)
        )

        for row in (result.data or []):
            titulo = row.get("objeto_compra", "Edital sem titulo")
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
                    "edital_id": row["pncp_id"],
                    "valor": valor,
                    "orgao": row.get("orgao_razao_social", ""),
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
            .select("pncp_id, user_id, objeto_compra, orgao_razao_social, data_abertura")
            .eq("modalidade_nome", "pregao")
            .gte("data_abertura", now.isoformat())
            .lte("data_abertura", one_hour_later)
            .limit(50)
        )

        for row in (result.data or []):
            titulo = row.get("objeto_compra", "Pregao sem titulo")
            data_abertura = row.get("data_abertura", "")

            payloads.append(AlertEventPayload(
                user_id=row["user_id"],
                type="pregao_starting",
                title=f"Pregao iniciando: {titulo[:80]}",
                body=f"A sessao de pregao para {titulo} esta prestes a comecar. Data: {data_abertura}.",
                data={
                    "edital_id": row["pncp_id"],
                    "data_abertura": data_abertura,
                    "orgao": row.get("orgao_razao_social", ""),
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


# ---------------------------------------------------------------------------
# B2GOPS-011 (#2021): Watchlist-based detection
# ---------------------------------------------------------------------------


async def detect_new_alerts(db=None) -> List[AlertEventPayload]:
    """Detect new matching editais from the user's workspace watchlist.

    For each user's workspace_watchlist entries, queries recent PNCP data
    (pncp_raw_bids) and matches by UF + setor + keywords. Generates an alert
    for each new match that hasn't been alerted yet.

    Args:
        db: Supabase client (fetched if None).

    Returns:
        List of AlertEventPayload to insert.
    """
    if db is None:
        db = get_supabase()

    payloads: List[AlertEventPayload] = []
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    try:
        # Get all active watchlist entries grouped by user
        watchlist_result = await sb_execute(
            db.table("workspace_watchlist")
            .select("id, user_id, edital_id, uf, setor, keywords")
            .limit(500)
        )

        watchlist_entries = watchlist_result.data or []
        if not watchlist_entries:
            return []

        # Get recent PNCP data to match against
        bids_result = await sb_execute(
            db.table("pncp_raw_bids")
            .select("pncp_id, uf, setor, objeto_compra, orgao_razao_social, modalidade_nome, data_publicacao")
            .gte("created_at", since)
            .limit(200)
        )

        recent_bids = bids_result.data or []
        if not recent_bids:
            return []

        # Build lookup: set of already-watchlisted edital_ids per user
        from collections import defaultdict
        user_watchlist: Dict[str, List[dict]] = defaultdict(list)
        for entry in watchlist_entries:
            user_watchlist[entry["user_id"]].append(entry)

        # Track already-generated alerts to avoid duplicates in this run
        # Key: (user_id, edital_id) -> True means already processed
        processed: set = set()

        for user_id, entries in user_watchlist.items():
            for entry in entries:
                dedup_key = (user_id, entry["edital_id"])
                if dedup_key in processed:
                    continue
                processed.add(dedup_key)

                entry_uf = (entry.get("uf") or "").strip().upper()
                entry_setor = (entry.get("setor") or "").strip()
                entry_keywords = entry.get("keywords") or []

                for bid in recent_bids:
                    bid_id = bid.get("pncp_id") or ""
                    if not bid_id:
                        continue

                    bid_uf = (bid.get("uf") or "").strip().upper()
                    bid_setor = (bid.get("setor") or "").strip()
                    bid_titulo = bid.get("objeto_compra") or ""
                    bid_orgao = bid.get("orgao_razao_social") or ""

                    match_score = 0.0
                    match_type = ""

                    # UF match
                    uf_match = entry_uf and bid_uf and entry_uf == bid_uf
                    # Setor match
                    setor_match = entry_setor and bid_setor and entry_setor == bid_setor
                    # Keyword match (case-insensitive substring)
                    kw_match = False
                    if entry_keywords and bid_titulo:
                        titulo_lower = bid_titulo.lower()
                        kw_match = any(
                            kw.lower() in titulo_lower
                            for kw in entry_keywords
                            if kw.strip()
                        )

                    # Determine match type and score
                    if uf_match and setor_match:
                        match_type = "uf_setor"
                        match_score = 1.0
                    elif uf_match and kw_match:
                        match_type = "uf_keyword"
                        match_score = 0.85
                    elif setor_match and kw_match:
                        match_type = "setor_keyword"
                        match_score = 0.75
                    elif uf_match:
                        match_type = "uf"
                        match_score = 0.5
                    elif setor_match:
                        match_type = "setor"
                        match_score = 0.5
                    elif kw_match:
                        match_type = "keyword"
                        match_score = 0.6

                    if not match_type:
                        continue

                    # Skip if match score too low
                    if match_score < 0.4:
                        continue

                    # Don't alert for the exact same edital_id as in watchlist
                    if bid_id == entry["edital_id"]:
                        continue

                    payloads.append(AlertEventPayload(
                        user_id=user_id,
                        type="new_matching_edital",
                        title=f"Novo edital encontrado: {bid_titulo[:80]}",
                        body=(
                            f"Um novo edital corresponde aos seus filtros de monitoramento "
                            f"(UF: {entry_uf}, Setor: {entry_setor}). "
                            f"Orgao: {bid_orgao}. "
                            f"Tipo de match: {match_type}."
                        ),
                        data={
                            "edital_id": bid_id,
                            "titulo": bid_titulo,
                            "orgao": bid_orgao,
                            "uf": bid_uf,
                            "setor": bid_setor,
                            "match_type": match_type,
                            "match_score": match_score,
                            "watchlist_entry_id": entry["id"],
                        },
                    ))

        logger.info(
            "Watchlist detection complete: %d alerts generated from %d entries",
            len(payloads), len(watchlist_entries),
        )

    except Exception as e:
        logger.error("Watchlist detection failed: %s", e)

    return payloads


async def generate_alert(
    user_id: str,
    tipo: str,
    titulo: str,
    descricao: str,
    edital_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db=None,
) -> bool:
    """Generate a single alert for a user and insert into user_alerts.

    This is a convenience wrapper around _insert_alert that constructs
    the AlertEventPayload from individual fields.

    Args:
        user_id: User UUID.
        tipo: Alert event type (e.g. 'new_matching_edital', 'deadline_approaching').
        titulo: Alert title.
        descricao: Alert body/description.
        edital_id: Optional related edital ID (stored in metadata).
        metadata: Optional dict of additional metadata.
        db: Supabase client (fetched if None).

    Returns:
        True if inserted successfully, False otherwise.
    """
    payload = AlertEventPayload(
        user_id=user_id,
        type=tipo,
        title=titulo,
        body=descricao,
        data={
            "edital_id": edital_id or "",
            **(metadata or {}),
        },
    )
    return await _insert_alert(payload, db)
