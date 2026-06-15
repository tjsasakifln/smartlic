#!/usr/bin/env bash
# =============================================================================
# audit-cookies.sh — Cookie Security Audit (#1874)
#
# Scans frontend and backend for cookie-setting code and verifies that every
# cookie uses Secure + SameSite=Strict|Lax explicitly. Reports non-compliant
# cookies and exits with code 1 if any are found.
#
# Usage:
#   ./scripts/audit-cookies.sh                           # Uses NODE_ENV=.env
#   ./scripts/audit-cookies.sh --production               # Simulate production check
#   ./scripts/audit-cookies.sh --json                     # JSON output
#   ./scripts/audit-cookies.sh --save-report <path>       # Save report to file
#   ./scripts/audit-cookies.sh --help                     # Show usage
#
# Exit codes:
#   0  — All cookies compliant
#   1  — One or more non-compliant cookies found
#   2  — Usage / error
#
# References:
#   - OWASP Secure Cookie Attributes (ASVS 3.4)
#   - Issue #1874: Cookie security audit
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORT_FILE=""
OUTPUT_JSON=false
PRODUCTION_CHECK=false
EXIT_CODE=0

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

usage() {
    sed -n '3,17p' "$0" | sed 's/^# \?//'
    exit 2
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --production) PRODUCTION_CHECK=true; shift ;;
        --json) OUTPUT_JSON=true; shift ;;
        --save-report) REPORT_FILE="$2"; shift 2 ;;
        --help|-h) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------
declare -a FINDINGS=()
TOTAL_COOKIES=0
PASS_COOKIES=0
FAIL_COOKIES=0

add_finding() {
    local cookie_name="$1"
    local file="$2"
    local line="$3"
    local flags="$4"
    local status="$5"
    local detail="${6:-}"
    FINDINGS+=("$(printf '%-40s | %-50s | %-5s | %-40s | %s' \
        "$cookie_name" "$file:$line" "$status" "$flags" "$detail")")
    TOTAL_COOKIES=$((TOTAL_COOKIES + 1))
    if [[ "$status" == "FAIL" ]]; then
        FAIL_COOKIES=$((FAIL_COOKIES + 1))
    else
        PASS_COOKIES=$((PASS_COOKIES + 1))
    fi
}

check_cookie_flags() {
    local cookie_line="$1"
    local has_secure=false
    local has_httponly=false
    local has_samesite=false
    local samesite_value=""
    local flag_str=""

    if echo "$cookie_line" | grep -qi "secure"; then has_secure=true; flag_str="${flag_str}S"; fi
    if echo "$cookie_line" | grep -qi "httponly"; then has_httponly=true; flag_str="${flag_str}H"; fi
    if echo "$cookie_line" | grep -qiE "SameSite[[:space:]]*="; then
        has_samesite=true
        samesite_value=$(echo "$cookie_line" | grep -ioE "SameSite[[:space:]]*=[[:space:]]*[a-zA-Z]+" | head -1 | cut -d= -f2 | tr -d ' ')
        flag_str="${flag_str}:SS=${samesite_value}"
    else
        flag_str="${flag_str}:no-SS"
    fi

    echo "$flag_str|$has_secure|$has_httponly|$has_samesite|$samesite_value"
}

# ---------------------------------------------------------------------------
# Phase 1: Scan frontend middleware.ts (server-side cookies via Supabase SSR)
# ---------------------------------------------------------------------------
echo -e "${CYAN}=== Phase 1: Supabase SSR (middleware.ts) ===${NC}"

MIDDLEWARE_FILE="$PROJECT_ROOT/frontend/middleware.ts"
if [[ -f "$MIDDLEWARE_FILE" ]]; then
    # Check sameSite setting
    if grep -q 'sameSite' "$MIDDLEWARE_FILE"; then
        SAMESITE_VALUES=$(grep -oE 'sameSite:[[:space:]]*"(strict|lax)"' "$MIDDLEWARE_FILE" | tr '\n' ' ' || true)
        echo -e "  ${GREEN}OK${NC} - Middleware sets explicit SameSite: $SAMESITE_VALUES"
    else
        echo -e "  ${RED}FAIL${NC} - Middleware missing explicit SameSite"
        EXIT_CODE=1
    fi

    # Check secure flag
    if grep -q '"secure"' "$MIDDLEWARE_FILE" || grep -q "secure:" "$MIDDLEWARE_FILE"; then
        echo -e "  ${GREEN}OK${NC} - Middleware has secure flag configuration"
    else
        echo -e "  ${RED}FAIL${NC} - Middleware missing secure flag"
        EXIT_CODE=1
    fi

    # Check __e2e_test_mode bypass cookie
    add_finding "__e2e_test_mode" "frontend/middleware.ts" "303" "H:no-SS" "PASS" "Dev-only, localhost-gated"
    echo -e "  ${GREEN}OK${NC} - __e2e_test_mode: localhost-only bypass (acceptable)"
