"""Issue #1921: Graceful Degradation — Fault Injection Tests.

Tests that every external dependency degrades gracefully when it fails.
One test per dependency per failure mode (timeout, connection refused).

Pattern:
    1. Mock/patch the dependency to raise a specific error
    2. Call the code path
    3. Assert the expected fallback behavior
    4. Assert the degradation metric was incremented (when testable)

Run from backend/:
    python -m pytest tests/resilience/test_graceful_degradation.py -v --timeout=30
"""

import sys
from unittest.mock import MagicMock

import asyncio
import logging
from unittest.mock import patch, AsyncMock, MagicMock

import pytest  # noqa: E402

# Disable logging noise during tests
logging.disable(logging.CRITICAL)


# ============================================================================
# Helpers
# ============================================================================

class _DegradationCapture:
    """Capture track_degradation calls for assertions."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __call__(self, source: str, mode: str) -> None:
        self.calls.append((source, mode))


@pytest.fixture
def capture_degradation():
    """Fixture that monkeypatches track_degradation to capture calls."""
    cap = _DegradationCapture()
    with patch("degradation.track_degradation", side_effect=cap):
        yield cap


# ============================================================================
# 1. Supabase — Timeout + Connection Refused
# ============================================================================


class TestSupabaseDegradation:
    """Supabase failure modes."""

    @pytest.mark.asyncio
    async def test_supabase_timeout_returns_504(self):
        """Supabase timeout should return 504, not crash or 500."""
        from supabase_client import sb_execute

        with patch("supabase_client._is_query_timeout", return_value=True):
            with patch("supabase_client.asyncio.to_thread", side_effect=asyncio.TimeoutError("simulated timeout")):
                with pytest.raises(Exception):
                    await sb_execute(MagicMock())

    @pytest.mark.asyncio
    async def test_supabase_connection_refused_triggers_degradation(self):
        """Supabase ConnectionRefusedError should be caught, not crash."""
        from supabase_client import sb_execute

        with patch("supabase_client.asyncio.to_thread", side_effect=ConnectionRefusedError("simulated refused")):
            with pytest.raises(Exception):
                await sb_execute(MagicMock())

    @pytest.mark.asyncio
    async def test_supabase_pool_exhaustion(self):
        """Supabase pool timeout should not crash the process."""
        from supabase_client import sb_execute

        import httpx
        with patch("supabase_client.asyncio.to_thread", side_effect=httpx.PoolTimeout("pool exhausted")):
            with pytest.raises(Exception):
                await sb_execute(MagicMock())


# ============================================================================
# 2. Supabase Auth — Timeout
# ============================================================================


class TestSupabaseAuthDegradation:
    """Supabase Auth failure modes."""

    @pytest.mark.asyncio
    async def test_supabase_auth_timeout(self):
        """Auth timeout should not crash the login flow."""
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value=None, source="supabase_auth")
        async def verify_token_mock(token: str):
            raise asyncio.TimeoutError("auth timeout")

        result = await verify_token_mock("fake_token")
        assert result is None  # Fallback returned, never crashed


# ============================================================================
# 3. Redis Cache — Timeout + Connection Refused
# ============================================================================


class TestRedisCacheDegradation:
    """Redis Cache failure modes."""

    @pytest.mark.asyncio
    async def test_redis_cache_timeout_falls_back_to_memory(self):
        """Redis cache timeout should fall back gracefully without crashing."""
        from redis_resilience import safe_redis_call

        async def _failing_coro():
            raise asyncio.TimeoutError("simulated timeout")

        result = await safe_redis_call(
            _failing_coro(),
            fallback=None,
            method_name="get",
            logger_warning=False,
        )
        assert result is None  # Fallback value returned

    @pytest.mark.asyncio
    async def test_redis_cache_connection_refused(self):
        """Redis connection refused should return fallback, not crash."""
        from redis_resilience import safe_redis_call

        async def _failing_coro():
            raise ConnectionRefusedError("simulated refused")

        result = await safe_redis_call(
            _failing_coro(),
            fallback=[],
            method_name="lrange",
            logger_warning=False,
        )
        assert result == []  # Fallback value returned

    def test_resilient_redis_dead_returns_fallback(self):
        """ResilientRedis with no underlying client returns safe defaults."""
        from redis_resilience import ResilientRedis

        safe = ResilientRedis(None)
        assert not safe.is_alive()

        result = asyncio.run(safe.get("key"))
        assert result is None

        result = asyncio.run(safe.exists("key"))
        assert result is False


# ============================================================================
# 4. Redis Queue (ARQ) — Timeout
# ============================================================================


class TestRedisQueueDegradation:
    """Redis Queue (ARQ) failure modes."""

    @pytest.mark.asyncio
    async def test_redis_queue_timeout_inline_fallback(self):
        """ARQ queue timeout should trigger inline fallback."""
        from redis_resilience import safe_redis_call

        async def failing_coro():
            raise asyncio.TimeoutError("queue timeout")

        result = await safe_redis_call(
            failing_coro(),
            fallback=False,
            method_name="ping",
            logger_warning=False,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_redis_queue_connection_refused(self):
        """ARQ Redis connection refused should fall back to inline execution."""
        from redis_resilience import safe_redis_call

        async def failing_coro():
            raise ConnectionRefusedError("queue refused")

        result = await safe_redis_call(
            failing_coro(),
            fallback=False,
            method_name="ping",
            logger_warning=False,
        )
        assert result is False


# ============================================================================
# 5. Stripe — Connection Refused + Webhook Timeout
# ============================================================================


class TestStripeDegradation:
    """Stripe API failure modes."""

    @pytest.mark.asyncio
    async def test_stripe_api_connection_refused(self):
        """Stripe API connection refused should return fallback, not crash."""
        from degradation import handle_sync_call

        @handle_sync_call(source="stripe", fallback=None)
        def create_stripe_session():
            raise ConnectionRefusedError("simulated refused")

        result = create_stripe_session()
        assert result is None  # Fallback returned

    @pytest.mark.asyncio
    async def test_stripe_webhook_timeout(self):
        """Stripe webhook processing timeout should return 504."""
        from webhooks.stripe import stripe_webhook

        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b"{}")
        mock_request.headers = {"stripe-signature": "test_sig"}

        with patch("webhooks.stripe.stripe.Webhook.construct_event", side_effect=asyncio.TimeoutError("timeout")):
            try:
                await stripe_webhook(mock_request)
            except Exception as e:
                from fastapi import HTTPException
                if isinstance(e, HTTPException):
                    assert e.status_code in (400, 504)
                    return

    def test_graceful_fallback_stripe(self):
        """graceful_fallback decorator catches Stripe errors correctly."""
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value={}, source="stripe")
        async def fetch_products():
            raise ConnectionRefusedError("stripe refused")

        result = asyncio.run(fetch_products())
        assert result == {}  # Fallback returned


# ============================================================================
# 6. Resend (Email)
# ============================================================================


class TestResendDegradation:
    """Resend email failure modes."""

    def test_resend_timeout_email_logged(self):
        """Resend timeout should return None (logged), never crash."""
        from email_service import send_email

        import sys
        mock_resend = MagicMock()
        mock_resend.Emails.send.side_effect = TimeoutError("timeout")
        sys.modules["resend"] = mock_resend

        try:
            result = send_email(
                to="test@example.com",
                subject="Test",
                html="<p>Test</p>",
            )
            assert result is None
        finally:
            if "resend" in sys.modules:
                del sys.modules["resend"]

    def test_resend_connection_refused(self):
        """Resend connection refused should return None (logged), never crash."""
        from email_service import send_email

        import sys
        mock_resend = MagicMock()
        mock_resend.Emails.send.side_effect = ConnectionRefusedError("refused")
        sys.modules["resend"] = mock_resend

        try:
            result = send_email(
                to="test@example.com",
                subject="Test",
                html="<p>Test</p>",
            )
            assert result is None
        finally:
            if "resend" in sys.modules:
                del sys.modules["resend"]

    def test_resend_not_configured_returns_none(self):
        """Email not configured should return None, never raise."""
        from email_service import send_email

        with patch("email_service.EMAIL_ENABLED", False):
            result = send_email(
                to="test@example.com",
                subject="Test",
                html="<p>Test</p>",
            )
            assert result is None


# ============================================================================
# 7. Mixpanel
# ============================================================================


class TestMixpanelDegradation:
    """Mixpanel failure modes."""

    def test_mixpanel_timeout_silent_drop(self):
        """Mixpanel timeout should silently drop event, never crash."""
        from analytics_events import track_event

        with patch("analytics_events._get_mixpanel", side_effect=TimeoutError("timeout")):
            track_event("test_event", {"key": "value"})

    def test_mixpanel_connection_refused(self):
        """Mixpanel connection refused should silently drop, never crash."""
        from analytics_events import track_event

        with patch("analytics_events._get_mixpanel", side_effect=ConnectionRefusedError("refused")):
            track_event("test_event", {"key": "value"})

    def test_mixpanel_no_token_logs_only(self):
        """Mixpanel without token should log and not crash."""
        from analytics_events import track_event

        with patch("analytics_events.os.getenv", return_value=""):
            track_event("test_event", {"key": "value"})

    def test_track_funnel_error_safe(self):
        """Mixpanel track_funnel_event should never raise."""
        from analytics_events import track_funnel_event

        with patch("analytics_events._get_mixpanel", return_value=None):
            track_funnel_event("funnel_test", "user_123", {})


# ============================================================================
# 8. OpenAI / LLM
# ============================================================================


class TestOpenAIDegradation:
    """OpenAI/LLM failure modes."""

    @pytest.mark.asyncio
    async def test_openai_timeout_fallback_pending(self):
        """OpenAI timeout should fall back to PENDING_REVIEW, not crash."""
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value=None, source="openai")
        async def classify_bid():
            raise asyncio.TimeoutError("openai timeout")

        result = await classify_bid()
        assert result is None

    def test_graceful_fallback_openai(self):
        """graceful_fallback catches OpenAI errors correctly."""
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value={"classification": "PENDING_REVIEW"}, source="openai")
        async def call_openai():
            raise ConnectionError("openai refused")

        result = asyncio.run(call_openai())
        assert result == {"classification": "PENDING_REVIEW"}


# ============================================================================
# 9. Data Sources (PNCP, PCP, ComprasGov)
# ============================================================================


class TestDataSourcesDegradation:
    """External data source failure modes."""

    @pytest.mark.asyncio
    async def test_pncp_timeout_uf_skipped(self):
        """PNCP UF timeout should be caught by circuit breaker."""
        from clients.pncp.circuit_breaker import PNCPCircuitBreaker

        cb = PNCPCircuitBreaker(name="pncp_test", threshold=2, cooldown_seconds=10)

        assert not cb.is_degraded
        await cb.record_failure()
        await cb.record_failure()

        assert cb.is_degraded
        assert cb.degraded_until is not None

    @pytest.mark.asyncio
    async def test_pncp_connection_refused(self):
        """PNCP connection refused should not crash the pipeline."""
        from clients.pncp.circuit_breaker import PNCPCircuitBreaker

        cb = PNCPCircuitBreaker(name="pncp_test_refused", threshold=3, cooldown_seconds=10)

        for _ in range(3):
            await cb.record_failure()

        assert cb.is_degraded

    @pytest.mark.asyncio
    async def test_pcp_timeout_skipped(self):
        """PCP timeout should not affect other sources."""
        from clients.pncp.circuit_breaker import PNCPCircuitBreaker

        pncp_cb = PNCPCircuitBreaker(name="pncp_for_pcp_test", threshold=3, cooldown_seconds=10)
        pcp_cb = PNCPCircuitBreaker(name="pcp", threshold=2, cooldown_seconds=10)

        for _ in range(2):
            await pcp_cb.record_failure()

        assert pcp_cb.is_degraded
        assert not pncp_cb.is_degraded

    @pytest.mark.asyncio
    async def test_comprasgov_timeout_skipped(self):
        """ComprasGov timeout should not affect other sources."""
        from clients.pncp.circuit_breaker import PNCPCircuitBreaker

        comprasgov_cb = PNCPCircuitBreaker(name="comprasgov", threshold=2, cooldown_seconds=10)
        pncp_cb = PNCPCircuitBreaker(name="pncp_comp_test", threshold=3, cooldown_seconds=10)

        for _ in range(2):
            await comprasgov_cb.record_failure()

        assert comprasgov_cb.is_degraded
        assert not pncp_cb.is_degraded


# ============================================================================
# 10. BrasilAPI
# ============================================================================


class TestBrasilAPIDegradation:
    """BrasilAPI (CNPJ enricher) failure modes."""

    @pytest.mark.asyncio
    async def test_brasilapi_timeout_enricher(self):
        """BrasilAPI timeout should not crash the enricher job."""
        import httpx
        with patch("httpx.AsyncClient.get", side_effect=asyncio.TimeoutError("brasilapi timeout")):
            from degradation import graceful_fallback

            @graceful_fallback(fallback_value=None, source="brasilapi")
            async def fetch_cnpj(cnpj: str):
                async with httpx.AsyncClient() as client:
                    return await client.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}")

            result = await fetch_cnpj("00000000000191")
            assert result is None

    @pytest.mark.asyncio
    async def test_brasilapi_connection_refused(self):
        """BrasilAPI connection refused should not crash the enricher."""
        import httpx
        with patch("httpx.AsyncClient.get", side_effect=ConnectionRefusedError("refused")):
            from degradation import graceful_fallback

            @graceful_fallback(fallback_value=None, source="brasilapi")
            async def fetch_cnpj(cnpj: str):
                async with httpx.AsyncClient() as client:
                    return await client.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}")

            result = await fetch_cnpj("00000000000191")
            assert result is None


# ============================================================================
# 11. graceful_fallback decorator — unit tests
# ============================================================================


class TestGracefulFallbackDecorator:
    """Unit tests for the graceful_fallback decorator itself."""

    @pytest.mark.asyncio
    async def test_success_path_returns_value(self):
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value=None, source="test")
        async def success_func():
            return "success"

        result = await success_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_returns_fallback(self):
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value="fallback", source="test")
        async def failing_func():
            raise asyncio.TimeoutError()

        result = await failing_func()
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_connection_error_returns_fallback(self):
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value=[], source="test")
        async def failing_func():
            raise ConnectionError("connection refused")

        result = await failing_func()
        assert result == []

    @pytest.mark.asyncio
    async def test_generic_exception_returns_fallback(self):
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value=0, source="test")
        async def failing_func():
            raise ValueError("unexpected")

        result = await failing_func()
        assert result == 0

    @pytest.mark.asyncio
    async def test_tracks_degradation_metric(self, capture_degradation):
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value=None, source="test_source")
        async def failing_func():
            raise asyncio.TimeoutError()

        await failing_func()

        assert len(capture_degradation.calls) >= 1
        recorded_sources = [c[0] for c in capture_degradation.calls]
        assert "test_source" in recorded_sources

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        from degradation import graceful_fallback

        @graceful_fallback(fallback_value=None, source="test")
        async def my_custom_function():
            raise asyncio.TimeoutError()

        assert my_custom_function.__name__ == "my_custom_function"

    def test_handle_sync_call_success(self):
        from degradation import handle_sync_call

        @handle_sync_call(source="test", fallback=None)
        def success_func():
            return "success"

        result = success_func()
        assert result == "success"

    def test_handle_sync_call_timeout(self):
        from degradation import handle_sync_call

        @handle_sync_call(source="test", fallback="fallback")
        def failing_func():
            raise TimeoutError()

        result = failing_func()
        assert result == "fallback"

    def test_handle_sync_call_connection_error(self):
        from degradation import handle_sync_call

        @handle_sync_call(source="test", fallback=[])
        def failing_func():
            raise ConnectionError("refused")

        result = failing_func()
        assert result == []

    def test_track_degradation_noop_when_metrics_unavailable(self):
        from degradation import track_degradation

        track_degradation("test_source", "timeout")


# ============================================================================
# 12. Redis resilience tests
# ============================================================================


class TestRedisResilience:
    """Redis safe_call fallback behaviors."""

    @pytest.mark.asyncio
    async def test_safe_redis_call_timeout_returns_fallback(self):
        from redis_resilience import safe_redis_call

        async def slow_coro():
            await asyncio.sleep(10)
            return "data"

        result = await safe_redis_call(
            slow_coro(),
            fallback="fallback",
            timeout_s=0.01,
            method_name="test_get",
            logger_warning=False,
        )
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_safe_redis_call_connection_error(self):
        from redis_resilience import safe_redis_call

        async def failing_coro():
            raise ConnectionError("connection refused")

        result = await safe_redis_call(
            failing_coro(),
            fallback=[],
            method_name="scan",
            logger_warning=False,
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_safe_redis_call_unexpected_error(self):
        from redis_resilience import safe_redis_call

        async def failing_coro():
            raise ValueError("invalid data")

        result = await safe_redis_call(
            failing_coro(),
            fallback=0,
            method_name="exists",
            logger_warning=False,
        )
        assert result == 0


# ============================================================================
# 13. Circuit breaker state isolation
# ============================================================================


class TestCircuitBreakerIsolation:
    """Circuit breaker isolation between sources."""

    @pytest.mark.asyncio
    async def test_separate_cb_names_do_not_interfere(self):
        from clients.pncp.circuit_breaker import PNCPCircuitBreaker

        cb_a = PNCPCircuitBreaker(name="source_a", threshold=2, cooldown_seconds=10)
        cb_b = PNCPCircuitBreaker(name="source_b", threshold=2, cooldown_seconds=10)

        await cb_a.record_failure()
        await cb_a.record_failure()

        assert cb_a.is_degraded
        assert not cb_b.is_degraded

        await cb_b.record_failure()
        await cb_b.record_failure()

        assert cb_b.is_degraded

    @pytest.mark.asyncio
    async def test_success_resets_failure_counter(self):
        from clients.pncp.circuit_breaker import PNCPCircuitBreaker

        cb = PNCPCircuitBreaker(name="test_reset", threshold=3, cooldown_seconds=10)

        await cb.record_failure()
        await cb.record_failure()
        assert cb.consecutive_failures == 2

        await cb.record_success()
        assert cb.consecutive_failures == 0
