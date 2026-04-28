#!/usr/bin/env python3
"""RBAC-ORG-001 backfill dry-run helper.

Mitigation for story risk R1 ("first member = owner heuristic may
mis-classify ~5% of orgs"). Run this BEFORE applying
`supabase/migrations/20260428100200_organization_members_role_backfill.sql`
in production:

    python scripts/rbac_org_001_backfill_dryrun.py --dry-run

The dry-run mode connects to Supabase (read-only), simulates the same
heuristic the migration uses, and writes a CSV at
`artifacts/rbac_org_001_backfill.csv` listing every member with the
proposed role transition. A human can then review and override
specific (org_id, user_id) pairs by editing the CSV before running the
migration. Override entries are NOT auto-applied; this is informational
only.

Without --dry-run the script just prints a summary (no DB writes).

Required env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (read-only used).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

try:
    from supabase import create_client
except ImportError:  # pragma: no cover — script-only dep
    print("ERROR: install supabase-py (`pip install supabase`)", file=sys.stderr)
    sys.exit(2)


REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"


def fetch_members(client) -> list[dict]:
    """Return all `organization_members` rows ordered by (org_id, invited_at)."""
    page = 0
    page_size = 1000
    out: list[dict] = []
    while True:
        result = (
            client.table("organization_members")
            .select("id, org_id, user_id, role, invited_at, accepted_at")
            .order("org_id", desc=False)
            .order("invited_at", desc=False)
            .range(page * page_size, (page + 1) * page_size - 1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            break
        out.extend(rows)
        if len(rows) < page_size:
            break
        page += 1
    return out


def compute_transitions(rows: Iterable[dict]) -> list[dict]:
    """Apply the same heuristic the migration uses, return per-row transitions.

    Output dict shape:
        org_id, user_id, current_role, proposed_role, reason
    """
    by_org: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_org[r["org_id"]].append(r)

    transitions: list[dict] = []
    for org_id, members in by_org.items():
        # Same ORDER BY as the SQL CTE: invited_at ASC NULLS LAST, id ASC
        members.sort(
            key=lambda m: (
                m.get("invited_at") is None,
                m.get("invited_at") or "",
                m.get("id") or "",
            )
        )
        for idx, m in enumerate(members):
            current = (m.get("role") or "").strip().lower()
            if current == "admin":
                proposed = "member"
                reason = "legacy_admin_to_member"
            elif current in ("owner", "member", "viewer"):
                proposed = current
                reason = "no_change"
            else:
                # NULL or unknown → heuristic
                proposed = "owner" if idx == 0 else "member"
                reason = "heuristic_first_member" if idx == 0 else "heuristic_later_member"

            transitions.append(
                {
                    "org_id": org_id,
                    "user_id": m["user_id"],
                    "current_role": current or "(null)",
                    "proposed_role": proposed,
                    "reason": reason,
                    "invited_at": m.get("invited_at") or "",
                    "accepted_at": m.get("accepted_at") or "",
                }
            )
    return transitions


def write_csv(transitions: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "org_id",
        "user_id",
        "current_role",
        "proposed_role",
        "reason",
        "invited_at",
        "accepted_at",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(transitions)


def summarize(transitions: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for t in transitions:
        counts[t["reason"]] += 1
    counts["total"] = len(transitions)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write CSV to artifacts/ instead of just printing summary",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ARTIFACTS_DIR / "rbac_org_001_backfill.csv",
        help="CSV output path (default: artifacts/rbac_org_001_backfill.csv)",
    )
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print(
            "ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set",
            file=sys.stderr,
        )
        return 2

    client = create_client(url, key)
    rows = fetch_members(client)
    transitions = compute_transitions(rows)
    summary = summarize(transitions)

    print("RBAC-ORG-001 backfill dry-run summary:")
    for k, v in sorted(summary.items()):
        print(f"  {k}: {v}")

    if args.dry_run:
        write_csv(transitions, args.out)
        print(f"\nWrote {len(transitions)} rows to {args.out}")
        print(
            "Review the CSV. To override a row, edit it manually then "
            "run UPDATE statements via psql AFTER the migration applies."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
