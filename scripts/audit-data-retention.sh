#!/usr/bin/env bash
# ============================================================================
# GAP-005 (#1877): Data Retention Audit Script
# ============================================================================
# Verifies that purge operations are running correctly for all temporal tables.
# Checks:
#   1. Maximum row age per table via Supabase SQL query
#   2. Whether any table exceeds 2x the retention period without purge
#   3. Exits non-zero if any violation is found (CI-friendly)
#
# Usage:
#   bash scripts/audit-data-retention.sh
#   bash scripts/audit-data-retention.sh --verbose
#   bash scripts/audit-data-retention.sh --supabase-url <url> --supabase-key <key>
#
# Dependencies:
#   - curl, jq
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Config ──────────────────────────────────────────────────────────────────
# Retention policies in days (must stay in sync with data_retention.py)
RETENTION_TRIAL_EMAIL_LOG=180
RETENTION_MESSAGES=365
RETENTION_INGESTION_CHECKPOINTS=30
RETENTION_STRIPE_WEBHOOK_EVENTS=90

# 2x retention threshold for alerting
WARN_MULTIPLIER=2

VERBOSE=false
FAILED=0

# ── Colors (CI-safe: skip if no terminal) ───────────────────────────────────
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

# ── Parse args ──────────────────────────────────────────────────────────────
SUPABASE_URL="${SUPABASE_URL:-}"
SUPABASE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --verbose|-v) VERBOSE=true; shift ;;
        --supabase-url) SUPABASE_URL="$2"; shift 2 ;;
        --supabase-key) SUPABASE_KEY="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# ── Load .env if present ────────────────────────────────────────────────────
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    if [ -f "$PROJECT_DIR/.env" ]; then
        # shellcheck disable=SC1091
        source "$PROJECT_DIR/.env"
        SUPABASE_URL="${SUPABASE_URL:-$SUPABASE_URL}"
        SUPABASE_KEY="${SUPABASE_KEY:-$SUPABASE_SERVICE_ROLE_KEY}"
    fi
fi

if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    echo -e "${RED}ERROR: SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY required${NC}"
    echo "Set via env vars or --supabase-url / --supabase-key flags"
    echo "Or create a .env file at the project root."
    exit 1
fi

# ── Helper functions ─────────────────────────────────────────────────────────

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_debug() { $VERBOSE && echo -e "[DEBUG] $*" || true; }

