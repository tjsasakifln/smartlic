#!/usr/bin/env bash
# ============================================================================
# run-zap-scan.sh — Executa OWASP ZAP contra um alvo (staging/producao)
# ============================================================================
#
# Uso:
#   bash scripts/security/run-zap-scan.sh --target <URL> [--mode full|quick|api] [--output <dir>]
#
# Modos:
#   full    - Scan completo: spider + active scan (OWASP Top 10 + API Top 10) — ~45min
#   quick   - Scan rapido: passive scan + spider convencional — ~10min
#   api     - Scan de API: importa OpenAPI schema e testa endpoints — ~20min
#
# Requisitos:
#   - Docker instalado e em execucao
#   - Portas 8080 e 8081 disponiveis
#
# Exemplos:
#   bash scripts/security/run-zap-scan.sh --target https://staging.smartlic.tech --mode full
#   bash scripts/security/run-zap-scan.sh --target https://staging.smartlic.tech --mode quick --output ./reports
#   bash scripts/security/run-zap-scan.sh --target https://api.smartlic.tech/openapi.json --mode api
#
# Exit codes:
#   0 = Scan concluido (com ou sem alertas)
#   1 = Erro de configuracao
#   2 = ZAP nao disponivel
# ============================================================================

set -euo pipefail

# --- Config defaults ---
TARGET=""
MODE="full"
OUTPUT_DIR="./zap-reports"
TIMEOUT_MIN=60
ZAP_CONTAINER_NAME="zap-scan-$(date +%s)"
ZAP_PORT=8080
ZAP_PORT_API=8081
ZAP_IMAGE="ghcr.io/zaproxy/zaproxy:stable"

# Farben para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# --- Help ---
usage() {
    grep "^#" "$0" | grep -v "^#!/" | sed 's/^# //g' | sed 's/^#$//g'
    exit 0
}

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target|-t)
            TARGET="$2"
            shift 2
            ;;
        --mode|-m)
            MODE="$2"
            shift 2
            ;;
        --output|-o)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            log_error "Argumento desconhecido: $1"
            usage
            ;;
    esac
done

# --- Validacoes ---
if [[ -z "$TARGET" ]]; then
    log_error "--target e obrigatorio"
    usage
fi

if [[ ! "$MODE" =~ ^(full|quick|api)$ ]]; then
    log_error "Modo invalido: $MODE. Use full, quick, ou api."
    exit 1
fi

if ! command -v docker &>/dev/null; then
    log_error "Docker nao encontrado. Instale Docker primeiro."
    exit 2
fi

if ! docker info &>/dev/null; then
    log_error "Docker daemon nao esta em execucao."
    exit 2
fi

# --- Setup ---
mkdir -p "$OUTPUT_DIR"
REPORT_FILE="$OUTPUT_DIR/zap-report-$(date +%Y%m%d-%H%M%S)"
TIMESTAMP=$(date +%Y-%m-%d_%H-%M-%S)

log_info "=== OWASP ZAP Scan ==="
log_info "Target:  $TARGET"
log_info "Mode:    $MODE"
log_info "Output:  $OUTPUT_DIR"
log_info ""

