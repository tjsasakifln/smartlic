#!/usr/bin/env bash
# =============================================================================
# OWASP ZAP Baseline Scan — CI-friendly wrapper
# =============================================================================
# Lightweight wrapper for OWASP ZAP designed for CI pipelines.
# Runs passive scan only (no active attacks) — safe for production targets
# when used as a non-blocking gate.
#
# Usage:
#   ./scripts/security/zap-baseline.sh --target <URL> [options]
#
# Options:
#   --target=<URL>    Target URL to scan (required)
#   --output=<dir>    Output directory (default: reports/security/zap-baseline)
#   --timeout=<secs>  Max scan duration in seconds (default: 600)
#   --docker-args=""  Extra arguments to docker run
#
# Environment:
#   ZAP_IMAGE         ZAP Docker image (default: ghcr.io/zaproxy/zaproxy:stable)
#
# Output:
#   - report.html     HTML report
#   - report.json     JSON report with all alerts
#   - report.md       Markdown summary (parsed from JSON)
#
# Exit codes:
#   0 — Scan completed (with or without alerts)
#   1 — Scan or configuration error
#   2 — Docker not available
# =============================================================================

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
TARGET=""
OUTPUT_DIR="reports/security/zap-baseline"
TIMEOUT=600
ZAP_PORT=8080
ZAP_PORT_API=8081
ZAP_CONTAINER_NAME="zap-baseline-$(date +%s)"
ZAP_IMAGE="${ZAP_IMAGE:-ghcr.io/zaproxy/zaproxy:stable}"
EXTRA_DOCKER_ARGS=""

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ─────────────────────────────────────────────────────────────────────────────
# Parse args
# ─────────────────────────────────────────────────────────────────────────────
usage() {
    grep "^# Usage:" "$0" | sed 's/^# //'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target=*)
            TARGET="${1#*=}"
            shift
            ;;
        --target)
            TARGET="$2"
            shift 2
            ;;
        --output=*)
            OUTPUT_DIR="${1#*=}"
            shift
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --timeout=*)
            TIMEOUT="${1#*=}"
            shift
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --docker-args=*)
            EXTRA_DOCKER_ARGS="${1#*=}"
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            log_error "Unknown argument: $1"
            usage
            ;;
    esac
done

if [[ -z "$TARGET" ]]; then
    log_error "--target is required"
    usage
fi

if ! command -v docker &>/dev/null; then
    log_error "Docker not found"
    exit 2
fi

if ! docker info &>/dev/null; then
    log_error "Docker daemon not running"
    exit 2
fi

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────
mkdir -p "$OUTPUT_DIR"
REPORT_BASE="$OUTPUT_DIR/zap-baseline-$(date +%Y%m%d-%H%M%S)"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

log_info "=== OWASP ZAP Baseline Scan ==="
log_info "Target:   $TARGET"
log_info "Output:   $OUTPUT_DIR"
log_info "Timeout:  ${TIMEOUT}s"
log_info "Image:    $ZAP_IMAGE"
log_info ""

