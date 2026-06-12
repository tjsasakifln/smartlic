"""SCORE-001: SmartLic Score routes — internal ML win probability API.

POST /v1/intel/score         — single bid score (admin/internal only)
POST /v1/intel/score/batch   — batch score (admin/internal only)

Feature flag: SMARTLIC_SCORE_ENABLED (config/features.py)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from config.features import get_feature_flag
from schemas.score import (
    ScoreBatchRequest,
    ScoreBatchResponse,
    ScoreRequest,
    ScoreResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["score"])

# Global scorer instance (lazy-initialized on first request)
_scorer = None


def _get_scorer():
    """Get or create the global WinProbabilityScorer instance."""
    global _scorer
    if _scorer is None:
        from ml.score_service import WinProbabilityScorer
        _scorer = WinProbabilityScorer()
    return _scorer


@router.post("/intel/score", response_model=ScoreResponse)
async def score_bid(request: Request, body: ScoreRequest):
    """Score a single (bid, CNPJ) pair for win probability.

    Requires SMARTLIC_SCORE_ENABLED=true. Returns default 0.5 probability
    when the feature is disabled or model is unavailable.
    """
    if not get_feature_flag("SMARTLIC_SCORE_ENABLED"):
        return ScoreResponse(
            probability=0.5,
            confidence=0.0,
            model_version="v1",
            feature_enabled=False,
        )

    scorer = _get_scorer()
    try:
        result = scorer.score(body.bid, body.cnpj)
        return ScoreResponse(
            probability=result["probability"],
            confidence=result["confidence"],
            model_version="v1",
            feature_enabled=True,
        )
    except Exception as exc:
        logger.error("Score error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Scoring failed: {exc}") from exc


@router.post("/intel/score/batch", response_model=ScoreBatchResponse)
async def score_batch(request: Request, body: ScoreBatchRequest):
    """Score multiple bids for the same CNPJ.

    Requires SMARTLIC_SCORE_ENABLED=true.
    """
    if not get_feature_flag("SMARTLIC_SCORE_ENABLED"):
        return ScoreBatchResponse(
            scores=[
                ScoreResponse(probability=0.5, confidence=0.0, model_version="v1", feature_enabled=False)
                for _ in body.bids
            ],
            count=len(body.bids),
            model_version="v1",
            feature_enabled=False,
        )

    scorer = _get_scorer()
    try:
        results = scorer.score_batch(body.bids, body.cnpj)
        scores = [
            ScoreResponse(
                probability=r["probability"],
                confidence=r["confidence"],
                model_version="v1",
                feature_enabled=True,
            )
            for r in results
        ]
        return ScoreBatchResponse(
            scores=scores,
            count=len(scores),
            model_version="v1",
            feature_enabled=True,
        )
    except Exception as exc:
        logger.error("Batch score error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Batch scoring failed: {exc}") from exc
