"""SCORE-001 (#1614): Feature engineering for win probability model.

Extracts bid-level features from pncp_raw_bids and pncp_supplier_contracts
to build a training DataFrame with win/loss target labels.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Modality encoding
# ---------------------------------------------------------------------------

_MODALITY_ENCODING: dict[str, int] = {
    "pregão": 1,
    "pregao": 1,
    "pregão eletrônico": 1,
    "pregao eletronico": 1,
    "pregão presencial": 2,
    "pregao presencial": 2,
    "concorrência": 3,
    "concorrencia": 3,
    "concorrência eletrônica": 3,
    "concorrencia eletronica": 3,
    "concorrência presencial": 4,
    "concorrencia presencial": 4,
    "credenciamento": 5,
    "dispensa": 6,
    "dispensa eletrônica": 6,
    "dispensa eletronica": 6,
    "dispensa de licitação": 6,
    "dispensa de licitacao": 6,
}

_UF_ENCODING: dict[str, int] = {
    uf: idx
    for idx, uf in enumerate(
        sorted(
            [
                "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
                "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
                "RJ", "RN", "RS", "RO", "RR", "SC", "SE", "SP", "TO",
            ]
        )
    )
}


def encode_modality(modalidade: str | None) -> int:
    """Encode procurement modality string to integer."""
    if not modalidade:
        return 0
    mod_lower = modalidade.strip().lower()
    for key, val in _MODALITY_ENCODING.items():
        if key in mod_lower:
            return val
    return 0


def encode_uf(uf: str | None) -> int:
    """Encode UF (state) string to integer."""
    if not uf:
        return 0
    return _UF_ENCODING.get(uf.upper().strip(), 0)


def extract_epoca_ano(data_str: str | None) -> tuple[int, int]:
    """Extract month and year from a date string."""
    if not data_str:
        return 0, 0
    try:
        dt = datetime.strptime(data_str[:10], "%Y-%m-%d")
        return dt.month, dt.year
    except (ValueError, TypeError):
        return 0, 0


# ---------------------------------------------------------------------------
# Supplier-level features
# ---------------------------------------------------------------------------


def build_supplier_features(
    contracts: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Build supplier-level features from contract history.

    Returns a dict keyed by CNPJ with:
        - taxa_vitoria: win rate (contracts / total tracked)
        - valor_medio: average contract value
        - recencia: days since last contract
        - total_contratos: total contract count
    """
    now = datetime.now(timezone.utc)
    supplier_features: dict[str, dict] = {}

    for row in contracts:
        cnpj = row.get("ni_fornecedor") or ""
        if not cnpj:
            continue
        valor = float(row.get("valor_global") or 0)
        data_str = row.get("data_assinatura") or ""

        if cnpj not in supplier_features:
            supplier_features[cnpj] = {
                "total_contratos": 0,
                "valor_total": 0.0,
                "ultima_data": None,
            }

        feat = supplier_features[cnpj]
        feat["total_contratos"] += 1
        feat["valor_total"] += valor

        if data_str:
            try:
                dt = datetime.strptime(data_str[:10], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                if feat["ultima_data"] is None or dt > feat["ultima_data"]:
                    feat["ultima_data"] = dt
            except (ValueError, TypeError):
                pass

    result: dict[str, dict[str, float]] = {}
    for cnpj, feat in supplier_features.items():
        dias_recencia = (
            (now - feat["ultima_data"]).days
            if feat.get("ultima_data")
            else 365
        )
        result[cnpj] = {
            "taxa_vitoria": min(feat["total_contratos"] / 100.0, 1.0),
            "valor_medio": round(feat["valor_total"] / max(feat["total_contratos"], 1), 2),
            "recencia": float(dias_recencia),
            "total_contratos": float(feat["total_contratos"]),
        }

    return result


# ---------------------------------------------------------------------------
# Bid-level feature vector
# ---------------------------------------------------------------------------


def extract_bid_features(
    bid: dict[str, Any],
    supplier_features: dict[str, dict[str, float]] | None = None,
) -> list[float]:
    """Extract a feature vector from a single bid dict.

    Features (12 dimensions):
        0: modalidade (encoded int)
        1: UF (encoded int)
        2: log(valor_estimado + 1)
        3: setor (placeholder)
        4: porte (encoded)
        5: mes (epoca do ano)
        6: ano
        7: taxa_vitoria
        8: valor_medio
        9: recencia
        10: qtd_licitantes (placeholder)
        11: total_contratos
    """
    modalidade_enc = encode_modality(
        bid.get("modalidadeNome") or bid.get("modalidade")
    )
    uf_enc = encode_uf(bid.get("uf", ""))
    valor = float(bid.get("valorTotalEstimado") or bid.get("valorEstimado") or 0)
    log_valor = math.log1p(valor)

    mes, ano = extract_epoca_ano(
        bid.get("dataEncerramentoProposta") or bid.get("dataAberturaProposta")
    )

    # Porte encoding
    porte_raw = bid.get("porte_orgao") or bid.get("porte") or ""
    porte_str = porte_raw.strip().lower()
    if porte_str in ("mei",):
        porte_enc = 0
    elif porte_str in ("me",):
        porte_enc = 1
    elif porte_str in ("epp",):
        porte_enc = 2
    elif porte_str in ("medio", "médio"):
        porte_enc = 3
    elif porte_str in ("grande",):
        porte_enc = 4
    else:
        porte_enc = 2

    # Supplier features
    cnpj = bid.get("cnpj_fornecedor") or ""
    if supplier_features and cnpj in supplier_features:
        sf = supplier_features[cnpj]
        taxa_vitoria = sf.get("taxa_vitoria", 0.5)
        valor_medio = sf.get("valor_medio", 0.0)
        recencia = sf.get("recencia", 365.0)
        total_contratos = sf.get("total_contratos", 0.0)
    else:
        taxa_vitoria = 0.5
        valor_medio = 0.0
        recencia = 365.0
        total_contratos = 0.0

    return [
        float(modalidade_enc),
        float(uf_enc),
        log_valor,
        0.0,  # setor — placeholder
        float(porte_enc),
        float(mes),
        float(ano),
        taxa_vitoria,
        valor_medio,
        recencia,
        0.0,  # qtd_licitantes — placeholder
        total_contratos,
    ]


_FEATURE_NAMES = [
    "modalidade",
    "uf",
    "log_valor",
    "setor",
    "porte",
    "mes",
    "ano",
    "taxa_vitoria",
    "valor_medio",
    "recencia",
    "qtd_licitantes",
    "total_contratos",
]


def get_feature_names() -> list[str]:
    """Return the ordered list of feature names."""
    return _FEATURE_NAMES.copy()
