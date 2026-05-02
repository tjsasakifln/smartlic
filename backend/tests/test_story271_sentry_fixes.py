"""STORY-271: Resolve All 5 Sentry Unresolved Issues — unit tests.

Tests cover:
  AC2: Pipeline timeout < GUNICORN_TIMEOUT (sufficient buffer)
  AC3: AllSourcesFailedError fallback exists
  AC4: PNCP health canary uses correct params (date format, modalidade, status)

Note: AC1 (WARMING_USER_ID config) removed — cache warming jobs deprecated
2026-04-18 (STORY-CIG-BE-cache-warming-deprecate); WARMING_USER_ID guard
removed as dead code 2026-04-28.

Mock strategy:
  - health.py: patch httpx.AsyncClient to verify request params
  - consolidation: import class constants
"""

import os
import re
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# AC2: Worker timeout buffer
# ---------------------------------------------------------------------------


class TestAC2WorkerTimeout:
    """AC2: Verify pipeline timeout has buffer before GUNICORN_TIMEOUT."""

    def test_degraded_global_timeout_reduced(self):
        """DEGRADED_GLOBAL_TIMEOUT must be <= 100s (15s buffer before 115s gunicorn)."""
        from consolidation import ConsolidationService

        assert ConsolidationService.DEGRADED_GLOBAL_TIMEOUT <= 100

    def test_degraded_global_timeout_is_100(self):
        """DEGRADED_GLOBAL_TIMEOUT should be exactly 100 after STORY-271."""
        from consolidation import ConsolidationService

        assert ConsolidationService.DEGRADED_GLOBAL_TIMEOUT == 100

    def test_failover_timeout_per_source_within_budget(self):
        """FAILOVER_TIMEOUT_PER_SOURCE must be < DEGRADED_GLOBAL_TIMEOUT."""
        from consolidation import ConsolidationService

        assert (
            ConsolidationService.FAILOVER_TIMEOUT_PER_SOURCE
            < ConsolidationService.DEGRADED_GLOBAL_TIMEOUT
        )

    def test_gunicorn_default_in_start_sh(self):
        """start.sh should have GUNICORN_TIMEOUT default of 110.

        DEBT-04 AC1: changed 120 → 110 so Gunicorn aborts before Railway's
        120s proxy timeout, leaving ~10s headroom for response serialization.
        See start.sh comment block for the time-budget waterfall invariant.
        """
        start_sh = os.path.join(os.path.dirname(__file__), "..", "start.sh")
        if os.path.isfile(start_sh):
            with open(start_sh) as f:
                content = f.read()
            assert "GUNICORN_TIMEOUT:-110" in content

    def test_early_return_config_defined(self):
        """EARLY_RETURN_TIME_S and EARLY_RETURN_THRESHOLD_PCT must be in config."""
        from config import EARLY_RETURN_TIME_S, EARLY_RETURN_THRESHOLD_PCT

        assert isinstance(EARLY_RETURN_TIME_S, float)
        assert isinstance(EARLY_RETURN_THRESHOLD_PCT, float)
        assert EARLY_RETURN_TIME_S == 80.0
        assert EARLY_RETURN_THRESHOLD_PCT == 0.66


# ---------------------------------------------------------------------------
# AC4: PNCP health canary
# ---------------------------------------------------------------------------


