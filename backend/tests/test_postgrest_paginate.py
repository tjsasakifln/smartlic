"""DATA-CAP-001 — unit tests for ``utils.postgrest_paginate.paginate_full``.

These tests do NOT require Supabase: they mock a builder that records every
``.range(start, end).execute()`` call and serves a pre-set list of rows
sliced by the requested range. That is enough to validate:

* Empty result set → return [].
* Result smaller than batch_size → 1 query, return all.
* Result exactly batch_size rows → 2 queries (second returns empty / short).
* Result larger than batch_size → N queries until short batch.
* ``max_total`` upper bound respected.
* Truncation suspect metric is incremented exactly when a full batch is
  returned (non-final batch) and NOT on the short final batch.
"""

from __future__ import annotations

from typing import List
from unittest.mock import MagicMock, patch

import pytest

from utils.postgrest_paginate import (
    POSTGREST_MAX_ROWS_CAP,
    paginate_full,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeBuilder:
    """Mimics the supabase-py query builder for paginate_full's purposes.

    Stores ``rows`` and serves slices on each ``.range(start, end).execute()``
    call. Keeps a log of every range call so tests can assert call shapes.
    """

    def __init__(self, rows: List[dict]):
        self._rows = rows
        self.range_calls: list[tuple[int, int]] = []
        self._next_range: tuple[int, int] | None = None

    def range(self, start: int, end: int) -> "FakeBuilder":
        self.range_calls.append((start, end))
        self._next_range = (start, end)
        return self

    def execute(self):
        if self._next_range is None:
            raise RuntimeError("execute() called before range()")
        start, end = self._next_range
        # PostgREST .range is INCLUSIVE on both ends.
        slice_data = self._rows[start : end + 1]
        resp = MagicMock()
        resp.data = slice_data
        return resp


# ---------------------------------------------------------------------------
# Tests — happy paths
# ---------------------------------------------------------------------------


def test_paginate_returns_empty_when_no_rows():
    builder = FakeBuilder([])

    result = paginate_full(builder, batch_size=1000, max_total=5000, route="t.empty", entity_type="t")

    assert result == []
    # Empty data returns immediately on the first batch.
    assert builder.range_calls == [(0, 999)]


def test_paginate_short_batch_single_query():
    rows = [{"id": i} for i in range(42)]
    builder = FakeBuilder(rows)

    result = paginate_full(builder, batch_size=1000, max_total=5000, route="t.short", entity_type="t")

    assert result == rows
    assert builder.range_calls == [(0, 999)]


def test_paginate_full_batch_two_queries():
    """Exactly batch_size rows → 1 full batch + 1 empty/short batch."""
    rows = [{"id": i} for i in range(1000)]
    builder = FakeBuilder(rows)

    result = paginate_full(builder, batch_size=1000, max_total=5000, route="t.exact", entity_type="t")

    assert len(result) == 1000
    # First range fetches 0..999 (full); second range 1000..1999 returns empty.
    assert builder.range_calls == [(0, 999), (1000, 1999)]


def test_paginate_multi_batch():
    rows = [{"id": i} for i in range(2300)]
    builder = FakeBuilder(rows)

    result = paginate_full(builder, batch_size=1000, max_total=5000, route="t.multi", entity_type="t")

    assert len(result) == 2300
    assert builder.range_calls == [(0, 999), (1000, 1999), (2000, 2999)]
    # Last batch returned 300 rows (short) → loop ends.


def test_paginate_max_total_caps_result():
    rows = [{"id": i} for i in range(5000)]
    builder = FakeBuilder(rows)

    result = paginate_full(builder, batch_size=1000, max_total=2000, route="t.cap", entity_type="t")

    assert len(result) == 2000
    # We stop at offset 2000 (max_total) because len(rows) >= max_total triggers break.
    # With batch_size=1000, max_total=2000 we expect 2 calls then loop exit.
    assert builder.range_calls[:2] == [(0, 999), (1000, 1999)]
    assert len(builder.range_calls) == 2


def test_paginate_clamps_batch_size_above_postgrest_cap():
    """batch_size > 1000 must be clamped (would silently truncate otherwise)."""
    rows = [{"id": i} for i in range(500)]
    builder = FakeBuilder(rows)

    paginate_full(
        builder,
        batch_size=5000,  # ridiculous; must be clamped to 1000
        max_total=10_000,
        route="t.clamp",
        entity_type="t",
    )

    # The single range call must use end=999 (inclusive), confirming clamp.
    assert builder.range_calls == [(0, 999)]
    assert POSTGREST_MAX_ROWS_CAP == 1000


# ---------------------------------------------------------------------------
# Tests — input validation
# ---------------------------------------------------------------------------


def test_paginate_rejects_zero_batch_size():
    builder = FakeBuilder([])
    with pytest.raises(ValueError):
        paginate_full(builder, batch_size=0, max_total=10, route="t", entity_type="t")


def test_paginate_rejects_zero_max_total():
    builder = FakeBuilder([])
    with pytest.raises(ValueError):
        paginate_full(builder, batch_size=10, max_total=0, route="t", entity_type="t")


# ---------------------------------------------------------------------------
# Tests — instrumentation (truncation-suspect metric)
# ---------------------------------------------------------------------------


def test_truncation_metric_inc_on_full_batch_only():
    """A full batch (len == batch_size) increments the metric; a short batch does not."""
    rows = [{"id": i} for i in range(1500)]
    builder = FakeBuilder(rows)

    with patch("utils.postgrest_paginate._record_truncation_suspect") as record:
        paginate_full(builder, batch_size=1000, max_total=5000, route="t.metric", entity_type="t")

    # First batch (1000 rows) is full → metric incremented exactly once.
    # Second batch (500 rows) is short → no increment.
    assert record.call_count == 1
    record.assert_called_with(route="t.metric", entity_type="t")


def test_truncation_metric_not_inc_when_under_batch():
    rows = [{"id": i} for i in range(50)]
    builder = FakeBuilder(rows)

    with patch("utils.postgrest_paginate._record_truncation_suspect") as record:
        paginate_full(builder, batch_size=1000, max_total=5000, route="t", entity_type="t")

    record.assert_not_called()


def test_truncation_metric_inc_when_exact_batch_size():
    """Exactly batch_size → first call full → metric increments once,
    then second call returns empty → no extra metric increment."""
    rows = [{"id": i} for i in range(1000)]
    builder = FakeBuilder(rows)

    with patch("utils.postgrest_paginate._record_truncation_suspect") as record:
        paginate_full(builder, batch_size=1000, max_total=5000, route="t", entity_type="t")

    assert record.call_count == 1


def test_record_truncation_suspect_swallows_metric_failure(caplog):
    """Failure inside metrics import / Sentry must NOT break the query path."""
    from utils import postgrest_paginate

    # If POSTGREST_TRUNCATION_SUSPECTED raises on .labels(...), the query keeps running.
    with patch.object(postgrest_paginate, "logger") as fake_log, patch(
        "metrics.POSTGREST_TRUNCATION_SUSPECTED",
        new=MagicMock(labels=MagicMock(side_effect=RuntimeError("metric backend down"))),
    ):
        # Should not raise.
        postgrest_paginate._record_truncation_suspect(route="t", entity_type="t")
        # Logger.warning was called (the announcement line) — confirms function ran.
        assert fake_log.warning.called
