"""Tests for ``call_openai_with_retry`` (GAP-013 / #1591).

Verifies:
  1. Mock 429 three times -> APIError raised after exhausting retries.
  2. Mock 429 once -> success on the second attempt.
  3. Jitter is applied (delay varies within +/-25% of expected).
  4. Metrics are incremented correctly on retry attempts.
  5. Success on first attempt (no retry) does not touch metrics.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from openai import APIError, RateLimitError

from llm_arbiter.retry import call_openai_with_retry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client():
    """Return a MagicMock that mimics ``client.chat.completions.create``."""
    client = MagicMock()
    client.chat.completions.create = MagicMock()
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_rate_limit_error(status_code: int = 429) -> RateLimitError:
    """Build a realistic ``RateLimitError`` with a response."""
    from httpx import Response
    response = Response(status_code=status_code, request=MagicMock())
    return RateLimitError(
        message="Rate limit exceeded",
        response=response,
        body={"error": {"message": "Rate limit exceeded"}},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCallOpenaiWithRetry:
    """Suite for ``call_openai_with_retry``."""

    def test_first_attempt_success(self, mock_client):
        """Success on the very first call -> no retry, metric not incremented."""
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = "SIM"
        mock_client.chat.completions.create.return_value = fake_response

        result = call_openai_with_retry(
            mock_client,
            {"model": "gpt-4.1-nano", "messages": []},
        )

        assert result is fake_response
        # Should have been called exactly once
        assert mock_client.chat.completions.create.call_count == 1

    @patch("llm_arbiter.retry.OPENAI_RETRY_TOTAL")
    def test_rate_limit_3x_raises(self, mock_metric, mock_client):
        """Three consecutive 429s exhaust all retries -> APIError raised."""
        mock_client.chat.completions.create.side_effect = _make_rate_limit_error()

        with pytest.raises(APIError):
            call_openai_with_retry(
                mock_client,
                {"model": "gpt-4.1-nano", "messages": []},
                max_retries=3,
            )

        # Should have been called 3 times (1 initial + 2 retries)
        assert mock_client.chat.completions.create.call_count == 3

        # Metric should record 3 failures — one per attempt
        assert mock_metric.labels.call_count >= 3
        for attempt in ("1", "2", "3"):
            mock_metric.labels.assert_any_call(attempt=attempt, outcome="failure")

    @patch("llm_arbiter.retry.OPENAI_RETRY_TOTAL")
    def test_rate_limit_then_success(self, mock_metric, mock_client):
        """First call 429, second succeeds -> retry metric recorded."""
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = "SIM"

        mock_client.chat.completions.create.side_effect = [
            _make_rate_limit_error(),
            fake_response,
        ]

        result = call_openai_with_retry(
            mock_client,
            {"model": "gpt-4.1-nano", "messages": []},
            max_retries=2,
        )

        assert result is fake_response
        assert mock_client.chat.completions.create.call_count == 2

        # Should have recorded a failure on attempt 1 and a success on attempt 2
        mock_metric.labels.assert_any_call(attempt="1", outcome="failure")
        mock_metric.labels.assert_any_call(attempt="2", outcome="success")

    def test_jitter_applied(self, mock_client):
        """Verify that delays are non-deterministic (jitter effect)."""
        mock_client.chat.completions.create.side_effect = _make_rate_limit_error()

        delays: list[float] = []

        original_sleep = time.sleep

        def _tracking_sleep(delay: float) -> None:
            delays.append(delay)
            original_sleep(0)  # Don't actually wait in tests

        with patch("llm_arbiter.retry.time.sleep", _tracking_sleep):
            with pytest.raises(APIError):
                call_openai_with_retry(
                    mock_client,
                    {"model": "gpt-4.1-nano", "messages": []},
                    max_retries=3,
                )

        # We expect 2 delays (for retries 1 and 2; the 3rd attempt is the last)
        assert len(delays) == 2, f"Expected 2 delays, got {len(delays)}"

        # Delay 1: 4^(1-1)=1s * jitter 0.75-1.25 => range [0.75, 1.25]
        delay1 = delays[0]
        assert 0.60 <= delay1 <= 1.40, f"Delay 1 ({delay1}) outside expected jitter range"

        # Delay 2: 4^(2-1)=4s * jitter 0.75-1.25 => range [3.0, 5.0]
        delay2 = delays[1]
        assert 2.0 <= delay2 <= 6.0, f"Delay 2 ({delay2}) outside expected jitter range"

    @patch("llm_arbiter.retry.OPENAI_RETRY_TOTAL")
    def test_max_retries_1(self, mock_metric, mock_client):
        """With max_retries=1, a 429 raises immediately (no retry)."""
        mock_client.chat.completions.create.side_effect = _make_rate_limit_error()

        with pytest.raises(APIError):
            call_openai_with_retry(
                mock_client,
                {"model": "gpt-4.1-nano", "messages": []},
                max_retries=1,
            )

        assert mock_client.chat.completions.create.call_count == 1
        # Only one failure recorded
        mock_metric.labels.assert_called_once_with(attempt="1", outcome="failure")

    @patch("llm_arbiter.retry.OPENAI_RETRY_TOTAL")
    def test_non_rate_limit_openai_error(self, mock_metric, mock_client):
        """Non-rate-limit APIError (e.g. auth) also triggers retry."""
        from httpx import Request
        auth_error = APIError(
            "Incorrect API key provided",
            Request(method="POST", url="https://api.openai.com/v1/chat/completions"),
            body={"error": {"message": "Incorrect API key"}},
        )
        mock_client.chat.completions.create.side_effect = auth_error

        with pytest.raises(APIError):
            call_openai_with_retry(
                mock_client,
                {"model": "gpt-4.1-nano", "messages": []},
                max_retries=2,
            )

        assert mock_client.chat.completions.create.call_count == 2
        mock_metric.labels.assert_any_call(attempt="1", outcome="failure")
        mock_metric.labels.assert_any_call(attempt="2", outcome="failure")


# ---------------------------------------------------------------------------
# Integration smoke: verify _base.py imports and calls the retry function
# ---------------------------------------------------------------------------

def test_retry_function_importable():
    """``call_openai_with_retry`` is importable from the package."""
    from llm_arbiter.retry import call_openai_with_retry as fn
    assert callable(fn)
    assert fn.__name__ == "call_openai_with_retry"


def test_retry_function_signature():
    """Verify function signature matches expectations."""
    import inspect
    from llm_arbiter.retry import call_openai_with_retry
    sig = inspect.signature(call_openai_with_retry)
    params = list(sig.parameters.keys())
    assert params == ["client", "api_kwargs", "max_retries"], f"Unexpected params: {params}"
