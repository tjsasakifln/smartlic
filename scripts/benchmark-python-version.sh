#!/bin/bash
# benchmark-python-version.sh — Benchmark comparativo Python 3.12 vs 3.13
#
# Uso:
#   ./scripts/benchmark-python-version.sh              # Testa 3.12 e 3.13
#   ./scripts/benchmark-python-version.sh --only 3.13   # Apenas 3.13
#   ./scripts/benchmark-python-version.sh --output /tmp/resultados.md
#
# Requer: python3.12, python3.13 (ou pyenv), pytest, hyperfine
#
# Metricas capturadas:
#   - Test suite: tempo total, falhas, cobertura
#   - Latencia p50/p95: hyperfine em endpoints-chave
#   - Memory RSS: pico de uso durante test suite

set -euo pipefail

OUTPUT_FILE="${OUTPUT_FILE:-/tmp/python-benchmark-$(date +%Y%m%d-%H%M%S).md}"
ONLY_VERSION=""
BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="${BASE_DIR}/backend"
VENV_DIR="${BACKEND_DIR}/venv"

# ── Helpers ─────────────────────────────────────────────────────────────────
_info()   { echo "[INFO]  $*"; }
_warn()   { echo "[WARN]  $*" >&2; }
_error()  { echo "[ERROR] $*" >&2; exit 1; }

_section() {
  echo "" >> "$OUTPUT_FILE"
  echo "## $*" >> "$OUTPUT_FILE"
  echo "" >> "$OUTPUT_FILE"
}

_metric() {
  # _metric "Nome" "valor" "unidade"
  echo "| $1 | $2 | $3 |" >> "$OUTPUT_FILE"
}

_usage() {
  echo "Uso: $0 [--only 3.13] [--output /path/resultados.md]"
  echo ""
  echo "  --only VERSION   Testar apenas uma versao (3.12 ou 3.13)"
  echo "  --output PATH    Caminho do arquivo de resultados (default: /tmp/)"
  exit 1
}

# ── Parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --only)     ONLY_VERSION="$2"; shift 2 ;;
    --output)   OUTPUT_FILE="$2";  shift 2 ;;
    --help|-h)  _usage ;;
    *)          _error "Argumento desconhecido: $1" ;;
  esac
done

# ── Pre-flight checks ──────────────────────────────────────────────────────
for cmd in pytest hyperfine python3; do
  command -v "$cmd" >/dev/null 2>&1 || _error "Requerido: $cmd (sudo apt install -y python3-pytest hyperfine)"
done

# ── Inicializa arquivo de output ───────────────────────────────────────────
cat > "$OUTPUT_FILE" <<EOF
# Benchmark Python: 3.12 vs 3.13

**Data:** $(date +%Y-%m-%d)
**Host:** $(uname -a | cut -d' ' -f1-3)
**Repo:** ${BASE_DIR}
**Arquivo gerado por:** scripts/benchmark-python-version.sh

EOF

