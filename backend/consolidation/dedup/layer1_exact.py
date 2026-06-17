"""Layer 1: source_id exact deduplication."""
import logging
from typing import Dict, List
from clients.base import UnifiedProcurement

logger = logging.getLogger(__name__)


def deduplicate_by_source_id(
    records: List[UnifiedProcurement],
    adapters: Dict,
) -> List[UnifiedProcurement]:
    """Deduplicate by source_id when same ID appears from multiple paths."""
    if not records:
        return []

    seen: Dict[str, UnifiedProcurement] = {}
    no_id: list[UnifiedProcurement] = []

    for record in records:
        sid = record.source_id
        if not sid:
            no_id.append(record)
            continue

        existing = seen.get(sid)
        if existing is None:
            seen[sid] = record
        else:
            existing_priority = getattr(
                getattr(adapters.get(existing.source_name), "metadata", None),
                "priority", 999,
            )
            new_priority = getattr(
                getattr(adapters.get(record.source_name), "metadata", None),
                "priority", 999,
            )
            if new_priority < existing_priority:
                seen[sid] = record

    result = list(seen.values()) + no_id
    removed = len(records) - len(result)
    if removed > 0:
        logger.info(f"[DEDUP] source_id dedup removed {removed} duplicates")
    return result
