"""GAP-004 (#1581): Tests for ARQ retry policy per job type.

Verifies:
- _with_ingestion_retry raises arq.Retry when job_try < max_tries
- _with_ingestion_retry returns normally when job_try >= max_tries
- Backoff delay calculation: base * multiplier^(try-1)
- Prometheus metric ARQ_JOB_RETRIES_TOTAL is incremented on retry
- WARNING log emitted on retry with job_id, try_count, next_retry_at
- arq.func() wrappers have correct max_tries per job type
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Tests for _with_ingestion_retry helper
# ============================================================================


class TestWithIngestionRetry:
    """Unit tests for the _with_ingestion_retry helper function."""

    @pytest.mark.asyncio
    async def test_raises_retry_on_first_failure(self):
        """job_try=1, max_tries=3 -> raises arq.Retry(defer=60) (base=60, mult=5)."""
        from ingestion.scheduler import _with_ingestion_retry

        ctx = {"job_try": 1}

        from arq import Retry; with pytest.raises(Retry) as exc_info:
            await _with_ingestion_retry(
                ctx=ctx,
                job_name="TestJob",
                max_tries=3,
                backoff_base=60,
                backoff_multiplier=5,
                error=RuntimeError("boom"),
                duration_s=10.0,
            )

        # 60 * 5^(1-1) = 60 * 1 = 60
        assert exc_info.value.defer_score == 60000  # 60s in ms

    @pytest.mark.asyncio
    async def test_raises_retry_on_second_failure(self):
        """job_try=2, max_tries=3 -> raises arq.Retry(defer=300)."""
        from ingestion.scheduler import _with_ingestion_retry

        ctx = {"job_try": 2}

        from arq import Retry; with pytest.raises(Retry) as exc_info:
            await _with_ingestion_retry(
                ctx=ctx,
                job_name="TestJob",
                max_tries=3,
                backoff_base=60,
                backoff_multiplier=5,
                error=RuntimeError("boom"),
                duration_s=10.0,
            )

        # 60 * 5^(2-1) = 60 * 5 = 300
        assert exc_info.value.defer_score == 300000  # 300s in ms

    @pytest.mark.asyncio
    async def test_returns_normally_on_last_attempt(self):
        """job_try=3, max_tries=3 -> returns normally (no retry)."""
        from ingestion.scheduler import _with_ingestion_retry

        ctx = {"job_try": 3}

        # Should NOT raise Retry
        result = await _with_ingestion_retry(
            ctx=ctx,
            job_name="TestJob",
            max_tries=3,
            backoff_base=60,
            backoff_multiplier=5,
            error=RuntimeError("boom"),
            duration_s=10.0,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_normally_when_exceeded(self):
        """job_try=5, max_tries=3 -> returns normally (exceeded max)."""
        from ingestion.scheduler import _with_ingestion_retry

        ctx = {"job_try": 5}

        result = await _with_ingestion_retry(
            ctx=ctx,
            job_name="TestJob",
            max_tries=3,
            backoff_base=60,
            backoff_multiplier=5,
            error=RuntimeError("boom"),
            duration_s=10.0,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_default_job_try_is_one(self):
        """When ctx has no job_try, defaults to 1 (retry on first failure)."""
        from ingestion.scheduler import _with_ingestion_retry

        ctx = {}  # no job_try key

        from arq import Retry; with pytest.raises(Retry):
            await _with_ingestion_retry(
                ctx=ctx,
                job_name="TestJob",
                max_tries=3,
                backoff_base=10,
                backoff_multiplier=2,
                error=ValueError("fail"),
                duration_s=5.0,
            )

    @pytest.mark.asyncio
    async def test_emits_warning_log_on_retry(self, caplog):
        """WARNING log emitted with job_name, try_count, delay info."""
        from ingestion.scheduler import _with_ingestion_retry

        ctx = {"job_try": 1}

        with caplog.at_level(logging.WARNING), pytest.raises(Retry):
            await _with_ingestion_retry(
                ctx=ctx,
                job_name="FullCrawl",
                max_tries=3,
                backoff_base=60,
                backoff_multiplier=5,
                error=RuntimeError("API timeout"),
                duration_s=30.5,
            )

        assert len(caplog.records) >= 1
        log_msg = caplog.text
        assert "FullCrawl" in log_msg
        assert "Attempt 1/3" in log_msg
        assert "Retrying in 60s" in log_msg
        assert "next_retry_at" in log_msg
        assert "RuntimeError" in log_msg

    @pytest.mark.asyncio
    async def test_increments_prometheus_metric_on_retry(self):
        """ARQ_JOB_RETRIES_TOTAL is incremented on retry."""
        from ingestion.scheduler import _with_ingestion_retry

        mock_metric = MagicMock()
        mock_metric.labels.return_value = mock_metric

        ctx = {"job_try": 1}

        with (
            patch("ingestion.metrics.ARQ_JOB_RETRIES_TOTAL", mock_metric),
            from arq import Retry; pytest.raises(Retry),
        ):
            await _with_ingestion_retry(
                ctx=ctx,
                job_name="FullCrawl",
                max_tries=3,
                backoff_base=60,
                backoff_multiplier=5,
                error=RuntimeError("timeout"),
                duration_s=10.0,
            )

        mock_metric.labels.assert_called_once_with(job_name="FullCrawl")
        mock_metric.inc.assert_called_once()

    @pytest.mark.asyncio
    async def test_metric_not_incremented_on_final_failure(self):
        """ARQ_JOB_RETRIES_TOTAL NOT incremented on final failure (no retry)."""
        from ingestion.scheduler import _with_ingestion_retry

        mock_metric = MagicMock()

        ctx = {"job_try": 3}  # max_tries=3, so this is final

        with patch("ingestion.metrics.ARQ_JOB_RETRIES_TOTAL", mock_metric):
            await _with_ingestion_retry(
                ctx=ctx,
                job_name="FullCrawl",
                max_tries=3,
                backoff_base=60,
                backoff_multiplier=5,
                error=RuntimeError("timeout"),
                duration_s=10.0,
            )

        mock_metric.labels.assert_not_called()
        mock_metric.inc.assert_not_called()


# ============================================================================
# Tests for arq.func() wrapper max_tries
# ============================================================================


class TestJobWrapperMaxTries:
    """Verify arq.func() wrappers have correct max_tries per job type."""

    def test_full_crawl_wrapper_has_max_tries_3(self):
        """ingestion_full_crawl_func should have max_tries=3."""
        from ingestion.scheduler import ingestion_full_crawl_func

        assert ingestion_full_crawl_func.max_tries == 3

    def test_incremental_wrapper_has_max_tries_3(self):
        """ingestion_incremental_func should have max_tries=3."""
        from ingestion.scheduler import ingestion_incremental_func

        assert ingestion_incremental_func.max_tries == 3

    def test_contracts_full_wrapper_has_max_tries_3(self):
        """contracts_full_crawl_func should have max_tries=3."""
        from ingestion.scheduler import contracts_full_crawl_func

        assert contracts_full_crawl_func.max_tries == 3

    def test_contracts_incremental_wrapper_has_max_tries_3(self):
        """contracts_incremental_func should have max_tries=3."""
        from ingestion.scheduler import contracts_incremental_func

        assert contracts_incremental_func.max_tries == 3

    def test_backfill_wrapper_has_max_tries_3(self):
        """ingestion_backfill_func should have max_tries=3."""
        from ingestion.scheduler import ingestion_backfill_func

        assert ingestion_backfill_func.max_tries == 3

    def test_purge_wrapper_has_max_tries_1(self):
        """ingestion_purge_func should have max_tries=1 (no retry)."""
        from ingestion.scheduler import ingestion_purge_func

        assert ingestion_purge_func.max_tries == 1

    def test_enrich_entities_wrapper_has_max_tries_1(self):
        """enrich_entities_func should have max_tries=1 (no retry)."""
        from ingestion.scheduler import enrich_entities_func

        assert enrich_entities_func.max_tries == 1

    def test_enrich_municipios_wrapper_has_max_tries_1(self):
        """enrich_municipios_func should have max_tries=1 (no retry)."""
        from ingestion.scheduler import enrich_municipios_func

        assert enrich_municipios_func.max_tries == 1

    def test_enrich_ibge_codes_wrapper_has_max_tries_1(self):
        """enrich_pncp_ibge_codes_func should have max_tries=1 (no retry)."""
        from ingestion.scheduler import enrich_pncp_ibge_codes_func

        assert enrich_pncp_ibge_codes_func.max_tries == 1


# ============================================================================
# Tests for WorkerSettings global max_tries
# ============================================================================


class TestWorkerSettingsMaxTries:
    """WorkerSettings should default to max_tries=1 (no retry)."""

    def test_worker_settings_max_tries_defaults_to_1(self):
        """WorkerSettings.max_tries should be 1 (GAP-004)."""
        # We can't easily import WorkerSettings without full ARQ setup,
        # so we check the source attribute directly.
        from jobs.queue.config import WorkerSettings

        assert WorkerSettings.max_tries == 1

    def test_worker_settings_no_retry_delay(self):
        """WorkerSettings should NOT have retry_delay (dead code removed)."""
        from jobs.queue.config import WorkerSettings

        assert not hasattr(WorkerSettings, "retry_delay")


# ============================================================================
# Tests for crawl job integration (retry called on exception)
# ============================================================================


class TestCrawlJobRetryIntegration:
    """Crawl jobs should call _with_ingestion_retry on exception."""

    @pytest.mark.asyncio
    async def test_full_crawl_invokes_retry_on_failure(self):
        """ingestion_full_crawl_job calls _with_ingestion_retry on exception.

        crawl_full is imported locally inside the job function, so we
        patch it at its actual module: ingestion.crawler.crawl_full.
        """
        from ingestion.scheduler import ingestion_full_crawl_job

        with (
            patch("ingestion.scheduler.DATALAKE_ENABLED", True),
            patch("ingestion.crawler.crawl_full", side_effect=RuntimeError("PNCP timeout")),
            patch("ingestion.scheduler._with_ingestion_retry", new_callable=AsyncMock) as mock_retry,
        ):
            await ingestion_full_crawl_job({"job_try": 1})

        mock_retry.assert_called_once()
        # job_name is the 2nd positional arg (ctx is 1st)
        assert mock_retry.call_args.args[1] == "FullCrawl"
        assert mock_retry.call_args.kwargs["max_tries"] == 3
        assert mock_retry.call_args.kwargs["backoff_base"] == 60
        assert mock_retry.call_args.kwargs["backoff_multiplier"] == 5

    @pytest.mark.asyncio
    async def test_incremental_crawl_invokes_retry_on_failure(self):
        """ingestion_incremental_job calls _with_ingestion_retry on exception.

        crawl_incremental is imported locally inside the job function, so we
        patch it at its actual module: ingestion.crawler.crawl_incremental.
        """
        from ingestion.scheduler import ingestion_incremental_job

        with (
            patch("ingestion.scheduler.DATALAKE_ENABLED", True),
            patch("ingestion.crawler.crawl_incremental", side_effect=RuntimeError("timeout")),
            patch("ingestion.scheduler._with_ingestion_retry", new_callable=AsyncMock) as mock_retry,
        ):
            await ingestion_incremental_job({"job_try": 1})

        mock_retry.assert_called_once()
        # job_name is the 2nd positional arg
        assert mock_retry.call_args.args[1] == "Incremental"

    @pytest.mark.asyncio
    async def test_purge_job_does_not_retry(self):
        """ingestion_purge_job should NOT call _with_ingestion_retry (no retry).

        purge_old_bids is imported locally inside the job function, so we
        patch it at its actual module: ingestion.loader.purge_old_bids.
        """
        from ingestion.scheduler import ingestion_purge_job

        with (
            patch("ingestion.scheduler.DATALAKE_ENABLED", True),
            patch("ingestion.loader.purge_old_bids", side_effect=RuntimeError("DB error")),
            patch("ingestion.scheduler._with_ingestion_retry", new_callable=AsyncMock) as mock_retry,
            patch("ingestion.scheduler._notify_failure", new_callable=AsyncMock),
        ):
            result = await ingestion_purge_job({"job_try": 1})

        mock_retry.assert_not_called()
        assert result["status"] == "failed"


# ============================================================================
# Tests for config constants
# ============================================================================


class TestRetryConfig:
    """Verify retry config defaults."""

    def test_crawl_retry_defaults(self):
        """Crawl retry defaults: max_tries=3, base=60, multiplier=5."""
        from ingestion.config import (
            CRAWL_RETRY_MAX_TRIES,
            CRAWL_RETRY_BACKOFF_BASE,
            CRAWL_RETRY_BACKOFF_MULTIPLIER,
        )

        assert CRAWL_RETRY_MAX_TRIES == 3
        assert CRAWL_RETRY_BACKOFF_BASE == 60
        assert CRAWL_RETRY_BACKOFF_MULTIPLIER == 5

    def test_purge_retry_defaults(self):
        """Purge retry defaults: max_tries=1 (no retry)."""
        from ingestion.config import PURGE_RETRY_MAX_TRIES

        assert PURGE_RETRY_MAX_TRIES == 1

    def test_enricher_retry_defaults(self):
        """Enricher retry defaults: max_tries=1 (no retry)."""
        from ingestion.config import ENRICHER_RETRY_MAX_TRIES

        assert ENRICHER_RETRY_MAX_TRIES == 1


# ============================================================================
# Edge case tests
# ============================================================================


class TestRetryEdgeCases:
    """Edge cases for the retry logic."""

    @pytest.mark.asyncio
    async def test_graceful_metric_failure_does_not_block_retry(self):
        """If Prometheus metric increment fails, retry still happens."""
        from ingestion.scheduler import _with_ingestion_retry

        broken_metric = MagicMock()
        broken_metric.labels.side_effect = Exception("Prometheus down")

        ctx = {"job_try": 1}

        with (
            patch("ingestion.metrics.ARQ_JOB_RETRIES_TOTAL", broken_metric),
            from arq import Retry; pytest.raises(Retry),
        ):
            await _with_ingestion_retry(
                ctx=ctx,
                job_name="FullCrawl",
                max_tries=3,
                backoff_base=60,
                backoff_multiplier=5,
                error=RuntimeError("timeout"),
                duration_s=10.0,
            )

    @pytest.mark.asyncio
    async def test_backoff_calculations(self):
        """Verify backoff formula for multiple retries."""
        from ingestion.scheduler import _with_ingestion_retry

        ctx = {"job_try": 1}

        # 1st retry: base * mult^0 = 60s
        with patch("time.time", return_value=1000), pytest.raises(Retry) as exc:
            await _with_ingestion_retry(
                ctx=ctx, job_name="Test", max_tries=3,
                backoff_base=60, backoff_multiplier=5,
                error=Exception("e"), duration_s=5.0,
            )
        assert exc.value.defer_score == 60000  # 60s

        # 2nd retry: base * mult^1 = 300s
        ctx["job_try"] = 2
        with patch("time.time", return_value=1000), pytest.raises(Retry) as exc:
            await _with_ingestion_retry(
                ctx=ctx, job_name="Test", max_tries=3,
                backoff_base=60, backoff_multiplier=5,
                error=Exception("e"), duration_s=5.0,
            )
        assert exc.value.defer_score == 300000  # 300s
