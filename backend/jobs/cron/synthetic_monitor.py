"""Issue #1869 — ARQ cron job for synthetic user-flow monitoring.

Runs every 15 minutes via ARQ cron (not lifespan loop). Executes a
complete user flow: auth -> busca -> results check -> viability check
-> excel generation, logs per-stage timings, and emits Prometheus metrics
and Sentry alerts on sustained failure.

State (last result, consecutive failures, run history) is stored in Redis
under the ``synthetic_monitor:`` key prefix so the admin endpoint can
serve it without a dedicated Supabase table.
"""

from __future__ import annotations

import json
import logging
import os
import time as time_mod
from typing import Any

logger = logging.getLogger(__name__)

SYNTHETIC_MONITOR_STATE_PREFIX = "synthetic_monitor:"
SYNTHETIC_MONITOR_INTERVAL_S = 15 * 60  # 15 minutes
SYNTHETIC_MONITOR_ALERT_THRESHOLD = 3  # SEV1 after N consecutive failures
SYNTHETIC_MONITOR_HISTORY_SIZE = 10
SYNTHETIC_MONITOR_TIMEOUT_S = 60  # AC3: global timeout (half of Railway 120s)
SYNTHETIC_MONITOR_SEARCH_TIMEOUT_S = 30  # AC2: search must complete in <30s


async def _get_redis() -> Any:
    """Lazy Redis pool accessor — avoids import at module load time."""
    from redis_pool import get_redis_pool
    return await get_redis_pool()


def _state_key(*parts: str) -> str:
    return SYNTHETIC_MONITOR_STATE_PREFIX + ":".join(parts)


async def _get_state(key: str) -> Any:
    redis = await _get_redis()
    if not redis:
        return None
    raw = await redis.get(_state_key(key))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


async def _set_state(key: str, value: Any, ttl: int = 86400) -> None:
    redis = await _get_redis()
    if not redis:
        return
    await redis.setex(_state_key(key), ttl, json.dumps(value, default=str))


def _get_config(key: str, default: str = "") -> str:
    return os.getenv(key, default)


