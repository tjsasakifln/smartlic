"""Issue #640: Tests for calculate_wedge_risk() and wedge_risk field in /health/ready."""
import time
from unittest.mock import patch, MagicMock, AsyncMock

import pytest


# ---------------------------------------------------------------------------
# Unit tests for calculate_wedge_risk()
# ---------------------------------------------------------------------------

class TestCalculateWedgeRisk:
    """Unit tests for health.calculate_wedge_risk()."""

    def setup_method(self):
        import health
        health._counter_baseline.clear()

    def _make_counter_sample(self, value: float):
        """Build a minimal Prometheus MetricFamily mock with a single sample."""
        sample = MagicMock()
        sample.value = value
        metric_family = MagicMock()
        metric_family.samples = [sample]
        return metric_family

    def test_low_when_pools_nominal(self):
        """wedge_risk=low when pool stats are normal and no budget exceeded."""
        with (
            patch("redis_pool.get_pool_stats", return_value={"used": 5, "max": 20}),
            patch("metrics.PIPELINE_BUDGET_EXCEEDED_TOTAL") as mock_pb,
            patch("metrics.ROUTE_TIMEOUT_TOTAL") as mock_rt,
        ):
            mock_pb.collect.return_value = [self._make_counter_sample(0)]
            mock_rt.collect.return_value = [self._make_counter_sample(0)]

            from health import calculate_wedge_risk
            result = calculate_wedge_risk()
            assert result == "low"

    def test_medium_when_pool_50_to_80_percent(self):
        """wedge_risk=medium when Redis pool is 60% saturated."""
        with (
            patch("redis_pool.get_pool_stats", return_value={"used": 12, "max": 20}),
            patch("metrics.PIPELINE_BUDGET_EXCEEDED_TOTAL") as mock_pb,
            patch("metrics.ROUTE_TIMEOUT_TOTAL") as mock_rt,
        ):
            mock_pb.collect.return_value = [self._make_counter_sample(0)]
            mock_rt.collect.return_value = [self._make_counter_sample(0)]

            from health import calculate_wedge_risk
            result = calculate_wedge_risk()
            assert result == "medium"

    def test_high_when_pool_over_80_percent(self):
        """wedge_risk=high when Redis pool is >80% saturated."""
        with (
            patch("redis_pool.get_pool_stats", return_value={"used": 17, "max": 20}),
            patch("metrics.PIPELINE_BUDGET_EXCEEDED_TOTAL") as mock_pb,
            patch("metrics.ROUTE_TIMEOUT_TOTAL") as mock_rt,
        ):
            mock_pb.collect.return_value = [self._make_counter_sample(0)]
            mock_rt.collect.return_value = [self._make_counter_sample(0)]

            from health import calculate_wedge_risk
            result = calculate_wedge_risk()
            assert result == "high"

    def test_high_when_pipeline_budget_exceeded(self):
        """wedge_risk=high when pipeline_budget_exceeded counter > 0."""
        with (
            patch("redis_pool.get_pool_stats", return_value={"used": 2, "max": 20}),
            patch("metrics.PIPELINE_BUDGET_EXCEEDED_TOTAL") as mock_pb,
            patch("metrics.ROUTE_TIMEOUT_TOTAL") as mock_rt,
        ):
            mock_pb.collect.return_value = [self._make_counter_sample(1)]  # > 0
            mock_rt.collect.return_value = [self._make_counter_sample(0)]

            from health import calculate_wedge_risk
            result = calculate_wedge_risk()
            assert result == "high"

    def test_high_when_route_timeout_triggered(self):
        """wedge_risk=high when route_timeout counter > 0 (sync .execute() wedge)."""
        with (
            patch("redis_pool.get_pool_stats", return_value={"used": 2, "max": 20}),
            patch("metrics.PIPELINE_BUDGET_EXCEEDED_TOTAL") as mock_pb,
            patch("metrics.ROUTE_TIMEOUT_TOTAL") as mock_rt,
        ):
            mock_pb.collect.return_value = [self._make_counter_sample(0)]
            mock_rt.collect.return_value = [self._make_counter_sample(3)]  # > 0

            from health import calculate_wedge_risk
            result = calculate_wedge_risk()
            assert result == "high"

    def test_unknown_when_redis_pool_raises(self):
        """wedge_risk=unknown when get_pool_stats raises (e.g. Redis offline)."""
        with patch("redis_pool.get_pool_stats", side_effect=Exception("Redis offline")):
            from health import calculate_wedge_risk
            # Should not raise — returns "unknown"
            result = calculate_wedge_risk()
            assert result == "unknown"

    def test_low_when_pool_stats_zero_max(self):
        """wedge_risk=low when pool max=0 (division-safe — no pool configured)."""
        with (
            patch("redis_pool.get_pool_stats", return_value={"used": 0, "max": 0}),
            patch("metrics.PIPELINE_BUDGET_EXCEEDED_TOTAL") as mock_pb,
            patch("metrics.ROUTE_TIMEOUT_TOTAL") as mock_rt,
        ):
            mock_pb.collect.return_value = [self._make_counter_sample(0)]
            mock_rt.collect.return_value = [self._make_counter_sample(0)]

            from health import calculate_wedge_risk
            result = calculate_wedge_risk()
            assert result == "low"

    def test_unknown_does_not_raise(self):
        """calculate_wedge_risk() never raises even with fully broken imports."""
        with patch("redis_pool.get_pool_stats", side_effect=RuntimeError("catastrophic")):
            from health import calculate_wedge_risk
            result = calculate_wedge_risk()
            assert result == "unknown"


