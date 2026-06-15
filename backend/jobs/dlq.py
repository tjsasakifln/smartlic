"""ARQ Dead Letter Queue — preserve failed jobs instead of discarding them.

When an ARQ job exhausts all retries (max_tries reached), the job is silently
discarded with no forensic record. This module provides a Redis-backed DLQ
that preserves the failed job's payload, error message, and traceback for
admin inspection, manual retry, and bulk purge.

Storage layout (Redis):
    arq:dlq:{job_name}  — LIST of JSON objects, each with a unique ``uuid``,
                          ``payload``, ``error``, ``traceback``, ``enqueued_at``.
    TTL: ARQ_DLQ_TTL_DAYS (default 7 days) set on every key after each push.

Usage:
    from jobs.dlq import enqueue_dlq, get_dlq_jobs, retry_dlq_job, purge_dlq
"""

from __future__ import annotations

import json
import logging
import os
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DLQ_TTL_DAYS: int = int(os.getenv("ARQ_DLQ_TTL_DAYS", "7"))
"""TTL in days for DLQ entries (default 7). Set to 0 for no expiry."""

DLQ_PREFIX: str = "arq:dlq"
"""Redis key prefix for Dead Letter Queue entries."""

_DLQ_TTL_SECONDS: int = DLQ_TTL_DAYS * 86400 if DLQ_TTL_DAYS > 0 else 0


# ---------------------------------------------------------------------------
# Core DLQ operations
# ---------------------------------------------------------------------------


async def enqueue_dlq(
    job_name: str,
    payload: dict,
    error: str,
    traceback: str,
) -> None:
    """Save a failed job to the Dead Letter Queue.

    Args:
        job_name: Name of the ARQ job function (e.g. ``"llm_summary_job"``).
        payload: Serialisable dict of the job arguments.
        error: Exception message string.
        traceback: Full formatted traceback string.

    The entry is pushed onto ``arq:dlq:{job_name}`` LIST and its TTL is
    refreshed to ``ARQ_DLQ_TTL_DAYS``.  If Redis is unavailable the failure
    is logged at WARNING level but **not** re-raised — the DLQ degrades
    gracefully.
    """
    from redis_pool import get_redis_pool

    redis = await get_redis_pool()
    if redis is None:
        logger.warning(
            "Redis unavailable — DLQ entry dropped: job=%s error=%.200s",
            job_name,
            error,
        )
        return

    entry = {
        "uuid": str(_uuid.uuid4()),
        "job_name": job_name,
        "payload": payload,
        "error": error[:2000],
        "traceback": traceback[:5000],
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    }

    key = f"{DLQ_PREFIX}:{job_name}"
    try:
        await redis.lpush(key, json.dumps(entry, default=str))
        if _DLQ_TTL_SECONDS > 0:
            await redis.expire(key, _DLQ_TTL_SECONDS)
        logger.warning(
            "DLQ: job=%s uuid=%s enqueued (TTL=%dd, error=%.100s)",
            job_name,
            entry["uuid"],
            DLQ_TTL_DAYS,
            error,
        )

        try:
            from metrics import DLQ_ENQUEUED_TOTAL
            DLQ_ENQUEUED_TOTAL.inc()
        except Exception:
            pass

    except Exception as exc:
        logger.error(
            "DLQ: failed to persist entry job=%s uuid=%s: %s",
            job_name,
            entry["uuid"],
            exc,
        )