async def run_synthetic_monitor(
    base_url: str | None = None,
    email: str | None = None,
    password: str | None = None,
) -> dict:
    """Execute the complete user flow, returning a result dict with timings.

    Steps:
      1. auth       — login via Supabase Auth REST API
      2. search     — POST /v1/buscar (synchronous mode)
      3. results    — verify total_bids > 0
      4. viability  — verify viability_score present in results
      5. excel      — verify excel_url present

    Each step records elapsed_ms and success/failure.  The overall flow
    is bounded by ``SYNTHETIC_MONITOR_TIMEOUT_S`` (60s — AC3); the search
    step specifically is bounded by 30s (AC2).
    """
    import httpx

    base_url = (base_url or _get_config("API_BASE_URL", "https://api.smartlic.tech")).rstrip("/")
    email = email or _get_config("SYNTHETIC_MONITOR_EMAIL", "")
    password = password or _get_config("SYNTHETIC_MONITOR_PASSWORD", "")

    if not email or not password:
        return {
            "status": "skipped",
            "error": "SYNTHETIC_MONITOR_EMAIL/PASSWORD not configured",
            "timings": {},
        }

    stages: dict[str, dict] = {}
    overall_start = time_mod.monotonic()
    overall_status = "success"

    async with httpx.AsyncClient(timeout=httpx.Timeout(SYNTHETIC_MONITOR_TIMEOUT_S)) as client:
        # ---- Step 1: Auth ----
        step_start = time_mod.monotonic()
        try:
            supabase_url = _get_config("SUPABASE_URL", "").rstrip("/")
            anon_key = _get_config("SUPABASE_ANON_KEY", "")
            if supabase_url and anon_key:
                auth_resp = await client.post(
                    f"{supabase_url}/auth/v1/token?grant_type=password",
                    headers={
                        "apikey": anon_key,
                        "Content-Type": "application/json",
                    },
                    json={"email": email, "password": password},
                )
                auth_resp.raise_for_status()
                auth_data = auth_resp.json()
                access_token = auth_data.get("access_token", "")
                stages["auth"] = {
                    "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                    "success": bool(access_token),
                }
                if not access_token:
                    stages["auth"]["error"] = "no access_token in response"
                    overall_status = "failure"
                    return {"status": overall_status, "stages": stages, "timings": {}}
            else:
                stages["auth"] = {"elapsed_ms": 0, "success": False, "error": "SUPABASE_URL/ANON_KEY not configured"}
                overall_status = "failure"
                return {"status": overall_status, "stages": stages, "timings": {}}
        except Exception as exc:
            stages["auth"] = {
                "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                "success": False,
                "error": str(exc),
            }
            overall_status = "failure"
            return {"status": overall_status, "stages": stages, "timings": {}}

        # ---- Step 2: Search (POST /v1/buscar) ----
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        step_start = time_mod.monotonic()
        try:
            search_payload = {
                "termo": "informatica",         # sector popular (AC1)
                "ufs": ["SP"],                  # AC1: busca em SP
                "modalidades": ["pregao"],      # modalidade mais comum
            }
            search_resp = await client.post(
                f"{base_url}/v1/buscar",
                headers=headers,
                json=search_payload,
                timeout=httpx.Timeout(SYNTHETIC_MONITOR_SEARCH_TIMEOUT_S),
            )
            search_elapsed = int((time_mod.monotonic() - step_start) * 1000)
            if search_resp.status_code == 202:
                # Async mode — poll for completion
                search_data = search_resp.json()
                search_id = search_data.get("search_id", "")
                # Poll status until complete or timeout
                poll_start = time_mod.monotonic()
                poll_timeout = SYNTHETIC_MONITOR_SEARCH_TIMEOUT_S
                while (time_mod.monotonic() - poll_start) < poll_timeout:
                    await asyncio_sleep(2)
                    status_resp = await client.get(
                        f"{base_url}/v1/search/{search_id}/status",
                        headers=headers,
                    )
                    if status_resp.status_code == 200:
                        status_data = status_resp.json()
                        state = status_data.get("state", "")
                        if state in ("completed", "complete"):
                            search_elapsed = int((time_mod.monotonic() - step_start) * 1000)
                            stages["search"] = {
                                "elapsed_ms": search_elapsed,
                                "success": True,
                                "search_id": search_id,
                                "state": state,
                            }
                            break
                        elif state in ("error", "failed"):
                            stages["search"] = {
                                "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                                "success": False,
                                "search_id": search_id,
                                "state": state,
                                "error": status_data.get("error", "search failed"),
                            }
                            overall_status = "failure"
                            break
                else:
                    # Timeout polling
                    stages["search"] = {
                        "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                        "success": False,
                        "search_id": search_id,
                        "error": "poll timeout",
                    }
                    overall_status = "failure"
            elif search_resp.status_code == 200:
                # Synchronous mode — results are inline
                search_data = search_resp.json()
                stages["search"] = {
                    "elapsed_ms": search_elapsed,
                    "success": True,
                    "search_id": search_data.get("search_id", ""),
                    "state": "completed",
                }
            else:
                stages["search"] = {
                    "elapsed_ms": search_elapsed,
                    "success": False,
                    "error": f"HTTP {search_resp.status_code}: {search_resp.text[:200]}",
                    "state": "error",
                }
                overall_status = "failure"
        except Exception as exc:
            stages["search"] = {
                "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                "success": False,
                "error": str(exc),
            }
            overall_status = "failure"

        # ---- Step 3: Check results > 0 (AC2) ----
        if stages.get("search", {}).get("success"):
            search_id = stages["search"].get("search_id", "")
            step_start = time_mod.monotonic()
            try:
                results_resp = await client.get(
                    f"{base_url}/v1/search/{search_id}/results",
                    headers=headers,
                )
                results_elapsed = int((time_mod.monotonic() - step_start) * 1000)
                if results_resp.status_code == 200:
                    results_data = results_resp.json()
                    total_bids = 0
                    if isinstance(results_data, dict):
                        total_bids = results_data.get("total_bids", 0) or results_data.get("total_results", 0) or len(results_data.get("results", []) or [])
                    elif isinstance(results_data, list):
                        total_bids = len(results_data)
                    stages["results"] = {
                        "elapsed_ms": results_elapsed,
                        "success": total_bids > 0,
                        "total_bids": total_bids,
                    }
                    if total_bids == 0:
                        stages["results"]["error"] = "no results returned"
                        overall_status = "degraded"
                else:
                    stages["results"] = {
                        "elapsed_ms": results_elapsed,
                        "success": False,
                        "error": f"HTTP {results_resp.status_code}",
                    }
                    overall_status = "degraded"
            except Exception as exc:
                stages["results"] = {
                    "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                    "success": False,
                    "error": str(exc),
                }
                overall_status = "degraded"

            # ---- Step 4: Check viability present (AC2) ----
            step_start = time_mod.monotonic()
            try:
                if isinstance(results_data, dict) and results_data.get("results"):
                    first_bid = results_data["results"][0] if isinstance(results_data["results"], list) else results_data["results"]
                    viability = None
                    if isinstance(first_bid, dict):
                        viability = first_bid.get("viability_score") or first_bid.get("viability") or first_bid.get("viabilidade")
                    stages["viability"] = {
                        "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                        "success": viability is not None,
                        "has_viability": viability is not None,
                    }
                    if viability is None:
                        stages["viability"]["error"] = "no viability data in first result"
                        overall_status = "degraded"
                else:
                    stages["viability"] = {
                        "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                        "success": False,
                        "error": "no results to check viability",
                    }
                    overall_status = "degraded"
            except Exception as exc:
                stages["viability"] = {
                    "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                    "success": False,
                    "error": str(exc),
                }
                overall_status = "degraded"

            # ---- Step 5: Check Excel generation (AC2) ----
            step_start = time_mod.monotonic()
            try:
                if isinstance(results_data, dict):
                    excel_url = results_data.get("excel_url") or results_data.get("relatorio_url")
                    stages["excel"] = {
                        "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                        "success": bool(excel_url),
                        "has_excel": bool(excel_url),
                    }
                    if not excel_url:
                        stages["excel"]["error"] = "no excel_url in results"
                        overall_status = "degraded"
                else:
                    stages["excel"] = {
                        "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                        "success": False,
                        "error": "no results to check excel",
                    }
                    overall_status = "degraded"
            except Exception as exc:
                stages["excel"] = {
                    "elapsed_ms": int((time_mod.monotonic() - step_start) * 1000),
                    "success": False,
                    "error": str(exc),
                }
                overall_status = "degraded"

    overall_elapsed_ms = int((time_mod.monotonic() - overall_start) * 1000)

    # Build per-stage timing list for Prometheus (AC4, AC8)
    timings = {
        stage: data.get("elapsed_ms", 0)
        for stage, data in stages.items()
    }

    result = {
        "status": overall_status,
        "queried_at": time_mod.time(),
        "overall_elapsed_ms": overall_elapsed_ms,
        "stages": stages,
        "timings": timings,
    }
    return result


