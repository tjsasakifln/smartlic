"""SCORE-001 (#1614): Win probability scoring service.

WinProbabilityScorer loads the trained model + scaler and produces
win probability scores for (bid, CNPJ) pairs with Redis caching (24h TTL).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler

from ml.feature_engineering import extract_bid_features
from ml.train_model import load_model

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache configuration
# ---------------------------------------------------------------------------

_SCORE_CACHE_TTL = 24 * 60 * 60  # 24 hours — scores don't change
_REDIS_HASH_KEY = "smartlic:score:cache"
_CACHE_PREFIX = "score:"


class WinProbabilityScorer:
    """Loads model + scaler and scores (bid, CNPJ) pairs.

    Singleton-like: load model once, reuse across requests.
    Uses in-memory fallback if Redis is unavailable.
    """

    def __init__(self) -> None:
        self._model: CalibratedClassifierCV | None = None
        self._scaler: StandardScaler | None = None
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy-load model on first use."""
        if self._loaded:
            return
        artifacts = load_model()
        if artifacts is not None:
            self._model, self._scaler = artifacts
        self._loaded = True

    @property
    def is_ready(self) -> bool:
        """Check if model is loaded and ready for scoring."""
        self._ensure_loaded()
        return self._model is not None and self._scaler is not None

    def _make_cache_key(self, bid_id: str, cnpj: str) -> str:
        """Generate deterministic cache key for a (bid, CNPJ) pair."""
        raw = f"{_CACHE_PREFIX}{bid_id}:{cnpj}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_cached_score(self, cache_key: str) -> float | None:
        """Retrieve score from cache.

        Tries Redis first, falls back to in-memory dict.
        """
        try:
            from redis_pool import get_redis_sync

            r = get_redis_sync()
            if r is not None:
                data = r.hget(_REDIS_HASH_KEY, cache_key)
                if data is not None:
                    entry = json.loads(data)
                    if time.time() - entry.get("ts", 0) < _SCORE_CACHE_TTL:
                        return entry.get("score")
        except Exception:
            logger.warning("Redis cache read failed for score", exc_info=True)

        # In-memory fallback
        entry = self._in_memory_cache.get(cache_key)
        if entry and (time.time() - entry["ts"]) < _SCORE_CACHE_TTL:
            return entry["score"]
        return None

    def _set_cached_score(self, cache_key: str, score: float) -> None:
        """Store score in cache (Redis + in-memory)."""
        data = json.dumps({"score": score, "ts": time.time()})

        try:
            from redis_pool import get_redis_sync

            r = get_redis_sync()
            if r is not None:
                r.hset(_REDIS_HASH_KEY, cache_key, data)
        except Exception:
            pass

        if cache_key not in self._in_memory_cache:
            if len(self._in_memory_cache) > 10000:
                self._in_memory_cache.clear()
        self._in_memory_cache[cache_key] = json.loads(data)

    # In-memory LRU-like fallback
    _in_memory_cache: dict[str, dict] = {}

    def score(
        self,
        bid: dict[str, Any],
        cnpj: str,
        supplier_features: dict[str, dict[str, float]] | None = None,
    ) -> float:
        """Compute win probability for a (bid, CNPJ) pair.

        Returns:
            Float between 0.0 and 1.0 representing win probability.
            Returns 0.5 if model is not ready (fallback neutral score).
        """
        self._ensure_loaded()

        if not self.is_ready:
            logger.warning("Model not loaded — returning neutral score 0.5")
            return 0.5

        # Enrich bid with CNPJ for feature extraction
        bid_with_cnpj = dict(bid)
        bid_with_cnpj["cnpj_fornecedor"] = cnpj

        bid_id = str(bid.get("id", "") or bid.get("licitacao_id", "") or hash(json.dumps(bid, default=str)))
        cache_key = self._make_cache_key(bid_id, cnpj)

        # Check cache
        cached = self._get_cached_score(cache_key)
        if cached is not None:
            return cached

        # Extract features and score
        features = extract_bid_features(bid_with_cnpj, supplier_features)
        X = np.array([features])
        X_scaled = self._scaler.transform(X)

        proba = float(self._model.predict_proba(X_scaled)[0, 1])

        # Cache and return
        self._set_cached_score(cache_key, proba)
        return proba

    def score_batch(
        self,
        bids: list[dict[str, Any]],
        cnpj: str,
        supplier_features: dict[str, dict[str, float]] | None = None,
    ) -> list[dict[str, Any]]:
        """Score a batch of bids for a given CNPJ, enriching them in-place.

        Adds '_ml_score' and '_ml_score_available' to each bid dict.
        """
        if not self.is_ready:
            for bid in bids:
                bid["_ml_score"] = 0.5
                bid["_ml_score_available"] = False
            return bids

        for bid in bids:
            bid["_ml_score"] = self.score(bid, cnpj, supplier_features)
            bid["_ml_score_available"] = True

        return bids


# Module-level singleton
_scorer: WinProbabilityScorer | None = None


def get_scorer() -> WinProbabilityScorer:
    """Get or create the singleton WinProbabilityScorer."""
    global _scorer
    if _scorer is None:
        _scorer = WinProbabilityScorer()
    return _scorer


def reset_scorer() -> None:
    """Reset the singleton scorer (useful for testing)."""
    global _scorer
    _scorer = None
