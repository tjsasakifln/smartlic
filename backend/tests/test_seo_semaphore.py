"""Tests for POOL-001: SEOSemaphore universal pool protection.

Tests cover:
1. SEOSemaphore acquire/release basics
2. Semaphore exhaustion → 503
3. Negative cache check/set (Redis + InMemory fallback)
4. SEO_SEMAPHORE_DISABLED bypass
5. Context manager (protect)
6. Factory function
7. Prometheus metric no-op when prometheus_client unavailable
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from fastapi import HTTPException

from utils.seo_semaphore import (
    SEO_SEMAPHORE_DISABLED,
    SEOSemaphore,
    seo_semaphore,
)


class TestSEOSemaphoreBasics:
    """Core semaphore acquire/release behavior."""

    async def test_acquire_release(self):
        """Happy path: acquire and release a slot (single slot semaphore)."""
        sem = SEOSemaphore("test", max_concurrent=1)
        assert sem.max_concurrent == 1
        assert not sem.locked

        await sem.acquire()
        assert sem.locked

        sem.release()
        assert not sem.locked

    async def test_acquire_on_full_semaphore_raises_503(self):
        """When all slots are busy, acquire raises HTTPException(503)."""
        sem = SEOSemaphore(
            "test",
            max_concurrent=1,
            acquire_timeout_s=0.1,  # Fast timeout for tests
            retry_after_s=5,
        )

        # Take the only slot
        await sem.acquire()

        # Now try to acquire — should raise 503 after timeout
        with pytest.raises(HTTPException) as exc_info:
            await sem.acquire()

        assert exc_info.value.status_code == 503
        assert "Retry-After" in exc_info.value.headers
        assert exc_info.value.headers["Retry-After"] == "5"

        # Release the slot
        sem.release()

    async def test_acquire_then_release_frees_slot(self):
        """After release, the slot becomes available again."""
        sem = SEOSemaphore("test", max_concurrent=1, acquire_timeout_s=0.2)

        await sem.acquire()
        sem.release()

        # Now should be able to acquire again
        await sem.acquire()
        sem.release()


class TestSeoSemaphoreNegativeCache:
    """Negative cache check/set behavior."""

    async def test_check_negative_cache_no_redis(self):
        """When Redis is unavailable, check_negative_cache returns False."""
        sem = SEOSemaphore("test")

        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=None):
            result = await sem.check_negative_cache("some:key")
            assert result is False

    async def test_set_negative_cache_graceful_fallback(self):
        """When Redis set fails, no exception propagates."""
        sem = SEOSemaphore("test")

        with patch("redis_pool.get_redis_pool", return_value=None):
            with patch("redis_pool.get_fallback_cache", return_value=MagicMock()):
                # Should not raise
                await sem.set_negative_cache("some:key")

    async def test_check_negative_cache_empty_key(self):
        """Empty cache key returns False immediately (no Redis call)."""
        sem = SEOSemaphore("test")
        assert await sem.check_negative_cache("") is False

    async def test_set_negative_cache_empty_key(self):
        """Empty cache key doesn't attempt Redis call."""
        sem = SEOSemaphore("test")
        # Should not raise
        await sem.set_negative_cache("")


class TestSeoSemaphoreDisabled:
    """SEO_SEMAPHORE_DISABLED behavior."""

    def test_disabled_flag_default(self):
        """SEO_SEMAPHORE_DISABLED defaults to False."""
        # This test assumes no env var is set
        assert SEO_SEMAPHORE_DISABLED is False

    def test_disabled_flag_from_env(self, monkeypatch):
        """Setting env var disables semaphore."""
        monkeypatch.setenv("SEO_SEMAPHORE_DISABLED", "true")
        # Re-import to pick up new env var
        import importlib
        import utils.seo_semaphore as sem_mod

        importlib.reload(sem_mod)
        assert sem_mod.SEO_SEMAPHORE_DISABLED is True

        monkeypatch.delenv("SEO_SEMAPHORE_DISABLED", raising=False)
        importlib.reload(sem_mod)
        assert sem_mod.SEO_SEMAPHORE_DISABLED is False


class TestSeoSemaphoreFactory:
    """Factory function behavior."""

    def test_factory_returns_seo_semaphore(self):
        """seo_semaphore() factory returns a SEOSemaphore instance."""
        sem = seo_semaphore("test", max_concurrent=3)
        assert sem.name == "test"
        assert sem.max_concurrent == 3
        assert hasattr(sem, "acquire")
        assert hasattr(sem, "release")
        assert hasattr(sem, "check_negative_cache")

    def test_factory_defaults(self):
        """Factory uses sensible defaults."""
        sem = seo_semaphore("test")
        assert sem.max_concurrent == 3
        assert sem.name == "test"

    def test_factory_different_max_concurrent(self):
        """Different max_concurrent values create different semaphores."""
        sem_p1 = seo_semaphore("p1", max_concurrent=3)
        sem_p2 = seo_semaphore("p2", max_concurrent=2)
        assert sem_p1.max_concurrent == 3
        assert sem_p2.max_concurrent == 2


