#!/usr/bin/env bash
# =============================================================================
# Smoke Test Script — local/CI endpoint validation (#1794)
#
# Usage:
#   BACKEND_URL=https://api.smartlic.tech ./scripts/smoke-test.sh
#   ./scripts/smoke-test.sh                # uses http://localhost:8000
#   ./scripts/smoke-test.sh --fail-fast     # stop on first error
#   ./scripts/smoke-test.sh --help          # show this message
#
# Tests:
#   GET  /health/live      → 200 (liveness)
#   GET  /health/ready     → 200 (readiness)
#   GET  /openapi.json     → 200 (schema)
#   POST /v1/buscar        → not 5xx (search endpoint)
# =============================================================================

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FAIL_FAST=false
PASS_COUNT=0
FAIL_COUNT=0
TIMEOUT_S=15

# ── Help ─────────────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--help" ]]; then
  sed -n '2,16p' "$0"
  exit 0
fi

if [[ "${1:-}" == "--fail-fast" ]]; then
  FAIL_FAST=true
fi

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ── Functions ────────────────────────────────────────────────────────────────
check_endpoint() {
  local method="$1"
  local path="$2"
  local expected_text="$3"
  local label="$4"
  local url="${BACKEND_URL}${path}"

  echo "─── ${label} ──────────────────────────────────────"
  echo "${method} ${url}"

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" -X "${method}" \
    "${url}" \
    --max-time "${TIMEOUT_S}" \
    2>&1 || echo "000")

  local status="PASS"
  local color="${GREEN}"

  if [ "${http_code}" = "000" ]; then
    status="FAIL"
    color="${RED}"
    echo -e "  ${color}Connection failed (timeout or DNS error)${NC}"
    ((FAIL_COUNT+=1))
    $FAIL_FAST && exit 1
    return
  fi

  if [ "${http_code}" -ge 200 ] && [ "${http_code}" -lt 300 ]; then
    status="PASS"
    color="${GREEN}"
    ((PASS_COUNT+=1))
  elif [ "${http_code}" -ge 500 ]; then
    # 5xx is always a deploy regression.
    status="FAIL"
    color="${RED}"
    ((FAIL_COUNT+=1))
    $FAIL_FAST && exit 1
  elif [ "${path}" = "/v1/buscar" ]; then
    # /v1/buscar: 4xx expected (auth/validation missing in smoke test).
    echo -e "  ${YELLOW}INFO${NC}: HTTP ${http_code} (expected 202/200/4xx)"
    ((PASS_COUNT+=1))
  else
    # Other endpoints: non-2xx/non-5xx is a failure.
    status="FAIL"
    color="${RED}"
    ((FAIL_COUNT+=1))
    $FAIL_FAST && exit 1
  fi

  echo -e "  ${color}${status}${NC}: HTTP ${http_code} ${expected_text}"
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────
echo "=========================================="
echo "  Smoke Tests"
echo "  Target: ${BACKEND_URL}"
echo "=========================================="
echo ""

check_endpoint "GET" "/health/live"   "(expect 200)" "Liveness probe"
check_endpoint "GET" "/health/ready"  "(expect 200)" "Readiness probe"
check_endpoint "GET" "/openapi.json"  "(expect 200)" "OpenAPI schema"
check_endpoint "POST" "/v1/buscar"    "(expect not 5xx)" "Search endpoint"

# ── Summary ──────────────────────────────────────────────────────────────────
echo "=========================================="
echo "  Results: ${PASS_COUNT} passed, ${FAIL_COUNT} failed"
echo "=========================================="

if [ "${FAIL_COUNT}" -gt 0 ]; then
  exit 1
fi
exit 0
