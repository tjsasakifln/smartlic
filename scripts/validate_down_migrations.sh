#!/usr/bin/env bash
# ==============================================================================
# validate_down_migrations.sh
#
# Validates that every SQL migration in supabase/migrations/ has a paired
# .down.sql rollback script, and that no orphan .down.sql files exist.
#
# Usage:
#   ./scripts/validate_down_migrations.sh
#   ./scripts/validate_down_migrations.sh --quiet    # Only emit errors
#   ./scripts/validate_down_migrations.sh --strict   # Orphan .down.sql exits 1 too
#
# Exit codes:
#   0 -- All migrations have paired .down.sql, no orphans
#   1 -- Some migrations are missing .down.sql (and/or orphans with --strict)
#
# STORY-6.2: Every up migration requires a paired down migration.
# Issue #1803: PR gate enforces this via CI.
# ==============================================================================

set -euo pipefail

MIGRATIONS_DIR="supabase/migrations"
QUIET=false
STRICT=false

# Parse args
for arg in "$@"; do
  case "$arg" in
    --quiet) QUIET=true ;;
    --strict) STRICT=true ;;
    *)
      echo "Unknown option: $arg"
      echo "Usage: $0 [--quiet] [--strict]"
      exit 2
      ;;
  esac
done

# Resolve directory relative to repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MIGRATIONS_PATH="${SCRIPT_DIR}/${MIGRATIONS_DIR}"

if [ ! -d "$MIGRATIONS_PATH" ]; then
  echo "ERROR: Directory not found: ${MIGRATIONS_PATH}" >&2
  exit 1
fi

cd "$MIGRATIONS_PATH"

# Collect up and down migration files
UP_FILES=()
DOWN_FILES=()
MISSING_DOWN=()
ORPHAN_DOWN=()

while IFS= read -r -d '' f; do
  UP_FILES+=("$f")
done < <(find . -maxdepth 1 -name '*.sql' ! -name '*.down.sql' ! -name 'README.md' -print0 | sort -z)

while IFS= read -r -d '' f; do
  DOWN_FILES+=("$f")
done < <(find . -maxdepth 1 -name '*.down.sql' -print0 | sort -z)

# Check each up migration for a paired .down.sql
for up in "${UP_FILES[@]}"; do
  base="${up%.sql}"
  down="${base}.down.sql"
  if [ ! -f "$down" ]; then
    MISSING_DOWN+=("$up")
  fi
done

# Check for orphan .down.sql (no corresponding up migration)
for down in "${DOWN_FILES[@]}"; do
  base="${down%.down.sql}"
  up="${base}.sql"
  if [ ! -f "$up" ]; then
    ORPHAN_DOWN+=("$down")
  fi
done

# Build summary
TOTAL_UP=${#UP_FILES[@]}
TOTAL_DOWN=${#DOWN_FILES[@]}
TOTAL_MISSING=${#MISSING_DOWN[@]}
TOTAL_ORPHAN=${#ORPHAN_DOWN[@]}
TOTAL_WITH_DOWN=$((TOTAL_UP - TOTAL_MISSING))

# Report
if [ "$QUIET" = false ]; then
  echo "============================================="
  echo "  Migration .down.sql Validation Report"
  echo "============================================="
  echo ""
  echo "  Total up migrations:      ${TOTAL_UP}"
  echo "  Total down migrations:    ${TOTAL_DOWN}"
  echo "  With paired .down.sql:    ${TOTAL_WITH_DOWN}"
  echo "  Missing .down.sql:        ${TOTAL_MISSING}"
  echo "  Orphan .down.sql (no up): ${TOTAL_ORPHAN}"
  echo ""
fi

EXIT_CODE=0

if [ "$TOTAL_MISSING" -gt 0 ]; then
  if [ "$QUIET" = false ]; then
    echo "  Missing .down.sql files:"
    for up in "${MISSING_DOWN[@]}"; do
      # Clean leading "./"
      clean="${up#./}"
      echo "    - ${clean}"
    done
    echo ""
  fi
  EXIT_CODE=1
fi

if [ "$TOTAL_ORPHAN" -gt 0 ]; then
  if [ "$STRICT" = true ]; then
    if [ "$QUIET" = false ]; then
      echo "  Orphan .down.sql files (no matching up migration):"
      for down in "${ORPHAN_DOWN[@]}"; do
        clean="${down#./}"
        echo "    - ${clean} (WARNING)"
      done
      echo ""
    fi
    EXIT_CODE=1
  else
    if [ "$QUIET" = false ]; then
      echo "  Orphan .down.sql files (no matching up migration -- not blocking):"
      for down in "${ORPHAN_DOWN[@]}"; do
        clean="${down#./}"
        echo "    - ${clean} (WARNING)"
      done
      echo ""
    fi
    # Orphans are non-blocking by default
  fi
fi

if [ "$EXIT_CODE" -eq 0 ]; then
  if [ "$QUIET" = false ]; then
    echo "  RESULT: All ${TOTAL_UP} migrations have paired .down.sql files."
    echo ""
  fi
else
  if [ "$QUIET" = false ]; then
    echo "  RESULT: FAILED -- ${TOTAL_MISSING} migration(s) missing .down.sql." >&2
    echo "  Every up migration requires a paired down migration (STORY-6.2)." >&2
    echo ""
  fi
fi

exit $EXIT_CODE
