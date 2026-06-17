"""Layer 4: Process-number deduplication."""
import logging
import re
from collections import defaultdict
from typing import Dict, List

from clients.base import UnifiedProcurement
from consolidation.dedup._helpers import extract_lot_number, extract_process_base, jaccard, tokenize_objeto
from metrics import DEDUP_FUZZY_HITS

logger = logging.getLogger(__name__)


def deduplicate_by_process_number(
    records: List[UnifiedProcurement],
    fuzzy_threshold: float,
    source_priority: Dict[str, int],
) -> List[UnifiedProcurement]:
    """Deduplicate same org + same year records with very similar objects."""
    if len(records) < 2:
        return records

    groups: Dict[str, List[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        cnpj = re.sub(r"[^\d]", "", rec.cnpj_orgao or "")
        if cnpj and len(cnpj) < 14:
            cnpj = cnpj.zfill(14)
        base = extract_process_base(rec.source_id or "", cnpj)
        if base:
            groups[base].append(idx)

    to_remove: set = set()
    removed_count = 0
    tokens_cache: Dict[int, frozenset] = {}

    for base, indices in groups.items():
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

                val_a = records[idx_a].valor_estimado or 0
                val_b = records[idx_b].valor_estimado or 0
                if val_a > 0 and val_b > 0:
                    diff = abs(val_a - val_b) / max(val_a, val_b)
                    if diff > 0.20:
                        continue

                pri_a = source_priority.get(records[idx_a].source_name, 999)
                pri_b = source_priority.get(records[idx_b].source_name, 999)
                if pri_b < pri_a:
                    to_remove.add(idx_a)
                    DEDUP_FUZZY_HITS.labels(layer="process_number").inc()
                    removed_count += 1
                    break
                else:
                    to_remove.add(idx_b)
                    DEDUP_FUZZY_HITS.labels(layer="process_number").inc()
                    removed_count += 1

    if removed_count > 0:
        logger.info(f"[PROCESS-DEDUP] Removed {removed_count} process-number duplicates from {len(records)} records")

    return [rec for idx, rec in enumerate(records) if idx not in to_remove]
