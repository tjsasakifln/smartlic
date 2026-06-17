#!/usr/bin/env bash
# =============================================================================
# SmartLic Security Scan — Entry Point
# =============================================================================
# Top-level security scanning script. Runs enhanced HTTP header checks,
# delegates to automated-scan.sh for comprehensive scanning, and calls
# api-security-checklist.sh when API_BASE + tokens are configured.
#
# Usage:
#   ./scripts/security/scan.sh [--target=<URL>] [--mode=quick|full]
#
# Enhanced checks (always runs):
#   - HTTP security headers (CSP, HSTS, XFO, COEP, COOP, CORP, Cache-Control)
#   - Cross-Origin policies
#   - Cookie security flags (Secure, HttpOnly, SameSite)
#
# Delegates to:
#   - automated-scan.sh — full orchestrated scan (ZAP, nuclei, TLS, deps)
#   - api-security-checklist.sh — OWASP API Top 10 checks (if tokens set)
#
# Environment variables:
#   TARGET          — Target URL (default: https://staging.smartlic.tech)
#   MODE            — quick|full (default: quick)
#   REPORT_DIR      — Output directory (default: reports/security/$(date +%Y-%m-%d))
#   API_BASE        — API base URL (default: same as TARGET)
#   AUTH_TOKEN      — JWT for authenticated API checks
#   ADMIN_TOKEN     — Admin JWT for admin endpoint checks
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
API_BASE="${API_BASE:-$TARGET}"
MODE="${MODE:-quick}"
REPORT_DIR="${REPORT_DIR:-reports/security/$(date +%Y-%m-%d)}"
SUMMARY_FILE="${REPORT_DIR}/scan-summary.txt"

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
usage() {
    grep "^# Usage:" "$0" | sed 's/^# //'
    exit 2
}

log_info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_pass()  { echo -e "${GREEN}[PASS]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

check_pass() { ((PASS_COUNT++)); echo -e "  ${GREEN}PASS${NC} $1"; }
check_fail() { ((FAIL_COUNT++)); echo -e "  ${RED}FAIL${NC} $1"; }
check_warn() { ((WARN_COUNT++)); echo -e "  ${YELLOW}WARN${NC}  $1"; }

print_section() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  $1"
    echo "═══════════════════════════════════════════════════════════════"
}

