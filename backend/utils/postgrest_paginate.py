"""DATA-CAP-001 — PostgREST per-batch pagination helper.

PostgREST caps every response at ``max_rows = 1000`` (Supabase platform default,
NOT tunable). Calling ``.limit(5000).execute()`` therefore silently truncates to
1000 rows with no error or warning. Visible symptom: any public route that lists
contratos / fornecedores / licitações for an entity with >1000 records returns
exactly 1000 every time, which breaks credibility on programmatic SEO pages.

This module implements the canonical Pattern B fix: paginate via PostgREST
``.range(start, end)`` in a loop, batch_size capped at 1000 (the platform max).

Pattern A (RPC ``RETURNS json`` scalar) bypasses the cap entirely and is
preferred for aggregating queries — see
``supabase/migrations/20260408200000_sitemap_rpc_json.sql`` and the migration
introduced alongside this helper for ``get_orgao_top_contracts_json``.

Usage
-----
Synchronous (run inside ``asyncio.to_thread`` from async handlers):

.. code-block:: python

    from utils.postgrest_paginate import paginate_full

    def _sync_query() -> list[dict]:
        from supabase_client import get_supabase
        sb = get_supabase()
        builder = (
            sb.table("pncp_supplier_contracts")
            .select("ni_fornecedor,nome_fornecedor,valor_global")
            .eq("orgao_cnpj", cnpj)
            .eq("is_active", True)
            .order("data_assinatura", desc=True)
        )
        return paginate_full(
            builder,
            batch_size=1000,
            max_total=10_000,
            route="contratos_publicos.orgao_contratos_stats",
            entity_type="pncp_supplier_contracts",
        )

The helper deliberately does NOT call ``asyncio.to_thread`` itself: callers
already wrap the whole sync block in ``_run_with_budget(asyncio.to_thread(...))``
to keep the request inside the time budget waterfall.

Notes
-----
* ``batch_size`` MUST be ``<= 1000``. Values above are silently capped at 1000
  by PostgREST so each batch would still truncate.
* ``max_total`` defaults to 10_000 — a runaway guard. Most public routes need
  far less; tune per call site.
* On truncation suspect (``len(batch) == batch_size``) the helper increments
  ``POSTGREST_TRUNCATION_SUSPECTED{route, entity_type}`` and emits a
  ``logger.warning`` + Sentry breadcrumb. Metric failure never blocks the
  query path.
* The supabase-py builder is **stateful**: chaining ``.range(a, b)`` mutates
  the underlying request URL. We therefore call ``.range`` and ``.execute``
  on the SAME builder reference each iteration; this matches the patterns
  already used in ``backend/routes/sitemap_*.py`` and ``datalake_query.py``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# PostgREST platform cap (Supabase Cloud). NOT tunable — see story DATA-CAP-001.
POSTGREST_MAX_ROWS_CAP = 1000


def paginate_full(
    query_builder: Any,
    *,
    batch_size: int = 1000,
    max_total: int = 10_000,
    route: str = "unknown",
    entity_type: str = "unknown",
) -> list[dict]:
    """Paginate a supabase-py query builder in batches, returning all rows.

    Iterates ``builder.range(offset, offset + batch_size - 1).execute()`` until
    a short batch is returned (``len(batch) < batch_size``) or ``max_total`` is
    reached.

    Parameters
    ----------
    query_builder
        A supabase-py query builder ready for ``.execute()`` — i.e. the result
        of ``sb.table(...).select(...).eq(...).order(...)``. The builder MUST
        NOT have ``.limit()`` chained on it (use this helper instead).
    batch_size
        Rows per ``.range`` call. Capped at 1000 (PostgREST platform cap).
        Default 1000.
    max_total
        Hard upper bound on total rows fetched. Prevents runaway queries from
        exhausting the connection pool. Default 10 000.
    route
        Identifier for the calling route (used as Prometheus label and in
        Sentry breadcrumb). Convention: ``"<module>.<function>"``.
    entity_type
        Table or domain entity being queried (used as Prometheus label).
        Convention: the Supabase table name, e.g. ``"pncp_supplier_contracts"``.

    Returns
    -------
    list[dict]
        All rows returned by the query, up to ``max_total``. Empty list if
        the query returned no rows.

    Raises
    ------
    Whatever ``builder.execute()`` raises — typically ``httpx`` errors. The
    caller is responsible for wrapping in ``_run_with_budget`` to keep the
    request inside the time budget.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    if max_total <= 0:
        raise ValueError("max_total must be > 0")
    if batch_size > POSTGREST_MAX_ROWS_CAP:
        logger.warning(
            "[postgrest_paginate] batch_size=%d > PostgREST cap=%d; clamping to %d "
            "(route=%s entity=%s)",
            batch_size, POSTGREST_MAX_ROWS_CAP, POSTGREST_MAX_ROWS_CAP, route, entity_type,
        )
        batch_size = POSTGREST_MAX_ROWS_CAP

    rows: list[dict] = []
    offset = 0
    iterations = 0
    # Hard sanity cap on iterations — even with batch_size=1, max_total=10k
    # gives 10k iterations; a 100k requested with batch_size=1000 gives 100.
    # We pick a generous bound so it never fires in healthy paths but catches
    # bugs (e.g. callers passing builder that returns the same row forever).
    max_iterations = (max_total // batch_size) + 2

    while iterations < max_iterations and len(rows) < max_total:
        iterations += 1
        end = offset + batch_size - 1
        try:
            resp = query_builder.range(offset, end).execute()
        except Exception:
            # Re-raise — the caller wraps this in _run_with_budget and logs.
            raise

        batch = getattr(resp, "data", None) or []
        if not batch:
            break

        rows.extend(batch)

        # Truncation suspect: a full batch means there might be more rows.
        # We continue paginating; the metric records that this route hit the
        # batch boundary at least once (signal: this entity has many rows
        # and the helper is doing its job).
        if len(batch) == batch_size:
            _record_truncation_suspect(route=route, entity_type=entity_type)
            offset += batch_size
            continue

        # Short batch — we have everything.
        break

    if len(rows) >= max_total:
        logger.warning(
            "[postgrest_paginate] max_total=%d reached for route=%s entity=%s — "
            "returning capped result. Consider raising max_total or filtering tighter.",
            max_total, route, entity_type,
        )
        # Truncate defensively in case the last batch overshot
        rows = rows[:max_total]

    return rows


def _record_truncation_suspect(*, route: str, entity_type: str) -> None:
    """Increment Prometheus counter + emit log + Sentry breadcrumb.

    All instrumentation is best-effort: failures here NEVER block the query
    path. This matches the convention in ``datalake_query.py:213``.
    """
    logger.warning(
        "[postgrest_paginate] truncation suspect — full batch returned "
        "(route=%s entity=%s); paginating next batch",
        route, entity_type,
    )

    try:
        from metrics import POSTGREST_TRUNCATION_SUSPECTED

        POSTGREST_TRUNCATION_SUSPECTED.labels(route=route, entity_type=entity_type).inc()
    except Exception:
        # Metrics are optional — never block the flow.
        pass

    # Sentry breadcrumb (best-effort)
    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            category="postgrest.truncation",
            message="PostgREST batch returned full batch_size — pagination continued",
            level="info",
            data={"route": route, "entity_type": entity_type},
        )
    except Exception:
        pass
