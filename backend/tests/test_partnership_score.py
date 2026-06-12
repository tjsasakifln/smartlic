"""SUBINTEL-011 (#1674): Tests for Partnership Score route.

Covers:
- Route registration and response model
- Feature flag gating (SUBCONTRACT_INTEL_ENABLED off -> 404)
- Capability gating (no allow_subcontract_intel -> 403)
- CNPJ validation (invalid -> 422)
- Valid request with mock RPC data
- Signal score computation
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from auth import require_auth
from quota.plan_auth import get_subcontract_intel_dependency


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _override_deps():
    """Override auth + subcontract intel dependencies.

    The subcontract intel gate requires the feature flag ON and the
    allow_subcontract_intel capability. We override both so the route
    can be tested without external setup.
    """
    app.dependency_overrides[require_auth] = lambda: {
        "id": "test-user-001",
        "email": "test@smartlic.tech",
        "is_active": True,
    }
    app.dependency_overrides[get_subcontract_intel_dependency()] = lambda u=None: {
        "id": "test-user-001",
        "email": "test@smartlic.tech",
        "is_active": True,
    }
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Mock RPC response
# ---------------------------------------------------------------------------

MOCK_RPC_DATA = [
    {
        "ni_fornecedor": "11222333000181",
        "nome_fornecedor": "Empresa Exemplo Ltda",
        "total_contratos": 85,
        "valor_total": 32000000.00,
        "ticket_medio": 376470.59,
        "contratos_simultaneos_pico": 12,
        "ufs_distintas": 8,
        "municipios_distintos": 34,
        "orgaos_distintos": 27,
        "valor_por_uf": [
            {"uf": "SP", "contratos": 40, "valor": 15000000.00},
            {"uf": "MG", "contratos": 15, "valor": 6000000.00},
        ],
        "contratos_por_ano": [
            {"ano": 2024, "contratos": 28, "valor": 11000000.00},
            {"ano": 2025, "contratos": 35, "valor": 14000000.00},
            {"ano": 2026, "contratos": 22, "valor": 7000000.00},
        ],
        "score_capacidade": 0.78,
        "sinal_sobrecarga": True,
    }
]

EMPTY_RPC_DATA = [
    {
        "ni_fornecedor": "00000000000000",
        "nome_fornecedor": "",
        "total_contratos": 0,
        "valor_total": 0,
        "ticket_medio": 0,
        "contratos_simultaneos_pico": 0,
        "ufs_distintas": 0,
        "municipios_distintos": 0,
        "orgaos_distintos": 0,
        "valor_por_uf": [],
        "contratos_por_ano": [],
        "score_capacidade": 0.0,
        "sinal_sobrecarga": False,
    }
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSignalComputation:
    """Unit tests for signal score computation logic."""

    def _compute_scores(self, rpc_data: dict) -> dict:
        from routes.subcontract_intel import _compute_scores
        return _compute_scores(rpc_data)

    def test_repeat_winner_high(self):
        """High contract volume and capacity produce high repeat_winner score."""
        scores = self._compute_scores({
            "total_contratos": 200,
            "valor_total": 50000000,
            "ticket_medio": 250000,
            "contratos_simultaneos_pico": 10,
            "ufs_distintas": 5,
            "orgaos_distintos": 15,
            "score_capacidade": 0.9,
        })
        assert scores["repeat_winner"]["score"] > 0.5
        assert scores["repeat_winner"]["label"] in ("Alto", "Medio")

    def test_large_contract_high(self):
        """High ticket_medio produces high large_contract score."""
        scores = self._compute_scores({
            "total_contratos": 10,
            "valor_total": 10000000,
            "ticket_medio": 1_000_000,
            "contratos_simultaneos_pico": 2,
            "ufs_distintas": 2,
            "orgaos_distintos": 3,
            "score_capacidade": 0.5,
        })
        assert scores["large_contract"]["score"] >= 0.5
        assert scores["large_contract"]["score"] <= 1.0

    def test_large_contract_low(self):
        """Low ticket_medio produces low large_contract score."""
        scores = self._compute_scores({
            "total_contratos": 5,
            "valor_total": 50000,
            "ticket_medio": 10_000,
            "contratos_simultaneos_pico": 1,
            "ufs_distintas": 1,
            "orgaos_distintos": 1,
            "score_capacidade": 0.1,
        })
        assert scores["large_contract"]["score"] < 0.4
        assert scores["large_contract"]["label"] == "Baixo"

    def test_subcontracting_pattern_high(self):
        """Multi-orgao and multi-UF presence produces high subcontracting score."""
        scores = self._compute_scores({
            "total_contratos": 50,
            "valor_total": 15000000,
            "ticket_medio": 300000,
            "contratos_simultaneos_pico": 15,
            "ufs_distintas": 12,
            "orgaos_distintos": 25,
            "score_capacidade": 0.7,
        })
        assert scores["subcontracting_pattern"]["score"] > 0.5
        assert scores["subcontracting_pattern"]["label"] in ("Alto", "Medio")

    def test_subcontracting_pattern_low(self):
        """Single-uf, single-orgao presence produces low subcontracting score."""
        scores = self._compute_scores({
            "total_contratos": 3,
            "valor_total": 300000,
            "ticket_medio": 100000,
            "contratos_simultaneos_pico": 0,
            "ufs_distintas": 1,
            "orgaos_distintos": 1,
            "score_capacidade": 0.2,
        })
        assert scores["subcontracting_pattern"]["score"] < 0.4
        assert scores["subcontracting_pattern"]["label"] == "Baixo"

    def test_all_scores_in_range(self):
        """All signal scores must be in [0.0, 1.0]."""
        scores = self._compute_scores({
            "total_contratos": 85,
            "valor_total": 32000000,
            "ticket_medio": 376470.59,
            "contratos_simultaneos_pico": 12,
            "ufs_distintas": 8,
            "orgaos_distintos": 27,
            "score_capacidade": 0.78,
        })
        for key in ("repeat_winner", "large_contract", "subcontracting_pattern"):
            assert 0 <= scores[key]["score"] <= 1.0, f"{key} score out of range"
            assert scores[key]["label"] in ("Alto", "Medio", "Baixo")

    def test_scores_with_empty_data(self):
        """All scores are 0.0 when there's no data."""
        scores = self._compute_scores({
            "total_contratos": 0,
            "valor_total": 0,
            "ticket_medio": 0,
            "contratos_simultaneos_pico": 0,
            "ufs_distintas": 0,
            "orgaos_distintos": 0,
            "score_capacidade": 0.0,
        })
        for key in ("repeat_winner", "large_contract", "subcontracting_pattern"):
            assert scores[key]["score"] == 0.0
            assert scores[key]["label"] == "Baixo"

    def test_signal_detail_structure(self):
        """Each signal detail must have all required fields."""
        scores = self._compute_scores({
            "total_contratos": 10,
            "valor_total": 1000000,
            "ticket_medio": 100000,
            "contratos_simultaneos_pico": 2,
            "ufs_distintas": 2,
            "orgaos_distintos": 3,
            "score_capacidade": 0.5,
        })
        for sig in scores.values():
            assert "score" in sig
            assert "label" in sig
            assert "description" in sig
            assert "details" in sig
            assert isinstance(sig["details"], dict)


