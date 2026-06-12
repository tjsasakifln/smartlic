"""SCORE-001 (#1614): Model training for win probability prediction.

Trains a GradientBoostingClassifier with TimeSeriesSplit cross-validation,
calibrated probabilities via CalibratedClassifierCV, and serializes to joblib.

Target: AUC-ROC > 0.7 in cross-validation.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODELS_DIR = Path(__file__).resolve().parent / "models"
_MODEL_FILENAME = "win_probability_v1.joblib"
_SCALER_FILENAME = "scaler_v1.joblib"

_MIN_TRAIN_SAMPLES = 500
_CV_SPLITS = 5
_AUC_TARGET = 0.7
_RANDOM_STATE = 42


def get_model_path() -> Path:
    """Return the path to the serialized model file."""
    return _MODELS_DIR / _MODEL_FILENAME


def get_scaler_path() -> Path:
    """Return the path to the serialized scaler file."""
    return _MODELS_DIR / _SCALER_FILENAME


def _build_classifier() -> GradientBoostingClassifier:
    """Build the base GradientBoostingClassifier."""
    return GradientBoostingClassifier(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        min_samples_leaf=20,
        random_state=_RANDOM_STATE,
    )


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def train_model(
    X: np.ndarray,
    y: np.ndarray,
    feature_names: list[str] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Train the win probability model.

    Args:
        X: Feature matrix of shape (n_samples, n_features).
        y: Target vector of shape (n_samples,) with 0 (loss) / 1 (win) labels.
        feature_names: Optional list of feature names for logging.
        force: Force training even if sample count is below minimum.

    Returns:
        Dict with training results including AUC-ROC scores and model artifacts.

    Raises:
        ValueError: If insufficient samples and force=False.
    """
    if X.shape[0] < _MIN_TRAIN_SAMPLES and not force:
        raise ValueError(
            f"Insufficient training samples: {X.shape[0]} < {_MIN_TRAIN_SAMPLES}. "
            "Set force=True to override."
        )

    n_samples = X.shape[0]
    logger.info(
        "Training win probability model: %d samples, %d features",
        n_samples,
        X.shape[1],
    )

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Time-series cross-validation (temporal order preserved)
    tscv = TimeSeriesSplit(n_splits=_CV_SPLITS)
    base_clf = _build_classifier()

    # Cross-validate AUC-ROC
    cv_auc_scores = cross_val_score(
        base_clf, X_scaled, y, cv=tscv, scoring="roc_auc"
    )
    mean_auc = float(np.mean(cv_auc_scores))
    std_auc = float(np.std(cv_auc_scores))

    logger.info(
        "Cross-validation AUC-ROC: mean=%.4f, std=%.4f, scores=%s",
        mean_auc,
        std_auc,
        [f"{s:.4f}" for s in cv_auc_scores],
    )

    # Train final model on all data
    clf = _build_classifier()
    clf.fit(X_scaled, y)

    # Calibrate probabilities
    calibrated = CalibratedClassifierCV(
        estimator=clf, method="isotonic", cv="prefit"
    )
    calibrated.fit(X_scaled, y)

    # Feature importance
    importance = clf.feature_importances_.tolist()
    if feature_names:
        feat_ranking = sorted(
            zip(feature_names, importance), key=lambda x: x[1], reverse=True
        )
        logger.info("Top 5 features by importance:")
        for name, imp in feat_ranking[:5]:
            logger.info("  %s: %.4f", name, imp)

    # Predict probabilities
    y_prob = calibrated.predict_proba(X_scaled)[:, 1]
    final_auc = float(roc_auc_score(y, y_prob))

    logger.info("Final AUC-ROC on training data: %.4f", final_auc)

    if final_auc < _AUC_TARGET:
        logger.warning(
            "AUC-ROC %.4f is below target %.2f — model may need more features or data",
            final_auc,
            _AUC_TARGET,
        )

    # Compute optimal threshold via Youden's J statistic
    fpr, tpr, thresholds = roc_curve(y, y_prob)
    youden_j = tpr - fpr
    optimal_idx = int(np.argmax(youden_j))
    optimal_threshold = float(thresholds[optimal_idx])

    return {
        "classifier": clf,
        "calibrated_model": calibrated,
        "scaler": scaler,
        "auc_cv_mean": mean_auc,
        "auc_cv_std": std_auc,
        "auc_cv_scores": [float(s) for s in cv_auc_scores],
        "auc_final": final_auc,
        "feature_importance": importance,
        "optimal_threshold": optimal_threshold,
        "n_samples": n_samples,
        "n_features": X.shape[1],
    }


def save_model(
    calibrated_model: CalibratedClassifierCV,
    scaler: StandardScaler,
    model_path: str | Path | None = None,
    scaler_path: str | Path | None = None,
) -> tuple[str, str]:
    """Serialize calibrated model and scaler to disk.

    Returns:
        Tuple of (model_path, scaler_path).
    """
    import joblib

    model_path = Path(model_path or get_model_path())
    scaler_path = Path(scaler_path or get_scaler_path())

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)

    joblib.dump(calibrated_model, str(model_path))
    joblib.dump(scaler, str(scaler_path))

    model_size = os.path.getsize(str(model_path)) / 1024
    scaler_size = os.path.getsize(str(scaler_path)) / 1024

    logger.info(
        "Model saved: %s (%.1f KB), Scaler saved: %s (%.1f KB)",
        model_path,
        model_size,
        scaler_path,
        scaler_size,
    )

    return str(model_path), str(scaler_path)


def load_model(
    model_path: str | Path | None = None,
    scaler_path: str | Path | None = None,
) -> tuple[CalibratedClassifierCV, StandardScaler] | None:
    """Load serialized model and scaler.

    Returns:
        Tuple of (calibrated_model, scaler) or None if model not found.
    """
    import joblib

    model_path = Path(model_path or get_model_path())
    scaler_path = Path(scaler_path or get_scaler_path())

    if not model_path.exists() or not scaler_path.exists():
        logger.warning("Model or scaler not found at %s / %s", model_path, scaler_path)
        return None

    try:
        calibrated_model = joblib.load(str(model_path))
        scaler = joblib.load(str(scaler_path))
        logger.info("Model loaded from %s", model_path)
        return calibrated_model, scaler
    except Exception as e:
        logger.error("Failed to load model: %s", e)
        return None
