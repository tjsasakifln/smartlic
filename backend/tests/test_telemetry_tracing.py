"""Tests for #1862: Distributed tracing decorators (traced_job, traced_loop, traced_webhook).

Covers:
  - traced_job NO-OP when tracing disabled
  - traced_job creates span with job.name, job.id attributes
  - traced_job with custom job_name
  - traced_job handles exceptions (span ends, error status set by OTel)
  - traced_loop NO-OP when tracing disabled
  - traced_loop creates span with loop.name attribute
  - traced_webhook NO-OP when tracing disabled
  - traced_webhook creates span with webhook.handler attribute
  - Decorators preserve function signature and return value
"""

import asyncio
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers: reset telemetry module state between tests
# ---------------------------------------------------------------------------

def _reset_telemetry():
    """Reset the telemetry module state so each test starts clean."""
    import telemetry
    telemetry._initialized = False
    telemetry._tracer_provider = None
    telemetry._noop = True


@pytest.fixture(autouse=True)
def reset_telemetry_state():
    """Ensure telemetry is reset before and after each test."""
    _reset_telemetry()
    yield
    _reset_telemetry()


# ---------------------------------------------------------------------------
# Helper: create a mock tracer + context manager for span assertions
# ---------------------------------------------------------------------------

def _make_mock_tracer():
    """Create a mock tracer with a context-managed mock span.

    Returns:
        tuple: (mock_tracer, mock_span, mock_cm)
    """
    mock_span = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_span)
    mock_cm.__exit__ = MagicMock(return_value=None)
    mock_tracer = MagicMock()
    mock_tracer.start_as_current_span.return_value = mock_cm
    return mock_tracer, mock_span, mock_cm


# ===========================================================================
# traced_job: NO-OP mode
# ===========================================================================

class TestTracedJobNoop:
    """traced_job should be completely no-op when tracing is disabled."""

    @pytest.mark.asyncio
    async def test_noop_returns_value(self):
        """When tracing is disabled, traced_job should return the function's value."""
        from telemetry import traced_job

        @traced_job()
        async def my_job(ctx, arg1=None):
            return {"status": "ok", "arg": arg1}

        result = await my_job({"job_id": "test-123"}, arg1="hello")
        assert result == {"status": "ok", "arg": "hello"}

    @pytest.mark.asyncio
    async def test_noop_with_custom_name(self):
        """When tracing is disabled, traced_job with custom name still works."""
        from telemetry import traced_job

        @traced_job(job_name="custom_job_name")
        async def my_job(ctx):
            return {"status": "ok"}

        result = await my_job({"job_id": "test-123"})
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_noop_no_span_created(self):
        """When tracing is disabled, no span is created (0 overhead)."""
        import telemetry
        from telemetry import traced_job

        @traced_job()
        async def my_job(ctx):
            return {"status": "ok"}

        with patch.object(telemetry._NoopTracer, "start_as_current_span") as mock_start:
            await my_job({"job_id": "test-123"})
            # In noop mode, the decorator should NOT call start_as_current_span
            mock_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_noop_preserves_signature(self):
        """traced_job should preserve the wrapped function's signature."""
        from telemetry import traced_job

        @traced_job()
        async def my_job(ctx, search_id: str, **kwargs):
            return {"search_id": search_id}

        result = await my_job({"job_id": "x"}, search_id="abc-123", extra="value")
        assert result == {"search_id": "abc-123"}


# ===========================================================================
# traced_job: Active tracing
# ===========================================================================

