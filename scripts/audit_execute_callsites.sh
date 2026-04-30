#!/bin/bash
# =============================================================================
# RES-BE-002c AC1: Audit `.execute()` callsites em backend/routes/ que ainda
# não usam `_run_with_budget` wrapper.
# =============================================================================
# Pattern alvo (DEVE ser wrappado):
#   sb.table("...").select("...").execute()  # sync — bloqueia event loop
#
# Pattern OK (skip):
#   await _run_with_budget(asyncio.to_thread(...), ...)
#   await asyncio.to_thread(lambda: sb.table("...").execute())
#
# Memory references:
#   - feedback_pool_leak_caller_timeout_vs_sql_timeout
#   - project_backend_outage_2026_04_29_stage5 (10 routes Sentry-priorized P0)
#   - feedback_sweep_single_pr_required (Stages 4+5 confirmed)
#   - feedback_cluster_sweep_pattern (BTS-style hypothesis-first)
#
# Output: docs/audit/execute-callsites-2026-04-29.md
# =============================================================================

set -e

OUTPUT_FILE="${OUTPUT_FILE:-docs/audit/execute-callsites-2026-04-29.md}"
ROOT_DIR="${ROOT_DIR:-backend/routes}"

DATE_NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)

mkdir -p "$(dirname "$OUTPUT_FILE")"

{
  echo "# Audit: \`.execute()\` callsites unprotected (RES-BE-002c AC1)"
  echo ""
  echo "**Generated:** $DATE_NOW"
  echo "**Command:**"
  echo '```bash'
  echo "scripts/audit_execute_callsites.sh"
  echo '```'
  echo ""
  echo "**Pattern grep:** \`.execute(\` em \`$ROOT_DIR/\` excluindo \`_run_with_budget\`, \`asyncio.to_thread\`, \`test_\`."
  echo ""
  echo "## Callsites unprotected"
  echo ""
  echo "| File:line | Context (function) | Tier (manual) | Notes |"
  echo "|-----------|-------------------|---------------|-------|"

  # Greppar callsites
  grep -rEn "\.execute\(" "$ROOT_DIR/" 2>/dev/null \
    | grep -v "_run_with_budget" \
    | grep -v "asyncio.to_thread" \
    | grep -v "test_" \
    | grep -v "__pycache__" \
    | sort \
    | while IFS=: read -r file line content; do
        # Try to extract enclosing function name (look back up to 30 lines)
        relfile="${file#./}"
        # Get function context
        ctx=$(awk -v ln="$line" 'NR<=ln && /^[[:space:]]*(async )?def / { last=$0 } END { print last }' "$file" 2>/dev/null | sed 's/^[[:space:]]*//' | head -c 80)
        ctx_clean=$(echo "$ctx" | sed 's/[|]/\\|/g')
        echo "| \`$relfile:$line\` | $ctx_clean | TODO | |"
      done

  echo ""
  echo "## Total"
  count=$(grep -rEn "\.execute\(" "$ROOT_DIR/" 2>/dev/null \
    | grep -v "_run_with_budget" \
    | grep -v "asyncio.to_thread" \
    | grep -v "test_" \
    | grep -v "__pycache__" \
    | wc -l)
  echo ""
  echo "Unprotected callsites: **$count**"
  echo ""
  echo "## Tier classification (manual)"
  echo ""
  echo "- **Top tier (sweep this PR):** SEO public + bot-thrashable (contratos_publicos, orgao_publico, sitemap_*, observatorio)"
  echo "- **Mid tier (defer next session):** auth path (mfa.py, conta.py, auth_signup.py) — baixo bot impact"
  echo "- **Low tier (defer):** referral.py, plans.py — funcionalidade rara"
  echo ""
  echo "Priorização final em \`docs/audit/execute-sweep-priority-list.md\` (cross-ref Sentry impressions 7d)."
} > "$OUTPUT_FILE"

echo "Wrote $OUTPUT_FILE"
echo "Total unprotected callsites: $(grep -c "^| \`" "$OUTPUT_FILE" || echo 0)"
