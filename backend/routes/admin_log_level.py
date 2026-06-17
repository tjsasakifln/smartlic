"""#1814: Runtime log level toggle for admin.

POST /v1/admin/log-level -- altera log level em runtime (admin-only)
GET  /v1/admin/log-level -- retorna niveis atuais de loggers modificados

Mecanismo TTL: dict em memoria com timestamps. Background task (asyncio)
verifica a cada 30s e reverte loggers expirados.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from admin import require_admin_ops

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# In-memory state for log level overrides
# ---------------------------------------------------------------------------
# _log_level_overrides: dict[str, dict]
#   key = logger_name (e.g. "ingestion", "*" for root logger)
#   value = {
#       "original_level": int,    # nivel antes da sobrescrita
#       "current_level": int,     # nivel atual
#       "set_by": str,            # user_id que alterou
#       "set_at": str,            # ISO timestamp
#       "ttl_until": float | None,# time.monotonic() expiry
#   }
_log_level_overrides: dict[str, dict] = {}

_ROOT_LOGGER_KEY = "*"


def _resolve_logger(name: str) -> logging.Logger:
    """Resolve a logger name to a Python logger instance.

    ``*`` or empty string returns the root logger.
    """
    if name == _ROOT_LOGGER_KEY or not name:
        return logging.getLogger()
    return logging.getLogger(name)


def _level_name(level: int) -> str:
    """Convert a logging level number to its name (e.g. 10 -> 'DEBUG')."""
    name = logging.getLevelName(level)
    if isinstance(name, str):
        return name
    return f"LEVEL_{level}"


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class SetLogLevelRequest(BaseModel):
    """Request body for POST /v1/admin/log-level."""

    level: str = Field(
        ...,
        description="Log level name: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        examples=["DEBUG"],
    )
    module: str = Field(
        default="*",
        description=(
            "Logger name (e.g. 'ingestion', 'routes.search'). "
            "Use '*' or omit for root logger."
        ),
        examples=["ingestion"],
    )
    ttl_minutes: int = Field(
        default=15,
        ge=1,
        le=1440,
        description="Auto-revert after N minutes (1-1440). Default 15.",
        examples=[15],
    )


class LogLevelOverrideInfo(BaseModel):
    """Single override entry returned by GET /v1/admin/log-level."""

    logger: str
    original_level: str
    current_level: str
    set_by: str
    set_at: str
    ttl_remaining_seconds: Optional[int] = None


class LogLevelStatusResponse(BaseModel):
    """Response for GET /v1/admin/log-level."""

    overrides: list[LogLevelOverrideInfo]
    count: int


class SetLogLevelResponse(BaseModel):
    """Response for POST /v1/admin/log-level."""

    status: str
    logger: str
    original_level: str
    current_level: str
    ttl_minutes: int
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/log-level", response_model=SetLogLevelResponse)
async def set_log_level(
    body: SetLogLevelRequest,
    user: dict = Depends(require_admin_ops),
) -> SetLogLevelResponse:
    """Set a logger's level at runtime (admin-only).

    Altera o log level do *module* (ou root se omitido) para *level*.
    Apos *ttl_minutes*, reverte automaticamente ao nivel original.
    """
    user_id = str(user.get("id", "unknown"))

    # Validate level name
    level_num = getattr(logging, body.level.upper(), None)
    if not isinstance(level_num, int):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid log level: '{body.level}'. "
                f"Use one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"
            ),
        )

    log_name = body.module.strip() if body.module.strip() else _ROOT_LOGGER_KEY
    log_obj = _resolve_logger(log_name)

    # Save original level only on first override for this logger
    if log_name not in _log_level_overrides:
        original_level = log_obj.level
    else:
        original_level = _log_level_overrides[log_name]["original_level"]

    # Apply the new level
    log_obj.setLevel(level_num)

    now_iso = datetime.now(timezone.utc).isoformat()
    now_mono = time.monotonic()

    _log_level_overrides[log_name] = {
        "original_level": original_level,
        "current_level": level_num,
        "set_by": user_id,
        "set_at": now_iso,
        "ttl_until": now_mono + (body.ttl_minutes * 60) if body.ttl_minutes > 0 else None,
    }

    # Audit via structured logging
    logger.info(
        "ADMIN LOG LEVEL CHANGE -- logger=%s from=%s to=%s ttl=%dmin set_by=%s",
        log_name,
        _level_name(original_level),
        _level_name(level_num),
        body.ttl_minutes,
        user_id,
    )

    return SetLogLevelResponse(
        status="ok",
        logger=log_name,
        original_level=_level_name(original_level),
        current_level=_level_name(level_num),
        ttl_minutes=body.ttl_minutes,
        detail=(
            f"Logger '{log_name}' changed from "
            f"{_level_name(original_level)} to {_level_name(level_num)} "
            f"(reverts in {body.ttl_minutes} min)"
        ),
    )


@router.get("/log-level", response_model=LogLevelStatusResponse)
async def get_log_levels(
    user: dict = Depends(require_admin_ops),
) -> LogLevelStatusResponse:
    """Return current log level overrides (admin-only)."""
    now_mono = time.monotonic()
    overrides: list[LogLevelOverrideInfo] = []

    for log_name, state in list(_log_level_overrides.items()):
        ttl_remaining: Optional[int] = None
        if state["ttl_until"] is not None:
            remaining = int(state["ttl_until"] - now_mono)
            ttl_remaining = max(remaining, 0)

        overrides.append(LogLevelOverrideInfo(
            logger=log_name,
            original_level=_level_name(state["original_level"]),
            current_level=_level_name(state["current_level"]),
            set_by=state["set_by"],
            set_at=state["set_at"],
            ttl_remaining_seconds=ttl_remaining,
        ))

    return LogLevelStatusResponse(overrides=overrides, count=len(overrides))


# ---------------------------------------------------------------------------
# Background TTL checker (registered in startup/lifespan.py)
# ---------------------------------------------------------------------------


async def _periodic_log_level_ttl_checker() -> None:
    """Background task that checks every 30s and reverts expired overrides.

    Registered in ``startup/lifespan.py`` via TaskRegistry with
    ``is_coroutine=True``.
    """
    CHECK_INTERVAL = 30  # seconds

    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL)
            now_mono = time.monotonic()
            expired: list[str] = []

            for log_name, state in list(_log_level_overrides.items()):
                ttl_until = state.get("ttl_until")
                if ttl_until is not None and now_mono >= ttl_until:
                    expired.append(log_name)

            for log_name in expired:
                state = _log_level_overrides.pop(log_name, None)
                if state is None:
                    continue
                original_level = state["original_level"]
                log_obj = _resolve_logger(log_name)
                log_obj.setLevel(original_level)
                logger.info(
                    "ADMIN LOG LEVEL REVERT -- logger=%s from=%s to=%s (TTL expired)",
                    log_name,
                    _level_name(state["current_level"]),
                    _level_name(original_level),
                )

            if expired:
                logger.info(
                    "ADMIN LOG LEVEL TTL: Reverted %d expired override(s)",
                    len(expired),
                )

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning(
                "ADMIN LOG LEVEL TTL: Checker error: %s", e,
            )
