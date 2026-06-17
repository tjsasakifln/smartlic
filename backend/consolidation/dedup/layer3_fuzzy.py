"""Layer 3: Fuzzy Jaccard deduplication."""
import logging
import re
from collections import defaultdict
from typing import Dict, List

from clients.base import UnifiedProcurement
from consolidation.dedup._helpers import extract_edital_number, extract_lot_number, jaccard, tokenize_objeto
from metrics import DEDUP_FUZZY_HITS

logger = logging.getLogger(__name__)


def deduplicate_fuzzy(
    records: List[UnifiedProcurement],
    fuzzy_threshold: float,
) -> List[UnifiedProcurement]:
    """Fuzzy dedup: same procurement with different edital numbers."""
    if len(records) < 2:
        return records

    blocks: Dict[str, List[int]] = defaultdict(list)
    for idx, rec in enumerate(records):
        cnpj = re.sub(r"[^\d]", "", rec.cnpj_orgao or "")
        if cnpj and len(cnpj) < 14:
            cnpj = cnpj.zfill(14)
        if cnpj:
            blocks[cnpj].append(idx)

    to_remove: set = set()
    removed_count = 0
    tokens_cache: Dict[int, frozenset] = {}

    for cnpj, indices in blocks.items():
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
                if sim < 0.70:
                    continue

                lot_a_diag = extract_lot_number(records[idx_a].objeto)
                lot_b_diag = extract_lot_number(records[idx_b].objeto)

                lot_a = lot_a_diag
                lot_b = lot_b_diag
                if sim >= fuzzy_threshold and lot_a is not None and lot_b is not None and lot_a != lot_b:
                    continue

                if lot_a is not None:
                    records[idx_a]._lot_number = lot_a
                if lot_b is not None:
                    records[idx_b]._lot_number = lot_b

                if lot_a is None and lot_b is None:
                    num_a = extract_edital_number(records[idx_a].source_id)
                    num_b = extract_edital_number(records[idx_b].source_id)
                    if (
                        num_a is not None and num_b is not None
                        and abs(num_a - num_b) <= 3 and sim >= 0.60
                    ):
                        to_remove.add(idx_b)
                        DEDUP_FUZZY_HITS.labels(layer="fuzzy").inc()
                        removed_count += 1
                        continue

                val_a = records[idx_a].valor_estimado or 0
                val_b = records[idx_b].valor_estimado or 0
                if val_a > 0 and val_b > 0:
                    diff = abs(val_a - val_b) / max(val_a, val_b)
                    value_threshold = 0.20 if sim >= fuzzy_threshold else 0.05
                    if diff > value_threshold:
                        continue

                if sim < fuzzy_threshold:
                    num_a = extract_edital_number(records[idx_a].source_id)
                    num_b = extract_edital_number(records[idx_b].source_id)
                    if num_a is not None and num_b is not None:
                        if abs(num_a - num_b) > 5:
                            continue
                    else:
                        continue

                to_remove.add(idx_b)
                DEDUP_FUZZY_HITS.labels(layer="fuzzy").inc()
                removed_count += 1

    if removed_count > 0:
        logger.info(f"[FUZZY-DEDUP] Removed {removed_count} fuzzy duplicates from {len(records)} records")

    return [rec for idx, rec in enumerate(records) if idx not in to_remove]