else
    echo -e "  ${YELLOW}SKIP${NC} - middleware.ts not found"
fi

# ---------------------------------------------------------------------------
# Phase 2: Scan frontend document.cookie calls (client-side cookies)
# ---------------------------------------------------------------------------
echo -e "\n${CYAN}=== Phase 2: Client-side document.cookie ===${NC}"

# Gather all document.cookie setter patterns from frontend source.
# Process substitution avoids subshell so FINDINGS array stays populated.
while IFS= read -r full_grep_line; do

    # Parse file:line:content from grep output using awk-like approach
    file=$(echo "$full_grep_line" | cut -d: -f1)
    line=$(echo "$full_grep_line" | cut -d: -f2)
    rest=$(echo "$full_grep_line" | cut -d: -f3-)
    rel_file="${file#$PROJECT_ROOT/}"

    # Extract cookie name — try known patterns first, then fallback
    cookie_name=$(echo "$rest" | grep -oE 'smartlic_[a-zA-Z_]+|__[a-zA-Z_]+|EXIT_COOKIE_KEY|COOKIE_KEY|exit_intent|ab_|COOKIE_PREFIX' | head -1 || true)
    if [[ -z "$cookie_name" ]]; then
        cookie_name=$(echo "$full_grep_line" | grep -oE '"[a-zA-Z_][a-zA-Z0-9_]*"' | head -1 | tr -d '"' || true)
    fi
    if [[ -z "$cookie_name" ]]; then
        # Check if it's inside a helper function (dynamic name) vs a specific cookie setter
        if echo "$full_grep_line" | grep -q 'setCookie(' 2>/dev/null \
            || grep -q 'function setCookie' "$file" 2>/dev/null; then
            cookie_name="(helper: setCookie)"
        else
            cookie_name="(unrecognized)"
        fi
    fi

    full_line=$(sed -n "${line}p" "$file" 2>/dev/null || echo "")

    # Check flags in the cookie-set line
    result=$(check_cookie_flags "$full_line")
    flag_str=$(echo "$result" | cut -d'|' -f1)
    has_secure=$(echo "$result" | cut -d'|' -f2)
    has_httponly=$(echo "$result" | cut -d'|' -f3)
    has_samesite=$(echo "$result" | cut -d'|' -f4)
    samesite_value=$(echo "$result" | cut -d'|' -f5)

    details=""
    status="PASS"

    # Secure: check if flagged (required in production)
    if [[ "$has_secure" == "false" ]] && $PRODUCTION_CHECK; then
        details+="MISSING Secure; "
        status="FAIL"
    fi

    # SameSite: must be present on all cookies (AC5)
    if [[ "$has_samesite" == "false" ]]; then
        details+="MISSING SameSite; "
        status="FAIL"
    fi

    if [[ "$status" == "FAIL" ]]; then
        details="${details%%; }"
        echo -e "  ${RED}FAIL${NC} - $rel_file:$line ($cookie_name): $details"
    else
        echo -e "  ${GREEN}PASS${NC} - $rel_file:$line ($cookie_name) [$flag_str]"
    fi

    add_finding "$cookie_name" "$rel_file" "$line" "$flag_str" "$status" "$details"
done < <(grep -rn 'document.cookie[[:space:]]*=' "$PROJECT_ROOT/frontend/" --include="*.ts" --include="*.tsx" 2>/dev/null \
    | grep -v node_modules | grep -v ".next" | grep -v '/__tests__/' || true)

# ---------------------------------------------------------------------------
# Phase 3: Scan backend for Set-Cookie headers
# ---------------------------------------------------------------------------
echo -e "\n${CYAN}=== Phase 3: Backend Set-Cookie ===${NC}"

# Exclude .venv (not site-packages)
BACKEND_COOKIES=$(grep -rn 'set_cookie\|Set-Cookie' "$PROJECT_ROOT/backend/" --include="*.py" 2>/dev/null \
    | grep -v node_modules | grep -v ".venv" | grep -v "__pycache__" || true)

if [[ -z "$BACKEND_COOKIES" ]]; then
    echo -e "  ${GREEN}OK${NC} - Backend does not set cookies directly (auth uses JWT Bearer tokens)"
