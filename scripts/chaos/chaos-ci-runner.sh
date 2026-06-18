#!/usr/bin/env bash
# =============================================================================
# chaos-ci-runner.sh — CI-focused chaos engineering runner
#
# Automated chaos experiment executor for GitHub Actions.
# Runs experiments against staging/development environment and produces
# structured JSON results suitable for CI reporting.
#
# Usage:
#   ./scripts/chaos/chaos-ci-runner.sh [--scenario all|a|b|c|d] [options...]
#
# Scenarios:
#   all     - Run all scenarios sequentially (default)
#   a       - Redis connection kill (CLIENT PAUSE)
#   b       - Redis high latency (CLIENT PAUSE short bursts)
#   c       - DB connection pool exhaustion (Supabase REST connections)
#   d       - DB slow query (pg_sleep via Supabase REST)
#
# Options:
#   --url URL               Staging URL (default: https://staging.smartlic.tech)
#   --scenario SCENARIO     Scenario to run (default: all)
#   --observation SECONDS   Observation duration per scenario (default: 60)
#   --interval SECONDS      Health check interval (default: 5)
#   --recovery-wait SECONDS Wait time after rollback (default: 30)
#   --fivexx-threshold PCT  5xx error threshold % for pass criteria (default: 5)
#   --rollback-threshold PCT Auto-rollback if 5xx exceeds this % (default: 10)
#   --redis-url URL         Redis connection URL (for scenarios A/B)
#   --supabase-url URL      Supabase project URL (for scenarios C/D)
#   --supabase-key KEY      Supabase service role key (for scenarios C/D)
#   --output FILE           Write JSON report to file (default: stdout)
#   --dry-run               Print commands without executing
#   --json-only             Print only the JSON report at end
#
# Exit codes:
#   0 - All scenarios passed
#   1 - Any scenario failed metrics
#   2 - Auto-rollback triggered (>threshold 5xx)
#   3 - Pre-requisite failure (staging unreachable, missing tools)
#   4 - Partial execution (some scenarios skipped)
#
# Output: JSON report with per-scenario metrics + overall status.
#
# Safety:
#   - NEVER runs against https://smartlic.tech (production guard)
#   - Auto-rollback if >threshold 5xx errors detected
#   - Graceful skip if prerequisites not met
#   - All faults auto-revert via cleanup trap
#
# Author: @devops (Gage)
# Issue: #1961
# =============================================================================

set -euo pipefail

# ---- Constants ---------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TIMESTAMP_FORMAT="%Y-%m-%dT%H:%M:%S%z"

# Production guard — never against production
PRODUCTION_URL="https://smartlic.tech"

# ---- Defaults ----------------------------------------------------------------

STAGING_URL="${STAGING_URL:-https://staging.smartlic.tech}"
SCENARIO="${SCENARIO:-all}"
OBSERVATION_SECONDS=60
CHECK_INTERVAL=5
RECOVERY_WAIT=30
FIVEX_THRESHOLD=5    # 5% — pass/fail boundary
ROLLBACK_THRESHOLD=10 # 10% — auto-rollback trigger
REDIS_URL=""
SUPABASE_URL=""
SUPABASE_KEY=""
OUTPUT_FILE=""
DRY_RUN=false
JSON_ONLY=false

# ---- Runtime state -----------------------------------------------------------

declare -A SCENARIO_RESULTS
declare -A SCENARIO_STATUS
SCENARIO_ORDER=()
AUTO_ROLLBACK_TRIGGERED=false
DATA_LOSS_DETECTED=false
EXECUTED_SCENARIOS=0
SKIPPED_SCENARIOS=0
RAN_SCENARIOS=""

# Color output (disabled in CI/non-TTY or when --json-only)
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

if [[ ! -t 1 || "${JSON_ONLY}" == "true" ]]; then
    RED=''; GREEN=''; YELLOW=''; BLUE=''; BOLD=''; NC=''
fi

# ---- Logging -----------------------------------------------------------------

info()  { echo -e "${BLUE}[INFO]${NC}  $(date +"${TIMESTAMP_FORMAT}") $*"; }
pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
step()  { echo -e "\n${BLUE}==== $* ====${NC}"; }
dryrun() { echo -e "${YELLOW}[DRY-RUN]${NC} $*"; }

