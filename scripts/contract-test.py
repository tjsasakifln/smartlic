#!/usr/bin/env python3
"""
Contract tests — validates frontend <-> backend type safety in runtime.

Checks:
1. Schema drift: compares current OpenAPI endpoint schemas against committed
   snapshots (detects added/removed/changed fields).  Runs without a live
   backend — extracts the schema directly from ``app.openapi()``.
2. Response contract: validates real API responses (status, body schema,
   required headers) against the declared OpenAPI schemas.  Requires a
   running backend (``--base-url``).

Usage:
    # Check schema drift against committed snapshots (CI / pre-commit)
    cd backend && python ../scripts/contract-test.py

    # Update snapshots after intentional schema changes
    cd backend && python ../scripts/contract-test.py --snapshot

    # Validate responses against a running backend
    python scripts/contract-test.py --test --base-url http://localhost:8000

Exit code:
    0 — all checks passed (or snapshot updated successfully)
    1 — drift detected or response validation failed

Environment:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY, ENCRYPTION_KEY,
    ENVIRONMENT, SENTRY_DSN, REDIS_URL — needed for ``--snapshot`` / ``--check``
    (extracting OpenAPI schema from the imported FastAPI app).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "backend" / "tests" / "contracts" / "snapshots" / "openapi"

# ---------------------------------------------------------------------------
# Critical endpoint list  (20 endpoints across health, busca, pipeline, billing,
# auth, plans, user, alerts, MFA, messages, organizations)
#
# Sources: startup/routes.py + startup/endpoints.py + discovered OpenAPI paths.
# Format: (method, path, category, public_accessible)
# ---------------------------------------------------------------------------

CRITICAL_ENDPOINTS: list[tuple[str, str, str, bool]] = [
    # Health / Infrastructure
    ("GET", "/health/live", "health", True),
    ("GET", "/health/ready", "health", True),
    ("GET", "/health", "health", True),
    ("GET", "/sources/health", "health", True),
    # API Root
    ("GET", "/", "root", True),
    # Auth (signup + check-email are public; MFA requires auth)
    ("POST", "/v1/auth/signup", "auth", True),
    ("GET", "/v1/auth/check-email", "auth", True),
    ("POST", "/v1/mfa/enroll", "auth", False),
    # Plans / Billing (plans is public; subscription/status requires auth)
    ("GET", "/v1/plans", "billing", True),
    ("GET", "/v1/subscription/status", "billing", False),
    # User (both require auth)
    ("GET", "/v1/me", "user", False),
    ("GET", "/v1/trial-status", "user", False),
    # Search / Busca
    ("GET", "/v1/setores", "busca", True),
    # Pipeline
    ("GET", "/v1/pipeline", "pipeline", False),
    ("GET", "/v1/pipeline/alerts", "pipeline", False),
    # Analytics
    ("GET", "/v1/analytics/summary", "analytics", False),
    # Messages
    ("GET", "/v1/api/messages/conversations", "messages", False),
    # Alerts / Notifications
    ("GET", "/v1/alerts", "alerts", False),
    ("GET", "/v1/notifications/new-bids-count", "notifications", False),
    # Organizations
    ("GET", "/v1/organizations/me", "organizations", False),
]

_PATH_PARAMS: dict[str, dict[str, str]] = {}


def _resolve_path(method: str, path: str) -> str:
    """Replace template parameters with sample values."""
    params = deepcopy(_PATH_PARAMS.get(f"{method} {path}", {}))
    resolved = path
    for key, val in params.items():
        resolved = resolved.replace(f"{{{key}}}", val)
    return resolved


# ---------------------------------------------------------------------------
# OpenAPI extraction helper
# ---------------------------------------------------------------------------

# Cache for resolved $ref to avoid repeated resolution
_ref_cache: dict[str, Any] = {}
_components_schemas: dict[str, Any] = {}


def extract_openapi() -> dict[str, Any] | None:
    """Import the FastAPI app and extract its OpenAPI schema.

    Returns ``None`` on import failure (missing env vars, dependencies).
    """
    global _components_schemas
    _ensure_env()

    # Ensure backend/ is on sys.path so ``from main import app`` works
    backend_dir = str(REPO_ROOT / "backend")
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    original_cwd = os.getcwd()
    if os.path.basename(original_cwd) != "backend":
        os.chdir(backend_dir)

    try:
        from main import app  # type: ignore[import-unused]

        app.openapi_schema = None
        schema: dict[str, Any] = app.openapi()
        # Cache component schemas for $ref resolution
        _components_schemas = (
            schema.get("components", {}).get("schemas", {}) or {}
        )
        return schema
    except Exception as exc:
        print(f"[WARN] Could not extract OpenAPI schema: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None


def _ensure_env() -> None:
    """Set minimal environment variables required for app import."""
    os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
    os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    os.environ.setdefault("OPENAI_API_KEY", "sk-test-key")
    os.environ.setdefault(
        "ENCRYPTION_KEY", "bzc732A921Puw9JN4lrzMo1nw0EjlcUdAyR6Z6N7Sqc="
    )
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("SENTRY_DSN", "")
    os.environ.setdefault("REDIS_URL", "")
    os.environ.setdefault("LOG_LEVEL", "WARNING")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-prod")
    os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")
    os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_placeholder")
    os.environ.setdefault("RESEND_API_KEY", "re_placeholder")
    os.environ.setdefault("NEXT_PUBLIC_SUPABASE_URL", "https://test.supabase.co")
    os.environ.setdefault("NEXT_PUBLIC_SUPABASE_ANON_KEY", "test-anon-key")


# ---------------------------------------------------------------------------
# $ref resolution
# ---------------------------------------------------------------------------


def _resolve_ref(ref: str, depth: int = 0) -> Any:
    """Resolve a JSON Schema ``$ref`` relative to ``components/schemas``."""
    if depth > 15:
        return {"description": "max_ref_depth"}
    if not ref or not isinstance(ref, str):
        return ref
    if ref.startswith("#/components/schemas/"):
        name = ref[21:]
        if name in _ref_cache:
            return deepcopy(_ref_cache[name])
        raw = _components_schemas.get(name)
        if raw is None:
            return {"description": f"unknown_schema_{name}"}
        resolved = _resolve_schema(deepcopy(raw), depth + 1)
        _ref_cache[name] = resolved
        return deepcopy(resolved)
    return ref


def _resolve_schema(obj: Any, depth: int = 0) -> Any:
    """Recursively resolve all ``$ref`` pointers in a schema object."""
    if depth > 15:
        return obj
    if isinstance(obj, dict):
        if "$ref" in obj:
            return _resolve_ref(obj["$ref"], depth)
        return {k: _resolve_schema(v, depth) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_schema(v, depth) for v in obj]
    return obj


def resolve_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Public helper to fully resolve ``$ref`` in an extracted schema."""
    global _ref_cache
    _ref_cache = {}
    return _resolve_schema(deepcopy(schema))


