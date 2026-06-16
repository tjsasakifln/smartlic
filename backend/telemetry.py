"""OpenTelemetry distributed tracing for SmartLic backend.

GTM-RESILIENCE-F02: Provides tracing initialization, tracer factory, and helpers.

Design principles:
  - Zero overhead when OTEL_EXPORTER_OTLP_ENDPOINT is not set (no-op mode)
  - Graceful fallback when opentelemetry packages are not installed
  - Sampling rate configurable via OTEL_SAMPLING_RATE (default 0.1 = 10%)
  - Service name configurable via OTEL_SERVICE_NAME (default "smartlic-backend")

Usage:
    from telemetry import init_tracing, get_tracer, get_current_span

    # In lifespan():
    init_tracing()

    # In any module:
    tracer = get_tracer(__name__)
    with tracer.start_as_current_span("my_operation") as span:
        span.set_attribute("key", "value")
        ...
"""

import functools
import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Module-level state
_initialized = False
_tracer_provider = None
_noop = True  # True when tracing is disabled or packages unavailable


def _is_otel_available() -> bool:
    """Check if OpenTelemetry SDK packages are installed."""
    try:
        import opentelemetry.trace  # noqa: F401
        import opentelemetry.sdk.trace  # noqa: F401
        return True
    except ImportError:
        return False


def init_tracing() -> None:
    """Initialize OpenTelemetry tracing.

    AC2: Creates TracerProvider with OTLP exporter and configures sampling.
    AC8: Reads OTEL_EXPORTER_OTLP_ENDPOINT — if not set, tracing is no-op.
    AC9: No-op mode has zero overhead (no TracerProvider created).

    CRIT-023: Must be called BEFORE FastAPI() so class-level instrumentation works.
    """
    global _initialized, _tracer_provider, _noop

    if _initialized:
        return

    _initialized = True
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()

    if not endpoint:
        logger.info("OTEL_EXPORTER_OTLP_ENDPOINT not set — tracing disabled (no-op)")
        _noop = True
        return

    # CRIT-025: Log the effective traces endpoint for debugging.
    # SDK priority: OTEL_EXPORTER_OTLP_TRACES_ENDPOINT (as-is) > OTEL_EXPORTER_OTLP_ENDPOINT + /v1/traces
    traces_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if traces_endpoint:
        logger.info(
            f"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT set — SDK will use '{traces_endpoint}' as-is"
        )
    else:
        effective_url = endpoint.rstrip("/") + "/v1/traces"
        logger.info(
            f"OTEL_EXPORTER_OTLP_TRACES_ENDPOINT not set — SDK will auto-append /v1/traces: '{effective_url}'"
        )

    if not _is_otel_available():
        logger.warning(
            "OpenTelemetry packages not installed — tracing disabled. "
            "Install: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-exporter-otlp-proto-http"
        )
        _noop = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

        # AC7: Service name from env
        service_name = os.getenv("OTEL_SERVICE_NAME", "smartlic-backend")

        # AC6: Sampling rate from env (default 10%)
        sampling_rate = float(os.getenv("OTEL_SAMPLING_RATE", "0.1"))
        sampler = TraceIdRatioBased(sampling_rate)

        resource = Resource.create({SERVICE_NAME: service_name})

        _tracer_provider = TracerProvider(
            resource=resource,
            sampler=sampler,
        )

        # Configure OTLP exporter
        # CRIT-023: HTTP/protobuf exporter (Grafana Cloud recommended)
        # SDK auto-reads OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_HEADERS
        exporter = OTLPSpanExporter()
        span_processor = BatchSpanProcessor(exporter)
        _tracer_provider.add_span_processor(span_processor)

        # Set as global TracerProvider
        trace.set_tracer_provider(_tracer_provider)
        _noop = False

        logger.info(
            f"OpenTelemetry tracing initialized: service={service_name}, "
            f"endpoint={endpoint}, sampling_rate={sampling_rate}"
        )

        # AC5: Auto-instrument httpx (stateless, safe to call early)
        _instrument_httpx()

        # NOTE: FastAPI instrumentation is done via instrument_fastapi_app(app)
        # AFTER all middleware is registered, so OTel middleware wraps everything.

    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry: {e}")
        _noop = True


def instrument_fastapi_app(app) -> None:
    """Instrument a specific FastAPI app instance with OTel ASGI middleware.

    CRIT-023: Must be called AFTER all app.add_middleware() calls so that
    the OTel middleware is the outermost (LIFO stack). This ensures the
    span context is active for all inner middleware, enabling trace_id
    propagation in CorrelationIDMiddleware logs.
    """
    if _noop:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument_app(app)
        logger.info("FastAPI auto-instrumentation enabled (instrument_app)")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-fastapi not installed — skipping")
    except Exception as e:
        logger.warning(f"FastAPI instrumentation failed: {e}")