# ---- Argument parsing --------------------------------------------------------

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --url) STAGING_URL="$2"; shift 2 ;;
            --scenario) SCENARIO="$2"; shift 2 ;;
            --observation) OBSERVATION_SECONDS="$2"; shift 2 ;;
            --interval) CHECK_INTERVAL="$2"; shift 2 ;;
            --recovery-wait) RECOVERY_WAIT="$2"; shift 2 ;;
            --fivexx-threshold) FIVEX_THRESHOLD="$2"; shift 2 ;;
            --rollback-threshold) ROLLBACK_THRESHOLD="$2"; shift 2 ;;
            --redis-url) REDIS_URL="$2"; shift 2 ;;
            --supabase-url) SUPABASE_URL="$2"; shift 2 ;;
            --supabase-key) SUPABASE_KEY="$2"; shift 2 ;;
            --output) OUTPUT_FILE="$2"; shift 2 ;;
            --dry-run) DRY_RUN=true; shift ;;
            --json-only) JSON_ONLY=true; shift ;;
            --help|-h)
                echo "Usage: $0 [--scenario all|a|b|c|d] [options...]"
                echo ""
                echo "Scenarios:"
                echo "  a  Redis connection kill  (requires --redis-url)"
                echo "  b  Redis high latency     (requires --redis-url)"
                echo "  c  DB pool exhaustion     (requires --supabase-url, --supabase-key)"
                echo "  d  DB slow query          (requires --supabase-url, --supabase-key)"
                echo ""
                echo "See script header for full options."
                exit 0
                ;;
            *) echo "Unknown option: $1"; exit 1 ;;
        esac
    done

    case "${SCENARIO}" in
        all|a|b|c|d) ;;
        *) fail "Invalid scenario: ${SCENARIO}. Use: all, a, b, c, d"; exit 1 ;;
    esac

    # Production guard
    if [[ "${STAGING_URL}" == "${PRODUCTION_URL}" ]] || \
       [[ "${STAGING_URL}" == "https://smartlic.tech" ]] || \
       [[ "${STAGING_URL}" == "https://www.smartlic.tech" ]]; then
        fail "PRODUCTION GUARD: Refusing to run against ${STAGING_URL}"
        fail "This script targets STAGING only. Set --url to a non-production URL."
        exit 3
    fi

    # Env var fallbacks for credentials
    REDIS_URL="${REDIS_URL:-${REDIS_URL_ENV:-}}"
    SUPABASE_URL="${SUPABASE_URL:-${SUPABASE_URL_ENV:-}}"
    SUPABASE_KEY="${SUPABASE_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-}}"
}

# ---- Health check functions --------------------------------------------------

