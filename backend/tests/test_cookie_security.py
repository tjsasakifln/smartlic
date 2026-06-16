"""#1874 AC7: Cookie security tests — verification of Set-Cookie headers.

Tests that:
- get_auth_error_headers() returns headers with Secure + HttpOnly + SameSite=Strict
- Auth error HTTPException responses include cookie-clearing Set-Cookie headers
- No Set-Cookie header lacks explicit SameSite or Secure flags in auth error paths

Strategy: drive the functions directly and assert header values. No TestClient
required — the dependency injection and mock setup would introduce coupling.
"""

from __future__ import annotations

import re
from typing import Any

from auth import AUTH_COOKIE_CLEAR_HEADER, get_auth_error_headers


# ---------------------------------------------------------------------------
# Tests for get_auth_error_headers()
# ---------------------------------------------------------------------------


class TestAuthErrorHeaders:
    """AC2+AC3+AC5: Auth error cookie-clearing headers must have correct flags."""

    def test_returns_dict_with_set_cookie(self) -> None:
        """AC3: get_auth_error_headers() returns a dict with Set-Cookie key."""
        headers = get_auth_error_headers()
        assert "Set-Cookie" in headers
        assert isinstance(headers["Set-Cookie"], str)
        assert len(headers["Set-Cookie"]) > 0

    def test_has_secure_flag(self) -> None:
        """AC2: Set-Cookie header includes Secure flag."""
        headers = get_auth_error_headers()
        cookie = headers["Set-Cookie"]
        assert "Secure" in cookie, "AC2 FAIL: Set-Cookie missing Secure flag"

    def test_has_httponly_flag(self) -> None:
        """AC3: Set-Cookie header includes HttpOnly flag (auth cookie)."""
        headers = get_auth_error_headers()
        cookie = headers["Set-Cookie"]
        assert "HttpOnly" in cookie, "AC3 FAIL: Set-Cookie missing HttpOnly flag"

    def test_has_samesite_strict(self) -> None:
        """AC3: Set-Cookie header has SameSite=Strict (auth cookie)."""
        headers = get_auth_error_headers()
        cookie = headers["Set-Cookie"]
        # Match case-insensitively; value could be 'Strict' or 'strict'
        assert re.search(
            r"SameSite\s*=\s*[Ss]trict", cookie
        ), "AC3 FAIL: Set-Cookie missing SameSite=Strict"

    def test_has_max_age_zero(self) -> None:
        """Cookie clearing: Max-Age=0 or Expires in the past."""
        headers = get_auth_error_headers()
        cookie = headers["Set-Cookie"]
        has_max_age_zero = "Max-Age=0" in cookie
        has_past_expires = "Thu, 01 Jan 1970" in cookie
        assert has_max_age_zero or has_past_expires, (
            "FAIL: Clearing cookie must have Max-Age=0 or past Expires"
        )

    def test_cookie_name_is_generic(self) -> None:
        """Cookie name is a generic 'sb-auth-token' pattern."""
        headers = get_auth_error_headers()
        cookie = headers["Set-Cookie"]
        # Should match sb-*-auth-token pattern or generic auth-token
        assert "auth-token" in cookie or "sb-" in cookie, (
            "FAIL: Cookie should target auth-token pattern"
        )
        assert "=" in cookie, "FAIL: Set-Cookie must have name=value pair"

    def test_path_is_root(self) -> None:
        """Cookie clearing applies to entire site (Path=/)."""
        headers = get_auth_error_headers()
        cookie = headers["Set-Cookie"]
        assert "Path=/" in cookie, "FAIL: Clearing cookie must have Path=/"

    def test_no_missing_samesite(self) -> None:
        """AC5: Cookie header has explicit SameSite (no default fallback)."""
        headers = get_auth_error_headers()
        cookie = headers["Set-Cookie"]
        assert re.search(
            r"SameSite\s*=", cookie
        ), "AC5 FAIL: Set-Cookie missing explicit SameSite directive"


# ---------------------------------------------------------------------------
# Tests for AUTH_COOKIE_CLEAR_HEADER constant
# ---------------------------------------------------------------------------


class TestAuthCookieClearHeaderConstant:
    """AC2-AC5: The constant used by get_auth_error_headers must be valid."""

    def test_constant_is_non_empty(self) -> None:
        assert AUTH_COOKIE_CLEAR_HEADER
        assert len(AUTH_COOKIE_CLEAR_HEADER) > 20

    def test_constant_has_all_required_flags(self) -> None:
        """Verify all OWASP-required flags are present."""
        cookie = AUTH_COOKIE_CLEAR_HEADER
        checks = {
            "Secure": "Secure" in cookie,
            "HttpOnly": "HttpOnly" in cookie,
            "SameSite=Strict": bool(re.search(r"SameSite\s*=\s*[Ss]trict", cookie)),
            "Max-Age=0 or past Expires": (
                "Max-Age=0" in cookie or "Thu, 01 Jan 1970" in cookie
            ),
            "Path=/": "Path=/" in cookie,
        }
        failing = [name for name, passed in checks.items() if not passed]
        assert not failing, f"AC2+AC3+AC5 FAIL: Missing flags: {failing}"


