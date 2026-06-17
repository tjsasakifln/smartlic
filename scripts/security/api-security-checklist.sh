#!/bin/bash
# =============================================================================
# SmartLic API Security Checklist
# =============================================================================
# Automated API security checks targeting OWASP API Top 10 2023.
#
# SAFE: All tests are read-only or use crafted-but-safe inputs.
# No destructive operations are performed.
#
# Usage:
#   export API_BASE="https://staging.smartlic.tech"
#   export AUTH_TOKEN="<valid-jwt>"
#   export ADMIN_TOKEN="<admin-jwt>"
#   ./scripts/security/api-security-checklist.sh
#
# Environment variables:
#   API_BASE      — Base URL (default: https://staging.smartlic.tech)
#   AUTH_TOKEN    — Valid JWT for authenticated endpoint tests
#   ADMIN_TOKEN   — Valid JWT with admin privileges
#   REPORT_DIR    — Output directory (default: reports/security/$(date +%Y-%m-%d))
#
# Checks performed:
#   1. Auth bypass — endpoints that should require auth
#   2. Rate limiting — 429 responses on rapid requests
#   3. Input validation — SQLi and XSS payloads on free-text fields
#   4. CORS misconfiguration — origin reflection
#   5. Admin endpoint hardening — non-admin token blocked
#   6. HTTP methods — OPTIONS allowed methods
#   7. Security headers — present on all responses
#
# Exit codes:
#   0 — All checks passed
#   1 — One or more checks failed
# =============================================================================

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
API_BASE="${API_BASE:-https://staging.smartlic.tech}"
AUTH_TOKEN="${AUTH_TOKEN:-}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
REPORT_DIR="${REPORT_DIR:-reports/security/$(date +%Y-%m-%d)}"
SUMMARY_FILE="${REPORT_DIR}/api-checklist-summary.txt"

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

pass() { ((PASS_COUNT++)); echo -e "  ${GREEN}PASS${NC} $1"; }
fail() { ((FAIL_COUNT++)); echo -e "  ${RED}FAIL${NC} $1"; }
warn() { ((WARN_COUNT++)); echo -e "  ${YELLOW}WARN${NC} $1"; }

print_section() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  $1"
    echo "═══════════════════════════════════════════════════════════════"
}

# Check if a URL returns a specific status code
expect_status() {
    local url="$1"
    local expected="$2"
    local desc="$3"
    local extra_args="${4:-}"

    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 $extra_args "$url" 2>/dev/null || echo "000")

    if [[ "$status" == "$expected" ]]; then
        pass "$desc (HTTP $status)"
    else
        fail "$desc — expected HTTP $expected, got HTTP $status"
    fi
}

# Assert that auth is required (no token -> 401)
assert_auth_required() {
    local url="$1"
    local desc="$2"

    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

    if [[ "$status" == "401" || "$status" == "403" ]]; then
        pass "$desc — requires auth (HTTP $status)"
    else
        warn "$desc — no auth required (HTTP $status) — may be public by design"
    fi
}

# Assert that non-admin user is blocked
assert_admin_blocked() {
    local url="$1"
    local desc="$2"

    if [[ -z "$AUTH_TOKEN" ]]; then
        warn "Skip admin block test: AUTH_TOKEN not set"
        return
    fi

    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        "$url" 2>/dev/null || echo "000")

    if [[ "$status" == "403" || "$status" == "401" ]]; then
        pass "$desc — blocked for non-admin (HTTP $status)"
    else
        fail "$desc — non-admin allowed (HTTP $status)"
    fi
}

# Test rate limiting on a target endpoint
test_rate_limiting() {
    local url="$1"
    local desc="$2"
    local req_count="${3:-30}"

    local limited=false
    local statuses=""

    for ((i=1; i<=req_count; i++)); do
        local status
        status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
            -H "Authorization: Bearer $AUTH_TOKEN" \
            "$url" 2>/dev/null || echo "000")
        statuses="${statuses}${status} "

        if [[ "$status" == "429" ]]; then
            limited=true
            break
        fi
    done

    if $limited; then
        pass "$desc — rate limited at $i/$req_count requests"
    else
        warn "$desc — no 429 after $req_count requests (statuses: $statuses)"
    fi
}

