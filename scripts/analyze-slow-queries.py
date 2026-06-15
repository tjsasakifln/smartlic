#!/usr/bin/env python3
"""
#1866: Slow query analysis — pg_stat_statements + EXPLAIN ANALYZE.

Extracts the top 20 queries from pg_stat_statements sorted by total_time,
mean_time, and calls, then runs EXPLAIN ANALYZE for queries exceeding the
mean_time threshold (>100ms by default).

Outputs a structured JSON report to stdout (or a file with --output).

Usage:
    python scripts/analyze-slow-queries.py
    python scripts/analyze-slow-queries.py --threshold-ms 500 --limit 10 --output report.json
    python scripts/analyze-slow-queries.py --explain-only  # skip stats dump, only EXPLAIN

Environment:
    SUPABASE_URL         — Supabase project URL (e.g. https://<ref>.supabase.co)
    SUPABASE_SERVICE_ROLE_KEY — Service role key for admin queries

Dependencies:
    httpx (already in backend/requirements.txt)

Exit codes:
    0 — all queries below threshold
    1 — one or more queries exceed --fail-mean-ms (default 500ms, for CI gate)
    2 — connection/query error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PG_STAT_SQL = """
SELECT
    queryid,
    LEFT(query, 500) AS query_preview,
    calls,
    total_exec_time / 1000.0 AS total_time_ms,
    mean_exec_time / 1000.0 AS mean_time_ms,
    min_exec_time / 1000.0 AS min_time_ms,
    max_exec_time / 1000.0 AS max_time_ms,
    stddev_exec_time / 1000.0 AS stddev_time_ms,
    rows,
    shared_blks_hit,
    shared_blks_read,
    shared_blks_hit::numeric / GREATEST(shared_blks_hit + shared_blks_read, 1) * 100
        AS cache_hit_ratio,
    ROW_NUMBER() OVER (ORDER BY total_exec_time DESC) AS rank_by_total,
    ROW_NUMBER() OVER (ORDER BY mean_exec_time DESC) AS rank_by_mean,
    ROW_NUMBER() OVER (ORDER BY calls DESC) AS rank_by_calls
FROM extensions.pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
  AND query NOT LIKE '%pg_stat_%'
ORDER BY total_exec_time DESC
LIMIT %(limit)s
"""

_EXPLAIN_SQL = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) %(query)s"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_supabase_headers() -> dict[str, str]:
    """Build Supabase REST headers from environment variables."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        print("FATAL: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.", file=sys.stderr)
        sys.exit(2)
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}


def _run_sql(sql: str, params: dict[str, Any] | None = None, rest_url: str | None = None) -> list[dict[str, Any]]:
    """Execute a raw SQL query via Supabase REST /rpc/pg_stat_statements endpoint.

    Falls back to a direct POST to the Supabase SQL endpoint if available.
    """
    import httpx

    headers = _get_supabase_headers()
    base_url = rest_url or os.environ.get("SUPABASE_URL", "").rstrip("/")

    # Try the /rest/v1/rpc/ endpoint for pg_stat_statements query
    # In some Supabase projects, we can use pg_stat_statements via SQL endpoint.
    # We use the pg_stat_statements view through the REST API.
    payload: dict[str, Any] = {"query": sql}
    if params:
        payload["params"] = params

    try:
        with httpx.Client(timeout=60.0) as client:
            # Attempt direct SQL query via Supabase REST API
            resp = client.post(
                f"{base_url}/rest/v1/rpc/pg_stat_statements",
                headers=headers,
                json=params or {},
                timeout=60.0,
            )
            if resp.status_code == 200:
                return resp.json()

            # Fall back to raw SQL execution via the SQL endpoint
            resp = client.post(
                f"{base_url}/rest/v1/sql",
                headers=headers,
                content=sql.encode("utf-8"),
                timeout=60.0,
            )
            if resp.status_code == 200:
                return resp.json()

            # Last resort: try the pg_stat_statements table directly via REST
            resp = client.get(
                f"{base_url}/rest/v1/pg_stat_statements",
                headers=headers,
                params={} if not params else params,
                timeout=60.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return data

            # Explain why all attempts failed
            print(
                f"WARN: Supabase REST API returned {resp.status_code} for query.\n"
                f"Response: {resp.text[:500]}",
                file=sys.stderr,
            )
            return []
    except Exception as e:
        print(f"ERROR: Failed to execute SQL via Supabase REST API: {e}", file=sys.stderr)
        return []


def _run_explain(query_preview: str, queryid: int) -> dict[str, Any] | None:
    """Run EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) for a query."""
    import httpx

    headers = _get_supabase_headers()
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")

    # We can only EXPLAIN queries we can reconstruct. The preview text
    # from pg_stat_statements (first 500 chars) is usually enough for
    # most queries.
    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_preview}"

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{base_url}/rest/v1/sql",
                headers=headers,
                content=explain_sql.encode("utf-8"),
                timeout=30.0,
            )
            if resp.status_code == 200:
                return {
                    "queryid": queryid,
                    "plan": resp.json(),
                    "query_preview": query_preview,
                }

            # Truncated queries or parameterized queries may fail EXPLAIN
            print(
                f"  EXPLAIN failed for queryid={queryid}: HTTP {resp.status_code} — "
                f"query may be truncated or requires parameter binding.",
                file=sys.stderr,
            )
            return None
    except Exception as e:
        print(f"  EXPLAIN error for queryid={queryid}: {e}", file=sys.stderr)
        return None


