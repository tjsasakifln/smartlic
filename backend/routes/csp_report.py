"""Issue #1913: CSP violation report endpoint for Content-Security-Policy enforcement.

Receives CSP violation reports from browsers (CSP Level 3 spec, both legacy
report-uri format and Reporting API v1). Logs violations to structured logging
for analysis and forwards critical violations to Sentry.

Rate-limited to prevent abuse (30 reports/min per IP via in-memory counter).
"""

import json
import logging
import time
from collections import defaultdict
from fastapi import APIRouter, Request
from fastapi.responses import Response

logger = logging.getLogger("csp")

router = APIRouter(prefix="/v1", tags=["csp"])

# In-memory rate limiter: {ip: [timestamps]}
_reports: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 30          # max reports per window
_RATE_WINDOW_S = 60       # window in seconds
_CLEANUP_INTERVAL = 200   # cleanup every N requests
_cleanup_counter = 0


def _is_rate_limited(ip: str) -> bool:
    """Check if *ip* has exceeded the CSP report rate limit."""
    global _cleanup_counter
    now = time.time()
    cutoff = now - _RATE_WINDOW_S
    timestamps = _reports.get(ip, [])
    # Prune old entries
    _reports[ip] = [t for t in timestamps if t > cutoff]
    current = len(_reports[ip])
    if current >= _RATE_LIMIT:
        return True
    _reports[ip].append(now)
    _cleanup_counter += 1
    if _cleanup_counter >= _CLEANUP_INTERVAL:
        _cleanup_counter = 0
        _cleanup_stale_entries()
    return False


def _cleanup_stale_entries() -> None:
    """Remove entries with no recent activity."""
    now = time.time()
    cutoff = now - _RATE_WINDOW_S
    stale = [k for k, v in _reports.items() if not v or v[-1] < cutoff]
    for k in stale:
        del _reports[k]


def _get_client_ip(request: Request) -> str:
    """Extract client IP from X-Forwarded-For or direct connection."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


@router.post("/csp-report", status_code=204)
async def csp_report(request: Request):
    """Receive CSP violation reports from browsers.

    Accepts both legacy report-uri format (body wraps in "csp-report" key)
    and Reporting API v1 format (top-level fields). Returns 204 No Content
    on success, 429 on rate limit, and logs all violations.
    """
    ip = _get_client_ip(request)

    if _is_rate_limited(ip):
        logger.warning("CSP rate limit exceeded for IP %s", ip)
        return Response(status_code=429)

    try:
        body = await request.json()
    except Exception:
        logger.warning("CSP report received with invalid JSON body from %s", ip)
        return Response(status_code=400)

    # Normalize: legacy report-uri wraps in "csp-report" key
    report = body if "csp-report" not in body else body["csp-report"]

    violated_directive = (
        report.get("violated-directive")
        or report.get("violatedDirective")
        or report.get("effectiveDirective")
        or "unknown"
    )
    blocked_uri = (
        report.get("blocked-uri")
        or report.get("blockedURL")
        or "unknown"
    )
    document_uri = (
        report.get("document-uri")
        or report.get("documentURL")
        or "unknown"
    )
    disposition = report.get("disposition", "enforce")
    source_file = report.get("source-file", report.get("sourceFile", "unknown"))
    line_number = report.get("line-number", report.get("lineNumber", "unknown"))
    column_number = report.get("column-number", report.get("columnNumber", "unknown"))
    sample = report.get("script-sample", report.get("sample", ""))

    # Structured log for observability (picked up by Railway log drain + Sentry)
    log_data = {
        "type": "csp-violation",
        "violated_directive": violated_directive,
        "blocked_uri": blocked_uri,
        "document_uri": document_uri,
        "disposition": disposition,
        "source_file": source_file,
        "line_number": line_number,
        "column_number": column_number,
        "sample": sample,
        "ip": ip,
        "timestamp": time.time(),
    }
    logger.warning("CSP violation: %s", json.dumps(log_data, default=str))

    # Forward to Sentry for analysis
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("csp_violation", "true")
            scope.set_extra("violated_directive", violated_directive)
            scope.set_extra("blocked_uri", blocked_uri)
            scope.set_extra("document_uri", document_uri)
            scope.set_extra("disposition", disposition)
            sentry_sdk.capture_message(
                f"CSP violation: {violated_directive} blocked {blocked_uri}",
                level="warning",
            )
    except Exception:
        pass

    return None  # FastAPI returns 204 with empty body
