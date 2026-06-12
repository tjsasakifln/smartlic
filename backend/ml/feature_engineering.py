"""SCORE-001: Feature engineering for SmartLic Score ML win probability model.

Extracts features from 1.5M+ historic bids (pncp_raw_bids) and 4.2M+ contracts
(pncp_supplier_contracts) to train a GradientBoostingClassifier that predicts
win probability given a bid + CNPJ.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Brazilian states ordered list for one-hot encoding reference
_ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

# Modality scores (same as viability.py)
_MODALITY_SCORES: dict[str, int] = {
    "pregao eletronico": 100,
    "pregao": 100,
    "pregao presencial": 80,
    "concorrencia eletronica": 70,
    "concorrencia": 70,
    "concorrencia presencial": 60,
    "credenciamento": 50,
    "dispensa": 40,
    "dispensa eletronica": 40,
    "dispensa de licitacao": 40,
}
_DEFAULT_MODALITY_SCORE = 50


def _normalize_modalidade(modalidade: str | None) -> str:
    """Normalize modality string for feature extraction."""
    if not modalidade:
        return ""
    return modalidade.strip().lower()


def _modality_feature(modalidade: str | None) -> float:
    """Convert modality to a numeric score feature."""
    norm = _normalize_modalidade(modalidade)
    if not norm:
        return _DEFAULT_MODALITY_SCORE
    if norm in _MODALITY_SCORES:
        return float(_MODALITY_SCORES[norm])
    for key, val in _MODALITY_SCORES.items():
        if key in norm:
            return float(val)
    return float(_DEFAULT_MODALITY_SCORE)


def _month_sin_cos(month: int) -> tuple[float, float]:
    """Encode month as sine/cosine features for cyclical representation."""
    radians = 2 * math.pi * (month - 1) / 12.0
    return math.sin(radians), math.cos(radians)


# =============================================================================
# Feature Extraction
# =============================================================================


class WinProbabilityFeatures:
    """Feature engineering pipelines for win probability model.

    Three main pipelines:
    - extract_bid_features(): features from a single bid (modalidade, UF, value, etc.)
    - extract_winner_features(): features from a winner's history
    - build_training_data(): builds a full DataFrame for model training
    """

    # ------------------------------------------------------------------
    # Bid-level features
    # ------------------------------------------------------------------

    @staticmethod
    def extract_bid_features(bid: dict) -> dict[str, float]:
        """Extract features from a single bid dictionary.

        Args:
            bid: Bid dict with keys like modalidadeNome, uf, valorTotalEstimado,
                 dataEncerramentoProposta, setor, orgao, qtd_licitantes, etc.

        Returns:
            Dict of feature name -> float value suitable for model input.
        """
        features: dict[str, float] = {}

        # --- Categorical features encoded as numeric ---

        # Modality score
        modalidade = bid.get("modalidadeNome") or bid.get("modalidade")
        features["modalidade_score"] = _modality_feature(modalidade)

        # UF one-hot (only the presence of this UF)
        uf = (bid.get("uf") or "").upper().strip()
        for u in _ALL_UFS:
            features[f"uf_{u}"] = 1.0 if u == uf else 0.0

        # --- Numerical features ---

        # Estimated value (log-transformed to handle wide range)
        valor = float(bid.get("valorTotalEstimado") or bid.get("valorEstimado") or 0)
        if valor > 0:
            features["log_valor_estimado"] = math.log10(max(valor, 1.0))
        else:
            features["log_valor_estimado"] = 0.0

        # Month seasonality (sin/cos encoding)
        data_str = bid.get("dataEncerramentoProposta") or bid.get("dataAberturaProposta")
        if data_str:
            try:
                dt = datetime.strptime(data_str[:10], "%Y-%m-%d")
                sin_m, cos_m = _month_sin_cos(dt.month)
                features["mes_sin"] = sin_m
                features["mes_cos"] = cos_m
                # Day of week as a feature
                features["dia_semana"] = float(dt.weekday())
            except (ValueError, TypeError):
                features["mes_sin"] = 0.0
                features["mes_cos"] = 0.0
                features["dia_semana"] = 0.0
        else:
            features["mes_sin"] = 0.0
            features["mes_cos"] = 0.0
            features["dia_semana"] = 0.0

        # Quantity of bidders (when available)
        qtd = bid.get("quantidadeLicitantes") or bid.get("qtd_licitantes")
        if qtd is not None:
            features["qtd_licitantes"] = float(qtd)
        else:
            features["qtd_licitantes"] = -1.0  # Sentinel for unknown

        return features

    # ------------------------------------------------------------------
    # Winner-level features
    # ------------------------------------------------------------------

    @staticmethod
    def extract_winner_features(
        cnpj: str,
        winner_history: list[dict] | None = None,
    ) -> dict[str, float]:
        """Extract features from a winner's historical contract data.

        Args:
            cnpj: CNPJ of the company (14 digits).
            winner_history: List of historical contract dicts for this CNPJ.
                           Each dict should have 'valor_total', 'won' (bool),
                           'data_assinatura', etc.
                           If None, returns default/zero features.

        Returns:
            Dict of feature name -> float value.
        """
        features: dict[str, float] = {}

        if not winner_history:
            features["taxa_vitoria_historica"] = 0.0
            features["valor_medio_ganho"] = 0.0
            features["log_valor_medio_ganho"] = 0.0
            features["recencia_dias"] = 999.0
            features["total_contratos_historicos"] = 0.0
            return features

        # Historical win rate
        total = len(winner_history)
        wins = sum(1 for h in winner_history if h.get("won", True))
        features["taxa_vitoria_historica"] = wins / max(total, 1)
        features["total_contratos_historicos"] = float(total)

        # Average contract value
        valores = [
            float(h.get("valor_total", 0))
            for h in winner_history
            if h.get("valor_total")
        ]
        if valores:
            avg_val = sum(valores) / len(valores)
            features["valor_medio_ganho"] = avg_val
            features["log_valor_medio_ganho"] = math.log10(max(avg_val, 1.0))
        else:
            features["valor_medio_ganho"] = 0.0
            features["log_valor_medio_ganho"] = 0.0

        # Recency (days since last win)
        now = datetime.now(timezone.utc)
        latest: datetime | None = None
        for h in winner_history:
            data_str = h.get("data_assinatura") or h.get("data_publicacao")
            if data_str:
                try:
                    dt = datetime.strptime(data_str[:10], "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                    if latest is None or dt > latest:
                        latest = dt
                except (ValueError, TypeError):
                    pass
        if latest:
            features["recencia_dias"] = float((now - latest).days)
        else:
            features["recencia_dias"] = 999.0

        return features

    # ------------------------------------------------------------------
    # Combined features (bid + winner)
    # ------------------------------------------------------------------

    @staticmethod
    def extract_combined_features(
        bid: dict,
        winner_history: list[dict] | None = None,
    ) -> dict[str, float]:
        """Combine bid-level and winner-level features into a single vector.

        Args:
            bid: Bid dictionary.
            winner_history: Historical contracts for the company.

        Returns:
            Combined feature dict.
        """
        features = WinProbabilityFeatures.extract_bid_features(bid)
        cnpj = bid.get("cnpj_vencedor") or bid.get("cnpj_fornecedor") or ""
        winner_feats = WinProbabilityFeatures.extract_winner_features(
            cnpj, winner_history
        )
        features.update(winner_feats)
        return features

    # ------------------------------------------------------------------
    # Training data builder
    # ------------------------------------------------------------------

    @staticmethod
    def build_training_data(
        bids: list[dict],
        contracts_by_cnpj: dict[str, list[dict]] | None = None,
    ) -> pd.DataFrame:
        """Build a training DataFrame from bid records with win/loss targets.

        Args:
            bids: List of bid dicts. Each must have a 'won' (bool) key
                  indicating whether the company won this bid.
                  Also needs bid-level fields for feature extraction.
            contracts_by_cnpj: Optional pre-grouped contracts. If None,
                               winner_history will be empty for all rows.

        Returns:
            pd.DataFrame with feature columns + 'won' target column.
        """
        rows: list[dict[str, float]] = []

        contracts_by_cnpj = contracts_by_cnpj or {}

        for bid in bids:
            cnpj = bid.get("cnpj_vencedor") or bid.get("cnpj_fornecedor") or ""
            winner_history = contracts_by_cnpj.get(cnpj, [])
            combined = WinProbabilityFeatures.extract_combined_features(
                bid, winner_history
            )
            combined["won"] = float(bid.get("won", False))
            rows.append(combined)

        df = pd.DataFrame(rows)

        # Fill any NaN values that might have slipped through
        for col in df.columns:
            if df[col].dtype in (np.float64, np.float32, np.int64, np.int32):
                df[col] = df[col].fillna(0.0)

        logger.info(
            "Training data built: %d rows, %d features",
            len(df),
            len([c for c in df.columns if c != "won"]),
        )
        return df

    # ------------------------------------------------------------------
    # Feature metadata
    # ------------------------------------------------------------------

    @staticmethod
    def get_feature_names() -> list[str]:
        """Return the canonical list of feature names in order."""
        base = [
            "modalidade_score",
            "log_valor_estimado",
            "mes_sin",
            "mes_cos",
            "dia_semana",
            "qtd_licitantes",
        ]
        uf_features = [f"uf_{u}" for u in _ALL_UFS]
        winner_features = [
            "taxa_vitoria_historica",
            "log_valor_medio_ganho",
            "recencia_dias",
            "total_contratos_historicos",
        ]
        return base + uf_features + winner_features
