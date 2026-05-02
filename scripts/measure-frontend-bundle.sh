#!/usr/bin/env bash
# measure-frontend-bundle.sh — OPS-CI-001 helper
# Computes total gzip-compressed size of all .next/static/chunks/*.js files.
# Usage: ./scripts/measure-frontend-bundle.sh [frontend_dir]
# Output: total bytes (integer) on stdout; nothing else.

set -euo pipefail

FRONTEND_DIR="${1:-frontend}"
CHUNKS_DIR="${FRONTEND_DIR}/.next/static/chunks"

if [[ ! -d "$CHUNKS_DIR" ]]; then
  echo "ERROR: chunks dir not found: $CHUNKS_DIR" >&2
  echo "Did you run 'npm run build' first?" >&2
  exit 1
fi

total=0
shopt -s nullglob
for f in "$CHUNKS_DIR"/*.js; do
  [[ -f "$f" ]] || continue
  size=$(gzip -c "$f" | wc -c)
  total=$((total + size))
done
shopt -u nullglob

echo "$total"