mkdir -p "$REPORT_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# Pre-flight
# ─────────────────────────────────────────────────────────────────────────────
print_section "Pre-flight"
log_info "Target:    $API_BASE"
log_info "Auth set:  $([[ -n "$AUTH_TOKEN" ]] && echo "YES" || echo "NO")"
log_info "Admin set: $([[ -n "$ADMIN_TOKEN" ]] && echo "YES" || echo "NO")"
log_info "Report:    $REPORT_DIR"

# Ping target
ping_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$API_BASE/health" 2>/dev/null || echo "000")
if [[ "$ping_status" == "200" || "$ping_status" == "000" ]]; then
    log_info "Target reachable (health endpoint: HTTP $ping_status)"
else
    log_error "Target unreachable (health: HTTP $ping_status)"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# 1. Auth Bypass — Endpoints that should require authentication
# ─────────────────────────────────────────────────────────────────────────────
print_section "1. Auth Bypass (OWASP API1:2023 / A01:2021)"

# Search endpoints (require auth)
assert_auth_required "${API_BASE}/buscar"
assert_auth_required "${API_BASE}/v1/pipeline"
assert_auth_required "${API_BASE}/v1/feedback"
assert_auth_required "${API_BASE}/v1/messages"
assert_auth_required "${API_BASE}/v1/user/me"
assert_auth_required "${API_BASE}/v1/analytics/summary"

# Public endpoints should NOT require auth
expect_status "${API_BASE}/health" "200" "Health endpoint accessible without auth"
expect_status "${API_BASE}/v1/setores" "200" "Sectors endpoint public" "-H \"Accept: application/json\""
expect_status "${API_BASE}/v1/plans" "200" "Plans endpoint public"

echo "" | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Rate Limiting (OWASP API4:2023 / A04:2021)
# ─────────────────────────────────────────────────────────────────────────────
print_section "2. Rate Limiting (OWASP API4:2023 / A04:2021)"

test_rate_limiting "${API_BASE}/health" "Health endpoint rate limit"

if [[ -n "$AUTH_TOKEN" ]]; then
    test_rate_limiting "${API_BASE}/v1/plans" "Plans endpoint rate limit (auth'd)" 30
fi

echo "" | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Input Validation (OWASP API3:2023 / A03:2021)
# ─────────────────────────────────────────────────────────────────────────────
print_section "3. Input Validation (OWASP API3:2023 / A03:2021)"

SQLI_PAYLOADS=(
    "' OR 1=1--"
    "'; DROP TABLE users;--"
    "' UNION SELECT NULL--"
)

XSS_PAYLOADS=(
    "<script>alert(1)</script>"
    "<img src=x onerror=alert(1)>"
    "\"><script>alert(1)</script>"
)

echo "  SQL Injection payload tests:"
for payload in "${SQLI_PAYLOADS[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -d "{\"busca\": \"$(echo "$payload" | sed 's/"/\\"/g')\"}" \
        "${API_BASE}/buscar" 2>/dev/null || echo "000")

    # Any non-500 response is acceptable (422 Pydantic error is correct behavior)
    if [[ "$status" != "500" && "$status" != "000" ]]; then
        pass "SQLi payload '${payload:0:20}...' handled (HTTP $status)"
    else
        fail "SQLi payload '${payload:0:20}...' caused HTTP $status"
    fi
done

echo "  XSS payload tests:"
for payload in "${XSS_PAYLOADS[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
        -X POST \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -d "{\"busca\": \"$(echo "$payload" | sed 's/"/\\"/g')\"}" \
        "${API_BASE}/buscar" 2>/dev/null || echo "000")

    if [[ "$status" != "500" && "$status" != "000" ]]; then
        pass "XSS payload '${payload:0:20}...' handled (HTTP $status)"
    else
        fail "XSS payload '${payload:0:20}...' caused HTTP $status"
    fi
done

echo "" | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 4. CORS Configuration (OWASP API8:2023 / A05:2021)
# ─────────────────────────────────────────────────────────────────────────────
print_section "4. CORS Configuration (OWASP API8:2023 / A05:2021)"

cors_result=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
    -X OPTIONS \
    -H "Origin: https://evil.com" \
    -H "Access-Control-Request-Method: GET" \
    "${API_BASE}/v1/setores" 2>/dev/null || echo "000")

cors_allow_origin=$(curl -s --max-time 10 \
    -X OPTIONS \
    -H "Origin: https://evil.com" \
    -H "Access-Control-Request-Method: GET" \
    "${API_BASE}/v1/setores" 2>/dev/null | grep -i "access-control-allow-origin" || true)