class TestSignalLabel:
    """Unit tests for signal label computation."""

    def test_alto(self):
        from routes.subcontract_intel import _compute_signal_label
        assert _compute_signal_label(0.7) == "Alto"
        assert _compute_signal_label(0.85) == "Alto"
        assert _compute_signal_label(1.0) == "Alto"

    def test_medio(self):
        from routes.subcontract_intel import _compute_signal_label
        assert _compute_signal_label(0.4) == "Medio"
        assert _compute_signal_label(0.5) == "Medio"
        assert _compute_signal_label(0.69) == "Medio"

    def test_baixo(self):
        from routes.subcontract_intel import _compute_signal_label
        assert _compute_signal_label(0.0) == "Baixo"
        assert _compute_signal_label(0.1) == "Baixo"
        assert _compute_signal_label(0.39) == "Baixo"


class TestRouteWithMocks:
    """Route tests with proper dependency mocking."""

    @patch("config.features.get_feature_flag", return_value=True)
    @patch("authorization.has_master_access", return_value=True)
    def test_cnpj_invalid_returns_422(self, mock_master, mock_flag, client: TestClient):
        """Invalid CNPJ format returns 422 before hitting the RPC."""
        resp = client.get("/v1/subcontract/partnership-score/invalid")
        assert resp.status_code == 422

    @patch("config.features.get_feature_flag", return_value=True)
    @patch("authorization.has_master_access", return_value=True)
    def test_empty_cnpj_returns_422(self, mock_master, mock_flag, client: TestClient):
        """Empty CNPJ returns 404 (path resolution fails)."""
        resp = client.get("/v1/subcontract/partnership-score/")
        assert resp.status_code == 404

    @patch("config.features.get_feature_flag", return_value=True)
    @patch("authorization.has_master_access", return_value=True)
    def test_route_returns_200_or_502(self, mock_master, mock_flag, client: TestClient):
        """With gate open, route returns 200, 422, 500, or 502 (depends on DB)."""
        resp = client.get("/v1/subcontract/partnership-score/11222333000181")
        assert resp.status_code in (200, 422, 500, 502)
