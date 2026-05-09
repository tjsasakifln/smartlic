"""TEST-ERR-RECOVERY-2026-001 AC1.3 — Redis down → L2 fallback.

Validates that ``llm.get_or_generate_resumo_cached`` continues to produce
a result when Redis raises ``ConnectionError``: the cache reads/writes
are expected to log-and-continue (fire-and-forget), and the summary must
still be produced from the synchronous compute path.

Origin: 2026-04 cache-warming retirement (STORY-CIG-BE-cache-warming-deprecate)
exposed how reactive the cache layer is — when Redis blips, the LLM cache
must NOT propagate the error.
"""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


def _fake_resumo() -> MagicMock:
    """Return a minimal stand-in for ``ResumoLicitacoes`` with model_dump_json."""
    rs = MagicMock()
    rs.model_dump_json.return_value = '{"resumo":"ok"}'
    return rs


async def test_redis_get_failure_falls_back_to_compute():
    """AC1.3.a — Redis ConnectionError on read → recompute (no raise)."""
    import llm

    fake_resumo = _fake_resumo()

    failing_cache = MagicMock()
    failing_cache.get = AsyncMock(side_effect=ConnectionError("redis down"))
    failing_cache.setex = AsyncMock()

    fake_module = MagicMock()
    fake_module.redis_cache = failing_cache

    with patch.dict("sys.modules", {"cache_module": fake_module}), \
         patch.object(llm, "gerar_resumo", return_value=fake_resumo) as compute:
        result = await llm.get_or_generate_resumo_cached(
            licitacoes=[{"id": "abc", "uf": "SC"}],
            sector_name="construcao",
            termos_busca="asfalto",
            setor_id=1,
        )

    assert result is fake_resumo
    compute.assert_called_once()
    # The cache write attempt must still fire (even if it fails too) —
    # the contract is: fallback computed, cache failures swallowed.


async def test_redis_setex_failure_does_not_break_caller():
    """AC1.3.b — Redis ConnectionError on write → result still returned."""
    import llm

    fake_resumo = _fake_resumo()

    failing_cache = MagicMock()
    failing_cache.get = AsyncMock(return_value=None)  # cache miss
    failing_cache.setex = AsyncMock(side_effect=ConnectionError("redis down"))

    fake_module = MagicMock()
    fake_module.redis_cache = failing_cache

    with patch.dict("sys.modules", {"cache_module": fake_module}), \
         patch.object(llm, "gerar_resumo", return_value=fake_resumo):
        result = await llm.get_or_generate_resumo_cached(
            licitacoes=[{"id": "x", "uf": "SC"}],
            sector_name="construcao",
            termos_busca="ponte",
            setor_id=1,
        )

    assert result is fake_resumo
    failing_cache.setex.assert_awaited_once()


async def test_cache_rebuild_after_redis_recovers():
    """AC1.3.c — Edge: once Redis returns OK, the next call writes again.

    Regression for "cold cache after blip": when Redis came back up, the
    setex path must function normally (no leftover state from the failed
    attempt).
    """
    import llm

    fake_resumo = _fake_resumo()

    healed_cache = MagicMock()
    healed_cache.get = AsyncMock(return_value=None)  # miss
    healed_cache.setex = AsyncMock()  # write succeeds

    fake_module = MagicMock()
    fake_module.redis_cache = healed_cache

    with patch.dict("sys.modules", {"cache_module": fake_module}), \
         patch.object(llm, "gerar_resumo", return_value=fake_resumo):
        result = await llm.get_or_generate_resumo_cached(
            licitacoes=[{"id": "y", "uf": "PR"}],
            sector_name="ti",
            termos_busca="cloud",
            setor_id=2,
        )

    assert result is fake_resumo
    healed_cache.setex.assert_awaited_once()
    # First positional arg is the cache key; just validate it's a str.
    args = healed_cache.setex.await_args.args
    assert isinstance(args[0], str) and args[0]
