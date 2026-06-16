"""jobs.queue.config — ARQ WorkerSettings and cron job configuration."""
import logging
import os
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

arq_log_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"arq_fmt": {"format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", "datefmt": "%Y-%m-%d %H:%M:%S"}},
    "handlers": {"stdout": {"class": "logging.StreamHandler", "stream": "ext://sys.stdout", "formatter": "arq_fmt"}},
    "root": {"level": "INFO", "handlers": ["stdout"]},
}


def _get_redis_settings():
    """Build ARQ RedisSettings from REDIS_URL env var.

    Moved here from job_queue.py (was line 32) to break circular import:
    job_queue → jobs.queue.config → job_queue. Now jobs.queue.config
    defines the function and job_queue imports it.
    """
    from arq.connections import RedisSettings
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        raise ValueError("REDIS_URL not set — ARQ worker cannot start without Redis")
    parsed = urlparse(redis_url)
    ssl = parsed.scheme == "rediss"
    return RedisSettings(
        host=parsed.hostname or "localhost", port=parsed.port or 6379,
        password=parsed.password, database=int(parsed.path.lstrip("/") or 0),
        conn_timeout=10, conn_retries=5, conn_retry_delay=2.0, ssl=ssl,
        retry_on_timeout=True, retry_on_error=[TimeoutError, ConnectionError, OSError],
        max_connections=50,
    )


# Build worker Redis settings at module level
try:
    _worker_redis_settings = _get_redis_settings()
except Exception:
    _worker_redis_settings = None

