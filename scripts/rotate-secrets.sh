#!/usr/bin/env bash
# ==============================================================================
# SmartLic Secrets Rotation Script
# Issue #1915 — Automation of secret rotation with dry-run + rollback + audit
# ==============================================================================
# Usage:
#   ./scripts/rotate-secrets.sh <secret-name>          # Rotate a specific secret
#   ./scripts/rotate-secrets.sh --list                  # List all tracked secrets
#   ./scripts/rotate-secrets.sh --check                 # Check age of all secrets
#   ./scripts/rotate-secrets.sh <secret> --dry-run      # Preview without changes
#   ./scripts/rotate-secrets.sh <secret> --rollback     # Restore previous value
#   ./scripts/rotate-secrets.sh <secret> --value=xxx    # Provide the new value
#   ./scripts/rotate-secrets.sh --all --dry-run          # Show all pending rotations
#
# Requirements:
#   - Railway CLI authenticated (railway status)
#   - curl, jq, openssl, date (GNU date recommended)
# ==============================================================================

set -euo pipefail

# ── Constants ─────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

BACKUP_DIR="${PROJECT_DIR}/.secrets-backup"
LAST_ROTATION_FILE="${BACKUP_DIR}/last-rotation.json"
AUDIT_LOG="${BACKUP_DIR}/rotation-audit.log"
MAX_BACKUP_AGE_DAYS=90
SMOKE_TEST_URL="${SMOKE_TEST_URL:-https://api.smartlic.tech/health/ready}"
RAILWAY_SERVICE="${RAILWAY_SERVICE:-bidiq-backend}"
RAILWAY_FRONTEND_SERVICE="${RAILWAY_FRONTEND_SERVICE:-bidiq-frontend}"

# Secrets that can be auto-generated locally (no provider dashboard needed)
declare -A AUTO_GENERATABLE
AUTO_GENERATABLE=(
  ["REVALIDATE_SECRET"]="openssl rand -hex 32"
  ["LGPD_DELETION_SECRET"]="openssl rand -hex 32"
)

# Secrets that require manual creation in a provider dashboard
declare -A MANUAL_SECRETS
MANUAL_SECRETS=(
  ["OPENAI_API_KEY"]="OpenAI Platform: https://platform.openai.com/api-keys"
  ["DEEPSEEK_API_KEY"]="DeepSeek Platform: https://platform.deepseek.com/api_keys"
  ["OPENROUTER_API_KEY"]="OpenRouter: https://openrouter.ai/keys"
  ["EXA_API_KEY"]="Exa Dashboard: https://exa.ai/dashboard"
  ["SUPABASE_SERVICE_ROLE_KEY"]="Supabase Dashboard: Project Settings > API > service_role key > Regenerate"
  ["SUPABASE_ANON_KEY"]="Supabase Dashboard: Project Settings > API > anon public key > Regenerate"
  ["SUPABASE_ACCESS_TOKEN"]="Supabase Dashboard: Settings > Access Tokens"
  ["SUPABASE_DB_URL"]="Supabase Dashboard: Project Settings > Database > Connection string (must match new password)"
  ["STRIPE_SECRET_KEY"]="Stripe Dashboard: Developers > API Keys > Roll secret key"
  ["STRIPE_WEBHOOK_SECRET"]="Stripe Dashboard: Developers > Webhooks > Endpoint > Reveal > Reset signing secret"
  ["RESEND_API_KEY"]="Resend Dashboard: https://resend.com/api-keys"
  ["TRIAL_EMAILS_WEBHOOK_SECRET"]="Resend Dashboard: Webhooks > Signing Secret"
  ["SENTRY_DSN"]="Sentry Dashboard: Settings > Projects > DSN"
  ["SENTRY_AUTH_TOKEN"]="Sentry Dashboard: Settings > Auth Tokens > Create New"
  ["MIXPANEL_SERVICE_ACCOUNT_USERNAME"]="Mixpanel Dashboard: Settings > Service Accounts"
  ["MIXPANEL_SERVICE_ACCOUNT_PASSWORD"]="Mixpanel Dashboard: Settings > Service Accounts (regenerate)"
  ["MIXPANEL_PROJECT_ID"]="Mixpanel Dashboard: Settings > Project ID (rarely changes)"
  ["RAILWAY_TOKEN"]="Railway Dashboard: Settings > Tokens > Generate"
  ["REDIS_URL"]="Railway Dashboard: Redis plugin > Regenerate or Upstash Console: Reset Password"
  ["FOUNDING_ONE_TIME_PRICE_ID"]="Stripe Dashboard: Products > Founding Lifetime (rarely changes)"
  ["N8N_API_KEY"]="N8N Dashboard: Settings > API"
  ["GITHUB_TOKEN"]="GitHub: https://github.com/settings/tokens"
  ["SUPABASE_URL"]="Supabase Dashboard: Project Settings > API > Project URL (changes only if project is migrated)"
)