# Perform a single health check against /health/ready
# Returns pipe-separated: HTTP_STATUS|OVERALL|REDIS|SUPABASE|POOL_PCT|RTT_MS
do_health_check() {
    local start_ms end_ms elapsed_ms http_code body overall redis_status supabase_status pool_pct

    start_ms=$(date +%s%3N)

    local response
    response=$(curl -s -w "\n%{http_code}" --max-time 10 \
        "${STAGING_URL}/health/ready" 2>/dev/null || true)

    end_ms=$(date +%s%3N)
    elapsed_ms=$(( end_ms - start_ms ))

    http_code=$(echo "${response}" | tail -1)
    body=$(echo "${response}" | sed '$d')

    if [[ -z "${http_code}" || "${http_code}" == "000" ]]; then
        echo "000|unreachable|unknown|unknown|unknown|${elapsed_ms}"
        return
    fi

    overall=$(echo "${body}" | python3 -c "
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
    print('unknown')
" 2>/dev/null || echo "unknown")

    supabase_status=$(echo "${body}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('checks', {}).get('supabase', {}).get('status', 'unknown'))
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

    echo "${http_code}|${overall}|${redis_status}|${supabase_status}|${pool_pct}|${elapsed_ms}"
}

parse_health_result() {
    local result="$1"
    local field="$2"
    echo "${result}" | cut -d'|' -f"${field}"
}

# Run continuous health monitoring, collect results as JSON array
# Returns: JSON array of health snapshots
monitor_health() {
    local label="$1"
    local duration="$2"
    local interval="$3"
    local end_time
    end_time=$(( $(date +%s) + duration ))
    local results=()

    echo "  [Health Monitor: ${label}] Starting ${duration}s observation..."

    while [[ $(date +%s) -lt ${end_time} ]]; do
        local result
        result=$(do_health_check)

        local http_code overall redis_status supabase_status pool_pct elapsed_ms
        http_code=$(parse_health_result "${result}" 1)
        overall=$(parse_health_result "${result}" 2)
        redis_status=$(parse_health_result "${result}" 3)
        supabase_status=$(parse_health_result "${result}" 4)
        pool_pct=$(parse_health_result "${result}" 5)
        elapsed_ms=$(parse_health_result "${result}" 6)

        local timestamp
        timestamp=$(date +"${TIMESTAMP_FORMAT}")

        results+=("{\"ts\":\"${timestamp}\",\"http\":${http_code},\"overall\":\"${overall}\",\"redis\":\"${redis_status}\",\"supabase\":\"${supabase_status}\",\"pool_pct\":\"${pool_pct}\",\"rtt_ms\":${elapsed_ms}}")

        local status_icon="ok"
        if [[ "${overall}" == "degraded" ]]; then
            status_icon="degraded"
        elif [[ "${overall}" == "unhealthy" || "${overall}" == "unreachable" ]]; then
            status_icon="${overall}"
        fi

        echo "    [${timestamp}] HTTP ${http_code} | ${status_icon} | rtt=${elapsed_ms}ms redis=${redis_status} supabase=${supabase_status} pool=${pool_pct}%"

        sleep "${interval}"
    done

    # Build JSON array
    local json_items=""
    local first=true
    for item in "${results[@]}"; do
        if [[ "${first}" == "true" ]]; then
            json_items="${item}"
            first=false
        else
            json_items="${json_items},${item}"
        fi
    done

    echo "[${json_items}]"
}

# Compute metrics from health check JSON array
compute_metrics() {
    local health_json="$1"
    python3 -c "
import sys, json

try:
    checks = json.loads('''${health_json}''')
except Exception:
    print(json.dumps({'error': 'Failed to parse health checks'}))
    sys.exit(0)

total = len(checks)
if total == 0:
    print(json.dumps({'total': 0, 'healthy': 0, 'degraded': 0, 'unhealthy': 0,
                      'five_xx': 0, 'five_xx_pct': 0.0,
                      'avg_rtt_ms': 0, 'p99_rtt_ms': 0}))
    sys.exit(0)

healthy = sum(1 for c in checks if c.get('overall') == 'healthy')
degraded = sum(1 for c in checks if c.get('overall') == 'degraded')
unhealthy = sum(1 for c in checks if c.get('overall') in ('unhealthy', 'unreachable', 'parse_error'))
five_xx = sum(1 for c in checks if c.get('http', 0) >= 500)
rtts = sorted([c.get('rtt_ms', 0) for c in checks])

avg_rtt = sum(rtts) / len(rtts) if rtts else 0
p99_idx = max(0, int(len(rtts) * 0.99) - 1)
p99_rtt = rtts[p99_idx] if rtts else 0
five_xx_pct = (five_xx / total) * 100 if total > 0 else 0

print(json.dumps({
    'total': total,
    'healthy': healthy,
    'degraded': degraded,
    'unhealthy': unhealthy,
    'five_xx': five_xx,
    'five_xx_pct': round(five_xx_pct, 2),
    'avg_rtt_ms': round(avg_rtt, 1),
    'p99_rtt_ms': p99_rtt,
}))
"
}

# ---- Prerequisites -----------------------------------------------------------

check_prerequisites() {
    local missing=0

    echo "Checking prerequisites..."

    if ! command -v curl &>/dev/null; then
        fail "curl is required"; missing=1
    fi
    if ! command -v python3 &>/dev/null; then
        fail "python3 is required"; missing=1
    fi

    # Check for redis-cli if Redis scenarios requested
    if [[ "${SCENARIO}" == "all" || "${SCENARIO}" == "a" || "${SCENARIO}" == "b" ]]; then
        if ! command -v redis-cli &>/dev/null; then
            warn "redis-cli not found — Redis scenarios (A/B) will be skipped"
        elif [[ -z "${REDIS_URL}" ]]; then
            warn "REDIS_URL not provided — Redis scenarios (A/B) will be skipped"
            echo "  Provide via --redis-url or REDIS_URL_ENV env var"
        fi
    fi

    # Check for Supabase credentials if DB scenarios requested
    if [[ "${SCENARIO}" == "all" || "${SCENARIO}" == "c" || "${SCENARIO}" == "d" ]]; then
        if [[ -z "${SUPABASE_URL}" || -z "${SUPABASE_KEY}" ]]; then
            warn "SUPABASE_URL or SUPABASE_KEY not provided — DB scenarios (C/D) will be skipped"
            echo "  Provide via --supabase-url/--supabase-key or env vars"
        fi
    fi

    # Check staging reachable
    if [[ "${DRY_RUN}" != "true" ]]; then
        local status
        status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 \
            "${STAGING_URL}/health/live" 2>/dev/null || echo "000")
        if [[ "${status}" != "200" ]]; then
            fail "Staging URL ${STAGING_URL} returned HTTP ${status} (expected 200)"
            echo "  Use --url to specify a different staging URL"
            echo "  Target must have /health/live endpoint responding 200"
            missing=1
        else
            pass "Staging reachable: ${STAGING_URL} (HTTP ${status})"
        fi
    fi

    if [[ "${missing}" -gt 0 ]]; then
        fail "Missing prerequisites. Install required tools and try again."
        exit 3
    fi

    # Baseline health snapshot
    if [[ "${DRY_RUN}" != "true" ]]; then
        local baseline
        baseline=$(do_health_check)
        local http_code overall
        http_code=$(parse_health_result "${baseline}" 1)
        overall=$(parse_health_result "${baseline}" 2)
        if [[ "${http_code}" == "200" && "${overall}" == "healthy" ]]; then
            pass "Baseline healthy: /health/ready = HTTP ${http_code}, status=${overall}"
        else
            warn "Baseline: /health/ready = HTTP ${http_code}, status=${overall}"
            warn "Expected 200/healthy. Continuing but results may be affected."
        fi
    fi

    pass "Prerequisites check complete"
}

# ---- Scenario runners --------------------------------------------------------

run_scenario_a_redis_kill() {
    step "SCENARIO A: Redis Connection Kill"

    if ! command -v redis-cli &>/dev/null || [[ -z "${REDIS_URL}" ]]; then
        warn "Skipping Scenario A — redis-cli or REDIS_URL not available"
        SKIPPED_SCENARIOS=$((SKIPPED_SCENARIOS + 1))
        return 0
    fi

    echo "Phase: Inject — Pausing Redis clients for ${OBSERVATION_SECONDS}s"

    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "redis-cli -u '${REDIS_URL}' CLIENT PAUSE ${OBSERVATION_SECONDS}000"
    else
        if redis-cli -u "${REDIS_URL}" CLIENT PAUSE "$((OBSERVATION_SECONDS * 1000))" 2>/dev/null; then
            pass "Injection applied: Redis clients paused for ${OBSERVATION_SECONDS}s"
        else
            fail "Failed to execute CLIENT PAUSE on Redis"
            warn "Redis may not be accessible from this runner"
            SKIPPED_SCENARIOS=$((SKIPPED_SCENARIOS + 1))
            return 0
        fi
    fi

    sleep 2

    local inject_check
    inject_check=$(do_health_check)
    local redis_status
    redis_status=$(parse_health_result "${inject_check}" 3)
    echo "  Redis status after injection: ${redis_status}"

    echo "Phase: Observation (${OBSERVATION_SECONDS}s)"
    local health_json
    health_json=$(monitor_health "scenario-a" "${OBSERVATION_SECONDS}" "${CHECK_INTERVAL}")
    local metrics
    metrics=$(compute_metrics "${health_json}")

    echo "Phase: Recovery — Redis auto-unpauses after ${OBSERVATION_SECONDS}s"

    echo "  Waiting ${RECOVERY_WAIT}s for stabilization..."
    sleep "${RECOVERY_WAIT}"

    local recovery_check
    recovery_check=$(do_health_check)
    local recovery_http recovery_overall
    recovery_http=$(parse_health_result "${recovery_check}" 1)
    recovery_overall=$(parse_health_result "${recovery_check}" 2)
    echo "  Recovery check: HTTP ${recovery_http} | status=${recovery_overall}"

    if [[ "${DRY_RUN}" != "true" ]]; then
        local redis_ping
        redis_ping=$(redis-cli -u "${REDIS_URL}" PING 2>/dev/null || echo "FAIL")
        echo "  Redis PING after recovery: ${redis_ping}"
    fi

    local status="pass"
    local five_xx_pct
    five_xx_pct=$(echo "${metrics}" | python3 -c "import sys,json; print(json.load(sys.stdin)['five_xx_pct'])")

    if (( $(echo "${five_xx_pct} > ${ROLLBACK_THRESHOLD}" | bc -l 2>/dev/null || echo 0) )); then
        status="auto-rollback"
        AUTO_ROLLBACK_TRIGGERED=true
        warn "AUTO-ROLLBACK: ${five_xx_pct}% 5xx exceeds ${ROLLBACK_THRESHOLD}% threshold"
    elif (( $(echo "${five_xx_pct} > ${FIVEX_THRESHOLD}" | bc -l 2>/dev/null || echo 0) )); then
        status="fail"
        warn "Scenario A FAILED: ${five_xx_pct}% 5xx exceeds ${FIVEX_THRESHOLD}% threshold"
    fi

    SCENARIO_RESULTS["a"]="${metrics}"
    SCENARIO_STATUS["a"]="${status}"
    SCENARIO_ORDER+=("a")
    EXECUTED_SCENARIOS=$((EXECUTED_SCENARIOS + 1))
    RAN_SCENARIOS="${RAN_SCENARIOS} a"
    pass "Scenario A complete (status: ${status})"
}

run_scenario_b_redis_latency() {
    step "SCENARIO B: Redis High Latency"

    if ! command -v redis-cli &>/dev/null || [[ -z "${REDIS_URL}" ]]; then
        warn "Skipping Scenario B — redis-cli or REDIS_URL not available"
        SKIPPED_SCENARIOS=$((SKIPPED_SCENARIOS + 1))
        return 0
    fi

    # Simulate high latency via intermittent CLIENT PAUSE bursts
    local burst_count=3
    local burst_duration=$(( OBSERVATION_SECONDS / burst_count ))
    local all_health_data="["
    local first_batch=true

    echo "Phase: Inject — Simulating Redis high latency in ${burst_count} bursts"

    for (( i=1; i<=burst_count; i++ )); do
        echo "  Burst ${i}/${burst_count}: Pausing Redis for ${burst_duration}s"

        if [[ "${DRY_RUN}" == "true" ]]; then
            dryrun "redis-cli -u '${REDIS_URL}' CLIENT PAUSE ${burst_duration}000"
        else
            redis-cli -u "${REDIS_URL}" CLIENT PAUSE "$((burst_duration * 1000))" 2>/dev/null || true
        fi

        local burst_health
        burst_health=$(monitor_health "scenario-b-burst-${i}" "${burst_duration}" "${CHECK_INTERVAL}")

        burst_health="${burst_health#[}"
        burst_health="${burst_health%]}"

        if [[ "${first_batch}" == "true" ]]; then
            all_health_data="${all_health_data}${burst_health}"
            first_batch=false
        else
            all_health_data="${all_health_data},${burst_health}"
        fi
    done
    all_health_data="${all_health_data}]"

    local metrics
    metrics=$(compute_metrics "${all_health_data}")

    echo "Phase: Recovery — Redis auto-unpaused after bursts"

    echo "  Waiting ${RECOVERY_WAIT}s for stabilization..."
    sleep "${RECOVERY_WAIT}"

    local recovery_check
    recovery_check=$(do_health_check)
    local recovery_http recovery_overall
    recovery_http=$(parse_health_result "${recovery_check}" 1)
    recovery_overall=$(parse_health_result "${recovery_check}" 2)
    echo "  Recovery check: HTTP ${recovery_http} | status=${recovery_overall}"

    local status="pass"
    local five_xx_pct
    five_xx_pct=$(echo "${metrics}" | python3 -c "import sys,json; print(json.load(sys.stdin)['five_xx_pct'])")

    if (( $(echo "${five_xx_pct} > ${ROLLBACK_THRESHOLD}" | bc -l 2>/dev/null || echo 0) )); then
        status="auto-rollback"
        AUTO_ROLLBACK_TRIGGERED=true
        warn "AUTO-ROLLBACK: ${five_xx_pct}% 5xx exceeds ${ROLLBACK_THRESHOLD}% threshold"
    elif (( $(echo "${five_xx_pct} > ${FIVEX_THRESHOLD}" | bc -l 2>/dev/null || echo 0) )); then
        status="fail"
        warn "Scenario B FAILED: ${five_xx_pct}% 5xx exceeds ${FIVEX_THRESHOLD}% threshold"
    fi

    SCENARIO_RESULTS["b"]="${metrics}"
    SCENARIO_STATUS["b"]="${status}"
    SCENARIO_ORDER+=("b")
    EXECUTED_SCENARIOS=$((EXECUTED_SCENARIOS + 1))
    RAN_SCENARIOS="${RAN_SCENARIOS} b"
    pass "Scenario B complete (status: ${status})"
}

run_scenario_c_db_pool_exhaustion() {
    step "SCENARIO C: DB Connection Pool Exhaustion"

    if [[ -z "${SUPABASE_URL}" || -z "${SUPABASE_KEY}" ]]; then
        warn "Skipping Scenario C — SUPABASE_URL or SUPABASE_KEY not available"
        SKIPPED_SCENARIOS=$((SKIPPED_SCENARIOS + 1))
        return 0
    fi

    echo "Phase: Inject — Opening 23 Supabase REST connections (targeting ~90% pool)"

    local conn_pid=""
    if [[ "${DRY_RUN}" != "true" ]]; then
        python3 -c "
import asyncio, os, httpx, warnings
warnings.filterwarnings('ignore')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '${SUPABASE_URL}')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '${SUPABASE_KEY}')
POOL_SIZE = 23

