#!/usr/bin/env bash
# =============================================================================
# audit_rls.sh — RLS coverage audit for public schema (#1792)
#
# Connects to the Supabase database and runs audit_rls.sql to verify that
# every public-schema table has Row Level Security enabled with at least
# one policy. Generates a human-readable report and sets exit code.
#
# Usage:
#   ./scripts/audit_rls.sh                           # Uses SUPABASE_DB_URL from .env
#   ./scripts/audit_rls.sh --url <db_url>            # Explicit DB URL
#   ./scripts/audit_rls.sh --baseline                # Generate baseline (suppress CI output)
#   ./scripts/audit_rls.sh --save-report <path>      # Save report to file
#   ./scripts/audit_rls.sh --help                    # Show usage
#
# Exit codes:
#   0  — All tables RLS-compliant
#   1  — One or more tables missing RLS
#   2  — Usage / connectivity error
#
# Reference: ADR-RLS-MANDATORY-001 (docs/adr/ADR-RLS-MANDATORY-001-policy.md)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SQL_FILE="$SCRIPT_DIR/audit_rls.sql"
REPORT_FILE=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Audit RLS coverage on the public schema of the Supabase database.

Options:
  --url <db_url>         Database URL (overrides SUPABASE_DB_URL from .env)
  --baseline             Generate baseline output (quiet mode, plain text)
  --save-report <path>   Save full report to file
  --help                 Show this help message

Exit codes:
  0  — All tables RLS-compliant
  1  — One or more tables missing RLS
  2  — Usage / connectivity error
EOF
}

load_db_url() {
    if [ -n "${SUPABASE_DB_URL:-}" ]; then
        echo "$SUPABASE_DB_URL"
        return
    fi

    local env_file="$PROJECT_ROOT/.env"
    if [ -f "$env_file" ]; then
        local url
        url=$(grep -E '^SUPABASE_DB_URL=' "$env_file" | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'")
        if [ -n "$url" ]; then
            echo "$url"
            return
        fi

        # Fallback to DATABASE_URL (used by pg_dump scripts)
        url=$(grep -E '^DATABASE_URL=' "$env_file" | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'")
        if [ -n "$url" ]; then
            echo "$url"
            return
        fi
    fi

    echo ""
}

audit() {
    local db_url="$1"
    local baseline_mode="${2:-false}"

    if [ ! -f "$SQL_FILE" ]; then
        echo -e "${RED}ERROR: SQL file not found: $SQL_FILE${NC}" >&2
        exit 2
    fi

    if ! command -v psql &>/dev/null; then
        echo -e "${RED}ERROR: psql not found in PATH.${NC}" >&2
        echo "Install PostgreSQL client tools:" >&2
        echo "  apt:  sudo apt install postgresql-client" >&2
        echo "  rpm:  sudo dnf install postgresql" >&2
        echo "  brew: brew install libpq" >&2
        exit 2
    fi

    if [ "$baseline_mode" = "true" ]; then
        # Baseline mode: plain output, no colors
        psql "$db_url" -X -f "$SQL_FILE" 2>&1
    else
        echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
        echo -e "${CYAN}  RLS Audit — public schema                      ${NC}"
        echo -e "${CYAN}  $(date -u '+%Y-%m-%d %H:%M UTC')               ${NC}"
        echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
        echo ""

        # Run the SQL and capture output
        local output
        output=$(psql "$db_url" -X -f "$SQL_FILE" 2>&1) || {
            local exit_code=$?
            echo -e "${RED}ERROR: psql failed (exit $exit_code).${NC}" >&2
            echo "$output" >&2
            exit 2
        }

        echo "$output"
        echo ""

        # Parse the last result line: the summary verdict
        local verdict
        verdict=$(echo "$output" | grep -E '(PASS:|FAIL:)' | tail -1)

        if echo "$verdict" | grep -q 'FAIL:'; then
            echo -e "${RED}✗ RLS AUDIT FAILED${NC}"
            echo -e "${RED}  $verdict${NC}"
            echo ""
            echo -e "${YELLOW}Tables without RLS:${NC}"
            echo "$output" | grep 'FAIL: RLS disabled' | awk '{print "  - " $1}' || echo "  (none — RLS on but policy gaps)"
            echo "$output" | grep 'WARN: RLS on' | awk '{print "  - " $1 " [RLS on, 0 policies]"}' || true
            return 1
        else
            echo -e "${GREEN}✓ RLS AUDIT PASSED${NC}"
            echo -e "${GREEN}  $verdict${NC}"
            return 0
        fi
    fi
}

# --- Main ---

DB_URL=""
BASELINE_MODE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --url)
            DB_URL="$2"
            shift 2
            ;;
        --baseline)
            BASELINE_MODE=true
            shift
            ;;
        --save-report)
            REPORT_FILE="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            usage >&2
            exit 2
            ;;
    esac
done

# Resolve database URL
if [ -z "$DB_URL" ]; then
    DB_URL=$(load_db_url)
fi

if [ -z "$DB_URL" ]; then
    echo -e "${RED}ERROR: No database URL found.${NC}" >&2
    echo "Set SUPABASE_DB_URL in .env or use --url <db_url>" >&2
    exit 2
fi

# Run audit
if [ -n "$REPORT_FILE" ]; then
    # Save report to file
    audit "$DB_URL" "$BASELINE_MODE" 2>&1 | tee "$REPORT_FILE"
    exit "${PIPESTATUS[0]}"
else
    audit "$DB_URL" "$BASELINE_MODE"
    exit $?
fi
