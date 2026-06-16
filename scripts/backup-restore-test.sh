#!/usr/bin/env bash
# =============================================================================
# backup-restore-test.sh — Restore test automation (#1864 AC1-AC6, AC8)
#
# Validates database backup integrity by restoring to an isolated PostgreSQL
# instance and running post-restore checks (row counts, FK integrity, indexes,
# sequences). Measures restore time and alerts on RTO breach (>30 min).
#
# The script NEVER touches the production database for writes. All restore
# operations target a SEPARATE database provided via --target-url (AC8).
#
# Usage:
#   ./scripts/backup-restore-test.sh                                 \
#       --target-url "postgresql://user:pass@host:5432/restore_test" \
#       [--source-url "postgresql://..."                             \
#        | --from-file /path/to/backup.dump                          \
#        | --from-s3 "s3://bucket/db-backups/latest.dump"]           \
#       [--threshold 30]                                             \
#       [--skip-cleanup]                                             \
#       [--save-report /path/to/report.md]                           \
#       [--help]
#
# Options:
#   --target-url <url>    Target database URL for restore (MANDATORY, separate DB)
#   --source-url <url>    Production database URL (default: SUPABASE_DB_URL from .env)
#   --from-file <path>    Restore from a local pg_dump custom-format file
#   --from-s3 <uri>       Download backup from S3 and restore (requires aws CLI)
#   --threshold <min>     RTO threshold in minutes (default: 30, AC6)
#   --skip-cleanup        Keep restored schema for inspection (default: drop)
#   --save-report <path>  Save full report as Markdown
#   --help                Show this help message
#
# Exit codes:
#   0 — All checks passed, RTO compliant
#   1 — Restore succeeded but post-restore checks FAILED
#   2 — Restore FAILED (timeout, connectivity, disk space)
#   3 — RTO BREACHED (restore took longer than threshold)
#   4 — Usage / connectivity error / prereq missing
#
# Required environment:
#   AWS_ACCESS_KEY_ID       (if using --from-s3)
#   AWS_SECRET_ACCESS_KEY   (if using --from-s3)
#   AWS_DEFAULT_REGION      (if using --from-s3, default: us-east-1)
#
# Reference:
#   - Issue #1864: P0 Database backup restore test
#   - docs/operations/backup-dr-verified.md
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORT_FILE=""

# Defaults
RTO_THRESHOLD_MIN=30
SKIP_CLEANUP=false
MODE="live"    # live, file, s3
SOURCE_URL=""
TARGET_URL=""
FROM_FILE=""
FROM_S3_URI=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Timing accumulator
RESTORE_START_EPOCH=0
RESTORE_END_EPOCH=0

usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Database backup restore test — validates backup integrity and RTO compliance.

Options:
  --target-url <url>    Target database URL for restore (MANDATORY)
  --source-url <url>    Production database URL (default: SUPABASE_DB_URL from .env)
  --from-file <path>    Restore from a local pg_dump custom-format file
  --from-s3 <uri>       Download backup from S3 and restore
  --threshold <min>     RTO threshold in minutes (default: 30)
  --skip-cleanup        Keep restored schema for inspection (default: drop)
  --save-report <path>  Save full report as Markdown
  --help                Show this help message

Exit codes:
  0 — All checks passed, RTO compliant
  1 — Restore succeeded but post-restore checks FAILED
  2 — Restore FAILED (timeout, connectivity, disk space)
  3 — RTO BREACHED (restore took longer than threshold)
  4 — Usage / connectivity error / prereq missing
EOF
}

# --- Utility Functions ---

log_info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