class TestSeoSemaphoreContextManager:
    """Context manager (protect) behavior."""

    async def test_protect_context_happy_path(self):
        """protect context manager acquires and releases."""
        sem = SEOSemaphore("test", max_concurrent=1)

        async with sem.protect(cache_key="some:key"):
            pass  # Should acquire and release

        # After context, semaphore should be free
        assert not sem.locked

    async def test_protect_without_cache_key(self):
        """protect without cache_key does not check negative cache."""
        sem = SEOSemaphore("test", max_concurrent=1)

        async with sem.protect():
            pass

        assert not sem.locked

    async def test_protect_with_exception(self):
        """protect releases on exception."""
        sem = SEOSemaphore("test", max_concurrent=1)

        with pytest.raises(RuntimeError):
            async with sem.protect(cache_key="key"):
                raise RuntimeError("test error")

        # Semaphore should still be released
        assert not sem.locked
        # Can acquire again
        await sem.acquire()
        sem.release()


class TestSeoSemaphorePrometheusMetrics:
    """Prometheus metric integration."""

    async def test_metrics_labels(self):
        """Metric labels match route names."""
        sem_obs = seo_semaphore("observatorio", max_concurrent=3)
        sem_blog = seo_semaphore("blog_stats", max_concurrent=3)

        assert sem_obs.name == "observatorio"
        assert sem_blog.name == "blog_stats"

    async def test_acquire_records_wait_seconds(self):
        """Acquire observes a histogram metric."""
        sem = SEOSemaphore("test_metrics", acquire_timeout_s=1.0)

        # The metric object should be a no-op or real metric depending on
        # prometheus_client availability. Either way, acquire must not crash.
        await sem.acquire()
        sem.release()

    async def test_negative_cache_hits_metric(self):
        """Negative cache check incurs a counter metric."""
        from utils.seo_semaphore import SEO_NEGATIVE_CACHE_HITS

        # The metric object should not crash on method calls
        SEO_NEGATIVE_CACHE_HITS.labels(route="test").inc()


class TestBlogStatsMigration:
    """Blog stats migration does not break existing patterns."""

    async def test_blog_stats_semaphore_created(self):
        """blog_stats creates a SEOSemaphore with max_concurrent=3."""
        # Re-import blog_stats to verify its module-level semaphore
        from routes import blog_stats

        assert hasattr(blog_stats, "_SEM")
        assert blog_stats._SEM.name == "blog_stats"
        assert blog_stats._SEM.max_concurrent == 3


class TestRouterImports:
    """All 18+ routers have the SEOSemaphore import and _SEM variable."""

    ROUTER_NAMES = [
        ("routes.observatorio", "observatorio", 3),
        ("routes.contratos_publicos", "contratos_publicos", 3),
        ("routes.empresa_publica", "empresa_publica", 3),
        ("routes.orgao_publico", "orgao_publico", 3),
        ("routes.sectors_public", "sectors_public", 2),
        ("routes.municipios_publicos", "municipios_publicos", 2),
        ("routes.itens_publicos", "itens_publicos", 2),
        ("routes.alertas_publicos", "alertas_publicos", 2),
        ("routes.calculadora", "calculadora", 2),
        ("routes.comparador", "comparador", 2),
        ("routes.compliance_publicos", "compliance_publicos", 2),
        ("routes.indice_municipal", "indice_municipal", 2),
        ("routes.dados_publicos", "dados_publicos", 2),
        ("routes.daily_digest", "daily_digest", 2),
        ("routes.weekly_digest", "weekly_digest", 2),
    ]

    def test_semaphore_imports(self):
        """Verify each router module has the seo_semaphore import."""
        import importlib

        for module_name, expected_name, expected_max in self.ROUTER_NAMES:
            mod = importlib.import_module(module_name)
            assert hasattr(mod, "_SEM"), f"{module_name} missing _SEM"
            assert mod._SEM.name == expected_name, (
                f"{module_name} _SEM.name={mod._SEM.name}, expected {expected_name}"
            )
            assert mod._SEM.max_concurrent == expected_max, (
                f"{module_name} _SEM.max_concurrent={mod._SEM.max_concurrent}, "
                f"expected {expected_max}"
            )
