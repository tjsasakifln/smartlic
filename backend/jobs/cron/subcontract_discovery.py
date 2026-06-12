"""jobs.cron.subcontract_discovery — ARQ daily job for subcontract opportunity discovery.

MKT-001 (#1616): Scans pncp_supplier_contracts for contracts with high
subcontracting potential using configurable heuristics:

Heuristics:
1. High-value contracts (>R$1M) with multi-specialty scope (objeto contains
   multiple service areas)
2. Micro/small company winner with contract >R$5M (likely needs subcontractors)
3. High-subcontracting-rate sectors: construcao_civil, TI (informatica,
   software_desenvolvimento, software_licencas)

The job runs daily at 06:00 UTC (03:00 BRT) after the morning ingestion.
"""

import logging
from datetime import datetime, timezone, timedelta

from supabase_client import sb_execute

logger = logging.getLogger(__name__)

# Discovery config
SUBCONTRACT_MIN_VALUE = 1_000_000  # R$1M minimum for any heuristic
SUBCONTRACT_SMALL_WINNER_MIN_VALUE = 5_000_000  # R$5M for micro/small winners
SUBCONTRACT_DISCOVERY_HOUR_UTC = 3  # 03:00 UTC = 00:00 BRT

# Sectors with high subcontracting rates
HIGH_SUB_SECTORS = {
    "construcao_civil",
    "engenharia",
    "engenharia_rodoviaria",
    "informatica",
    "software_desenvolvimento",
    "software_licencas",
    "manutencao_predial",
    "servicos_prediais",
}

# Keywords suggesting multi-specialty scope (high sub potential)
MULTI_SPECIALTY_KEYWORDS = [
    "obra", "construção", "reforma", "ampliação",
    "engenharia", "arquitetura", "projeto", "executivo",
    "instalação", "montagem", "manutenção", "recuperação",
    "pavimentação", "terraplanagem", "fundação", "estrutura",
    "elétrica", "hidráulica", "hidrossanitário", "climatização",
    "sistema de incêndio", "cabeamento", "rede lógica",
    "infraestrutura", "intervenção", "restauro",
    "tecnologia da informação", "desenvolvimento", "sistema",
    "implantação", "suporte técnico", "consultoria",
]


async def run_subcontract_discovery() -> dict:
    """ARQ job function: discover subcontract opportunities from supplier contracts.

    Queries pncp_supplier_contracts for contracts matching the discovery heuristics,
    then upserts new opportunities into subcontract_opportunities table.

    Returns a summary dict with counts of discovered opportunities.
    """
    from supabase_client import get_supabase

    sb = get_supabase()
    stats = {
        "total_scanned": 0,
        "discovered": 0,
        "errors": 0,
        "heuristic_breakdown": {},
    }

    try:
        # === Heuristic 1: High-value contracts with multi-specialty scope ===
        discovered_1 = await _discover_multi_specialty(sb)
        stats["discovered"] += discovered_1
        stats["heuristic_breakdown"]["multi_specialty"] = discovered_1

        # === Heuristic 2: Micro/small company with large contracts ===
        discovered_2 = await _discover_small_winner_large_contract(sb)
        stats["discovered"] += discovered_2
        stats["heuristic_breakdown"]["small_winner_large_contract"] = discovered_2

        logger.info(
            "MKT-001: Subcontract discovery complete — %d opportunities found "
            "(multi_specialty=%d, small_winner_large=%d)",
            stats["discovered"],
            discovered_1,
            discovered_2,
        )
    except Exception as e:
        logger.error("MKT-001: Subcontract discovery failed: %s", e)
        stats["errors"] += 1

    return stats


async def _discover_multi_specialty(sb) -> int:
    """Heuristic 1: Contracts >R$1M with multi-specialty scope.

    Looks for contracts whose objeto_contrato contains multiple keywords
    suggesting the need for subcontractors across different specialties.
    """
    discovered = 0
    try:
        # Get recently created contracts (last 7 days) with value > SUBCONTRACT_MIN_VALUE
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        result = await sb_execute(
            sb.table("pncp_supplier_contracts")
            .select("id, ni_fornecedor, nome_fornecedor, valor_global, "
                    "objeto_contrato, uf, municipio, orgao_nome")
            .gte("valor_global", SUBCONTRACT_MIN_VALUE)
            .gte("data_assinatura", cutoff)
            .order("data_assinatura", desc=True)
            .limit(500)
        )
        contracts = result.data or []
        for contract in contracts:
            objeto = (contract.get("objeto_contrado") or "").lower()
            matched_keywords = [
                kw for kw in MULTI_SPECIALTY_KEYWORDS
                if kw in objeto
            ]
            if len(matched_keywords) >= 2:
                # Multiple specialties detected — high sub potential
                upserted = await _upsert_opportunity(sb, contract, {
                    "reason": "multiple_specialties",
                    "keywords": matched_keywords,
                })
                if upserted:
                    discovered += 1
    except Exception as e:
        logger.error("MKT-001: multi_specialty heuristic failed: %s", e)
    return discovered


