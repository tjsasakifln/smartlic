#!/usr/bin/env python3
"""Build docs/adr/README.md index from ADRs in docs/adr/.

Idempotent: re-running yields byte-identical output.

Usage:
    python scripts/build_adr_index.py            # write README.md
    python scripts/build_adr_index.py --check    # exit 1 if README would change

Stdlib only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"
README_PATH = ADR_DIR / "README.md"
EXCLUDE_FILES = {"README.md", "TEMPLATE.md", "LIFECYCLE-REVIEW-2026-05-09.md"}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
BOLD_KV_RE = re.compile(
    r"^\s*-?\s*\*\*\s*(?P<key>[A-Za-zÀ-ÿ _\-/]+?)\s*[:：]?\s*\*\*\s*[:：]?\s*(?P<val>.+?)\s*$",
    re.MULTILINE,
)
# Markdown table row `| Key | Value |` (used by ADR-PARITY-BE-FE-001 etc).
TABLE_KV_RE = re.compile(
    r"^\|\s*(?P<key>[A-Za-zÀ-ÿ _\-/]+?)\s*\|\s*(?P<val>[^|]+?)\s*\|\s*$",
    re.MULTILINE,
)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
CONTEXT_BLOCK_RE = re.compile(
    r"^#{1,3}\s+(?:\d+(?:\.\d+)*\.?\s+)?Context\s*$([\s\S]*?)(?=^#{1,3}\s)",
    re.MULTILINE | re.IGNORECASE,
)
TABLE_KEYS_OF_INTEREST = {"status", "date", "authors", "owners", "supersedes", "superseded by", "stakeholders"}


def parse_metadata(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    fm = FRONTMATTER_RE.match(text)
    if fm:
        for line in fm.group(1).splitlines():
            if ":" in line and not line.strip().startswith("#"):
                k, _, v = line.partition(":")
                meta[k.strip().lower()] = v.strip().strip('"\'')
    for m in BOLD_KV_RE.finditer(text):
        key = m.group("key").strip().rstrip(":").strip().lower()
        val = m.group("val").strip().strip('"\'')
        if not key:
            continue
        meta.setdefault(key, val)
    # Markdown table fallback (e.g. PARITY-BE-FE-001 uses | Field | Value | rows)
    for m in TABLE_KV_RE.finditer(text):
        key = m.group("key").strip().lower()
        val = m.group("val").strip().strip('"\'')
        if not key or key not in TABLE_KEYS_OF_INTEREST or key.startswith("-"):
            continue
        meta.setdefault(key, val)
    # If status carries a parenthetical date (`Accepted (2026-05-09)`), backfill date
    if "status" in meta and "date" not in meta:
        date_m = re.search(r"\((\d{4}-\d{2}-\d{2})\)", meta["status"])
        if date_m:
            meta["date"] = date_m.group(1)
    return meta


def extract_title(text: str, fallback: str) -> str:
    m = H1_RE.search(text)
    return m.group(1).strip() if m else fallback


def extract_summary(text: str, meta: dict[str, str]) -> str:
    """Use `summary:` if present, else first non-empty paragraph after `## Context`."""
    if meta.get("summary"):
        return meta["summary"]
    block = CONTEXT_BLOCK_RE.search(text)
    if not block:
        return ""
    body = block.group(1).strip()
    # First non-empty paragraph (split on blank lines)
    for para in re.split(r"\n\s*\n", body):
        cleaned = " ".join(line.strip() for line in para.strip().splitlines() if line.strip())
        # Skip table rows or pure markdown noise
        if cleaned and not cleaned.startswith("|") and not cleaned.startswith("```"):
            # Truncate at first sentence boundary OR 200 chars
            sentence_match = re.search(r"^(.+?[.!?])(?:\s|$)", cleaned)
            summary = sentence_match.group(1) if sentence_match else cleaned
            if len(summary) > 200:
                summary = summary[:197].rstrip() + "..."
            # Escape pipes for markdown table
            return summary.replace("|", "\\|")
    return ""


def adr_slug(stem: str) -> str:
    """Compact identifier for the # column (e.g. 'ARCH-001', 'PARITY-BE-FE-001')."""
    # Strip leading 'ADR-' if present
    s = re.sub(r"^ADR[-_ ]+", "", stem, flags=re.IGNORECASE)
    # Drop everything after the first descriptor word (heuristic: keep up to last token of /[A-Z]+-\d+/)
    m = re.match(r"^([A-Z][A-Z0-9_-]*?-?\d+[a-z]?)", s)
    if m:
        return m.group(1)
    # Fallback: use first hyphen-separated token
    return s.split("-")[0]


def sort_key(stem: str) -> tuple[int, str]:
    """Sort: ADR-prefixed first (alphabetical), then unprefixed (alphabetical)."""
    if stem.lower().startswith("adr-"):
        return (0, stem.lower())
    return (1, stem.lower())


