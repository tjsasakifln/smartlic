"""Multi-source consolidation package — facade re-export for backwards compatibility.

TD-008: consolidation.py (1394 LOC) split into:
  - priority_resolver.py — SourceResult, ConsolidationResult, AllSourcesFailedError
  - dedup.py             — DeduplicationEngine (all dedup layers)
  - source_merger.py     — ConsolidationService (main orchestrator)

All original symbols re-exported here so that `from consolidation import X`
continues to work without any changes in callers (AC2 — zero broken imports).
"""

from consolidation.priority_resolver import (
    AllSourcesFailedError,
    ConsolidationResult,
    SourceResult,
)

from consolidation.dedup import DeduplicationEngine
from metrics import DEDUP_FIELDS_MERGED  # re-export for test patching (AC2)

from consolidation.source_merger import ConsolidationService
from consolidation.source_pipeline import SourceFetcher

__all__ = [
    "AllSourcesFailedError",
    "ConsolidationResult",
    "DEDUP_FIELDS_MERGED",
    "DeduplicationEngine",
    "ConsolidationService",
    "SourceFetcher",
    "SourceResult",
]