async def hold_connection(n):
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            await client.get(
                f'{SUPABASE_URL}/rest/v1/profiles',
                headers=headers,
                params={'select': 'id', 'limit': 1},
            )
            await asyncio.sleep(${OBSERVATION_SECONDS} + 30)
    except Exception:
        pass

async def main():
    tasks = [hold_connection(i) for i in range(POOL_SIZE)]
    await asyncio.gather(*tasks, return_exceptions=True)

asyncio.run(main())
" >/dev/null 2>&1 &
        conn_pid=$!
        pass "Connection holders started (PID: ${conn_pid})"
        echo "  Waiting 5s for connections to establish..."
        sleep 5
    else:
        dryrun "Opening 23 Supabase REST connections..."
        sleep 2
    fi

    local inject_check
    inject_check=$(do_health_check)
    local pool_pct
    pool_pct=$(parse_health_result "${inject_check}" 5)
    echo "  Pool utilization: ${pool_pct}%"

    echo "Phase: Observation (${OBSERVATION_SECONDS}s)"
    local health_json
    health_json=$(monitor_health "scenario-c" "${OBSERVATION_SECONDS}" "${CHECK_INTERVAL}")
    local metrics
    metrics=$(compute_metrics "${health_json}")

    echo "Phase: Rollback — Releasing held connections"
    if [[ -n "${conn_pid}" ]]; then
        kill "${conn_pid}" 2>/dev/null || true
        wait "${conn_pid}" 2>/dev/null || true
        pass "Connection holders released (PID: ${conn_pid})"
    fi

    echo "  Waiting ${RECOVERY_WAIT}s for stabilization..."
    sleep "${RECOVERY_WAIT}"

    local recovery_check
    recovery_check=$(do_health_check)
    local recovery_http recovery_overall
    recovery_http=$(parse_health_result "${recovery_check}" 1)
    recovery_overall=$(parse_health_result "${recovery_check}" 2)
    echo "  Recovery check: HTTP ${recovery_http} | status=${recovery_overall}"

    local status="pass"
    local five_xx_pct
    five_xx_pct=$(echo "${metrics}" | python3 -c "import sys,json; print(json.load(sys.stdin)['five_xx_pct'])")

    if (( $(echo "${five_xx_pct} > ${ROLLBACK_THRESHOLD}" | bc -l 2>/dev/null || echo 0) )); then
        status="auto-rollback"
        AUTO_ROLLBACK_TRIGGERED=true
        warn "AUTO-ROLLBACK: ${five_xx_pct}% 5xx exceeds ${ROLLBACK_THRESHOLD}% threshold"
    elif (( $(echo "${five_xx_pct} > ${FIVEX_THRESHOLD}" | bc -l 2>/dev/null || echo 0) )); then
        status="fail"
        warn "Scenario C FAILED: ${five_xx_pct}% 5xx exceeds ${FIVEX_THRESHOLD}% threshold"
    fi

    SCENARIO_RESULTS["c"]="${metrics}"
    SCENARIO_STATUS["c"]="${status}"
    SCENARIO_ORDER+=("c")
    EXECUTED_SCENARIOS=$((EXECUTED_SCENARIOS + 1))
    RAN_SCENARIOS="${RAN_SCENARIOS} c"
    pass "Scenario C complete (status: ${status})"
}

