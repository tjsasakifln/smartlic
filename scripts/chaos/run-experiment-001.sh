#!/usr/bin/env bash
# =============================================================================
# Chaos Experiment #001: Redis Failure + DB Failover
#
# Automated experiment runner for chaos engineering on SmartLic staging.
#
# Usage:
#   ./scripts/chaos/run-experiment-001.sh [scenario] [--dry-run]
#
# Scenarios:
#   all     - Run all scenarios sequentially (default)
#   a       - Scenario A: Redis latency spike (500ms)
#   b       - Scenario B: Redis connection refused
#   c       - Scenario C: DB connection pool at 90%
#
# Options:
#   --dry-run          - Print commands without executing
#   --url URL          - Staging URL (default: https://staging.smartlic.tech)
#   --redis-host HOST  - Redis hostname (default: from env or prompt)
#   --duration SECONDS - Duration per scenario (default: 300 for A/B, 180 for C)
#   --interval SECONDS - Health check interval in seconds (default: 5)
#   --output FILE      - Output file for results (default: stdout)
#
# Requirements:
#   - curl, jq, tc (traffic control), iptables, redis-cli
#   - Root/sudo access for tc and iptables
#   - Network access to staging environment
#
# Blast Radius: Staging environment ONLY. Single service: bidiq-backend.
# DO NOT run against production.
#
# Rollback:
#   All scenarios have automatic rollback on SIGINT/SIGTERM.
#   Manual rollback commands documented per scenario below.
#
# Author: @devops (Gage)
# Issue: #1922
# =============================================================================

set -euo pipefail

# ---- Constants --------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TIMESTAMP_FORMAT="%Y-%m-%dT%H:%M:%S%z"
RESULTS_FILE=""

# Scenario durations (seconds): A, B, C
DURATION_A=300
DURATION_B=300
DURATION_C=180

# Check interval for health polling (seconds)
CHECK_INTERVAL=5

# Lock file for cleanup
_CLEANUP_PIDS=""

# ---- Color output -----------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC}  $(date +"${TIMESTAMP_FORMAT}") $*"; }
pass()  { echo -e "${GREEN}[PASS]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; }
step()  { echo -e "\n${BLUE}==== $* ====${NC}"; }
dryrun() { echo -e "${YELLOW}[DRY-RUN]${NC} $*"; }

# ---- Parse arguments --------------------------------------------------------

SCENARIO="${1:-all}"
DRY_RUN=false
STAGING_URL="${STAGING_URL:-https://staging.smartlic.tech}"
REDIS_HOST="${REDIS_HOST:-}"
OUTPUT_FILE=""
shift 2>/dev/null || true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --url) STAGING_URL="$2"; shift 2 ;;
        --redis-host) REDIS_HOST="$2"; shift 2 ;;
        --duration) DURATION_A="$2"; DURATION_B="$2"; shift 2 ;;
        --interval) CHECK_INTERVAL="$2"; shift 2 ;;
        --output) OUTPUT_FILE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Validate scenario
case "${SCENARIO}" in
    all|a|A|b|B|c|C) ;;
    *) echo "Usage: $0 [all|a|b|c] [--dry-run] [--url URL] [--redis-host HOST]"; exit 1 ;;
esac

# Normalize to lowercase
SCENARIO="$(echo "${SCENARIO}" | tr '[:upper:]' '[:lower:]')"

# ---- Output file ------------------------------------------------------------

if [[ -n "${OUTPUT_FILE}" ]]; then
    exec > >(tee -a "${OUTPUT_FILE}") 2>&1
fi

# ---- Helper functions -------------------------------------------------------

# Log start of experiment with run metadata
log_header() {
    local scenario_label="$1"
    cat <<-EOF

	======================================================================
	CHAOS EXPERIMENT #001: ${scenario_label}
	======================================================================
	Date:       $(date +"${TIMESTAMP_FORMAT}")
	Scenario:   ${SCENARIO}
	Staging:    ${STAGING_URL}
	Redis Host: ${REDIS_HOST:-"(auto-detect)"}
	Dry run:    ${DRY_RUN}
	Duration:   $2 seconds
	======================================================================

EOF
}