# Build cron jobs list — cache_refresh_job + cache_warming_job deprecated 2026-04-18
# (STORY-CIG-BE-cache-warming-deprecate). DataLake is primary; no proactive warming needed.
try:
    from arq.cron import cron as _arq_cron
    from jobs.queue.jobs import daily_digest_job, email_alerts_job

    _worker_cron_jobs = []

    from config import DIGEST_ENABLED, DIGEST_HOUR_UTC
    if DIGEST_ENABLED:
        _worker_cron_jobs.append(_arq_cron(daily_digest_job, hour={DIGEST_HOUR_UTC}, minute=0, timeout=1800))

    from config import ALERTS_ENABLED, ALERTS_HOUR_UTC
    if ALERTS_ENABLED:
        _worker_cron_jobs.append(_arq_cron(email_alerts_job, hour={ALERTS_HOUR_UTC}, minute=0, timeout=1800))

    # PREDINT-024: daily predictive alert evaluation (7:00 UTC = 4:00 BRT).
    try:
        from jobs.cron.predictive_alert_job import predictive_alert_job
        _worker_cron_jobs.append(_arq_cron(predictive_alert_job, hour={7}, minute=0, timeout=600))
    except ImportError:
        pass

    # STORY-1.1 (EPIC-TD-2026Q2 P0): hourly pg_cron health monitor.
    # Always registered — surfaces silent failures of purge_old_bids + cleanup crons.
    try:
        from jobs.cron.cron_monitor import cron_monitoring_job
        _worker_cron_jobs.append(_arq_cron(cron_monitoring_job, minute={0}, timeout=300))
    except ImportError:  # cron_monitor optional — skip if module unavailable in test env
        pass

    # epic:fundadores — hourly auto-disable check: disables founding offer 1 day after deadline.
    try:
        from jobs.cron.founders_auto_disable import founders_auto_disable_check
        _worker_cron_jobs.append(_arq_cron(founders_auto_disable_check, minute={0}, timeout=60))
    except ImportError:
        pass

    # STORY-SEO-005: weekly GSC sync job (Sun 03:00 BRT = 06:00 UTC).
    # Graceful no-op if GSC_SERVICE_ACCOUNT_JSON env var missing — safe to register always.
    try:
        from jobs.cron.gsc_sync import gsc_sync_job
        _worker_cron_jobs.append(_arq_cron(gsc_sync_job, weekday={6}, hour={6}, minute=0, timeout=1800))
    except ImportError:
        pass

    # NETINT-007: weekly network_events cleanup job (Sun at configurable hour, default 03:00 UTC).
    try:
        from config import NETWORK_EVENTS_CLEANUP_HOUR, NETWORK_EVENTS_CLEANUP_ENABLED
        if NETWORK_EVENTS_CLEANUP_ENABLED:
            from jobs.cron.network_events_cleanup import aggregate_and_cleanup_network_events
            _worker_cron_jobs.append(
                _arq_cron(aggregate_and_cleanup_network_events, weekday={6}, hour={NETWORK_EVENTS_CLEANUP_HOUR}, minute=0, timeout=600)
            )
    except ImportError:
        pass

    try:
        from ingestion.config import DATALAKE_ENABLED
        if DATALAKE_ENABLED:
            from ingestion.scheduler import ingestion_full_crawl_job, ingestion_incremental_job, ingestion_purge_job
            from ingestion.config import INGESTION_FULL_CRAWL_HOUR_UTC, INGESTION_INCREMENTAL_HOURS
            _worker_cron_jobs.extend([
                _arq_cron(ingestion_full_crawl_job, hour={INGESTION_FULL_CRAWL_HOUR_UTC}, minute=0, timeout=14400),
                _arq_cron(ingestion_incremental_job, hour=set(INGESTION_INCREMENTAL_HOURS), minute=0, timeout=3600),
                _arq_cron(ingestion_purge_job, hour={INGESTION_FULL_CRAWL_HOUR_UTC + 2}, minute=0, timeout=600),
            ])
            # Supplier contracts index: 3x/week full crawl (Mon/Wed/Fri 06 UTC) + same days incremental
            # CONTRACTS_CRAWL_WEEKDAYS env var: comma-separated weekday names (default: mon,wed,fri)
            # Set CONTRACTS_CRAWL_WEEKDAYS=mon,tues,wed,thurs,fri,sat,sun for daily crawl
            from ingestion.scheduler import (
                contracts_full_crawl_job,
                contracts_incremental_job,
            )
            from ingestion.contracts_crawler import CONTRACTS_FULL_CRAWL_TIMEOUT, CONTRACTS_INCREMENTAL_TIMEOUT
            _contracts_enabled = __import__("os").getenv("CONTRACTS_INGESTION_ENABLED", "true").lower() in ("true", "1")
            if _contracts_enabled:
                _WDAY = {"mon": 0, "tues": 1, "wed": 2, "thurs": 3, "fri": 4, "sat": 5, "sun": 6}
                _raw_weekdays = __import__("os").getenv("CONTRACTS_CRAWL_WEEKDAYS", "mon,wed,fri")
                _contracts_weekdays = {_WDAY[w] for w in (d.strip() for d in _raw_weekdays.split(",")) if w in _WDAY}
                # DEBT-IO-BUDGET: staggered from +1h to +5h (10:00 UTC vs 06:00 UTC)
                # to avoid competing with full bid crawl for Disk IO
                _worker_cron_jobs.append(
                    _arq_cron(contracts_full_crawl_job, weekday=_contracts_weekdays, hour={INGESTION_FULL_CRAWL_HOUR_UTC + 5}, minute=0, timeout=CONTRACTS_FULL_CRAWL_TIMEOUT),
                )
                _worker_cron_jobs.append(
                    _arq_cron(contracts_incremental_job, weekday=_contracts_weekdays, hour={12, 18, 0}, minute=0, timeout=CONTRACTS_INCREMENTAL_TIMEOUT),
                )
            # Sprint 2 Parte 13: enriquecimento de fornecedores (BrasilAPI)
            # DEBT-IO-BUDGET: staggered to 20:00 UTC (17:00 BRT) to avoid
            # competing with ingestion crawls during 05:00-10:00 UTC peak window
            from ingestion.scheduler import enrich_entities_job
            _worker_cron_jobs.append(
                _arq_cron(enrich_entities_job, hour={20}, minute=0, timeout=7200),
            )
            # Sprint 4 Parte 13: enriquecimento de municipios (IBGE)
            # DEBT-IO-BUDGET: staggered to 21:00 UTC (18:00 BRT), 1h after enricher
            from ingestion.scheduler import enrich_municipios_job
            _worker_cron_jobs.append(
                _arq_cron(enrich_municipios_job, hour={21}, minute=0, timeout=3600),
            )
            # IBGE code backfill: runs 30min after each crawl wave
            # (full=5 UTC + 30min, incremental=11/17/23 UTC + 30min)
            # Backfills pncp_raw_bids.codigo_municipio_ibge for newly ingested rows
            from ingestion.scheduler import enrich_pncp_ibge_codes_job
            _worker_cron_jobs.append(
                _arq_cron(enrich_pncp_ibge_codes_job, hour={5, 11, 17, 23}, minute=30, timeout=1800),
            )
    except ImportError:
        pass

    # COMPINT-012 (#1666): Competitive alert detection (3x/day) + weekly digest.
    try:
        from jobs.cron.competitive_alert_job import (
            run_competitive_alert_detection,
            run_competitive_alert_weekly_digest,
        )
        _worker_cron_jobs.append(
            _arq_cron(
                run_competitive_alert_detection,
                hour={8, 14, 20},
                minute=0,
                timeout=600,
            )
        )
        _worker_cron_jobs.append(
            _arq_cron(
                run_competitive_alert_weekly_digest,
                weekday={0},  # Monday
                hour={11},
                minute=0,
                timeout=300,
            )
        )
    except ImportError:
        logger.debug("competitive_alert_job module not available — skipping registration")

    # Issue #1869: Synthetic monitoring — every 15 minutes (P1 user-flow check)
    try:
        from jobs.cron.synthetic_monitor import synthetic_monitor_job
        _worker_cron_jobs.append(
            _arq_cron(synthetic_monitor_job, minute={0, 15, 30, 45}, timeout=120),
        )
    except ImportError:
        logger.debug("synthetic_monitor_job not available — skipping registration")

