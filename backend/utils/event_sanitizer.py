"""NETINT-005: PII sanitization for network intelligence events (LGPD Art. 6, I).

Sanitizes metadata dicts before they reach the RPC layer, removing or
redacting personally identifiable information (PII) such as CNPJ, email,
UUID, IP addresses, and known sensitive keys.

Part of the fire-and-forget event collection pipeline.
See ``backend/services/network_collector.py`` for the collector service.

Usage::

    from utils.event_sanitizer import sanitize_metadata

    clean = sanitize_metadata({"cnpj": "12.345.678/0001-90", "uf": "SP"})
    # -> {"uf": "SP"}
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Compile regexes once at module load ──────────────────────────────────────

# CNPJ: XX.XXX.XXX/XXXX-XX or 14 consecutive digits
_CNPJ_RE = re.compile(
    r"\d{2}\.\d{3}\.\d{3}\/\d{4}\-\d{2}|\d{14}"
)

# Basic email: local-part@domain.tld
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)

# UUID v4 — hex with dashes
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

# IPv4 address
_IP_RE = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
)

# Known sensitive keys (case-insensitive match on lowercase)
_SENSITIVE_KEYS = frozenset({
    "user_id", "profile_id", "email", "ip_address", "user_agent",
    "fingerprint", "cnpj", "cpf", "telefone", "celular", "phone",
    "endereco", "address", "nome", "name", "token", "session_id",
    "access_token", "refresh_token", "password", "secret",
    "authorization", "api_key", "apikey",
    "userId", "customerId", "profileId", "userid",
})


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitize a metadata dict, removing or redacting PII.

    Steps:
    1. If ``None`` or empty, return ``{}``.
    2. Remove any key whose lowercased name is in the sensitive-keys set.
    3. Remove any key ending with ``id``, ``Id``, or ``ID``.
    4. For remaining string values, redact CNPJ, email, UUID, and IP
       patterns by replacing matches with ``[REDACTED]``.
    5. Non-string values are kept as-is (ints, bools, lists are safe for
       aggregated analytics).

    Returns a *new* dict — the original is never mutated.
    """
    if not metadata:
        return {}

    clean: dict[str, Any] = {}

    for key, value in metadata.items():
        # ── Step 2: Remove known sensitive keys ───────────────────────────────
        if key.lower() in _SENSITIVE_KEYS:
            logger.debug("sanitize_metadata: removed sensitive key '%s'", key)
            continue

        # ── Step 3: Remove keys ending with 'id' (case-insensitive) ───────────
        if re.search(r"[iI][dD]$", key):
            logger.debug("sanitize_metadata: removed key ending with 'id': '%s'", key)
            continue

        # ── Step 4: Redact PII patterns in string values ──────────────────────
        if isinstance(value, str):
            cleaned_value = _redact_pii(value)
            clean[key] = cleaned_value
        else:
            clean[key] = value

    return clean


def _redact_pii(value: str) -> str:
    """Redact CNPJ, email, UUID, and IP patterns in a string.

    Each match is replaced with ``[REDACTED]``. If no pattern matches,
    the original string is returned as-is.
    """
    # Order matters: apply all redactions in sequence.
    redacted = _CNPJ_RE.sub("[REDACTED]", value)
    redacted = _EMAIL_RE.sub("[REDACTED]", redacted)
    redacted = _UUID_RE.sub("[REDACTED]", redacted)
    redacted = _IP_RE.sub("[REDACTED]", redacted)

    if redacted != value:
        logger.debug("sanitize_metadata: redacted PII in value (len=%d)", len(value))

    return redacted


def has_pii(value: str) -> bool:
    """Check if a string contains any PII pattern (CNPJ, email, UUID, IP).

    Returns ``True`` if at least one pattern matches.

    Useful for quick pre-checks before deciding to log or pass data.
    """
    if _CNPJ_RE.search(value):
        return True
    if _EMAIL_RE.search(value):
        return True
    if _UUID_RE.search(value):
        return True
    if _IP_RE.search(value):
        return True
    return False