# Services that require the frontend service too
declare -A FRONTEND_SECRETS
FRONTEND_SECRETS=(
  ["SUPABASE_ANON_KEY"]=1
  ["SENTRY_DSN"]=1
  ["REVALIDATE_SECRET"]=1
)

# ── State ──────────────────────────────────────────────────────────────────────
DRY_RUN=false
ROLLBACK_MODE=false
PROVIDED_VALUE=""
FAILED=0

# ── Colors (CI-safe) ──────────────────────────────────────────────────────────
if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  CYAN='\033[0;36m'
  BOLD='\033[1m'
  NC='\033[0m'
else
  RED=''; GREEN=''; YELLOW=''; CYAN=''; BOLD=''; NC=''
fi

# ── Helpers ────────────────────────────────────────────────────────────────────
log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_step()  { echo -e "${CYAN}[STEP]${NC}  $*"; }
log_dry()   { echo -e "${YELLOW}[DRY-RUN]${NC} $*"; }

timestamp() { date -u '+%Y-%m-%dT%H:%M:%SZ'; }

audit_log() {
  local secret_name="$1"
  local action="$2"
  local status="$3"
  local message="${4:-}"
  local entry
  entry="$(timestamp) | ${secret_name} | ${action} | ${status} | ${message}"
  echo "$entry" >> "$AUDIT_LOG"
  log_info "Audit: ${entry}"
}

# ── Argument Parsing ──────────────────────────────────────────────────────────

show_help() {
  cat <<EOF
SmartLic Secrets Rotation Script — Issue #1915

Usage:
  $(basename "$0") <secret-name> [options]
  $(basename "$0") --list
  $(basename "$0") --check
  $(basename "$0") --help

Options:
  --dry-run           Preview what would be done (no actual changes)
  --rollback          Restore the previous value from backup
  --value=STRING      Provide the new secret value (non-interactive)
  --service=NAME      Railway service name (default: bidiq-backend)

Examples:
  $(basename "$0") REVALIDATE_SECRET --dry-run
  $(basename "$0") REVALIDATE_SECRET
  $(basename "$0") REVALIDATE_SECRET --rollback
  $(basename "$0") OPENAI_API_KEY --value="sk-proj-..."
  $(basename "$0") --check
  $(basename "$0") --list
EOF
  exit 0
}

list_secrets() {
  echo -e "${BOLD}Tracked Secrets:${NC}"
  echo ""
  printf "  %-40s %s\n" "SECRET" "TYPE"
  printf "  %-40s %s\n" "------" "----"

  # Auto-generatable
  for secret in "${!AUTO_GENERATABLE[@]}"; do
    printf "  ${GREEN}%-40s${NC} %s\n" "$secret" "Auto-generatable"
  done

  # Manual (from MANUAL_SECRETS keys not in AUTO_GENERATABLE)
  for secret in "${!MANUAL_SECRETS[@]}"; do
    if [[ -z "${AUTO_GENERATABLE[$secret]:-}" ]]; then
      printf "  ${YELLOW}%-40s${NC} %s\n" "$secret" "Manual (provider dashboard)"
    fi
  done

  echo ""
  echo "Total: $((${#AUTO_GENERATABLE[@]} + ${#MANUAL_SECRETS[@]})) secrets"
  exit 0
}