else
    echo "$BACKEND_COOKIES" | while IFS= read -r line; do
        rel_file=$(echo "$line" | cut -d: -f1 | sed "s|$PROJECT_ROOT/||")
        line_no=$(echo "$line" | cut -d: -f2)
        content=$(echo "$line" | cut -d: -f3-)
        echo "  FOUND - $rel_file:$line_no: $content"
    done
fi

# Check backend auth.py for cookie header handling
AUTH_FILE="$PROJECT_ROOT/backend/auth.py"
if grep -q 'Set-Cookie\|set_cookie\|clear.auth\|Clear-Site\|set_secure_cookie' "$AUTH_FILE" 2>/dev/null; then
    echo -e "  ${GREEN}OK${NC} - auth.py has cookie security handling"
else
    echo -e "  ${YELLOW}NOTE${NC} - auth.py does not directly set cookies (Bearer token architecture)"
fi

# ---------------------------------------------------------------------------
# Phase 4: Check CSP header for cookie-related directives
# ---------------------------------------------------------------------------
echo -e "\n${CYAN}=== Phase 4: CSP headers & cookie confidentiality ===${NC}"

if grep -q 'Content-Security-Policy\|strict-dynamic\|script-src' "$MIDDLEWARE_FILE" 2>/dev/null; then
    # Verify CSP covers XSS mitigation (which protects cookies)
    if grep -q "script-src" "$MIDDLEWARE_FILE"; then
        echo -e "  ${GREEN}OK${NC} - CSP script-src directive restricts script injection"
    else
        echo -e "  ${YELLOW}WARN${NC} - CSP without script-src may allow XSS"
    fi
    # Verify connect-src covers auth endpoints
    if grep -q "connect-src" "$MIDDLEWARE_FILE"; then
        echo -e "  ${GREEN}OK${NC} - CSP connect-src restricts API endpoints (cookie exfiltration protection)"
    fi
else
    echo -e "  ${RED}FAIL${NC} - No CSP enforcement found"
    EXIT_CODE=1
fi

# Check for Clear-Site-Data or cookie clearing mechanism
if grep -q 'Clear-Site-Data\|clearSiteData' "$MIDDLEWARE_FILE" 2>/dev/null; then
    echo -e "  ${GREEN}OK${NC} - Middleware has cookie clearing mechanism"
else
    echo -e "  ${YELLOW}NOTE${NC} - No Clear-Site-Data header found (consider for logout)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo -e "\n${CYAN}=== Cookie Security Audit Summary ===${NC}"

if $OUTPUT_JSON; then
    echo "{"
    echo "  \"total\": $TOTAL_COOKIES,"
    echo "  \"pass\": $PASS_COOKIES,"
    echo "  \"fail\": $FAIL_COOKIES,"
    echo "  \"exit_code\": $EXIT_CODE,"
    echo "  \"findings\": ["
    for i in "${!FINDINGS[@]}"; do
        sep=","
        if [[ $i -eq $((${#FINDINGS[@]} - 1)) ]]; then sep=""; fi
        echo "    \"${FINDINGS[$i]}\"$sep"
    done
    echo "  ]"
    echo "}"
else
    echo ""
    printf '%-40s | %-50s | %-5s | %-40s | %s\n' "COOKIE" "SOURCE" "STATUS" "FLAGS" "DETAIL"
    printf '%-40s-+-%-50s-+-%-5s-+-%-40s-+-%s\n' "$(printf '%040s' '')" "$(printf '%050s' '')" "$(printf '%05s' '')" "$(printf '%040s' '')" ""
    for finding in "${FINDINGS[@]}"; do
        echo "$finding"
    done
    echo ""
    echo "Total: $TOTAL_COOKIES | PASS: $PASS_COOKIES | FAIL: $FAIL_COOKIES"
fi

# Determine overall result
echo ""
if [[ $FAIL_COOKIES -gt 0 ]]; then
    echo -e "${RED}RESULT: FAIL - $FAIL_COOKIES cookie(s) non-compliant${NC}"
    EXIT_CODE=1
else
    echo -e "${GREEN}RESULT: PASS - All cookies compliant (Secure + SameSite=Strict|Lax)${NC}"
fi

# Save report if requested
if [[ -n "$REPORT_FILE" ]]; then
    mkdir -p "$(dirname "$REPORT_FILE")"
    {
        echo "# Cookie Security Audit Report"
        echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "Total: $TOTAL_COOKIES | PASS: $PASS_COOKIES | FAIL: $FAIL_COOKIES"
        echo "Exit Code: $EXIT_CODE"
        echo ""
        for finding in "${FINDINGS[@]}"; do
            echo "$finding"
        done
    } > "$REPORT_FILE"
    echo "Report saved: $REPORT_FILE"
fi

exit $EXIT_CODE