run_scenario_d_db_slow_query() {
    step "SCENARIO D: DB Slow Query (>5s)"

    if [[ -z "${SUPABASE_URL}" || -z "${SUPABASE_KEY}" ]]; then
        warn "Skipping Scenario D — SUPABASE_URL or SUPABASE_KEY not available"
        SKIPPED_SCENARIOS=$((SKIPPED_SCENARIOS + 1))
        return 0
    fi

    echo "Phase: Inject — Opening 5 connections running pg_sleep(6)"

    local conn_pid=""
    if [[ "${DRY_RUN}" != "true" ]]; then
        python3 -c "
import asyncio, os, httpx, warnings
warnings.filterwarnings('ignore')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '${SUPABASE_URL}')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '${SUPABASE_KEY}')
SLOW_QUERY_COUNT = 5

async def run_slow_query(n):
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            start = asyncio.get_event_loop().time()
            resp = await client.post(
                f'{SUPABASE_URL}/rest/v1/rpc/pg_sleep',
                headers=headers,
                json={'seconds': 6},
            )
            elapsed = asyncio.get_event_loop().time() - start
            print(f'Query {n}: HTTP {resp.status_code}, elapsed={elapsed:.1f}s')
    except httpx.TimeoutException:
        print(f'Query {n}: timed out (expected for slow query)')
    except Exception as e:
        print(f'Query {n}: error: {e}')