# ---------------------------------------------------------------------------
# Per-endpoint schema extraction
# ---------------------------------------------------------------------------


def _find_path_item(
    openapi: dict[str, Any], method: str, path: str
) -> dict[str, Any] | None:
    """Find the path item for *method* + *path* in the OpenAPI schema."""
    paths = openapi.get("paths", {})
    candidates = [path, path.rstrip("/"), path + "/"]
    for p in candidates:
        if p in paths:
            op = paths[p].get(method.lower())
            if op:
                return op  # type: ignore[return-value]
    # Try with leading /v1 for paths that might be missing prefix
    if not path.startswith("/v1/") and not path.startswith("/health"):
        v1_path = f"/v1{path}" if path.startswith("/") else f"/v1/{path}"
        if v1_path in paths:
            op = paths[v1_path].get(method.lower())
            if op:
                return op
    return None


def _schema_for_status(
    operation: dict[str, Any], status_code: str = "200"
) -> dict[str, Any] | None:
    """Extract and resolve the response schema for a given HTTP status."""
    responses = operation.get("responses", {})
    resp = responses.get(status_code) or responses.get("default")
    if not resp:
        return None
    content = resp.get("content", {})
    json_content = content.get("application/json", content.get("*/*", {}))
    raw = json_content.get("schema")
    if raw:
        return resolve_refs(raw)
    return None


def extract_endpoint_schema(
    openapi: dict[str, Any], method: str, path: str
) -> dict[str, Any] | None:
    """Extract the full response schema for an endpoint from the OpenAPI spec.

    Returns a dict with ``method``, ``path``, ``operationId``, ``parameters``,
    ``requestBody``, and ``response_200`` / ``response_422`` / ``response_401``
    — all with ``$ref`` resolved to inline schemas.
    """
    operation = _find_path_item(openapi, method, path)
    if not operation:
        return None

    result: dict[str, Any] = {
        "method": method,
        "path": path,
        "operationId": operation.get("operationId", ""),
        "parameters": resolve_refs(operation.get("parameters", [])),
        "requestBody": resolve_refs(operation.get("requestBody")),
        "response_200": _schema_for_status(operation, "200"),
        "response_401": _schema_for_status(operation, "401"),
        "response_403": _schema_for_status(operation, "403"),
        "response_422": _schema_for_status(operation, "422"),
    }
    return result


