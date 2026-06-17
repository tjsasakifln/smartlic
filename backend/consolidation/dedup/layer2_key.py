"""Layer 2: dedup_key exact deduplication with merge-enrichment."""
import logging
from typing import Dict, List, Tuple
from clients.base import UnifiedProcurement

logger = logging.getLogger(__name__)


def deduplicate_by_key(
    records: List[UnifiedProcurement],
    adapters: Dict,
    merge_fields: Tuple[str, ...],
) -> List[UnifiedProcurement]:
    """Deduplicate records by dedup_key with merge-enrichment."""
    if not records:
        return []

    source_priority = _build_source_priority(adapters)
    seen: Dict[str, UnifiedProcurement] = {}

    for record in records:
        key = record.dedup_key
        if not key:
            seen[f"_nokey_{id(record)}"] = record
            continue

        existing = seen.get(key)
        if existing is None:
            seen[key] = record
        else:
            if (
                existing.source_name != record.source_name
                and existing.valor_estimado > 0
                and record.valor_estimado > 0
            ):
                diff_pct = abs(existing.valor_estimado - record.valor_estimado) / max(
                    existing.valor_estimado, record.valor_estimado
                )
                if diff_pct > 0.05:
                    logger.warning(
                        f"[CONSOLIDATION] Value discrepancy >5% for dedup_key={key}: "
                        f"{existing.source_name}=R${existing.valor_estimado:,.2f} vs "
                        f"{record.source_name}=R${record.valor_estimado:,.2f} "
                        f"(diff={diff_pct:.1%})"
                    )

            existing_priority = source_priority.get(existing.source_name, 999)
            new_priority = source_priority.get(record.source_name, 999)
            if new_priority < existing_priority:
                winner, loser = record, existing
                seen[key] = record
            else:
                winner, loser = existing, record

            merge_enrich(winner, loser, key, merge_fields)

    return list(seen.values())


def merge_enrich(
    winner: UnifiedProcurement,
    loser: UnifiedProcurement,
    dedup_key: str,
    merge_fields: Tuple[str, ...],
) -> None:
    """Enrich winner with non-empty fields from loser (HARDEN-006)."""
    for field_name in merge_fields:
        winner_val = getattr(winner, field_name, None)
        loser_val = getattr(loser, field_name, None)

        winner_empty = (
            winner_val is None
            or winner_val == ""
            or (isinstance(winner_val, (int, float)) and winner_val == 0)
        )
        loser_has = (
            loser_val is not None
            and loser_val != ""
            and not (isinstance(loser_val, (int, float)) and loser_val == 0)
        )

        if winner_empty and loser_has:
            setattr(winner, field_name, loser_val)
            winner.merged_from[field_name] = loser.source_name
            import consolidation as _consolidation
            _consolidation.DEDUP_FIELDS_MERGED.labels(field=field_name).inc()
            logger.debug(
                f"[DEDUP-MERGE] key={dedup_key} field={field_name} "
                f"filled from {loser.source_name}"
            )


def _build_source_priority(adapters: Dict) -> Dict[str, int]:
    """Build source priority lookup from adapters."""
    source_priority = {}
    for code, adapter in adapters.items():
        adapter_code = getattr(adapter, "code", code)
        adapter_meta = getattr(adapter, "metadata", None)
        if adapter_meta is not None:
            source_priority[adapter_code] = adapter_meta.priority
    return source_priority
