#!/usr/bin/env bash
# =============================================================================
# Health Check Loop — Continuous health monitoring during chaos experiments
#
# Polls /health/ready every N seconds during an experiment.
# Logs status changes, timestamps, and alerts if degraded > threshold.
#
# Usage:
#   ./scripts/chaos/health-check-loop.sh [--url URL] [options...]
#
# Options:
#   --url URL           Staging URL (default: https://staging.smartlic.tech)
#   --interval SECONDS  Polling interval (default: 5)
#   --alert-after SEC   Alert if degraded/exceeds this duration (default: 30)
#   --output FILE       Write log to file (default: stdout)
#   --csv FILE          Write structured CSV log (optional)
#   --once              Single check and exit
#   --json              Output each check as single-line JSON
#   --no-color          Disable color output
#   --timeout SEC       HTTP request timeout (default: 5)
#
# Exit codes:
#   0 - All checks healthy
#   1 - Any check degraded
#   2 - Any check unhealthy
#   3 - Connection error (staging unreachable)
#   4 - Interrupted
#
# Output format (text mode):
#   [2026-06-17T10:00:00-0300] HTTP 200 | status=healthy | redis=ok | supabase=ok | pool=ok | cache=ok
#
# Output format (JSON mode):
#   {"timestamp":"...","status_code":200,"overall":"healthy","checks":{"redis":"ok","supabase":"ok","pool":"ok","cache":"ok"},"degraded_duration_s":0}
#
# Author: @devops (Gage)
# Issue: #1922
# =============================================================================

set -euo pipefail

# ---- Constants --------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP_FORMAT="%Y-%m-%dT%H:%M:%S%z"

# ---- Defaults ---------------------------------------------------------------

STAGING_URL="${STAGING_URL:-https://staging.smartlic.tech}"
CHECK_INTERVAL=5
ALERT_AFTER=30
OUTPUT_FILE=""
CSV_FILE=""
ONCE=false
JSON_MODE=false
NO_COLOR=false
HTTP_TIMEOUT=5

# ---- Color output -----------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

if ${NO_COLOR}; then
    RED=''; GREEN=''; YELLOW=''; BLUE=''; BOLD=''; NC=''
fi

info()  { echo -e "${BLUE}[INFO]${NC}  $*"; }
pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }

# ---- Parse arguments --------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --url) STAGING_URL="$2"; shift 2 ;;
        --interval) CHECK_INTERVAL="$2"; shift 2 ;;
        --alert-after) ALERT_AFTER="$2"; shift 2 ;;
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        --csv) CSV_FILE="$2"; shift 2 ;;
        --once) ONCE=true; shift ;;
        --json) JSON_MODE=true; shift ;;
        --no-color) NO_COLOR=true; shift ;;
        --timeout) HTTP_TIMEOUT="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: $0 [--url URL] [--interval N] [--alert-after N] [--output FILE] [--csv FILE] [--once] [--json] [--no-color] [--timeout N]"
            exit 0
            ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ---- State tracking ---------------------------------------------------------

_CONSECUTIVE_DEGRADED=0
_DEGRADED_START=""
_DEGRADED_DURATION=0
_PREV_STATUS="healthy"
_START_TIME=$(date +%s)

# ---- Output redirect --------------------------------------------------------

if [[ -n "${OUTPUT_FILE}" ]]; then
    exec > >(tee -a "${OUTPUT_FILE}") 2>&1
fi

# ---- Functions --------------------------------------------------------------