async def _discover_small_winner_large_contract(sb) -> int:
    """Heuristic 2: Winner is likely micro/small company with contract >R$5M.

    Detects companies with patterns suggesting small size (MEI, individual names,
    or no complex corporate structure) having contracts large enough to need
    subcontracting. Also covers high-sub sectors regardless of winner size.
    """
    discovered = 0
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        result = await sb_execute(
            sb.table("pncp_supplier_contracts")
            .select("id, ni_fornecedor, nome_fornecedor, valor_global, "
                    "objeto_contrato, uf, municipio, orgao_nome")
            .gte("valor_global", SUBCONTRACT_SMALL_WINNER_MIN_VALUE)
            .gte("data_assinatura", cutoff)
            .order("data_assinatura", desc=True)
            .limit(500)
        )
        contracts = result.data or []
        for contract in contracts:
            winner_name = (contract.get("nome_fornecedor") or "").lower()
            objeto = (contract.get("objeto_contrado") or "").lower()

            # Check if winner appears to be micro/small company
            is_small = any(
                indicator in winner_name
                for indicator in ["mei", "micro", "pequena", "ltda - me", "epp",
                                  "individual", "unipessoal", "autônomo"]
            )

            # Check if sector has high sub rate
            has_high_sub_sector = any(
                sector_keyword in objeto
                for sector_keyword in HIGH_SUB_SECTORS
            )

            if is_small or has_high_sub_sector:
                upserted = await _upsert_opportunity(sb, contract, {
                    "reason": "small_winner_large_contract" if is_small
                              else "high_sub_sector",
                    "is_small_winner": is_small,
                    "has_high_sub_sector": has_high_sub_sector,
                })
                if upserted:
                    discovered += 1
    except Exception as e:
        logger.error("MKT-001: small_winner_large_contract heuristic failed: %s", e)
    return discovered


async def _upsert_opportunity(sb, contract: dict, discovery_info: dict) -> bool:
    """Upsert a subcontract opportunity into the database.

    Uses winner_cnpj + contract_id as dedup key to avoid duplicates.
    Returns True if a new opportunity was inserted, False if already exists.
    """
    try:
        contract_id = contract.get("id")
        winner_cnpj = contract.get("ni_fornecedor", "")
        winner_name = contract.get("nome_fornecedor", "")
        valor_global = contract.get("valor_global", 0) or 0
        objeto = contract.get("objeto_contrado", "") or ""

        # Check if already exists for this contract
        existing = await sb_execute(
            sb.table("subcontract_opportunities")
            .select("id")
            .eq("contract_id", contract_id)
            .limit(1)
        )
        if existing.data:
            return False  # Already discovered

        # Derive sector from object keywords
        sector = _derive_sector(objeto, discovery_info.get("keywords", []))

        # Build services list from matched keywords
        services = list(set(
            discovery_info.get("keywords", [])
            + ([obj.strip() for obj in objeto.split(",") if len(obj.strip()) > 20][:5])
        ))

        # Build discovery reason
        reason = _build_discovery_reason(discovery_info, winner_name, valor_global)

        await sb_execute(
            sb.table("subcontract_opportunities").insert({
                "contract_id": contract_id,
                "winner_cnpj": winner_cnpj,
                "winner_name": winner_name,
                "sector": sector,
                "value": float(valor_global) if valor_global else None,
                "services_needed": services[:10],  # Max 10 services
                "status": "open",
                "uf": contract.get("uf"),
                "municipio": contract.get("municipio"),
                "orgao_nome": contract.get("orgao_nome"),
                "objeto": objeto[:500] if objeto else None,  # Truncate to 500
                "discovery_reason": reason,
            })
        )
        logger.debug(
            "MKT-001: Discovered opportunity — contract=%s, winner=%s, value=R$%.2f",
            contract_id, winner_cnpj, float(valor_global) if valor_global else 0,
        )
        return True
    except Exception as e:
        logger.warning("MKT-001: Failed to upsert opportunity: %s", e)
        return False


def _derive_sector(objeto: str, keywords: list[str]) -> str:
    """Derive the most likely sector from the contract object description."""
    objeto_lower = objeto.lower()

    sector_map = {
        "construcao_civil": ["obra", "construção", "reforma", "edificação", "alvenaria"],
        "engenharia": ["engenharia", "projeto executivo", "estudo técnico"],
        "engenharia_rodoviaria": ["rodovia", "pavimentação", "estrada", "asfalto"],
        "informatica": ["informática", "ti", "tecnologia", "computador", "software"],
        "software_desenvolvimento": ["desenvolvimento", "programação", "sistema", "aplicativo"],
        "manutencao_predial": ["manutenção predial", "manutenção", "conservação"],
        "servicos_prediais": ["serviço predial", "limpeza", "vigilância", "portaria"],
    }

    for sector, sector_keywords in sector_map.items():
        if any(kw in objeto_lower for kw in sector_keywords):
            return sector

    # Fallback to first keyword match
    if keywords:
        for sector, sector_keywords in sector_map.items():
            if any(kw in sector_keywords for kw in keywords):
                return sector

    return None


def _build_discovery_reason(info: dict, winner_name: str, value: float) -> str:
    """Build a human-readable discovery reason."""
    reason = info.get("reason", "")

    if reason == "multiple_specialties":
        keywords = info.get("keywords", [])
        return (
            f"Contrato de R$ {float(value):,.2f} da {winner_name} abrange "
            f"múltiplas especialidades ({', '.join(keywords)}), "
            f"indicando alta necessidade de subcontratação."
        )
    elif reason == "small_winner_large_contract":
        return (
            f"Contrato de R$ {float(value):,.2f} — a vencedora ({winner_name}) "
            f"aparenta ser micro/pequena empresa, provavelmente necessitará "
            f"de subcontratados para execução."
        )
    elif reason == "high_sub_sector":
        return (
            f"Contrato de R$ {float(value):,.2f} da {winner_name} em setor "
            f"com alta taxa histórica de subcontratação."
        )
    return f"Potencial de subcontratação identificado — contrato de R$ {float(value):,.2f}"


def _next_utc_hour(target_hour: int) -> float:
    """Calculate seconds until next occurrence of target_hour UTC."""
    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if now.hour >= target_hour:
        next_run += timedelta(days=1)
    return max(60.0, min((next_run - now).total_seconds(), 86400.0))
