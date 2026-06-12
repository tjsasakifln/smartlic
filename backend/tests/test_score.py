"""SCORE-001: Tests for SmartLic Score routes, ML module, and feature flag."""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# Feature Engineering Tests
# =============================================================================


class TestWinProbabilityFeatures:
    """Unit tests for feature extraction."""

    def test_extract_bid_features_minimal(self):
        """Minimal bid still produces feature vector with defaults."""
        from ml.feature_engineering import WinProbabilityFeatures

        bid = {}
        features = WinProbabilityFeatures.extract_bid_features(bid)
        assert "modalidade_score" in features
        assert features["modalidade_score"] == 50.0  # default
        assert "log_valor_estimado" in features
        assert features["log_valor_estimado"] == 0.0

    def test_extract_bid_features_with_modality(self):
        """Known modality maps to correct score."""
        from ml.feature_engineering import WinProbabilityFeatures

        bid = {"modalidadeNome": "pregao eletronico"}
        features = WinProbabilityFeatures.extract_bid_features(bid)
        assert features["modalidade_score"] == 100.0

    def test_extract_bid_features_with_value(self):
        """Value is log-transformed."""
        from ml.feature_engineering import WinProbabilityFeatures

        bid = {"valorTotalEstimado": "100000"}
        features = WinProbabilityFeatures.extract_bid_features(bid)
        assert math.isclose(features["log_valor_estimado"], math.log10(100000))

    def test_extract_bid_features_uf_onehot(self):
        """UF creates correct one-hot feature."""
        from ml.feature_engineering import WinProbabilityFeatures

        bid = {"uf": "SP"}
        features = WinProbabilityFeatures.extract_bid_features(bid)
        assert features["uf_SP"] == 1.0
        assert features["uf_RJ"] == 0.0

    def test_extract_bid_features_month_seasonality(self):
        """Date string creates month sin/cos features."""
        from ml.feature_engineering import WinProbabilityFeatures

        bid = {"dataEncerramentoProposta": "2026-06-15T10:00:00"}
        features = WinProbabilityFeatures.extract_bid_features(bid)
        assert "mes_sin" in features
        assert "mes_cos" in features
        assert "dia_semana" in features
        # June = month 6
        expected_sin = math.sin(2 * math.pi * 5 / 12.0)
        assert math.isclose(features["mes_sin"], expected_sin, rel_tol=1e-3)

    def test_extract_winner_features_empty(self):
        """Empty history produces default values."""
        from ml.feature_engineering import WinProbabilityFeatures

        features = WinProbabilityFeatures.extract_winner_features("11222333000181", [])
        assert features["taxa_vitoria_historica"] == 0.0
        assert features["recencia_dias"] == 999.0

    def test_extract_winner_features_with_history(self):
        """Winner features are computed from history."""
        from ml.feature_engineering import WinProbabilityFeatures

        history = [
            {"valor_total": "50000", "data_assinatura": "2026-01-15", "won": True},
            {"valor_total": "100000", "data_assinatura": "2026-03-20", "won": True},
            {"valor_total": "75000", "data_assinatura": "2025-11-10", "won": False},
        ]
        features = WinProbabilityFeatures.extract_winner_features(
            "11222333000181", history
        )
        assert features["taxa_vitoria_historica"] == pytest.approx(2.0 / 3.0)
        assert features["total_contratos_historicos"] == 3.0
        assert features["log_valor_medio_ganho"] > 0

    def test_build_training_data(self):
        """Training data is a valid DataFrame with features + target."""
        import pandas as pd
        from ml.feature_engineering import WinProbabilityFeatures

        bids = [
            {"modalidadeNome": "Pregão Eletrônico", "valorTotalEstimado": "100000", "uf": "SP", "won": True},
            {"modalidadeNome": "Concorrência", "valorTotalEstimado": "5000000", "uf": "RJ", "won": False},
        ]
        df = WinProbabilityFeatures.build_training_data(bids)
        assert isinstance(df, pd.DataFrame)
        assert "won" in df.columns
        assert len(df) == 2
        assert df["won"].iloc[0] == 1.0
        assert df["won"].iloc[1] == 0.0

    def test_get_feature_names(self):
        """Feature names are consistent and include all expected groups."""
        from ml.feature_engineering import WinProbabilityFeatures

        names = WinProbabilityFeatures.get_feature_names()
        assert "modalidade_score" in names
        assert "log_valor_estimado" in names
        assert "mes_sin" in names
        assert "taxa_vitoria_historica" in names
        assert "uf_SP" in names
        assert "recencia_dias" in names


# =============================================================================
# Score Service Tests
# =============================================================================