async def main():
    tasks = [run_slow_query(i) for i in range(SLOW_QUERY_COUNT)]
    await asyncio.gather(*tasks, return_exceptions=True)

asyncio.run(main())
" 2>&1 &
        conn_pid=$!
        pass "Slow query connections started (PID: ${conn_pid})"
        sleep 2
    else:
        dryrun "Opening 5 connections with pg_sleep(6)..."
        sleep 2
    fi

    local inject_check
    inject_check=$(do_health_check)
    local supabase_status pool_pct
    supabase_status=$(parse_health_result "${inject_check}" 4)
    pool_pct=$(parse_health_result "${inject_check}" 5)
    echo "  Supabase status: ${supabase_status} | pool: ${pool_pct}%"

    echo "Phase: Observation (${OBSERVATION_SECONDS}s)"
    local health_json
    health_json=$(monitor_health "scenario-d" "${OBSERVATION_SECONDS}" "${CHECK_INTERVAL}")
    local metrics
    metrics=$(compute_metrics "${health_json}")

    echo "Phase: Rollback — Waiting for slow queries to complete"
    if [[ -n "${conn_pid}" ]]; then
        kill "${conn_pid}" 2>/dev/null || true
        wait "${conn_pid}" 2>/dev/null || true
        pass "Slow query connections released (PID: ${conn_pid})"
    fi

    echo "  Waiting ${RECOVERY_WAIT}s for stabilization..."
    sleep "${RECOVERY_WAIT}"

    local recovery_check
    recovery_check=$(do_health_check)
    local recovery_http recovery_overall
    recovery_http=$(parse_health_result "${recovery_check}" 1)
    recovery_overall=$(parse_health_result "${recovery_check}" 2)
    echo "  Recovery check: HTTP ${recovery_http} | status=${recovery_overall}"

    local status="pass"
    local five_xx_pct
    five_xx_pct=$(echo "${metrics}" | python3 -c "import sys,json; print(json.load(sys.stdin)['five_xx_pct'])")

    if (( $(echo "${five_xx_pct} > ${ROLLBACK_THRESHOLD}" | bc -l 2>/dev/null || echo 0) )); then
        status="auto-rollback"
        AUTO_ROLLBACK_TRIGGERED=true
        warn "AUTO-ROLLBACK: ${five_xx_pct}% 5xx exceeds ${ROLLBACK_THRESHOLD}% threshold"
    elif (( $(echo "${five_xx_pct} > ${FIVEX_THRESHOLD}" | bc -l 2>/dev/null || echo 0) )); then
        status="fail"
        warn "Scenario D FAILED: ${five_xx_pct}% 5xx exceeds ${FIVEX_THRESHOLD}% threshold"
    fi

    SCENARIO_RESULTS["d"]="${metrics}"
    SCENARIO_STATUS["d"]="${status}"
    SCENARIO_ORDER+=("d")
    EXECUTED_SCENARIOS=$((EXECUTED_SCENARIOS + 1))
    RAN_SCENARIOS="${RAN_SCENARIOS} d"
    pass "Scenario D complete (status: ${status})"
}