class TestAC4PNCPHealthCanary:
    """AC4: Verify PNCP health canary uses correct params."""

    @pytest.mark.asyncio
    async def test_pncp_canary_date_format_yyyymmdd(self):
        """PNCP canary must use yyyyMMdd date format, not YYYY-MM-DD."""
        from health import check_source_health

        captured_params = {}

        class FakeResponse:
            status_code = 200

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, params=None):
                captured_params.update(params or {})
                return FakeResponse()

        with patch("health.httpx.AsyncClient", return_value=FakeClient()):
            await check_source_health("PNCP")

        # Date params must be yyyyMMdd (no dashes)
        assert "dataInicial" in captured_params
        assert re.match(r"^\d{8}$", str(captured_params["dataInicial"])), (
            f"dataInicial should be yyyyMMdd format, got: {captured_params['dataInicial']}"
        )
        assert "-" not in str(captured_params["dataInicial"]), (
            "dataInicial must NOT contain dashes"
        )

    @pytest.mark.asyncio
    async def test_pncp_canary_has_modalidade_param(self):
        """PNCP canary must include codigoModalidadeContratacao parameter."""
        from health import check_source_health

        captured_params = {}

        class FakeResponse:
            status_code = 200

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, params=None):
                captured_params.update(params or {})
                return FakeResponse()

        with patch("health.httpx.AsyncClient", return_value=FakeClient()):
            await check_source_health("PNCP")

        assert "codigoModalidadeContratacao" in captured_params, (
            "PNCP canary must include codigoModalidadeContratacao"
        )
        assert captured_params["codigoModalidadeContratacao"] == 6

    @pytest.mark.asyncio
    async def test_pncp_canary_400_is_unhealthy(self):
        """HTTP 400 from PNCP should NOT be treated as healthy."""
        from health import check_source_health, HealthStatus

        class FakeResponse:
            status_code = 400

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, params=None):
                return FakeResponse()

        with patch("health.httpx.AsyncClient", return_value=FakeClient()):
            result = await check_source_health("PNCP")

        # HTTP 400 should be DEGRADED (not HEALTHY as it was before the fix)
        assert result.status != HealthStatus.HEALTHY, (
            "HTTP 400 must NOT be reported as HEALTHY"
        )
        assert result.status == HealthStatus.DEGRADED

    @pytest.mark.asyncio
    async def test_pncp_canary_200_is_healthy(self):
        """HTTP 200 from PNCP should be HEALTHY."""
        from health import check_source_health, HealthStatus

        class FakeResponse:
            status_code = 200

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, params=None):
                return FakeResponse()

        with patch("health.httpx.AsyncClient", return_value=FakeClient()):
            result = await check_source_health("PNCP")

        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_pncp_canary_uses_realistic_page_size(self):
        """PNCP canary should use tamanhoPagina=50 (STORY-316: realistic canary detects page size bug).

        BTS-011 cluster 6 fix: STORY-4.5 added a second probe call via
        `pncp_canary.validate_page_size_limit(client, expected_limit=50)`
        that sends `tamanhoPagina=51`. With a single `captured_params` dict
        the later probe overwrites the canary value and the assertion reads
        51 instead of 50. Switched to collecting all call params in a list
        and asserting the canary (first) call used 50, while also allowing
        the follow-up probe (tamanhoPagina=51) without breaking the test.
        """
        from health import check_source_health

        calls: list[dict] = []

        class FakeResponse:
            status_code = 200

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def get(self, url, params=None):
                calls.append(dict(params or {}))
                return FakeResponse()

        with patch("health.httpx.AsyncClient", return_value=FakeClient()):
            await check_source_health("PNCP")

        # First call is the realistic canary — must be tamanhoPagina=50.
        assert calls, "check_source_health should have issued at least one GET"
        assert calls[0].get("tamanhoPagina") == 50
        # Any follow-up probe (STORY-4.5 validate_page_size_limit) must be
        # exactly 51 — the canary-next check that detects a silent limit bump.
        if len(calls) > 1:
            assert calls[1].get("tamanhoPagina") == 51


# ---------------------------------------------------------------------------
# AC3: AllSourcesFailedError resilience (verification only)
# ---------------------------------------------------------------------------


class TestAC3AllSourcesFailed:
    """AC3: Verify AllSourcesFailedError fallback exists."""

    def test_all_sources_failed_error_defined(self):
        """AllSourcesFailedError exception class must exist."""
        from consolidation import AllSourcesFailedError

        assert issubclass(AllSourcesFailedError, Exception)

    def test_all_sources_failed_error_has_source_errors(self):
        """AllSourcesFailedError must carry source_errors dict."""
        from consolidation import AllSourcesFailedError

        err = AllSourcesFailedError({"PNCP": "timeout", "PCP": "connection refused"})
        assert err.source_errors == {"PNCP": "timeout", "PCP": "connection refused"}
        assert "PNCP" in str(err)

    def test_circuit_breaker_thresholds(self):
        """Circuit breaker thresholds should be reasonable."""
        from pncp_client import (
            PNCP_CIRCUIT_BREAKER_THRESHOLD,
            PNCP_CIRCUIT_BREAKER_COOLDOWN,
        )

        assert PNCP_CIRCUIT_BREAKER_THRESHOLD == 15
        assert PNCP_CIRCUIT_BREAKER_COOLDOWN == 60
