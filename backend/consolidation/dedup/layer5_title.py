"""Layer 5: Title-prefix deduplication."""
import logging
import re
from collections import defaultdict
from typing import Dict, List

from clients.base import UnifiedProcurement
from consolidation.dedup._helpers import extract_lot_number, jaccard, tokenize_objeto
from metrics import DEDUP_FUZZY_HITS

logger = logging.getLogger(__name__)


def deduplicate_by_title_prefix(
    records: List[UnifiedProcurement],
    fuzzy_threshold: float,
    source_priority: Dict[str, int],
) -> List[UnifiedProcurement]:
    """Cross-org dedup: same title prefix with similar objects."""
    if len(records) < 2:
        return records

    blocks: Dict[str, List[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        texto = re.sub(r"[^\w\s]", " ", (rec.objeto or "").lower())
        texto = " ".join(texto.split())
        prefix = texto[:60].strip()
        if prefix and len(prefix) > 15:
            blocks[prefix].append(idx)

    to_remove: set = set()
    tokens_cache: Dict[int, frozenset] = {}

    for prefix, indices in blocks.items():
        if len(indices) < 2:
            continue
        for i_pos in range(len(indices)):
            idx_a = indices[i_pos]
            if idx_a in to_remove:
                continue
            if idx_a not in tokens_cache:
                tokens_cache[idx_a] = tokenize_objeto(records[idx_a].objeto)
            for j_pos in range(i_pos + 1, len(indices)):
                idx_b = indices[j_pos]
                if idx_b in to_remove:
                    continue
                if idx_b not in tokens_cache:
                    tokens_cache[idx_b] = tokenize_objeto(records[idx_b].objeto)

                sim = jaccard(tokens_cache[idx_a], tokens_cache[idx_b])
                if sim < fuzzy_threshold:
                    continue

                lot_a = extract_lot_number(records[idx_a].objeto)
                lot_b = extract_lot_number(records[idx_b].objeto)
                if lot_a is not None and lot_b is not None and lot_a != lot_b:
                    continue

                va = records[idx_a].valor_estimado or 0
                vb = records[idx_b].valor_estimado or 0
                if va > 0 and vb > 0:
                    diff = abs(va - vb) / max(va, vb)
                    if diff > 0.20:
                        continue

                pa = source_priority.get(records[idx_a].source_name, 999)
                pb = source_priority.get(records[idx_b].source_name, 999)
                loser = idx_b if pa <= pb else idx_a
                to_remove.add(loser)
                DEDUP_FUZZY_HITS.labels(layer="title_prefix").inc()

    if to_remove:
        logger.info(f"[TITLE-PREFIX-DEDUP] Removed {len(to_remove)} cross-org duplicates")
    return [r for i, r in enumerate(records) if i not in to_remove]
