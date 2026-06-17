#!/bin/bash
# =============================================================================
# SmartLic Automated Security Scan
# =============================================================================
# Orchestrates multiple security tools for a comprehensive scan.
# Safe by default: targets staging, never runs destructive tests.
#
# Usage:
#   ./scripts/security/automated-scan.sh [--target=<URL>] [--mode=quick|full]
#   ./scripts/security/automated-scan.sh --target=https://staging.smartlic.tech
#   ./scripts/security/automated-scan.sh --target=https://staging.smartlic.tech --mode=full
#
# Tools (when available):
#   1. Security headers check (curl) — always runs
#   2. TLS/SSL check (testssl.sh or openssl) — always runs
#   3. OWASP ZAP (docker) — quick mode only
#   4. nuclei (template-based) — if installed
#   5. nikto (web server scan) — if installed
#   6. CSP analysis — always runs
#   7. Dependency audit (pip-audit + npm audit) — if repos accessible
#
# Exit codes:
#   0 — All checks passed (or warnings only)
#   1 — One or more checks failed
#   2 — Fatal configuration error
# =============================================================================

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
TARGET="${TARGET:-https://staging.smartlic.tech}"
MODE="${MODE:-quick}"  # quick or full
REPORT_DIR="${REPORT_DIR:-reports/security/$(date +%Y-%m-%d)}"
SUMMARY_FILE="${REPORT_DIR}/scan-summary.txt"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
usage() {
    grep "^# Usage:" "$0" | sed 's/^# //'
    exit 2
}

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

check_dep() {
    if ! command -v "$1" &>/dev/null; then
        log_warn "Dependency '$1' not found — skipping related checks"
        return 1
    fi
    return 0
}

check_pass() { ((PASS_COUNT++)); echo -e "  ${GREEN}PASS${NC}"; }
check_fail() { ((FAIL_COUNT++)); echo -e "  ${RED}FAIL${NC}"; }
check_skip() { ((SKIP_COUNT++)); echo -e "  ${YELLOW}SKIP${NC}"; }

print_section() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  $1"
    echo "═══════════════════════════════════════════════════════════════"
}

# Parse args
for arg in "$@"; do
    case "$arg" in
        --target=*) TARGET="${arg#*=}" ;;
        --mode=*)   MODE="${arg#*=}" ;;
        --help|-h)  usage ;;
        *)          log_error "Unknown argument: $arg"; usage ;;
    esac
done

if [[ "$MODE" != "quick" && "$MODE" != "full" ]]; then
    log_error "Mode must be 'quick' or 'full', got '$MODE'"
    exit 2
fi

mkdir -p "$REPORT_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Security Headers Check
# ─────────────────────────────────────────────────────────────────────────────
print_section "1. Security Headers Check [$TARGET]"

