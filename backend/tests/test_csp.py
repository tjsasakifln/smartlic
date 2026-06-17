"""Issue #1913: Tests for CSP Enforced Mode.

Covers:
- Content-Security-Policy header present on API responses
- CSP_ENFORCE_MODE toggle (enforce vs report-only)
- CSP report endpoint accepts valid payloads
- CSP report endpoint rate limiting
- CSP report endpoint error handling

These tests use a minimal FastAPI app with only the SecurityHeadersMiddleware
and CSP report router to avoid the heavy imports (sentry_sdk, etc.) that hang
when sentry_sdk is not configured.
"""

import pytest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware import SecurityHeadersMiddleware
from routes.csp_report import router as csp_report_router


@pytest.fixture
def client():
    """Create a minimal FastAPI TestClient with only CSP-related middleware/route."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(csp_report_router)
    # Add a simple health endpoint
    @app.get("/health")
    async def health():
        return {"status": "ok"}
    return TestClient(app)


def _make_csp_report_body(
    document_uri: str = "https://smartlic.tech/api",
    violated_directive: str = "script-src 'self'",
    blocked_uri: str = "https://evil.com/script.js",
    disposition: str = "enforce",
    wrap_legacy: bool = True,
) -> dict:
    """Build a CSP violation report body.

    If *wrap_legacy* is True, wraps in {"csp-report": {...}} per legacy
    report-uri format. Otherwise returns top-level fields (Reporting API v1).
    """
    report = {
        "document-uri": document_uri,
        "violated-directive": violated_directive,
        "blocked-uri": blocked_uri,
        "disposition": disposition,
        "source-file": "https://smartlic.tech/app.js",
        "line-number": 42,
        "column-number": 10,
        "script-sample": "alert(1)",
    }
    if wrap_legacy:
        return {"csp-report": report}
    return report


class TestSecurityHeadersMiddleware:
    """Tests for CSP header in SecurityHeadersMiddleware."""

    def test_csp_header_present(self, client: TestClient):
        """AC: CSP header is present on API responses."""
        resp = client.get("/health")
        # The header should be present (either enforce or report-only)
        has_csp = (
            "Content-Security-Policy" in resp.headers
            or "Content-Security-Policy-Report-Only" in resp.headers
        )
        assert has_csp, "CSP header must be present on API responses"

    def test_csp_header_contains_report_uri(self, client: TestClient):
        """AC: CSP report-uri points to /v1/csp-report."""
        resp = client.get("/health")
        csp = resp.headers.get("Content-Security-Policy", "")
        csp_ro = resp.headers.get("Content-Security-Policy-Report-Only", "")
        combined = csp + csp_ro
        assert "/v1/csp-report" in combined, (
            "CSP directive must include report-uri /v1/csp-report"
        )

    def test_report_to_header_present(self, client: TestClient):
        """AC: Report-To header is present with csp-endpoint group."""
        resp = client.get("/health")
        report_to = resp.headers.get("Report-To", "")
        assert "csp-endpoint" in report_to, (
            "Report-To header must define csp-endpoint group"
        )
        assert "/v1/csp-report" in report_to, (
            "Report-To must point to /v1/csp-report endpoint"
        )

    @patch("config.features.CSP_ENFORCE_MODE", True)
    def test_csp_enforce_mode_true(self, client: TestClient):
        """AC: When CSP_ENFORCE_MODE=true, header is Content-Security-Policy."""
        resp = client.get("/health")
        assert "Content-Security-Policy" in resp.headers, (
            "Must use Content-Security-Policy (enforce) when CSP_ENFORCE_MODE=true"
        )
        enforce_header = resp.headers.get("Content-Security-Policy", "")
        assert "default-src 'none'" in enforce_header, (
            "Enforce CSP must contain default-src 'none'"
        )
        # When enforced, report-only should NOT be present
        assert "Content-Security-Policy-Report-Only" not in resp.headers, (
            "Report-Only should not be present in enforce mode"
        )

    @patch("config.features.CSP_ENFORCE_MODE", False)
    def test_csp_report_only_mode(self, client: TestClient):
        """AC: When CSP_ENFORCE_MODE=false, header is Content-Security-Policy-Report-Only."""
        resp = client.get("/health")
        csp_ro = resp.headers.get("Content-Security-Policy-Report-Only", "")
        assert csp_ro, (
            "Must use Content-Security-Policy-Report-Only when CSP_ENFORCE_MODE=false"
        )
        assert "default-src 'none'" in csp_ro, (
            "Report-only CSP must contain default-src 'none'"
        )
        # When report-only, enforce should NOT be present
        assert "Content-Security-Policy" not in resp.headers, (
            "Content-Security-Policy should not be present in report-only mode"
        )


class TestCspReportEndpoint:
    """Tests for POST /v1/csp-report."""

    def test_accept_legacy_format(self, client: TestClient):
        """AC: Accepts legacy report-uri format (wrapped in csp-report key)."""
        body = _make_csp_report_body(wrap_legacy=True)
        resp = client.post("/v1/csp-report", json=body)
        assert resp.status_code == 204, (
            "Legacy format should return 204 No Content"
        )

    def test_accept_reporting_api_format(self, client: TestClient):
        """AC: Accepts Reporting API v1 format (top-level fields)."""
        body = _make_csp_report_body(wrap_legacy=False)
        resp = client.post("/v1/csp-report", json=body)
        assert resp.status_code == 204, (
            "Reporting API format should return 204 No Content"
        )

    def test_reject_invalid_json(self, client: TestClient):
        """AC: Returns 400 for invalid JSON body."""
        resp = client.post(
            "/v1/csp-report",
            content=b"not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 400, (
            "Invalid JSON should return 400"
        )

    def test_rate_limit_exceeded(self, client: TestClient):
        """AC: Rate limits after 30 requests per IP."""
        # Reset rate limiter state
        from routes.csp_report import _reports
        _reports.clear()

        test_ip = "192.168.1.1"
        # Send 30 requests (should all succeed)
        for i in range(30):
            body = _make_csp_report_body(
                document_uri=f"https://test.com/page-{i}",
                wrap_legacy=True,
            )
            resp = client.post(
                "/v1/csp-report",
                json=body,
                headers={"X-Forwarded-For": test_ip},
            )
            assert resp.status_code == 204, (
                f"Request {i+1}/30 should succeed, got {resp.status_code}"
            )

        # 31st should be rate limited
        body = _make_csp_report_body()
        resp = client.post(
            "/v1/csp-report",
            json=body,
            headers={"X-Forwarded-For": test_ip},
        )
        assert resp.status_code == 429, (
            "31st request should be rate limited (429)"
        )

    def test_rate_limit_different_ips_independent(self, client: TestClient):
        """AC: Different IPs have independent rate limit counters."""
        from routes.csp_report import _reports
        _reports.clear()

        ip1 = "10.0.0.1"
        ip2 = "10.0.0.2"

        # IP1 sends 25 requests
        for i in range(25):
            resp = client.post(
                "/v1/csp-report",
                json=_make_csp_report_body(wrap_legacy=True),
                headers={"X-Forwarded-For": ip1},
            )
            assert resp.status_code == 204

        # IP2 should not be affected
        resp = client.post(
            "/v1/csp-report",
            json=_make_csp_report_body(wrap_legacy=True),
            headers={"X-Forwarded-For": ip2},
        )
        assert resp.status_code == 204, (
            "IP2 should not be rate limited by IP1's requests"
        )