check_dep() {
    if ! command -v "$1" &>/dev/null; then
        return 1
    fi
    return 0
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
# Banner
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════════════════════════╗"
echo "  ║        SmartLic Security Scan — Entry Point             ║"
echo "  ╚══════════════════════════════════════════════════════════╝"
echo ""
log_info "Target:    $TARGET"
log_info "API_BASE:  $API_BASE"
log_info "Mode:      $MODE"
log_info "Report:    $REPORT_DIR"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 1. Enhanced HTTP Security Headers Check
# ─────────────────────────────────────────────────────────────────────────────
print_section "1. Enhanced HTTP Security Headers [$TARGET]"

{
    HEADERS=$(curl -sI --max-time 10 "$TARGET" 2>/dev/null || true)
    HEADERS_FILE="$REPORT_DIR/enhanced-headers.txt"
    echo "$HEADERS" > "$HEADERS_FILE"

    # ── Standard security headers ──
    log_info "Standard security headers:"

    declare -A STD_HEADERS
    STD_HEADERS["Content-Security-Policy"]="CSP nao definido — considerar adicionar CSP header"
    STD_HEADERS["Strict-Transport-Security"]="HSTS nao definido — risco de SSL stripping"
    STD_HEADERS["X-Content-Type-Options"]="X-Content-Type-Options nao definido — risco de MIME sniffing"
    STD_HEADERS["X-Frame-Options"]="X-Frame-Options nao definido — risco de clickjacking"
    STD_HEADERS["Referrer-Policy"]="Referrer-Policy nao definido — vazamento de referrer"
    STD_HEADERS["Permissions-Policy"]="Permissions-Policy nao definido — APIs do browser expostas"

    for header in "${!STD_HEADERS[@]}"; do
        if echo "$HEADERS" | grep -qi "^${header}:"; then
            val=$(echo "$HEADERS" | grep -i "^${header}:" | head -1 | sed 's/^[^:]*: //' | tr -d '\r')
            check_pass "$header: $val"
        else
            check_warn "${header} — ${STD_HEADERS[$header]}"
        fi
    done

    # ── Enhanced: Cross-Origin isolation headers ──
    log_info ""
    log_info "Cross-Origin isolation headers:"

    declare -A COOP_HEADERS
    COOP_HEADERS["Cross-Origin-Embedder-Policy"]="COEP nao definido — permite cross-origin resource loading sem requerer CORP"
    COOP_HEADERS["Cross-Origin-Opener-Policy"]="COOP nao definido — janela pode ser acessada por cross-origin openers"
    COOP_HEADERS["Cross-Origin-Resource-Policy"]="CORP nao definido — cross-origin resource loading irrestrito"

    for header in "${!COOP_HEADERS[@]}"; do
        if echo "$HEADERS" | grep -qi "^${header}:"; then
            val=$(echo "$HEADERS" | grep -i "^${header}:" | head -1 | sed 's/^[^:]*: //' | tr -d '\r')
            check_pass "$header: $val"
        else
            check_warn "${header} — ${COOP_HEADERS[$header]}"
        fi
    done

    # ── Enhanced: Cache-Control (for sensitive pages) ──
    log_info ""
    log_info "Cache-Control header:"

    if echo "$HEADERS" | grep -qi "^cache-control:"; then
        val=$(echo "$HEADERS" | grep -i "^cache-control:" | head -1 | sed 's/^[^:]*: //' | tr -d '\r')
        if echo "$val" | grep -qi "no-store"; then
            check_pass "Cache-Control: $val (no-store presente)"
        else
            check_warn "Cache-Control: $val (no-store ausente — dados sensiveis podem ser cacheados)"
        fi
    else
        check_warn "Cache-Control nao definido — browser pode cachear respostas"
    fi

    # ── Enhanced: Cookie security flags ──
    log_info ""
    log_info "Cookie security flags:"

    SET_COOKIES=$(echo "$HEADERS" | grep -i "^set-cookie:" || true)
    if [[ -n "$SET_COOKIES" ]]; then
        cookie_count=$(echo "$SET_COOKIES" | wc -l)
        log_info "  $cookie_count cookie(s) encontrado(s)"

        while IFS= read -r cookie_line; do
            cookie_name=$(echo "$cookie_line" | sed 's/^[^:]*: //' | cut -d= -f1 | tr -d '\r')
            issues=""

            echo "$cookie_line" | grep -qi "secure" || issues="${issues} Secure ausente,"
            echo "$cookie_line" | grep -qi "httponly" || issues="${issues} HttpOnly ausente,"
            echo "$cookie_line" | grep -qi "samesite" || issues="${issues} SameSite ausente,"

            if [[ -z "$issues" ]]; then
                check_pass "Cookie '$cookie_name': Secure + HttpOnly + SameSite presentes"
            else
                issues="${issues%,}"
                check_warn "Cookie '$cookie_name': $issues"
            fi
        done <<< "$SET_COOKIES"
    else
        log_info "  Nenhum cookie Set-Cookie encontrado (pode ser esperado para APIs stateless)"
    fi
} 2>&1 | tee -a "$SUMMARY_FILE"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Delegar para automated-scan.sh (orquestrador existente)
# ─────────────────────────────────────────────────────────────────────────────
print_section "2. Automated Scan (delegated to automated-scan.sh)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATED_SCAN="${SCRIPT_DIR}/automated-scan.sh"

if [[ -x "$AUTOMATED_SCAN" ]]; then
    log_info "Delegating to automated-scan.sh (target=$TARGET, mode=$MODE)..."
    bash "$AUTOMATED_SCAN" --target="$TARGET" --mode="$MODE" 2>&1 | tee -a "$SUMMARY_FILE"
    log_info "automated-scan.sh concluido."
else
    log_warn "automated-scan.sh nao encontrado ou nao executavel em $AUTOMATED_SCAN"
    log_info "Run manually: scripts/security/automated-scan.sh --target=$TARGET --mode=$MODE"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 3. Delegar para api-security-checklist.sh (se tokens configurados)
# ─────────────────────────────────────────────────────────────────────────────
if [[ -n "${AUTH_TOKEN:-}" || -n "${ADMIN_TOKEN:-}" ]]; then
    print_section "3. API Security Checklist (delegated to api-security-checklist.sh)"

    API_CHECKLIST="${SCRIPT_DIR}/api-security-checklist.sh"
    if [[ -x "$API_CHECKLIST" ]]; then
        log_info "Delegating to api-security-checklist.sh..."
        API_BASE="$API_BASE" AUTH_TOKEN="$AUTH_TOKEN" ADMIN_TOKEN="$ADMIN_TOKEN" \
            REPORT_DIR="$REPORT_DIR" \
            bash "$API_CHECKLIST" 2>&1 | tee -a "$SUMMARY_FILE"
        log_info "api-security-checklist.sh concluido."
    else
        log_warn "api-security-checklist.sh nao encontrado em $API_CHECKLIST"
    fi
else
    log_info "Skipping API Security Checklist (set AUTH_TOKEN/ADMIN_TOKEN for API tests)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print_section "Scan Complete"

{
    echo ""
    echo "  Target:        $TARGET"
    echo "  Mode:          $MODE"
    echo "  Report dir:    $(cd "$REPORT_DIR" 2>/dev/null && pwd || echo "$REPORT_DIR")"
    echo ""
    echo "  PASS:          $PASS_COUNT"
    echo "  FAIL:          $FAIL_COUNT"
    echo "  WARN:          $WARN_COUNT"
    echo ""
    echo "  Reports generated:"
    for f in "$REPORT_DIR"/*; do
        [[ -f "$f" ]] && echo "    - $(basename "$f")"
    done
    echo ""
} 2>&1 | tee -a "$SUMMARY_FILE"

if (( FAIL_COUNT > 0 )); then
    log_error "$FAIL_COUNT check(s) failed — review reports in $REPORT_DIR"
    exit 1
else
    log_info "All checks passed (or warnings only)"
    if (( WARN_COUNT > 0 )); then
        log_info "$WARN_COUNT warning(s) — review recommended"
    fi
    exit 0
fi
