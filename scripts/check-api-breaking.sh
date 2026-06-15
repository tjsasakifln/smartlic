#!/bin/bash
# check-api-breaking.sh — Detecta breaking changes entre duas versões do OpenAPI schema
#
# Uso:
#   ./scripts/check-api-breaking.sh <base_branch> <head_branch>
#   ./scripts/check-api-breaking.sh main feature/nova-versao
#   ./scripts/check-api-breaking.sh --local schema_v1.json schema_v2.json
#
# Requer: python3

set -euo pipefail

BASE_BRANCH="${1:-origin/main}"
HEAD_BRANCH="${2:-HEAD}"

echo "=== API Breaking Change Detection ==="
echo "Base:  $BASE_BRANCH"
echo "Head:  $HEAD_BRANCH"
echo ""

# Extrair OpenAPI schema de cada branch (assume backend rodando localmente ou arquivo)
extract_schema() {
    local branch="$1"
    local output="$2"

    # Tentar obter schema do backend local primeiro
    if curl -s http://localhost:8000/openapi.json > "$output" 2>/dev/null; then
        return 0
    fi

    # Fallback: usar arquivo de schema committado
    if [[ -f "backend/openapi.json" ]]; then
        cp "backend/openapi.json" "$output"
        return 0
    fi

    echo "ERRO: Não foi possível obter OpenAPI schema."
    echo "  Execute o backend localmente: cd backend && uvicorn main:app --port 8000"
    echo "  Ou gere o schema: cd backend && python -c 'from main import app; import json; json.dump(app.openapi(), open(\"openapi.json\",\"w\"))'"
    exit 1
}

SCHEMA_BASE="/tmp/openapi_base_$$.json"
SCHEMA_HEAD="/tmp/openapi_head_$$.json"

if [[ "${1:-}" == "--local" ]]; then
    cp "${2:-schema_v1.json}" "$SCHEMA_BASE"
    cp "${3:-schema_v2.json}" "$SCHEMA_HEAD"
else
    echo "Extraindo schema do branch $BASE_BRANCH..."
    git show "$BASE_BRANCH:backend/openapi.json" > "$SCHEMA_BASE" 2>/dev/null || {
        echo "AVISO: backend/openapi.json não encontrado em $BASE_BRANCH"
        echo "{}" > "$SCHEMA_BASE"
    }

    echo "Extraindo schema do branch $HEAD_BRANCH..."
    git show "$HEAD_BRANCH:backend/openapi.json" > "$SCHEMA_HEAD" 2>/dev/null || {
        # Tentar gerar localmente
        if [[ -f "backend/openapi.json" ]]; then
            cp "backend/openapi.json" "$SCHEMA_HEAD"
        else
            echo "{}" > "$SCHEMA_HEAD"
        fi
    }
fi

# Análise de breaking changes via Python
python3 << PYEOF
import json
import sys

def load_schema(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return {"paths": {}, "components": {"schemas": {}}}

base = load_schema("$SCHEMA_BASE")
head = load_schema("$SCHEMA_HEAD")

errors = []
warnings = []
info = []

# 1. Comparar paths (endpoints)
base_paths = set(base.get("paths", {}).keys())
head_paths = set(head.get("paths", {}).keys()) if head else set()

removed_paths = base_paths - head_paths
added_paths = head_paths - base_paths

for p in sorted(removed_paths):
    errors.append(f"ENDPOINT REMOVIDO: {p}")

for p in sorted(added_paths):
    info.append(f"Endpoint adicionado: {p}")

# 2. Comparar schemas (tipos de dados)
base_schemas = base.get("components", {}).get("schemas", {})
head_schemas = head.get("components", {}).get("schemas", {})

for schema_name in base_schemas:
    if schema_name not in head_schemas:
        warnings.append(f"SCHEMA REMOVIDO: {schema_name}")
        continue

    base_props = base_schemas[schema_name].get("properties", {})
    head_props = head_schemas[schema_name].get("properties", {})

    for prop_name in base_props:
        if prop_name not in head_props:
            errors.append(f"CAMPO REMOVIDO: {schema_name}.{prop_name}")
        else:
            base_type = base_props[prop_name].get("type", "unknown")
            head_type = head_props[prop_name].get("type", "unknown")
            if base_type != head_type:
                errors.append(f"TIPO ALTERADO: {schema_name}.{prop_name} ({base_type} → {head_type})")

    for prop_name in head_props:
        if prop_name not in base_props:
            info.append(f"Campo adicionado: {schema_name}.{prop_name}")

    # Verificar required fields
    base_required = set(base_schemas[schema_name].get("required", []))
    head_required = set(head_schemas[schema_name].get("required", []))

    new_required = head_required - base_required
    for field in sorted(new_required):
        errors.append(f"CAMPO TORNOU-SE OBRIGATÓRIO: {schema_name}.{field}")

# Output
print("=" * 50)
print("  RESULTADO DA ANÁLISE DE BREAKING CHANGES")
print("=" * 50)
print()

if errors:
    print(f"🔴 BREAKING CHANGES ({len(errors)}):")
    for e in errors:
        print(f"  ❌ {e}")
    print()

if warnings:
    print(f"🟡 WARNINGS ({len(warnings)}):")
    for w in warnings:
        print(f"  ⚠️  {w}")
    print()

if info:
    print(f"🟢 INFO ({len(info)}):")
    for i in info:
        print(f"  ℹ️  {i}")
    print()

if not errors and not warnings and not info:
    print("✅ Nenhuma mudança detectada entre os schemas.")

print()
print("=" * 50)

# Exit code
if errors:
    print("❌ BREAKING CHANGES detectados. Corrija ou justifique antes do merge.")
    sys.exit(1)
else:
    print("✅ Nenhum breaking change detectado.")
    sys.exit(0)
PYEOF

EXIT_CODE=$?

# Limpeza
rm -f "$SCHEMA_BASE" "$SCHEMA_HEAD"

exit $EXIT_CODE