# ---------------------------------------------------------------------------
# Snapshot management
# ---------------------------------------------------------------------------


def _snapshot_path(method: str, path: str) -> Path:
    """Convert ``/v1/user/me`` -> ``GET_v1_user_me.json``."""
    safe = f"{method.upper()}_{path.replace('/', '_').strip('_')}"
    safe = safe.replace("{", "_").replace("}", "_")
    return SNAPSHOT_DIR / f"{safe}.json"


def load_snapshot(method: str, path: str) -> dict[str, Any] | None:
    """Load a previously committed snapshot for the given endpoint."""
    fp = _snapshot_path(method, path)
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(
            f"  [WARN] Corrupted snapshot {fp.name}: {exc}. "
            f"Run --snapshot to regenerate.",
            file=sys.stderr,
        )
        return None


def save_snapshot(method: str, path: str, data: dict[str, Any]) -> Path:
    """Persist an endpoint schema snapshot."""
    fp = _snapshot_path(method, path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return fp


# ---------------------------------------------------------------------------
# Schema diff (inline — avoids importing from backend/tests/contracts)
# ---------------------------------------------------------------------------


def _diff_shapes(schema_a: dict, schema_b: dict, path: str = "<root>") -> list[str]:
    """Return a human-readable diff between two JSON schemas.

    Reports added fields, removed fields, type changes, and required-set
    changes.  Mirrors ``backend/tests/contracts/contract_validator.diff_shapes``.
    """
    diffs: list[str] = []

    type_a = schema_a.get("type")
    type_b = schema_b.get("type")
    if type_a != type_b:
        diffs.append(f"TYPE_CHANGED at {path}: {type_a!r} -> {type_b!r}")

    if type_a == "object" and type_b == "object":
        props_a = schema_a.get("properties", {}) or {}
        props_b = schema_b.get("properties", {}) or {}
        req_a = set(schema_a.get("required", []) or [])
        req_b = set(schema_b.get("required", []) or [])

        added = sorted(set(props_b) - set(props_a))
        removed = sorted(set(props_a) - set(props_b))
        for name in added:
            diffs.append(f"FIELD_ADDED at {path}.{name}")
        for name in removed:
            diffs.append(f"FIELD_REMOVED at {path}.{name}")

        became_required = sorted(req_b - req_a - set(added))
        became_optional = sorted(req_a - req_b - set(removed))
        for name in became_required:
            diffs.append(f"REQUIRED_ADDED at {path}.{name}")
        for name in became_optional:
            diffs.append(f"REQUIRED_REMOVED at {path}.{name}")

        for name in sorted(set(props_a) & set(props_b)):
            diffs.extend(_diff_shapes(props_a[name], props_b[name], f"{path}.{name}"))

    elif type_a == "array" and type_b == "array":
        items_a = schema_a.get("items") or {}
        items_b = schema_b.get("items") or {}
        diffs.extend(_diff_shapes(items_a, items_b, f"{path}[]"))

    return diffs


def compare_schemas(
    current: dict[str, Any], previous: dict[str, Any], label: str
) -> list[str]:
    """Compare two endpoint schemas and return drift descriptions.

    Detects added/removed fields, type changes, required-set changes,
    parameter changes, and request body changes.
    """
    diffs: list[str] = []

    # --- Response schema drift ---
    for key in ("response_200", "response_201", "response_422", "response_401"):
        cur_val = current.get(key)
        prev_val = previous.get(key)
        if prev_val and not cur_val:
            diffs.append(f"[{label}] {key}: REMOVED")
        elif cur_val and not prev_val:
            diffs.append(f"[{label}] {key}: ADDED")
        elif cur_val and prev_val:
            diffs.extend(_diff_shapes(prev_val, cur_val, f"{label}.{key}"))

    # --- Parameters drift ---
    cur_p = {p.get("name", "?"): p for p in current.get("parameters", [])}
    prev_p = {p.get("name", "?"): p for p in previous.get("parameters", [])}
    for n in sorted(set(cur_p) - set(prev_p)):
        diffs.append(f"[{label}] PARAM_ADDED: {n}")
    for n in sorted(set(prev_p) - set(cur_p)):
        diffs.append(f"[{label}] PARAM_REMOVED: {n}")

    # --- Request body drift ---
    cur_rb = current.get("requestBody")
    prev_rb = previous.get("requestBody")
    if prev_rb and not cur_rb:
        diffs.append(f"[{label}] REQUEST_BODY_REMOVED")
    elif cur_rb and not prev_rb:
        diffs.append(f"[{label}] REQUEST_BODY_ADDED")

    return diffs


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


def _validate_headers(response: Any, path: str) -> list[str]:
    """Validate required headers on a response."""
    issues: list[str] = []
    ct = response.headers.get("content-type", "")
    if not ct and response.status_code < 400:
        issues.append(f"[{path}] MISSING_HEADER: content-type")
    return issues


def validate_response(
    method: str,
    path: str,
    status_code: int,
    body: Any,
    operation: dict[str, Any] | None,
    response: Any,
) -> list[str]:
    """Validate an actual HTTP response against the OpenAPI schema."""
    issues: list[str] = []
    issues.extend(_validate_headers(response, path))

    if not operation:
        return issues

    # Status code validation
    expected = set()
    for key in operation.get("responses", {}):
        try:
            expected.add(int(key))
        except (ValueError, TypeError):
            pass
    if expected and status_code not in expected:
        issues.append(
            f"[{path}] STATUS_MISMATCH: got {status_code}, "
            f"expected one of {sorted(expected)}"
        )

    # Body schema validation
    status_schema = _schema_for_status(operation, str(status_code))
    if status_schema and body is not None:
        val = _validate_shape(body, status_schema)
        if not val["valid"]:
            for err in val["errors"]:
                issues.append(f"[{path}] SCHEMA_ERROR ({status_code}): {err}")

    return issues


def _validate_shape(sample: Any, schema: dict) -> dict[str, Any]:
    """Lightweight jsonschema validation (avoids importing jsonschema runtime).

    Checks type and required fields recursively.  Returns
    ``{"valid": True}`` or ``{"valid": False, "errors": [...]}``.
    """
    errors: list[str] = []
    _validate_recursive(sample, schema, "<root>", errors)
    return {"valid": len(errors) == 0, "errors": errors}


def _validate_recursive(
    value: Any, schema: dict, path: str, errors: list[str]
) -> None:
    schema_type = schema.get("type")
    if not schema_type:
        return
    if schema_type == "object":
        if not isinstance(value, dict):
            errors.append(f"TYPE_MISMATCH at {path}: expected object, got {type(value).__name__}")
            return
        props = schema.get("properties", {})
        for required_field in schema.get("required", []):
            if required_field not in value:
                errors.append(f"MISSING_REQUIRED at {path}.{required_field}")
        for key, sub_schema in props.items():
            if key in value:
                _validate_recursive(value[key], sub_schema, f"{path}.{key}", errors)
    elif schema_type == "array":
        if not isinstance(value, list):
            errors.append(f"TYPE_MISMATCH at {path}: expected array, got {type(value).__name__}")
            return
        items_schema = schema.get("items", {})
        for i, item in enumerate(value):
            _validate_recursive(item, items_schema, f"{path}[{i}]", errors)
    elif schema_type == "string":
        if not isinstance(value, str):
            errors.append(f"TYPE_MISMATCH at {path}: expected string, got {type(value).__name__}")
    elif schema_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"TYPE_MISMATCH at {path}: expected integer, got {type(value).__name__}")
    elif schema_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            errors.append(f"TYPE_MISMATCH at {path}: expected number, got {type(value).__name__}")
    elif schema_type == "boolean":
        if not isinstance(value, bool):
            errors.append(f"TYPE_MISMATCH at {path}: expected boolean, got {type(value).__name__}")
    # null type — accept None


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def run_snapshot(openapi: dict[str, Any]) -> tuple[int, int]:
    """Extract and save current endpoint schemas as snapshots."""
    saved = 0
    failed = 0
    for method, path, category, _ in CRITICAL_ENDPOINTS:
        ep = extract_endpoint_schema(openapi, method, path)
        if ep:
            ep["_snapshot_meta"] = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "category": category,
                "endpoint": f"{method} {path}",
            }
            save_snapshot(method, path, ep)
            print(f"  [OK] Saved snapshot: {_snapshot_path(method, path).name}")
            saved += 1
        else:
            print(f"  [SKIP] {method} {path} — not found in OpenAPI schema")
            failed += 1
    return saved, failed


