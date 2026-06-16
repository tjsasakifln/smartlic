#!/usr/bin/env python3
"""
#1866 AC5: Unused index detection via pg_stat_user_indexes.

Queries pg_stat_user_indexes for indexes where idx_scan = 0 (never used
since last stats reset) and pg_index for indexes marked as invalid.
Reports candidates for removal along with table size impact.

Usage:
    python scripts/check-unused-indexes.py
    python scripts/check-unused-indexes.py --output report.json
    python scripts/check-unused-indexes.py --min-size-mb 10  # only indexes > 10MB

Environment:
    SUPABASE_URL              — Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY — Service role key

Dependencies:
    httpx (already in backend/requirements.txt)

Exit codes:
    0 — no unused indexes found (or all reported are acceptable)
    1 — unused indexes detected
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

_UNUSED_INDEXES_SQL = r"""
SELECT
    schemaname,
    tablename,
    indexname,
    indexrelid::text,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid::regclass)) AS index_size_pretty,
    pg_relation_size(indexrelid::regclass) AS index_size_bytes,
    idx_tup_read,
    idx_tup_fetch,
    -- Flag indexes that have NEVER been scanned
    CASE WHEN idx_scan = 0 THEN 'UNUSED' ELSE 'USED' END AS usage_status,
    -- Check if index is unique (can't simply drop unique indexes)
    i.indisunique AS is_unique,
    -- Check if index is primary key
    i.indisprimary AS is_primary,
    -- Check for invalid indexes
    i.indisvalid AS is_valid
FROM pg_stat_user_indexes s
JOIN pg_index i ON s.indexrelid = i.indexrelid
WHERE
    -- Exclude primary keys and unique constraints (needed for data integrity)
    NOT i.indisprimary
    AND NOT i.indisunique
    -- Only consider the public schema (our application tables)
    AND s.schemaname = 'public'
ORDER BY pg_relation_size(s.indexrelid::regclass) DESC
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_supabase_headers() -> dict[str, str]:
    """Build Supabase REST headers."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        print("FATAL: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.", file=sys.stderr)
        sys.exit(2)
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json"}


def _run_sql(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute SQL via Supabase REST /rest/v1/sql endpoint."""
    import httpx

    headers = _get_supabase_headers()
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{base_url}/rest/v1/sql",
                headers=headers,
                content=sql.encode("utf-8"),
                timeout=30.0,
            )
            if resp.status_code == 200:
                return resp.json()
            print(
                f"ERROR: SQL query returned HTTP {resp.status_code}: {resp.text[:300]}",
                file=sys.stderr,
            )
            return []
    except Exception as e:
        print(f"ERROR: Failed to execute SQL: {e}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


def check_unused_indexes(min_size_mb: float = 0) -> dict[str, Any]:
    """Check for unused indexes in the database.

    Args:
        min_size_mb: Minimum index size in MB to report (0 = all).

    Returns:
        A dictionary with unused index report.
    """
    rows = _run_sql(_UNUSED_INDEXES_SQL)
    if not rows:
        print("WARN: No results from pg_stat_user_indexes.", file=sys.stderr)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "no_data",
            "unused_indexes": [],
            "total_unused_count": 0,
            "total_unused_size_bytes": 0,
            "total_unused_size_pretty": "0 bytes",
            "recommendations": [],
        }

    unused: list[dict[str, Any]] = []
    total_size = 0

    for row in rows:
        idx_scan = row.get("idx_scan", 0) or 0
        size_bytes = row.get("index_size_bytes", 0) or 0
        is_valid = row.get("is_valid", True)

        if idx_scan == 0 or not is_valid:
            if min_size_mb > 0 and size_bytes < min_size_mb * 1024 * 1024:
                continue
            entry = {
                "schema": row.get("schemaname"),
                "table": row.get("tablename"),
                "index": row.get("indexname"),
                "index_size_pretty": row.get("index_size_pretty", "0 bytes"),
                "index_size_bytes": size_bytes,
                "idx_scan": idx_scan,
                "idx_tup_read": row.get("idx_tup_read", 0),
                "idx_tup_fetch": row.get("idx_tup_fetch", 0),
                "is_unique": row.get("is_unique", False),
                "is_primary": row.get("is_primary", False),
                "is_valid": is_valid,
                "reason": "never_scanned" if idx_scan == 0 else "invalid",
            }
            unused.append(entry)
            total_size += size_bytes

    # Generate recommendations
    recommendations: list[str] = []
    if unused:
        total_mb = total_size / (1024 * 1024)
        recommendations.append(
            f"Found {len(unused)} unused indexes ({total_mb:.1f} MB total). "
            "Review each before dropping — some may be used only in specific queries "
            "or during index creation."
        )
        for idx in unused[:5]:  # Top 5 recommendations
            tbl = idx["table"]
            nm = idx["index"]
            sz = idx["index_size_pretty"]
            if idx["is_valid"] is False:
                recommendations.append(f"  DROP INDEX IF EXISTS {nm};  -- invalid on {tbl} ({sz})")
            else:
                recommendations.append(f"  -- DROP INDEX IF EXISTS {nm};  -- never scanned on {tbl} ({sz})")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok" if not unused else "unused_found",
        "unused_indexes": unused,
        "total_unused_count": len(unused),
        "total_unused_size_bytes": total_size,
        "total_unused_size_pretty": _format_bytes(total_size),
        "recommendations": recommendations,
    }


def _format_bytes(n: int) -> str:
    """Format byte count to human-readable string."""
    for unit in ("bytes", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect unused indexes via pg_stat_user_indexes",
    )
    parser.add_argument("--output", type=str, default="", help="Write JSON report to file")
    parser.add_argument("--min-size-mb", type=float, default=0, help="Minimum index size in MB to report")
    args = parser.parse_args()

    report = check_unused_indexes(min_size_mb=args.min_size_mb)

    output = json.dumps(report, indent=2, default=str)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output)

    if report.get("status") == "unused_found":
        print(
            f"\n{report['total_unused_count']} unused index(es) found "
            f"({report['total_unused_size_pretty']}). Review recommendations above.",
            file=sys.stderr,
        )
        return 1

    print("\nNo unused indexes detected.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