check_age() {
  if [ ! -f "$LAST_ROTATION_FILE" ]; then
    log_error "Tracker file not found: $LAST_ROTATION_FILE"
    echo "  Run once to initialize: $(basename "$0") --dry-run <secret>"
    exit 1
  fi

  local now_epoch
  now_epoch=$(date +%s)
  local expired_count=0
  local total=0
  local warn_threshold=$((MAX_BACKUP_AGE_DAYS * 86400))

  echo -e "${BOLD}Secrets Age Report (threshold: ${MAX_BACKUP_AGE_DAYS}d)${NC}"
  echo ""
  printf "  %-40s %-22s %s\n" "SECRET" "LAST ROTATION" "AGE"
  printf "  %-40s %-22s %s\n" "------" "-------------" "---"

  while IFS= read -r line; do
    local key
    key=$(echo "$line" | jq -r '.key')
    local val
    val=$(echo "$line" | jq -r '.value')

    # Skip meta keys
    if [[ "$key" == _* ]]; then
      continue
    fi

    local ts_epoch
    ts_epoch=$(date -d "$val" +%s 2>/dev/null || echo "0")
    local age_days=$(( (now_epoch - ts_epoch) / 86400 ))
    local display_time="${val}"
    local color="${GREEN}"

    if [ "$age_days" -gt "$MAX_BACKUP_AGE_DAYS" ]; then
      color="${RED}"
      expired_count=$((expired_count + 1))
    elif [ "$age_days" -gt $((MAX_BACKUP_AGE_DAYS * 3 / 4)) ]; then
      color="${YELLOW}"
    fi

    printf "  ${color}%-40s${NC} %-22s %dd\n" "$key" "${display_time:0:19}" "$age_days"
    total=$((total + 1))
  done < <(jq -c 'to_entries[]' "$LAST_ROTATION_FILE")

  echo ""
  if [ "$expired_count" -gt 0 ]; then
    echo -e "  ${RED}${expired_count}/${total} secrets EXCEED ${MAX_BACKUP_AGE_DAYS}d rotation window${NC}"
    echo "  Run './scripts/rotate-secrets.sh <name>' for each expired secret."
  else
    echo -e "  ${GREEN}All ${total} secrets are within the ${MAX_BACKUP_AGE_DAYS}d rotation window.${NC}"
  fi
  exit "$expired_count"
}

# ── Core Functions ─────────────────────────────────────────────────────────────

backup_secret() {
  local secret_name="$1"
  local backup_file="${BACKUP_DIR}/${secret_name}.env"

  DRY_RUN && log_dry "Would backup current value of ${secret_name} to ${backup_file}" && return 0

  mkdir -p "$BACKUP_DIR"

  # Try to get current value from Railway
  local current_value=""
  current_value=$(railway variables get "$secret_name" 2>/dev/null || true)

  if [ -n "$current_value" ]; then
    # NEVER log or print the actual value — mask it
    echo "# Backup of ${secret_name} — $(timestamp)" > "$backup_file"
    echo "# This file contains sensitive credentials — do NOT commit!" >> "$backup_file"
    echo "${secret_name}=${current_value}" >> "$backup_file"
    chmod 600 "$backup_file"
    log_info "Backed up current ${secret_name} to ${backup_file} (chmod 600)"
  else
    log_warn "Could not read current ${secret_name} from Railway — backup skipped"
    echo "# WARNING: Failed to read current value at $(timestamp)" > "$backup_file"
    echo "# You must ensure you have access to the old value for rollback." >> "$backup_file"
    echo "# Backup will be incomplete — manual rollback may be needed." >> "$backup_file"
    echo "${secret_name}=UNKNOWN" >> "$backup_file"
  fi
}