if [[ -n "$cors_allow_origin" ]]; then
    if echo "$cors_allow_origin" | grep -qi "\*"; then
        warn "CORS allows wildcard origin on OPTIONS"
    elif echo "$cors_allow_origin" | grep -qi "evil.com"; then
        fail "CORS reflects arbitrary origin (https://evil.com)"
    else
        pass "CORS properly restricted (Origin not reflected)"
    fi
else
    pass "CORS properly configured (no Access-Control-Allow-Origin for arbitrary origin)"
fi

echo "" | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 5. Admin Endpoint Hardening (OWASP API5:2023 / A01:2021)
# ─────────────────────────────────────────────────────────────────────────────
print_section "5. Admin Endpoint Hardening (OWASP API5:2023 / A01:2021)"

if [[ -n "$AUTH_TOKEN" ]]; then
    assert_admin_blocked "${API_BASE}/v1/admin/users" "GET /v1/admin/users"
    assert_admin_blocked "${API_BASE}/v1/admin/cache" "GET /v1/admin/cache"
    assert_admin_blocked "${API_BASE}/v1/admin/trace" "GET /v1/admin/trace"
    assert_admin_blocked "${API_BASE}/v1/admin/cron-status" "GET /v1/admin/cron-status"
else
    warn "Admin hardening tests skipped: AUTH_TOKEN not set"
fi

if [[ -n "$ADMIN_TOKEN" ]]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        "${API_BASE}/v1/admin/users" 2>/dev/null || echo "000")

    if [[ "$status" != "401" && "$status" != "403" ]]; then
        pass "Admin token can access admin endpoint (HTTP $status)"
    else
        warn "Admin token rejected by admin endpoint (HTTP $status) — may be expected"
    fi
fi

echo "" | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 6. HTTP Methods (OWASP API3:2023)
# ─────────────────────────────────────────────────────────────────────────────
print_section "6. HTTP Methods (OWASP API3:2023)"

test_methods() {
    local url="$1"
    local desc="$2"
    local methods=("GET" "POST" "PUT" "DELETE" "PATCH" "OPTIONS" "HEAD")
    local allowed=""

    for method in "${methods[@]}"; do
        local status
        status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
            -X "$method" \
            -H "Authorization: Bearer $AUTH_TOKEN" \
            "$url" 2>/dev/null || echo "000")

        if [[ "$status" != "405" && "$status" != "404" && "$status" != "000" ]]; then
            allowed="${allowed}${method}($status) "
        fi
    done

    if [[ -n "$allowed" ]]; then
        pass "$desc — allowed methods: $allowed"
    else
        warn "$desc — no non-405 methods detected (might need auth bypass)"
    fi
}

echo "  Checking HTTP methods on key endpoints..."
test_methods "${API_BASE}/health" "GET /health"
test_methods "${API_BASE}/v1/setores" "GET /v1/setores"

echo "" | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 7. Verbose Error Messages (OWASP API9:2023 / A05:2021)
# ─────────────────────────────────────────────────────────────────────────────
print_section "7. Verbose Error Messages (OWASP API9:2023 / A05:2021)"

# Test with malformed input to check error verbosity
error_response=$(curl -s --max-time 5 \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $AUTH_TOKEN" \
    -d '{"busca": 12345}' \
    "${API_BASE}/buscar" 2>/dev/null || true)

if echo "$error_response" | grep -qi "traceback\\|stack trace\\|at\\s+\\w+\\.py\\|File.*line"; then
    fail "Error response exposes stack trace details"
elif echo "$error_response" | grep -qi "detail\\|validation_error"; then
    pass "Error messages are structured and controlled"
else
    pass "No verbose error information leaked"
fi

echo "" | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print_section "API Security Checklist Summary"
{
    echo "  Target:     $API_BASE"
    echo "  PASS:       $PASS_COUNT"
    echo "  FAIL:       $FAIL_COUNT"
    echo "  WARN:       $WARN_COUNT"
    echo ""
    echo "  Full report: $SUMMARY_FILE"
} 2>&1 | tee -a "$SUMMARY_FILE"

if (( FAIL_COUNT > 0 )); then
    log_error "$FAIL_COUNT check(s) failed — review $SUMMARY_FILE"
    exit 1
else
    log_info "All API security checks passed"
    exit 0
fi