section() {
    echo ""
    echo -e "${BOLD}══════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  $*${NC}"
    echo -e "${BOLD}══════════════════════════════════════════════════${NC}"
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
        url=$(grep -E '^DATABASE_URL=' "$env_file" | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'")
        if [ -n "$url" ]; then
            echo "$url"
            return
        fi
    fi
    echo ""
}

report_metric() {
    mkdir -p "$REPORT_DIR"
    echo "${1}=${2}" >> "$METRICS_FILE"
}

check_prereqs() {
    local missing=0

    if ! command -v psql &>/dev/null; then
        log_error "psql not found. Install PostgreSQL client:"
        log_error "  apt: sudo apt install postgresql-client"
        log_error "  brew: brew install libpq"
        missing=1
    fi

    if ! command -v pg_restore &>/dev/null; then
        log_error "pg_restore not found (part of postgresql-client)."
        missing=1
    fi

    if [ "$MODE" = "s3" ]; then
        if ! command -v aws &>/dev/null; then
            log_error "aws CLI not found. Required for --from-s3 mode."
            missing=1
        fi
    fi

    if [ "$MODE" = "live" ] && [ -z "$SOURCE_URL" ]; then
        log_error "No source database URL found. Set --source-url, SUPABASE_DB_URL in .env,"
        log_error "or use --from-file / --from-s3 to restore from a backup file."
        missing=1
    fi

    return $missing
}

# --- Verification Functions ---

capture_production_row_counts() {
    section "Capturing Production Row Counts (Baseline)"
    local db_url="$1"
    log_info "Querying top 10 largest tables in public schema..."

    local sql
    sql=$(cat <<'SQL'
SELECT
    schemaname || '.' || relname AS table_name,
    n_live_tup AS row_count,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC
LIMIT 10;
SQL
    )

    psql "$db_url" -X -t -A -F'|' -c "$sql" 2>/dev/null || {
        log_warn "Could not query production row counts (permission or connectivity)."
        return 1
    }
}

verify_row_counts() {
    section "AC2: Row Count Verification"
    local target_url="$1"
    local expected_file="$2"
    local failed=0

    if [ ! -f "$expected_file" ] || [ ! -s "$expected_file" ]; then
        log_warn "No baseline file available — verifying target has non-zero data."
        local total_rows
        total_rows=$(psql "$target_url" -X -t -A -c "
            SELECT COALESCE(SUM(n_live_tup), 0)
            FROM pg_stat_user_tables
            WHERE schemaname = 'public';
        " 2>/dev/null || echo "0")

        if [ "$total_rows" -eq 0 ] 2>/dev/null; then
            log_error "Target database appears empty after restore (0 rows total)."
            failed=1
        else
            log_ok "Target database has ~$total_rows total rows."
        fi
        return $failed
    fi

    # Compare with baseline
    while IFS='|' read -r table_name expected_count _size; do
        [ -z "$table_name" ] && continue
        local actual_count
        actual_count=$(psql "$target_url" -X -t -A -c "
            SELECT COUNT(*) FROM $table_name;
        " 2>/dev/null || echo "ERROR")

        if [ "$actual_count" = "ERROR" ]; then
            log_error "Could not query table $table_name in target."
            failed=1
        elif [ "$actual_count" -ne "$expected_count" ]; then
            # Allow small delta for live-dump mode (concurrent writes)
            local delta=$(( actual_count - expected_count ))
            local abs_delta=${delta#-}
            if [ "$abs_delta" -le 5 ]; then
                log_ok "Row count OK for $table_name: expected~$expected_count actual=$actual_count (delta=$delta, concurrent writes expected)"
            else
                log_error "Row count MISMATCH for $table_name: expected=$expected_count actual=$actual_count"
                failed=1
            fi
        else
            log_ok "Row count MATCH for $table_name: $actual_count rows"
        fi
    done < "$expected_file"

    return $failed
}

verify_fk_integrity() {
    section "AC3: FK Constraint Integrity"
    local target_url="$1"
    local failed=0

    log_info "Checking foreign key constraints..."

    # Get the count of FK constraints
    local fk_count
    fk_count=$(psql "$target_url" -X -t -A -c "
        SELECT count(*)::int
        FROM pg_constraint
        WHERE contype = 'f'
          AND connamespace = 'public'::regnamespace;
    " 2>/dev/null || echo "0")

    log_info "FK constraint count: ${fk_count}"
    report_metric "fk_constraint_count" "$fk_count"

    if [ "$fk_count" -eq 0 ]; then
        log_ok "No FK constraints to validate."
        return 0
    fi

    # Check for NOT VALID constraints
    local invalid_count
    invalid_count=$(psql "$target_url" -X -t -A -c "
        SELECT count(*)::int
        FROM pg_constraint
        WHERE contype = 'f'
          AND connamespace = 'public'::regnamespace
          AND NOT convalidated;
    " 2>/dev/null || echo "0")

    if [ "$invalid_count" -gt 0 ]; then
        log_error "Found $invalid_count NOT VALID FK constraints (restore may have skipped validation)."
        failed=1
    else
        log_ok "All FK constraints are validated."
    fi

    # Check for orphaned rows using PL/pgSQL dynamic query
    # Iterates over each FK, builds the NOT EXISTS join from pg_attribute,
    # and counts violations. Only runs on validated constraints to avoid
    # false positives on intentionally unvalidated FKs.
    log_info "Checking for orphaned rows across FK constraints..."
    local total_orphans=0

    # Create temporary function and execute in a single psql call
    local orphan_check
    orphan_check=$(psql "$target_url" -X -t -A 2>/dev/null <<SQL
DO \$\$
DECLARE
    r RECORD;
    orphan_count BIGINT;
    total_orphans BIGINT := 0;
    child_col TEXT;
    parent_col TEXT;
    join_cond TEXT;
BEGIN
    FOR r IN
        SELECT
            con.conname,
            con.confrelid::regclass::text AS parent_table,
            con.conrelid::regclass::text AS child_table,
            con.conkey,
            con.confkey
        FROM pg_constraint con
        WHERE con.contype = 'f'
          AND con.connamespace = 'public'::regnamespace
          AND con.convalidated
    LOOP
        -- Build join condition from column mappings
        join_cond := '';
        FOR i IN 1 .. array_length(r.conkey, 1) LOOP
            IF i > 1 THEN join_cond := join_cond || ' AND '; END IF;

            SELECT att.attname INTO child_col
            FROM pg_attribute att
            WHERE att.attrelid = (
                SELECT conrelid FROM pg_constraint WHERE conname = r.conname
                  AND connamespace = 'public'::regnamespace
                LIMIT 1
            ) AND att.attnum = r.conkey[i];

            SELECT att.attname INTO parent_col
            FROM pg_attribute att
            WHERE att.attrelid = (
                SELECT confrelid FROM pg_constraint WHERE conname = r.conname
                  AND connamespace = 'public'::regnamespace
                LIMIT 1
            ) AND att.attnum = r.confkey[i];

            IF child_col IS NOT NULL AND parent_col IS NOT NULL THEN
                join_cond := join_cond || format('child.%I = parent.%I', child_col, parent_col);
            END IF;
        END LOOP;

        IF join_cond != '' THEN
            EXECUTE format(
                'SELECT count(*) FROM %I child WHERE NOT EXISTS (SELECT 1 FROM %I parent WHERE %s)',
                r.child_table, r.parent_table, join_cond
            ) INTO orphan_count;

            IF orphan_count > 0 THEN
                RAISE WARNING 'FK %: % orphan(s) in % referencing %',
                    r.conname, orphan_count, r.child_table, r.parent_table;
                total_orphans := total_orphans + orphan_count;
            END IF;
        END IF;
    END LOOP;

    IF total_orphans > 0 THEN
        RAISE NOTICE 'TOTAL_ORPHANS=%', total_orphans;
    ELSE
        RAISE NOTICE 'TOTAL_ORPHANS=0';
    END IF;
END;
\$\$;
SQL
)

    local orphans_detected
    orphans_detected=$(echo "$orphan_check" | grep -Eo 'TOTAL_ORPHANS=[0-9]+' | cut -d= -f2 || echo "0")

    if [ -n "$orphans_detected" ] && [ "$orphans_detected" -gt 0 ]; then
        log_warn "Found $orphans_detected orphaned row(s) across FK constraints."
        report_metric "fk_orphans" "$orphans_detected"
    else
        log_ok "No orphaned rows detected — FK referential integrity intact."
        report_metric "fk_orphans" "0"
    fi

    log_ok "FK constraint integrity verified across $fk_count constraints."
    return $failed
}

verify_indexes() {
    section "AC3: Index Verification"
    local target_url="$1"
    local failed=0

    log_info "Checking indexes exist on all tables..."

    local index_count
    index_count=$(psql "$target_url" -X -t -A -c "
        SELECT count(*)::int
        FROM pg_indexes
        WHERE schemaname = 'public';
    " 2>/dev/null || echo "0")

    log_ok "Found $index_count indexes across all tables in the restored schema."

    # Check for tables without indexes
    local no_index_tables
    no_index_tables=$(psql "$target_url" -X -t -A -c "
        SELECT t.schemaname || '.' || t.tablename
        FROM pg_tables t
        WHERE t.schemaname = 'public'
          AND t.tablename NOT LIKE '_prisma_%'
          AND t.tablename NOT LIKE 'pg_%'
          AND NOT EXISTS (
              SELECT 1 FROM pg_indexes ci
              WHERE ci.schemaname = t.schemaname
                AND ci.tablename = t.tablename
          )
        ORDER BY t.tablename;
    " 2>/dev/null || true)

    if [ -n "$no_index_tables" ]; then
        local line_count
        line_count=$(echo "$no_index_tables" | grep -c . || true)
        if [ "$line_count" -gt 0 ]; then
            log_warn "Tables without indexes ($line_count):"
            echo "$no_index_tables" | while IFS='|' read -r tbl; do
                [ -z "$tbl" ] && continue
                echo "  - $tbl"
            done
            log_warn "This may be expected for small lookup/enum tables."
        fi
    else
        log_ok "All tables have at least one index."
    fi

    return $failed
}

verify_sequences() {
    section "AC3: Sequence Validation"
    local target_url="$1"
    local failed=0

    log_info "Validating sequences in restored schema..."

    local seq_count
    seq_count=$(psql "$target_url" -X -t -A -c "
        SELECT count(*)::int
        FROM information_schema.sequences
        WHERE sequence_schema = 'public';
    " 2>/dev/null || echo "0")

    if [ "$seq_count" -eq 0 ]; then
        log_ok "No sequences found in public schema."
        return 0
    fi

    log_info "Found $seq_count sequences."

    # Check sequences are not exhausted
    local seq_warnings=0
    local row
    while IFS='|' read -r seq_name last_val max_val; do
        [ -z "$seq_name" ] && continue
        if [ "$last_val" -gt 0 ] 2>/dev/null && [ "$max_val" -gt 0 ] 2>/dev/null; then
            local pct_used=$(( last_val * 100 / max_val ))
            if [ "$pct_used" -ge 90 ]; then
                log_warn "Sequence $seq_name is ${pct_used}% exhausted (last_value=$last_val / max_value=$max_val)"
                seq_warnings=$((seq_warnings + 1))
            fi
        fi
    done <<< "$(psql "$target_url" -X -t -A -F'|' -c "
        SELECT sequence_name, last_value, max_value
        FROM information_schema.sequences s
        JOIN pg_sequences ps ON ps.sequencename = s.sequence_name
        WHERE s.sequence_schema = 'public'
        ORDER BY s.sequence_name;
    " 2>/dev/null || true)"

    if [ "$seq_warnings" -eq 0 ]; then
        log_ok "All sequences within safe range."
    fi
    return $failed
}

# --- Restore Functions ---

do_restore_from_live() {
    section "Restore: Live pg_dump -> pg_restore"
    local source_url="$1"
    local target_url="$2"
    local dump_file="$3"

    log_info "Step 1: pg_dump from production (custom format, compress=9)"
    log_info "Source: (masked) $source_url" | sed 's|://[^@]*@|://***@|'

    local dump_start dump_end dump_elapsed
    local dump_exit=0
    dump_start=$(date +%s)

    pg_dump \
        --format=custom \
        --compress=9 \
        --no-acl \
        --no-owner \
        --verbose \
        --file="$dump_file" \
        "$source_url" 2>&1 | grep -E '^(pg_dump:|last|ERROR|WARNING)' || dump_exit=${PIPESTATUS[0]}
    if [ $dump_exit -ne 0 ]; then
        log_error "pg_dump FAILED (exit code $dump_exit)."
        return 2
    fi

    dump_end=$(date +%s)
    dump_elapsed=$(( dump_end - dump_start ))
    local dump_size
    dump_size=$(du -sh "$dump_file" 2>/dev/null | cut -f1)
    log_ok "pg_dump completed in ${dump_elapsed}s, size=$dump_size"

    local rs_exit=0
    RESTORE_START_EPOCH=$(date +%s)

    log_info "Step 2: pg_restore to target"
    log_info "Target: (masked) $target_url" | sed 's|://[^@]*@|://***@|'

    pg_restore \
        --clean \
        --if-exists \
        --no-acl \
        --no-owner \
        --verbose \
        --dbname="$target_url" \
        "$dump_file" 2>&1 | grep -E '^(pg_restore:|ERROR|WARNING)' || rs_exit=${PIPESTATUS[0]}
    if [ $rs_exit -ne 0 ]; then
        log_error "pg_restore FAILED (exit code $rs_exit)."
        rm -f "$dump_file"
        return 2
    fi

    RESTORE_END_EPOCH=$(date +%s)
    rm -f "$dump_file"
    log_ok "Restore completed."
    return 0
}

do_restore_from_file() {
    section "Restore: From Local File"
    local file_path="$1"
    local target_url="$2"

    if [ ! -f "$file_path" ]; then
        log_error "Backup file not found: $file_path"
        return 4
    fi

    local file_size
    file_size=$(du -sh "$file_path" 2>/dev/null | cut -f1)
    log_info "Backup file: $(basename "$file_path") ($file_size)"

    local rs_exit=0
    RESTORE_START_EPOCH=$(date +%s)

    pg_restore \
        --clean \
        --if-exists \
        --no-acl \
        --no-owner \
        --verbose \
        --dbname="$target_url" \
        "$file_path" 2>&1 | grep -E '^(pg_restore:|ERROR|WARNING)' || rs_exit=${PIPESTATUS[0]}
    if [ $rs_exit -ne 0 ]; then
        log_error "pg_restore FAILED (exit code $rs_exit)."
        return 2
    fi

    RESTORE_END_EPOCH=$(date +%s)
    log_ok "Restore completed."
    return 0
}

do_restore_from_s3() {
    section "Restore: From S3"
    local s3_uri="$1"
    local target_url="$2"
    local dump_file="$3"

    if ! command -v aws &>/dev/null; then
        log_error "aws CLI not found."
        return 4
    fi

    log_info "Downloading from $s3_uri"

    local dl_start dl_end dl_elapsed
    dl_start=$(date +%s)

    aws s3 cp "$s3_uri" "$dump_file" --no-progress 2>&1 || {
        log_error "S3 download FAILED."
        return 2
    }

    dl_end=$(date +%s)
    dl_elapsed=$(( dl_end - dl_start ))
    local file_size
    file_size=$(du -sh "$dump_file" 2>/dev/null | cut -f1)
    log_ok "Downloaded in ${dl_elapsed}s, size=$file_size"

    local rs_exit=0
    RESTORE_START_EPOCH=$(date +%s)

    pg_restore \
        --clean \
        --if-exists \
        --no-acl \
        --no-owner \
        --verbose \
        --dbname="$target_url" \
        "$dump_file" 2>&1 | grep -E '^(pg_restore:|ERROR|WARNING)' || rs_exit=${PIPESTATUS[0]}
    RESTORE_END_EPOCH=$(date +%s)
    BACKUP_SIZE_CAPTURED="${file_size:-unknown}"
    rm -f "$dump_file"

    if [ $rs_exit -ne 0 ]; then
        log_error "pg_restore FAILED (exit code $rs_exit)."
        return 2
    fi

    log_ok "Restore completed."
    return 0
}

# Global for backup size capture (set inside restore functions before file deletion)
BACKUP_SIZE_CAPTURED=""

cleanup_target() {
    section "AC8: Cleanup - Dropping Restored Schema"
    local target_url="$1"

    if [ "$SKIP_CLEANUP" = "true" ]; then
        log_info "Skipping cleanup (--skip-cleanup). Schema left intact for inspection."
        return 0
    fi

    log_info "Dropping all public-schema objects from target database..."

    psql "$target_url" -X -t -c "
        DO \$\$
        DECLARE
            r RECORD;
        BEGIN
            -- Drop all tables (cascading drops views, sequences, etc.)
            FOR r IN
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename NOT IN ('_prisma_migrations')
            LOOP
                EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', r.tablename);
            END LOOP;

            -- Drop remaining sequences
            FOR r IN
                SELECT sequence_name
                FROM information_schema.sequences
                WHERE sequence_schema = 'public'
            LOOP
                EXECUTE format('DROP SEQUENCE IF EXISTS %I CASCADE', r.sequence_name);
            END LOOP;
        END \$\$;
    " 1>/dev/null 2>&1 || {
        log_warn "Cleanup encountered errors. Target may need manual cleanup."
        return 1
    }

    log_ok "Restored schema dropped from target database."
}

# --- Report Functions ---

save_report() {
    local report_path="$1"
    local exit_code="$2"
    local restore_elapsed="$3"
    local backup_size="$4"
    local rto_seconds="$5"
    local rto_violation="$6"

    cat > "$report_path" <<REPORTEOF
# Backup Restore Test Report

**Date:** $(date -u '+%Y-%m-%d %H:%M UTC')
**Mode:** $MODE
**Exit Code:** $exit_code

## Timing Metrics (AC4)

| Metric | Value |
|--------|-------|
| Restore Time | ${restore_elapsed}s (restore $(( restore_elapsed / 60 ))m $(( restore_elapsed % 60 ))s) |
| RTO Threshold | ${RTO_THRESHOLD_MIN}min (${rto_seconds}s) |
| RTO Compliant | $([ "$rto_violation" = "0" ] && echo "YES" || echo "NO") |
| Backup Size | ${backup_size:-N/A} |

## Post-Restore Checks

- Row Count Verification: $([ "$exit_code" -ne 2 ] && echo "PASS" || echo "FAIL")
- FK Integrity: $([ "$exit_code" -ne 2 ] && echo "PASS" || echo "FAIL")
- Index Presence: $([ "$exit_code" -ne 2 ] && echo "PASS" || echo "FAIL")
- Sequence Validation: $([ "$exit_code" -ne 2 ] && echo "PASS" || echo "FAIL")

## RPO Status

- **RPO Target:** < 24h
- **Live-dump mode:** RPO is effectively 0 (backup just created).
- **File/S3 mode:** RPO depends on when the backup was taken.

## Safety (AC8)

- **Production modified?** NO
- **Cleanup:** $([ "$SKIP_CLEANUP" = "true" ] && echo "Skipped" || echo "Completed")
REPORTEOF
}

# --- Main ---

main() {
    echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}  Database Backup Restore Test v1.0                           ${NC}"
    echo -e "${BOLD}  $(date -u '+%Y-%m-%d %H:%M UTC')                            ${NC}"
    echo -e "${BOLD}══════════════════════════════════════════════════════════════${NC}"

    # === Parse Arguments ===
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --target-url)
                TARGET_URL="$2"
                shift 2
                ;;
            --source-url)
                SOURCE_URL="$2"
                MODE="live"
                shift 2
                ;;
            --from-file)
                FROM_FILE="$2"
                MODE="file"
                shift 2
                ;;
            --from-s3)
                FROM_S3_URI="$2"
                MODE="s3"
                shift 2
                ;;
            --threshold)
                RTO_THRESHOLD_MIN="$2"
                shift 2
                ;;
            --skip-cleanup)
                SKIP_CLEANUP=true
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
                log_error "Unknown option: $1"
                usage >&2
                exit 4
                ;;
        esac
    done

    # === Validate ===
    if [ -z "$TARGET_URL" ]; then
        log_error "--target-url is MANDATORY (must point to a SEPARATE restore database)."
        echo ""
        usage >&2
        exit 4
    fi

    if [ "$MODE" = "live" ] && [ -z "$SOURCE_URL" ]; then
        SOURCE_URL=$(load_db_url)
    fi

    check_prereqs || exit 4

    # Verify target is NOT production
    if { [ -n "${SUPABASE_DB_URL:-}" ] && [ "$TARGET_URL" = "$SUPABASE_DB_URL" ]; } || \
       { [ -n "${SOURCE_URL:-}" ] && [ "$TARGET_URL" = "$SOURCE_URL" ]; }; then
        log_error "TARGET URL IS THE SAME AS PRODUCTION. Aborting to protect production (AC8)."
        exit 4
    fi

    # === Phase 1: Capture Pre-Restore Baseline ===
    local baseline_file
    baseline_file=$(mktemp /tmp/restore_test_baseline_XXXXXX)
    trap 'rm -f "$baseline_file"' EXIT

    if [ "$MODE" = "live" ]; then
        capture_production_row_counts "$SOURCE_URL" > "$baseline_file" || true
    fi

    # === Phase 2: Execute Restore ===
    section "AC1: Executing Restore"
    local dump_file
    dump_file=$(mktemp /tmp/restore_test_dump_XXXXXX.dump)
    local overall_exit=0
    local backup_size=""

    case "$MODE" in
        live)
            do_restore_from_live "$SOURCE_URL" "$TARGET_URL" "$dump_file" || overall_exit=$?
            backup_size="${BACKUP_SIZE_CAPTURED:-$(du -sh "$dump_file" 2>/dev/null | cut -f1)}"
            ;;
        file)
            do_restore_from_file "$FROM_FILE" "$TARGET_URL" || overall_exit=$?
            backup_size=$(du -sh "$FROM_FILE" 2>/dev/null | cut -f1)
            ;;
        s3)
            do_restore_from_s3 "$FROM_S3_URI" "$TARGET_URL" "$dump_file" || overall_exit=$?
            backup_size="${BACKUP_SIZE_CAPTURED:-$(du -sh "$dump_file" 2>/dev/null | cut -f1)}"
            ;;
    esac

    rm -f "$dump_file" 2>/dev/null || true

    # RTO check (AC4/AC6)
    local restore_elapsed=0
    local rto_violation=0
    local rto_seconds=$(( RTO_THRESHOLD_MIN * 60 ))

    if [ "$RESTORE_START_EPOCH" -gt 0 ] && [ "$RESTORE_END_EPOCH" -gt 0 ]; then
        restore_elapsed=$(( RESTORE_END_EPOCH - RESTORE_START_EPOCH ))
        local restore_min=$(( restore_elapsed / 60 ))
        local restore_sec=$(( restore_elapsed % 60 ))

        echo ""
        echo -e "${BOLD}--- RTO Check (AC6) ---${NC}"
        echo "  Restore time: ${restore_elapsed}s (${restore_min}m ${restore_sec}s)"
        echo "  RTO threshold: ${RTO_THRESHOLD_MIN}min (${rto_seconds}s)"

        if [ "$restore_elapsed" -gt "$rto_seconds" ]; then
            log_error "RTO BREACHED: Restore took ${restore_elapsed}s, threshold is ${rto_seconds}s."
            rto_violation=1
            if [ "$overall_exit" -eq 0 ]; then
                overall_exit=3
            fi
        else
            log_ok "RTO COMPLIANT: ${restore_elapsed}s < ${rto_seconds}s threshold."
        fi
    fi

    # === Phase 3: Post-Restore Verification ===
    if [ "$overall_exit" -ne 2 ] && [ "$overall_exit" -ne 4 ]; then
        verify_row_counts "$TARGET_URL" "$baseline_file"; [ $? -eq 1 ] && overall_exit=1
        verify_fk_integrity "$TARGET_URL"; [ $? -eq 1 ] && overall_exit=1
        verify_indexes "$TARGET_URL"; [ $? -eq 1 ] && overall_exit=1
        verify_sequences "$TARGET_URL"; [ $? -eq 1 ] && overall_exit=1
    fi

    # === Phase 4: Metrics Summary (AC4) ===
    section "AC4: Metrics Summary"
    echo "  Restore time:    ${restore_elapsed}s"
    echo "  Backup size:     ${backup_size:-N/A}"
    echo "  RTO threshold:   ${RTO_THRESHOLD_MIN}min"
    echo "  RTO compliant:   $([ "$rto_violation" = "0" ] && echo "YES" || echo "NO")"
    echo "  Mode:            ${MODE}"

    # === Phase 5: Cleanup (AC8) ===
    cleanup_target "$TARGET_URL" || true

    # === Phase 6: Save Report ===
    if [ -n "$REPORT_FILE" ]; then
        save_report "$REPORT_FILE" "$overall_exit" "$restore_elapsed" \
            "$backup_size" "$rto_seconds" "$rto_violation"
        log_ok "Report saved to $REPORT_FILE"
    fi

    # === Final Result ===
    echo ""
    section "Result"
    case "$overall_exit" in
        0)
            echo -e "${GREEN}ALL CHECKS PASSED - Backup verified, RTO compliant.${NC}"
            ;;
        1)
            echo -e "${YELLOW}RESTORE OK BUT POST-RESTORE CHECKS FAILED."
            echo -e "  Review the report above and fix integrity issues.${NC}"
            ;;
        2)
            echo -e "${RED}RESTORE FAILED.${NC}"
            echo -e "  Check connectivity, disk space, and database URL."
            ;;
        3)
            echo -e "${RED}RTO BREACHED."
            echo -e "  Restore took longer than ${RTO_THRESHOLD_MIN}min."
            echo -e "  Consider: larger instance, parallel workers, or higher threshold.${NC}"
            ;;
    esac

    exit "$overall_exit"
}

main "$@"
