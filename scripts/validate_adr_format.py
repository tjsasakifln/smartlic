#!/usr/bin/env python3
"""Validate ADR format under docs/adr/.

Required metadata (either YAML frontmatter OR `**Key:** value` markdown convention):
    - status (one of: Accepted, Deprecated, Superseded, Proposed)
    - date (ISO date)
    - authors (or "owners")

Required sections (markdown headings, case-insensitive, level 1-3):
    - Context
    - Decision
    - Consequences
    - Alternatives Considered

Usage:
    python scripts/validate_adr_format.py [--ci-warn-only]

Exit codes:
    0 — all ADRs valid (or --ci-warn-only flag passed regardless)
    1 — one or more violations (strict mode only)

Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"
EXCLUDE_FILES = {"README.md", "TEMPLATE.md", "LIFECYCLE-REVIEW-2026-05-09.md"}

VALID_STATUSES = {"Accepted", "Deprecated", "Superseded", "Proposed"}
REQUIRED_META_KEYS = ("status", "date")  # authors/owners checked together
REQUIRED_SECTIONS = ("context", "decision", "consequences", "alternatives considered")

# Match either YAML frontmatter (--- ... ---) or markdown bold convention (**Key:** Value).
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Match `**Key:** value`, `**Key**: value`, also bullet `- **Key:** value`.
BOLD_KV_RE = re.compile(
    r"^\s*-?\s*\*\*\s*(?P<key>[A-Za-zÀ-ÿ _\-/]+?)\s*[:：]?\s*\*\*\s*[:：]?\s*(?P<val>.+?)\s*$",
    re.MULTILINE,
)
TABLE_KV_RE = re.compile(
    r"^\|\s*(?P<key>[A-Za-zÀ-ÿ _\-/]+?)\s*\|\s*(?P<val>[^|]+?)\s*\|\s*$",
    re.MULTILINE,
)
TABLE_KEYS_OF_INTEREST = {"status", "date", "authors", "owners", "supersedes", "superseded by", "stakeholders"}
HEADING_RE = re.compile(r"^#{1,3}\s+(?:\d+(?:\.\d+)*\.?\s+)?(.+?)\s*$", re.MULTILINE)


def parse_metadata(text: str) -> dict[str, str]:
    """Parse metadata from either YAML frontmatter or `**Key:** Value` lines."""
    meta: dict[str, str] = {}

    # 1. YAML frontmatter (best-effort, no PyYAML dep)
    fm_match = FRONTMATTER_RE.match(text)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line and not line.strip().startswith("#"):
                k, _, v = line.partition(":")
                meta[k.strip().lower()] = v.strip().strip('"\'')

    # 2. Markdown bold convention `**Key:** value` (overlay; frontmatter wins if both)
    for match in BOLD_KV_RE.finditer(text):
        key = match.group("key").strip().rstrip(":").strip().lower()
        val = match.group("val").strip().strip('"\'')
        if not key:
            continue
        meta.setdefault(key, val)

    # 3. Markdown table fallback (some ADRs use a metadata table with | Field | Value |)
    for match in TABLE_KV_RE.finditer(text):
        key = match.group("key").strip().lower()
        val = match.group("val").strip().strip('"\'')
        if not key or key not in TABLE_KEYS_OF_INTEREST or key.startswith("-"):
            continue
        meta.setdefault(key, val)

    # If status carries embedded date (e.g. "Accepted (2026-05-09)"), backfill date
    if "status" in meta and "date" not in meta:
        date_m = re.search(r"\((\d{4}-\d{2}-\d{2})\)", meta["status"])
        if date_m:
            meta["date"] = date_m.group(1)

    return meta


def extract_headings(text: str) -> set[str]:
    """Return set of heading titles (lowercased, leading numbers stripped)."""
    return {m.strip().lower() for m in HEADING_RE.findall(text)}


def validate_one(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    meta = parse_metadata(text)
    headings = extract_headings(text)
    violations: list[str] = []

    # Status
    status = meta.get("status", "")
    if not status:
        violations.append("missing 'status' (frontmatter or **Status:**)")
    else:
        # Strip parenthetical content (e.g. "Accepted (2026-04-28)")
        status_token = re.sub(r"\s*\(.*?\)\s*$", "", status).strip()
        if status_token not in VALID_STATUSES:
            violations.append(
                f"invalid status '{status_token}' (must be one of {sorted(VALID_STATUSES)})"
            )

    # Date
    if not meta.get("date"):
        violations.append("missing 'date'")

    # Authors / Owners (either accepted)
    if not (meta.get("authors") or meta.get("owners")):
        violations.append("missing 'authors' or 'owners'")

    # Required sections
    for section in REQUIRED_SECTIONS:
        if section not in headings:
            violations.append(f"missing section '## {section.title()}'")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ADR format")
    parser.add_argument(
        "--ci-warn-only",
        action="store_true",
        help="Print violations but always exit 0 (warn-only CI mode)",
    )
    args = parser.parse_args()

    if not ADR_DIR.is_dir():
        print(f"ERROR: ADR dir not found: {ADR_DIR}", file=sys.stderr)
        return 1

    files = sorted(p for p in ADR_DIR.glob("*.md") if p.name not in EXCLUDE_FILES)
    if not files:
        print("No ADR files found.")
        return 0

    total_violations = 0
    print(f"Validating {len(files)} ADR(s) under {ADR_DIR.relative_to(Path.cwd()) if ADR_DIR.is_relative_to(Path.cwd()) else ADR_DIR}\n")

    for path in files:
        problems = validate_one(path)
        if problems:
            total_violations += len(problems)
            print(f"FAIL  {path.name}")
            for v in problems:
                print(f"      - {v}")
        else:
            print(f"OK    {path.name}")

    print()
    if total_violations == 0:
        print(f"All {len(files)} ADR(s) valid.")
        return 0

    print(f"{total_violations} violation(s) across {len(files)} ADR(s).")
    if args.ci_warn_only:
        print("WARN-ONLY mode: exiting 0. Fix in follow-up PRs.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