# Perform a single health check and return structured data
do_health_check() {
    local status_code
    local body
    local http_code
    local err_flag=0

    # Collect HTTP code + body together
    local response
    response=$(curl -s -w "\n%{http_code}" --max-time "${HTTP_TIMEOUT}" \
        "${STAGING_URL}/health/ready" 2>/dev/null || true)

    http_code=$(echo "${response}" | tail -1)
    body=$(echo "${response}" | sed '$d')

    if [[ -z "${http_code}" || "${http_code}" == "000" ]]; then
        http_code="000"
        body='{"status":"unreachable"}'
        err_flag=1
    fi

    # Parse JSON fields
    local overall_status="unknown"
    local redis_status="unknown"
    local supabase_status="unknown"
    local pool_status="unknown"
    local cache_status="unknown"
    local wedge_risk="unknown"
    local pool_pct=""

    if [[ -n "${body}" ]]; then
        overall_status=$(echo "${body}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('status', 'unknown'))
except Exception:
    print('parse_error')
" 2>/dev/null || echo "parse_error")

        redis_status=$(echo "${body}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('checks', {}).get('redis', {}).get('status', 'unknown'))
except Exception:
    print('parse_error')
" 2>/dev/null || echo "parse_error")

        supabase_status=$(echo "${body}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('checks', {}).get('supabase', {}).get('status', 'unknown'))
except Exception:
    print('parse_error')
" 2>/dev/null || echo "parse_error")

        pool_status=$(echo "${body}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('checks', {}).get('pool', {}).get('status', 'unknown'))
except Exception:
    print('parse_error')
" 2>/dev/null || echo "parse_error")

        cache_status=$(echo "${body}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('checks', {}).get('cache', {}).get('status', 'unknown'))
except Exception:
    print('parse_error')
" 2>/dev/null || echo "parse_error")

        wedge_risk=$(echo "${body}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('wedge_risk', 'unknown'))
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown")

        pool_pct=$(echo "${body}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('checks', {}).get('pool', {}).get('utilization_pct', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")
    fi

    cat <<-EOF
HTTP_CODE=${http_code}
OVERALL=${overall_status}
REDIS=${redis_status}
SUPABASE=${supabase_status}
POOL=${pool_status}
POOL_PCT=${pool_pct}
CACHE=${cache_status}
WEDGE_RISK=${wedge_risk}
ERR=${err_flag}
EOF
}

# Format one line of output
format_output() {
    local data="$1"
    local timestamp
    timestamp=$(date +"${TIMESTAMP_FORMAT}")

    local http_code overall redis_status supabase_status pool_status pool_pct cache_status wedge_risk err_flag
    http_code=$(echo "${data}" | grep "^HTTP_CODE=" | cut -d= -f2)
    overall=$(echo "${data}" | grep "^OVERALL=" | cut -d= -f2)
    redis_status=$(echo "${data}" | grep "^REDIS=" | cut -d= -f2)
    supabase_status=$(echo "${data}" | grep "^SUPABASE=" | cut -d= -f2)
    pool_status=$(echo "${data}" | grep "^POOL=" | cut -d= -f2)
    pool_pct=$(echo "${data}" | grep "^POOL_PCT=" | cut -d= -f2)
    cache_status=$(echo "${data}" | grep "^CACHE=" | cut -d= -f2)
    wedge_risk=$(echo "${data}" | grep "^WEDGE_RISK=" | cut -d= -f2)
    err_flag=$(echo "${data}" | grep "^ERR=" | cut -d= -f2)

    if [[ "${JSON_MODE}" == "true" ]]; then
        # JSON output
        local pool_str="\"pool\":\"${pool_status}\""
        if [[ -n "${pool_pct}" ]]; then
            pool_str="\"pool_status\":\"${pool_status}\",\"pool_pct\":${pool_pct}"
        fi
        echo "{\"timestamp\":\"${timestamp}\",\"status_code\":${http_code},\"overall\":\"${overall}\",\"checks\":{\"redis\":\"${redis_status}\",\"supabase\":\"${supabase_status}\",${pool_str},\"cache\":\"${cache_status}\"},\"wedge_risk\":\"${wedge_risk}\",\"degraded_duration_s\":${_DEGRADED_DURATION},\"err_flag\":${err_flag}}"
    else
        # Text output
        local color="${GREEN}"
        local status_label="HEALTHY"
        if [[ "${overall}" == "degraded" ]]; then
            color="${YELLOW}"
            status_label="DEGRADED"
        elif [[ "${overall}" == "unhealthy" || "${overall}" == "unreachable" ]]; then
            color="${RED}"
            status_label="UNHEALTHY"
        fi

        echo -e "[${timestamp}] ${color}${BOLD}${status_label}${NC} HTTP ${http_code} | overall=${overall} redis=${redis_status} supabase=${supabase_status} pool=${pool_status}${pool_pct:+ (${pool_pct}%)} cache=${cache_status} wedge=${wedge_risk}"
    fi
}

# Write CSV row
write_csv() {
    local data="$1"
    local csv_file="$2"
    local timestamp
    timestamp=$(date +"${TIMESTAMP_FORMAT}")

    local http_code overall redis_status supabase_status pool_status cache_status
    http_code=$(echo "${data}" | grep "^HTTP_CODE=" | cut -d= -f2)
    overall=$(echo "${data}" | grep "^OVERALL=" | cut -d= -f2)
    redis_status=$(echo "${data}" | grep "^REDIS=" | cut -d= -f2)
    supabase_status=$(echo "${data}" | grep "^SUPABASE=" | cut -d= -f2)
    pool_status=$(echo "${data}" | grep "^POOL=" | cut -d= -f2)
    cache_status=$(echo "${data}" | grep "^CACHE=" | cut -d= -f2)

    if [[ ! -f "${csv_file}" ]]; then
        echo "timestamp,status_code,overall,redis,supabase,pool,cache" > "${csv_file}"
    fi
    echo "${timestamp},${http_code},${overall},${redis_status},${supabase_status},${pool_status},${cache_status}" >> "${csv_file}"
}

# ---- Trap -------------------------------------------------------------------

cleanup() {
    local exit_code=$?
    local total_duration=$(( $(date +%s) - _START_TIME ))
    echo ""
    info "Health check loop ended after ${total_duration}s"
    info "Exit code: ${exit_code}"
    exit "${exit_code}"
}

trap cleanup SIGINT SIGTERM

# ---- Main loop --------------------------------------------------------------

main() {
    local check_count=0
    local degraded_count=0
    local unhealthy_count=0
    local unreachable_count=0

    # CSV header
    if [[ -n "${CSV_FILE}" ]]; then
        mkdir -p "$(dirname "${CSV_FILE}")" 2>/dev/null || true
        echo "timestamp,status_code,overall,redis,supabase,pool,cache" > "${CSV_FILE}"
    fi

    info "Starting health check loop..."
    info "  URL:       ${STAGING_URL}"
    info "  Interval:  ${CHECK_INTERVAL}s"
    info "  Alert at:  ${ALERT_AFTER}s degraded"
    info "  JSON mode: ${JSON_MODE}"
    info "  CSV:       ${CSV_FILE:-"(none)"}"
    echo ""

    while true; do
        check_count=$((check_count + 1))

        # Perform health check
        local result
        result=$(do_health_check)
        local overall_status
        overall_status=$(echo "${result}" | grep "^OVERALL=" | cut -d= -f2)

        # Track degraded duration
        if [[ "${overall_status}" == "degraded" || "${overall_status}" == "unreachable" || "${overall_status}" == "unhealthy" ]]; then
            _CONSECUTIVE_DEGRADED=$((_CONSECUTIVE_DEGRADED + 1))
            degraded_count=$((degraded_count + 1))
            if [[ -z "${_DEGRADED_START}" ]]; then
                _DEGRADED_START=$(date +%s)
            fi
            _DEGRADED_DURATION=$(( $(date +%s) - _DEGRADED_START ))
        else
            if [[ -n "${_DEGRADED_START}" ]]; then
                # Recovery
                local recovery_duration=$(( $(date +%s) - _DEGRADED_START ))
                _PREV_STATUS="${overall_status}"
            fi
            _CONSECUTIVE_DEGRADED=0
            _DEGRADED_START=""
            _DEGRADED_DURATION=0
        fi

        if [[ "${overall_status}" == "unhealthy" ]]; then
            unhealthy_count=$((unhealthy_count + 1))
        fi
        if [[ "${overall_status}" == "unreachable" ]]; then
            unreachable_count=$((unreachable_count + 1))
        fi

        # Alert if degraded for too long
        if [[ "${_DEGRADED_DURATION}" -gt "${ALERT_AFTER}" ]] && [[ "${_CONSECUTIVE_DEGRADED}" -eq $((ALERT_AFTER / CHECK_INTERVAL + 1)) ]]; then
            warn "Degraded for ${_DEGRADED_DURATION}s (threshold: ${ALERT_AFTER}s)"
        fi

        # Print output
        local output_line
        output_line=$(format_output "${result}")
        echo "${output_line}"

        # Write CSV row
        if [[ -n "${CSV_FILE}" ]]; then
            write_csv "${result}" "${CSV_FILE}"
        fi

        # Exit if --once
        if ${ONCE}; then
            local http_code
            http_code=$(echo "${result}" | grep "^HTTP_CODE=" | cut -d= -f2)
            if [[ "${http_code}" == "000" || "${http_code}" == "" ]]; then
                exit 3
            fi
            case "${overall_status}" in
                healthy)   exit 0 ;;
                degraded)  exit 1 ;;
                unhealthy) exit 2 ;;
                *)         exit 3 ;;
            esac
        fi

        # Detect status transitions
        if [[ -n "${_PREV_STATUS:-}" && "${overall_status}" != "${_PREV_STATUS}" ]]; then
            info "Status transition: ${_PREV_STATUS} -> ${overall_status}"
        fi
        _PREV_STATUS="${overall_status}"

        sleep "${CHECK_INTERVAL}"
    done
}

main "$@"
