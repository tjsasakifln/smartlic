#!/usr/bin/env python3
"""RBAC-ORG-002 AC1: Audit org_id propagation across backend routes.

Walks every router module in `backend/routes/*.py` (recursing into sub-packages
like `routes/search/`), parses each route function with the `ast` module, and
classifies it on three axes:

1. **Org-scoped path?** — does the route accept an `org_id` path/query parameter?
2. **Org-table touch?** — does the function reference an org-scoped table
   (organizations, organization_members) via supabase `table()` or RPC name?
3. **Enforcement?** — does the route call `require_org_role(...)` as a
   dependency (or reside in a module already known to enforce via include).

Each route is assigned a severity:

- **P0 multi-tenant leak** — accepts `{org_id}` AND queries an org-scoped
  resource WITHOUT `require_org_role`. Cross-org user could read/mutate.
- **P1 escalation risk** — accepts `{org_id}` but only enforces auth (no role
  check). A member of org X could perform owner-only operations on org Y if
  the service layer trusts the path param without re-validating role.
- **P2 read-only org touch** — references org-scoped table but the route is
  user-scoped (`.eq("user_id", current_user.id)`); no obvious leak but worth
  reviewing.
- **OK** — no org context OR full enforcement OR explicitly exempt.

Output formats: markdown table (default), JSON (`--json`), or both. Exits
non-zero in `--ci` mode if any P0 finding exists outside the allow-list.

Usage
-----

    # Human-readable report:
    python backend/scripts/audit_org_id_propagation.py

    # Save markdown to docs/audits/:
    python backend/scripts/audit_org_id_propagation.py --output docs/audits/2026-05-rbac-org-propagation.md

    # JSON output for CI annotations:
    python backend/scripts/audit_org_id_propagation.py --json

    # CI gate mode (exit 1 on new P0 outside allow-list):
    python backend/scripts/audit_org_id_propagation.py --ci

Exit codes
----------

    0   no P0 violations OR all P0 inside allow-list (--ci mode)
    1   new P0 violation found (--ci mode)
    2   invalid invocation / IO error
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Allow-list / config
# ---------------------------------------------------------------------------

# Make the script runnable from either repo root or `backend/`.
_HERE = Path(__file__).resolve().parent
_BACKEND_DIR = _HERE.parent
_ROUTES_DIR = _BACKEND_DIR / "routes"

# Import the exempt modules from a sibling file so it can be reviewed/diffed
# independently of the script logic.
sys.path.insert(0, str(_HERE))
try:
    from exempt_routes import EXEMPT_MODULES  # type: ignore
except ImportError:
    EXEMPT_MODULES = frozenset()

# Tables that, when referenced, indicate the route touches org-scoped data.
ORG_SCOPED_TABLES: frozenset[str] = frozenset(
    {
        "organizations",
        "organization_members",
    }
)

# Severity ladder.
SEV_P0 = "P0_multi_tenant_leak"
SEV_P1 = "P1_escalation_risk"
SEV_P2 = "P2_read_only_touch"
SEV_OK = "OK"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class RouteFinding:
    module: str  # e.g. "organizations" or "search/__init__"
    function: str  # e.g. "get_org"
    method: str  # e.g. "GET" / "POST"
    path: str  # e.g. "/organizations/{org_id}"
    accepts_org_id: bool  # True if `{org_id}` in path or `org_id` parameter
    touches_org_table: bool  # True if function body references ORG_SCOPED_TABLES
    enforces_role: bool  # True if `require_org_role(...)` in dependencies
    severity: str  # SEV_P0 / SEV_P1 / SEV_P2 / SEV_OK
    line: int  # source line of the route decorator
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def _decorator_route_info(dec: ast.expr) -> tuple[str, str] | None:
    """Return (METHOD, path) if decorator is a router method call, else None.

    Handles ``@router.get("/foo")``, ``@router.post("/x", status_code=201)``,
    and ``@some_router.delete("/x")``.
    """
    if not isinstance(dec, ast.Call):
        return None
    func = dec.func
    if not isinstance(func, ast.Attribute):
        return None
    method = func.attr.lower()
    if method not in _HTTP_METHODS:
        return None
    if not dec.args:
        return None
    path_node = dec.args[0]
    if isinstance(path_node, ast.Constant) and isinstance(path_node.value, str):
        return method.upper(), path_node.value
    return None


def _depends_calls(node: ast.AST) -> Iterable[ast.Call]:
    """Yield every ``Depends(...)`` call inside an AST node (recursive)."""
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "Depends"
        ):
            yield child


def _is_require_org_role(call: ast.Call) -> bool:
    """True if the call is ``require_org_role(...)`` (factory) inside Depends."""
    # Depends(require_org_role(OrgRole.MEMBER))
    if not call.args:
        return False
    first = call.args[0]
    if isinstance(first, ast.Call) and isinstance(first.func, ast.Name):
        return first.func.id == "require_org_role"
    # Depends(require_org_role) — treated as un-parameterized factory; still counts
    if isinstance(first, ast.Name):
        return first.id == "require_org_role"
    return False


def _function_accepts_org_id(func: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    """True if function takes an ``org_id`` parameter (path or query)."""
    args = list(func.args.posonlyargs) + list(func.args.args) + list(func.args.kwonlyargs)
    return any(a.arg == "org_id" for a in args)


def _path_has_org_id(path: str) -> bool:
    return "{org_id}" in path or "{org_id:" in path


def _function_touches_org_table(func: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    """Check if the function body references org-scoped tables.

    Looks for either ``.table("organizations")`` style calls or string literal
    matches inside the function body.
    """
    for node in ast.walk(func):
        # supabase().table("organizations")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "table"
            and node.args
        ):
            arg = node.args[0]
            if (
                isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and arg.value in ORG_SCOPED_TABLES
            ):
                return True
        # raw string literal — e.g. table_name = "organizations"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in ORG_SCOPED_TABLES:
                return True
    return False


def _function_enforces_role(func: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    """True if any default-arg of the function uses ``Depends(require_org_role(...))``."""
    # Combine `args.defaults` (positional) + `args.kw_defaults` (kw-only)
    defaults: list[ast.expr] = list(func.args.defaults) + [
        d for d in func.args.kw_defaults if d is not None
    ]
    for default in defaults:
        for call in _depends_calls(default):
            if _is_require_org_role(call):
                return True
    return False


# ---------------------------------------------------------------------------
# Audit core
# ---------------------------------------------------------------------------


def _module_name(file: Path) -> str:
    rel = file.relative_to(_ROUTES_DIR)
    if rel.suffix == ".py":
        rel = rel.with_suffix("")
    return str(rel).replace("\\", "/")


def _classify(
    *,
    accepts_org_id: bool,
    touches_org_table: bool,
    enforces_role: bool,
    is_exempt: bool,
) -> tuple[str, list[str]]:
    notes: list[str] = []
    if is_exempt:
        return SEV_OK, ["module is in exempt allow-list"]
    if accepts_org_id and touches_org_table and not enforces_role:
        return SEV_P0, ["accepts {org_id}, touches org table, MISSING require_org_role"]
    if accepts_org_id and not enforces_role:
        return SEV_P1, ["accepts {org_id} without require_org_role (escalation risk)"]
    if touches_org_table and not accepts_org_id and not enforces_role:
        notes.append("touches org table but no {org_id} path param")
        return SEV_P2, notes
    return SEV_OK, notes


def audit_file(file: Path) -> list[RouteFinding]:
    """Parse one router file and return a finding per route function."""
    findings: list[RouteFinding] = []
    try:
        source = file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file))
    except (OSError, SyntaxError) as exc:
        print(f"[warn] could not parse {file}: {exc}", file=sys.stderr)
        return findings

    module = _module_name(file)
    is_exempt_module = module in EXEMPT_MODULES or module.split("/")[0] in EXEMPT_MODULES

    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        # find route decorator
        for dec in node.decorator_list:
            info = _decorator_route_info(dec)
            if info is None:
                continue
            method, path = info
            accepts_org_id = _path_has_org_id(path) or _function_accepts_org_id(node)
            touches_org_table = _function_touches_org_table(node)
            enforces_role = _function_enforces_role(node)
            severity, notes = _classify(
                accepts_org_id=accepts_org_id,
                touches_org_table=touches_org_table,
                enforces_role=enforces_role,
                is_exempt=is_exempt_module,
            )
            findings.append(
                RouteFinding(
                    module=module,
                    function=node.name,
                    method=method,
                    path=path,
                    accepts_org_id=accepts_org_id,
                    touches_org_table=touches_org_table,
                    enforces_role=enforces_role,
                    severity=severity,
                    line=dec.lineno,
                    notes=notes,
                )
            )
            break  # one finding per function
    return findings


def audit_directory(directory: Path = _ROUTES_DIR) -> list[RouteFinding]:
    findings: list[RouteFinding] = []
    if not directory.exists():
        print(f"[error] routes directory not found: {directory}", file=sys.stderr)
        return findings
    for file in sorted(directory.rglob("*.py")):
        if file.name.startswith("_") and file.name != "__init__.py":
            continue
        findings.extend(audit_file(file))
    return findings


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_markdown(findings: list[RouteFinding]) -> str:
    by_sev = {SEV_P0: [], SEV_P1: [], SEV_P2: [], SEV_OK: []}
    for f in findings:
        by_sev[f.severity].append(f)

    lines: list[str] = []
    lines.append("# RBAC Org-ID Propagation Audit")
    lines.append("")
    lines.append("Generated by `backend/scripts/audit_org_id_propagation.py` (RBAC-ORG-002 AC1).")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|------:|")
    lines.append(f"| P0 multi-tenant leak | {len(by_sev[SEV_P0])} |")
    lines.append(f"| P1 escalation risk | {len(by_sev[SEV_P1])} |")
    lines.append(f"| P2 read-only org touch | {len(by_sev[SEV_P2])} |")
    lines.append(f"| OK | {len(by_sev[SEV_OK])} |")
    lines.append(f"| **Total routes audited** | **{len(findings)}** |")
    lines.append("")

    for sev_key, sev_label in (
        (SEV_P0, "P0 — Multi-tenant leak (must fix)"),
        (SEV_P1, "P1 — Escalation risk (review)"),
        (SEV_P2, "P2 — Read-only org table touch (review)"),
    ):
        bucket = by_sev[sev_key]
        if not bucket:
            continue
        lines.append(f"## {sev_label}")
        lines.append("")
        lines.append("| Module | Function | Method | Path | accepts_org_id | touches_org_table | enforces_role | Notes |")
        lines.append("|--------|----------|--------|------|:--------------:|:-----------------:|:-------------:|-------|")
        for f in bucket:
            notes = "; ".join(f.notes) if f.notes else ""
            lines.append(
                f"| `{f.module}` | `{f.function}` | {f.method} | `{f.path}` "
                f"| {'YES' if f.accepts_org_id else 'no'} "
                f"| {'YES' if f.touches_org_table else 'no'} "
                f"| {'YES' if f.enforces_role else 'NO'} | {notes} |"
            )
        lines.append("")

    # Compact OK section
    ok_routes = by_sev[SEV_OK]
    lines.append("## OK — no org context or fully enforced")
    lines.append("")
    lines.append(f"{len(ok_routes)} routes — see JSON output for full list (`--json`).")
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append("1. Walks every `.py` file in `backend/routes/` (recursive).")
    lines.append("2. AST-parses each function decorated with `@router.<method>(...)`.")
    lines.append("3. Classifies on three axes:")
    lines.append("   - `accepts_org_id`: `{org_id}` in path OR `org_id` in parameter list")
    lines.append("   - `touches_org_table`: references `.table(\"organizations\")` or `.table(\"organization_members\")`")
    lines.append("   - `enforces_role`: any default-arg uses `Depends(require_org_role(...))`")
    lines.append("4. Severity matrix:")
    lines.append("   - P0 = accepts org_id + touches table + NO require_org_role")
    lines.append("   - P1 = accepts org_id + NO require_org_role (regardless of table)")
    lines.append("   - P2 = touches table + does not accept org_id (no obvious leak, review)")
    lines.append("   - OK = exempt module OR fully enforced OR no org context")
    lines.append("")
    lines.append("## Allow-list")
    lines.append("")
    lines.append("Modules in `backend/scripts/exempt_routes.py::EXEMPT_MODULES` are treated as OK regardless of pattern. Adding entries requires `@architect` + `@devops` review (analogous to `prod-env-blocklist.txt`).")
    lines.append("")
    return "\n".join(lines)


def render_json(findings: list[RouteFinding]) -> str:
    return json.dumps([asdict(f) for f in findings], indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Write markdown report to this path (default: stdout).",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit JSON instead of markdown.",
    )
    parser.add_argument(
        "--ci", action="store_true",
        help="CI gate mode: exit 1 if any P0 violation exists outside allow-list.",
    )
    args = parser.parse_args(argv)

    findings = audit_directory()

    if args.json:
        out = render_json(findings)
    else:
        out = render_markdown(findings)

    if args.output:
        try:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(out, encoding="utf-8")
            print(f"[ok] wrote report to {args.output}", file=sys.stderr)
        except OSError as exc:
            print(f"[error] could not write {args.output}: {exc}", file=sys.stderr)
            return 2
    else:
        print(out)

    if args.ci:
        p0 = [f for f in findings if f.severity == SEV_P0]
        if p0:
            print(
                f"\n[CI FAIL] {len(p0)} P0 multi-tenant leak finding(s) detected. "
                "Apply require_org_role(OrgRole.MEMBER) or add module to "
                "backend/scripts/exempt_routes.py with @architect+@devops sign-off.",
                file=sys.stderr,
            )
            for f in p0:
                print(
                    f"  - {f.module}:{f.line} {f.method} {f.path} ({f.function})",
                    file=sys.stderr,
                )
            return 1
        print("[CI OK] no P0 violations.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
