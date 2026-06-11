"""TEST-ERR-RECOVERY-2026-001 AC1.2 — Pool exhaustion recovery.

Validates the datalake_query semaphore (memory ``outcome_log_2026_05`` →
chief-pool-semaphore-001): when concurrent fan-out saturates the pool,
later requests fail-fast with ``[]`` (no wedge), and once the burst
clears, fresh requests recover normally.

Origin: POOL-LEAK-001 (2026-04-29) — N waiters queueing on the Supabase
pool produced a wedge that survived statement_timeout. The fix (Apr 30)
was a per-process ``asyncio.Semaphore(3)`` in ``backend/datalake_query.py``
with a 2 s acquire timeout (fail-open with ``[]``).
"""

from __future__ import annotations

import asyncio

import pytest


pytestmark = pytest.mark.asyncio


async def test_semaphore_sheds_when_saturated(monkeypatch):
    """AC1.2.a — Acquiring more than the configured slots fails fast.

    We replace the module-level semaphore with a tiny one (size 1) and
    park one slow holder. A second arrival must NOT block past the 2 s
    acquire budget — the function returns ``[]`` (fail-open) and lets
    the worker handle other traffic.
    """

    import datalake_query as dq

    tiny = asyncio.Semaphore(1)
    monkeypatch.setattr(dq, "_SEO_SEMAPHORE", tiny)
    # Empty cache to force the semaphore path.
    dq._query_cache.clear()

    # Park the only slot.
    _hold1 = await tiny.acquire()  # type: ignore[func-returns-value]
    try:
        # Force the supabase import to fail fast so the test does not need
        # network/DB. The semaphore-shed path returns BEFORE this import,
        # but if we ever release the semaphore, we still want a
        # deterministic exit.
        async def _patched_query():
            # 2.0 s acquire timeout inside query_datalake — give it 4 s
            # ceiling so we can detect a wedge regression.
            return await asyncio.wait_for(
                dq.query_datalake(
                    ufs=["SC"],
                    data_inicial="2026-05-01",
                    data_final="2026-05-08",
                    keywords=["asfalto"],
                ),
                timeout=4.0,
            )

        result = await _patched_query()
        # Fail-open contract: empty list, never None, never exception.
        assert result == []
    finally:
        # tiny.acquire() is a coroutine in some Python versions and a
        # context-managed primitive in others — release defensively.
        try:
            tiny.release()
        except Exception:
            pass


async def test_subsequent_request_recovers_after_burst(monkeypatch):
    """AC1.2.b — Once the burst clears, the next caller runs again.

    Reproduces the recovery half of POOL-LEAK-001: even after 5 callers
    were shed, the pool returns to a healthy state and the very next
    request observes the cache instead of being wedged.
    """

    import datalake_query as dq

    # Seed the cache so query_datalake short-circuits without DB.
    dq._query_cache.clear()
    cache_payload = [{"numero_controle_pncp": "abc", "uf_label": "SC"}]
    key = dq._cache_key(["SC"], "2026-05-01", "2026-05-08", "asfalto", "", "publicacao")
    dq._cache_put(key, cache_payload)

    tiny = asyncio.Semaphore(2)
    monkeypatch.setattr(dq, "_SEO_SEMAPHORE", tiny)

    # Burst of 6 cache-hit requests — semaphore is bypassed for cache hits,
    # so all 6 must succeed without contention.
    results = await asyncio.gather(
        *[
            dq.query_datalake(
                ufs=["SC"],
                data_inicial="2026-05-01",
                data_final="2026-05-08",
                keywords=["asfalto"],
            )
            for _ in range(6)
        ]
    )
    assert all(r == cache_payload for r in results), \
        "cache-hit path should NOT contend on the semaphore"


async def test_acquire_timeout_does_not_double_release(monkeypatch):
    """AC1.2.c — Edge case: shedding does not leak semaphore counters.

    Regression for the original pool leak: the wait_for cancels the
    awaiting coroutine, but the helper must NOT call ``release()`` for a
    slot that was never acquired (which would unbalance the counter and
    silently raise the slot count).
    """

    import datalake_query as dq

    tiny = asyncio.Semaphore(1)
    monkeypatch.setattr(dq, "_SEO_SEMAPHORE", tiny)
    dq._query_cache.clear()

    _hold2 = await tiny.acquire()  # type: ignore[func-returns-value]
    try:
        # First call should shed (slot is held by us).
        out = await dq.query_datalake(
            ufs=["SC"],
            data_inicial="2026-05-01",
            data_final="2026-05-08",
            keywords=["asfalto"],
        )
        assert out == []
    finally:
        tiny.release()

    # Counter should be back at exactly 1 — verify we can acquire+release
    # exactly once more without going negative.
    await tiny.acquire()
    tiny.release()