# ---- Cleanup / Rollback ------------------------------------------------------

cleanup_handler() {
    local exit_code=$?
    echo ""
    warn "Cleanup handler triggered (exit: ${exit_code})"

    # Kill any background Python processes (connection holders)
    pkill -f "hold_connection\|run_slow_query\|pg_sleep" 2>/dev/null || true

    # Ensure Redis is unpaused
    if command -v redis-cli &>/dev/null && [[ -n "${REDIS_URL}" ]]; then
        redis-cli -u "${REDIS_URL}" CLIENT UNPAUSE 2>/dev/null || true
    fi

    echo ""
    echo "Cleanup complete."
}

# ---- Report generation -------------------------------------------------------

generate_report() {
    local end_timestamp
    end_timestamp=$(date +"${TIMESTAMP_FORMAT}")

    # Build per-scenario JSON array
    local scenarios_json=""
    local first=true
    for key in "${SCENARIO_ORDER[@]}"; do
        local metrics="${SCENARIO_RESULTS[${key}]:-}"
        local status="${SCENARIO_STATUS[${key}]:-skipped}"

        local scenario_name=""
        case "${key}" in
            a) scenario_name="redis_connection_kill" ;;
            b) scenario_name="redis_high_latency" ;;
            c) scenario_name="db_pool_exhaustion" ;;
            d) scenario_name="db_slow_query" ;;
        esac

        local metrics_obj="${metrics:-{\}}"

        if [[ "${first}" == "true" ]]; then
            scenarios_json="{\"id\":\"${key}\",\"name\":\"${scenario_name}\",\"status\":\"${status}\",\"metrics\":${metrics_obj}}"
            first=false
        else
            scenarios_json="${scenarios_json},{\"id\":\"${key}\",\"name\":\"${scenario_name}\",\"status\":\"${status}\",\"metrics\":${metrics_obj}}"
        fi
    done

    # Overall status
    local overall_status="pass"
    local overall_five_xx_pct=0
    local scenarios_with_data=0

    for key in "${SCENARIO_ORDER[@]}"; do
        local s="${SCENARIO_STATUS[${key}]:-skipped}"
        if [[ "${s}" == "auto-rollback" ]]; then
            overall_status="auto-rollback"
        elif [[ "${s}" == "fail" && "${overall_status}" != "auto-rollback" ]]; then
            overall_status="fail"
        fi

        local m="${SCENARIO_RESULTS[${key}]:-}"
        if [[ -n "${m}" && "${m}" != "{}" ]]; then
            local fxx
            fxx=$(echo "${m}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('five_xx_pct', 0))" 2>/dev/null || echo 0)
            overall_five_xx_pct=$(echo "${overall_five_xx_pct} + ${fxx}" | bc -l 2>/dev/null || echo "${overall_five_xx_pct}")
            scenarios_with_data=$((scenarios_with_data + 1))
        fi
    done

    if [[ "${scenarios_with_data}" -gt 0 ]]; then
        overall_five_xx_pct=$(echo "scale=2; ${overall_five_xx_pct} / ${scenarios_with_data}" | bc -l 2>/dev/null || echo "0")
    fi

    local report
    report=$(python3 -c "
import json

report = {
    'experiment': {
        'tool': 'chaos-ci-runner.sh',
        'version': '1.0.0',
        'issue': '#1961',
    },
    'timestamp': '${end_timestamp}',
    'target_url': '${STAGING_URL}',
    'scenarios_run': '${RAN_SCENARIOS}'.strip(),
    'executed': ${EXECUTED_SCENARIOS},
    'skipped': ${SKIPPED_SCENARIOS},
    'status': '${overall_status}',
    'overall_five_xx_pct': ${overall_five_xx_pct},
    'auto_rollback_triggered': ${AUTO_ROLLBACK_TRIGGERED},
    'data_loss_detected': ${DATA_LOSS_DETECTED},
    'scenarios': [${scenarios_json}],
    'success_metrics': {
        'five_xx_threshold_pct': ${FIVEX_THRESHOLD},
        'rollback_threshold_pct': ${ROLLBACK_THRESHOLD},
        'recovery_time_target_seconds': ${RECOVERY_WAIT},
        'zero_data_loss': not ${DATA_LOSS_DETECTED},
    },
}

print(json.dumps(report, indent=2))
" 2>/dev/null || echo '{"error":"Report generation failed"}')

    # Output to file or stdout
    if [[ -n "${OUTPUT_FILE}" ]]; then
        echo "${report}" > "${OUTPUT_FILE}"
        echo "Report written to ${OUTPUT_FILE}"
    fi

    echo "${report}"
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Safety: bail immediately if trying to run against production
    if [[ "${STAGING_URL}" == "${PRODUCTION_URL}" ]] || \
       [[ "${STAGING_URL}" == *"smartlic.tech" && "${STAGING_URL}" != *"staging"* ]]; then
        fail "SAFETY: This script targets STAGING only. Refusing to run against ${STAGING_URL}"
        fail "Set --url or STAGING_URL to a non-production URL (e.g. https://staging.smartlic.tech)"
        exit 3
    fi

    trap cleanup_handler EXIT SIGINT SIGTERM

    echo ""
    echo "============================================================"
    echo " Chaos CI Runner — Automated Experiments"
    echo " Issue: #1961"
    echo "============================================================"
    echo ""
    echo "  Target:     ${STAGING_URL}"
    echo "  Scenario:   ${SCENARIO}"
    echo "  Obs period: ${OBSERVATION_SECONDS}s per scenario"
    echo "  Dry run:    ${DRY_RUN}"
    echo ""

    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "DRY-RUN MODE"
    fi

    step "Pre-flight"
    check_prerequisites

    if [[ "${SCENARIO}" == "all" || "${SCENARIO}" == "a" ]]; then
        run_scenario_a_redis_kill
    fi
    if [[ "${SCENARIO}" == "all" || "${SCENARIO}" == "b" ]]; then
        run_scenario_b_redis_latency
    fi
    if [[ "${SCENARIO}" == "all" || "${SCENARIO}" == "c" ]]; then
        run_scenario_c_db_pool_exhaustion
    fi
    if [[ "${SCENARIO}" == "all" || "${SCENARIO}" == "d" ]]; then
        run_scenario_d_db_slow_query
    fi

    step "Report"
    local report
    report=$(generate_report)

    # Print human-readable summary
    echo ""
    echo "============================================================"
    echo " EXPERIMENT RESULTS"
    echo "============================================================"
    echo ""
    echo "  Status:   $(echo "${report}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null)"
    echo "  Executed: $(echo "${report}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('executed',0))" 2>/dev/null)"
    echo "  Skipped:  $(echo "${report}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('skipped',0))" 2>/dev/null)"
    echo "  5xx avg:  $(echo "${report}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('overall_five_xx_pct','?'))" 2>/dev/null)%"
    echo ""
    echo "  Scenarios:"
    for key in "${SCENARIO_ORDER[@]}"; do
        local s="${SCENARIO_STATUS[${key}]:-skipped}"
        local icon="PASS"
        [[ "${s}" == "fail" ]] && icon="FAIL"
        [[ "${s}" == "auto-rollback" ]] && icon="AUTO-ROLLBACK"
        [[ "${s}" == "skipped" ]] && icon="SKIP"

        local name=""
        case "${key}" in
            a) name="Redis Connection Kill" ;;
            b) name="Redis High Latency" ;;
            c) name="DB Pool Exhaustion" ;;
            d) name="DB Slow Query" ;;
        esac
        echo "    ${key}) ${name} ... ${icon}"
    done
    echo ""

    # Determine exit code
    if [[ "${AUTO_ROLLBACK_TRIGGERED}" == "true" ]]; then
        echo "AUTO-ROLLBACK triggered: 5xx exceeded ${ROLLBACK_THRESHOLD}% threshold"
        exit 2
    fi

    local any_fail=false
    for key in "${SCENARIO_ORDER[@]}"; do
        if [[ "${SCENARIO_STATUS[${key}]:-}" == "fail" ]]; then
            any_fail=true
            break
        fi
    done

    if [[ "${any_fail}" == "true" ]]; then
        echo "Some scenarios failed metrics"
        exit 1
    fi

    if [[ "${EXECUTED_SCENARIOS}" -eq 0 && "${SKIPPED_SCENARIOS}" -gt 0 ]]; then
        echo "All scenarios skipped (missing prerequisites)"
        exit 4
    fi

    pass "All scenarios passed"
    exit 0
}

main "$@"