def normalize_status(raw: str) -> str:
    if not raw:
        return "—"
    # Strip parenthetical date like "Accepted (2026-04-28)"
    return re.sub(r"\s*\(.*?\)\s*$", "", raw).strip()


def normalize_date(raw: str, status: str) -> str:
    if raw:
        return raw
    # Try to pull date from status if embedded as "Accepted (YYYY-MM-DD)"
    m = re.search(r"\((\d{4}-\d{2}-\d{2})\)", status)
    return m.group(1) if m else "—"


def short_link(filename: str) -> str:
    return f"[{filename}](./{filename})"


def build_table(rows: list[dict[str, str]]) -> str:
    headers = ["#", "Title", "Status", "Date", "Authors/Owners", "Supersedes", "Superseded By", "Summary"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for r in rows:
        lines.append(
            "| " + " | ".join(
                [
                    r["number"],
                    r["title"],
                    r["status"],
                    r["date"],
                    r["authors"],
                    r["supersedes"],
                    r["superseded_by"],
                    r["summary"],
                ]
            ) + " |"
        )
    return "\n".join(lines)


def collect() -> list[dict[str, str]]:
    files = sorted(
        (p for p in ADR_DIR.glob("*.md") if p.name not in EXCLUDE_FILES),
        key=lambda p: sort_key(p.stem),
    )
    rows: list[dict[str, str]] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        meta = parse_metadata(text)
        title_h1 = extract_title(text, path.stem)
        status = normalize_status(meta.get("status", ""))
        date = normalize_date(meta.get("date", ""), meta.get("status", ""))
        authors = meta.get("authors") or meta.get("owners") or "—"
        supersedes = meta.get("supersedes") or "—"
        superseded_by = meta.get("superseded by") or meta.get("superseded_by") or "—"
        summary = extract_summary(text, meta) or "—"
        # Link the title to the ADR file
        safe_title = title_h1.replace("|", "\\|")
        title_cell = f"[{safe_title}](./{path.name})"
        slug = adr_slug(path.stem)
        rows.append(
            {
                "number": slug,
                "title": title_cell,
                "status": status or "—",
                "date": date or "—",
                "authors": authors,
                "supersedes": supersedes,
                "superseded_by": superseded_by,
                "summary": summary,
                "filename": path.name,
            }
        )
    return rows


def render(rows: list[dict[str, str]]) -> str:
    table = build_table(rows)
    body = f"""# Architecture Decision Records (ADR) Index

> AUTO-GENERATED by `scripts/build_adr_index.py`. Do not edit by hand.
> Re-run: `python scripts/build_adr_index.py`

This index lists every ADR under `docs/adr/`. ADRs document durable architectural and policy decisions with their context, alternatives, and consequences.

## ADR Status Legend

- **Accepted** — decision is in force.
- **Deprecated** — decision is no longer recommended; replacement may not yet exist.
- **Superseded** — replaced by a newer ADR (see `Superseded By`).
- **Proposed** — under deliberation; not yet enforced.

## Format Convention

New ADRs SHOULD use either YAML frontmatter or the `**Status:** ...` markdown convention. Required keys:

- `status` (one of: Accepted, Deprecated, Superseded, Proposed)
- `date` (ISO format)
- `authors` (or `owners`)

Required sections (markdown headings):

- `## Context`
- `## Decision`
- `## Consequences`
- `## Alternatives Considered`

Format is enforced by `scripts/validate_adr_format.py` and CI workflow `.github/workflows/adr-format-check.yml`.

## Index

{table}

## Cross-References

- `_reversa_sdd/architecture.md` §7 Spec Impact Matrix references ADRs by file path.
- `_reversa_sdd/code-spec-matrix.md` Refs section maps code areas to ADRs.
- `docs/adr/LIFECYCLE-REVIEW-2026-05-09.md` — per-ADR vigência assessment.

## Related

- Issue [#972](https://github.com/tjsasakifln/PNCP-poc/issues/972) — ADR-INDEX-001 (this index).
- `_reversa_sdd/review-report.md` §15.3 — architectural consistency tracking.
"""
    # Ensure trailing newline (idempotent stable output)
    if not body.endswith("\n"):
        body += "\n"
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ADR index README.md")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if README.md would change (drift gate for CI)",
    )
    args = parser.parse_args()

    if not ADR_DIR.is_dir():
        print(f"ERROR: ADR dir not found: {ADR_DIR}", file=sys.stderr)
        return 1

    rows = collect()
    rendered = render(rows)

    if args.check:
        if not README_PATH.exists():
            print(f"DRIFT: {README_PATH} does not exist. Run scripts/build_adr_index.py.", file=sys.stderr)
            return 1
        current = README_PATH.read_text(encoding="utf-8")
        if current != rendered:
            print(
                f"DRIFT: {README_PATH.name} is out of date. Run scripts/build_adr_index.py and commit.",
                file=sys.stderr,
            )
            return 1
        print(f"OK: {README_PATH.name} is up to date.")
        return 0

    README_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {README_PATH} ({len(rows)} ADR(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
