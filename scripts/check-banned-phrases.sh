#!/usr/bin/env bash
# NO-JARGON-004: Banned phrase validation for blog and search components.
# Scans frontend source files for banned technical jargon.
# Exit 0 = clean, Exit 1 = violations found.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"

# Banned phrases — keep in sync with BANNED_PHRASES in lib/copy/valueProps.ts
# and REPO_COMMS_BANNED_WORDS in lib/copy/b2gIntelCopy.ts
BANNED=(
  "datalake"
  "data lake"
  "GPT-4"
  "GPT-3.5"
  "GPT"
  "LLM"
  "large language model"
  "machine learning"
  "cache expirado"
  "em cache"
  "quota"
)

# Directories to scan (user-facing content)
SCAN_DIRS=(
  "$FRONTEND_DIR/app/blog"
  "$FRONTEND_DIR/app/buscar"
  "$FRONTEND_DIR/components"
  "$FRONTEND_DIR/lib/copy"
)

# Exceptions: dev-facing docs and config files
EXCLUDE_PATTERNS="node_modules|.next|.git|worktrees|__tests__|api-types|.storybook"

violations=0

for dir in "${SCAN_DIRS[@]}"; do
  if [ ! -d "$dir" ]; then
    continue
  fi
  for phrase in "${BANNED[@]}"; do
    while IFS= read -r -d '' file; do
      # Skip excluded paths
      if echo "$file" | grep -qE "$EXCLUDE_PATTERNS"; then
        continue
      fi
      # Search for the phrase (case-insensitive, whole-word where possible)
      if grep -nHi "$phrase" "$file" 2>/dev/null; then
        violations=$((violations + 1))
      fi
    done < <(find "$dir" -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.mdx" \) -print0 2>/dev/null || true)
  done
done

if [ "$violations" -gt 0 ]; then
  echo ""
  echo "❌ NO-JARGON-004: Found $violations banned phrase violation(s)."
  echo "   Replace technical jargon with user-facing alternatives."
  echo "   See: frontend/lib/copy/valueProps.ts (BANNED_PHRASES)"
  echo "        frontend/lib/copy/b2gIntelCopy.ts (REPO_COMMS_BANNED_WORDS)"
  exit 1
fi

echo "✅ NO-JARGON-004: No banned phrases detected in blog and search components."
exit 0