restore_backup() {
  local secret_name="$1"
  local backup_file="${BACKUP_DIR}/${secret_name}.env"

  if [ ! -f "$backup_file" ]; then
    log_error "No backup found for ${secret_name} at ${backup_file}"
    return 1
  fi

  local old_value
  old_value=$(grep "^${secret_name}=" "$backup_file" | cut -d'=' -f2-)

  if [ -z "$old_value" ] || [ "$old_value" = "UNKNOWN" ]; then
    log_error "Backup file for ${secret_name} does not contain a valid value"
    return 1
  fi

  log_step "Restoring ${secret_name} from backup..."

  if DRY_RUN; then
    log_dry "Would restore ${secret_name} from backup ${backup_file}"
    return 0
  fi

  update_railway "$secret_name" "$old_value"
  audit_log "$secret_name" "ROLLBACK" "SUCCESS" "Restored from ${backup_file}"
  log_info "Rollback of ${secret_name} completed"
}

generate_secret() {
  local secret_name="$1"

  if [ -n "${AUTO_GENERATABLE[$secret_name]:-}" ]; then
    local cmd="${AUTO_GENERATABLE[$secret_name]}"
    local value
    value=$(eval "$cmd")
    echo "$value"
    return 0
  fi

  # Manual secret — should not auto-generate
  return 1
}

update_railway() {
  local secret_name="$1"
  local new_value="$2"
  local service="${3:-$RAILWAY_SERVICE}"

  DRY_RUN && log_dry "railway variables set ${secret_name}=*** --service ${service}" && return 0

  log_step "Updating ${secret_name} on Railway service '${service}'..."

  if railway variables set "${secret_name}=${new_value}" --service "$service" 2>&1; then
    log_info "${secret_name} updated on ${service}"
    return 0
  else
    log_error "Failed to update ${secret_name} on ${service}"
    return 1
  fi
}

wait_for_deploy() {
  local service="${1:-$RAILWAY_SERVICE}"
  local timeout_s=180
  local interval_s=10
  local elapsed=0

  DRY_RUN && log_dry "Would wait for deploy of '${service}' (timeout: ${timeout_s}s)" && return 0

  log_step "Waiting for deploy of '${service}' to complete (timeout: ${timeout_s}s)..."

  while [ $elapsed -lt $timeout_s ]; do
    local status
    status=$(railway status --service "$service" 2>/dev/null || echo "unknown")

    if echo "$status" | grep -qi "running\|active\|deployed"; then
      log_info "Service '${service}' is deployed and running"
      return 0
    fi

    sleep "$interval_s"
    elapsed=$((elapsed + interval_s))
  done

  log_warn "Timed out waiting for '${service}' deploy after ${timeout_s}s"
  return 1
}

smoke_test() {
  local url="${1:-$SMOKE_TEST_URL}"

  DRY_RUN && log_dry "Would run smoke test against ${url}" && return 0

  log_step "Running smoke test against ${url}..."

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$url" 2>&1 || echo "000")

  if [ "$http_code" = "200" ]; then
    log_info "Smoke test PASSED (HTTP ${http_code})"
    return 0
  else
    log_error "Smoke test FAILED (HTTP ${http_code})"
    return 1
  fi
}

verify_endpoint() {
  local description="$1"
  local url="$2"
  local expected_code="${3:-200}"

  DRY_RUN && log_dry "Would verify: ${description} (expect ${expected_code})" && return 0

  log_step "Verifying: ${description}..."

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "$url" 2>&1 || echo "000")

  if [ "$http_code" = "$expected_code" ]; then
    log_info "  PASS (HTTP ${http_code})"
    return 0
  else
    log_error "  FAIL — expected ${expected_code}, got HTTP ${http_code}"
    return 1
  fi
}