def run_check(openapi: dict[str, Any]) -> int:
    """Compare current endpoint schemas against committed snapshots.

    Returns the number of endpoints with drift.
    """
    all_diffs: list[str] = []
    for method, path, *_ in CRITICAL_ENDPOINTS:
        current = extract_endpoint_schema(openapi, method, path)
        previous = load_snapshot(method, path)
        if not previous:
            print(f"  [NEW] {method} {path} — no previous snapshot (use --snapshot)")
            continue
        if not current:
            print(f"  [MISSING] {method} {path} — not found in OpenAPI schema")
            continue
        diffs = compare_schemas(current, previous, f"{method} {path}")
        if diffs:
            all_diffs.extend(diffs)
            print(f"\n  [DRIFT] {method} {path}:")
            for d in diffs:
                print(f"    {d}")
        else:
            print(f"  [OK] {method} {path} — no drift")

    if all_diffs:
        rel = SNAPSHOT_DIR.relative_to(REPO_ROOT)
        print(
            f"\n  [!] {len(all_diffs)} drift(s) detected. "
            f"Run `python scripts/contract-test.py --snapshot` "
            f"to update snapshots in {rel}/",
            file=sys.stderr,
        )
    return len(all_diffs)


def run_test(openapi: dict[str, Any], base_url: str) -> int:
    """Validate actual API responses against OpenAPI schemas."""
    import httpx

    issues: list[str] = []
    tested = 0
    skipped = 0

    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        for method, path, *_ in CRITICAL_ENDPOINTS:
            resolved = _resolve_path(method, path)
            op = _find_path_item(openapi, method, resolved)
            if not op:
                print(f"  [SKIP] {method} {resolved} — not in OpenAPI schema")
                skipped += 1
                continue

            body_kw: dict = {}
            if method == "POST" and openapi.get("paths", {}).get(resolved, {}).get(
                method.lower(), {}
            ).get("requestBody"):
                body_kw["json"] = {}

            try:
                resp = getattr(client, method.lower())(resolved, **body_kw)
            except httpx.RequestError as exc:
                issues.append(f"[{method} {resolved}] REQUEST_FAILED: {exc}")
                continue

            try:
                resp_body = resp.json() if resp.text else None
            except ValueError:
                resp_body = None

            errs = validate_response(method, resolved, resp.status_code, resp_body, op, resp)
            if errs:
                issues.extend(errs)
                for e in errs:
                    print(f"  [FAIL] {e}")
            else:
                tag = "OK" if resp.status_code < 400 else "EXPECTED_ERROR"
                print(f"  [{tag}] {method} {resolved} -> {resp.status_code}")
            tested += 1

    print(
        f"\n  Tested {tested} endpoints ({skipped} skipped). "
        f"{len(issues)} issue(s)."
    )
    return len(issues)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Contract tests — runtime type safety between frontend and backend",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  cd backend && python ../scripts/contract-test.py\n"
            "  cd backend && python ../scripts/contract-test.py --snapshot\n"
            "  python scripts/contract-test.py --test --base-url http://localhost:8000\n"
        ),
    )
    p.add_argument(
        "--snapshot", action="store_true", help="Update endpoint schema snapshots"
    )
    p.add_argument(
        "--test",
        action="store_true",
        help="Validate actual API responses against OpenAPI schemas",
    )
    p.add_argument(
        "--base-url",
        default=os.getenv("CONTRACT_TEST_BASE_URL", "http://localhost:8000"),
        help="Backend base URL (default: $CONTRACT_TEST_BASE_URL or "
        "http://localhost:8000)",
    )
    return p.parse_args(argv)


