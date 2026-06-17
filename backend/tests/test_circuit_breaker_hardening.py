"""Issue #1919: Circuit breaker hardening tests."""
import asyncio
import pytest
from clients.pncp.circuit_breaker import (
    PNCPCircuitBreaker, ALL_CIRCUIT_BREAKERS,
    get_circuit_breaker, get_all_circuit_breaker_states,
)

def _make_cb(name="test", threshold=3, cooldown=0.01):
    return PNCPCircuitBreaker(name=name, threshold=threshold, cooldown_seconds=cooldown)

class TestCBOpens:
    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        cb = _make_cb(threshold=3)
        for _ in range(3):
            await cb.record_failure()
        assert cb.is_degraded

    @pytest.mark.asyncio
    async def test_success_resets(self):
        cb = _make_cb(threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        await cb.record_failure()
        assert not cb.is_degraded

class TestRecovery:
    @pytest.mark.asyncio
    async def test_recovers_after_cooldown(self):
        cb = _make_cb(threshold=2, cooldown=0.05)
        for _ in range(2):
            await cb.record_failure()
        assert cb.is_degraded
        await asyncio.sleep(0.06)
        recovered = await cb.try_recover()
        assert recovered
        assert not cb.is_degraded

    @pytest.mark.asyncio
    async def test_reset(self):
        cb = _make_cb(threshold=3)
        for _ in range(3):
            await cb.record_failure()
        assert cb.is_degraded
        cb.reset()
        assert not cb.is_degraded

class TestPerSource:
    SOURCES = ["pncp", "pcp", "comprasgov", "brasilapi", "ibge"]

    def test_all_have_cb(self):
        for s in self.SOURCES:
            assert s in ALL_CIRCUIT_BREAKERS

    @pytest.mark.asyncio
    async def test_brasilapi(self):
        cb = get_circuit_breaker("brasilapi")
        cb.reset()
        for _ in range(3):
            await cb.record_failure()
        assert cb.is_degraded

    @pytest.mark.asyncio
    async def test_ibge(self):
        cb = get_circuit_breaker("ibge")
        cb.reset()
        for _ in range(5):
            await cb.record_failure()
        assert cb.is_degraded

class TestGetCB:
    def test_default_pncp(self):
        assert get_circuit_breaker().name == "pncp"
    def test_brasilapi(self):
        assert get_circuit_breaker("brasilapi").name == "brasilapi"
    def test_ibge(self):
        assert get_circuit_breaker("ibge").name == "ibge"
    def test_fallback(self):
        assert get_circuit_breaker("unknown").name == "pncp"
    @pytest.mark.asyncio
    async def test_all_states(self):
        states = await get_all_circuit_breaker_states()
        sources = {name for name in states}
        for s in ["pncp", "pcp", "comprasgov", "brasilapi", "ibge"]:
            assert s in sources
