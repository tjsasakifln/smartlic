#!/usr/bin/env bash
# NO-JARGON-004: Banned phrase validation for blog and search components.
# Checks ONLY git diff (new/changed lines) against banned technical jargon.
# Existing violations are NOT flagged — only new additions fail.
# Exit 0 = clean, Exit 1 = new violations found.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Banned phrases — keep in sync with BANNED_PHRASES in lib/copy/valueProps.ts
# and REPO_COMMS_BANNED_WORDS in lib/copy/b2gIntelCopy.ts
# Use word-boundary patterns to avoid substring false-positives
BANNED_PATTERNS=(
  '\bdatalake\b'
  '\bdata lake\b'
  '\bGPT-4\b'
  '\bGPT-3.5\b'
  '\bLLM\b'
  '\blarge language model\b'
  '\bmachine learning\b'
  '\bcache expirado\b'
  '\bem cache\b'
  '\bquota\b'
)

# Directories to scan (user-facing content)
SCAN_DIRS=(
  "$ROOT_DIR/frontend/app/blog"
  "$ROOT_DIR/frontend/app/buscar"
  "$ROOT_DIR/frontend/components"
  "$ROOT_DIR/frontend/lib/copy"
)

# Build regex alternation from patterns
PATTERN_REGEX=""
for p in "${BANNED_PATTERNS[@]}"; do
  if [ -z "$PATTERN_REGEX" ]; then
    PATTERN_REGEX="$p"
  else
    PATTERN_REGEX="$PATTERN_REGEX|$p"
  fi
done

# Determine diff base: use PR base ref if available, else compare to HEAD~1
BASE_REF="${GITHUB_BASE_REF:-main}"
# Fetch base ref to ensure it's available (CI may have shallow clone)
if git rev-parse "origin/$BASE_REF" >/dev/null 2>&1; then
  DIFF_BASE="origin/$BASE_REF"
else
  DIFF_BASE="HEAD~1"
fi

echo "🔍 NO-JARGON-004: Checking diff against $DIFF_BASE for banned phrases..."

violations=0

# Get list of changed files in the scan directories, then check only added lines
for dir in "${SCAN_DIRS[@]}"; do
  if [ ! -d "$dir" ]; then
    continue
  fi
  changed_files=$(git diff --name-only "$DIFF_BASE" HEAD -- "$dir" 2>/dev/null || true)
  if [ -z "$changed_files" ]; then
    continue
  fi
  while IFS= read -r file; do
    [ -z "$file" ] && continue
    # Skip files that define banned word lists (not user-facing content)
    if echo "$file" | grep -qE "(valueProps\.ts|b2gIntelCopy\.ts)$"; then
      continue
    fi
    # Get only added lines (lines starting with +)
    added_lines=$(git diff "$DIFF_BASE" HEAD -- "$file" | grep '^+' | grep -v '^+++' || true)
    if [ -z "$added_lines" ]; then
      continue
    fi
    # Check each banned pattern against added lines
    if echo "$added_lines" | grep -nHiE "$PATTERN_REGEX" 2>/dev/null; then
      violations=$((violations + 1))
      echo "  ↳ in $file"
    fi
  done <<< "$changed_files"
done

if [ "$violations" -gt 0 ]; then
  echo ""
  echo "❌ NO-JARGON-004: Found $violations new banned phrase violation(s) in diff."
  echo "   Replace technical jargon with user-facing alternatives."
  echo "   See: frontend/lib/copy/valueProps.ts (BANNED_PHRASES)"
  echo "        frontend/lib/copy/b2gIntelCopy.ts (REPO_COMMS_BANNED_WORDS)"
  exit 1
fi

echo "✅ NO-JARGON-004: No new banned phrases detected in diff."
exit 0