def main() -> int:
    args = parse_args()

    # Run from backend/ unless already there
    cwd = Path.cwd()
    backend_dir = REPO_ROOT / "backend"
    if cwd.resolve() != backend_dir.resolve():
        os.chdir(str(backend_dir))

    print("Extracting OpenAPI schema from FastAPI app...", flush=True)
    openapi = extract_openapi()
    if openapi is None:
        print("[ERROR] Could not extract OpenAPI schema.", file=sys.stderr)
        return 1

    pc = len(openapi.get("paths", {}))
    sc = len(openapi.get("components", {}).get("schemas", {}))
    print(f"  Found {pc} paths, {sc} component schemas.\n")

    exit_code = 0

    if args.snapshot:
        print("=== Snapshot mode ===\n")
        saved, failed = run_snapshot(openapi)
        print(f"\n  Saved {saved} snapshots ({failed} not found)\n")

    # Always check drift against existing snapshots
    snap_files = list(SNAPSHOT_DIR.glob("*.json"))
    if snap_files:
        print("=== Drift check ===\n")
        drift = run_check(openapi)
        if drift > 0:
            exit_code = 1
        print()
    elif not args.snapshot:
        print("[WARN] No snapshots found. Run with --snapshot first.\n", file=sys.stderr)

    if args.test:
        print(f"=== Response validation against {args.base_url} ===\n")
        n = run_test(openapi, args.base_url)
        if n > 0:
            exit_code = 1
        print()

    if exit_code == 0:
        print("Contract test: PASSED")
    else:
        print("Contract test: FAILED", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
