"""DeduplicationEngine orchestrator (#1781)."""
import logging
from typing import Dict, List, Optional

from clients.base import UnifiedProcurement
from config import DEDUP_FUZZY_ENABLED, DEDUP_FUZZY_THRESHOLD
from filter.stopwords import PT_BR_STOPWORDS

logger = logging.getLogger(__name__)


class DeduplicationEngine:
    """Runs all deduplication layers against UnifiedProcurement records."""

    _MERGE_FIELDS = ("valor_estimado", "modalidade", "orgao", "objeto")
    _FUZZY_STOPWORDS = PT_BR_STOPWORDS

    def __init__(
        self,
        adapters: Dict,
        fuzzy_enabled: Optional[bool] = None,
        fuzzy_threshold: Optional[float] = None,
    ):
        self._adapters = adapters
        self._fuzzy_enabled = (
            DEDUP_FUZZY_ENABLED if fuzzy_enabled is None else fuzzy_enabled
        )
        self._fuzzy_threshold = (
            DEDUP_FUZZY_THRESHOLD if fuzzy_threshold is None else fuzzy_threshold
        )

    def run(self, records: List[UnifiedProcurement]) -> List[UnifiedProcurement]:
        """Run all dedup layers in sequence."""
        from consolidation.dedup.layer1_exact import deduplicate_by_source_id
        deduped = deduplicate_by_source_id(records, self._adapters)

        from consolidation.dedup.layer2_key import deduplicate_by_key
        deduped = deduplicate_by_key(deduped, self._adapters, self._MERGE_FIELDS)

        if self._fuzzy_enabled:
            from consolidation.dedup.layer3_fuzzy import deduplicate_fuzzy
            deduped = deduplicate_fuzzy(deduped, self._fuzzy_threshold)

            from consolidation.dedup.layer4_process import deduplicate_by_process_number
            deduped = deduplicate_by_process_number(
                deduped, self._fuzzy_threshold, self._get_source_priority()
            )

            from consolidation.dedup.layer5_title import deduplicate_by_title_prefix
            deduped = deduplicate_by_title_prefix(
                deduped, self._fuzzy_threshold, self._get_source_priority()
            )

        return deduped

    def _get_source_priority(self) -> Dict[str, int]:
        """Build source priority lookup from adapters."""
        source_priority = {}
        for code, adapter in self._adapters.items():
            adapter_code = getattr(adapter, "code", code)
            adapter_meta = getattr(adapter, "metadata", None)
            if adapter_meta is not None:
                source_priority[adapter_code] = adapter_meta.priority
        return source_priority

    # --- Layer method wrappers (backward compat) ---
    def _deduplicate_by_source_id(self, records):
        from consolidation.dedup.layer1_exact import deduplicate_by_source_id as _fn
        return _fn(records, self._adapters)

    def _deduplicate(self, records):
        from consolidation.dedup.layer2_key import deduplicate_by_key as _fn
        return _fn(records, self._adapters, self._MERGE_FIELDS)

    def _deduplicate_fuzzy(self, records):
        from consolidation.dedup.layer3_fuzzy import deduplicate_fuzzy as _fn
        return _fn(records, self._fuzzy_threshold)

    def _deduplicate_by_process_number(self, records):
        from consolidation.dedup.layer4_process import deduplicate_by_process_number as _fn
        return _fn(records, self._fuzzy_threshold, self._get_source_priority())

    def _deduplicate_by_title_prefix(self, records):
        from consolidation.dedup.layer5_title import deduplicate_by_title_prefix as _fn
        return _fn(records, self._fuzzy_threshold, self._get_source_priority())

    def _merge_enrich(self, winner, loser, dedup_key):
        from consolidation.dedup.layer2_key import merge_enrich as _fn
        _fn(winner, loser, dedup_key, self._MERGE_FIELDS)

    @staticmethod
    def _tokenize_objeto(texto):
        from consolidation.dedup._helpers import tokenize_objeto as _fn
        return _fn(texto)

    @staticmethod
    def _jaccard(a, b):
        from consolidation.dedup._helpers import jaccard as _fn
        return _fn(a, b)

    @staticmethod
    def _extract_edital_number(source_id):
        from consolidation.dedup._helpers import extract_edital_number as _fn
        return _fn(source_id)

    @staticmethod
    def _extract_lot_number(obj_text):
        from consolidation.dedup._helpers import extract_lot_number as _fn
        return _fn(obj_text)

    @staticmethod
    def _extract_process_base(source_id, cnpj):
        from consolidation.dedup._helpers import extract_process_base as _fn
        return _fn(source_id, cnpj)
