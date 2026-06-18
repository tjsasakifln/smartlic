#!/usr/bin/env bash
# audit-seo-notfound.sh — Scan protected SEO routes for unmarked notFound() calls.
# Operationalises ADR-SEO-001.
#
# Usage: ./audit-seo-notfound.sh [file1.tsx file2.tsx ...]
#   Se arquivos forem fornecidos, scaneia apenas esses arquivos.
#   Se nenhum arquivo for fornecido, scaneia todos os diretorios protegidos.
#
# Exit: 0 = pass (no violations), 1 = violations found.
#
# Notes:
# - Usa grep -P (PCRE) para padroes complexos; disponivel em ubuntu-latest (CI).
# - Em macOS, instale GNU grep via `brew install grep` e use `ggrep -P`.

set -euo pipefail

VIOLATIONS_FILE="/tmp/seo_notfound_violations.txt"
WARNINGS_FILE="/tmp/seo_notfound_warnings.txt"
: > "$VIOLATIONS_FILE"
: > "$WARNINGS_FILE"

PROTECTED_DIRS=(
  frontend/app/observatorio
  frontend/app/cnpj
  frontend/app/fornecedores
  frontend/app/orgaos
  frontend/app/municipios
  frontend/app/licitacoes
  frontend/app/contratos
  frontend/app/alertas-publicos
  frontend/app/itens
  frontend/app/blog
  frontend/app/casos
  frontend/app/glossario
  frontend/app/guia
  frontend/app/masterclass
  frontend/app/perguntas
  frontend/app/compliance
  frontend/app/indice-municipal
  frontend/app/analise
)

# Detecta notFound() em qualquer contexto (bloco, condicional, ternario, callback)
find_notfound_calls() {
  local files=("$@")
  if [ ${#files[@]} -eq 0 ]; then
    local dirs=()
    for d in "${PROTECTED_DIRS[@]}"; do
      [ -d "$d" ] && dirs+=("$d")
    done
    if [ ${#dirs[@]} -eq 0 ]; then
      echo "No protected directories found."
      return 0
    fi
    # Usa grep -P por portabilidade com ubuntu-latest (CI).
    # \b previne falsos positivos com identificadores como myNotFound().
    grep -RHn -P "\bnotFound\s*\(" \
      --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" \
      "${dirs[@]}" 2>/dev/null || true
  else
    grep -Hn -P "\bnotFound\s*\(" "${files[@]}" 2>/dev/null || true
  fi
}

# Verifica se a linha ou linha anterior tem marcador adr-seo-001-allow
has_marker() {
  local file="$1" lineno="$2"
  local current_line prev_line

  current_line=$(sed -n "${lineno}p" "$file" 2>/dev/null || true)
  if echo "$current_line" | grep -q "adr-seo-001-allow:"; then
    return 0
  fi

  if [ "$lineno" -gt 1 ]; then
    prev_line=$(sed -n "$((lineno - 1))p" "$file" 2>/dev/null || true)
    if echo "$prev_line" | grep -q "adr-seo-001-allow:"; then
      return 0
    fi
  fi

  return 1
}

# Detecta padrao de alto risco (Estrategia C): notFound() condicional em dados
is_high_risk_pattern() {
  local content="$1"
  if echo "$content" | grep -qP 'if\s*\(\s*!\s*(data|stats|result|item|info)\s*\)\s*notFound\s*\('; then
    return 0
  fi
  return 1
}

# Contexto de 3 linhas ao redor (linha anterior, atual, proxima)
get_context() {
  local file="$1" lineno="$2"
  local start=$((lineno - 1))
  local end=$((lineno + 1))
  [ "$start" -lt 1 ] && start=1
  sed -n "${start},${end}p" "$file" 2>/dev/null || true
}

echo "Scanning for unmarked notFound() calls in protected SEO routes..."
echo ""

HITS=$(find_notfound_calls "$@")

if [ -z "$HITS" ]; then
  echo "No notFound() calls found."
  echo "violations_found=false"
  echo "violation_count=0"
  exit 0
fi

echo "Hits to classify:"
echo "$HITS"
echo ""

VIOLATION_COUNT=0
WARNING_COUNT=0

while IFS= read -r hit; do
  [ -z "$hit" ] && continue
  file="${hit%%:*}"
  rest="${hit#*:}"
  lineno="${rest%%:*}"
  content="${rest#*:}"

  # Skip pure comment lines (JSDoc mentioning notFound() in prose)
  trimmed=$(printf '%s' "$content" | sed 's/^[[:space:]]*//')
  case "$trimmed" in
    "//"*|"/*"*|"*"*) continue ;;
  esac

  # Check marker
  if has_marker "$file" "$lineno"; then
    # Has marker — check for high-risk pattern anyway (warning only)
    if is_high_risk_pattern "$content"; then
      echo "WARNING: $file:$lineno — high-risk conditional notFound() with marker (Estrategia C pattern)"
      echo "  Context:"
      get_context "$file" "$lineno" | while IFS= read -r ctx; do echo "    $ctx"; done
      WARNING_COUNT=$((WARNING_COUNT + 1))
    fi
    continue
  fi

  # VIOLATION — no marker found
  echo "VIOLATION: $hit"
  echo "  Context:"
  get_context "$file" "$lineno" | while IFS= read -r ctx; do echo "    $ctx"; done

  if is_high_risk_pattern "$content"; then
    echo "  ** HIGH RISK: conditional notFound() on data null — Estrategia C (SEN-FE-001 risk) **"
  fi

  echo "$hit" >> "$VIOLATIONS_FILE"
  VIOLATION_COUNT=$((VIOLATION_COUNT + 1))
done <<< "$HITS"

echo ""
if [ "$VIOLATION_COUNT" -gt 0 ]; then
  echo "violations_found=true"
  echo "violation_count=$VIOLATION_COUNT"
  echo "warning_count=$WARNING_COUNT"
  echo ""
  echo "FAIL: $VIOLATION_COUNT unmarked notFound() call(s) in protected SEO routes."
  echo "Violations:"
  cat "$VIOLATIONS_FILE"
  exit 1
else
  echo "violations_found=false"
  echo "violation_count=0"
  echo "warning_count=$WARNING_COUNT"
  echo ""
  echo "PASS: All notFound() calls carry the adr-seo-001-allow: marker."
  exit 0
fi
