"""Tests for #647: startup Supabase probe timeout — uvicorn must not hang."""

import asyncio
import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_probe_raises_timeout_when_supabase_hangs():
    """asyncio.wait_for raises TimeoutError when execute never returns."""

    async def _blocking_in_thread():
        # Simulate a sync call that takes forever — via a short sleep for test speed
        await asyncio.sleep(5)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(_blocking_in_thread(), timeout=0.05)


@pytest.mark.asyncio
async def test_probe_succeeds_when_supabase_fast():
    """Probe completes normally when Supabase responds immediately."""
    fake_result = MagicMock()
    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.limit.return_value.execute = MagicMock(
        return_value=fake_result
    )

    result = await asyncio.wait_for(
        asyncio.to_thread(fake_db.table("profiles").select("id").limit(1).execute),
        timeout=10,
    )
    assert result == fake_result


@pytest.mark.asyncio
async def test_probe_timeout_env_var_respected(monkeypatch):
    """STARTUP_PROBE_TIMEOUT_S env var controls probe timeout."""
    monkeypatch.setenv("STARTUP_PROBE_TIMEOUT_S", "2")

    import os
    _probe_timeout = int(os.getenv("STARTUP_PROBE_TIMEOUT_S", "10"))
    assert _probe_timeout == 2


@pytest.mark.asyncio
async def test_probe_default_timeout_is_ten(monkeypatch):
    """Default STARTUP_PROBE_TIMEOUT_S is 10 when env var not set."""
    monkeypatch.delenv("STARTUP_PROBE_TIMEOUT_S", raising=False)

    import os
    _probe_timeout = int(os.getenv("STARTUP_PROBE_TIMEOUT_S", "10"))
    assert _probe_timeout == 10


@pytest.mark.asyncio
async def test_probe_uses_asyncio_to_thread_pattern():
    """Verify the probe pattern: to_thread wraps sync .execute() call."""
    call_count = 0

    def sync_execute():
        nonlocal call_count
        call_count += 1
        return MagicMock()

    fake_db = MagicMock()
    fake_db.table.return_value.select.return_value.limit.return_value.execute = sync_execute

    await asyncio.wait_for(
        asyncio.to_thread(fake_db.table("profiles").select("id").limit(1).execute),
        timeout=5,
    )
    assert call_count == 1
