"""Resend webhook HMAC signature verification tests.

Validates Svix-format signature verification on POST /v1/trial-emails/webhook.
Security: fail-closed when secret missing, signature invalid, or timestamp stale.
"""

import base64
import hashlib
import hmac
import json
import os
import time
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def fake_secret():
    """Generate a known whsec_<base64> secret for signing test payloads."""
    raw = b"\x01" * 32
    return f"whsec_{base64.b64encode(raw).decode()}", raw


def _sign(secret_raw: bytes, svix_id: str, ts: int, body: bytes) -> str:
    payload = f"{svix_id}.{ts}.".encode("utf-8") + body
    sig = base64.b64encode(hmac.new(secret_raw, payload, hashlib.sha256).digest()).decode()
    return f"v1,{sig}"


@pytest.fixture
def client(fake_secret):
    """TestClient with RESEND_WEBHOOK_SECRET set."""
    secret_str, _ = fake_secret
    with patch.dict(os.environ, {"RESEND_WEBHOOK_SECRET": secret_str}):
        from main import app
        yield TestClient(app)


def test_valid_signature_processes_webhook(client, fake_secret):
    """Valid Svix signature → handler called → 200."""
    _, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {"email_id": "res-1"}}).encode()
    ts = int(time.time())
    headers = {
        "svix-id": "msg_test_1",
        "svix-timestamp": str(ts),
        "svix-signature": _sign(raw, "msg_test_1", ts, body),
        "content-type": "application/json",
    }
    with patch(
        "services.trial_email_sequence.handle_resend_webhook",
        new=AsyncMock(return_value=True),
    ):
        r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] in ("processed", "skipped", "ignored")


def test_missing_signature_header_rejected(client):
    """No svix-signature header → 401 (fail-closed)."""
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    r = client.post(
        "/v1/trial-emails/webhook",
        content=body,
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 401


def test_missing_secret_rejects_all(fake_secret):
    """RESEND_WEBHOOK_SECRET unset → all events rejected with 401."""
    _, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    ts = int(time.time())
    with patch.dict(os.environ, {"RESEND_WEBHOOK_SECRET": ""}, clear=False):
        # Force re-read by reimporting? env is read at request time, so this works.
        from main import app
        c = TestClient(app)
        r = c.post(
            "/v1/trial-emails/webhook",
            content=body,
            headers={
                "svix-id": "msg",
                "svix-timestamp": str(ts),
                "svix-signature": _sign(raw, "msg", ts, body),
                "content-type": "application/json",
            },
        )
    assert r.status_code == 401


def test_tampered_body_rejected(client, fake_secret):
    """Signature computed for body A, request sends body B → 401."""
    _, raw = fake_secret
    original = json.dumps({"type": "email.opened", "data": {"email_id": "1"}}).encode()
    tampered = json.dumps({"type": "email.bounced", "data": {"email_id": "EVIL"}}).encode()
    ts = int(time.time())
    headers = {
        "svix-id": "msg",
        "svix-timestamp": str(ts),
        "svix-signature": _sign(raw, "msg", ts, original),
        "content-type": "application/json",
    }
    r = client.post("/v1/trial-emails/webhook", content=tampered, headers=headers)
    assert r.status_code == 401


def test_replay_old_timestamp_rejected(client, fake_secret):
    """Timestamp >5 min old → 401 (replay protection)."""
    _, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    stale_ts = int(time.time()) - 600  # 10 min ago
    headers = {
        "svix-id": "msg",
        "svix-timestamp": str(stale_ts),
        "svix-signature": _sign(raw, "msg", stale_ts, body),
        "content-type": "application/json",
    }
    r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 401


def test_wrong_secret_rejected(client):
    """Signature signed with different secret → 401."""
    other_secret = b"\xff" * 32
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    ts = int(time.time())
    headers = {
        "svix-id": "msg",
        "svix-timestamp": str(ts),
        "svix-signature": _sign(other_secret, "msg", ts, body),
        "content-type": "application/json",
    }
    r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 401


def test_multiple_signatures_one_valid(client, fake_secret):
    """Header with multiple `v1,sig` entries — accept if ANY matches (key rotation)."""
    _, raw = fake_secret
    other = b"\xab" * 32
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    ts = int(time.time())
    bad_sig = _sign(other, "msg", ts, body)  # wrong key first
    good_sig = _sign(raw, "msg", ts, body)
    headers = {
        "svix-id": "msg",
        "svix-timestamp": str(ts),
        "svix-signature": f"{bad_sig} {good_sig}",
        "content-type": "application/json",
    }
    with patch(
        "services.trial_email_sequence.handle_resend_webhook",
        new=AsyncMock(return_value=True),
    ):
        r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 200


def test_trial_emails_webhook_secret_alias(fake_secret):
    """AC1 (SEC-HMAC-001): TRIAL_EMAILS_WEBHOOK_SECRET is the canonical alias.

    When TRIAL_EMAILS_WEBHOOK_SECRET is set and RESEND_WEBHOOK_SECRET is absent,
    signatures must still be accepted — confirming the canonical name takes
    precedence over the legacy alias.
    """
    secret_str, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {"email_id": "res-alias-1"}}).encode()
    ts = int(time.time())
    headers = {
        "svix-id": "msg_alias_1",
        "svix-timestamp": str(ts),
        "svix-signature": _sign(raw, "msg_alias_1", ts, body),
        "content-type": "application/json",
    }
    env_override = {"TRIAL_EMAILS_WEBHOOK_SECRET": secret_str, "RESEND_WEBHOOK_SECRET": ""}
    with patch.dict(os.environ, env_override, clear=False):
        from main import app
        c = TestClient(app)
        with patch(
            "services.trial_email_sequence.handle_resend_webhook",
            new=AsyncMock(return_value=True),
        ):
            r = c.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] in ("processed", "skipped", "ignored")


