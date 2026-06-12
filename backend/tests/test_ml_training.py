"""SCORE-001: Tests for ML model training pipeline.

Uses synthetic data to verify training, evaluation, and serialization.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.feature_engineering import WinProbabilityFeatures
from ml.train_model import load_model, train_win_probability_model

logger = logging.getLogger(__name__)


@pytest.fixture
def synthetic_training_data() -> pd.DataFrame:
    """Create synthetic training data with known patterns.

    Creates 500 samples where win probability is influenced by:
    - modalidade_score (higher = more likely to win)
    - log_valor_estimado (moderate values = more accessible)
    - Winner history features
    """
    rng = np.random.RandomState(42)
    feature_names = WinProbabilityFeatures.get_feature_names()
    n_features = len(feature_names)
    n_samples = 500

    # Build feature matrix
    data: dict[str, list[float]] = {}
    for name in feature_names:
        data[name] = []

    for i in range(n_samples):
        for name in feature_names:
            if name.startswith("uf_"):
                data[name].append(0.0)
            else:
                data[name].append(float(rng.rand()))

    # Set one UF per sample
    uf_names = [n for n in feature_names if n.startswith("uf_")]
    for i in range(n_samples):
        uf_idx = i % max(len(uf_names), 1)
        for j, uf_name in enumerate(uf_names):
            data[uf_name][i] = 1.0 if j == uf_idx else 0.0

    # Create target with known signal
    mod_scores = np.array([data["modalidade_score"][i] for i in range(n_samples)])
    log_vals = np.array([data["log_valor_estimado"][i] for i in range(n_samples)])
    win_rates = np.array([
        data.get("taxa_vitoria_historica", [0.5] * n_samples)[i]
        if "taxa_vitoria_historica" in data
        else 0.5
        for i in range(n_samples)
    ])

    # Signal: combination of features
    scores = (
        0.4 * mod_scores
        + 0.3 * (1.0 - log_vals)
        + 0.3 * win_rates
        + 0.1 * rng.rand(n_samples)
    )
    data["won"] = [1.0 if s > 0.6 else 0.0 for s in scores]

    df = pd.DataFrame(data)
    pos_count = int(df["won"].sum())
    logger.info(
        "Synthetic data: %d positive, %d negative, features=%d",
        pos_count,
        n_samples - pos_count,
        n_features,
    )
    return df


class TestTrainingPipeline:
    """Tests for the model training pipeline."""

    def test_train_model_with_synthetic_data(self, synthetic_training_data: pd.DataFrame):
        """Training completes with synthetic data and produces valid metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.joblib"
            result = train_win_probability_model(
                training_data=synthetic_training_data,
                model_path=model_path,
                gb_params={"n_estimators": 20, "max_depth": 3},
                n_splits=3,
            )

            assert "model_path" in result
            assert Path(result["model_path"]).exists()
            assert "auc_train" in result
            assert "auc_cv_mean" in result
            assert "n_features" in result
            assert "n_samples" in result
            assert result["n_samples"] == len(synthetic_training_data)
            assert result["n_features"] > 0

    def test_trained_model_loads_and_predicts(self, synthetic_training_data: pd.DataFrame):
        """Saved model can be loaded and used for prediction."""
        import joblib

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "test_model.joblib"
            train_win_probability_model(
                training_data=synthetic_training_data,
                model_path=model_path,
                gb_params={"n_estimators": 20, "max_depth": 3},
                n_splits=2,
            )

            # Load and predict
            model = joblib.load(model_path)
            feature_names = WinProbabilityFeatures.get_feature_names()
            X_sample = np.array([[0.0] * len(feature_names)])
            proba = model.predict_proba(X_sample)[0, 1]
            assert 0.0 <= proba <= 1.0

    def test_empty_data_raises_error(self):
        """Empty training data raises ValueError."""
        with pytest.raises(ValueError):
            train_win_probability_model(pd.DataFrame())

    def test_missing_target_column_raises_error(self):
        """Data without 'won' column raises ValueError."""
        df = pd.DataFrame({"a": [1, 2, 3]})
        with pytest.raises(ValueError):
            train_win_probability_model(df)

    def test_model_path_is_created(self, synthetic_training_data: pd.DataFrame):
        """Model file is created at specified path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "models" / "test_v1.joblib"
            result = train_win_probability_model(
                training_data=synthetic_training_data,
                model_path=model_path,
                gb_params={"n_estimators": 10, "max_depth": 2},
                n_splits=2,
            )
            assert Path(result["model_path"]).exists()

    def test_load_model_nonexistent_raises(self):
        """Loading a nonexistent model raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_model("/nonexistent/path/model.joblib")

    def test_calibrated_probabilities(self, synthetic_training_data: pd.DataFrame):
        """Calibrated model produces probabilities in valid range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "calibrated_model.joblib"
            train_win_probability_model(
                training_data=synthetic_training_data,
                model_path=model_path,
                gb_params={"n_estimators": 20, "max_depth": 3},
                calibrate=True,
                n_splits=2,
            )

            model = load_model(model_path)
            feature_names = WinProbabilityFeatures.get_feature_names()
            X_sample = np.array([[0.5] * len(feature_names)])
            proba = model.predict_proba(X_sample)[0, 1]
            assert 0.0 <= proba <= 1.0


class TestScoreIntegration:
    """Integration test: training pipeline + scoring service."""

    def test_train_then_score(self, synthetic_training_data: pd.DataFrame):
        """Train a model, then score a bid with the WinProbabilityScorer."""
        import tempfile
        from pathlib import Path

        from ml.score_service import WinProbabilityScorer

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "integ_model.joblib"
            train_win_probability_model(
                training_data=synthetic_training_data,
                model_path=model_path,
                gb_params={"n_estimators": 20, "max_depth": 3},
                n_splits=2,
            )

            scorer = WinProbabilityScorer(model_path=model_path)
            bid = {
                "modalidadeNome": "Pregão Eletrônico",
                "valorTotalEstimado": "150000",
                "uf": "SP",
            }
            result = scorer.score(bid, "11222333000181")
            assert "probability" in result
            assert "confidence" in result
            assert 0.0 <= result["probability"] <= 1.0
            assert 0.0 <= result["confidence"] <= 1.0

    def test_batch_scoring(self, synthetic_training_data: pd.DataFrame):
        """Batch scoring returns correct number of results."""
        import tempfile
        from pathlib import Path

        from ml.score_service import WinProbabilityScorer

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = Path(tmpdir) / "batch_model.joblib"
            train_win_probability_model(
                training_data=synthetic_training_data,
                model_path=model_path,
                gb_params={"n_estimators": 10, "max_depth": 2},
                n_splits=2,
            )

            scorer = WinProbabilityScorer(model_path=model_path)
            bids = [
                {"modalidadeNome": "Pregão", "uf": "SP"},
                {"modalidadeNome": "Concorrência", "uf": "RJ"},
                {"modalidadeNome": "Dispensa", "uf": "MG"},
            ]
            results = scorer.score_batch(bids, "11222333000181")
            assert len(results) == 3
            for r in results:
                assert "probability" in r
                assert "confidence" in r