# ---------------------------------------------------------------------------
# Integration tests: /health/ready endpoint includes wedge_risk field
# ---------------------------------------------------------------------------

class TestHealthReadyWedgeRiskField:
    """Integration tests: /health/ready response includes wedge_risk."""

    def _mock_redis_ok(self):
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        return patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis)

    def _mock_supabase_ok(self):
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.limit.return_value = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [{"id": "test"}]
        return (
            patch("supabase_client.sb_execute_direct", new_callable=AsyncMock, return_value=mock_response),
            patch("supabase_client.get_supabase", return_value=mock_sb),
        )

    def _mock_wedge_risk(self, value: str):
        return patch("health.calculate_wedge_risk", return_value=value)

    def test_ready_response_contains_wedge_risk(self):
        """Issue #640 AC1: /health/ready response must include wedge_risk field."""
        from fastapi.testclient import TestClient

        sb_exec_patch, sb_get_patch = self._mock_supabase_ok()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            self._mock_redis_ok(),
            sb_exec_patch,
            sb_get_patch,
            self._mock_wedge_risk("low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert "wedge_risk" in data, "wedge_risk field missing from /health/ready response"

    def test_ready_wedge_risk_low_when_nominal(self):
        """Issue #640 AC2: wedge_risk=low returned when all nominal."""
        from fastapi.testclient import TestClient

        sb_exec_patch, sb_get_patch = self._mock_supabase_ok()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            self._mock_redis_ok(),
            sb_exec_patch,
            sb_get_patch,
            self._mock_wedge_risk("low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            data = response.json()
            assert data["wedge_risk"] == "low"

    def test_ready_wedge_risk_high_when_pool_saturated(self):
        """Issue #640 AC3: wedge_risk=high returned when pool mocked >80%."""
        from fastapi.testclient import TestClient

        sb_exec_patch, sb_get_patch = self._mock_supabase_ok()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            self._mock_redis_ok(),
            sb_exec_patch,
            sb_get_patch,
            self._mock_wedge_risk("high"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            data = response.json()
            assert data["wedge_risk"] == "high"

    def test_ready_wedge_risk_high_does_not_affect_http_status(self):
        """Issue #640: wedge_risk=high must not change HTTP 200 when deps are up.

        The field is additive — it must never block readiness.
        """
        from fastapi.testclient import TestClient

        sb_exec_patch, sb_get_patch = self._mock_supabase_ok()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            self._mock_redis_ok(),
            sb_exec_patch,
            sb_get_patch,
            self._mock_wedge_risk("high"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            # High wedge_risk must NOT trigger 503 — only dep failures do
            assert response.status_code == 200
            data = response.json()
            assert data["ready"] is True
            assert data["wedge_risk"] == "high"

    def test_ready_wedge_risk_unknown_does_not_affect_readiness(self):
        """Issue #640: wedge_risk=unknown (e.g. Redis pool unreachable) must not fail readiness."""
        from fastapi.testclient import TestClient

        sb_exec_patch, sb_get_patch = self._mock_supabase_ok()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            self._mock_redis_ok(),
            sb_exec_patch,
            sb_get_patch,
            self._mock_wedge_risk("unknown"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["wedge_risk"] == "unknown"