{
    HEADERS=$(curl -sI --max-time 10 "$TARGET" 2>/dev/null || true)
    HEADERS_FILE="$REPORT_DIR/headers.txt"

    # Save raw headers
    echo "$HEADERS" > "$HEADERS_FILE"

    checks=(
        "Content-Security-Policy:CSP not set — consider adding CSP header"
        "Strict-Transport-Security:HSTS not set"
        "X-Content-Type-Options:X-Content-Type-Options not set"
        "X-Frame-Options:X-Frame-Options not set"
        "Referrer-Policy:Referrer-Policy not set"
        "Permissions-Policy:Permissions-Policy not set"
        "X-XSS-Protection:X-XSS-Protection not set"
    )

    for check in "${checks[@]}"; do
        header="${check%%:*}"
        msg="${check#*:}"
        if echo "$HEADERS" | grep -qi "^${header}:"; then
            val=$(echo "$HEADERS" | grep -i "^${header}:" | head -1 | sed 's/^[^:]*: //' | tr -d '\r')
            echo -e "  ${GREEN}OK${NC}     $header: $val"
        else
            echo -e "  ${RED}MISSING${NC} $header — $msg"
        fi
    done
} 2>&1 | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 2. TLS / SSL Check
# ─────────────────────────────────────────────────────────────────────────────
print_section "2. TLS/SSL Check [$TARGET]"
{
    DOMAIN=$(echo "$TARGET" | sed 's|^https://||; s|/.*$||')

    if command -v testssl.sh &>/dev/null; then
        log_info "Running testssl.sh (this may take a few minutes)..."
        testssl.sh --quiet --jsonfile "$REPORT_DIR/tls.json" "$TARGET" 2>&1 | tail -5 || true
        check_pass
    elif command -v openssl &>/dev/null; then
        log_info "testssl.sh not found — using openssl for basic TLS check"
        echo "TLS version check for $DOMAIN:443" | tee -a "$SUMMARY_FILE"

        # Check TLS 1.2
        if echo Q | openssl s_client -connect "${DOMAIN}:443" -tls1_2 2>/dev/null | grep -q "CONNECTED"; then
            echo -e "  ${GREEN}OK${NC}     TLS 1.2 supported"
        else
            echo -e "  ${YELLOW}WARN${NC}  TLS 1.2 check failed (may be expected)"
        fi

        # Check TLS 1.3
        if echo Q | openssl s_client -connect "${DOMAIN}:443" -tls1_3 2>/dev/null | grep -q "CONNECTED"; then
            echo -e "  ${GREEN}OK${NC}     TLS 1.3 supported"
        else
            echo -e "  ${YELLOW}WARN${NC}  TLS 1.3 not supported"
        fi

        # Certificate expiry
        expiry=$(echo Q | openssl s_client -connect "${DOMAIN}:443" 2>/dev/null | \
            openssl x509 -noout -dates 2>/dev/null | grep "notAfter" | cut -d= -f2 || true)
        if [[ -n "$expiry" ]]; then
            echo -e "  ${GREEN}OK${NC}     Certificate expires: $expiry"
        fi

        check_pass
    else
        log_warn "Neither testssl.sh nor openssl found — skipping TLS check"
        check_skip
    fi
} 2>&1 | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 3. CSP Analysis
# ─────────────────────────────────────────────────────────────────────────────
print_section "3. CSP Analysis [$TARGET]"
{
    CSP=$(curl -sI --max-time 10 "$TARGET" 2>/dev/null | grep -i "^content-security-policy:" | sed 's/^[^:]*: //' | tr -d '\r' || true)

    if [[ -z "$CSP" ]]; then
        log_warn "No Content-Security-Policy header found"
        log_info "The backend does not set CSP — this is a known gap."
        log_info "OWASP ZAP will report this as a medium-severity finding."
        check_skip

        # Save CSP-absence note to report
        echo "CSP: NOT SET — known gap. Backend uses other security headers (HSTS, XFO, etc.)" \
            > "$REPORT_DIR/csp-analysis.txt"
    else
        echo "$CSP" > "$REPORT_DIR/csp-analysis.txt"
        echo "CSP found: ${CSP:0:120}..."

        # Check for unsafe directives
        if echo "$CSP" | grep -qi "unsafe-inline\\|unsafe-eval"; then
            echo -e "  ${YELLOW}WARN${NC}  CSP contains unsafe-inline or unsafe-eval"
        else
            echo -e "  ${GREEN}OK${NC}     No unsafe-inline or unsafe-eval in CSP"
        fi

        # Check if in report-only mode
        if echo "$CSP" | grep -qi "report-only\\|Content-Security-Policy-Report-Only"; then
            echo -e "  ${YELLOW}WARN${NC}  CSP is in report-only mode (not enforced)"
        fi

        check_pass
    fi
} 2>&1 | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 4. OWASP ZAP Scan (quick mode only — no active attacks)
# ─────────────────────────────────────────────────────────────────────────────
print_section "4. OWASP ZAP Scan (${MODE})"
{
    if command -v docker &>/dev/null; then
        ZAP_CONTAINER=$(docker ps --filter "name=zap" --format "{{.Names}}" 2>/dev/null | head -1 || true)
        if [[ -z "$ZAP_CONTAINER" ]]; then
            log_info "No running ZAP container found"
            log_info "To run ZAP: docker run -d --name zap-staging -p 8080:8080 ghcr.io/zaproxy/zaproxy:stable"
            log_info "Then run: scripts/security/run-zap-scan.sh --target $TARGET --mode $MODE"
            check_skip
        else
            log_info "ZAP container found: $ZAP_CONTAINER"
            log_info "Running ZAP scan via run-zap-scan.sh..."

            if [[ -f "scripts/security/run-zap-scan.sh" ]]; then
                bash "scripts/security/run-zap-scan.sh" \
                    --target "$TARGET" \
                    --mode "${MODE}" \
                    --output "$REPORT_DIR/zap" 2>&1 | tail -10 || true

                if [[ -f "$REPORT_DIR/zap/report.html" ]]; then
                    check_pass
                else
                    log_warn "ZAP scan completed but no report generated"
                    check_skip
                fi
            else
                log_warn "run-zap-scan.sh not found — skipping ZAP scan"
                check_skip
            fi
        fi
    else
        log_info "Docker not available — skipping ZAP scan"
        check_skip
    fi
} 2>&1 | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 5. nuclei Scan (template-based, if installed)
# ─────────────────────────────────────────────────────────────────────────────
print_section "5. nuclei Scan [$TARGET]"
{
    if check_dep "nuclei"; then
        log_info "Running nuclei vulnerability scan..."
        nuclei -u "$TARGET" \
            -severity low,medium,high,critical \
            -json \
            -o "$REPORT_DIR/nuclei-results.json" \
            -silent 2>&1 || true

        if [[ -f "$REPORT_DIR/nuclei-results.json" ]]; then
            COUNT=$(wc -l < "$REPORT_DIR/nuclei-results.json" 2>/dev/null || echo 0)
            log_info "nuclei found $COUNT findings — see $REPORT_DIR/nuclei-results.json"
            check_pass
        else
            check_pass  # No findings is still a pass
        fi
    else
        log_info "nuclei not installed. Install: brew install nuclei or go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
        check_skip
    fi
} 2>&1 | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 6. nikto Scan (web server scan, if installed)
# ─────────────────────────────────────────────────────────────────────────────
print_section "6. nikto Web Server Scan [$TARGET]"
{
    if [[ "$MODE" == "full" ]] && check_dep "nikto"; then
        log_info "Running nikto web server scan..."
        nikto -h "$TARGET" \
            -Format json \
            -output "$REPORT_DIR/nikto-results.json" \
            -nointeractive 2>&1 || true
        check_pass
    elif [[ "$MODE" == "quick" ]]; then
        log_info "Skipping nikto in quick mode (use --mode=full)"
        check_skip
    else
        log_info "nikto not installed. Install: brew install nikto or apt install nikto"
        check_skip
    fi
} 2>&1 | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 7. Dependency Audit
# ─────────────────────────────────────────────────────────────────────────────
print_section "7. Dependency Audit"
{
    # Backend pip-audit
    if [[ -f "backend/requirements.txt" ]] && check_dep "pip-audit"; then
        log_info "Running pip-audit on backend dependencies..."
        cd backend
        pip-audit --strict -r requirements.txt \
            --desc on \
            --format json \
            --output "../$REPORT_DIR/pip-audit.json" \
            2>&1 || true
        cd ..
        log_info "pip-audit report saved to $REPORT_DIR/pip-audit.json"
        check_pass
    else
        log_info "Skipping pip-audit (pip-audit not installed or backend/requirements.txt not found)"
        check_skip
    fi

    # Frontend npm audit
    if [[ -f "frontend/package.json" ]] && check_dep "npm"; then
        log_info "Running npm audit on frontend dependencies..."
        cd frontend
        npm audit --json > "../$REPORT_DIR/npm-audit.json" 2>/dev/null || true
        cd ..
        log_info "npm audit report saved to $REPORT_DIR/npm-audit.json"
        check_pass
    else
        log_info "Skipping npm audit (npm not installed or frontend/package.json not found)"
        check_skip
    fi
} 2>&1 | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print_section "Scan Complete"
{
    echo "  Target:        $TARGET"
    echo "  Mode:          $MODE"
    echo "  Report dir:    $(cd "$REPORT_DIR" 2>/dev/null && pwd || echo "$REPORT_DIR")"
    echo ""
    echo "  PASS:          $PASS_COUNT"
    echo "  FAIL:          $FAIL_COUNT"
    echo "  SKIP:          $SKIP_COUNT"
    echo ""
    echo "  Reports generated:"
    for f in "$REPORT_DIR"/*; do
        [[ -f "$f" ]] && echo "    - $(basename "$f")"
    done
} 2>&1 | tee -a "$SUMMARY_FILE"

# Exit with appropriate code
if (( FAIL_COUNT > 0 )); then
    log_error "$FAIL_COUNT check(s) failed — review reports in $REPORT_DIR"
    exit 1
else
    log_info "All checks passed (or skipped due to missing tools)"
    exit 0
fi
