"""
STORY-278 AC2 + DIGEST-002 (#1411): Digest Service — personalized digest builder.

DIGEST-002 adds sector-based query with tier limits, frequency-based lookback
windows, and zero-results fallback.

Queries:
  - build_digest_for_user() — legacy, uses search_results_cache
  - build_personalized_digest() — DIGEST-002, queries datalake per sector

Usage:
    from services.digest_service import build_digest_for_user
    from services.digest_service import build_personalized_digest

    opportunities = await build_digest_for_user(user_id, max_items=10)
    digest = await build_personalized_digest(user_id)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from supabase_client import sb_execute

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DIGEST-002: Tier limits and frequency lookback windows
# ---------------------------------------------------------------------------

# Max opportunities per sector per plan tier
TIER_LIMITS: dict[str, int] = {
    "free_trial": 5,
    "smartlic_pro": 20,
    "smartlic_consulting": 20,
    "consultoria": 20,
    "master": 20,
}

# Lookback window per frequency (used by build_personalized_digest)
FREQUENCY_WINDOWS: dict[str, timedelta] = {
    "daily": timedelta(days=1),
    "twice_weekly": timedelta(days=3),
    "weekly": timedelta(days=7),
}


async def _get_user_profile_context(user_id: str, db) -> Optional[dict]:
    """Fetch user's profile_context from profiles table.

    Returns:
        Dict with context_data keys (setor_id, ufs_atuacao, etc.) or None.
    """
    try:
        result = await sb_execute(
            db.table("profiles").select(
                "context_data"
            ).eq("id", user_id).single()
        )
        return (result.data or {}).get("context_data") or {}
    except Exception as e:
        logger.warning(f"Failed to get profile context for digest: user_id={user_id[:8]}, error={e}")
        return None


async def _get_alert_preferences(user_id: str, db) -> Optional[dict]:
    """Fetch user's alert preferences.

    Returns:
        Dict with frequency, enabled, last_digest_sent_at or None.
    """
    try:
        result = await sb_execute(
            db.table("alert_preferences").select(
                "frequency, enabled, last_digest_sent_at"
            ).eq("user_id", user_id).single()
        )
        return result.data
    except Exception:
        return None


def _is_digest_due(prefs: dict) -> bool:
    """Check if user is due for a digest based on frequency and last sent time.

    Args:
        prefs: Alert preferences dict with frequency and last_digest_sent_at.

    Returns:
        True if digest should be sent now.
    """
    if not prefs.get("enabled", True):
        return False

    frequency = prefs.get("frequency", "daily")
    if frequency not in ("daily", "twice_weekly", "weekly"):
        return False

    last_sent_str = prefs.get("last_digest_sent_at")
    if not last_sent_str:
        return True  # Never sent — always due

    try:
        if isinstance(last_sent_str, str):
            # Handle ISO format with timezone
            last_sent = datetime.fromisoformat(last_sent_str.replace("Z", "+00:00"))
        else:
            last_sent = last_sent_str
    except (ValueError, TypeError):
        return True  # Can't parse — send anyway

    now = datetime.now(timezone.utc)
    elapsed = now - last_sent

    if frequency == "daily":
        return elapsed >= timedelta(hours=20)  # 20h buffer to avoid timezone edge cases
    elif frequency == "twice_weekly":
        return elapsed >= timedelta(days=3)  # ~2x per week = every 3-4 days
    elif frequency == "weekly":
        return elapsed >= timedelta(days=6)  # 6-day buffer
    else:
        return False


async def _query_recent_opportunities(
    db,
    setor_id: str | None,
    ufs: list[str] | None,
    since: datetime | None,
    max_items: int = 10,
) -> list[dict]:
    """Query search_results_cache for recent opportunities matching user profile.

    Args:
        db: Supabase client.
        setor_id: User's sector ID filter.
        ufs: User's UFs filter.
        since: Only include results newer than this timestamp.
        max_items: Max opportunities to return.

    Returns:
        List of opportunity dicts.
    """
    try:
        query = db.table("search_results_cache").select(
            "results, search_params, created_at"
        ).order("created_at", desc=True).limit(50)

        if since:
            query = query.gte("created_at", since.isoformat())

        result = await sb_execute(query)

        if not result.data:
            return []

        # Flatten all results and filter by setor/UFs
        all_opps = []
        seen_ids = set()

        for row in result.data:
            results = row.get("results") or []
            params = row.get("search_params") or {}

            # Filter by setor if user has one
            if setor_id and params.get("setor_id") and params["setor_id"] != setor_id:
                continue

            for item in results:
                if not isinstance(item, dict):
                    continue

                # Dedup by PNCP ID or object hash
                item_id = item.get("id") or item.get("numeroControlePNCP") or id(item)
                if item_id in seen_ids:
                    continue
                seen_ids.add(item_id)

                # Filter by UF if user has UF preference
                item_uf = item.get("uf") or item.get("unidadeFederativa", "")
                if ufs and item_uf and item_uf not in ufs:
                    continue

                all_opps.append({
                    "titulo": item.get("objetoCompra") or item.get("titulo") or "Sem titulo",
                    "orgao": item.get("nomeOrgao") or item.get("orgao") or "Nao informado",
                    "valor_estimado": float(item.get("valorTotalEstimado") or 0),
                    "uf": item_uf,
                    "viability_score": item.get("viability_score"),
                    "data_publicacao": item.get("dataPublicacaoPncp") or item.get("data_publicacao"),
                })

        # Sort: viability_score DESC (None at end), then valor_estimado DESC
        all_opps.sort(
            key=lambda x: (
                x.get("viability_score") or 0.0,
                x.get("valor_estimado") or 0.0,
            ),
            reverse=True,
        )

        return all_opps[:max_items]

    except Exception as e:
        logger.error(f"Failed to query opportunities for digest: {e}")
        return []


async def build_digest_for_user(
    user_id: str,
    db=None,
    max_items: int = 10,
) -> dict | None:
    """Build a digest payload for a single user.

    STORY-278 AC2: Main entry point for digest generation.

    Args:
        user_id: User UUID.
        db: Supabase client (fetched if None).
        max_items: Max opportunities per digest email.

    Returns:
        Dict with keys: user_name, opportunities, stats, email.
        None if user is not due for digest or has no profile.
    """
    if db is None:
        from supabase_client import get_supabase
        db = get_supabase()

    # Check alert preferences
    prefs = await _get_alert_preferences(user_id, db)
    if prefs and not _is_digest_due(prefs):
        return None

    # Get profile context
    profile_ctx = await _get_user_profile_context(user_id, db)
    if profile_ctx is None:
        return None

    setor_id = profile_ctx.get("setor_id")
    ufs = profile_ctx.get("ufs_atuacao")

    # Determine time window
    last_sent_str = (prefs or {}).get("last_digest_sent_at")
    if last_sent_str:
        try:
            since = datetime.fromisoformat(
                last_sent_str.replace("Z", "+00:00") if isinstance(last_sent_str, str) else str(last_sent_str)
            )
        except (ValueError, TypeError):
            since = datetime.now(timezone.utc) - timedelta(days=1)
    else:
        since = datetime.now(timezone.utc) - timedelta(days=1)

    # Query opportunities
    opportunities = await _query_recent_opportunities(
        db=db,
        setor_id=setor_id,
        ufs=ufs,
        since=since,
        max_items=max_items,
    )

    # Get user email and name
    try:
        user_data = db.auth.admin.get_user_by_id(user_id)
        email = user_data.user.email if user_data and user_data.user else None
        user_name = email.split("@")[0] if email else "Usuario"
    except Exception:
        email = None
        user_name = "Usuario"

    if not email:
        logger.debug(f"No email found for user {user_id[:8]} — skipping digest")
        return None

    # Calculate stats
    total_valor = sum(opp.get("valor_estimado", 0) for opp in opportunities)
    setor_nome = setor_id or "seu setor"

    # Map sector IDs to friendly names (subset)
    _SECTOR_NAMES = {
        "vestuario": "Vestuario e Uniformes",
        "alimentos": "Alimentos",
        "informatica": "TI e Hardware",
        "software_desenvolvimento": "Desenvolvimento de Software",
        "software_licencas": "Licencas de Software",
        "engenharia": "Engenharia",
        "medicamentos": "Medicamentos",
        "equipamentos_medicos": "Equipamentos Medicos",
        "insumos_hospitalares": "Insumos Hospitalares",
        "servicos_prediais": "Servicos Prediais",
        "produtos_limpeza": "Produtos de Limpeza",
        "mobiliario": "Mobiliario",
    }
    setor_nome = _SECTOR_NAMES.get(setor_id, setor_id or "seu setor")

    return {
        "user_id": user_id,
        "user_name": user_name,
        "email": email,
        "opportunities": opportunities,
        "stats": {
            "total_novas": len(opportunities),
            "setor_nome": setor_nome,
            "total_valor": total_valor,
        },
    }


async def get_digest_eligible_users(db=None) -> list[dict]:
    """Query all users eligible for digest right now.

    Returns list of dicts with user_id, frequency, last_digest_sent_at.
    """
    if db is None:
        from supabase_client import get_supabase
        db = get_supabase()

    try:
        result = await sb_execute(
            db.table("alert_preferences").select(
                "user_id, frequency, enabled, last_digest_sent_at"
            ).eq("enabled", True).neq("frequency", "off")
        )

        if not result.data:
            return []

        # Filter by schedule
        eligible = []
        for prefs in result.data:
            if _is_digest_due(prefs):
                eligible.append(prefs)

        return eligible
    except Exception as e:
        logger.error(f"Failed to query eligible digest users: {e}")
        return []


async def mark_digest_sent(user_id: str, db=None) -> None:
    """Update last_digest_sent_at after successful send."""
    if db is None:
        from supabase_client import get_supabase
        db = get_supabase()

    try:
        now = datetime.now(timezone.utc)
        await sb_execute(
            db.table("alert_preferences").update({
                "last_digest_sent_at": now.isoformat(),
            }).eq("user_id", user_id)
        )
    except Exception as e:
        logger.warning(f"Failed to update last_digest_sent_at for {user_id[:8]}: {e}")


# ============================================================================
# DIGEST-002 (#1411): Personalized digest builder
# ============================================================================


async def get_user_plan_tier(user_id: str, db=None) -> str:
    """Determine user's plan tier for digest limit enforcement.

    Checks ``user_subscriptions`` (active subscription) first, then falls
    back to ``profiles.plan_type``. Returns ``"free_trial"`` as default.

    Args:
        user_id: User UUID.
        db: Supabase client (fetched if None).

    Returns:
        Plan tier string (e.g. ``"free_trial"``, ``"smartlic_pro"``).
    """
    if db is None:
        from supabase_client import get_supabase
        db = get_supabase()

    # Check active subscription first
    try:
        result = await sb_execute(
            db.table("user_subscriptions")
            .select("plan_id")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .limit(1)
        )
        if result.data:
            plan_id = result.data[0]["plan_id"]
            if "consulting" in plan_id or "consultoria" in plan_id:
                return "smartlic_consulting"
            return "smartlic_pro"
    except Exception as e:
        logger.warning(
            "Failed to get subscription tier for user %s: %s",
            user_id[:8], e,
        )

    # Fallback to profile plan_type
    try:
        result = await sb_execute(
            db.table("profiles")
            .select("plan_type")
            .eq("id", user_id)
            .limit(1)
        )
        if result.data:
            pt = result.data[0].get("plan_type", "free_trial")
            return pt or "free_trial"
    except Exception as e:
        logger.warning(
            "Failed to get profile plan_type for user %s: %s",
            user_id[:8], e,
        )

    return "free_trial"


async def get_user_sectors(user_id: str, db=None) -> list[str]:
    """Get user's selected sectors for digest personalization.

    Checks ``user_sector_affinity`` first (multi-sector support), then falls
    back to ``profiles.context_data`` / ``profiles.sector`` (legacy single-sector).

    Args:
        user_id: User UUID.
        db: Supabase client (fetched if None).

    Returns:
        List of sector IDs (e.g. ``["vestuario", "informatica"]``).
    """
    if db is None:
        from supabase_client import get_supabase
        db = get_supabase()

    # 1. Check user_sector_affinity (primary — multi-sector)
    try:
        result = await sb_execute(
            db.table("user_sector_affinity")
            .select("sector_id")
            .eq("user_id", user_id)
        )
        if result.data:
            sectors = [r["sector_id"] for r in result.data if r.get("sector_id")]
            if sectors:
                return sectors
    except Exception as e:
        logger.warning(
            "Failed to get user_sector_affinity for %s: %s",
            user_id[:8], e,
        )

    # 2. Fallback: profile context_data (legacy single-sector)
    try:
        result = await sb_execute(
            db.table("profiles")
            .select("context_data, sector")
            .eq("id", user_id)
            .limit(1)
        )
        if result.data:
            profile = result.data[0]
            ctx = profile.get("context_data") or {}
            if ctx.get("setor_id"):
                return [ctx["setor_id"]]
            if profile.get("sector"):
                return [profile["sector"]]
    except Exception as e:
        logger.warning(
            "Failed to get profile sector for %s: %s",
            user_id[:8], e,
        )

    return []


async def get_user_frequency(user_id: str, db=None) -> str:
    """Get user's digest frequency from ``alert_preferences``.

    Args:
        user_id: User UUID.
        db: Supabase client (fetched if None).

    Returns:
        Frequency string: ``"daily"``, ``"twice_weekly"``, ``"weekly"``, or
        ``"daily"`` as default.
    """
    if db is None:
        from supabase_client import get_supabase
        db = get_supabase()

    try:
        result = await sb_execute(
            db.table("alert_preferences")
            .select("frequency")
            .eq("user_id", user_id)
            .limit(1)
        )
        if result.data:
            return result.data[0].get("frequency", "daily")
    except Exception as e:
        logger.warning(
            "Failed to get frequency for user %s: %s",
            user_id[:8], e,
        )

    return "daily"


async def find_opportunities_for_sector(
    sector_id: str,
    lookback_days: int,
    limit: int,
    db=None,
) -> list[dict]:
    """Query the datalake for new opportunities matching a sector.

    Uses the sector's keywords as tsquery terms via ``query_datalake``,
    searching across all 27 UFs within the lookback window.

    Args:
        sector_id: Sector ID (e.g. ``"vestuario"``).
        lookback_days: Number of days to look back.
        limit: Max opportunities to return (tier-enforced upstream).
        db: Supabase client (used only for sector data, not direct query).

    Returns:
        List of normalized opportunity dicts. Empty list on failure.
    """
    from datalake_query import query_datalake
    from sectors import SECTORS
    from unified_schemas.unified import VALID_UFS

    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    today = datetime.now(timezone.utc).isoformat()

    # Get sector keywords for datalake FTS query
    sector_obj = SECTORS.get(sector_id)
    keywords: list[str] | None = None
    if sector_obj and hasattr(sector_obj, "keywords") and sector_obj.keywords:
        keywords = list(sector_obj.keywords)

    all_ufs = sorted(VALID_UFS)

    try:
        results = await query_datalake(
            ufs=all_ufs,
            data_inicial=since[:10],
            data_final=today[:10],
            keywords=keywords,
            limit=limit * 3,  # Request extra to account for post-filtering
            modo_busca="publicacao",
        )

        # Normalize results to match the format used by digest consumers
        normalized = []
        seen_ids: set[str] = set()
        for item in (results or []):
            if not isinstance(item, dict):
                continue
            item_id = (
                item.get("numeroControlePNCP")
                or item.get("codigoCompra")
                or item.get("id")
                or ""
            )
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            normalized.append({
                "id": item_id,
                "titulo": (
                    item.get("objetoCompra")
                    or item.get("titulo")
                    or "Sem titulo"
                ),
                "orgao": (
                    item.get("nomeOrgao")
                    or item.get("orgao")
                    or "Nao informado"
                ),
                "valor_estimado": float(
                    item.get("valorTotalEstimado")
                    or item.get("valor_estimado")
                    or 0
                ),
                "uf": item.get("uf") or item.get("unidadeFederativa", ""),
                "modalidade": (
                    item.get("modalidadeNome")
                    or item.get("modalidade")
                    or ""
                ),
                "data_publicacao": (
                    item.get("dataPublicacaoFormatted")
                    or item.get("dataPublicacao")
                    or ""
                ),
                "link_pncp": item.get("linkSistemaOrigem") or "",
                "viability_score": item.get("viability_score"),
            })

        # Sort by viability_score DESC, then valor_estimado DESC
        normalized.sort(
            key=lambda x: (
                x.get("viability_score") or 0.0,
                x.get("valor_estimado") or 0.0,
            ),
            reverse=True,
        )

        return normalized[:limit]

    except Exception as e:
        logger.error(
            "Failed to query opportunities for sector %s: %s",
            sector_id, e,
        )
        return []


async def build_personalized_digest(
    user_id: str,
    db=None,
) -> dict:
    """Build a personalized digest for a user by sector.

    DIGEST-002: Queries the datalake per sector, applies tier-based limits
    and frequency-based lookback windows. Returns structured digest with
    per-sector opportunity lists.

    Args:
        user_id: User UUID.
        db: Supabase client (fetched if None).

    Returns:
        Digest dict with structure::
            {
                "user_id": str,
                "frequency": str,
                "tier": str,
                "sectors": {sector_id: {"opportunities": [...], "count": int}},
                "total_opportunities": int,
                "has_content": bool,
                "generated_at": str (ISO 8601)
            }
    """
    if db is None:
        from supabase_client import get_supabase
        db = get_supabase()

    tier = await get_user_plan_tier(user_id, db)
    sectors = await get_user_sectors(user_id, db)
    frequency = await get_user_frequency(user_id, db)

    if not sectors:
        logger.info("No sectors configured for user %s", user_id[:8])
        return {
            "user_id": user_id,
            "frequency": frequency,
            "tier": tier,
            "sectors": {},
            "total_opportunities": 0,
            "has_content": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    limit = TIER_LIMITS.get(tier, 5)
    lookback_window = FREQUENCY_WINDOWS.get(frequency, timedelta(days=1))
    lookback_days = lookback_window.days

    digest_sectors: dict[str, dict] = {}
    total_opps = 0

    for sector_id in sectors:
        opportunities = await find_opportunities_for_sector(
            sector_id=sector_id,
            lookback_days=lookback_days,
            limit=limit,
            db=db,
        )
        digest_sectors[sector_id] = {
            "opportunities": opportunities,
            "count": len(opportunities),
        }
        total_opps += len(opportunities)

    has_content = total_opps > 0

    if not has_content:
        logger.info(
            "No opportunities for user %s across %d sectors",
            user_id[:8], len(sectors),
        )

    return {
        "user_id": user_id,
        "frequency": frequency,
        "tier": tier,
        "sectors": digest_sectors,
        "total_opportunities": total_opps,
        "has_content": has_content,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
