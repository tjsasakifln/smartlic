"""Exponential backoff + jitter retry for OpenAI API calls (GAP-013 / #1591).

Provides ``call_openai_with_retry`` which wraps ``client.chat.completions.create``
with a 3-attempt retry loop:

  1st retry: 1s +/-25%
  2nd retry: 4s +/-25%
  3rd retry: 16s +/-25% (if a fourth attempt were made)

After all retries are exhausted the last ``APIError`` is re-raised so the
caller can apply its own fallback logic (e.g. PENDING_REVIEW in the arbiter).
Retry attempts and outcomes are recorded as Prometheus metrics.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from openai import APIError

from metrics import OPENAI_RETRY_TOTAL

logger = logging.getLogger(__name__)


def call_openai_with_retry(
    client: Any,
    api_kwargs: dict[str, Any],
    max_retries: int = 3,
) -> Any:
    """Call ``client.chat.completions.create(**api_kwargs)`` with retry.

    Parameters
    ----------
    client : OpenAI (or async stub)
        Any object that exposes ``client.chat.completions.create(**kwargs)``.
    api_kwargs : dict
        Keyword arguments forwarded to ``chat.completions.create``.
    max_retries : int
        Maximum number of attempts (default 3). Each failed attempt waits
        ``4 ** (attempt - 1)`` seconds with +/-25% jitter before retrying.

    Returns
    -------
    The raw response from ``chat.completions.create``.

    Raises
    ------
    openai.APIError
        The last error encountered if all retries are exhausted.

    Notes
    -----
    - The ``client`` parameter is intentionally loosely typed to support both
      the sync ``OpenAI`` and async ``AsyncOpenAI`` clients; callers are
      responsible for passing the correct variant.
    - This function is **synchronous** (blocks with ``time.sleep``). It
      mirrors the existing sync call pattern in ``strategies/_base.py``.
    """
    last_error: APIError | None = None

    for attempt in range(1, max_retries + 1):
        try:
            result = client.chat.completions.create(**api_kwargs)
            if attempt > 1:
                OPENAI_RETRY_TOTAL.labels(
                    attempt=str(attempt), outcome="success"
                ).inc()
            return result
        except APIError as e:
            last_error = e
            OPENAI_RETRY_TOTAL.labels(
                attempt=str(attempt), outcome="failure"
            ).inc()

            if attempt == max_retries:
                break

            # Exponential backoff: 4^(attempt-1) seconds with +/-25% jitter
            delay = (4 ** (attempt - 1)) * random.uniform(0.75, 1.25)
            logger.warning(
                f"OpenAI API error (attempt {attempt}/{max_retries}): "
                f"retrying in {delay:.1f}s -- {e}"
            )
            time.sleep(delay)

    # All retries exhausted -- re-raise the last error so the caller can
    # apply its own fallback (PENDING_REVIEW, hard REJECT, ...).
    raise last_error  # type: ignore[misc]  # last_error is set if we reach here
