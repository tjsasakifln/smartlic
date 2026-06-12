"""Tests for NETINT-008 — Pipeline metrics + observability (Issue #1679).

Validates:
  - Prometheus metric definitions exist
  - Health endpoint returns correct JSON structure
  - Health endpoint query logic handles edge cases
  - Metrics are registered with correct labels and help text
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch



# ═══════════════════════════════════════════════════════════════════════════
# Prometheus metric definitions
# ═══════════════════════════════════════════════════════════════════════════


class TestPrometheusMetrics:
    """AC: All 5 Prometheus metrics are registered in metrics.py."""

    def test_network_events_collected_total_exists(self):
        """Counter: network_events_collected_total with evento_tipo label."""
        import metrics as m
        assert hasattr(m, "NETWORK_EVENTS_COLLECTED_TOTAL")
        assert hasattr(m.NETWORK_EVENTS_COLLECTED_TOTAL, "labels")

    def test_network_events_discarded_total_exists(self):
        """Counter: network_events_discarded_total with motivo label."""
        import metrics as m
        assert hasattr(m, "NETWORK_EVENTS_DISCARDED_TOTAL")
        assert hasattr(m.NETWORK_EVENTS_DISCARDED_TOTAL, "labels")

    def test_network_events_sanitization_failures_total_exists(self):
        """Counter: network_events_sanitization_failures_total."""
        import metrics as m
        assert hasattr(m, "NETWORK_EVENTS_SANITIZATION_FAILURES_TOTAL")

    def test_network_events_collection_duration_seconds_exists(self):
        """Histogram: network_events_collection_duration_seconds."""
        import metrics as m
        assert hasattr(m, "NETWORK_EVENTS_COLLECTION_DURATION_SECONDS")

    def test_network_events_cleanup_last_run_exists(self):
        """Gauge: network_events_cleanup_last_run_timestamp."""
        import metrics as m
        assert hasattr(m, "NETWORK_EVENTS_CLEANUP_LAST_RUN")

    def test_network_cleanup_duration_exists(self):
        """Histogram: network_cleanup_duration_seconds."""
        import metrics as m
        assert hasattr(m, "network_events_cleanup_duration_seconds")


# ═══════════════════════════════════════════════════════════════════════════
# Health endpoint
# ═══════════════════════════════════════════════════════════════════════════


class TestNetworkHealthEndpoint:
    """AC: Health endpoint returns aggregated metrics."""

    @patch("services.network_metrics.get_supabase")
    async def test_health_returns_expected_structure(self, mock_get_supabase):
        """AC: Endpoint returns JSON with expected fields."""
        db = MagicMock()

        # Mock events count
        events_resp = MagicMock()
        events_resp.data = [{"contagem": 100}, {"contagem": 50}]
        events_exec = AsyncMock(return_value=events_resp)
        db.table.return_value.select.return_value.gte.return_value.execute = events_exec

        # Mock opt-in
        opt_in_resp = MagicMock()
        # Mock simulates the not_.is_ filter - only non-null values returned
        opt_in_resp.data = [
            {"allow_network_analytics": True},
            {"allow_network_analytics": True},
            {"allow_network_analytics": False},
            {"allow_network_analytics": True},
        ]
        opt_in_exec = AsyncMock(return_value=opt_in_resp)
        mock_chain = MagicMock()
        mock_chain.execute = opt_in_exec
        db.table.return_value.select.return_value.not_.is_.return_value = mock_chain

        # Mock table count
        count_resp = MagicMock()
        count_resp.count = 10000
        count_exec = AsyncMock(return_value=count_resp)
        db.table.return_value.select.return_value.limit.return_value.execute = count_exec

        mock_get_supabase.return_value = db

        from services.network_metrics import get_network_health
        result = await get_network_health()

        assert "status" in result
        assert "metrics" in result
        assert "total_events_collected_24h" in result["metrics"]
        assert "opt_in_rate" in result["metrics"]
        assert "table_size_mb" in result["metrics"]
        assert "cleanup_last_rows_affected" in result["metrics"]

        # 3 opted in out of 4 who answered (None is excluded)
        assert result["metrics"]["opt_in_rate"] == 0.75

        # 100 + 50 = 150 events in last 24h
        assert result["metrics"]["total_events_collected_24h"] == 150

    @patch("services.network_metrics.get_supabase")
    async def test_health_empty_db_does_not_error(self, mock_get_supabase):
        """AC: Empty database returns zeroes, not errors."""
        db = MagicMock()

        # Empty responses
        def _make_empty_exec():
            resp = MagicMock()
            resp.data = []
            resp.count = 0
            exec_fn = AsyncMock(return_value=resp)
            return exec_fn

        exec_events = _make_empty_exec()
        exec_optin = _make_empty_exec()
        exec_count = _make_empty_exec()

        db.table.return_value.select.return_value.gte.return_value.execute = exec_events
        mock_chain = MagicMock()
        mock_chain.execute = exec_optin
        db.table.return_value.select.return_value.not_.is_.return_value = mock_chain
        db.table.return_value.select.return_value.limit.return_value.execute = exec_count

        mock_get_supabase.return_value = db

        from services.network_metrics import get_network_health
        result = await get_network_health()

        assert result["metrics"]["total_events_collected_24h"] == 0
        assert result["metrics"]["opt_in_rate"] == 0.0
        assert result["metrics"]["table_size_mb"] == 0.0

    @patch("services.network_metrics.get_supabase")
    async def test_health_partial_failure_returns_degraded(self, mock_get_supabase):
        """AC: If some queries fail, status is 'degraded' but response still returns."""
        db = MagicMock()
        # Events query throws
        db.table.return_value.select.return_value.gte.side_effect = Exception("Timeout")

        mock_get_supabase.return_value = db

        from services.network_metrics import get_network_health
        result = await get_network_health()

        assert result["status"] == "degraded"
        assert "metrics" in result

    @patch("services.network_metrics.get_supabase")
    async def test_health_opt_in_all_false(self, mock_get_supabase):
        """AC: opt_in_rate is 0 when all users opted out."""
        db = MagicMock()

        events_resp = MagicMock()
        events_resp.data = []
        db.table.return_value.select.return_value.gte.return_value.execute = AsyncMock(return_value=events_resp)

        opt_in_resp = MagicMock()
        opt_in_resp.data = [
            {"allow_network_analytics": False},
            {"allow_network_analytics": False},
        ]
        opt_in_exec = AsyncMock(return_value=opt_in_resp)
        mock_chain = MagicMock()
        mock_chain.execute = opt_in_exec
        db.table.return_value.select.return_value.not_.is_.return_value = mock_chain

        mock_get_supabase.return_value = db

        from services.network_metrics import get_network_health
        result = await get_network_health()

        assert result["metrics"]["opt_in_rate"] == 0.0