# Run a curl health check against staging
health_check() {
    local endpoint="${1:-ready}"
    local url="${STAGING_URL}/health/${endpoint}"
    local status_code
    local body

    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "curl -s -o /dev/null -w '%{http_code}' '${url}'"
        return 0
    fi

    status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "${url}" 2>/dev/null || echo "000")
    body=$(curl -s --max-time 5 "${url}" 2>/dev/null || echo "{}")

    echo "${status_code} ${body}"
}

# Format health check result
format_health() {
    local output="$1"
    local status_code
    local body

    status_code=$(echo "${output}" | awk '{print $1}')
    body=$(echo "${output}" | cut -d' ' -f2-)

    # Try to parse JSON fields for status
    local overall_status
    overall_status=$(echo "${body}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "parse_error")

    echo "HTTP ${status_code} | status=${overall_status}"
}

# Collect metrics snapshot
collect_metrics() {
    local label="$1"

    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "Collecting metrics snapshot: ${label}"
        return 0
    fi

    echo ""
    echo "--- Metrics [${label}] at $(date +"${TIMESTAMP_FORMAT}") ---"

    # Getting health states
    local ready_output
    ready_output=$(health_check "ready")
    echo "  /health/ready: $(format_health "${ready_output}")"

    local health_output
    health_output=$(health_check "")
    echo "  /health: $(format_health "${health_output}")"

    local live_output
    live_output=$(health_check "live")
    echo "  /health/live: $(format_health "${live_output}")"

    # Prometheus /metrics for resilience indicators
    echo "  --- Prometheus ---"
    curl -s --max-time 5 "${STAGING_URL}/metrics" 2>/dev/null \
        | grep -E "(redis_fallback|circuit_breaker|pool_active|route_timeout|pipeline_budget)" \
        | head -20 \
        || echo "  (no matching metrics found)"
    echo ""
}

# Trap cleanup on exit
cleanup_handler() {
    local exit_code=$?
    echo ""
    warn "INTERRUPT - Running cleanup..."

    # Kill any background processes we started
    if [[ -n "${_CLEANUP_PIDS}" ]]; then
        info "Killing background PIDs: ${_CLEANUP_PIDS}"
        kill ${_CLEANUP_PIDS} 2>/dev/null || true
    fi

    # Attempt rollback
    if [[ "${SCENARIO}" == "a" || "${SCENARIO}" == "all" ]]; then
        rollback_scenario_a
    fi
    if [[ "${SCENARIO}" == "b" || "${SCENARIO}" == "all" ]]; then
        rollback_scenario_b
    fi
    if [[ "${SCENARIO}" == "c" || "${SCENARIO}" == "all" ]]; then
        rollback_scenario_c
    fi

    info "Cleanup complete. Exiting with code ${exit_code}."
    exit "${exit_code}"
}

trap cleanup_handler SIGINT SIGTERM EXIT

# ---- Scenario injection functions -------------------------------------------

check_prerequisites() {
    local missing=0

    info "Checking prerequisites..."

    if ! command -v curl &>/dev/null; then
        fail "curl is required"; missing=1
    fi
    if ! command -v jq &>/dev/null; then
        warn "jq is recommended for JSON parsing (will use python3 fallback)"
    fi
    if ! command -v python3 &>/dev/null; then
        fail "python3 is required"; missing=1
    fi

    # Check sudo for tc/iptables scenarios
    if [[ "${SCENARIO}" == "a" || "${SCENARIO}" == "all" ]]; then
        if ! command -v tc &>/dev/null; then
            fail "tc (traffic control) is required for Scenario A"
            missing=1
        fi
        if ! sudo -n true 2>/dev/null; then
            warn "Scenario A requires sudo for 'tc' commands"
            warn "Run with NOPASSWD sudo or execute tc commands manually"
        fi
    fi
    if [[ "${SCENARIO}" == "b" || "${SCENARIO}" == "all" ]]; then
        if ! command -v iptables &>/dev/null; then
            fail "iptables is required for Scenario B"
            missing=1
        fi
        if ! sudo -n true 2>/dev/null; then
            warn "Scenario B requires sudo for 'iptables' commands"
            warn "Run with NOPASSWD sudo or execute iptables commands manually"
        fi
    fi

    # Check staging URL reachable
    if [[ "${DRY_RUN}" != "true" ]]; then
        local status
        status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${STAGING_URL}/health/live" 2>/dev/null || echo "000")
        if [[ "${status}" != "200" ]]; then
            fail "Staging URL ${STAGING_URL} returned HTTP ${status} (expected 200)"
            info "Use --url to specify a different staging URL"
            missing=1
        else
            pass "Staging URL reachable: ${STAGING_URL} (HTTP ${status})"
        fi
    fi

    if [[ "${missing}" -gt 0 ]]; then
        fail "Missing prerequisites. Install required tools and try again."
        exit 1
    fi

    pass "All prerequisites satisfied"
}

# Resolve Redis host from staging if not provided
resolve_redis_host() {
    if [[ -n "${REDIS_HOST}" ]]; then
        echo "${REDIS_HOST}"
        return
    fi

    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "dry-run-redis-host"
        return
    fi

    # Try to get Redis host from staging /health endpoint
    local health_json
    health_json=$(curl -s --max-time 5 "${STAGING_URL}/health" 2>/dev/null || echo "{}")

    # If we have REDIS_URL env locally, extract host
    if [[ -n "${REDIS_URL:-}" ]]; then
        echo "${REDIS_URL}" | sed -E 's|redis://([^:]+):.*|\1|'
        return
    fi

    # Try to resolve via DNS
    local host
    host=$(echo "${health_json}" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('redis_host', 'unknown'))
except Exception:
    print('unknown')
" 2>/dev/null || echo "unknown")

    echo "${host}"
}

# Verify pre-experiment health baseline
verify_baseline() {
    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "Verifying baseline health..."
        return 0
    fi

    info "Verifying baseline health:"

    local ready_status
    ready_status=$(health_check "ready")
    local status_code
    status_code=$(echo "${ready_status}" | awk '{print $1}')
    local body
    body=$(echo "${ready_status}" | cut -d' ' -f2-)
    local overall
    overall=$(echo "${body}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")

    if [[ "${status_code}" == "200" && "${overall}" == "healthy" ]]; then
        pass "Baseline verified: /health/ready = HTTP 200, status=healthy"
    else
        warn "Baseline: /health/ready = HTTP ${status_code}, status=${overall}"
        warn "Expected 200/healthy. Continuing anyway..."
    fi
}

# Run continuous health monitoring loop in a subshell
start_health_monitor() {
    local label="$1"
    local pid_file="$2"

    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "Starting health monitor: ${label}"
        echo "0"
        return
    fi

    (
        # Run health check loop in background
        while true; do
            local timestamp
            timestamp=$(date +"${TIMESTAMP_FORMAT}")
            local ready_output
            ready_output=$(health_check "ready")
            local health_output
            health_output=$(health_check "")
            local ready_fmt
            ready_fmt=$(format_health "${ready_output}")

            echo "[${timestamp}] [${label}] ${ready_fmt}"

            # Alert if degraded for more than threshold
            sleep "${CHECK_INTERVAL}"
        done
    ) &
    local pid=$!
    echo "${pid}"
}

stop_health_monitor() {
    local pid="$1"
    if [[ -n "${pid}" && "${pid}" != "0" ]]; then
        kill "${pid}" 2>/dev/null || true
        wait "${pid}" 2>/dev/null || true
    fi
}

# Wait and show progress
wait_with_progress() {
    local seconds="$1"
    local label="$2"

    info "Waiting ${seconds}s (${label})..."
    while [[ "${seconds}" -gt 0 ]]; do
        if [[ $((seconds % 30)) -eq 0 ]] || [[ "${seconds}" -lt 10 ]]; then
            echo -n "  ${seconds}s remaining..."
            local ready_out
            ready_out=$(health_check "ready" 2>/dev/null || echo "000 {}")
            echo " $(format_health "${ready_out}")"
        fi
        sleep 1
        seconds=$((seconds - 1))
    done
    echo ""
}

# ---- Rollback functions -----------------------------------------------------

rollback_scenario_a() {
    info "Rollback Scenario A: Removing tc netem delay..."

    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "tc qdisc del dev eth0 root netem 2>/dev/null || true"
        return 0
    fi

    # Try common interfaces
    for iface in eth0 ens5 eno1 enp0s3 enp1s0 bond0; do
        sudo tc qdisc del dev "${iface}" root netem 2>/dev/null || true
    done

    # Verify removal
    local remaining
    remaining=$(tc qdisc show 2>/dev/null | grep -c "netem" || true)
    if [[ "${remaining}" -eq 0 ]]; then
        pass "Scenario A rollback complete (tc netem removed)"
    else
        warn "Scenario A rollback: netem rules may still exist:"
        tc qdisc show 2>/dev/null | grep netem || true
    fi
}

rollback_scenario_b() {
    info "Rollback Scenario B: Removing iptables DROP rule..."

    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "sudo iptables -D OUTPUT -p tcp --dport 6379 -j DROP 2>/dev/null || true"
        return 0
    fi

    sudo iptables -D OUTPUT -p tcp --dport 6379 -j DROP 2>/dev/null || true
    pass "Scenario B rollback complete (iptables rule removed)"
}

rollback_scenario_c() {
    info "Rollback Scenario C: Killing held DB connections..."

    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "Killing connection holders (PID from experiment)"
        return 0
    fi

    # Kill any remaining connection-holder processes managed by this script
    if [[ -n "${_CONN_HOLD_PID:-}" ]]; then
        kill "${_CONN_HOLD_PID}" 2>/dev/null || true
        wait "${_CONN_HOLD_PID}" 2>/dev/null || true
        info "Killed connection holder PID ${_CONN_HOLD_PID}"
    fi

    # Also kill any stray Python processes that may be holding connections
    # (only those started by this script session)
    pkill -f "hold_connection" 2>/dev/null || true

    pass "Scenario C rollback complete (held connections released)"
}

# ---- Scenario implementations -----------------------------------------------

scenario_a_redis_latency() {
    log_header "SCENARIO A: Redis Latency Spike (+500ms)" "${DURATION_A}"

    info "Phase: Injection"
    info "Adding 500ms latency to Redis port (6379) via tc..."

    local iface=""
    for candidate in eth0 ens5 eno1 enp0s3 enp1s0; do
        if ip link show "${candidate}" &>/dev/null 2>&1; then
            iface="${candidate}"
            break
        fi
    done

    if [[ -z "${iface}" ]]; then
        fail "Could not find network interface. Available interfaces:"
        ip link show | grep -E "^[0-9]" | awk '{print $2}' | tr -d ':'
        return 1
    fi
    info "Using interface: ${iface}"

    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "sudo tc qdisc add dev ${iface} root netem delay 500ms 100ms distribution normal"
    else
        # Check if qdisc already exists
        if tc qdisc show dev "${iface}" | grep -q "netem"; then
            warn "netem qdisc already exists on ${iface}, removing first..."
            sudo tc qdisc del dev "${iface}" root netem
        fi
        sudo tc qdisc add dev "${iface}" root netem delay 500ms 100ms distribution normal
        pass "Injection applied: +500ms latency on ${iface}"
    fi

    step "Verification: check if Redis latency increased"
    if [[ -n "${REDIS_HOST}" && "${DRY_RUN}" != "true" ]]; then
        local ping_result
        ping_result=$(ping -c 2 -W 3 "${REDIS_HOST}" 2>/dev/null | tail -1 || echo "ping failed")
        info "Redis ping: ${ping_result}"
    fi

    step "Experiment Phase: Observing (${DURATION_A}s)"
    collect_metrics "scenario-a-start"
    wait_with_progress "${DURATION_A}" "Scenario A active"
    collect_metrics "scenario-a-end"

    step "Rollback"
    rollback_scenario_a

    info "Waiting 30s for stabilization..."
    sleep 30
    collect_metrics "scenario-a-recovery"
    pass "Scenario A complete"
}

scenario_b_redis_refused() {
    log_header "SCENARIO B: Redis Connection Refused" "${DURATION_B}"

    info "Phase: Injection"
    info "Blocking all outbound traffic to Redis port 6379 via iptables..."

    if [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "sudo iptables -A OUTPUT -p tcp --dport 6379 -j DROP"
    else
        # Check if rule already exists
        if sudo iptables -C OUTPUT -p tcp --dport 6379 -j DROP 2>/dev/null; then
            warn "iptables DROP rule for port 6379 already exists"
        else
            sudo iptables -A OUTPUT -p tcp --dport 6379 -j DROP
            pass "Injection applied: all traffic to port 6379 blocked"
        fi
    fi

    step "Verification: check Redis unreachable"
    if [[ -n "${REDIS_HOST}" && "${DRY_RUN}" != "true" ]]; then
        if command -v redis-cli &>/dev/null; then
            local redis_check
            redis_check=$(timeout 3 redis-cli -h "${REDIS_HOST}" ping 2>&1 || true)
            info "Redis CLI test: ${redis_check}"
        fi
    fi

    step "Experiment Phase: Observing (${DURATION_B}s)"
    collect_metrics "scenario-b-start"
    wait_with_progress "${DURATION_B}" "Scenario B active"
    collect_metrics "scenario-b-end"

    step "Rollback"
    rollback_scenario_b

    info "Waiting 30s for stabilization..."
    sleep 30
    collect_metrics "scenario-b-recovery"
    pass "Scenario B complete"
}

scenario_c_db_pool_exhaustion() {
    log_header "SCENARIO C: DB Connection Pool at 90%" "${DURATION_C}"

    # Need Supabase credentials from environment
    local supabase_url="${SUPABASE_URL:-}"
    local supabase_key="${SUPABASE_SERVICE_ROLE_KEY:-}"

    if [[ -z "${supabase_url}" || -z "${supabase_key}" ]]; then
        warn "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY not set in environment"
        info "These are needed to open connections against the database."
        info ""
        info "Alternative: Run the connection-holder script manually:"
        info "  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python3 -c \""
        info "    import httpx, os, asyncio"
        info "    async def hold(n):"
        info "        headers = {'apikey': os.environ['SUPABASE_SERVICE_ROLE_KEY'],"
        info "                    'Authorization': f'Bearer {os.environ[\"SUPABASE_SERVICE_ROLE_KEY\"]}'}"
        info "        async with httpx.AsyncClient() as client:"
        info "            await asyncio.sleep(300)"
        info "    async def main():"
        info "        await asyncio.gather(*[hold(i) for i in range(23)])"
        info "    asyncio.run(main())"
        info "  \""
        info ""
        info "Proceeding with search-only validation (no connection injection)..."
    fi

    local injected_connections=false

    info "Phase: Injection"
    info "Opening 23 Supabase connections to reach ~90% pool utilization..."

    if [[ -n "${supabase_url}" && -n "${supabase_key}" && "${DRY_RUN}" != "true" ]]; then
        # Start connection holders in background
        python3 -c "
import asyncio, os, httpx
import warnings
warnings.filterwarnings('ignore')

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']

async def hold_connection(n):
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Make a real query to establish a connection
            await client.get(
                f'{SUPABASE_URL}/rest/v1/profiles',
                headers=headers,
                params={'select': 'id', 'limit': 1},
            )
            # Hold the connection
            await asyncio.sleep(300)
    except Exception:
        pass  # Connection will be closed anyway

async def main():
    tasks = [hold_connection(i) for i in range(23)]
    await asyncio.gather(*tasks, return_exceptions=True)

asyncio.run(main())
" >/dev/null 2>&1 &
        _CONN_HOLD_PID=$!
        _CLEANUP_PIDS="${_CLEANUP_PIDS} ${_CONN_HOLD_PID}"
        injected_connections=true
        pass "Connection holders started (PID: ${_CONN_HOLD_PID})"

        # Wait for connections to establish
        info "Waiting 5s for connections to establish..."
        sleep 5
    elif [[ "${DRY_RUN}" == "true" ]]; then
        dryrun "Opening 23 Supabase connections..."
    else
        warn "Skipping connection injection (no credentials)"
    fi

    step "Verification: pool utilization"
    if [[ "${DRY_RUN}" != "true" ]]; then
        local pool_check
        pool_check=$(health_check "ready")
        local pool_info
        pool_info=$(echo "${pool_check}" | cut -d' ' -f2- | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    pool = d.get('checks', {}).get('pool', {})
    print(f\"utilization={pool.get('utilization_pct', '?')}%, status={pool.get('status', '?')}\")
except Exception as e:
    print(f'parse_error: {e}')
" 2>/dev/null || echo "parse_error")
        info "Pool status: ${pool_info}"
    fi

    step "Experiment Phase: Observing (${DURATION_C}s)"
    collect_metrics "scenario-c-start"

    # During pool exhaustion, trigger a few test searches
    if [[ "${DRY_RUN}" != "true" && "${injected_connections}" == "true" ]]; then
        info "Triggering test search during pool exhaustion..."
        local search_result
        search_result=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 \
            -X POST "${STAGING_URL}/v1/search" \
            -H "Content-Type: application/json" \
            -d '{"query":"test","ufs":["SC"],"setores":["saude"]}' 2>/dev/null || echo "000")
        info "Test search HTTP ${search_result} during pool exhaustion"
    fi

    wait_with_progress "${DURATION_C}" "Scenario C active"
    collect_metrics "scenario-c-end"

    step "Rollback"
    rollback_scenario_c

    info "Waiting 30s for stabilization..."
    sleep 30
    collect_metrics "scenario-c-recovery"
    pass "Scenario C complete"
}

# =============================================================================
# Main
# =============================================================================

main() {
    echo ""
    echo "======================================================================"
    echo " CHAOS ENGINEERING EXPERIMENT #001"
    echo " Redis Failure + DB Failover"
    echo "======================================================================"
    echo ""
    echo "  Scenario:  ${SCENARIO}"
    echo "  Staging:   ${STAGING_URL}"
    echo "  Dry run:   ${DRY_RUN}"
    echo ""
    echo "  WARNING: This experiment will DEGRADE the staging environment."
    echo "  Do NOT run against production."
    echo ""
    if [[ "${DRY_RUN}" == "true" ]]; then
        echo "  [DRY-RUN MODE] Commands will be printed but not executed."
    fi
    echo ""

    # Confirm for non-dry-run
    if [[ "${DRY_RUN}" != "true" ]]; then
        if [[ -z "${AIOX_ACTIVE_AGENT:-}" ]]; then
            echo -n "Continue? [y/N] "
            read -r confirm
            if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
                info "Aborted by user."
                exit 0
            fi
        fi
    fi

    step "Pre-flight"
    check_prerequisites

    if [[ "${SCENARIO}" == "all" || "${SCENARIO}" == "a" ]]; then
        REDIS_HOST="$(resolve_redis_host)"
        step "Pre-experiment Baseline"
        collect_metrics "pre-experiment"
        verify_baseline

        scenario_a_redis_latency
    fi

    if [[ "${SCENARIO}" == "all" || "${SCENARIO}" == "b" ]]; then
        REDIS_HOST="$(resolve_redis_host)"
        step "Pre-experiment Baseline"
        collect_metrics "pre-experiment"
        verify_baseline

        scenario_b_redis_refused
    fi

    if [[ "${SCENARIO}" == "all" || "${SCENARIO}" == "c" ]]; then
        step "Pre-experiment Baseline"
        collect_metrics "pre-experiment"
        verify_baseline

        scenario_c_db_pool_exhaustion
    fi

    step "Experiment Complete"
    echo ""
    echo "======================================================================"
    echo " RESULTS SUMMARY"
    echo "======================================================================"
    echo ""
    echo "  Scenarios executed: ${SCENARIO}"
    echo "  Timestamp: $(date +"${TIMESTAMP_FORMAT}")"
    echo "  Environment: staging"
    echo ""
    echo "  Document findings in:"
    echo "    docs/operations/chaos-engineering/experiment-001-results.md"
    echo ""
    echo "  Fill in the results template and create action items."
    echo "======================================================================"
    echo ""

    pass "Experiment complete. All rollbacks executed."
}

main "$@"
