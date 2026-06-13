"""startup/app_factory.py — FastAPI app factory (DEBT-107).

Single entry point: call create_app() to get a fully-configured FastAPI instance.
"""

import asyncio
import concurrent.futures
import logging
import os

from fastapi import FastAPI

from config import setup_logging, log_feature_flags, validate_feature_flags
from startup.sentry import init_sentry
from startup.lifespan import lifespan
from startup.middleware_setup import setup_middleware, setup_metrics_endpoint, DOCS_ACCESS_TOKEN
from startup.routes import register_routes
from startup.exception_handlers import register_exception_handlers
from startup.endpoints import register_endpoints, APP_VERSION

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build and return the configured SmartLic FastAPI application."""
    # Logging
    setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    log_feature_flags()
    validate_feature_flags()

    # Sentry
    _env = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
    init_sentry(env=_env, version=APP_VERSION)

    # #1694: Configure asyncio event loop to prevent slow callback warnings.
    # ---
    # Python 3.12+ defaults to ThreadPoolExecutor(max_workers=min(32, cpu_count*5)),
    # which can be as low as 5 on Railway containers (2 vCPUs). Every sb_execute
    # call uses asyncio.to_thread() to offload synchronous postgrest-py .execute(),
    # so a small thread pool causes queueing delays and legible slow-callback warnings.
    #
    # Raise max_workers=20 so 2× Gunicorn workers × 10 SB slots = 20 parallel
    # thread-offloaded Supabase calls before queuing.
    try:
        _loop = asyncio.get_running_loop()
    except RuntimeError:
        # Python 3.12+: no running event loop in the current thread
        # (e.g., during TestClient tests that call create_app() synchronously).
        # Fall back to a fresh loop — production always has get_running_loop().
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)

    _loop.set_default_executor(
        concurrent.futures.ThreadPoolExecutor(max_workers=20)
    )
    # Also raise the slow-callback warning threshold from 100ms to 500ms so
    # brief (100-180ms) event-loop delays don't pollute production logs.
    # PYTHONASYNCIODEBUG must still be OFF in prod; this is a belt-and-suspenders
    # guard for the case where DEBUG gets accidentally enabled.
    _loop.slow_callback_duration = 0.5  # warn only >500ms (default 0.1s)
    logger.info(
        "asyncio configured: default_executor=max_workers=20, slow_callback_duration=0.5s"
    )

    # OTel tracing — before app creation
    from telemetry import init_tracing as _init_tracing
    _init_tracing()

    # FastAPI instance
    app = FastAPI(
        title="SmartLic API",
        description=(
            "API para busca e analise de licitacoes em fontes oficiais brasileiras.\n\n"
            "## Data Sources\n"
            "- **PNCP** (Portal Nacional de Contratacoes Publicas) - primary\n"
            "- **PCP v2** (Portal de Compras Publicas) - secondary\n"
            "- **ComprasGov v3** (Dados Abertos de Compras Governamentais) - tertiary\n\n"
            "## Authentication\n"
            "All endpoints require a Supabase JWT Bearer token unless noted otherwise.\n\n"
            "## Contact\n"
            "CONFENGE Avaliacoes e Inteligencia Artificial LTDA\n"
            "- Website: https://smartlic.tech\n"
            "- Email: suporte@smartlic.tech"
        ),
        version=APP_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "search", "description": "Multi-source procurement search with AI classification"},
            {"name": "pipeline", "description": "Opportunity pipeline (kanban board)"},
            {"name": "billing", "description": "Stripe billing, subscriptions, and plan management"},
            {"name": "admin", "description": "Admin-only user management and system operations"},
            {"name": "feature-flags", "description": "Runtime feature flag management (admin only)"},
            {"name": "analytics", "description": "Usage analytics and dashboards"},
            {"name": "health", "description": "Health checks and readiness probes"},
        ],
    )

    # Middleware (CORS, custom, inline HTTP middlewares)
    setup_middleware(app)

    # Routes
    register_routes(app)

    # OTel instrumentation — after all middleware
    from telemetry import instrument_fastapi_app
    instrument_fastapi_app(app)

    # Exception handlers
    register_exception_handlers(app)

    # Root endpoints (/, /v1/setores, /debug/pncp-test)
    register_endpoints(app)

    # Prometheus /metrics (conditional)
    setup_metrics_endpoint(app)

    logger.info(
        "FastAPI application initialized — PORT=%s, docs=%s",
        os.getenv("PORT", "8000"),
        "protected" if DOCS_ACCESS_TOKEN else "open",
    )

    return app
