"""FEEDBACK-002: User sector affinity — updates affinity scores based on feedback verdicts.

Each time a user submits feedback, their affinity score for the relevant sector
is adjusted per these rules:
  - correct:        affinity += 0.1 (capped at 1.0)
  - false_positive: affinity -= 0.2 (floored at 0.0)
  - false_negative: affinity += 0.05 (capped at 1.0)

Cold start: affinity defaults to 0.5 (neutral).

Weekly decay: all affinities multiplied by 0.99 (floored at 0.01).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_affinity(supabase, user_id: str, sector_id: str) -> float:
    """Get current affinity score for user+sector.

    Returns 0.5 (cold start / neutral) if no row exists.
    """
    from supabase_client import sb_execute

    result = await sb_execute(
        supabase.table("user_sector_affinity")
        .select("affinity_score")
        .eq("user_id", user_id)
        .eq("sector_id", sector_id),
        category="read",
    )

    if result.data and len(result.data) > 0:
        return float(result.data[0]["affinity_score"])

    return 0.5  # Cold start: neutral


async def upsert_affinity(supabase, user_id: str, sector_id: str, score: float) -> None:
    """Upsert affinity score for user+sector.

    Uses ON CONFLICT to support both insert and update with a single call.
    """
    from supabase_client import sb_execute

    await sb_execute(
        supabase.table("user_sector_affinity")
        .upsert(
            {
                "user_id": user_id,
                "sector_id": sector_id,
                "affinity_score": round(score, 2),
            },
            on_conflict="user_id,sector_id",
        ),
        category="write",
    )


async def update_affinity(
    supabase, user_id: str, sector_id: str, feedback_type: str
) -> Optional[float]:
    """Update affinity score based on feedback verdict.

    Args:
        supabase: Supabase client instance.
        user_id: The user's UUID.
        sector_id: The sector identifier (e.g. "vestuario").
        feedback_type: One of "correct", "false_positive", "false_negative".

    Returns:
        The new affinity score, or None if feedback_type is unknown or sector_id is empty.

    Rules:
        - correct:        min(1.0, current + 0.10)
        - false_positive: max(0.0, current - 0.20)
        - false_negative: min(1.0, current + 0.05)
    """
    if not sector_id or sector_id == "unknown":
        logger.debug("Skipping affinity update: no sector_id provided")
        return None

    current = await get_affinity(supabase, user_id, sector_id)

    if feedback_type == "correct":
        new_score = min(1.0, current + 0.10)
    elif feedback_type == "false_positive":
        new_score = max(0.0, current - 0.20)
    elif feedback_type == "false_negative":
        new_score = min(1.0, current + 0.05)
    else:
        logger.debug(
            "Skipping affinity update: unknown feedback_type=%s", feedback_type
        )
        return None

    await upsert_affinity(supabase, user_id, sector_id, new_score)
    logger.info(
        "Affinity updated: user=%s sector=%s feedback=%s %.2f -> %.2f",
        user_id[:8],
        sector_id,
        feedback_type,
        current,
        new_score,
    )
    return new_score


async def decay_all_affinities(supabase) -> Optional[int]:
    """Apply weekly decay: multiply all affinity scores by 0.99, floored at 0.01.

    Calls the ``decay_user_sector_affinities()`` RPC on Supabase.
    If the RPC does not exist (migration not applied), handles gracefully.

    Returns:
        Number of rows affected, or None on error.
    """
    from supabase_client import sb_execute

    try:
        result = await sb_execute(
            supabase.rpc("decay_user_sector_affinities"),
            category="rpc",
        )
        count = result.data if result.data is not None else 0
        logger.info("Affinity decay applied: %d rows affected", count)
        return count
    except Exception as exc:
        logger.warning(
            "Affinity decay failed (RPC may not exist yet): %s", exc
        )
        return None
