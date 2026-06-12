"""SCORE-001: Win probability scoring service.

Loads the trained model, scores (bid, cnpj) pairs, and caches results in Redis.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import numpy as np

from ml.feature_engineering import WinProbabilityFeatures
from ml.train_model import load_model

logger = logging.getLogger(__name__)

# Redis cache TTL for score results (24h)
_SCORE_CACHE_TTL = 86400

# When model is unavailable, return this default score
_DEFAULT_PROBABILITY = 0.5
_DEFAULT_CONFIDENCE = 0.0


class WinProbabilityScorer:
    """Score bids with the trained win probability model.

    Usage:
        scorer = WinProbabilityScorer()
        result = scorer.score(bid_dict, "11222333000181")
        # -> {"probability": 0.73, "confidence": 0.85}
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        redis_client: Any | None = None,
    ):
        """Initialize the scorer.

        Args:
            model_path: Path to model .joblib file.
                        Defaults to backend/ml/models/win_probability_v1.joblib.
            redis_client: Optional Redis client for caching.
        """
        self._model = None
        self._model_path = model_path
        self._redis = redis_client
        self._model_loaded = False

    def _ensure_model(self) -> None:
        """Lazy-load the model on first use."""
        if not self._model_loaded:
            try:
                self._model = load_model(self._model_path)
                self._model_loaded = True
                logger.info("Win probability model loaded successfully.")
            except FileNotFoundError:
                logger.warning(
                    "Win probability model not found. "
                    "Use default probability of %.2f.",
                    _DEFAULT_PROBABILITY,
                )
                self._model = None

    def _cache_key(self, bid_id: str, cnpj: str) -> str:
        """Generate Redis cache key for a (bid, cnpj) pair."""
        return f"score:{bid_id}:{cnpj}"

    def score(
        self,
        bid: dict,
        cnpj: str,
        winner_history: list[dict] | None = None,
        use_cache: bool = True,
    ) -> dict[str, float]:
        """Score a single (bid, cnpj) pair.

        Args:
            bid: Bid dictionary with modalidade, uf, valor, etc.
            cnpj: CNPJ of the company to score.
            winner_history: Optional historical contracts for the company.
            use_cache: Whether to check Redis cache first (default: True).

        Returns:
            Dict with keys:
            - 'probability': float (0.0 to 1.0) — estimated win probability.
            - 'confidence': float (0.0 to 1.0) — model confidence proxy.
        """
        # Check Redis cache
        if use_cache and self._redis:
            bid_id = str(bid.get("id", bid.get("sequencialLicitacao", "")))
            cache_key = self._cache_key(bid_id, cnpj)
            cached = self._redis.get(cache_key)
            if cached:
                try:
                    import json
                    return json.loads(cached)
                except (ValueError, TypeError):
                    pass

        self._ensure_model()

        if self._model is None:
            return {
                "probability": _DEFAULT_PROBABILITY,
                "confidence": _DEFAULT_CONFIDENCE,
            }

        # Extract features
        features = WinProbabilityFeatures.extract_combined_features(bid, winner_history)

        # Build feature vector in canonical order
        feature_names = WinProbabilityFeatures.get_feature_names()
        X = np.array([[features.get(name, 0.0) for name in feature_names]])

        # Predict probability
        proba = self._model.predict_proba(X)[0, 1]
        probability = float(np.clip(proba, 0.0, 1.0))

        # Confidence is approximated by how far from 0.5 the prediction is
        # (higher distance from decision boundary = higher confidence)
        confidence = float(abs(probability - 0.5) * 2.0)  # Maps 0.5->0.0, 0.0/1.0->1.0

        result = {
            "probability": round(probability, 4),
            "confidence": round(confidence, 4),
        }

        # Store in Redis cache
        if use_cache and self._redis:
            import json
            bid_id = str(bid.get("id", bid.get("sequencialLicitacao", "")))
            cache_key = self._cache_key(bid_id, cnpj)
            try:
                self._redis.setex(cache_key, _SCORE_CACHE_TTL, json.dumps(result))
            except Exception:
                pass  # Cache failure is non-critical

        return result

    def score_batch(
        self,
        bids: list[dict],
        cnpj: str,
        winner_history: list[dict] | None = None,
    ) -> list[dict[str, float]]:
        """Score multiple bids for the same CNPJ.

        Args:
            bids: List of bid dicts.
            cnpj: CNPJ of the company.
            winner_history: Optional historical contracts.

        Returns:
            List of result dicts, one per bid, in the same order.
        """
        return [
            self.score(bid, cnpj, winner_history=winner_history)
            for bid in bids
        ]