# --- Cleanup handler ---
cleanup() {
    log_info "Limpando container ZAP..."
    docker stop "$ZAP_CONTAINER_NAME" 2>/dev/null || true
    docker rm "$ZAP_CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

# --- Start ZAP container ---
log_info "Iniciando ZAP container (${ZAP_IMAGE})..."
docker run --rm -d \
    --name "$ZAP_CONTAINER_NAME" \
    -p "$ZAP_PORT":8080 \
    -p "$ZAP_PORT_API":8081 \
    -v "$(pwd)/$OUTPUT_DIR":/zap/wrk:rw \
    "$ZAP_IMAGE" \
    zap.sh -daemon -port 8080 -host 0.0.0.0 \
    -config api.disablekey=true \
    -config api.addrs.addr.name=.* \
    -config api.addrs.addr.regex=true

# Aguardar ZAP iniciar
log_info "Aguardando ZAP iniciar (ate 30s)..."
for i in $(seq 1 30); do
    if curl -s "http://localhost:${ZAP_PORT_API}" >/dev/null 2>&1; then
        log_ok "ZAP pronto (${i}s)"
        break
    fi
    if [[ "$i" -eq 30 ]]; then
        log_error "ZAP nao iniciou apos 30s. Verifique logs do container."
        docker logs "$ZAP_CONTAINER_NAME" --tail 20
        exit 2
    fi
    sleep 1
done

# --- Execute scan based on mode ---
case "$MODE" in
    full)
        log_info "Modo FULL: spider + active scan"
        log_info "Passo 1/4: Spider tradicional..."
        docker exec "$ZAP_CONTAINER_NAME" zap-cli \
            -p 8080 spider "$TARGET" 2>&1

        log_info "Passo 2/4: Spider AJAX (SPA)..."
        curl -s "http://localhost:${ZAP_PORT_API}/JSON/spiderAjax/action/scan/?url=${TARGET}&maxChildren=10" >/dev/null

        log_info "Passo 3/4: Active scan (OWASP Top 10 + API Top 10)..."
        docker exec "$ZAP_CONTAINER_NAME" zap-cli \
            -p 8080 active-scan --scanners all "$TARGET" 2>&1

        log_info "Passo 4/4: Exportando relatorios..."
        # HTML Report
        curl -s "http://localhost:${ZAP_PORT_API}/OTHER/core/other/htmlreport/" \
            -o "${REPORT_FILE}.html"
        # XML Report (para processamento)
        curl -s "http://localhost:${ZAP_PORT_API}/OTHER/core/other/xmlreport/" \
            -o "${REPORT_FILE}.xml"
        # JSON Report
        curl -s "http://localhost:${ZAP_PORT_API}/JSON/core/view/alerts/" \
            -o "${REPORT_FILE}.json"
        ;;

    quick)
        log_info "Modo QUICK: passive scan + spider"
        log_info "Passo 1/2: Spider tradicional..."
        docker exec "$ZAP_CONTAINER_NAME" zap-cli \
            -p 8080 spider "$TARGET" 2>&1

        log_info "Passo 2/2: Coletando alertas passive scan..."
        sleep 10  # Aguardar processamento passivo
        curl -s "http://localhost:${ZAP_PORT_API}/JSON/core/view/alerts/" \
            -o "${REPORT_FILE}.json"
        curl -s "http://localhost:${ZAP_PORT_API}/OTHER/core/other/htmlreport/" \
            -o "${REPORT_FILE}.html"
        ;;

    api)
        log_info "Modo API: import OpenAPI + scan endpoints"
        log_info "Passo 1/3: Importando OpenAPI spec..."
        curl -s "http://localhost:${ZAP_PORT_API}/JSON/openapi/action/importUrl/" \
            --data-urlencode "url=${TARGET}" >/dev/null

        log_info "Passo 2/3: Active scan em endpoints descobertos..."
        # Obter context ID e fazer scan
        docker exec "$ZAP_CONTAINER_NAME" zap-cli \
            -p 8080 active-scan --scanners all "${TARGET}" 2>&1

        log_info "Passo 3/3: Exportando relatorios..."
        curl -s "http://localhost:${ZAP_PORT_API}/JSON/core/view/alerts/" \
            -o "${REPORT_FILE}.json"
        curl -s "http://localhost:${ZAP_PORT_API}/OTHER/core/other/htmlreport/" \
            -o "${REPORT_FILE}.html"
        ;;
esac

# --- Summary ---
log_ok "Scan concluido!"
log_info "Relatorios salvos em:"
log_info "  HTML: ${REPORT_FILE}.html"
log_info "  JSON: ${REPORT_FILE}.json"
if [[ -f "${REPORT_FILE}.xml" ]]; then
    log_info "  XML:  ${REPORT_FILE}.xml"
fi

# Parse alert count from JSON if available
if [[ -f "${REPORT_FILE}.json" ]]; then
    TOTAL_ALERTS=$(python3 -c "
import json
with open('${REPORT_FILE}.json') as f:
    data = json.load(f)
alerts = data.get('alerts', [])
print(f'Total: {len(alerts)}')
for a in alerts:
    risk = a.get('risk', 'Unknown')
    name = a.get('name', 'Unknown')
    print(f'  [{risk}] {name}')
" 2>/dev/null || echo "  (parse manual do JSON)")
    log_info "Resumo de alertas:"
    echo "$TOTAL_ALERTS"
fi

log_ok "Scan finalizado com sucesso em $(date)"
exit 0
