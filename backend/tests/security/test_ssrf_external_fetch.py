"""SEC-TEST-2026-001 — AC1: SSRF regression guard for external fetchers.

OWASP A10:2021 Server-Side Request Forgery.

Strategy (advisor-confirmed): SmartLic's PNCP/PCP/ComprasGov clients use
HARDCODED `BASE_URL` constants. There is no user-controllable URL parameter
in the fetcher surface. So we don't fuzz a non-existent input — we install
**regression guards** that fail if a future PR introduces SSRF surface:

- BASE_URL is a https:// constant pointing only at the official host.
- No env override silently overwrites BASE_URL.
- No fetcher constructor accepts a url= / base_url= kwarg.

If any of these change, this test breaks BEFORE the regression ships.

Future extension (SEC-TEST-002+): when user-supplied URL params land in
auth_oauth (`redirect_uri`), export_sheets (`spreadsheet_url`), or
intel_reports (`pdf_url`), add probes against `file://`, `http://localhost`,
and `http://169.254.169.254` (AWS IMDS).
"""

from __future__ import annotations

import inspect
import pytest


SSRF_DANGEROUS_HOSTS = (
    "file://etc/passwd",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://169.254.169.254/latest/meta-data/",  # AWS IMDS
    "http://[::1]",  # IPv6 loopback
    "gopher://localhost:6379/_FLUSHALL",  # Redis poke via gopher
)


# ──────────────────────────────────────────────────────────────────────
# Regression guards — BASE_URL is a constant
# ──────────────────────────────────────────────────────────────────────

def test_pncp_async_base_url_is_official_host():
    from clients.pncp.async_client import AsyncPNCPClient

    assert AsyncPNCPClient.BASE_URL == "https://pncp.gov.br/api/consulta/v1"
    assert AsyncPNCPClient.BASE_URL.startswith("https://pncp.gov.br")


def test_pncp_sync_base_url_is_official_host():
    from clients.pncp.sync_client import PNCPClient  # type: ignore

    assert PNCPClient.BASE_URL == "https://pncp.gov.br/api/consulta/v1"
    assert PNCPClient.BASE_URL.startswith("https://pncp.gov.br")


@pytest.mark.parametrize("dangerous", SSRF_DANGEROUS_HOSTS)
def test_pncp_base_url_is_not_dangerous(dangerous):
    from clients.pncp.async_client import AsyncPNCPClient
    from clients.pncp.sync_client import PNCPClient

    assert dangerous not in AsyncPNCPClient.BASE_URL
    assert dangerous not in PNCPClient.BASE_URL


# ──────────────────────────────────────────────────────────────────────
# Regression guards — fetcher constructors do NOT accept url override
# ──────────────────────────────────────────────────────────────────────

def test_pncp_async_client_no_url_kwarg():
    """AsyncPNCPClient.__init__ MUST NOT accept a url= or base_url= kwarg."""
    from clients.pncp.async_client import AsyncPNCPClient

    sig = inspect.signature(AsyncPNCPClient.__init__)
    forbidden = {"url", "base_url", "host", "endpoint"}
    leaked = forbidden.intersection(sig.parameters.keys())
    assert leaked == set(), (
        f"AsyncPNCPClient.__init__ exposes URL kwargs {leaked} — SSRF risk"
    )


def test_pncp_sync_client_no_url_kwarg():
    from clients.pncp.sync_client import PNCPClient

    sig = inspect.signature(PNCPClient.__init__)
    forbidden = {"url", "base_url", "host", "endpoint"}
    leaked = forbidden.intersection(sig.parameters.keys())
    assert leaked == set(), (
        f"PNCPClient.__init__ exposes URL kwargs {leaked} — SSRF risk"
    )


# ──────────────────────────────────────────────────────────────────────
# Env override safety — BASE_URL is NOT pulled from env at import time
# ──────────────────────────────────────────────────────────────────────

def test_pncp_base_url_not_env_overridable(monkeypatch):
    """Setting PNCP_BASE_URL env var MUST NOT change BASE_URL after import.

    If a future PR makes BASE_URL = os.getenv('PNCP_BASE_URL', ...), this
    test catches it on re-import.
    """
    monkeypatch.setenv("PNCP_BASE_URL", "http://attacker.example.com")
    monkeypatch.setenv("PNCP_API_URL", "http://attacker.example.com")
    monkeypatch.setenv("BASE_URL", "http://attacker.example.com")

    # Force re-import to simulate a fresh process under attacker env.
    import importlib
    import clients.pncp.async_client as ac
    import clients.pncp.sync_client as sc

    importlib.reload(ac)
    importlib.reload(sc)

    assert "attacker.example.com" not in ac.AsyncPNCPClient.BASE_URL
    assert "attacker.example.com" not in sc.PNCPClient.BASE_URL


# ──────────────────────────────────────────────────────────────────────
# Future-surface placeholder: payload library is ready when needed
# ──────────────────────────────────────────────────────────────────────

def test_ssrf_payload_library_complete():
    """Sanity: the dangerous-host list covers cloud metadata, loopback,
    file://, and gopher (Redis bypass) — these are the SEC-TEST-002 probes.
    """
    families = {
        "file": any("file://" in p for p in SSRF_DANGEROUS_HOSTS),
        "loopback_v4": any("127.0.0.1" in p or "localhost" in p for p in SSRF_DANGEROUS_HOSTS),
        "loopback_v6": any("[::1]" in p for p in SSRF_DANGEROUS_HOSTS),
        "imds": any("169.254.169.254" in p for p in SSRF_DANGEROUS_HOSTS),
        "gopher": any("gopher://" in p for p in SSRF_DANGEROUS_HOSTS),
    }
    missing = [k for k, v in families.items() if not v]
    assert not missing, f"SSRF payload library missing families: {missing}"
