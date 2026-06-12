"""SCORE-001 (#1614): SmartLic Score API routes.

POST /v1/intel/score — score a single bid for a CNPJ (admin/internal)
POST /v1/intel/score/batch — score multiple bids for a CNPJ

Feature flag: SMARTLIC_SCORE_ENABLED (config/features.py)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from admin import require_admin
from config.features import get_feature_flag
from ml.score_service import get_scorer
from schemas.score import (
    BatchScoreRequest,
    BatchScoreResponse,
    ScoreRequest,
    ScoreResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["score"], prefix="/intel")


@router.get("/score/status")
async def score_status():
    """Check if the ML model is loaded and ready (public health check)."""
    from ml.score_service import get_scorer

    scorer = get_scorer()
    return {
        "model_ready": scorer.is_ready,
        "feature_enabled": get_feature_flag("SMARTLIC_SCORE_ENABLED", False),
    }


@router.post(
    "/score",
    summary="Score a single bid for win probability (internal/admin)",
    response_model=ScoreResponse,
)
async def score_bid(
    request: ScoreRequest,
    admin: dict = Depends(require_admin),
):
    if not get_feature_flag("SMARTLIC_SCORE_ENABLED", False):
        raise HTTPException(status_code=503, detail="SmartLic Score feature is disabled")

    scorer = get_scorer()
    if not scorer.is_ready:
        raise HTTPException(status_code=503, detail="ML model not loaded — retrain or check artifacts")

    # Build bid dict from request
    bid_dict = {
        "id": request.bid_id,
        "modalidade": request.modalidade,
        "uf": request.uf,
        "valorTotalEstimado": request.valor_estimado,
        "dataEncerramentoProposta": request.data_encerramento,
        "porte": request.porte,
    }

    probability = scorer.score(bid_dict, request.cnpj)

    return ScoreResponse(
        bid_id=request.bid_id,
        cnpj=request.cnpj,
        win_probability=round(probability, 4),
        score_available=True,
        model_version="v1",
    )


@router.post(
    "/score/batch",
    summary="Score multiple bids for a CNPJ (internal/admin)",
    response_model=BatchScoreResponse,
)
async def score_batch(
    request: BatchScoreRequest,
    admin: dict = Depends(require_admin),
):
    if not get_feature_flag("SMARTLIC_SCORE_ENABLED", False):
        raise HTTPException(status_code=503, detail="SmartLic Score feature is disabled")

    scorer = get_scorer()
    if not scorer.is_ready:
        raise HTTPException(status_code=503, detail="ML model not loaded — retrain or check artifacts")

    scores: list[ScoreResponse] = []
    total_prob = 0.0

    for bid_req in request.bids:
        bid_dict = {
            "id": bid_req.bid_id,
            "modalidade": bid_req.modalidade,
            "uf": bid_req.uf,
            "valorTotalEstimado": bid_req.valor_estimado,
            "dataEncerramentoProposta": bid_req.data_encerramento,
            "porte": bid_req.porte,
        }
        prob = scorer.score(bid_dict, request.cnpj)
        total_prob += prob
        scores.append(
            ScoreResponse(
                bid_id=bid_req.bid_id,
                cnpj=request.cnpj,
                win_probability=round(prob, 4),
                score_available=True,
                model_version="v1",
            )
        )

    mean_prob = total_prob / len(scores) if scores else 0.0

    return BatchScoreResponse(
        cnpj=request.cnpj,
        scores=scores,
        mean_probability=round(mean_prob, 4),
        model_version="v1",
    )