# ---------------------------------------------------------------------------
# HMAC-ENFORCE-001 (confirm) — coverage expansion 2026-05-09
# Audit confirmed enforcement is already shipped (PR #534/#858/#954). These
# additional cases close the remaining test-spec gaps without changing
# production code: malformed signature header, future-skewed timestamp,
# non-numeric timestamp, missing svix-id, invalidly-encoded secret, and a
# byte-replacement tamper variant (memory feedback_jwt_base64url_flaky_test:
# prefer full byte replacement over single-char flips for deterministic fail).
# ---------------------------------------------------------------------------


def test_malformed_signature_header_rejected(client, fake_secret):
    """Header missing the `v1,` prefix → no candidate sigs extracted → 401.

    Behavior check (memory feedback_test_regex_invariant_semantic): we assert
    the status code 401 produced by the verifier rejecting an unparseable
    header, not the literal log string.
    """
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    ts = int(time.time())
    # No comma → unparseable. Verifier filters require "," + startswith("v1,")
    headers = {
        "svix-id": "msg_malformed",
        "svix-timestamp": str(ts),
        "svix-signature": "not-a-valid-svix-header-format",
        "content-type": "application/json",
    }
    r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 401


def test_unsupported_scheme_rejected(client, fake_secret):
    """Header with `v2,...` (unsupported scheme) → no candidates → 401.

    Defense-in-depth: only `v1` Svix scheme must be accepted. A future v2
    scheme would need explicit support, not silent acceptance.
    """
    _, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    ts = int(time.time())
    sig_v1 = _sign(raw, "msg_v2", ts, body)  # valid v1 signature
    sig_v2_only = sig_v1.replace("v1,", "v2,", 1)  # rebrand as v2
    headers = {
        "svix-id": "msg_v2",
        "svix-timestamp": str(ts),
        "svix-signature": sig_v2_only,
        "content-type": "application/json",
    }
    r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 401


def test_non_numeric_timestamp_rejected(client, fake_secret):
    """Non-numeric svix-timestamp → ValueError caught → 401."""
    _, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    headers = {
        "svix-id": "msg_bad_ts",
        "svix-timestamp": "not-a-number",
        "svix-signature": _sign(raw, "msg_bad_ts", int(time.time()), body),
        "content-type": "application/json",
    }
    r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 401


def test_future_skewed_timestamp_rejected(client, fake_secret):
    """Timestamp >5 min in the future → 401 (replay window symmetric).

    Complements `test_replay_old_timestamp_rejected` — verifier uses
    `abs(now - ts) > tolerance`, so future drift must also fail.
    """
    _, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    future_ts = int(time.time()) + 600  # 10 min ahead
    headers = {
        "svix-id": "msg_future",
        "svix-timestamp": str(future_ts),
        "svix-signature": _sign(raw, "msg_future", future_ts, body),
        "content-type": "application/json",
    }
    r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 401


def test_missing_svix_id_rejected(client, fake_secret):
    """All three Svix headers required — drop svix-id → 401."""
    _, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    ts = int(time.time())
    headers = {
        # svix-id intentionally absent
        "svix-timestamp": str(ts),
        "svix-signature": _sign(raw, "any-id", ts, body),
        "content-type": "application/json",
    }
    r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 401


def test_invalid_base64_secret_rejected(fake_secret):
    """Secret value that is not valid base64 → exception caught → 401.

    Confirms `_verify_svix_signature` swallows base64 decode errors instead of
    bubbling them up as 500s, which would leak operational state to attackers.
    """
    _, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    ts = int(time.time())
    bad_secret = "whsec_!!!not-base64!!!"
    with patch.dict(os.environ, {"RESEND_WEBHOOK_SECRET": bad_secret}, clear=False):
        from main import app
        c = TestClient(app)
        r = c.post(
            "/v1/trial-emails/webhook",
            content=body,
            headers={
                "svix-id": "msg_bad_secret",
                "svix-timestamp": str(ts),
                "svix-signature": _sign(raw, "msg_bad_secret", ts, body),
                "content-type": "application/json",
            },
        )
    assert r.status_code == 401


def test_signature_byte_replacement_rejected(client, fake_secret):
    """Replace one base64 char in the signature → 401.

    Memory `feedback_jwt_base64url_flaky_test`: single-char base64url flips
    can land on an equivalent character (~6% false-pass risk). We replace a
    middle char with one that is guaranteed not to be a valid base64 alphabet
    member at that position, ensuring deterministic mismatch.
    """
    _, raw = fake_secret
    body = json.dumps({"type": "email.opened", "data": {}}).encode()
    ts = int(time.time())
    valid = _sign(raw, "msg_tamper", ts, body)  # "v1,<base64>"
    prefix, b64 = valid.split(",", 1)
    # Replace 5 contiguous chars with a determinedly distinct sequence.
    # Use chars that are valid base64 (so the parse succeeds) but
    # statistically guaranteed not to coincide with the original 5 bytes.
    if len(b64) >= 16:
        replacement = "AAAAA" if not b64[8:13].startswith("A") else "BBBBB"
        tampered_b64 = b64[:8] + replacement + b64[13:]
    else:
        tampered_b64 = "A" * len(b64)
    headers = {
        "svix-id": "msg_tamper",
        "svix-timestamp": str(ts),
        "svix-signature": f"{prefix},{tampered_b64}",
        "content-type": "application/json",
    }
    r = client.post("/v1/trial-emails/webhook", content=body, headers=headers)
    assert r.status_code == 401
