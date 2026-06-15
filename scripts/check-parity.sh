#!/bin/bash
# check-parity.sh — Compara staging vs produção para detectar drift
#
# Uso:
#   ./scripts/check-parity.sh
#   ./scripts/check-parity.sh --json   # Output em JSON para CI
#
# Requer:
#   - railway CLI autenticado
#   - gh CLI autenticado (para Supabase)
#   - jq instalado

set -euo pipefail

# Configuração
STAGING_SERVICE="bidiq-backend-staging"
PROD_SERVICE="bidiq-backend"
OUTPUT_JSON=false

[[ "${1:-}" == "--json" ]] && OUTPUT_JSON=true

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DRIFT_COUNT=0
WARNINGS=()

log_ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; WARNINGS+=("$1"); ((DRIFT_COUNT++)); }
log_err()  { echo -e "${RED}[ERR]${NC} $1"; ((DRIFT_COUNT++)); }
log_info() { echo -e "      $1"; }

check_var() {
    local var_name="$1"
    local prod_val staging_val

    prod_val=$(railway variables get "$var_name" --service "$PROD_SERVICE" --environment production 2>/dev/null || echo "ERRO")
    staging_val=$(railway variables get "$var_name" --service "$STAGING_SERVICE" --environment staging 2>/dev/null || echo "ERRO")

    if [[ "$prod_val" == "ERRO" || "$staging_val" == "ERRO" ]]; then
        log_err "$var_name: Não foi possível obter valores"
        return
    fi

    # Verificar se ambas existem (não comparar valores)
    if [[ -z "$prod_val" ]]; then
        log_warn "$var_name: Ausente em produção"
    elif [[ -z "$staging_val" ]]; then
        log_warn "$var_name: Ausente em staging"
    else
        log_ok "$var_name: Presente em ambos ambientes"
    fi
}

echo "================================================"
echo "  SmartLic — Verificação de Paridade Staging/Prod"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================"
echo ""

# === Seção 1: Railway Services ===
echo "--- Railway Services ---"

log_info "Verificando serviços Railway..."

PROD_DEPLOY=$(railway status --service "$PROD_SERVICE" --environment production 2>/dev/null || echo "ERRO")
STAGING_DEPLOY=$(railway status --service "$STAGING_SERVICE" --environment staging 2>/dev/null || echo "ERRO")

if [[ "$PROD_DEPLOY" == "ERRO" ]]; then
    log_err "Não foi possível obter status de produção. railway CLI autenticado?"
else
    log_ok "Produção: $PROD_SERVICE respondendo"
fi

if [[ "$STAGING_DEPLOY" == "ERRO" ]]; then
    log_err "Não foi possível obter status de staging. Staging provisionado?"
else
    log_ok "Staging: $STAGING_SERVICE respondendo"
fi

# === Seção 2: Variáveis de Ambiente ===
echo ""
echo "--- Variáveis de Ambiente ---"

CRITICAL_VARS=(
    "DATABASE_URL"
    "REDIS_URL"
    "OPENAI_API_KEY"
    "STRIPE_SECRET_KEY"
    "STRIPE_WEBHOOK_SECRET"
    "SUPABASE_URL"
    "SUPABASE_SERVICE_KEY"
    "SENTRY_DSN"
    "MIXPANEL_TOKEN"
    "RESEND_API_KEY"
    "CORS_ORIGINS"
    "ENVIRONMENT"
    "LOG_LEVEL"
)

log_info "Verificando ${#CRITICAL_VARS[@]} variáveis críticas..."
for var in "${CRITICAL_VARS[@]}"; do
    check_var "$var"
done

# === Seção 3: PostgreSQL ===
echo ""
echo "--- PostgreSQL (Supabase) ---"

# Usar gh para verificar Supabase (se disponível)
SUPABASE_PROD_REF="fqqyovlzdzimiwfofdjk"

log_info "Verificando versão PostgreSQL em produção..."
PG_VERSION_PROD=$(curl -s "https://api.supabase.com/v1/projects/$SUPABASE_PROD_REF" \
    -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" 2>/dev/null | jq -r '.database.version' 2>/dev/null || echo "DESCONHECIDO")

if [[ "$PG_VERSION_PROD" != "DESCONHECIDO" && -n "$PG_VERSION_PROD" ]]; then
    log_ok "Produção PostgreSQL: $PG_VERSION_PROD"
else
    log_warn "Não foi possível verificar versão PostgreSQL de produção. SUPABASE_ACCESS_TOKEN configurado?"
fi

# === Seção 4: Redis ===
echo ""
echo "--- Redis ---"

log_info "Redis gerenciado pelo Railway/Upstash — verificar manualmente:"
log_info "  Produção: railway variables get REDIS_URL --service $PROD_SERVICE"
log_info "  Staging:  railway variables get REDIS_URL --service $STAGING_SERVICE"

# === Seção 5: Versões de Runtime ===
echo ""
echo "--- Versões de Runtime ---"

log_info "Verificar manualmente nos logs de build de cada ambiente:"
log_info "  Produção: railway logs --service $PROD_SERVICE | grep 'Python 3'"
log_info "  Staging:  railway logs --service $STAGING_SERVICE | grep 'Python 3'"

# === Seção 6: Extensões PostgreSQL ===
echo ""
echo "--- Extensões PostgreSQL ---"

log_info "Executar em ambos ambientes:"
log_info "  SELECT extname, extversion FROM pg_extension ORDER BY extname;"

# === Sumário ===
echo ""
echo "================================================"
echo "  Sumário da Verificação"
echo "================================================"

if [[ $DRIFT_COUNT -eq 0 ]]; then
    echo -e "${GREEN}✅ NENHUM DRIFT DETECTADO${NC}"
    echo "   Ambos ambientes estão em paridade."
    exit 0
else
    echo -e "${RED}⚠️  $DRIFT_COUNT DIVERGÊNCIA(S) DETECTADA(S)${NC}"
    for w in "${WARNINGS[@]}"; do
        echo "   - $w"
    done
    echo ""
    echo "⚠️  Corrija as divergências antes do próximo deploy."
    exit 1
fi