def _instrument_httpx() -> None:
    """AC5: Auto-instrument httpx HTTP calls (PNCP, PCP, etc.)."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("httpx auto-instrumentation enabled")
    except ImportError:
        logger.warning("opentelemetry-instrumentation-httpx not installed — skipping")
    except Exception as e:
        logger.warning(f"httpx instrumentation failed: {e}")


def shutdown_tracing() -> None:
    """Gracefully shut down the TracerProvider, flushing pending spans."""
    global _tracer_provider
    if _tracer_provider is not None:
        try:
            _tracer_provider.shutdown()
            logger.info("OpenTelemetry tracing shut down")
        except Exception as e:
            logger.warning(f"Error shutting down tracing: {e}")


def get_tracer(name: str = __name__) -> Any:
    """Get a tracer instance for creating spans.

    AC25: Returns a functional tracer that creates spans when tracing is active.
    Returns a no-op tracer when tracing is disabled (zero overhead).

    Args:
        name: Module name for the tracer (typically __name__).

    Returns:
        opentelemetry.trace.Tracer or NoopTracer
    """
    if _noop:
        return _NoopTracer()

    from opentelemetry import trace
    return trace.get_tracer(name)


def get_current_span() -> Any:
    """Get the currently active span, or a no-op span if tracing is disabled.

    Useful for adding attributes to the current span from any code location.
    """
    if _noop:
        return _NoopSpan()

    from opentelemetry import trace
    return trace.get_current_span()


def get_trace_id() -> Optional[str]:
    """Get the current trace ID as a hex string, or None if tracing is disabled.

    AC17: Used to include trace_id in SSE events and log records.
    """
    if _noop:
        return None

    from opentelemetry import trace
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.trace_id != 0:
        return format(ctx.trace_id, "032x")
    return None


def get_span_id() -> Optional[str]:
    """Get the current span ID as a hex string, or None if tracing is disabled."""
    if _noop:
        return None

    from opentelemetry import trace
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.span_id != 0:
        return format(ctx.span_id, "016x")
    return None


def is_tracing_enabled() -> bool:
    """AC21: Check if tracing is active (OTLP endpoint configured and SDK loaded)."""
    return not _noop


@contextmanager
def optional_span(tracer: Any, name: str, attributes: Optional[dict] = None):
    """Context manager that creates a span if tracing is active, or no-ops.

    Convenience wrapper for instrumenting code without checking _noop everywhere.

    Args:
        tracer: Tracer instance from get_tracer().
        name: Span name.
        attributes: Optional dict of span attributes.

    Yields:
        The span (or _NoopSpan if tracing is disabled).
    """
    if _noop:
        yield _NoopSpan()
        return

    with tracer.start_as_current_span(name, attributes=attributes or {}) as span:
        yield span


# ============================================================================
# Decorators for ARQ jobs, cron loops, and webhooks (#1862)
# ============================================================================


def traced_job(func: Optional[Callable] = None, *, job_name: Optional[str] = None):
    """Decorator for ARQ job functions. Creates span with job attributes.

    Usage::

        @traced_job
        async def my_job(ctx, ...): ...

        @traced_job(job_name="custom_name")
        async def my_job(ctx, ...): ...

    Span attributes:
        - ``job.name``: name of the job (function name or custom)
        - ``job.id``: ARQ job ID (from ctx, if available)

    NO-OP safe: when tracing is disabled, the decorated function runs
    without any overhead (no span created, no attributes set).
    """
    def decorator(f: Callable) -> Callable:
        span_name = job_name or f.__name__

        @functools.wraps(f)
        async def wrapper(ctx, *args, **kwargs):
            if _noop:
                return await f(ctx, *args, **kwargs)

            tracer = get_tracer(__name__)
            attrs = {"job.name": span_name}
            if isinstance(ctx, dict):
                job_id = ctx.get("job_id")
                if job_id:
                    attrs["job.id"] = str(job_id)

            with tracer.start_as_current_span(span_name, attributes=attrs):
                return await f(ctx, *args, **kwargs)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


def traced_loop(loop_name: str):
    """Decorator for cron/lifespan loop functions. Creates span with loop attributes.

    Usage::

        @traced_loop("health_canary")
        async def run_health_check(): ...

    Span attributes:
        - ``loop.name``: name of the loop
        - ``loop.status``: set on completion or error

    NO-OP safe: when tracing is disabled, the decorated function runs
    without any overhead.
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            if _noop:
                return await f(*args, **kwargs)

            tracer = get_tracer(__name__)
            attrs = {"loop.name": loop_name}

            with tracer.start_as_current_span(loop_name, attributes=attrs):
                return await f(*args, **kwargs)

        return wrapper
    return decorator


def traced_webhook(handler_name: str):
    """Decorator for Stripe webhook handlers. Creates span with webhook attributes.

    Usage::

        @traced_webhook("checkout.session.completed")
        async def handle(event): ...

    Span attributes:
        - ``webhook.handler``: name of the handler
        - ``webhook.event_type``: Stripe event type (set manually if not in decorator)
        - ``webhook.event_id``: Stripe event ID (set manually if not in decorator)

    NO-OP safe: when tracing is disabled, the decorated function runs
    without any overhead.
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        async def wrapper(*args, **kwargs):
            if _noop:
                return await f(*args, **kwargs)

            tracer = get_tracer(__name__)
            attrs = {"webhook.handler": handler_name}

            with tracer.start_as_current_span(handler_name, attributes=attrs):
                return await f(*args, **kwargs)

        return wrapper
    return decorator


# ============================================================================
# No-op implementations for zero-overhead fallback
# ============================================================================

class _NoopSpan:
    """No-op span that silently accepts all operations."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any, description: str = "") -> None:
        pass

    def record_exception(self, exception: Exception, attributes: Optional[dict] = None) -> None:
        pass

    def add_event(self, name: str, attributes: Optional[dict] = None) -> None:
        pass

    def is_recording(self) -> bool:
        return False

    def get_span_context(self) -> "_NoopSpanContext":
        return _NoopSpanContext()

    def end(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoopSpanContext:
    """No-op span context."""
    trace_id = 0
    span_id = 0


class _NoopTracer:
    """No-op tracer that returns _NoopSpan for all operations."""

    def start_span(self, name: str, **kwargs) -> _NoopSpan:
        return _NoopSpan()

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs):
        yield _NoopSpan()