except Exception:
    _worker_cron_jobs = []


async def _worker_on_startup(ctx: dict) -> None:
    import os as _os
    try:
        from config import setup_logging
        setup_logging(level=_os.getenv("LOG_LEVEL", "INFO"))
        logger.info("CRIT-051: Worker logging configured to stdout")
    except Exception as _log_err:
        logger.warning(f"CRIT-051: Failed to configure worker logging: {_log_err}")

    redis = ctx.get("redis")
    if redis and hasattr(redis, "connection_pool"):
        pool = redis.connection_pool
        if hasattr(pool, "connection_kwargs"):
            pool.connection_kwargs.setdefault("socket_timeout", 30)
            pool.connection_kwargs.setdefault("socket_connect_timeout", 10)
            pool.connection_kwargs.setdefault("socket_keepalive", True)
            logger.info("CRIT-038: Worker Redis pool hardened — socket_timeout=%ss", pool.connection_kwargs.get("socket_timeout"))
    else:
        logger.warning("CRIT-038: Could not access worker Redis connection pool for hardening")


class WorkerSettings:
    """ARQ worker configuration. Start with: arq job_queue.WorkerSettings"""
    from jobs.queue.jobs import (
        llm_summary_job, excel_generation_job, bid_analysis_job,
        daily_digest_job, email_alerts_job,
        reclassify_pending_bids_job, classify_zero_match_job,
        generate_intel_report,
        send_post_purchase_step,
        send_founders_welcome,
    )
    from jobs.queue.search import search_job

    _ingestion_functions: list = []
    try:
        from ingestion.config import DATALAKE_ENABLED as _dl_enabled
        if _dl_enabled:
            from ingestion.scheduler import (
                ingestion_full_crawl_func, ingestion_incremental_func, ingestion_purge_func,
                ingestion_backfill_func,
                contracts_full_crawl_func, contracts_incremental_func,
                enrich_entities_func,
                enrich_municipios_func,
                enrich_pncp_ibge_codes_func,
            )
            _ingestion_functions = [
                ingestion_full_crawl_func, ingestion_incremental_func, ingestion_purge_func,
                ingestion_backfill_func,
                contracts_full_crawl_func, contracts_incremental_func,
                enrich_entities_func,
                enrich_municipios_func,
                enrich_pncp_ibge_codes_func,
            ]
    except ImportError:
        pass

    # PREDINT-024: include predictive_alert_job so ARQ can dispatch daily runs.
    try:
        from jobs.cron.predictive_alert_job import predictive_alert_job as _predictive_alert_job
        _predictive_functions = [_predictive_alert_job]
    except ImportError:
        _predictive_functions = []

    # STORY-1.1: include cron_monitoring_job so ARQ can dispatch hourly runs.
    try:
        from jobs.cron.cron_monitor import cron_monitoring_job as _cron_monitoring_job
        _monitoring_functions = [_cron_monitoring_job]
    except ImportError:
        _monitoring_functions = []

    # epic:fundadores: auto-disable cron function.
    try:
        from jobs.cron.founders_auto_disable import founders_auto_disable_check as _founders_auto_disable_check
        _founders_functions = [_founders_auto_disable_check]
    except ImportError:
        _founders_functions = []

    # COMPINT-012 (#1666): Competitive alert detection + digest functions
    try:
        from jobs.cron.competitive_alert_job import (
            run_competitive_alert_detection,
            run_competitive_alert_weekly_digest,
        )
        _competitive_alert_functions = [
            run_competitive_alert_detection,
            run_competitive_alert_weekly_digest,
        ]
    except ImportError:
        _competitive_alert_functions = []

    # Lead magnet PDF delivery jobs
    try:
        from jobs.cron.send_lead_magnet import send_lead_magnet_job as _send_lead_magnet_job
        from jobs.cron.send_lead_magnet import send_lead_magnet_batch_job as _send_lead_magnet_batch_job
        _lead_magnet_functions = [_send_lead_magnet_job, _send_lead_magnet_batch_job]
    except ImportError:
        logger.exception(
            "Lead magnet jobs not registered; queued lead-magnet jobs will silently fail"
        )
        _lead_magnet_functions = []

    # NETINT-007: network_events cleanup function (weekly cron).
    try:
        from jobs.cron.network_events_cleanup import aggregate_and_cleanup_network_events as _network_events_cleanup_func
        _network_events_functions = [_network_events_cleanup_func]
    except ImportError:
        _network_events_functions = []

    # Issue #1869: Synthetic monitoring function
    try:
        from jobs.cron.synthetic_monitor import synthetic_monitor_job as _synthetic_monitor_job
        _synthetic_monitor_functions = [_synthetic_monitor_job]
    except ImportError:
        _synthetic_monitor_functions = []

    functions = [
        llm_summary_job, excel_generation_job, search_job,
        bid_analysis_job, daily_digest_job, email_alerts_job,
        reclassify_pending_bids_job, classify_zero_match_job,
        send_founders_welcome,
        generate_intel_report,
        send_post_purchase_step,
        send_founders_welcome,
        *_ingestion_functions,
        *_predictive_functions,
        *_monitoring_functions,
        *_founders_functions,
        *_lead_magnet_functions,
        *_competitive_alert_functions,
        *_network_events_functions,
        *_synthetic_monitor_functions,
    ]
    cron_jobs = _worker_cron_jobs
    on_startup = _worker_on_startup
    redis_settings = _worker_redis_settings
    max_jobs = 10
    job_timeout = 300
    max_tries = 1  # GAP-004 (#1581): per-job override via arq.func() for crawl jobs
    health_check_interval = 30

    # Issue #1813: ARQ Dead Letter Queue — capture failed jobs after max_tries
    # exhausted. Graceful degradation: enqueue failure is logged but never raised.
    try:
        from jobs.dlq import arq_on_job_failure as _arq_on_job_failure
        on_job_failure = _arq_on_job_failure
    except ImportError:
        on_job_failure = None
