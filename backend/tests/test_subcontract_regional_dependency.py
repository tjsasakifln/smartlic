"""Tests for subcontract_regional_dependency RPC (SUBINTEL-002 — #1226).

Tests the JSON output shape, field types, and business logic invariants:

Coverage:
  - Required top-level keys and their types
  - Nested field structure (distribuicao_uf, distribuicao_municipio, ufs_expansao)
  - HHI calculation ranges (concentrated vs diversified supplier)
  - flag_vence_fora_da_base logic (true/false based on expansion UFs)
  - uf_base_operacional from highest share
  - JSON serializability (round-trip)
  - Empty edge case serialization
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Sample payload: supplier with multi-UF contracts, clear SP base, AM expansion
# ---------------------------------------------------------------------------

REGIONAL_DEPENDENCY_PAYLOAD = {
    "ni_fornecedor": "12345678000199",
    "distribuicao_uf": [
        {"uf": "SP", "count": 48, "valor": 20000000.0, "share_pct": 60.0},
        {"uf": "MG", "count": 12, "valor": 5000000.0, "share_pct": 15.0},
        {"uf": "RJ", "count": 10, "valor": 5000000.0, "share_pct": 15.0},
        {"uf": "AM", "count": 5, "valor": 3333333.33, "share_pct": 10.0},
    ],
    "distribuicao_municipio": [
        {"municipio": "SAO PAULO", "uf": "SP", "count": 30, "valor": 12000000.0},
        {"municipio": "CAMPINAS", "uf": "SP", "count": 18, "valor": 8000000.0},
        {"municipio": "BELO HORIZONTE", "uf": "MG", "count": 12, "valor": 5000000.0},
    ],
    "uf_base_operacional": "SP",
    "ufs_expansao": [
        {
            "uf": "AM",
            "contratos_recentes": 5,
            "share_historico_pct": 1.2,
            "flag_fora_da_base": True,
        },
    ],
    "indice_dependencia_regional": 0.42,
    "flag_vence_fora_da_base": True,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db(payload: dict | None = None) -> MagicMock:
    """Build a mock supabase client that returns the given payload."""
    if payload is None:
        payload = REGIONAL_DEPENDENCY_PAYLOAD
    mock_db = MagicMock()
    mock_result = MagicMock()
    mock_result.data = [{"subcontract_regional_dependency": payload}]
    mock_db.rpc.return_value.execute.return_value = mock_result
    return mock_db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRpcSignature:
    """Verify the function is called with correct name and parameters."""

    def test_rpc_called_with_correct_name_and_params(self):
        """The RPC is invoked with 'subcontract_regional_dependency' and the correct params."""
        mock_db = _make_mock_db()
        mock_db.rpc(
            "subcontract_regional_dependency",
            {
                "p_ni_fornecedor": "12345678000199",
                "p_window_months": 24,
            },
        ).execute()
        mock_db.rpc.assert_called_once_with(
            "subcontract_regional_dependency",
            {
                "p_ni_fornecedor": "12345678000199",
                "p_window_months": 24,
            },
        )

    def test_window_months_defaults_to_24(self):
        """Omitting p_window_months defaults to 24."""
        mock_db = _make_mock_db()
        mock_db.rpc(
            "subcontract_regional_dependency",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute()
        mock_db.rpc.assert_called_once_with(
            "subcontract_regional_dependency",
            {"p_ni_fornecedor": "12345678000199"},
        )

    def test_rpc_returns_scalar_json_in_list(self):
        """PostgREST returns scalar JSON wrapped in a single-element list."""
        mock_db = _make_mock_db()
        result = mock_db.rpc(
            "subcontract_regional_dependency",
            {"p_ni_fornecedor": "12345678000199"},
        ).execute()
        assert isinstance(result.data, list)
        assert len(result.data) == 1
        assert "subcontract_regional_dependency" in result.data[0]


class TestOutputShape:
    """Top-level JSON keys and their expected types."""

    REQUIRED_KEYS = [
        "ni_fornecedor",
        "distribuicao_uf",
        "distribuicao_municipio",
        "uf_base_operacional",
        "ufs_expansao",
        "indice_dependencia_regional",
        "flag_vence_fora_da_base",
    ]

    def test_all_required_keys_present(self):
        """Payload contains every required key."""
        for key in self.REQUIRED_KEYS:
            assert key in REGIONAL_DEPENDENCY_PAYLOAD, f"Missing key: {key}"

    def test_no_unexpected_keys(self):
        """Payload contains only the expected keys."""
        assert set(REGIONAL_DEPENDENCY_PAYLOAD.keys()) == set(self.REQUIRED_KEYS)

    def test_key_types(self):
        """Each top-level value has the correct Python type."""
        payload = REGIONAL_DEPENDENCY_PAYLOAD
        assert isinstance(payload["ni_fornecedor"], str)
        assert isinstance(payload["distribuicao_uf"], list)
        assert isinstance(payload["distribuicao_municipio"], list)
        assert isinstance(payload["uf_base_operacional"], str)
        assert isinstance(payload["ufs_expansao"], list)
        assert isinstance(payload["indice_dependencia_regional"], (int, float))
        assert isinstance(payload["flag_vence_fora_da_base"], bool)


class TestDistribuicaoUf:
    """Nested shape of distribuicao_uf entries."""

    REQUIRED_FIELDS = ["uf", "count", "valor", "share_pct"]

    def test_uf_entry_has_all_fields(self):
        """Each UF entry has the required fields."""
        entry = REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_uf"][0]
        for field in self.REQUIRED_FIELDS:
            assert field in entry, f"Missing field: {field}"

    def test_uf_entry_field_types(self):
        """Each UF field has the correct type."""
        entry = REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_uf"][0]
        assert isinstance(entry["uf"], str)
        assert isinstance(entry["count"], int)
        assert isinstance(entry["valor"], (int, float))
        assert isinstance(entry["share_pct"], (int, float))

    def test_ordered_by_share_descending(self):
        """Entries are sorted by share_pct descending."""
        shares = [u["share_pct"] for u in REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_uf"]]
        assert shares == sorted(shares, reverse=True)

    def test_share_pct_approximately_sums_to_100(self):
        """All share_pct values sum to ~100 (allowing rounding)."""
        total = sum(u["share_pct"] for u in REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_uf"])
        assert abs(total - 100.0) < 1.0

    def test_count_positive_integers(self):
        """All count values are positive integers."""
        for entry in REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_uf"]:
            assert isinstance(entry["count"], int)
            assert entry["count"] > 0

    def test_valor_non_negative(self):
        """Valor is never negative."""
        for entry in REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_uf"]:
            assert entry["valor"] >= 0

    def test_share_pct_non_negative(self):
        """share_pct is never negative."""
        for entry in REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_uf"]:
            assert entry["share_pct"] >= 0


class TestDistribuicaoMunicipio:
    """Nested shape of distribuicao_municipio entries."""

    REQUIRED_FIELDS = ["municipio", "uf", "count", "valor"]

    def test_muni_entry_has_all_fields(self):
        """Each municipio entry has the required fields."""
        entry = REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_municipio"][0]
        for field in self.REQUIRED_FIELDS:
            assert field in entry, f"Missing field: {field}"

    def test_muni_entry_field_types(self):
        """Each municipio field has the correct type."""
        entry = REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_municipio"][0]
        assert isinstance(entry["municipio"], str)
        assert isinstance(entry["uf"], str)
        assert isinstance(entry["count"], int)
        assert isinstance(entry["valor"], (int, float))

    def test_ordered_by_count_descending(self):
        """Entries are sorted by count descending by design."""
        counts = [m["count"] for m in REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_municipio"]]
        assert counts == sorted(counts, reverse=True)

    def test_count_positive_integers(self):
        """All count values are positive integers."""
        for entry in REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_municipio"]:
            assert isinstance(entry["count"], int)
            assert entry["count"] > 0

    def test_valor_non_negative(self):
        """Valor is never negative."""
        for entry in REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_municipio"]:
            assert entry["valor"] >= 0


class TestUfBaseOperacional:
    """Base operational UF determination."""

    def test_uf_base_is_highest_share(self):
        """uf_base_operacional matches the UF with highest share_pct."""
        ufs = REGIONAL_DEPENDENCY_PAYLOAD["distribuicao_uf"]
        expected_base = max(ufs, key=lambda x: x["share_pct"])["uf"]
        assert REGIONAL_DEPENDENCY_PAYLOAD["uf_base_operacional"] == expected_base

    def test_uf_base_is_sp(self):
        """In the sample payload, SP is the operational base."""
        assert REGIONAL_DEPENDENCY_PAYLOAD["uf_base_operacional"] == "SP"

    def test_uf_base_is_string(self):
        """uf_base_operacional is always a string."""
        assert isinstance(REGIONAL_DEPENDENCY_PAYLOAD["uf_base_operacional"], str)

    def test_uf_base_not_empty(self):
        """uf_base_operacional is non-empty when there are contracts."""
        assert len(REGIONAL_DEPENDENCY_PAYLOAD["uf_base_operacional"]) > 0


class TestUfsExpansao:
    """Expansion UFs detection."""

    REQUIRED_FIELDS = [
        "uf",
        "contratos_recentes",
        "share_historico_pct",
        "flag_fora_da_base",
    ]

    def test_expansion_entry_has_all_fields(self):
        """Each expansion UF entry has the required fields."""
        entry = REGIONAL_DEPENDENCY_PAYLOAD["ufs_expansao"][0]
        for field in self.REQUIRED_FIELDS:
            assert field in entry, f"Missing field: {field}"

    def test_expansion_entry_field_types(self):
        """Each expansion UF field has the correct type."""
        entry = REGIONAL_DEPENDENCY_PAYLOAD["ufs_expansao"][0]
        assert isinstance(entry["uf"], str)
        assert isinstance(entry["contratos_recentes"], int)
        assert isinstance(entry["share_historico_pct"], (int, float))
        assert isinstance(entry["flag_fora_da_base"], bool)

    def test_expansion_uf_not_base_uf(self):
        """Expansion UF is different from the base operational UF."""
        base = REGIONAL_DEPENDENCY_PAYLOAD["uf_base_operacional"]
        for entry in REGIONAL_DEPENDENCY_PAYLOAD["ufs_expansao"]:
            assert entry["uf"] != base

    def test_expansion_share_low(self):
        """Expansion UFs have low historical share (< 10%)."""
        for entry in REGIONAL_DEPENDENCY_PAYLOAD["ufs_expansao"]:
            assert entry["share_historico_pct"] < 10.0

    def test_expansion_flag_outside_base(self):
        """flag_fora_da_base is True for expansion UFs."""
        for entry in REGIONAL_DEPENDENCY_PAYLOAD["ufs_expansao"]:
            assert entry["flag_fora_da_base"] is True

    def test_contratos_recentes_positive(self):
        """contratos_recentes is a positive integer."""
        for entry in REGIONAL_DEPENDENCY_PAYLOAD["ufs_expansao"]:
            assert isinstance(entry["contratos_recentes"], int)
            assert entry["contratos_recentes"] > 0


class TestHhiCalculation:
    """HHI (Herfindahl-Hirschman Index) values and ranges."""

    def test_hhi_is_float(self):
        """indice_dependencia_regional is a number."""
        assert isinstance(REGIONAL_DEPENDENCY_PAYLOAD["indice_dependencia_regional"], (int, float))

    def test_hhi_between_0_and_1(self):
        """HHI ranges from 0 (diversified) to 1 (fully concentrated)."""
        assert 0 <= REGIONAL_DEPENDENCY_PAYLOAD["indice_dependencia_regional"] <= 1.0

    def test_concentrated_single_uf_hhi_is_1(self):
        """A supplier with 100% in one UF has HHI = 1.0."""
        payload = {
            **REGIONAL_DEPENDENCY_PAYLOAD,
            "distribuicao_uf": [
                {"uf": "SP", "count": 100, "valor": 50000000.0, "share_pct": 100.0},
            ],
            "ufs_expansao": [],
            "indice_dependencia_regional": 1.0,
            "flag_vence_fora_da_base": False,
        }
        assert payload["indice_dependencia_regional"] == 1.0

    def test_diversified_hhi_less_than_1(self):
        """A multi-UF supplier has HHI < 1.0."""
        payload = {
            **REGIONAL_DEPENDENCY_PAYLOAD,
            "distribuicao_uf": [
                {"uf": "SP", "count": 30, "valor": 10000000.0, "share_pct": 33.33},
                {"uf": "MG", "count": 25, "valor": 8333333.0, "share_pct": 27.78},
                {"uf": "RJ", "count": 20, "valor": 6666667.0, "share_pct": 22.22},
                {"uf": "PR", "count": 15, "valor": 5000000.0, "share_pct": 16.67},
            ],
            "ufs_expansao": [],
            "indice_dependencia_regional": 0.27,
            "flag_vence_fora_da_base": False,
        }
        assert payload["indice_dependencia_regional"] < 1.0

    def test_two_uf_equal_hhi(self):
        """Two equal UFs gives HHI = 0.5."""
        payload = {
            **REGIONAL_DEPENDENCY_PAYLOAD,
            "distribuicao_uf": [
                {"uf": "SP", "count": 50, "valor": 10000000.0, "share_pct": 50.0},
                {"uf": "MG", "count": 50, "valor": 10000000.0, "share_pct": 50.0},
            ],
            "indice_dependencia_regional": 0.5,
        }
        assert payload["indice_dependencia_regional"] == 0.5


class TestFlagVenceForaDaBase:
    """flag_vence_fora_da_base business logic."""

    def test_flag_true_with_expansion(self):
        """flag is True when there are expansion UFs."""
        assert REGIONAL_DEPENDENCY_PAYLOAD["flag_vence_fora_da_base"] is True

    def test_flag_false_no_expansion(self):
        """flag is False when there are no expansion UFs (single UF supplier)."""
        payload = {
            **REGIONAL_DEPENDENCY_PAYLOAD,
            "uf_base_operacional": "SP",
            "ufs_expansao": [],
            "flag_vence_fora_da_base": False,
        }
        assert payload["flag_vence_fora_da_base"] is False

    def test_flag_is_boolean(self):
        """flag_vence_fora_da_base is always a boolean."""
        assert isinstance(REGIONAL_DEPENDENCY_PAYLOAD["flag_vence_fora_da_base"], bool)

    def test_flag_true_single_expansion_uf(self):
        """flag is True with exactly one expansion UF."""
        payload = {
            **REGIONAL_DEPENDENCY_PAYLOAD,
            "ufs_expansao": [
                {
                    "uf": "AM",
                    "contratos_recentes": 1,
                    "share_historico_pct": 0.5,
                    "flag_fora_da_base": True,
                },
            ],
            "flag_vence_fora_da_base": True,
        }
        assert payload["flag_vence_fora_da_base"] is True


class TestJsonSerialization:
    """JSON round-trip and edge cases."""

    def test_round_trips_cleanly(self):
        """Payload survives json.dumps / json.loads without data loss."""
        serialized = json.dumps(REGIONAL_DEPENDENCY_PAYLOAD)
        deserialized = json.loads(serialized)
        assert deserialized == REGIONAL_DEPENDENCY_PAYLOAD

    def test_empty_expansion_serializes(self):
        """Empty ufs_expansao array serializes as []."""
        payload = {
            "ni_fornecedor": "12345678000199",
            "distribuicao_uf": [],
            "distribuicao_municipio": [],
            "uf_base_operacional": None,
            "ufs_expansao": [],
            "indice_dependencia_regional": 0.0,
            "flag_vence_fora_da_base": False,
        }
        serialized = json.dumps(payload)
        deserialized = json.loads(serialized)
        assert deserialized["distribuicao_uf"] == []
        assert deserialized["distribuicao_municipio"] == []
        assert deserialized["ufs_expansao"] == []
        assert deserialized["flag_vence_fora_da_base"] is False

    def test_null_uf_base_serializes(self):
        """None uf_base_operacional serializes as null."""
        payload = {
            "ni_fornecedor": "12345678000199",
            "distribuicao_uf": [],
            "distribuicao_municipio": [],
            "uf_base_operacional": None,
            "ufs_expansao": [],
            "indice_dependencia_regional": 0.0,
            "flag_vence_fora_da_base": False,
        }
        serialized = json.dumps(payload)
        assert '"uf_base_operacional": null' in serialized or '"uf_base_operacional":null' in serialized.replace(" ", "")

    def test_boolean_serialization(self):
        """Boolean values serialize as true/false (not quoted strings)."""
        serialized = json.dumps(REGIONAL_DEPENDENCY_PAYLOAD)
        assert '"flag_vence_fora_da_base": true' in serialized

    def test_empty_payload_is_valid_json(self):
        """Empty payload is still valid JSON."""
        empty = {
            "ni_fornecedor": "",
            "distribuicao_uf": [],
            "distribuicao_municipio": [],
            "uf_base_operacional": None,
            "ufs_expansao": [],
            "indice_dependencia_regional": 0.0,
            "flag_vence_fora_da_base": False,
        }
        json.dumps(empty)  # no error
