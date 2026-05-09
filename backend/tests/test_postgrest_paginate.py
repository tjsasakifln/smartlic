"""DATA-CAP-001: Unit tests for backend/utils/postgrest_paginate.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from utils.postgrest_paginate import (
    DEFAULT_BATCH_SIZE,
    POSTGREST_ROW_CAP,
    paginate_full,
)


class FakeQuery:
    """Stand-in for a Supabase/PostgREST query builder.

    ``range(start, end).execute()`` slices the canned ``rows`` list. Tracks
    how many round-trips the helper made so tests can assert page counts.
    """

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.calls: list[tuple[int, int]] = []
        self._last_range: tuple[int, int] | None = None

    def range(self, start: int, end: int) -> "FakeQuery":
        self._last_range = (start, end)
        self.calls.append((start, end))
        return self

    def execute(self) -> MagicMock:
        assert self._last_range is not None, "execute() called without range()"
        start, end = self._last_range
        # PostgREST .range() is inclusive on both ends.
        page = self._rows[start : end + 1]
        # Reset for next call so a stray double-execute() crashes the test.
        self._last_range = None
        return MagicMock(data=page)


def test_zero_rows_single_call_then_break():
    q = FakeQuery(rows=[])
    out = paginate_full(q, route="t.zero", entity_type="rows", max_total=5000)
    assert out == []
    # One call to discover emptiness; loop exits on `if not page: break`.
    assert q.calls == [(0, DEFAULT_BATCH_SIZE - 1)]


def test_under_batch_size_one_call():
    rows = [{"i": i} for i in range(500)]
    q = FakeQuery(rows=rows)
    out = paginate_full(q, route="t.under", entity_type="rows", max_total=5000)
    assert out == rows
    # Page returned 500 < batch_size → loop exits immediately.
    assert len(q.calls) == 1


def test_exactly_batch_size_two_calls_second_empty():
    # Exactly POSTGREST_ROW_CAP rows. First call returns 1000, second returns 0.
    rows = [{"i": i} for i in range(POSTGREST_ROW_CAP)]
    q = FakeQuery(rows=rows)
    with patch("utils.postgrest_paginate._record_truncation_suspect") as rec:
        out = paginate_full(q, route="t.exact", entity_type="rows", max_total=5000)
    assert len(out) == POSTGREST_ROW_CAP
    # Two .range() calls: (0, 999) full page + (1000, 1999) empty page.
    assert q.calls == [(0, 999), (1000, 1999)]
    # Truncation suspect fires on the full-1000 page.
    assert rec.call_count == 1


def test_more_than_batch_size_paginates_until_short_page():
    rows = [{"i": i} for i in range(2_500)]
    q = FakeQuery(rows=rows)
    out = paginate_full(q, route="t.more", entity_type="rows", max_total=5000)
    assert len(out) == 2_500
    # Three calls: 0-999, 1000-1999, 2000-2999 — last page returns 500 (short),
    # so the loop breaks without a fourth call.
    assert q.calls == [(0, 999), (1000, 1999), (2000, 2999)]


def test_max_total_caps_the_loop():
    # Source has 10_000 rows but max_total=2_500 — helper must stop early
    # AND trim the result to exactly max_total.
    rows = [{"i": i} for i in range(10_000)]
    q = FakeQuery(rows=rows)
    out = paginate_full(q, route="t.cap", entity_type="rows", max_total=2_500)
    assert len(out) == 2_500
    # Loop condition is `while len(rows) < max_total`. After 2 pages we have
    # 2000 rows (< 2500) so a 3rd page runs (0-999, 1000-1999, 2000-2999),
    # produces 3000 cumulative, then the trim brings it to 2500 and the
    # loop exits because the next iteration of `while` sees 3000 >= 2500.
    assert len(q.calls) == 3


def test_truncation_suspect_records_route_entity_labels():
    rows = [{"i": i} for i in range(POSTGREST_ROW_CAP)]
    q = FakeQuery(rows=rows)
    with patch("utils.postgrest_paginate._record_truncation_suspect") as rec:
        paginate_full(q, route="my.route", entity_type="bids", max_total=5000)
    rec.assert_called_with(route="my.route", entity_type="bids")


def test_invalid_batch_size_raises():
    with pytest.raises(ValueError):
        paginate_full(FakeQuery(rows=[]), route="t", batch_size=0, max_total=10)


def test_invalid_max_total_raises():
    with pytest.raises(ValueError):
        paginate_full(FakeQuery(rows=[]), route="t", max_total=0)


def test_record_truncation_suspect_metric_no_op_when_unavailable():
    """When prometheus_client is not installed, _record_truncation_suspect
    must not raise — instrumentation is best-effort."""
    from utils.postgrest_paginate import _record_truncation_suspect

    # The function catches Exception around both metrics + sentry imports,
    # so calling it here exercises the success branch when metrics are
    # available and the except branch when they are not.
    _record_truncation_suspect(route="t", entity_type="rows")  # must not raise