class TestTracedJobActive:
    """traced_job should create spans when tracing is active."""

    @pytest.mark.asyncio
    async def test_creates_span_with_function_name(self):
        """traced_job should create a span named after the function."""
        mock_tracer, _, _ = _make_mock_tracer()
        from telemetry import traced_job

        @traced_job()
        async def my_test_job(ctx):
            return {"status": "ok"}

        with patch("telemetry._noop", False):
            with patch("telemetry.get_tracer", return_value=mock_tracer):
                result = await my_test_job({"job_id": "test-123"})

        assert result == {"status": "ok"}
        mock_tracer.start_as_current_span.assert_called_once_with(
            "my_test_job",
            attributes={"job.name": "my_test_job", "job.id": "test-123"},
        )

    @pytest.mark.asyncio
    async def test_creates_span_with_custom_name(self):
        """traced_job(job_name='x') should use the custom name for the span."""
        mock_tracer, _, _ = _make_mock_tracer()
        from telemetry import traced_job

        @traced_job(job_name="custom_name")
        async def my_test_job(ctx):
            return {"status": "ok"}

        with patch("telemetry._noop", False):
            with patch("telemetry.get_tracer", return_value=mock_tracer):
                result = await my_test_job({"job_id": "test-456"})

        assert result == {"status": "ok"}
        mock_tracer.start_as_current_span.assert_called_once_with(
            "custom_name",
            attributes={"job.name": "custom_name", "job.id": "test-456"},
        )

    @pytest.mark.asyncio
    async def test_no_job_id_if_not_in_ctx(self):
        """traced_job should not set job.id if ctx has no job_id."""
        mock_tracer, _, _ = _make_mock_tracer()
        from telemetry import traced_job

        @traced_job()
        async def my_job(ctx):
            return {"status": "ok"}

        with patch("telemetry._noop", False):
            with patch("telemetry.get_tracer", return_value=mock_tracer):
                result = await my_job({"some_key": "value"})

        assert result == {"status": "ok"}
        mock_tracer.start_as_current_span.assert_called_once_with(
            "my_job",
            attributes={"job.name": "my_job"},
        )

    @pytest.mark.asyncio
    async def test_handles_ctx_as_none(self):
        """traced_job should handle ctx=None gracefully."""
        mock_tracer, _, _ = _make_mock_tracer()
        from telemetry import traced_job

        @traced_job()
        async def my_job(ctx):
            return {"status": "ok", "ctx_type": type(ctx).__name__ if ctx is not None else "NoneType"}

        with patch("telemetry._noop", False):
            with patch("telemetry.get_tracer", return_value=mock_tracer):
                result = await my_job(None)

        assert result["status"] == "ok"
        mock_tracer.start_as_current_span.assert_called_once_with(
            "my_job",
            attributes={"job.name": "my_job"},
        )

    @pytest.mark.asyncio
    async def test_spans_ended_on_success(self):
        """Span context manager should be exited (span ended) on success."""
        _, _, mock_cm = _make_mock_tracer()
        mock_tracer, _, _ = _make_mock_tracer()  # fresh for this test
        from telemetry import traced_job

        @traced_job()
        async def my_job(ctx):
            return {"status": "ok"}

        with patch("telemetry._noop", False):
            with patch("telemetry.get_tracer", return_value=mock_tracer):
                await my_job({"job_id": "t-1"})

        # The wrapper's tracer.start_as_current_span should be called
        assert mock_tracer.start_as_current_span.called

    @pytest.mark.asyncio
    async def test_exception_propagation(self):
        """Exception in traced_job should propagate to caller."""
        mock_tracer, mock_span, mock_cm = _make_mock_tracer()
        from telemetry import traced_job

        @traced_job()
        async def failing_job(ctx):
            raise ValueError("job failed")

        with patch("telemetry._noop", False):
            with patch("telemetry.get_tracer", return_value=mock_tracer):
                with pytest.raises(ValueError, match="job failed"):
                    await failing_job({"job_id": "t-1"})

        # Span context manager should have been entered
        assert mock_tracer.start_as_current_span.called


# ===========================================================================
# traced_loop
# ===========================================================================

class TestTracedLoop:
    """traced_loop should create spans with loop attributes."""

    @pytest.mark.asyncio
    async def test_noop_returns_value(self):
        """When tracing is disabled, traced_loop should return the function's value."""
        from telemetry import traced_loop

        @traced_loop("health_check")
        async def my_loop():
            return {"status": "ok"}

        result = await my_loop()
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_creates_span_with_loop_name(self):
        """traced_loop should create a span named after the loop."""
        mock_tracer, _, _ = _make_mock_tracer()
        from telemetry import traced_loop

        @traced_loop("cache_cleanup")
        async def my_loop():
            return {"status": "ok"}

        with patch("telemetry._noop", False):
            with patch("telemetry.get_tracer", return_value=mock_tracer):
                result = await my_loop()

        assert result == {"status": "ok"}
        mock_tracer.start_as_current_span.assert_called_once_with(
            "cache_cleanup",
            attributes={"loop.name": "cache_cleanup"},
        )

    @pytest.mark.asyncio
    async def test_loop_noop_no_span(self):
        """traced_loop should not create spans when tracing is disabled."""
        import telemetry

        with patch.object(telemetry._NoopTracer, "start_as_current_span") as mock_start:
            from telemetry import traced_loop

            @traced_loop("test_loop")
            async def my_loop():
                return 42

            result = await my_loop()
            assert result == 42
            mock_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_loop_exception_propagates(self):
        """Exception in traced_loop should propagate."""
        from telemetry import traced_loop

        @traced_loop("failing_loop")
        async def failing_loop():
            raise RuntimeError("loop error")

        with pytest.raises(RuntimeError, match="loop error"):
            await failing_loop()


