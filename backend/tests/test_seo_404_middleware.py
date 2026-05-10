"""Issue #1041: Tests for ``smartlic_seo_404_total`` counter + middleware.

Strategy:
- Build a minimal Starlette app wired only with ``SEO404MetricsMiddleware``.
- Define routes mimicking real SEO prefixes (``/v1/observatorio/...``,
  ``/v1/cnpj/...``) and a non-SEO control route (``/v1/admin/foo``).
- Assert the Prometheus counter is incremented exactly when expected, by
  comparing snapshots from ``REGISTRY.get_sample_value`` before/after each
  request. This avoids depending on the full FastAPI app and its 30+ env
  requirements (Supabase, Stripe, etc.) — keeps the test fast (<1s) and hermetic.
"""
from __future__ import annotations

import pytest

pytest.importorskip("prometheus_client")
from prometheus_client import REGISTRY  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.responses import JSONResponse, Response  # noqa: E402
from starlette.routing import Route  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from seo_404_middleware import (  # noqa: E402
    SEO404MetricsMiddleware,
    _reason_for,
    _route_type_for,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# prometheus_client strips the trailing ``_total`` from Counter names internally,
# then re-appends ``_total`` for the sample name. So a Counter declared as
# ``smartlic_seo_404_total`` exposes:
#   - metric family name : "smartlic_seo_404"
#   - cumulative sample  : "smartlic_seo_404_total"
_METRIC_FAMILY = "smartlic_seo_404"
_SAMPLE_NAME = "smartlic_seo_404_total"


def _counter_value(route_type: str, reason: str) -> float:
    """Read the current value of the counter for the given label pair.

    ``REGISTRY.get_sample_value`` returns ``None`` when the labelset has not
    been observed yet — normalise to 0.0 so deltas are arithmetic.
    """
    val = REGISTRY.get_sample_value(
        _SAMPLE_NAME,
        labels={"route_type": route_type, "reason": reason},
    )
    return val if val is not None else 0.0


def _make_app() -> Starlette:
    async def observatorio_404(request):  # malformed slug → 404
        return JSONResponse({"detail": "not found"}, status_code=404)

    async def cnpj_404_with_reason(request):
        # Route advertises why it 404'd via header — middleware should pick it up.
        return JSONResponse(
            {"detail": "no rows"},
            status_code=404,
            headers={"X-SEO-404-Reason": "empty_data"},
        )

    async def cnpj_200(request):
        return JSONResponse({"ok": True})

    async def admin_404(request):  # non-SEO route — must NOT increment counter
        return JSONResponse({"detail": "not found"}, status_code=404)

    app = Starlette(
        routes=[
            Route("/v1/observatorio/relatorio/{mes}/{ano}", observatorio_404),
            Route("/v1/cnpj/{cnpj}/missing", cnpj_404_with_reason),
            Route("/v1/cnpj/{cnpj}", cnpj_200),
            Route("/v1/admin/foo", admin_404),
        ],
    )
    app.add_middleware(SEO404MetricsMiddleware)
    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(_make_app())


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestRouteTypeFor:
    """`_route_type_for` returns the first non-version segment for SEO paths."""

    @pytest.mark.parametrize(
        "path, expected",
        [
            ("/v1/observatorio/relatorio/3/2026", "observatorio"),
            ("/v1/cnpj/12345678000199", "cnpj"),
            ("/v1/orgao/abc", "orgao"),
            ("/v1/orgaos/abc", "orgaos"),
            ("/v1/contratos/saude/sp", "contratos"),
            ("/v1/municipios/sao-paulo-sp", "municipios"),
            ("/v1/blog/licitacoes/saude", "blog"),
            ("/v1/dados/abertos", "dados"),
        ],
    )
    def test_seo_prefixes_match(self, path: str, expected: str) -> None:
        assert _route_type_for(path) == expected

    @pytest.mark.parametrize(
        "path",
        [
            "/v1/admin/foo",
            "/v1/buscar",
            "/v1/pipeline",
            "/health/live",
            "/metrics",
            "/v1/user/me",
        ],
    )
    def test_non_seo_paths_return_none(self, path: str) -> None:
        assert _route_type_for(path) is None


class TestReasonFor:
    """`_reason_for` prefers the explicit header, then heuristics, then unknown."""

    def test_explicit_header_wins(self) -> None:
        resp = Response(status_code=404, headers={"X-SEO-404-Reason": "malformed_slug"})
        assert _reason_for(resp) == "malformed_slug"

    def test_invalid_header_falls_back_to_unknown(self) -> None:
        resp = Response(status_code=404, headers={"X-SEO-404-Reason": "lol"})
        assert _reason_for(resp) == "unknown"

    def test_coverage_status_empty_maps_to_empty_data(self) -> None:
        resp = Response(status_code=404, headers={"X-Coverage-Status": "empty"})
        assert _reason_for(resp) == "empty_data"

    def test_no_hints_unknown(self) -> None:
        resp = Response(status_code=404)
        assert _reason_for(resp) == "unknown"


# ---------------------------------------------------------------------------
# Middleware behavior — increment / no-increment
# ---------------------------------------------------------------------------


class TestSEO404MiddlewareIncrements:
    def test_404_on_seo_route_increments_counter(self, client: TestClient) -> None:
        before = _counter_value("observatorio", "unknown")
        resp = client.get("/v1/observatorio/relatorio/99/9999")
        assert resp.status_code == 404
        after = _counter_value("observatorio", "unknown")
        assert after == before + 1.0

    def test_404_with_reason_header_uses_that_reason(self, client: TestClient) -> None:
        before = _counter_value("cnpj", "empty_data")
        resp = client.get("/v1/cnpj/00000000000000/missing")
        assert resp.status_code == 404
        after = _counter_value("cnpj", "empty_data")
        assert after == before + 1.0

    def test_404_on_non_seo_route_does_not_increment_any_label(
        self, client: TestClient
    ) -> None:
        # Snapshot ALL existing label combos for this metric before the request.
        before: dict[tuple[str, str], float] = {}
        for metric in REGISTRY.collect():
            if metric.name != _METRIC_FAMILY:
                continue
            for sample in metric.samples:
                if sample.name == _SAMPLE_NAME:
                    key = (sample.labels.get("route_type", ""), sample.labels.get("reason", ""))
                    before[key] = sample.value

        resp = client.get("/v1/admin/foo")
        assert resp.status_code == 404

        # No label combination should have grown.
        for metric in REGISTRY.collect():
            if metric.name != _METRIC_FAMILY:
                continue
            for sample in metric.samples:
                if sample.name == _SAMPLE_NAME:
                    key = (sample.labels.get("route_type", ""), sample.labels.get("reason", ""))
                    assert sample.value == before.get(key, 0.0), (
                        f"Non-SEO 404 leaked into label {key}"
                    )

    def test_2xx_on_seo_route_does_not_increment(self, client: TestClient) -> None:
        before = _counter_value("cnpj", "unknown")
        resp = client.get("/v1/cnpj/12345678000199")
        assert resp.status_code == 200
        after = _counter_value("cnpj", "unknown")
        assert after == before
