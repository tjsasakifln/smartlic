"""STORY-358: Tests for daily volume metric infrastructure.

Covers:
- AC1: BIDS_PROCESSED_TOTAL Prometheus counter exists and accepts source label
- AC2: record_daily_volume() cron function sums total_raw from search_sessions
- AC3: GET /v1/metrics/daily-volume endpoint — happy path, empty data, DB errors,
       display_value formatting thresholds
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


# ============================================================================
# AC1: BIDS_PROCESSED_TOTAL metric
# ============================================================================


class TestBidsProcessedTotalMetric:
    def test_metric_exists(self):
        """BIDS_PROCESSED_TOTAL counter is defined in the metrics module."""
        import metrics

        assert hasattr(metrics, "BIDS_PROCESSED_TOTAL")

    def test_metric_accepts_source_label(self):
        """BIDS_PROCESSED_TOTAL can be incremented with a source label without raising."""
        import metrics

        # Should not raise regardless of whether prometheus_client is installed
        metrics.BIDS_PROCESSED_TOTAL.labels(source="pncp").inc(10)
        metrics.BIDS_PROCESSED_TOTAL.labels(source="portal").inc(5)
        metrics.BIDS_PROCESSED_TOTAL.labels(source="comprasgov").inc(3)

    def test_metric_requires_source_label(self):
        """BIDS_PROCESSED_TOTAL requires source label (labeled counter — direct .inc() raises)."""
        import metrics
        import pytest

        # Prometheus enforces label values — calling .inc() without labels raises ValueError
        # The correct usage is always .labels(source=X).inc()
        with pytest.raises((ValueError, Exception)):
            metrics.BIDS_PROCESSED_TOTAL.inc()


# ============================================================================
# AC2: record_daily_volume() cron function
# ============================================================================


class TestRecordDailyVolume:
    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_sums_total_raw_correctly(self, mock_get_sb, mock_sb_execute):
        """Sums total_raw across all returned sessions."""
        from cron_jobs import record_daily_volume

        mock_sb_execute.return_value = MagicMock(
            data=[
                {"total_raw": 300},
                {"total_raw": 150},
                {"total_raw": 50},
            ]
        )

        result = await record_daily_volume()

        assert result["total_bids_24h"] == 500
        assert result["session_count"] == 3
        assert "recorded_at" in result

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_handles_none_total_raw(self, mock_get_sb, mock_sb_execute):
        """Sessions with null total_raw are treated as 0."""
        from cron_jobs import record_daily_volume

        mock_sb_execute.return_value = MagicMock(
            data=[
                {"total_raw": None},
                {"total_raw": 200},
                {"total_raw": None},
            ]
        )

        result = await record_daily_volume()

        assert result["total_bids_24h"] == 200
        assert result["session_count"] == 3

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_empty_sessions(self, mock_get_sb, mock_sb_execute):
        """Returns zeros when no sessions exist in the last 24h."""
        from cron_jobs import record_daily_volume

        mock_sb_execute.return_value = MagicMock(data=[])

        result = await record_daily_volume()

        assert result["total_bids_24h"] == 0
        assert result["session_count"] == 0
        assert "recorded_at" in result

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_handles_db_error_gracefully(self, mock_get_sb, mock_sb_execute):
        """Returns safe defaults with error key when DB raises."""
        from cron_jobs import record_daily_volume

        mock_sb_execute.side_effect = Exception("connection refused")

        result = await record_daily_volume()

        assert result["total_bids_24h"] == 0
        assert result["session_count"] == 0
        assert "error" in result
        assert "connection refused" in result["error"]

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_result_data_none_treated_as_empty(self, mock_get_sb, mock_sb_execute):
        """result.data = None is handled without crashing."""
        from cron_jobs import record_daily_volume

        mock_sb_execute.return_value = MagicMock(data=None)

        result = await record_daily_volume()

        assert result["total_bids_24h"] == 0
        assert result["session_count"] == 0


# ============================================================================
# AC3: GET /v1/metrics/daily-volume endpoint
# ============================================================================


class TestDailyVolumeEndpoint:
    """Tests for the public GET /v1/metrics/daily-volume endpoint."""

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_happy_path_returns_correct_avg(self, mock_get_sb, mock_sb_execute):
        """Returns correct avg_bids_per_day computed from session data."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        # Two sessions on the same day: 600 + 400 = 1000 bids for that day
        # avg_per_day = 1000 / 1 day = 1000
        mock_sb_execute.return_value = MagicMock(
            data=[
                {"total_raw": 600, "created_at": "2026-03-01T10:00:00+00:00"},
                {"total_raw": 400, "created_at": "2026-03-01T15:30:00+00:00"},
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/metrics/daily-volume")

        assert resp.status_code == 200
        data = resp.json()
        assert data["avg_bids_per_day"] == 1000.0
        assert data["total_bids_30d"] == 1000
        assert data["total_sessions_30d"] == 2
        assert data["days_with_data"] == 1
        assert data["display_value"] == "1000+"

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_no_sessions_returns_centenas(self, mock_get_sb, mock_sb_execute):
        """Empty result set returns display_value='centenas' and zero counts."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        mock_sb_execute.return_value = MagicMock(data=[])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/metrics/daily-volume")

        assert resp.status_code == 200
        data = resp.json()
        assert data["avg_bids_per_day"] == 0
        assert data["total_bids_30d"] == 0
        assert data["total_sessions_30d"] == 0
        assert data["days_with_data"] == 0
        assert data["display_value"] == "centenas"

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_db_error_returns_fallback(self, mock_get_sb, mock_sb_execute):
        """DB exception returns HTTP 200 with safe fallback (not 500)."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        mock_sb_execute.side_effect = RuntimeError("timeout")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/metrics/daily-volume")

        assert resp.status_code == 200
        data = resp.json()
        assert data["display_value"] == "centenas"
        assert data["avg_bids_per_day"] == 0

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_display_value_above_1000(self, mock_get_sb, mock_sb_execute):
        """avg_bids_per_day >= 1000 formats as 'N+'."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        # 3 sessions on one day totalling 2400 bids = avg 2400/day
        mock_sb_execute.return_value = MagicMock(
            data=[
                {"total_raw": 800, "created_at": "2026-03-01T08:00:00+00:00"},
                {"total_raw": 900, "created_at": "2026-03-01T12:00:00+00:00"},
                {"total_raw": 700, "created_at": "2026-03-01T18:00:00+00:00"},
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/metrics/daily-volume")

        assert resp.status_code == 200
        data = resp.json()
        assert data["display_value"] == "2400+"

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_display_value_100_to_999(self, mock_get_sb, mock_sb_execute):
        """avg_bids_per_day in range [100, 999] formats as 'N+'."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        mock_sb_execute.return_value = MagicMock(
            data=[
                {"total_raw": 250, "created_at": "2026-03-01T10:00:00+00:00"},
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/metrics/daily-volume")

        assert resp.status_code == 200
        data = resp.json()
        assert data["display_value"] == "250+"

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_display_value_below_100_is_centenas(self, mock_get_sb, mock_sb_execute):
        """avg_bids_per_day < 100 shows 'centenas' (masks low volume)."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        mock_sb_execute.return_value = MagicMock(
            data=[
                {"total_raw": 42, "created_at": "2026-03-01T10:00:00+00:00"},
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/metrics/daily-volume")

        assert resp.status_code == 200
        data = resp.json()
        assert data["display_value"] == "centenas"

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_multi_day_avg_computed_correctly(self, mock_get_sb, mock_sb_execute):
        """Sessions spread across two days are averaged per day correctly."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        # Day 1: 600 bids, Day 2: 400 bids — avg = (600+400)/2 = 500
        mock_sb_execute.return_value = MagicMock(
            data=[
                {"total_raw": 600, "created_at": "2026-03-01T10:00:00+00:00"},
                {"total_raw": 400, "created_at": "2026-03-02T10:00:00+00:00"},
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/metrics/daily-volume")

        assert resp.status_code == 200
        data = resp.json()
        assert data["avg_bids_per_day"] == 500.0
        assert data["days_with_data"] == 2
        assert data["total_bids_30d"] == 1000

    @pytest.mark.asyncio
    async def test_no_auth_required(self):
        """Endpoint is public — responds without any Authorization header."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        with patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec, \
             patch("supabase_client.get_supabase"):
            mock_exec.return_value = MagicMock(data=[])

            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/v1/metrics/daily-volume")

        assert resp.status_code == 200  # Not 401 or 403

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_custom_days_param_accepted(self, mock_get_sb, mock_sb_execute):
        """Respects custom ?days= query parameter (valid range 1-90)."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        mock_sb_execute.return_value = MagicMock(data=[])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/v1/metrics/daily-volume?days=7")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    @patch("supabase_client.get_supabase")
    async def test_invalid_days_param_rejected(self, mock_get_sb, mock_sb_execute):
        """days=0 and days=91 are rejected (ge=1, le=90 constraint)."""
        from httpx import AsyncClient, ASGITransport
        from main import app

        mock_sb_execute.return_value = MagicMock(data=[])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp_low = await client.get("/v1/metrics/daily-volume?days=0")
            resp_high = await client.get("/v1/metrics/daily-volume?days=91")

        assert resp_low.status_code == 422
        assert resp_high.status_code == 422