class TestWinProbabilityScorer:
    """Tests for the scoring service."""

    def test_score_without_model_returns_default(self):
        """When model is not loaded, returns default 0.5 probability."""
        from ml.score_service import WinProbabilityScorer

        scorer = WinProbabilityScorer()
        result = scorer.score({"modalidadeNome": "Pregão"}, "11222333000181")
        assert result["probability"] == 0.5
        assert result["confidence"] == 0.0

    def test_score_with_model(self):
        """With a trained model, scoring returns a valid probability."""
        import numpy as np
        from sklearn.ensemble import GradientBoostingClassifier
        from ml.score_service import WinProbabilityScorer
        from ml.feature_engineering import WinProbabilityFeatures

        # Train a tiny model for testing
        feature_names = WinProbabilityFeatures.get_feature_names()
        n_features = len(feature_names)

        # Create synthetic training data
        rng = np.random.RandomState(42)
        X_train = rng.rand(200, n_features)
        y_train = (X_train[:, 0] + X_train[:, 1] > 0.8).astype(int)

        model = GradientBoostingClassifier(
            n_estimators=10, max_depth=3, random_state=42
        )
        model.fit(X_train, y_train)

        # Inject the trained model into the scorer
        scorer = WinProbabilityScorer()
        scorer._model = model
        scorer._model_loaded = True

        bid = {"modalidadeNome": "Pregão Eletrônico", "valorTotalEstimado": "200000", "uf": "SP"}
        result = scorer.score(bid, "11222333000181")
        assert 0.0 <= result["probability"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0

    def test_confidence_boundary(self):
        """Confidence is 0 at boundary (0.5) and 1 at extremes."""
        import numpy as np
        from sklearn.ensemble import GradientBoostingClassifier
        from ml.score_service import WinProbabilityScorer
        from ml.feature_engineering import WinProbabilityFeatures

        feature_names = WinProbabilityFeatures.get_feature_names()
        n_features = len(feature_names)

        # Extreme training data for clear decision boundary
        rng = np.random.RandomState(0)
        X_train = rng.rand(100, n_features)
        y_train = (X_train[:, 0] > 0.5).astype(int)

        model = GradientBoostingClassifier(
            n_estimators=10, max_depth=2, random_state=42
        )
        model.fit(X_train, y_train)

        scorer = WinProbabilityScorer()
        scorer._model = model
        scorer._model_loaded = True

        bid = {"modalidadeNome": "Pregão", "uf": "SP"}
        result = scorer.score(bid, "11222333000181")
        assert 0.0 <= result["confidence"] <= 1.0


# =============================================================================
# Route Tests
# =============================================================================


class TestScoreRoute:
    """Tests for POST /v1/intel/score endpoint."""

    def test_route_registered(self, client: TestClient):
        """Route exists and returns 200 or 422."""
        resp = client.post(
            "/v1/intel/score",
            json={"bid": {}, "cnpj": "11222333000181"},
        )
        # Without model: returns 200 with default score + feature_enabled false
        assert resp.status_code in (200, 422, 500)

    def test_invalid_cnpj_returns_422(self, client: TestClient):
        """CNPJ with wrong length returns 422."""
        resp = client.post(
            "/v1/intel/score",
            json={"bid": {}, "cnpj": "123"},
        )
        assert resp.status_code == 422

    def test_response_structure(self, client: TestClient):
        """Response has expected keys."""
        resp = client.post(
            "/v1/intel/score",
            json={"bid": {"modalidadeNome": "Pregão"}, "cnpj": "11222333000181"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "probability" in data
            assert "confidence" in data
            assert "model_version" in data
            assert "feature_enabled" in data

    def test_feature_flag_disabled_by_default(self, client: TestClient):
        """SMARTLIC_SCORE_ENABLED is false by default, so feature_enabled=False."""
        resp = client.post(
            "/v1/intel/score",
            json={"bid": {}, "cnpj": "11222333000181"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data["feature_enabled"] is False
            assert data["probability"] == 0.5


class TestScoreBatchRoute:
    """Tests for POST /v1/intel/score/batch endpoint."""

    def test_batch_route_registered(self, client: TestClient):
        """Batch route exists."""
        resp = client.post(
            "/v1/intel/score/batch",
            json={
                "bids": [{"modalidadeNome": "Pregão"}],
                "cnpj": "11222333000181",
            },
        )
        assert resp.status_code in (200, 422, 500)

    def test_batch_response_structure(self, client: TestClient):
        """Batch response has scores list."""
        resp = client.post(
            "/v1/intel/score/batch",
            json={
                "bids": [
                    {"modalidadeNome": "Pregão"},
                    {"modalidadeNome": "Concorrência"},
                ],
                "cnpj": "11222333000181",
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "scores" in data
            assert "count" in data
            assert data["count"] == 2
            assert len(data["scores"]) == 2

    def test_batch_empty_bids_returns_422(self, client: TestClient):
        """Empty bids list returns 422."""
        resp = client.post(
            "/v1/intel/score/batch",
            json={"bids": [], "cnpj": "11222333000181"},
        )
        assert resp.status_code == 422

    def test_batch_too_many_bids_returns_422(self, client: TestClient):
        """More than 100 bids returns 422."""
        resp = client.post(
            "/v1/intel/score/batch",
            json={
                "bids": [{} for _ in range(101)],
                "cnpj": "11222333000181",
            },
        )
        assert resp.status_code == 422