update_rotation_tracker() {
  local secret_name="$1"
  local ts
  ts=$(timestamp)

  DRY_RUN && log_dry "Would update ${LAST_ROTATION_FILE}: ${secret_name} = ${ts}" && return 0

  if [ ! -f "$LAST_ROTATION_FILE" ]; then
    log_warn "Tracker file not found at ${LAST_ROTATION_FILE} — creating"
    echo '{"_schema_version":1}' > "$LAST_ROTATION_FILE"
  fi

  local tmp
  tmp=$(mktemp)
  jq --arg key "$secret_name" --arg ts "$ts" \
    '.[$key] = $ts | ._last_updated = $ts' \
    "$LAST_ROTATION_FILE" > "$tmp" && mv "$tmp" "$LAST_ROTATION_FILE"

  log_info "Rotation tracker updated: ${secret_name} = ${ts}"
}

# ── Rotation Procedure Per Secret ─────────────────────────────────────────────

rotate_secret() {
  local secret_name="$1"
  local new_value="${2:-}"

  echo ""
  echo "================================================"
  echo "  Rotating: ${secret_name}"
  echo "  Timestamp: $(timestamp)"
  echo "  Mode: $([ "$DRY_RUN" = true ] && echo 'DRY RUN' || echo 'LIVE')"
  echo "================================================"
  echo ""

  # ── Step 0: Validate ──────────────────────────────────────────────────────
  if [ -z "${AUTO_GENERATABLE[$secret_name]:-}" ] && [ -z "${MANUAL_SECRETS[$secret_name]:-}" ]; then
    log_error "Unknown secret: ${secret_name}"
    echo "  Run './scripts/rotate-secrets.sh --list' to see all tracked secrets."
    return 1
  fi

  # ── Step 1: Backup current value ──────────────────────────────────────────
  log_step "Step 1: Backing up current ${secret_name}..."
  backup_secret "$secret_name"

  # ── Step 2: Obtain new value ──────────────────────────────────────────────
  log_step "Step 2: Obtaining new value for ${secret_name}..."

  # If a value was provided via --value=, use it
  if [ -n "$new_value" ]; then
    log_info "Using provided value from --flag"

  # If auto-generatable, generate
  elif [ -n "${AUTO_GENERATABLE[$secret_name]:-}" ]; then
    local generated
    generated=$(generate_secret "$secret_name")
    new_value="$generated"
    log_info "Auto-generated new ${secret_name}"

  # Manual — prompt user
  else
    local source_url="${MANUAL_SECRETS[$secret_name]}"
    echo ""
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  MANUAL ACTION REQUIRED                                  ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  Create a new value for ${BOLD}${secret_name}${NC} at:"
    echo "    ${source_url}"
    echo ""
    echo "  Then provide it via one of:"
    echo "    1. Set the env var: ${BOLD}ROTATE_${secret_name}=<value>${NC}"
    echo "    2. Run with: --value=<new-value>"
    echo "    3. Paste it below"
    echo ""

    if [ -t 0 ] && [ ! -p /dev/stdin ]; then
      # Interactive terminal
      read -r -p "  Paste the new value (or press Enter to skip): " new_value
    else
      # Non-interactive — try env var
      local env_var_name="ROTATE_${secret_name}"
      new_value="${!env_var_name:-}"
      if [ -n "$new_value" ]; then
        log_info "Using value from ${env_var_name} env var"
      fi
    fi

    if [ -z "$new_value" ]; then
      log_warn "No new value provided — skipping ${secret_name}"
      echo ""
      echo "  To complete manually:"
      echo "    railway variables set ${secret_name}=<value> --service ${RAILWAY_SERVICE}"
      echo "    Then update the tracker:"
      echo "    jq '.${secret_name} = \"$(timestamp)\" | ._last_updated = \"$(timestamp)\"' \\"
      echo "      ${LAST_ROTATION_FILE} > /tmp/tmp.json && mv /tmp/tmp.json ${LAST_ROTATION_FILE}"
      echo ""
      return 0
    fi
  fi

  # ── Step 3: Update Railway ────────────────────────────────────────────────
  log_step "Step 3: Updating Railway environment..."

  # Update backend service
  if ! update_railway "$secret_name" "$new_value" "$RAILWAY_SERVICE"; then
    log_error "Failed to update ${secret_name} on backend service"
    audit_log "$secret_name" "ROTATE" "FAILED" "Backend service update failed"
    return 1
  fi

  # Update frontend service if needed
  if [ -n "${FRONTEND_SECRETS[$secret_name]:-}" ]; then
    log_info "This secret also needs to be set on the frontend service"
    if ! update_railway "$secret_name" "$new_value" "$RAILWAY_FRONTEND_SERVICE"; then
      log_warn "Failed to update ${secret_name} on frontend service"
      log_warn "Update manually: railway variables set ${secret_name}=<value> --service ${RAILWAY_FRONTEND_SERVICE}"
    fi
  fi

  # ── Step 4: Wait for deploy ────────────────────────────────────────────────
  log_step "Step 4: Waiting for deployment..."
  if ! wait_for_deploy "$RAILWAY_SERVICE"; then
    log_warn "Proceeding without confirmed deploy — verify manually"
  fi

  # ── Step 5: Smoke test ─────────────────────────────────────────────────────
  log_step "Step 5: Running post-rotation smoke tests..."
  local smoke_ok=true

  if ! smoke_test; then
    smoke_ok=false
    log_error "Primary smoke test failed"
  fi

  # Run additional service-specific tests
  case "$secret_name" in
    OPENAI_API_KEY)
      if ! verify_endpoint "Health endpoint" "$SMOKE_TEST_URL"; then
        smoke_ok=false
      fi
      ;;
    SUPABASE_SERVICE_ROLE_KEY|SUPABASE_ANON_KEY)
      if ! verify_endpoint "Health ready" "$SMOKE_TEST_URL"; then
        smoke_ok=false
      fi
      ;;
    STRIPE_SECRET_KEY|STRIPE_WEBHOOK_SECRET)
      if ! verify_endpoint "Health ready" "$SMOKE_TEST_URL"; then
        smoke_ok=false
      fi
      ;;
    RESEND_API_KEY|TRIAL_EMAILS_WEBHOOK_SECRET)
      if ! verify_endpoint "Health ready" "$SMOKE_TEST_URL"; then
        smoke_ok=false
      fi
      ;;
    REVALIDATE_SECRET)
      if ! verify_endpoint "Health ready" "$SMOKE_TEST_URL"; then
        smoke_ok=false
      fi
      ;;
  esac

  # ── Step 6: Update rotation tracker ─────────────────────────────────────────
  log_step "Step 6: Updating rotation tracker..."
  update_rotation_tracker "$secret_name"

  # ── Summary ─────────────────────────────────────────────────────────────────
  echo ""
  echo "================================================"
  if [ "$smoke_ok" = true ]; then
    echo -e "  ${GREEN}✓ Rotation of ${secret_name} completed successfully${NC}"
  else
    echo -e "  ${YELLOW}⚠ Rotation of ${secret_name} completed, but smoke tests had issues${NC}"
    echo "  Verify manually and check logs."
  fi
  echo "================================================"
  echo ""

  audit_log "$secret_name" "ROTATE" "$([ "$smoke_ok" = true ] && echo 'SUCCESS' || echo 'DEGRADED')" \
    "Service: ${RAILWAY_SERVICE}, smoke: ${smoke_ok}"

  if [ "$smoke_ok" = false ]; then
    return 1
  fi
  return 0
}