# ─────────────────────────────────────────────────────────────────────────────
# Cleanup handler
# ─────────────────────────────────────────────────────────────────────────────
cleanup() {
    log_info "Cleaning up ZAP container..."
    docker stop "$ZAP_CONTAINER_NAME" 2>/dev/null || true
    docker rm "$ZAP_CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

# ─────────────────────────────────────────────────────────────────────────────
# Start ZAP daemon
# ─────────────────────────────────────────────────────────────────────────────
log_info "Starting ZAP container..."
# shellcheck disable=SC2086
docker run --rm -d \
    --name "$ZAP_CONTAINER_NAME" \
    -p "$ZAP_PORT":8080 \
    -p "$ZAP_PORT_API":8081 \
    -v "$(pwd)/$OUTPUT_DIR":/zap/wrk:rw \
    $EXTRA_DOCKER_ARGS \
    "$ZAP_IMAGE" \
    zap.sh -daemon -port 8080 -host 0.0.0.0 \
    -config api.disablekey=true \
    -config api.addrs.addr.name=.* \
    -config api.addrs.addr.regex=true \
    -config connection.timeoutInSecs=120 \
    -config scanner.stripChart=true 2>&1

log_info "Waiting for ZAP to start..."
ZAP_READY=false
for i in $(seq 1 30); do
    if curl -s "http://localhost:${ZAP_PORT_API}" >/dev/null 2>&1; then
        log_ok "ZAP ready (${i}s)"
        ZAP_READY=true
        break
    fi
    if [[ "$i" -eq 30 ]]; then
        log_error "ZAP did not start within 30s"
        docker logs "$ZAP_CONTAINER_NAME" --tail 20
        exit 1
    fi
    sleep 1
done

# ─────────────────────────────────────────────────────────────────────────────
# Baseline Scan: Spider + Passive Scan only (no active attacks)
# ─────────────────────────────────────────────────────────────────────────────
log_info "Phase 1/3: Spider (traditional crawl)..."
curl -s "http://localhost:${ZAP_PORT_API}/JSON/spider/action/scan/" \
    --data-urlencode "url=$TARGET" \
    --data "maxChildren=5" \
    --data "recurse=true" \
    --data "subtreeOnly=false" \
    >/dev/null

# Wait for spider to complete
log_info "Waiting for spider to complete..."
for i in $(seq 1 60); do
    SPIDER_STATUS=$(curl -s "http://localhost:${ZAP_PORT_API}/JSON/spider/view/status/" \
        | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','0'))" 2>/dev/null || echo "0")
    if [[ "$SPIDER_STATUS" == "100" ]]; then
        log_ok "Spider complete (${i}s)"
        break
    fi
    if [[ "$i" -eq 60 ]]; then
        log_warn "Spider timed out — proceeding with partial crawl"
    fi
    sleep 1
done

log_info "Phase 2/3: Passive scan processing..."
# Allow passive scan rules to process (ZAP needs time for background analysis)
sleep 15

log_info "Phase 3/3: Exporting reports..."
# HTML Report
curl -s "http://localhost:${ZAP_PORT_API}/OTHER/core/other/htmlreport/" \
    -o "${REPORT_BASE}.html"
log_ok "HTML report: ${REPORT_BASE}.html"

# JSON Report (all alerts)
curl -s "http://localhost:${ZAP_PORT_API}/JSON/core/view/alerts/" \
    --data-urlencode "baseurl=$TARGET" \
    --data "start=0" \
    --data "count=1000" \
    -o "${REPORT_BASE}.json"
log_ok "JSON report: ${REPORT_BASE}.json"

# ─────────────────────────────────────────────────────────────────────────────
# Generate Markdown Summary
# ─────────────────────────────────────────────────────────────────────────────
log_info "Generating Markdown summary..."
SUMMARY_MD="${REPORT_BASE}.md"

cat > "$SUMMARY_MD" <<MDEOF
# OWASP ZAP Baseline Scan — Summary

**Target:** $TARGET
**Date:** $(date -u)
**Mode:** Passive + Spider (no active attacks)
**Timestamp:** $TIMESTAMP

## Alert Summary

MDEOF

# Parse JSON and generate summary table
if [[ -f "${REPORT_BASE}.json" ]]; then
    python3 -c "
import json, sys

try:
    with open('${REPORT_BASE}.json') as f:
        data = json.load(f)
except (json.JSONDecodeError, FileNotFoundError) as e:
    print(f'Error parsing JSON: {e}', file=sys.stderr)
    sys.exit(1)

alerts = data.get('alerts', [])

# Count by risk level
counts = {'High': 0, 'Medium': 0, 'Low': 0, 'Informational': 0}
risk_map = {'0': 'Informational', '1': 'Low', '2': 'Medium', '3': 'High'}

for alert in alerts:
    risk_code = str(alert.get('risk', '0'))
    risk = risk_map.get(risk_code, 'Informational')
    if risk in counts:
        counts[risk] += 1

total = sum(counts.values())

with open('$SUMMARY_MD', 'a') as f:
    f.write(f'| Risk Level | Count |\n')
    f.write(f'|------------|-------|\n')
    for risk in ['High', 'Medium', 'Low', 'Informational']:
        f.write(f'| {risk} | {counts[risk]} |\n')
    f.write(f'| **Total** | **{total}** |\n\n')

    if total > 0:
        f.write('## Alerts\n\n')
        for i, alert in enumerate(alerts, 1):
            risk_code = str(alert.get('risk', '0'))
            risk = risk_map.get(risk_code, 'Informational')
            name = alert.get('name', 'Unknown')
            url = alert.get('url', '')
            desc = alert.get('description', '')
            solution = alert.get('solution', '')

            f.write(f'### {i}. [{risk}] {name}\n\n')
            f.write(f'- **URL:** {url}\n')
            f.write(f'- **Risk:** {risk}\n')
            f.write(f'- **Description:** {desc[:200]}\n')
            if solution:
                f.write(f'- **Solution:** {solution[:200]}\n')
            f.write('\n')
" 2>&1 || log_warn "Failed to parse ZAP JSON report"
fi

log_ok "Markdown summary: ${SUMMARY_MD}"

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
log_ok "ZAP Baseline Scan complete!"
echo ""
log_info "Reports:"
log_info "  HTML:  ${REPORT_BASE}.html"
log_info "  JSON:  ${REPORT_BASE}.json"
log_info "  MD:    ${SUMMARY_MD}"

# Export alert counts for CI consumption
if [[ -f "${REPORT_BASE}.json" ]]; then
    python3 -c "
import json
try:
    with open('${REPORT_BASE}.json') as f:
        data = json.load(f)
    alerts = data.get('alerts', [])
    risk_map = {'0': 'Informational', '1': 'Low', '2': 'Medium', '3': 'High'}
    counts = {'High': 0, 'Medium': 0, 'Low': 0, 'Informational': 0}
    for a in alerts:
        r = risk_map.get(str(a.get('risk', '0')), 'Informational')
        if r in counts:
            counts[r] += 1
    print(f'ZAP_HIGH={counts[\"High\"]}')
    print(f'ZAP_MEDIUM={counts[\"Medium\"]}')
    print(f'ZAP_LOW={counts[\"Low\"]}')
    print(f'ZAP_INFO={counts[\"Informational\"]}')
    print(f'ZAP_TOTAL={sum(counts.values())}')
except Exception:
    print('ZAP_HIGH=-1')
    print('ZAP_MEDIUM=-1')
    print('ZAP_LOW=-1')
    print('ZAP_INFO=-1')
    print('ZAP_TOTAL=-1')
" | tee "${REPORT_BASE}.counts"
fi

log_info "Scan completed at $(date -u)"
exit 0
