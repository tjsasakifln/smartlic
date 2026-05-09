"""TEST-ERR-RECOVERY-2026-001 AC1.1 — Pipeline timeout recovery.

Validates that when a pipeline call hangs beyond the budget, the
``_run_with_budget`` wrapper raises ``TimeoutError`` (not propagating the
underlying ``asyncio.TimeoutError`` silently) and that the worker is
free to accept the next request — i.e. no event-loop wedge.

Origin: CRIT-084 + POOL-LEAK-001 incidents (2026-04-27 → 2026-04-30).
Memory: feedback_pool_leak_caller_timeout_vs_sql_timeout — wait_for cancels
the await but the SQL keeps running until statement_timeout. The route
must still be free to accept new work.
"""

import asyncio

import pytest

from pipeline.budget import _run_with_budget


pytestmark = pytest.mark.asyncio


async def _hangs_forever() -> None:
    """Coroutine that never completes (simulates a wedged DB call)."""
    await asyncio.sleep(3600)


async def _completes_quickly(value: int = 42) -> int:
    return value


async def test_run_with_budget_raises_on_overrun():
    """AC1.1.a — TimeoutError is raised when budget exceeds."""
    with pytest.raises(asyncio.TimeoutError):
        await _run_with_budget(
            _hangs_forever(),
            budget=0.1,
            phase="route",
            source="test_pipeline_timeout_recovery",
        )


async def test_worker_recycles_after_budget_overrun():
    """AC1.1.b — After the timeout, the event loop accepts new work.

    The hallmark of pool-leak / wedge is that subsequent work blocks. We
    fire a fast follow-up call right after the timeout fires and assert it
    completes within a tight bound.
    """
    with pytest.raises(asyncio.TimeoutError):
        await _run_with_budget(
            _hangs_forever(),
            budget=0.05,
            phase="route",
            source="test_pipeline_timeout_recovery",
        )

    # If the loop were wedged, this would also time out. Tight 1s bound
    # makes the regression unmistakable.
    result = await asyncio.wait_for(_completes_quickly(99), timeout=1.0)
    assert result == 99


async def test_concurrent_requests_independent_under_timeout():
    """AC1.1.c — Edge case: a hanging call must not starve sibling calls.

    Two coroutines run together; one hangs, one is fast. The fast one must
    return promptly even while the hung sibling is being torn down by the
    budget wrapper.
    """

    async def hung():
        with pytest.raises(asyncio.TimeoutError):
            await _run_with_budget(
                _hangs_forever(),
                budget=0.2,
                phase="route",
                source="hung_sibling",
            )
        return "hung_done"

    async def fast():
        return await _run_with_budget(
            _completes_quickly(7),
            budget=2.0,
            phase="route",
            source="fast_sibling",
        )

    hung_result, fast_result = await asyncio.gather(hung(), fast())
    assert hung_result == "hung_done"
    assert fast_result == 7
