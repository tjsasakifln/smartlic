#!/usr/bin/env bash
# =============================================================================
# Smoke Test Script — post-deploy health validation (#1971)
#
# Usage:
#   SMOKE_TEST_API_URL=https://api.smartlic.tech \
#     SMOKE_TEST_FRONTEND_URL=https://smartlic.tech \
#     ./scripts/smoke-test.sh
#   ./scripts/smoke-test.sh                # uses localhost defaults
#   ./scripts/smoke-test.sh --help          # show this message
#
# Tests:
#   (a) GET  /health/live      → 200 (liveness)
#   (b) GET  /health/ready     → 200 (readiness)
#   (c) GET  /v1/sectors       → 200 (public sectors)
#   (d) GET  /observatorio/    → 200 (frontend ISR page)
#   (e) GET  /v1/plans         → 200 (plans)
#   (f) Redis ping             → PONG (if redis-cli or python3+redis available)
#   (g) Supabase connect       → OK (if supabase CLI available)
#   (h) Migrations up-to-date  → clean (if supabase CLI + migrations dir exist)
#
# Env vars:
#   SMOKE_TEST_API_URL          API base URL (default: http://localhost:8000)
#   SMOKE_TEST_FRONTEND_URL     Frontend base URL (default: http://localhost:3000)
#   SMOKE_TEST_REDIS_URL        Redis URL for ping check (default: empty)
#   SMOKE_TEST_EXPECTED_MIGRATIONS  Expected migration count (default: empty)
#
# Returns: 0 = all checks passed, 1 = any check failed
# =============================================================================

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
API_URL="${SMOKE_TEST_API_URL:-http://localhost:8000}"
FRONTEND_URL="${SMOKE_TEST_FRONTEND_URL:-http://localhost:3000}"
REDIS_URL="${SMOKE_TEST_REDIS_URL:-}"
EXPECTED_MIGRATIONS="${SMOKE_TEST_EXPECTED_MIGRATIONS:-}"

CHECK_TIMEOUT=10
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# ── Help ─────────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--help" ]]; then
  sed -n '3,30p' "$0"
  exit 0
fi

# ── Output helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() { echo -e "  ${GREEN}PASS${NC}  $1 — $2"; ((PASS_COUNT+=1)); }
log_fail() { echo -e "  ${RED}FAIL${NC}  $1 — $2"; ((FAIL_COUNT+=1)); }
log_skip() { echo -e "  ${YELLOW}SKIP${NC}  $1 — $2"; ((SKIP_COUNT+=1)); }

# ── Check functions ─────────────────────────────────────────────────────────

# (a)-(e) HTTP 200 check
check_http_200() {
  local label="$1" url="$2" method="${3:-GET}" extra_flags="${4:-}"

  echo "─── ${label} ──────────────────────────────────────"
  echo "${method} ${url}"

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" -X "${method}" \
    ${extra_flags} "${url}" --max-time "${CHECK_TIMEOUT}" 2>&1 || echo "000")

  if [ "${http_code}" = "000" ]; then
    log_fail "${label}" "Connection failed (timeout or DNS error)"
  elif [ "${http_code}" -ge 200 ] && [ "${http_code}" -lt 300 ]; then
    log_pass "${label}" "HTTP ${http_code}"
  else
    log_fail "${label}" "HTTP ${http_code} (expected 2xx)"
  fi
  echo ""
}