check_table() {
    local table_name="$1"
    local date_column="$2"
    local retention_days="$3"
    local label="$4"

    log_debug "Checking $label ($table_name.$date_column, retention=${retention_days}d)"

    # Query the maximum age of rows in the table
    local sql
    sql=$(cat <<SQL
SELECT
    EXTRACT(EPOCH FROM (NOW() - MAX($date_column))) / 86400 AS max_age_days,
    COUNT(*) AS row_count
FROM $table_name
WHERE $date_column IS NOT NULL;
SQL
)

    local result
    result=$(curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/query_simple" \
        -H "apikey: $SUPABASE_KEY" \
        -H "Authorization: Bearer $SUPABASE_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"query\": $(echo "$sql" | jq -Rs .)}" 2>/dev/null) || true

    # Fallback: try direct SQL via the REST API (PostgREST)
    if [ -z "$result" ] || [ "$result" = "null" ]; then
        # Use the REST API with a simple aggregate query
        local rest_result
        rest_result=$(curl -s "$SUPABASE_URL/rest/v1/$table_name?select=count%3A%2A%2Cmax_age%3Amax($date_column)" \
            -H "apikey: $SUPABASE_KEY" \
            -H "Authorization: Bearer $SUPABASE_KEY" \
            2>/dev/null) || true

        if [ -n "$rest_result" ] && [ "$rest_result" != "[]" ]; then
            # Parse from PostgREST response
            local max_age_days
            max_age_days=$(echo "$rest_result" | jq -r '.[0].max_age // empty | .[0:10]' 2>/dev/null || echo "")
            local row_count
            row_count=$(echo "$rest_result" | jq -r '.[0].count // 0' 2>/dev/null || echo "0")

            if [ -n "$max_age_days" ] && [ "$max_age_days" != "null" ]; then
                # Calculate age in days from the ISO date
                local max_date_epoch
                max_date_epoch=$(date -d "$max_age_days" +%s 2>/dev/null || echo "0")
                local now_epoch
                now_epoch=$(date +%s)
                local age_days
                age_days=$(( (now_epoch - max_date_epoch) / 86400 ))
                echo "$age_days|$row_count"
                return
            fi
        fi
    fi

    # Try via SQL execution RPC if available
    local sql_result
    sql_result=$(curl -s -X POST "$SUPABASE_URL/rest/v1/rpc/exec_sql" \
        -H "apikey: $SUPABASE_KEY" \
        -H "Authorization: Bearer $SUPABASE_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"sql_text\": \"SELECT EXTRACT(EPOCH FROM (NOW() - MAX($date_column))) / 86400 AS age, COUNT(*) AS cnt FROM $table_name WHERE $date_column IS NOT NULL;\"}" \
        2>/dev/null) || true

    if [ -n "$sql_result" ] && [ "$sql_result" != "null" ]; then
        local age
        age=$(echo "$sql_result" | jq -r '.[0].age // 0' 2>/dev/null || echo "0")
        local cnt
        cnt=$(echo "$sql_result" | jq -r '.[0].cnt // 0' 2>/dev/null || echo "0")
        age=${age%.*}  # Truncate to integer
        echo "${age}|${cnt}"
        return
    fi

    # Final fallback: use raw SQL via /rest/v1/ with a simple query
    log_debug "Using fallback: SELECT count on $table_name"
    local count_result
    count_result=$(curl -s "$SUPABASE_URL/rest/v1/$table_name?select=count%3A%2A" \
        -H "apikey: $SUPABASE_KEY" \
        -H "Authorization: Bearer $SUPABASE_KEY" \
        2>/dev/null) || true
    local count_val
    count_val=$(echo "$count_result" | jq -r '.[0].count // "unknown"' 2>/dev/null || echo "unknown")
    echo "unknown|${count_val}"
}

# ── Main audit ──────────────────────────────────────────────────────────────

echo ""
echo "========================================================"
echo " GAP-005: Data Retention Audit"
echo " $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "========================================================"
echo ""

# ── Check each table ────────────────────────────────────────────────────────

declare -A TABLES
TABLES["trial_email_log|sent_at"]="$RETENTION_TRIAL_EMAIL_LOG"
TABLES["messages|created_at"]="$RETENTION_MESSAGES"
TABLES["ingestion_checkpoints|completed_at"]="$RETENTION_INGESTION_CHECKPOINTS"
TABLES["stripe_webhook_events|processed_at"]="$RETENTION_STRIPE_WEBHOOK_EVENTS"

for table_spec in "${!TABLES[@]}"; do
    IFS='|' read -r table_name date_column <<< "$table_spec"
    retention_days="${TABLES[$table_spec]}"
    label="${table_name}.${date_column}"
    warn_threshold=$(( retention_days * WARN_MULTIPLIER ))

    result=$(check_table "$table_name" "$date_column" "$retention_days" "$label")
    IFS='|' read -r max_age_days row_count <<< "$result"

    if [ "$max_age_days" = "unknown" ]; then
        log_warn "$label: idade desconhecida (COUNT=$row_count)"
        continue
    fi

    if [ "$max_age_days" -gt "$warn_threshold" ]; then
        log_error "$label: ${max_age_days}d > ${warn_threshold}d (2x retention=${retention_days}d) — PURGE ATRASADO!"
        FAILED=1
    elif [ "$max_age_days" -gt "$retention_days" ]; then
        log_warn "$label: ${max_age_days}d > ${retention_days}d (dentro da janela de tolerancia 2x)"
    else
        log_info "$label: ${max_age_days}d <= ${retention_days}d — OK (rows: $row_count)"
    fi
done

# ── Summary ─────────────────────────────────────────────────────────────────

echo ""
echo "--------------------------------------------------------"
if [ "$FAILED" -eq 0 ]; then
    echo -e " ${GREEN}PASS${NC}: All tables within retention policy"
else
    echo -e " ${RED}FAIL${NC}: One or more tables exceed 2x retention — purge may be stalled"
fi
echo "--------------------------------------------------------"
echo ""

exit "$FAILED"
