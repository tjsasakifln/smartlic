"""SCORE-001 (#1614): Tests for ML feature engineering, training, and scoring."""

import pytest
import numpy as np


class TestFeatureEngineering:
    """Test feature extraction functions."""

    def test_encode_modality(self):
        from ml.feature_engineering import encode_modality

        assert encode_modality("Pregão Eletrônico") == 1
        assert encode_modality("Concorrência") == 3
        assert encode_modality("Dispensa") == 6
        assert encode_modality(None) == 0
        assert encode_modality("") == 0

    def test_encode_uf(self):
        from ml.feature_engineering import encode_uf

        assert encode_uf("SP") > 0
        assert encode_uf("XX") == 0
        assert encode_uf(None) == 0
        assert encode_uf("") == 0

    def test_extract_epoca_ano(self):
        from ml.feature_engineering import extract_epoca_ano

        mes, ano = extract_epoca_ano("2026-03-15")
        assert mes == 3
        assert ano == 2026

        mes, ano = extract_epoca_ano(None)
        assert mes == 0
        assert ano == 0

    def test_extract_bid_features_length(self):
        from ml.feature_engineering import extract_bid_features, get_feature_names

        bid = {
            "modalidade": "Pregão Eletrônico",
            "uf": "SP",
            "valorTotalEstimado": 50000.0,
            "dataEncerramentoProposta": "2026-06-30",
            "porte": "ME",
        }
        features = extract_bid_features(bid)
        assert len(features) == len(get_feature_names())

    def test_build_supplier_features(self):
        from ml.feature_engineering import build_supplier_features

        contracts = [
            {
                "ni_fornecedor": "12345678901234",
                "valor_global": "10000.0",
                "data_assinatura": "2026-01-15T00:00:00",
            },
            {
                "ni_fornecedor": "12345678901234",
                "valor_global": "20000.0",
                "data_assinatura": "2026-03-20T00:00:00",
            },
            {
                "ni_fornecedor": "98765432109876",
                "valor_global": "50000.0",
                "data_assinatura": "2026-02-10T00:00:00",
            },
        ]
        features = build_supplier_features(contracts)

        assert "12345678901234" in features
        assert features["12345678901234"]["total_contratos"] == 2
        assert features["12345678901234"]["valor_medio"] == 15000.0

    def test_get_feature_names(self):
        from ml.feature_engineering import get_feature_names

        names = get_feature_names()
        assert isinstance(names, list)
        assert len(names) == 12
        assert "modalidade" in names
        assert "taxa_vitoria" in names


class TestModelTraining:
    """Test model training functions (without sklearn dependency issues)."""

    def test_train_model_with_insufficient_samples(self):
        """Training with insufficient samples raises ValueError."""
        from ml.train_model import train_model

        X = np.random.rand(10, 5)
        y = np.random.randint(0, 2, 10)

        with pytest.raises(ValueError, match="Insufficient training samples"):
            train_model(X, y, force=False)

    def test_train_model_with_force(self):
        """Training with force=True bypasses sample check."""
        from ml.train_model import train_model

        np.random.seed(42)
        n = 50
        X = np.random.rand(n, 5)
        # Ensure both classes exist with signal (feature 0 splits classes)
        y = (X[:, 0] > 0.5).astype(int)
        # Verify both classes present
        assert len(set(y)) == 2

        result = train_model(X, y, force=True)
        assert "classifier" in result
        assert "calibrated_model" in result
        assert "scaler" in result
        assert result["n_samples"] == n
        assert result["n_features"] == 5

    def test_train_model_with_sufficient_samples(self):
        """Training with sufficient samples produces valid outputs."""
        from ml.train_model import train_model

        np.random.seed(42)
        n = 600
        X = np.random.rand(n, 8)
        y = (X[:, 0] + X[:, 1] > 1.0).astype(int)

        result = train_model(X, y, force=False)
        assert result["auc_cv_mean"] > 0
        assert result["auc_final"] > 0
        assert len(result["feature_importance"]) == 8

    def test_save_and_load_model(self, tmp_path):
        """Save and load model round-trip."""
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.preprocessing import StandardScaler
        from ml.train_model import save_model, load_model

        X = np.random.rand(100, 5)
        y = np.random.randint(0, 2, 100)

        clf = GradientBoostingClassifier(n_estimators=10, random_state=42)
        clf.fit(X, y)

        calibrated = CalibratedClassifierCV(estimator=clf, cv="prefit")
        calibrated.fit(X, y)

        scaler = StandardScaler()
        scaler.fit(X)

        model_path = tmp_path / "model.joblib"
        scaler_path = tmp_path / "scaler.joblib"

        saved_model, saved_scaler = save_model(calibrated, scaler, model_path, scaler_path)
        assert saved_model.endswith("model.joblib")

        loaded = load_model(model_path, scaler_path)
        assert loaded is not None

        loaded_model, loaded_scaler = loaded
        proba = loaded_model.predict_proba(loaded_scaler.transform(X[:5]))[0, 1]
        assert 0.0 <= proba <= 1.0

    def test_load_model_not_found(self):
        """load_model returns None when model doesn't exist."""
        from ml.train_model import load_model

        result = load_model("/tmp/nonexistent_model.joblib", "/tmp/nonexistent_scaler.joblib")
        assert result is None