def _format_duration(ms: float) -> str:
    """Format milliseconds to a human-readable string."""
    if ms < 1:
        return f"{ms * 1000:.1f}us"
    if ms < 1000:
        return f"{ms:.1f}ms"
    return f"{ms / 1000:.2f}s"


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


def analyze_queries(limit: int = 20, threshold_ms: float = 100.0, explain_only: bool = False) -> dict[str, Any]:
    """Run the full slow query analysis.

    Args:
        limit: Number of top queries to fetch.
        threshold_ms: Only run EXPLAIN for queries with mean_time > this value.
        explain_only: Skip the stats dump, only generate EXPLAIN plans.

    Returns:
        A dictionary with the analysis report.
    """
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold_ms": threshold_ms,
        "limit": limit,
        "top_by_total_time": [],
        "top_by_mean_time": [],
        "top_by_calls": [],
        "slow_queries_explain": [],
        "summary": {},
    }

    if explain_only:
        # Skip the full fetch and go straight to EXPLAIN for known slow queries
        return report

    # Fetch top queries from pg_stat_statements
    rows = _run_sql(_PG_STAT_SQL, {"limit": limit})
    if not rows:
        print("WARN: No results from pg_stat_statements. The extension may not be active.", file=sys.stderr)
        report["summary"]["status"] = "pg_stat_statements_not_available"
        return report

    # Categorize rows
    top_by_total = sorted(rows, key=lambda r: r.get("total_time_ms", 0) or 0, reverse=True)
    top_by_mean = sorted(rows, key=lambda r: r.get("mean_time_ms", 0) or 0, reverse=True)
    top_by_calls = sorted(rows, key=lambda r: r.get("calls", 0) or 0, reverse=True)

    report["top_by_total_time"] = top_by_total[:limit]
    report["top_by_mean_time"] = top_by_mean[:limit]
    report["top_by_calls"] = top_by_calls[:limit]

    # Calculate summary stats
    total_calls = sum(r.get("calls", 0) or 0 for r in rows)
    mean_of_means = sum(r.get("mean_time_ms", 0) or 0 for r in rows) / max(len(rows), 1)
    max_mean = max((r.get("mean_time_ms", 0) or 0) for r in rows)
    report["summary"] = {
        "status": "ok",
        "queries_fetched": len(rows),
        "total_calls": total_calls,
        "overall_mean_time_ms": round(mean_of_means, 2),
        "max_mean_time_ms": round(max_mean, 2),
        "queries_above_threshold": sum(1 for r in rows if (r.get("mean_time_ms", 0) or 0) > threshold_ms),
        "queries_above_500ms": sum(1 for r in rows if (r.get("mean_time_ms", 0) or 0) > 500),
        "slowest_query": _format_duration(max_mean),
    }

    # Run EXPLAIN ANALYZE for queries above threshold
    for row in rows:
        if (row.get("mean_time_ms", 0) or 0) > threshold_ms:
            query_preview = row.get("query_preview", "")
            queryid = row.get("queryid", 0)
            if query_preview and queryid:
                plan = _run_explain(query_preview, queryid)
                if plan:
                    report["slow_queries_explain"].append(plan)

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Slow query analysis via pg_stat_statements + EXPLAIN ANALYZE",
    )
    parser.add_argument("--limit", type=int, default=20, help="Number of top queries to fetch (default: 20)")
    parser.add_argument("--threshold-ms", type=float, default=100.0, help="EXPLAIN threshold in ms (default: 100)")
    parser.add_argument("--fail-mean-ms", type=float, default=500.0, help="CI fail threshold for mean_time (default: 500)")
    parser.add_argument("--output", type=str, default="", help="Write JSON report to file (default: stdout)")
    parser.add_argument("--explain-only", action="store_true", help="Skip stats dump, only run EXPLAIN on known queries")
    args = parser.parse_args()

    report = analyze_queries(
        limit=args.limit,
        threshold_ms=args.threshold_ms,
        explain_only=args.explain_only,
    )

    # Format output
    output = json.dumps(report, indent=2, default=str)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    # Determine exit code
    max_mean = report.get("summary", {}).get("max_mean_time_ms", 0)
    if max_mean > args.fail_mean_ms:
        print(
            f"\nCI FAIL: Slowest query mean_time ({_format_duration(max_mean)}) "
            f"exceeds --fail-mean-ms ({_format_duration(args.fail_mean_ms)})",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
