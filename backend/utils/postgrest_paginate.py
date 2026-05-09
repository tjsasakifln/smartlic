"""DATA-CAP-001: Helper for paginating PostgREST queries past the 1000-row cap.

Background
----------
PostgREST (the Supabase REST layer) silently caps every ``SELECT`` it serves
at ``max_rows=1000`` per call. A ``.limit(5000).execute()`` therefore returns
exactly 1000 rows with no error or warning. This was the root cause of
DATA-CAP-001: 9 callsites in ``backend/routes/`` were issuing ``.limit(N)``
where N ranged from 1000 to 5000, and the aggregations downstream were silently
working on the first 1000 rows only.

The reference implementation lives in ``backend/datalake_query.py`` (lines
195-218): paginate per-UF and detect truncation via ``len(rows) == cap``. This
helper generalizes that pattern.

Usage
-----
The caller is expected to wrap ``paginate_full`` in
``_run_with_budget(asyncio.to_thread(...))`` so the resilience CI gate
(``audit-execute-without-budget.yml``) keeps passing. Internally this helper is
synchronous — it loops PostgREST ``.range(offset, offset+batch-1).execute()``
calls until exhaustion, then returns the concatenated rows::

    def _sync_query() -> list[dict]:
        from supabase_client import get_supabase
        from utils.postgrest_paginate import paginate_full

        sb = get_supabase()
        query = (
            sb.table("pncp_supplier_contracts")
            .select("orgao_cnpj,valor_global,...")
            .eq("is_active", True)
        )
        return paginate_full(query, route="contratos_publicos.sector_contracts",
                             entity_type="contracts", max_total=5000)

    rows = await _run_with_budget(asyncio.to_thread(_sync_query),
                                  budget=_BUDGET, phase="route", source=...)

Truncation suspect detection
----------------------------
When a single ``.range()`` call returns *exactly* ``batch_size`` rows, that is
suspicious — PostgREST may have truncated. We do not abort: we keep paging,
because the next call will either return more rows (legitimate hit) or zero
(truncation confirmed). Either way we increment
``DATALAKE_TRUNCATION_SUSPECTED{route, entity_type}`` so operators can spot it.

Cap
---
``max_total`` (default 10000) is a safety belt against runaway loops on
million-row tables. Callers should pass the value the original ``.limit(N)``
intended (e.g. 5000) — that is the *known* row budget for the aggregation.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# PostgREST silently caps SELECT responses at this many rows.
# Set on the Supabase REST schema (``pgrst.db_max_rows``).
POSTGREST_ROW_CAP = 1000

DEFAULT_BATCH_SIZE = 1000
DEFAULT_MAX_TOTAL = 10000


def paginate_full(
    query_builder: Any,
    *,
    route: str,
    entity_type: str = "rows",
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_total: int = DEFAULT_MAX_TOTAL,
) -> list[dict]:
    """Run a PostgREST query in pages of ``batch_size`` until exhausted or capped.

    Parameters
    ----------
    query_builder:
        A Supabase/PostgREST query builder *before* ``.execute()``. Must accept
        ``.range(start, end)`` and ``.execute()``. The builder is reused across
        pages — supabase-py's builders are stateful, so ``.range(...)`` mutates
        the same instance, which is the same shape used by
        ``backend/routes/sitemap_orgaos.py`` paginated fallback.
    route:
        Telemetry label — typically ``module.endpoint`` (e.g.
        ``contratos_publicos.sector_contracts``). Surfaces in
        ``smartlic_datalake_truncation_suspected_total`` so operators know
        which callsite is hitting the cap.
    entity_type:
        Telemetry label — coarse description of what is being paginated
        (``contracts``, ``bids``, ``orgaos``, ...).
    batch_size:
        Page size. Default ``1000`` matches PostgREST's hard cap. Setting
        anything > 1000 is a no-op because PostgREST will still trim to 1000.
    max_total:
        Hard cap on accumulated rows. Defaults to ``10_000``. Use this to
        reproduce the previous ``.limit(N)`` behavior — pass ``N`` here.

    Returns
    -------
    list[dict]
        Concatenated rows across all pages, never longer than ``max_total``.
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be > 0, got {batch_size}")
    if max_total <= 0:
        raise ValueError(f"max_total must be > 0, got {max_total}")

    rows: list[dict] = []
    offset = 0
    page_count = 0

    while len(rows) < max_total:
        # PostgREST .range(start, end) is inclusive on both ends.
        end = offset + batch_size - 1
        result = query_builder.range(offset, end).execute()
        page = list(result.data or [])
        page_count += 1

        if not page:
            break

        rows.extend(page)

        # Heuristic: a page that comes back exactly batch_size big is a
        # truncation suspect — PostgREST's silent ``max_rows`` cap kicks in at
        # 1000 even when the SQL ``LIMIT`` is higher. We do not abort here; the
        # loop continues paging so legitimate full pages keep working. The
        # counter lets operators see when a route is bumping into the cap and
        # decide whether to migrate to Pattern A (RPC RETURNS json scalar).
        if len(page) == POSTGREST_ROW_CAP and batch_size <= POSTGREST_ROW_CAP:
            _record_truncation_suspect(route=route, entity_type=entity_type)

        # Short page = data exhausted, no need for another round-trip.
        if len(page) < batch_size:
            break

        offset += batch_size

    # Trim to max_total in case the last page overshot.
    if len(rows) > max_total:
        rows = rows[:max_total]

    logger.debug(
        "paginate_full route=%s entity=%s pages=%d rows=%d max_total=%d",
        route, entity_type, page_count, len(rows), max_total,
    )
    return rows


def _record_truncation_suspect(*, route: str, entity_type: str) -> None:
    """Increment the truncation-suspect counter and add a Sentry breadcrumb.

    Both side-effects are best-effort: metrics may be a no-op (when
    prometheus_client is missing) and Sentry may not be installed in the dev
    environment. We never let an instrumentation failure abort the pagination
    loop.
    """
    try:
        from metrics import POSTGREST_TRUNCATION_SUSPECTED

        POSTGREST_TRUNCATION_SUSPECTED.labels(
            route=route, entity_type=entity_type
        ).inc()
    except Exception:  # pragma: no cover - metrics unavailable in some envs
        pass

    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            category="postgrest",
            message=f"Truncation suspected on {route}",
            level="warning",
            data={
                "route": route,
                "entity_type": entity_type,
                "row_count": POSTGREST_ROW_CAP,
            },
        )
    except Exception:  # pragma: no cover - sentry optional in dev
        pass

    logger.warning(
        "DATA-CAP-001: paginate_full hit PostgREST cap (route=%s entity=%s) — "
        "page returned exactly %d rows. Possible silent truncation. Consider "
        "migrating to a RETURNS json scalar RPC.",
        route, entity_type, POSTGREST_ROW_CAP,
    )