class TestScoreService:
    """Test WinProbabilityScorer service."""

    def test_scorer_not_ready_returns_neutral(self):
        """Scorer without model returns neutral 0.5."""
        from ml.score_service import WinProbabilityScorer, reset_scorer

        reset_scorer()
        scorer = WinProbabilityScorer()
        assert scorer.is_ready is False

        score = scorer.score({"id": "test", "uf": "SP"}, "12345678901234")
        assert score == 0.5

    def test_scorer_batch_not_ready(self):
        """Batch scoring without model adds _ml_score fields."""
        from ml.score_service import WinProbabilityScorer, reset_scorer

        reset_scorer()
        scorer = WinProbabilityScorer()

        bids = [{"id": "1", "uf": "SP"}, {"id": "2", "uf": "RJ"}]
        result = scorer.score_batch(bids, "12345678901234")

        assert len(result) == 2
        for bid in result:
            assert bid["_ml_score"] == 0.5
            assert bid["_ml_score_available"] is False

    def test_scorer_singleton(self):
        """get_scorer returns same instance."""
        from ml.score_service import get_scorer, reset_scorer

        reset_scorer()
        s1 = get_scorer()
        s2 = get_scorer()
        assert s1 is s2

    def test_cache_key_deterministic(self):
        """Same inputs produce same cache key."""
        from ml.score_service import WinProbabilityScorer

        scorer = WinProbabilityScorer()
        key1 = scorer._make_cache_key("bid-123", "12345678901234")
        key2 = scorer._make_cache_key("bid-123", "12345678901234")
        assert key1 == key2

        key3 = scorer._make_cache_key("bid-456", "12345678901234")
        assert key1 != key3


class TestViabilityMLIntegration:
    """Test viability.py integration with ml_score."""

    def test_calculate_viability_accepts_ml_score(self):
        """calculate_viability accepts and returns ml_score."""
        from viability import calculate_viability

        bid = {
            "modalidade": "Pregão Eletrônico",
            "uf": "SP",
            "valorTotalEstimado": 100000.0,
            "dataEncerramentoProposta": "2026-07-15",
        }
        result = calculate_viability(bid, {"SP"}, ml_score=0.85)
        assert result.ml_score == 0.85
        assert result.viability_score > 0

    def test_calculate_viability_ml_score_none_by_default(self):
        """ml_score is None when not provided."""
        from viability import calculate_viability

        bid = {
            "modalidade": "Pregão Eletrônico",
            "uf": "SP",
            "valorTotalEstimado": 100000.0,
            "dataEncerramentoProposta": "2026-07-15",
        }
        result = calculate_viability(bid, {"SP"})
        assert result.ml_score is None
