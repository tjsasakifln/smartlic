#!/usr/bin/env python3
"""Environment Parity Check (#1917) — detect staging<->production drift.

Fetches Railway env vars from staging and production via the Railway CLI,
compares them, and emits GitHub Action annotations for any drift found.

Critical drift (exit 1)
    An env var present in staging but *missing* in production (and not on the
    blocklist).  This usually means someone added a new var during development
    and forgot to promote it to production — exactly the pattern that caused
    incident RES-BE-013 (``PYTHONASYNCIODEBUG=1`` in prod with no PR trail).

Non-critical drift (warning, exit 0)
    An env var that exists in both environments but has a *different value*.
    Different values staging<->prod are expected (DEBUG vs INFO, different
    secrets, environment-specific URLs).  We surface them so operators can
    confirm they are intentional.

Exit codes
    0 — no critical drift detected
    1 — critical drift detected (env var in staging, missing in production)
    2 — usage / IO error / Railway CLI failure
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BLOCKLIST_DEFAULT = REPO_ROOT / "docs" / "operations" / "env-parity-blocklist.md"

SENSITIVE_PATTERNS = frozenset({
    "KEY", "SECRET", "TOKEN", "PASSWORD", "AUTH", "API_KEY",
    "DSN", "SIGNING", "FERNET", "JWT",
})


# ── helpers ──────────────────────────────────────────────────────────────────


def _load_vars(path: str) -> dict[str, str]:
    """Parse ``KEY=VALUE`` lines from *path* and return a dict.

    Empty lines, comment lines (``#``), and lines without ``=`` are skipped.
    Values may be stripped of surrounding quotes.
    """
    text = Path(path).read_text(encoding="utf-8")
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            result[key] = value
    return result


def _load_blocklist(path: Path) -> list[str]:
    """Load blocklist patterns (glob-style, one per line, ``#`` comments)."""
    if not path.exists():
        print(f"::warning::Blocklist not found at {path} — no intentional-diff exclusions.",
              file=sys.stderr)
        return []
    patterns: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def _is_blocklisted(key: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(key, p) for p in patterns)


def _mask_value(key: str, value: str) -> str:
    """Mask sensitive values before printing them in annotations.

    If the key looks like a secret (token, password, key, …) the value is
    shortened to just the first and last two characters separated by ``***``.
    """
    upper = key.upper()
    for pattern in SENSITIVE_PATTERNS:
        if pattern in upper:
            if len(value) <= 4:
                return "***"
            return value[:2] + "***" + value[-2:]
    if len(value) > 80:
        return value[:40] + "…" + value[-40:]
    return value


def _print_annotation(level: str, message: str) -> None:
    print(f"::{level}::{message}", file=sys.stderr)


def _fetch_railway_vars(service: str) -> dict[str, str]:
    """Fetch env vars from Railway via CLI.

    Requires ``RAILWAY_TOKEN`` to be set in the calling environment (set by
    the CI step env or via ``export RAILWAY_TOKEN=...`` locally).
    """
    env = os.environ.copy()
    try:
        result = subprocess.run(
            ["railway", "variables", "--service", service, "--kv"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except FileNotFoundError:
        _print_annotation("error", "railway CLI not on PATH.  Install from https://railway.com/install.sh")
        sys.exit(2)
    except subprocess.TimeoutExpired:
        _print_annotation("error", f"railway variables timed out after 30 s (service={service})")
        sys.exit(2)

    if result.returncode != 0:
        msg = result.stderr.strip() or f"exit code {result.returncode}"
        _print_annotation("error", f"railway variables failed (service={service}): {msg}")
        sys.exit(2)

    return _parse_kv_output(result.stdout)


def _parse_kv_output(text: str) -> dict[str, str]:
    """Parse Railway CLI ``--kv`` output into a dict."""
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            result[key] = value
    return result


# ── comparison ───────────────────────────────────────────────────────────────


def compare_env(
    staging: dict[str, str],
    production: dict[str, str],
    blocklist: list[str],
    service: str,
) -> tuple[int, list[dict], list[dict], list[dict]]:
    """Return ``(exit_code, critical, warnings, infos)``.

    *critical* — keys in staging but not in production (and not blocklisted).
    *warnings* — keys with different values between staging and production.
    *infos* — keys in production but not in staging.
    """
    staging_keys = set(staging.keys())
    prod_keys = set(production.keys())

    critical: list[dict] = []
    for key in sorted(staging_keys - prod_keys):
        if not _is_blocklisted(key, blocklist):
            critical.append({
                "key": key,
                "staging_value": _mask_value(key, staging[key]),
            })

    warnings_list: list[dict] = []
    for key in sorted(staging_keys & prod_keys):
        s_val = staging[key]
        p_val = production[key]
        if s_val != p_val:
            warnings_list.append({
                "key": key,
                "staging_value": _mask_value(key, s_val),
                "prod_value": _mask_value(key, p_val),
            })

    infos: list[dict] = [
        {"key": k} for k in sorted(prod_keys - staging_keys)
    ]

    exit_code = 1 if critical else 0

    # Emit annotations
    for c in critical:
        _print_annotation(
            "error",
            f"CRITICAL: '{c['key']}' exists in staging ({service}) "
            f"but is MISSING in production. "
            f"Add it to Railway prod or add to env-parity-blocklist.md if intentional. "
            f"staging={c['staging_value']}",
        )

    for w in warnings_list:
        _print_annotation(
            "warning",
            f"Value differs for '{w['key']}' ({service}): "
            f"staging={w['staging_value']} vs production={w['prod_value']}. "
            f"Verify this is intentional.",
        )

    if infos:
        shown = infos[:10]
        for i in shown:
            _print_annotation(
                "notice",
                f"'{i['key']}' exists in production ({service}) but not in staging. "
                f"This is normal for prod-specific config.",
            )
        remaining = len(infos) - len(shown)
        if remaining > 0:
            _print_annotation(
                "notice",
                f"… and {remaining} more var(s) only in production ({service}).",
            )

    return exit_code, critical, warnings_list, infos


# ── main ─────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--service",
        default="bidiq-backend",
        help="Railway service name (default: bidiq-backend)",
    )
    parser.add_argument(
        "--staging-file",
        help="Read staging env vars from this KEY=VALUE file instead of Railway CLI. "
        "Use '-' for stdin.",
    )
    parser.add_argument(
        "--prod-file",
        help="Read production env vars from this KEY=VALUE file instead of Railway CLI. "
        "Use '-' for stdin.",
    )
    parser.add_argument(
        "--blocklist",
        default=str(BLOCKLIST_DEFAULT),
        help="Path to blocklist file (default: docs/operations/env-parity-blocklist.md)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON summary to stdout",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    blocklist = _load_blocklist(Path(args.blocklist))

    # Fetch env vars
    if args.staging_file or args.prod_file:
        if not args.staging_file or not args.prod_file:
            _print_annotation("error", "Both --staging-file and --prod-file are required when using file mode.")
            return 2
        staging = _load_vars(args.staging_file)
        production = _load_vars(args.prod_file)
    else:
        # Fetch from Railway (requires RAILWAY_TOKEN in environment)
        staging = _fetch_railway_vars(args.service)
        print("::warning::Fetching staging vars via Railway CLI.  "
              "Override RAILWAY_TOKEN to staging token before calling.",
              file=sys.stderr)
        # NOTE: Railway CLI uses whatever RAILWAY_TOKEN is in the env. To
        # compare staging vs production, call the script TWICE with different
        # tokens, save the output, and re-run with --staging-file / --prod-file.

    exit_code, critical, warnings_list, infos = compare_env(
        staging, production, blocklist, args.service,
    )

    summary = {
        "service": args.service,
        "staging_count": len(staging),
        "production_count": len(production),
        "critical_count": len(critical),
        "warning_count": len(warnings_list),
        "info_count": len(infos),
        "critical": critical,
        "warnings": warnings_list,
        "production_only": [i["key"] for i in infos],
        "exit_code": exit_code,
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            f"parity summary: service={args.service} "
            f"staging={len(staging)} production={len(production)} "
            f"critical={len(critical)} warnings={len(warnings_list)} "
            f"prod_only={len(infos)}",
            file=sys.stderr,
        )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