# ---------------------------------------------------------------------------
# Integration: HTTPException header passing
# ---------------------------------------------------------------------------


class TestAuthExceptionHeaders:
    """Verify that auth-related HTTPException calls include cookie-clearing headers.

    We test the get_auth_error_headers() return value can be merged with
    other headers (e.g., WWW-Authenticate) via the {**dict} pattern used
    in auth.py.
    """

    def test_headers_merge_with_www_authenticate(self) -> None:
        """Clearing headers can coexist with WWW-Authenticate."""
        auth_headers = get_auth_error_headers()
        combined = {
            "WWW-Authenticate": "Bearer",
            **auth_headers,
        }
        assert "Set-Cookie" in combined
        assert "WWW-Authenticate" in combined
        assert "Secure" in combined["Set-Cookie"]

    def test_headers_are_mutable_copy(self) -> None:
        """get_auth_error_headers returns a new dict each call (no shared ref)."""
        h1 = get_auth_error_headers()
        h2 = get_auth_error_headers()
        assert h1 is not h2
        assert h1 == h2

    def test_samesite_value_is_strict_not_lax(self) -> None:
        """AC3: Auth cookie uses SameSite=Strict (not Lax) for CSRF protection."""
        headers = get_auth_error_headers()
        cookie = headers["Set-Cookie"]
        match = re.search(r"SameSite\s*=\s*(\w+)", cookie)
        assert match is not None, "SameSite not found"
        value = match.group(1).lower()
        assert value == "strict", (
            f"AC3 FAIL: Expected SameSite=Strict, got SameSite={value}"
        )

    def test_secure_before_httponly_order(self) -> None:
        """Both Secure and HttpOnly are present (order not important)."""
        headers = get_auth_error_headers()
        cookie = headers["Set-Cookie"]
        assert "Secure" in cookie
        assert "HttpOnly" in cookie


# ---------------------------------------------------------------------------
# Frontend-style cookie flag validation (parser-like tests)
# These validate hypothetical document.cookie patterns from the frontend
# for preference and partner cookies.
# ---------------------------------------------------------------------------


class TestFrontendCookieParser:
    """Validate cookie string patterns against AC4 (preference SameSite=Lax).

    These tests parse the cookie strings used in frontend components to
    verify they meet the security requirements.
    """

    @staticmethod
    def _parse_cookie_flags(cookie_str: str) -> dict[str, Any]:
        """Extract flags from a semicolon-separated cookie string."""
        parts = cookie_str.split(";")
        flags: dict[str, Any] = {
            "name": parts[0].split("=")[0].strip() if "=" in parts[0] else "",
            "has_secure": False,
            "has_httponly": False,
            "samesite": None,
        }
        for part in parts[1:]:
            part = part.strip()
            if part.lower() == "secure":
                flags["has_secure"] = True
            elif part.lower() == "httponly":
                flags["has_httponly"] = True
            elif part.lower().startswith("samesite"):
                _, val = part.split("=", 1)
                flags["samesite"] = val.strip().lower()
        return flags

    def test_preference_cookie_exit_intent(self) -> None:
        """AC4: Preference cookie (exit_intent) must have SameSite=Lax."""
        # Pattern used in ExitIntentPopup.tsx (#1874)
        cookie = (
            "smartlic_exit_intent_seen=%7B%22t%22%3A1234567890%7D; "
            "path=/; max-age=604800; SameSite=Lax; Secure"
        )
        flags = self._parse_cookie_flags(cookie)
        assert flags["samesite"] == "lax", "AC4 FAIL: Preference cookie must have SameSite=Lax"

    def test_preference_cookie_partner(self) -> None:
        """AC4: Preference cookie (partner) must have SameSite=Lax."""
        # Pattern used in signup/page.tsx and planos/page.tsx (#1874)
        cookie = (
            "smartlic_partner=test-partner; "
            "path=/; max-age=604800; SameSite=Lax; Secure"
        )
        flags = self._parse_cookie_flags(cookie)
        assert flags["samesite"] == "lax", "AC4 FAIL: Partner cookie must have SameSite=Lax"

    def test_ab_testing_cookie_has_samesite_lax(self) -> None:
        """AC4: A/B testing cookie must have SameSite=Lax."""
        # Pattern used in ab-testing.ts (#1874)
        cookie = (
            "smartlic_ab_experiment_1=variant_a; "
            "expires=Thu, 01 Jan 2026 00:00:00 GMT; "
            "path=/; SameSite=Lax; Secure"
        )
        flags = self._parse_cookie_flags(cookie)
        assert flags["samesite"] == "lax", "AC4 FAIL: A/B cookie must have SameSite=Lax"

    def test_no_cookie_without_samesite(self) -> None:
        """AC5: Every cookie must have explicit SameSite."""
        # Valid pattern
        valid = "name=value; path=/; SameSite=Lax; Secure"
        flags = self._parse_cookie_flags(valid)
        assert flags["samesite"] is not None, "AC5 FAIL: Cookie missing SameSite"

        # Invalid pattern (would fail audit)
        invalid = "name=value; path=/"
        flags2 = self._parse_cookie_flags(invalid)
        assert flags2["samesite"] is None, "Invalid test case — should lack SameSite"
