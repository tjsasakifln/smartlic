"""Issue #1041: SEO 404 Prometheus middleware.

Detects HTTP 404 responses on programmatic SEO route prefixes and increments
``smartlic_seo_404_total{route_type, reason}`` (defined in ``metrics.py``).

Why a dedicated counter (instead of derived from ``HTTP_RESPONSES_TOTAL``):
- Programmatic SEO drives the primary inbound funnel (10k+ ISR pages). 404s
  silently raise Google de-indexation risk if not alerted before the crawler
  re-checks. A per-route-type counter enables a Sentry rate alert
  (``seo_404_rate > 0.5%/24h``) without slicing the global 4xx counter.
- Labels stay deliberately low cardinality: ``route_type`` is the first non-/v1/
  segment (~15 known prefixes); ``reason`` has 4 enum values.

Operates purely on the response object so it never touches route handlers
(avoids races with concurrent route refactors). Safe under graceful Prometheus
fallback — ``SEO_404_TOTAL`` is a ``_NoopMetric`` when ``prometheus_client``
isn't installed.
"""
from __future__ import annotations

import logging
from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


# Programmatic SEO prefixes (whitelist). All registered under /v1/ in
# ``startup/routes.py::register_routes`` (every router goes through
# ``app.include_router(r, prefix="/v1")``). Public, no-auth routers that drive
# organic inbound — see ``.claude/rules/architecture-detail.md`` SEO Programmatic.
_SEO_ROUTE_PREFIXES: tuple[str, ...] = (
    "/v1/observatorio",
    "/v1/cnpj",
    "/v1/orgao",        # covers /v1/orgao/* and /v1/orgaos/*
    "/v1/orgaos",
    "/v1/contratos",
    "/v1/municipios",
    "/v1/itens",
    "/v1/compliance",
    "/v1/alertas",
    "/v1/sectors",
    "/v1/setores",
    "/v1/blog",
    "/v1/dados",
    "/v1/empresa",
    "/v1/fornecedores",
    "/v1/indice-municipal",
    "/v1/calculadora",
    "/v1/comparador",
)

_VALID_REASONS = frozenset({"malformed_slug", "empty_data", "timeout", "unknown"})


def _route_type_for(path: str, prefixes: Iterable[str] = _SEO_ROUTE_PREFIXES) -> str | None:
    """Return route_type label for *path* if it matches a SEO prefix, else None.

    The label is the first non-version segment (e.g. ``/v1/observatorio/raio-x/123``
    → ``observatorio``). Kept low cardinality on purpose.
    """
    for prefix in prefixes:
        if path == prefix or path.startswith(prefix + "/"):
            # First segment after /v1/ — strip leading slash and split.
            tail = path[len("/v1/"):] if path.startswith("/v1/") else path.lstrip("/")
            head = tail.split("/", 1)[0] if tail else ""
            return head or None
    return None


def _reason_for(response: Response) -> str:
    """Infer the reason label from response headers.

    Header-based hints are preferred over body inspection (cheaper, no
    streaming-body re-read). Routes that already classify 404s can advertise
    via ``X-SEO-404-Reason: malformed_slug|empty_data|timeout``. Anything
    else falls through to ``unknown`` so the counter still increments.
    """
    hint = response.headers.get("X-SEO-404-Reason", "").strip().lower()
    if hint in _VALID_REASONS:
        return hint
    # Soft heuristics from common existing headers.
    coverage = response.headers.get("X-Coverage-Status", "").strip().lower()
    if coverage in {"empty", "no-data", "no_data"}:
        return "empty_data"
    return "unknown"


class SEO404MetricsMiddleware(BaseHTTPMiddleware):
    """Increment ``SEO_404_TOTAL`` on programmatic SEO 404s.

    Place AFTER tracing middleware (added later → outermost runs earlier;
    we want the *final* status code, so this should be added near the
    response-tracking middlewares — see ``startup/middleware_setup.py``).
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response = await call_next(request)
        try:
            if response.status_code == 404:
                route_type = _route_type_for(request.url.path)
                if route_type:
                    reason = _reason_for(response)
                    from metrics import SEO_404_TOTAL
                    SEO_404_TOTAL.labels(route_type=route_type, reason=reason).inc()
        except Exception:  # pragma: no cover — defensive, never break the response
            logger.exception("seo_404_middleware: failed to record metric")
        return response