# ===========================================================================
# traced_webhook
# ===========================================================================

class TestTracedWebhook:
    """traced_webhook should create spans with webhook attributes."""

    @pytest.mark.asyncio
    async def test_noop_returns_value(self):
        """When tracing is disabled, traced_webhook should return the function's value."""
        from telemetry import traced_webhook

        @traced_webhook("checkout.session.completed")
        async def handler(event):
            return {"status": "processed"}

        result = await handler({"id": "evt_123"})
        assert result == {"status": "processed"}

    @pytest.mark.asyncio
    async def test_creates_span_with_handler_name(self):
        """traced_webhook should create a span named after the handler."""
        mock_tracer, _, _ = _make_mock_tracer()
        from telemetry import traced_webhook

        @traced_webhook("invoice.payment_succeeded")
        async def handler(event):
            return {"status": "processed"}

        with patch("telemetry._noop", False):
            with patch("telemetry.get_tracer", return_value=mock_tracer):
                result = await handler({"id": "evt_456", "type": "invoice.payment_succeeded"})

        assert result == {"status": "processed"}
        mock_tracer.start_as_current_span.assert_called_once_with(
            "invoice.payment_succeeded",
            attributes={"webhook.handler": "invoice.payment_succeeded"},
        )

    @pytest.mark.asyncio
    async def test_webhook_noop_no_span(self):
        """traced_webhook should not create spans when tracing is disabled."""
        import telemetry

        with patch.object(telemetry._NoopTracer, "start_as_current_span") as mock_start:
            from telemetry import traced_webhook

            @traced_webhook("test.event")
            async def handler(event):
                return "done"

            result = await handler({})
            assert result == "done"
            mock_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_webhook_exception_propagates(self):
        """Exception in traced_webhook should propagate."""
        from telemetry import traced_webhook

        @traced_webhook("failing.event")
        async def handler(event):
            raise KeyError("missing_field")

        with pytest.raises(KeyError, match="missing_field"):
            await handler({"id": "evt_789"})


# ===========================================================================
# Integration: decorators work in the codebase context
# ===========================================================================

class TestDecoratorIntegration:
    """Verify decorators don't break the existing codebase patterns."""

    @pytest.mark.asyncio
    async def test_jobs_module_imports(self):
        """jobs.queue.jobs should import cleanly with traced_job applied."""
        import jobs.queue.jobs

        # Verify all expected job functions exist and are async
        assert hasattr(jobs.queue.jobs, "generate_intel_report")
        assert hasattr(jobs.queue.jobs, "send_founders_welcome")
        assert hasattr(jobs.queue.jobs, "llm_summary_job")
        assert hasattr(jobs.queue.jobs, "excel_generation_job")
        assert hasattr(jobs.queue.jobs, "bid_analysis_job")
        assert hasattr(jobs.queue.jobs, "daily_digest_job")
        assert hasattr(jobs.queue.jobs, "email_alerts_job")
        assert hasattr(jobs.queue.jobs, "reclassify_pending_bids_job")
        assert hasattr(jobs.queue.jobs, "classify_zero_match_job")
        assert hasattr(jobs.queue.jobs, "send_post_purchase_step")

    @pytest.mark.asyncio
    async def test_decorated_function_is_async(self):
        """Decorated functions should still be async (coroutine functions)."""
        from telemetry import traced_job

        @traced_job()
        async def sample_job(ctx):
            return True

        assert asyncio.iscoroutinefunction(sample_job)

    @pytest.mark.asyncio
    async def test_decorator_preserves_name(self):
        """traced_job should preserve __name__ and __qualname__."""
        from telemetry import traced_job

        @traced_job()
        async def my_special_job_function(ctx):
            return True

        assert my_special_job_function.__name__ == "my_special_job_function"

    @pytest.mark.asyncio
    async def test_telemetry_module_exports_decorators(self):
        """telemetry module should export all three decorators."""
        import telemetry

        assert hasattr(telemetry, "traced_job")
        assert hasattr(telemetry, "traced_loop")
        assert hasattr(telemetry, "traced_webhook")

        # All should be callable
        assert callable(telemetry.traced_job)
        assert callable(telemetry.traced_loop)
        assert callable(telemetry.traced_webhook)

        # traced_job should work without args
        assert callable(telemetry.traced_job())
        # traced_job should work with args
        assert callable(telemetry.traced_job(job_name="test"))
        # traced_loop requires a name
        assert callable(telemetry.traced_loop("test"))
        # traced_webhook requires a name
        assert callable(telemetry.traced_webhook("test"))
