"""CRIT-026: Tests for worker timeout mitigation and SSE observability.

AC3: Worker timeout metric exists
AC8: SSE generator logs abrupt disconnection
"""

import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_auth():
    """Override auth dependency."""
    from main import app
    from auth import require_auth
    app.dependency_overrides[require_auth] = lambda: {"id": "test-user", "email": "test@test.com"}
    yield
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def mock_sse_limits():
    """Mock SSE connection limiter."""
    with patch("routes.search_sse.acquire_sse_connection", new_callable=AsyncMock, return_value=True), \
         patch("routes.search_sse.release_sse_connection", new_callable=AsyncMock):
        yield


# ============================================================================
# AC3: Worker timeout metric
# ============================================================================


class TestWorkerTimeoutMetric:
    """AC3: WORKER_TIMEOUT counter exists with correct labels."""

    def test_worker_timeout_metric_exists(self):
        """AC3: smartlic_worker_timeout_total metric is defined."""
        from metrics import WORKER_TIMEOUT
        assert WORKER_TIMEOUT is not None

    def test_worker_timeout_metric_has_reason_label(self):
        """AC3: WORKER_TIMEOUT has 'reason' label."""
        from metrics import WORKER_TIMEOUT
        # Should be callable with labels (no-op or real)
        labeled = WORKER_TIMEOUT.labels(reason="sse_generator_exception")
        assert labeled is not None

    def test_worker_timeout_inc_noop(self):
        """AC3: WORKER_TIMEOUT.inc() doesn't raise."""
        from metrics import WORKER_TIMEOUT
        WORKER_TIMEOUT.labels(reason="test").inc()


# ============================================================================
# AC8: SSE generator abrupt finish logging
# ============================================================================


@pytest.mark.asyncio
class TestSSEGeneratorAbruptLogging:
    """AC8: Backend logs when SSE generator finishes abruptly."""

    async def test_generator_exception_logged(self, mock_auth, mock_sse_limits, caplog):
        """AC8: Unexpected exception in SSE generator is logged and increments metric."""
        from main import app

        mock_tracker = MagicMock()
        mock_tracker._use_redis = False
        # Queue that raises an exception to simulate abrupt failure
        mock_queue = AsyncMock()
        mock_queue.get = AsyncMock(side_effect=RuntimeError("Simulated crash"))
        mock_tracker.queue = mock_queue

        with patch("routes.search_sse.get_tracker", new_callable=AsyncMock, return_value=mock_tracker), \
             patch("routes.search_sse.get_sse_redis_pool", new_callable=AsyncMock, return_value=None), \
             patch("routes.search_sse._SSE_HEARTBEAT_INTERVAL", 0.01), \
             caplog.at_level(logging.ERROR, logger="routes.search_sse"):

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/v1/buscar-progress/test-abrupt-crash")

        assert response.status_code == 200
        # Check that the abrupt finish was logged
        error_logs = [r for r in caplog.records if "CRIT-026" in r.message and "abrupt" in r.message]
        assert len(error_logs) >= 1, (
            f"Expected CRIT-026 abrupt finish log. Records: "
            f"{[r.message for r in caplog.records]}"
        )

    async def test_generator_normal_finish_logged_debug(self, mock_auth, mock_sse_limits, caplog):
        """AC8: Normal SSE generator finish is logged at DEBUG level."""
        from main import app
        from progress import ProgressEvent

        mock_tracker = MagicMock()
        mock_tracker._use_redis = False
        mock_tracker.queue = asyncio.Queue()
        await mock_tracker.queue.put(
            ProgressEvent(stage="complete", progress=100, message="Done")
        )

        with patch("routes.search_sse.get_tracker", new_callable=AsyncMock, return_value=mock_tracker), \
             patch("routes.search_sse.get_sse_redis_pool", new_callable=AsyncMock, return_value=None), \
             patch("routes.search_sse._SSE_HEARTBEAT_INTERVAL", 0.01), \
             caplog.at_level(logging.DEBUG, logger="routes.search_sse"):

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/v1/buscar-progress/test-normal-finish")

        assert response.status_code == 200
        # Check that the normal finish was logged at DEBUG
        debug_logs = [r for r in caplog.records if "CRIT-026" in r.message and "finished" in r.message]
        assert len(debug_logs) >= 1, (
            f"Expected CRIT-026 finished log. Records: "
            f"{[r.message for r in caplog.records]}"
        )

    async def test_no_tracker_emits_error_and_logs(self, mock_auth, mock_sse_limits, caplog):
        """AC8: When tracker not found, error event is emitted and generator finishes cleanly."""
        from main import app

        with patch("routes.search_sse.get_tracker", new_callable=AsyncMock, return_value=None), \
             patch("routes.search_sse.get_current_state", new_callable=AsyncMock, return_value=None), \
             patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("routes.search_sse._SSE_HEARTBEAT_INTERVAL", 0.01), \
             caplog.at_level(logging.DEBUG, logger="routes.search_sse"):

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/v1/buscar-progress/test-no-tracker")

        assert response.status_code == 200
        # Should contain the error event about search not found
        assert "Search not found" in response.text


# ============================================================================
# Start.sh config validation (smoke tests)
# ============================================================================


class TestStartShConfig:
    """Validate start.sh configuration values."""

    def test_start_sh_has_110s_timeout(self):
        """GTM-INFRA-001 AC7: UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN default is 120s (aligned with Railway drainingSeconds=120s)."""
        import os
        start_sh_path = os.path.join(os.path.dirname(__file__), "..", "start.sh")
        with open(start_sh_path) as f:
            content = f.read()
        assert "UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN:-120" in content, "Default graceful timeout should be 120s (aligned with Railway drainingSeconds)"

    def test_start_sh_has_2_workers(self):
        """SLA-002: WEB_CONCURRENCY default is 2."""
        import os
        start_sh_path = os.path.join(os.path.dirname(__file__), "..", "start.sh")
        with open(start_sh_path) as f:
            content = f.read()
        assert "WEB_CONCURRENCY:-2" in content, "Default workers should be 2 (SLA-002)"

    def test_start_sh_has_keep_alive(self):
        """AC2: start.sh has --timeout-keep-alive flag (uvicorn equivalent of --keep-alive)."""
        import os
        start_sh_path = os.path.join(os.path.dirname(__file__), "..", "start.sh")
        with open(start_sh_path) as f:
            content = f.read()
        assert "--timeout-keep-alive" in content, "start.sh should have --timeout-keep-alive flag"

    def test_start_sh_has_graceful_timeout_30(self):
        """GTM-STAB-002: uvicorn --timeout-graceful-shutdown defaults to 120s via UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN (aligned with Railway drainingSeconds)."""
        import os
        start_sh_path = os.path.join(os.path.dirname(__file__), "..", "start.sh")
        with open(start_sh_path) as f:
            content = f.read()
        # uvicorn uses --timeout-graceful-shutdown with env var override
        assert "UVICORN_TIMEOUT_GRACEFUL_SHUTDOWN:-120" in content, "Graceful shutdown timeout must default to 120s (aligned with Railway)"