# ── Rollback Procedure ────────────────────────────────────────────────────────

rollback_secret() {
  local secret_name="$1"

  echo ""
  echo "================================================"
  echo "  Rolling back: ${secret_name}"
  echo "  Timestamp: $(timestamp)"
  echo "================================================"
  echo ""

  if [ ! -f "${BACKUP_DIR}/${secret_name}.env" ]; then
    log_error "No backup found for ${secret_name}"
    echo "  Backup path: ${BACKUP_DIR}/${secret_name}.env"
    echo "  Cannot rollback without a backup file."
    return 1
  fi

  restore_backup "$secret_name"

  # Also update frontend if needed
  if [ -n "${FRONTEND_SECRETS[$secret_name]:-}" ]; then
    local old_value
    old_value=$(grep "^${secret_name}=" "${BACKUP_DIR}/${secret_name}.env" | cut -d'=' -f2-)
    if [ -n "$old_value" ] && [ "$old_value" != "UNKNOWN" ]; then
      update_railway "$secret_name" "$old_value" "$RAILWAY_FRONTEND_SERVICE" || true
    fi
  fi

  wait_for_deploy "$RAILWAY_SERVICE"
  smoke_test || true

  # Restore rotation tracker to previous date
  update_rotation_tracker "$secret_name"

  echo ""
  echo -e "${GREEN}✓ Rollback of ${secret_name} completed${NC}"
  echo ""

  audit_log "$secret_name" "ROLLBACK" "SUCCESS" "Rolled back to previous value"
}