# (f) Redis ping
check_redis() {
  echo "─── (f) Redis ping ─────────────────────────────────"

  if [ -z "${REDIS_URL}" ]; then
    log_skip "Redis" "SMOKE_TEST_REDIS_URL not set"
    echo ""; return
  fi

  # Try redis-cli first
  if command -v redis-cli &>/dev/null; then
    local result
    result=$(timeout "${CHECK_TIMEOUT}" redis-cli -u "${REDIS_URL}" ping 2>&1 || true)
    if [ "${result}" = "PONG" ]; then
      log_pass "Redis" "PONG (redis-cli)"
    else
      log_fail "Redis" "${result}"
    fi
    echo ""; return
  fi

  # Fallback: python3 + redis module
  if python3 -c "import redis" &>/dev/null 2>&1; then
    local result
    result=$(python3 -c "
import sys
try:
    import redis
    r = redis.from_url('${REDIS_URL}')
    r.ping()
    print('PONG')
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
" 2>&1 || true)
    if [ "${result}" = "PONG" ]; then
      log_pass "Redis" "PONG (python3)"
    else
      log_fail "Redis" "${result}"
    fi
    echo ""; return
  fi

  log_skip "Redis" "redis-cli not found and python3 redis module not available"
  echo ""
}

# (g) Supabase connect
check_supabase() {
  echo "─── (g) Supabase connect ────────────────────────────"

  if ! command -v supabase &>/dev/null; then
    log_skip "Supabase" "supabase CLI not found"
    echo ""; return
  fi

  local result
  result=$(timeout "${CHECK_TIMEOUT}" supabase db ping 2>&1 || true)
  if echo "${result}" | grep -qi "ok\|success\|successfully\|connected\|pong"; then
    log_pass "Supabase" "${result}"
  else
    log_fail "Supabase" "${result}"
  fi
  echo ""
}

# (h) Migration check
check_migrations() {
  echo "─── (h) Migration check ──────────────────────────────"

  if ! command -v supabase &>/dev/null; then
    log_skip "Migrations" "supabase CLI not found"
    echo ""; return
  fi

  # Count local migration files (.sql, excluding .down.sql)
  local local_count=0
  if [ -d "supabase/migrations" ]; then
    local_count=$(find supabase/migrations -maxdepth 1 -name '*.sql' ! -name '*.down.sql' | wc -l)
  fi

  # Check pending migrations via diff
  local diff_output
  diff_output=$(timeout "${CHECK_TIMEOUT}" supabase db diff --linked --quiet 2>&1 || true)

  # supabase db diff --linked --quiet exits 0 and produces no output when clean
  if [ -z "${diff_output}" ]; then
    if [ -n "${EXPECTED_MIGRATIONS}" ] && [ "${local_count}" -ne "${EXPECTED_MIGRATIONS}" ]; then
      log_fail "Migrations" "No pending diff, but local count (${local_count}) != expected (${EXPECTED_MIGRATIONS})"
    else
      log_pass "Migrations" "All applied (${local_count} local files, no pending diff)"
    fi
  elif echo "${diff_output}" | grep -qi "no changes\|nothing to change\|already applied\|up-to-date\|up to date"; then
    if [ -n "${EXPECTED_MIGRATIONS}" ] && [ "${local_count}" -ne "${EXPECTED_MIGRATIONS}" ]; then
      log_fail "Migrations" "No pending changes, but local count (${local_count}) != expected (${EXPECTED_MIGRATIONS})"
    else
      log_pass "Migrations" "All applied (${local_count} local files, ${diff_output:0:80})"
    fi
  else
    log_fail "Migrations" "Pending changes detected: ${diff_output:0:200}"
  fi
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
echo "=============================================================================="
echo "  Smoke Tests — ${TIMESTAMP}"
echo "=============================================================================="
echo "  API URL:      ${API_URL}"
echo "  Frontend URL: ${FRONTEND_URL}"
echo "=============================================================================="
echo ""

# (a) /health/live
check_http_200 "(a) Liveness probe"  "${API_URL}/health/live"

# (b) /health/ready
check_http_200 "(b) Readiness probe" "${API_URL}/health/ready"

# (c) /v1/sectors
check_http_200 "(c) Public sectors"  "${API_URL}/v1/sectors"

# (d) /observatorio (frontend ISR page)
# -L follows redirects — resilient to Next.js trailingSlash config changes
check_http_200 "(d) ISR page"        "${FRONTEND_URL}/observatorio" "GET" "-L"

# (e) /v1/plans
check_http_200 "(e) Plans"           "${API_URL}/v1/plans"

# (f) Redis ping (optional)
check_redis

# (g) Supabase connect (optional)
check_supabase

# (h) Migration check (optional)
check_migrations

# ── Summary ──────────────────────────────────────────────────────────────────
echo "=============================================================================="
echo "  Smoke Tests Summary — ${TIMESTAMP}"
echo "=============================================================================="
echo "  PASS: ${PASS_COUNT}   FAIL: ${FAIL_COUNT}   SKIP: ${SKIP_COUNT}"
echo "=============================================================================="

if [ "${FAIL_COUNT}" -gt 0 ]; then
  echo "  Result: FAILED"
  exit 1
fi

echo "  Result: PASSED"
exit 0
