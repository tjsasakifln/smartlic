"""SCORE-001: Win probability model training using GradientBoostingClassifier.

Trains, evaluates, and serializes a win probability model using scikit-learn.
Uses TimeSeriesSplit for realistic CV and CalibratedClassifierCV for calibrated
probabilities.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit


logger = logging.getLogger(__name__)

# Default model path relative to this file's directory
_MODELS_DIR = Path(__file__).resolve().parent / "models"
_DEFAULT_MODEL_PATH = _MODELS_DIR / "win_probability_v1.joblib"

# Training hyperparameters
_DEFAULT_GB_PARAMS: dict[str, Any] = {
    "n_estimators": 200,
    "max_depth": 5,
    "learning_rate": 0.1,
    "subsample": 0.8,
    "min_samples_split": 20,
    "min_samples_leaf": 10,
    "random_state": 42,
    "verbose": 0,
}

# Evaluation threshold
_AUC_TARGET = 0.70


def train_win_probability_model(
    training_data: pd.DataFrame,
    model_path: str | Path | None = None,
    gb_params: dict[str, Any] | None = None,
    n_splits: int = 5,
    calibrate: bool = True,
) -> dict[str, Any]:
    """Train, evaluate, and serialize a win probability model.

    Args:
        training_data: DataFrame with feature columns + 'won' target column.
                       Should be sorted chronologically for TimeSeriesSplit.
        model_path: Path to save the serialized model.
                    Defaults to backend/ml/models/win_probability_v1.joblib.
        gb_params: Override dict for GradientBoostingClassifier hyperparameters.
        n_splits: Number of time-based CV splits (default: 5).
        calibrate: Whether to wrap model in CalibratedClassifierCV (default: True).

    Returns:
        Dict with keys:
        - 'model_path': str path to saved model
        - 'auc_train': float, AUC-ROC on training set
        - 'auc_cv_mean': float, mean CV AUC-ROC
        - 'auc_cv_std': float, std dev of CV AUC-ROC
        - 'n_features': int, number of features used
        - 'n_samples': int, number of training samples

    Raises:
        ValueError: If training_data is empty or missing 'won' column.
    """
    if training_data.empty:
        raise ValueError("Training data is empty — cannot train model.")
    if "won" not in training_data.columns:
        raise ValueError("Training data must contain a 'won' target column.")

    # Separate features and target
    feature_cols = [c for c in training_data.columns if c != "won"]
    X = training_data[feature_cols].values
    y = training_data["won"].values

    # Log class balance
    pos_rate = float(y.mean())
    logger.info(
        "Training data: %d samples, %d features, positive rate=%.3f",
        len(y),
        X.shape[1],
        pos_rate,
    )

    # Use provided params or defaults
    params = {**_DEFAULT_GB_PARAMS, **(gb_params or {})}

    # --- TimeSeriesSplit CV evaluation ---
    tscv = TimeSeriesSplit(n_splits=n_splits)
    cv_auc_scores: list[float] = []

    for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_train_fold, X_val_fold = X[train_idx], X[val_idx]
        y_train_fold, y_val_fold = y[train_idx], y[val_idx]

        fold_clf = GradientBoostingClassifier(**params)
        fold_clf.fit(X_train_fold, y_train_fold)

        y_val_prob = fold_clf.predict_proba(X_val_fold)[:, 1]
        # ROC AUC requires at least one positive and one negative in val set
        if len(np.unique(y_val_fold)) > 1:
            fold_auc = roc_auc_score(y_val_fold, y_val_prob)
            cv_auc_scores.append(fold_auc)
            logger.info("  Fold %d AUC-ROC: %.4f", fold_idx + 1, fold_auc)
        else:
            logger.warning(
                "  Fold %d: only one class in validation set, skipping AUC",
                fold_idx + 1,
            )

    # Report CV results
    if cv_auc_scores:
        auc_cv_mean = float(np.mean(cv_auc_scores))
        auc_cv_std = float(np.std(cv_auc_scores))
        logger.info(
            "CV AUC-ROC: mean=%.4f, std=%.4f (over %d folds)",
            auc_cv_mean,
            auc_cv_std,
            len(cv_auc_scores),
        )
    else:
        auc_cv_mean = 0.0
        auc_cv_std = 0.0
        logger.warning("No valid CV folds for AUC calculation.")

    # --- Train final model on full data ---
    logger.info("Training final model on full dataset...")
    base_clf = GradientBoostingClassifier(**params)
    base_clf.fit(X, y)

    # Calibrate probabilities
    if calibrate:
        # sklearn 1.8+: CalibratedClassifierCV(cv='prefit') was removed.
        # Use cv=5 for cross-validated calibration (more robust anyway).
        logger.info("Calibrating probabilities with CalibratedClassifierCV (cv=5)...")
        clf: Any = CalibratedClassifierCV(
            base_clf, method="sigmoid", cv=5, ensemble=True,
        )
        clf.fit(X, y)
        model = clf
    else:
        model = base_clf

    # --- Evaluate on full training set ---
    y_prob = model.predict_proba(X)[:, 1]
    if len(np.unique(y)) > 1:
        auc_train = roc_auc_score(y, y_prob)
        logger.info("Training set AUC-ROC: %.4f", auc_train)
    else:
        auc_train = 0.0
        logger.warning("Single class in training data — AUC not meaningful.")

    # --- Serialize model ---
    save_path = Path(model_path or _DEFAULT_MODEL_PATH)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, save_path)
    logger.info("Model saved to %s", save_path)

    return {
        "model_path": str(save_path),
        "auc_train": round(auc_train, 4),
        "auc_cv_mean": round(auc_cv_mean, 4),
        "auc_cv_std": round(auc_cv_std, 4),
        "n_features": X.shape[1],
        "n_samples": len(y),
    }


def load_model(
    model_path: str | Path | None = None,
) -> Any:
    """Load a serialized win probability model.

    Args:
        model_path: Path to the .joblib file.
                    Defaults to backend/ml/models/win_probability_v1.joblib.

    Returns:
        Loaded model (GradientBoostingClassifier or CalibratedClassifierCV).

    Raises:
        FileNotFoundError: If the model file does not exist.
    """
    load_path = Path(model_path or _DEFAULT_MODEL_PATH)
    if not load_path.exists():
        raise FileNotFoundError(
            f"Model not found at {load_path}. "
            "Train the model first with train_win_probability_model()."
        )
    return joblib.load(load_path)