# ── Main ──────────────────────────────────────────────────────────────────────

main() {
  local command=""
  local secret_name=""

  # Parse args
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --help|-h) show_help ;;
      --list|-l) list_secrets ;;
      --check|-c) check_age ;;
      --dry-run|-n) DRY_RUN=true; shift ;;
      --rollback|-r) ROLLBACK_MODE=true; shift ;;
      --value=*) PROVIDED_VALUE="${1#*=}"; shift ;;
      --value) PROVIDED_VALUE="$2"; shift 2 ;;
      --service=*) RAILWAY_SERVICE="${1#*=}"; shift ;;
      --service) RAILWAY_SERVICE="$2"; shift 2 ;;
      --frontend-service=*) RAILWAY_FRONTEND_SERVICE="${1#*=}"; shift ;;
      --frontend-service) RAILWAY_FRONTEND_SERVICE="$2"; shift 2 ;;
      --all) command="all"; shift ;;
      --*) log_error "Unknown option: $1"; show_help ;;
      *) secret_name="$1"; shift ;;
    esac
  done

  # ── Pre-flight checks ─────────────────────────────────────────────────────
  if ! command -v curl &>/dev/null; then log_error "curl is required"; exit 1; fi
  if ! command -v jq &>/dev/null; then log_error "jq is required"; exit 1; fi
  if ! command -v openssl &>/dev/null; then log_error "openssl is required"; exit 1; fi

  # Railway CLI check (skip for --list and --check)
  if [ -n "$secret_name" ] && command -v railway &>/dev/null; then
    if ! railway status &>/dev/null 2>&1; then
      log_warn "Railway CLI not authenticated or not linked"
      log_warn "Run 'railway login' and 'railway link' first, or manually set env vars."
    fi
  fi

  # Create backup directory
  mkdir -p "$BACKUP_DIR"

  # ── Execute ────────────────────────────────────────────────────────────────
  if [ "$command" = "all" ]; then
    log_step "Checking all secrets for pending rotations..."
    check_age
    echo ""
    echo "Run individual: $(basename "$0") <secret-name> for each expired secret."
    return 0
  fi

  if [ -z "$secret_name" ]; then
    if [ "$DRY_RUN" = true ]; then
      log_info "Use --all to check all secrets, or specify a secret name."
      echo ""
      list_secrets
    fi
    log_error "No secret specified"
    echo "  Usage: $(basename "$0") <secret-name> [--dry-run] [--rollback]"
    echo "  Run '$(basename "$0") --help' for full usage."
    exit 1
  fi

  if [ "$ROLLBACK_MODE" = true ]; then
    rollback_secret "$secret_name"
  else
    rotate_secret "$secret_name" "$PROVIDED_VALUE"
  fi
}

main "$@"