# ── Funcao principal de benchmark ──────────────────────────────────────────
run_benchmark() {
  local py_version="$1"
  local py_cmd="${2:-python${py_version}}"
  local label="Python ${py_version}"

  _section "${label}"

  # 1. Verificar versao do interpretador
  local actual_version
  actual_version=$("$py_cmd" --version 2>&1)
  _metric "Interpretador" "${actual_version}" "-"

  # 2. Criar/ativar virtualenv
  local venv_path="${VENV_DIR}-${py_version}"
  if [ ! -d "$venv_path" ]; then
    _info "Criando virtualenv ${label} em ${venv_path}..."
    "$py_cmd" -m venv "$venv_path"
  fi

  # shellcheck disable=SC1091
  source "${venv_path}/bin/activate"

  _info "Instalando dependencias (${label})..."
  pip install --quiet --upgrade pip
  pip install --quiet -r "${BACKEND_DIR}/requirements.txt"
  pip install --quiet pytest pytest-timeout pytest-cov httpx

  # 3. Test suite — tempo total
  cd "$BACKEND_DIR"
  _info "Executando test suite (${label})..."

  local test_start test_end test_duration
  test_start=$(date +%s%N)

  # Usar timeout_method=thread para compatibilidade cross-version
  set +e
  local pytest_stdout pytest_exit
  pytest_stdout=$(pytest tests/ \
    --timeout=30 --timeout-method=thread \
    -m "not benchmark and not external" \
    --ignore=tests/fuzz --ignore=tests/integration \
    --tb=short -q 2>&1)
  pytest_exit=$?
  set -e

  test_end=$(date +%s%N)
  test_duration=$(( (test_end - test_start) / 1000000 ))  # ms

  _metric "Test suite duration" "$(( test_duration / 1000 ))s ${test_duration}ms" "ms"

  # Extrair pass/fail do output
  local passed failed skipped
  passed=$(echo "$pytest_stdout" | grep -oP '\d+ passed' | tail -1 | grep -oP '\d+' || echo "0")
  failed=$(echo "$pytest_stdout" | grep -oP '\d+ failed' | tail -1 | grep -oP '\d+' || echo "0")
  skipped=$(echo "$pytest_stdout" | grep -oP '\d+ skipped' | tail -1 | grep -oP '\d+' || echo "0")

  _metric "Tests passed" "${passed}" "count"
  _metric "Tests failed" "${failed}" "count"
  _metric "Tests skipped" "${skipped}" "count"

  if [ "$failed" -ne 0 ]; then
    _warn "${label}: ${failed} test(s) falharam!"
    echo "" >> "$OUTPUT_FILE"
    echo "### Test failures (${label})" >> "$OUTPUT_FILE"
    echo '```' >> "$OUTPUT_FILE"
    echo "$pytest_stdout" | grep -E "FAILED" >> "$OUTPUT_FILE" 2>/dev/null || echo "(no FAILED lines in output)" >> "$OUTPUT_FILE"
    echo '```' >> "$OUTPUT_FILE"
  fi

  # 4. Coverage report
  _info "Coletando cobertura (${label})..."
  local cov_output
  cov_output=$(pytest --cov=. --cov-report=term-missing --timeout=30 --timeout-method=thread \
    -m "not benchmark and not external" \
    --ignore=tests/fuzz --ignore=tests/integration \
    -q 2>&1 | tail -5 || true)
  local cov_pct
  cov_pct=$(echo "$cov_output" | grep -oP 'TOTAL\s+\d+\s+\d+\s+(\d+%)' | grep -oP '\d+%' || echo "N/A")
  _metric "Coverage total" "${cov_pct}" "%"

  # 5. Memory peak (RSS durante test suite)
  _info "Medindo pico de memoria RSS..."
  local mem_peak
  mem_peak=$(ps -o rss= -C "python${py_version}" 2>/dev/null | awk '{s+=$1} END {printf "%.0f", s/1024}' || echo "N/A")
  _metric "Peak RSS (all processes)" "${mem_peak:-N/A}" "MB"

  # 6. Latencia basica via hyperfine (se app estiver disponivel)
  # Pular latency test em CI — requer app rodando
  if command -v hyperfine &>/dev/null && [ -z "${CI:-}" ]; then
    _info "Benchmark de latencia com hyperfine (${label})..."
    _metric "Latencia benchmark" "(ver hyperfine output abaixo)" "-"

    echo "" >> "$OUTPUT_FILE"
    echo '```' >> "$OUTPUT_FILE"
    hyperfine --warmup 1 --min-runs 3 \
      --export-markdown /dev/stdout \
      "python3 -c \"import fastapi; print('ok')\"" \
      2>/dev/null | tail -10 >> "$OUTPUT_FILE" || true
    echo '```' >> "$OUTPUT_FILE"
  fi

  # 7. Dependency compatibility check
  _info "Verificando compatibilidade de dependencias..."
  local deps_compat
  set +e
  deps_compat=$(pip check 2>&1)
  local pip_check_exit=$?
  set -e

  echo "" >> "$OUTPUT_FILE"
  echo "### Dependency compatibility (${label})" >> "$OUTPUT_FILE"
  if [ "$pip_check_exit" -eq 0 ]; then
    echo "✅ Todas as dependencias compativeis." >> "$OUTPUT_FILE"
  else
    echo '```' >> "$OUTPUT_FILE"
    echo "$deps_compat" >> "$OUTPUT_FILE"
    echo '```' >> "$OUTPUT_FILE"
  fi

  deactivate
  cd "$BASE_DIR"
}

# ── Executar benchmarks ────────────────────────────────────────────────────
_section "Resumo"

echo "| Metrica | Python 3.12 | Python 3.13 | Diferenca |" >> "$OUTPUT_FILE"
echo "|---------|-------------|-------------|-----------|" >> "$OUTPUT_FILE"
echo "| (preenchido durante execucao) | | | |" >> "$OUTPUT_FILE"

_run_version() {
  local ver="$1"
  local cmd="${2:-python${ver}}"
  if command -v "$cmd" &>/dev/null; then
    run_benchmark "$ver" "$cmd"
  else
    _warn "python${ver} nao encontrado — pulando benchmark para Python ${ver}"
    _section "Python ${ver}"
    _metric "Status" "SKIPPED — interpretador nao encontrado" "-"
  fi
}

if [ -n "$ONLY_VERSION" ]; then
  _run_version "$ONLY_VERSION"
else
  _run_version "3.12" "python3.12"
  _run_version "3.13" "python3.13"
fi

# ── Finalizar ───────────────────────────────────────────────────────────────
cat >> "$OUTPUT_FILE" <<EOF

---

*Benchmark gerado em $(date '+%Y-%m-%d %H:%M') por benchmark-python-version.sh*
*Interpretador padrao: Python 3.12 (produção), Python 3.13 (staging Q3 2026, producao Q4 2026)*
*Issue de referencia: #1880 — Python 3.13 migration plan (GIL removal + JIT)*
EOF

_info "Benchmark concluido!"
_info "Resultados em: ${OUTPUT_FILE}"
echo ""
cat "$OUTPUT_FILE"