async def get_dlq_jobs(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent entries across all DLQ keys.

    Iterates every ``arq:dlq:*`` key in Redis, pulls up-to *limit* entries
    per key, and returns them sorted by ``enqueued_at`` descending (most
    recent first).

    Args:
        limit: Maximum number of entries to return (default 50).

    Returns:
        List of dicts with keys: uuid, job_name, payload, error, traceback,
        enqueued_at, dlq_key.  Empty list if Redis is unavailable.
    """
    from redis_pool import get_redis_pool

    redis = await get_redis_pool()
    if redis is None:
        return []

    jobs: list[dict[str, Any]] = []
    try:
        cursor = 0
        pattern = f"{DLQ_PREFIX}:*"
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                entries = await redis.lrange(key, 0, limit - 1)
                for raw in entries:
                    try:
                        data: dict[str, Any] = json.loads(raw)
                        data.setdefault("dlq_key", key)
                        jobs.append(data)
                    except json.JSONDecodeError:
                        continue
            if cursor == 0:
                break
    except Exception as exc:
        logger.error("DLQ: failed to list jobs: %s", exc)
        return []

    jobs.sort(key=lambda x: x.get("enqueued_at", ""), reverse=True)
    return jobs[:limit]


async def retry_dlq_job(dlq_uuid: str) -> bool:
    """Re-enqueue a single DLQ entry back into the ARQ job queue.

    Scans all ``arq:dlq:*`` keys for an entry whose ``uuid`` matches
    *dlq_uuid*, removes it from the DLQ, and enqueues it via
    :func:`job_queue.enqueue_job`.

    Args:
        dlq_uuid: The UUID of the entry to retry (returned by
            :func:`get_dlq_jobs`).

    Returns:
        True if the entry was found and re-enqueued; False if not found or
        if Redis / ARQ is unavailable.
    """
    from redis_pool import get_redis_pool
    from jobs.queue.definitions import enqueue_job

    redis = await get_redis_pool()
    if redis is None:
        return False

    try:
        cursor = 0
        pattern = f"{DLQ_PREFIX}:*"
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
            for key in keys:
                entries = await redis.lrange(key, 0, -1)
                for idx, raw in enumerate(entries):
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if data.get("uuid") == dlq_uuid:
                        removed = await redis.lrem(key, 1, raw)
                        if removed == 0:
                            logger.warning(
                                "DLQ: retry race — entry uuid=%s vanished from %s",
                                dlq_uuid,
                                key,
                            )
                            return False

                        job_name = data.get("job_name", "")
                        payload = data.get("payload", {}) or {}

                        if isinstance(payload, dict) and payload:
                            job = await enqueue_job(job_name, **payload)
                        else:
                            job = await enqueue_job(job_name)

                        if job:
                            logger.info(
                                "DLQ: retried job=%s uuid=%s arq_id=%s",
                                job_name,
                                dlq_uuid,
                                job.job_id,
                            )
                        else:
                            logger.warning(
                                "DLQ: enqueue_job returned None for retry "
                                "job=%s uuid=%s",
                                job_name,
                                dlq_uuid,
                            )

                        try:
                            from metrics import DLQ_RETRIED_TOTAL
                            DLQ_RETRIED_TOTAL.inc()
                        except Exception:
                            pass

                        return True
            if cursor == 0:
                break
    except Exception as exc:
        logger.error("DLQ: retry failed for uuid=%s: %s", dlq_uuid, exc)

    logger.warning("DLQ: entry uuid=%s not found in any DLQ key", dlq_uuid)
    return False


async def purge_dlq() -> int:
    """Delete *all* DLQ entries from Redis.

    Returns:
        Number of Redis keys deleted (each ``arq:dlq:{job_name}`` LIST counts
        as one key).
    """
    from redis_pool import get_redis_pool

    redis = await get_redis_pool()
    if redis is None:
        return 0

    deleted = 0
    try:
        cursor = 0
        pattern = f"{DLQ_PREFIX}:*"
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
            if keys:
                await redis.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
    except Exception as exc:
        logger.error("DLQ: purge failed: %s", exc)
        return deleted

    logger.info("DLQ: purged %d keys", deleted)

    try:
        from metrics import DLQ_SIZE
        DLQ_SIZE.set(0)
    except Exception:
        pass

    return deleted


# ---------------------------------------------------------------------------
# ARQ worker integration — on_job_failure hook
# ---------------------------------------------------------------------------


async def arq_on_job_failure(ctx: dict, job: Any, exc: BaseException) -> None:
    """ARQ ``on_job_failure`` callback — enqueue failed job to DLQ.

    Intended to be set as ``on_job_failure`` in
    :class:`jobs.queue.config.WorkerSettings`.  Captures the job's function
    name, arguments, and exception details, then persists them to the Redis
    DLQ.

    The callback is best-effort: enqueue failures are logged but never
    re-raised (ensuring the ARQ worker's own error handling is not disrupted).
    """
    job_name: str = getattr(job, "function", "unknown")
    job_id: str = getattr(job, "job_id", "unknown")
    job_try: int = getattr(job, "job_try", 0)
    max_tries: int = getattr(job, "max_tries", 1)
    args: tuple = getattr(job, "args", ())
    kwargs: dict = getattr(job, "kwargs", {})

    error_str = f"{type(exc).__name__}: {exc}"
    import traceback as _tb

    tb_str = _tb.format_exc()

    # Build a serialisable payload from the job arguments
    payload: dict = {"_args": list(args)}
    if kwargs:
        payload.update(kwargs)
    payload["_job_id"] = job_id
    payload["_job_try"] = job_try
    payload["_max_tries"] = max_tries

    logger.warning(
        "ARQ on_job_failure: job=%s id=%s try=%d/%d error=%.200s",
        job_name,
        job_id,
        job_try,
        max_tries,
        error_str,
    )

    await enqueue_dlq(
        job_name=job_name,
        payload=payload,
        error=error_str,
        traceback=tb_str,
    )