async def asyncio_sleep(seconds: float) -> None:
    """Thin wrapper for testability."""
    import asyncio
    await asyncio.sleep(seconds)


async def _record_metrics(result: dict) -> None:
    """Record Prometheus metrics for this run (AC4)."""
    try:
        from metrics import _create_counter, _create_histogram

        success_counter = _create_counter(
            "synthetic_monitor_success_total",
            "Synthetic monitor run count by status",
            labelnames=["status"],
        )
        duration_histogram = _create_histogram(
            "synthetic_monitor_duration_ms",
            "Synthetic monitor per-stage duration in ms",
            labelnames=["stage"],
            buckets=[100, 500, 1000, 2000, 5000, 10000, 20000, 30000, 60000],
        )

        status = result.get("status", "failure")
        success_counter.labels(status=status).inc()

        timings = result.get("timings", {})
        for stage, elapsed_ms in timings.items():
            duration_histogram.labels(stage=stage).observe(elapsed_ms)
    except Exception:
        logger.warning("Failed to record synthetic monitor metrics", exc_info=True)


async def synthetic_monitor_job(ctx: dict) -> dict:
    """ARQ cron job entry point — runs the synthetic monitor and stores state.

    Registered in ``backend/jobs/queue/config.py`` as an ARQ cron job
    that fires every 15 minutes.

    On 3 consecutive failures (AC5), emits a Sentry SEV1 alert.
    """
    # Detect base URL from environment
    base_url = _get_config("API_BASE_URL", "https://api.smartlic.tech")

    result = await run_synthetic_monitor(base_url=base_url)

    # Record Prometheus metrics
    await _record_metrics(result)

    # Store result in Redis
    try:
        status = result.get("status", "failure")
        is_success = status == "success"

        redis = await _get_redis()
        if redis:
            # Track consecutive failures
            consec_key = "consecutive_failures"
            if is_success:
                await _set_state(consec_key, 0, ttl=86400)
            else:
                prev = await _get_state(consec_key) or 0
                new_count = prev + 1
                await _set_state(consec_key, new_count, ttl=86400)

                # AC5: SEV1 alert on 3 consecutive failures
                if new_count >= SYNTHETIC_MONITOR_ALERT_THRESHOLD:
                    try:
                        import sentry_sdk
                        sentry_sdk.capture_message(
                            f"Synthetic monitor: {new_count} consecutive failures "
                            f"(status={status}, last_error={result.get('stages', {}).get('search', {}).get('error', 'unknown')})",
                            level="error",
                        )
                        logger.error(
                            "SEV1: Synthetic monitor %d consecutive failures",
                            new_count,
                        )
                    except Exception:
                        logger.exception("Sentry not available for SEV1 alert")
                    # Reset counter after alerting to avoid infinite alerts
                    await _set_state(consec_key, 0, ttl=86400)

            # Store last result
            last_result = {
                "status": status,
                "queried_at": result.get("queried_at"),
                "overall_elapsed_ms": result.get("overall_elapsed_ms"),
                "stages": result.get("stages", {}),
                "timings": result.get("timings", {}),
            }
            await _set_state("last_result", last_result, ttl=86400)

            # Append to history (ring buffer)
            history = await _get_state("history") or []
            history.append(last_result)
            if len(history) > SYNTHETIC_MONITOR_HISTORY_SIZE:
                history = history[-SYNTHETIC_MONITOR_HISTORY_SIZE:]
            await _set_state("history", history, ttl=86400)

        logger.info(
            "Synthetic monitor: status=%s elapsed=%dms stages=%s",
            status,
            result.get("overall_elapsed_ms", 0),
            {k: v.get("success") for k, v in result.get("stages", {}).items()},
        )
    except Exception as exc:
        logger.error("Synthetic monitor state storage failed: %s", exc, exc_info=True)

    return result
