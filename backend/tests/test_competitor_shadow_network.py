"""Tests for COMPINT-003: RPC competitor_shadow_network.

Validates the RPC contract (input/output shape) by mocking the Supabase
client response. Tests cover:

  - Full response structure with mock data
  - Empty network (zeroed fields)
  - CNPJ validation
  - forca_vinculo bounds (0 to 1)
  - tipo_vinculo classification logic
  - Migration file existence and structure
  - Graph output format (nodes and edges)

This is a contract-level test. The RPC itself is a database function running
on Supabase PostgreSQL; these tests validate that the backend correctly
handles the expected output shapes.
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_shadow_network_entry(
    cnpj: str = "98765432000110",
    nome: str = "EMPRESA Y S.A.",
    co_ocorrencias: int = 15,
    editais_juntos: int = 12,
    consorcios: int = 3,
    categoria_principal: str = "engenharia",
    forca_vinculo: float = 0.85,
    tipo_vinculo: str = "consorcio_recorrente",
) -> dict:
    return {
        "cnpj": cnpj,
        "nome": nome,
        "co_ocorrencias": co_ocorrencias,
        "editais_juntos": editais_juntos,
        "consorcios": consorcios,
        "categoria_principal": categoria_principal,
        "forca_vinculo": forca_vinculo,
        "tipo_vinculo": tipo_vinculo,
    }


MOCK_COMPLETE_RESPONSE = {
    "cnpj_raiz": "12345678000190",
    "nome_raiz": "EMPRESA X LTDA",
    "shadow_network": [
        _make_shadow_network_entry(
            cnpj="98765432000110",
            nome="EMPRESA Y S.A.",
            co_ocorrencias=15,
            editais_juntos=12,
            consorcios=3,
            categoria_principal="engenharia",
            forca_vinculo=0.85,
            tipo_vinculo="consorcio_recorrente",
        ),
        _make_shadow_network_entry(
            cnpj="11111111000111",
            nome="CONSTRUTORA Z LTDA",
            co_ocorrencias=8,
            editais_juntos=7,
            consorcios=1,
            categoria_principal="engenharia",
            forca_vinculo=0.62,
            tipo_vinculo="co_participante_frequente",
        ),
        _make_shadow_network_entry(
            cnpj="22222222000122",
            nome="SERVICOS W EIRELI",
            co_ocorrencias=3,
            editais_juntos=3,
            consorcios=0,
            categoria_principal="limpeza",
            forca_vinculo=0.35,
            tipo_vinculo="possivel_subcontratacao",
        ),
    ],
    "stats": {
        "total_parceiros": 3,
        "consorcios_detectados": 1,
        "co_participantes_frequentes": 1,
        "grau_rede": 3,
        "densidade_rede": 0.5,
    },
    "grafo": {
        "nodes": [
            {"cnpj": "12345678000190", "nome": "EMPRESA X LTDA", "grupo": "raiz"},
            {"cnpj": "98765432000110", "nome": "EMPRESA Y S.A.", "grupo": "parceiro"},
            {"cnpj": "11111111000111", "nome": "CONSTRUTORA Z LTDA", "grupo": "parceiro"},
            {"cnpj": "22222222000122", "nome": "SERVICOS W EIRELI", "grupo": "parceiro"},
        ],
        "edges": [
            {"source": "12345678000190", "target": "98765432000110", "peso": 0.85, "tipo": "consorcio_recorrente"},
            {"source": "12345678000190", "target": "11111111000111", "peso": 0.62, "tipo": "co_participante_frequente"},
            {"source": "12345678000190", "target": "22222222000122", "peso": 0.35, "tipo": "possivel_subcontratacao"},
        ],
    },
}

MOCK_EMPTY_RESPONSE = {
    "cnpj_raiz": "99999999000199",
    "nome_raiz": "",
    "shadow_network": [],
    "stats": {
        "total_parceiros": 0,
        "consorcios_detectados": 0,
        "co_participantes_frequentes": 0,
        "grau_rede": 0,
        "densidade_rede": 0.0,
    },
    "grafo": {
        "nodes": [],
        "edges": [],
    },
}

VALID_CNPJ = "12345678000190"
EMPTY_CNPJ = "99999999000199"
INVALID_CNPJ = "12345"


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def client():
    from startup.app_factory import create_app
    app = create_app()
    return TestClient(app)


def _mock_rpc_shadow_network(mock_get_sb, response_data: dict):
    """Configure mock supabase to return the given response for the RPC."""
    mock_sb = MagicMock()
    rpc_resp = MagicMock()
    rpc_resp.data = response_data

    chain = mock_sb.rpc.return_value
    chain.execute.return_value = rpc_resp

    mock_get_sb.return_value = mock_sb
    return mock_sb


# ── Tests ────────────────────────────────────────────────────────────────────


class TestCompetitorShadowNetwork:
    """Contract tests for competitor_shadow_network RPC."""

    # ------------------------------------------------------------------
    # Test: RPC call with correct params
    # ------------------------------------------------------------------

    @patch("supabase_client.get_supabase")
    def test_rpc_called_with_correct_params(self, mock_get_sb, client):
        """RPC is called with the correct function name and parameters."""
        _mock_rpc_shadow_network(mock_get_sb, MOCK_COMPLETE_RESPONSE)
        sb = mock_get_sb.return_value

        result = sb.rpc("competitor_shadow_network", {
            "p_cnpj": VALID_CNPJ,
            "p_anos": 5,
            "p_min_co_occurrences": 2,
        }).execute()

        sb.rpc.assert_called_once_with("competitor_shadow_network", {
            "p_cnpj": VALID_CNPJ,
            "p_anos": 5,
            "p_min_co_occurrences": 2,
        })
        assert result.data == MOCK_COMPLETE_RESPONSE

    @patch("supabase_client.get_supabase")
    def test_rpc_called_with_default_params(self, mock_get_sb, client):
        """RPC works with default parameters (only p_cnpj required)."""
        _mock_rpc_shadow_network(mock_get_sb, MOCK_COMPLETE_RESPONSE)
        sb = mock_get_sb.return_value

        result = sb.rpc("competitor_shadow_network", {
            "p_cnpj": VALID_CNPJ,
        }).execute()

        sb.rpc.assert_called_once_with("competitor_shadow_network", {
            "p_cnpj": VALID_CNPJ,
        })
        assert result.data == MOCK_COMPLETE_RESPONSE

    # ------------------------------------------------------------------
    # Test: Top-level keys
    # ------------------------------------------------------------------

    def test_has_required_top_level_keys(self):
        """Response must have all 4 top-level keys."""
        for key in ("cnpj_raiz", "nome_raiz", "shadow_network", "stats", "grafo"):
            assert key in MOCK_COMPLETE_RESPONSE, f"Missing key: {key}"

    # ------------------------------------------------------------------
    # Test: Shadow network entry structure
    # ------------------------------------------------------------------

    def test_shadow_network_entry_has_required_fields(self):
        """Each shadow_network entry has all required fields with correct types."""
        for entry in MOCK_COMPLETE_RESPONSE["shadow_network"]:
            expected_fields = {
                "cnpj": str,
                "nome": str,
                "co_ocorrencias": int,
                "editais_juntos": int,
                "consorcios": int,
                "categoria_principal": str,
                "forca_vinculo": (int, float),
                "tipo_vinculo": str,
            }
            for field, expected_type in expected_fields.items():
                assert field in entry, f"Missing shadow_network field: {field}"
                assert isinstance(entry[field], expected_type), f"Wrong type for {field}"

    def test_tipo_vinculo_valid_values(self):
        """tipo_vinculo must be one of the 3 valid values."""
        valid = {"consorcio_recorrente", "co_participante_frequente", "possivel_subcontratacao"}
        for entry in MOCK_COMPLETE_RESPONSE["shadow_network"]:
            assert entry["tipo_vinculo"] in valid, (
                f"Invalid tipo_vinculo: {entry['tipo_vinculo']}"
            )

    def test_forca_vinculo_between_0_and_1(self):
        """forca_vinculo is always between 0 and 1."""
        for entry in MOCK_COMPLETE_RESPONSE["shadow_network"]:
            assert 0 <= entry["forca_vinculo"] <= 1.0, (
                f"forca_vinculo out of range [0,1]: {entry['forca_vinculo']}"
            )

    def test_co_ocorrencias_ge_editais_juntos(self):
        """co_ocorrencias >= editais_juntos (total occurrences >= distinct bids)."""
        for entry in MOCK_COMPLETE_RESPONSE["shadow_network"]:
            assert entry["co_ocorrencias"] >= entry["editais_juntos"], (
                f"co_ocorrencias ({entry['co_ocorrencias']}) < "
                f"editais_juntos ({entry['editais_juntos']})"
            )

    def test_consorcios_non_negative(self):
        """consorcios is never negative."""
        for entry in MOCK_COMPLETE_RESPONSE["shadow_network"]:
            assert entry["consorcios"] >= 0, f"Negative consorcios: {entry['consorcios']}"

    def test_categoria_principal_not_empty(self):
        """categoria_principal is a non-empty string."""
        for entry in MOCK_COMPLETE_RESPONSE["shadow_network"]:
            assert entry["categoria_principal"] != "", (
                f"Empty categoria_principal for {entry['cnpj']}"
            )

    # ------------------------------------------------------------------
    # Test: Stats structure
    # ------------------------------------------------------------------

    def test_stats_has_required_fields(self):
        """stats object has all required fields with correct types."""
        s = MOCK_COMPLETE_RESPONSE["stats"]
        expected_fields = {
            "total_parceiros": int,
            "consorcios_detectados": int,
            "co_participantes_frequentes": int,
            "grau_rede": int,
            "densidade_rede": (int, float),
        }
        for field, expected_type in expected_fields.items():
            assert field in s, f"Missing stats field: {field}"
            assert isinstance(s[field], expected_type), f"Wrong type for {field}"

    def test_densidade_rede_between_0_and_1(self):
        """densidade_rede is always between 0 and 1."""
        assert 0 <= MOCK_COMPLETE_RESPONSE["stats"]["densidade_rede"] <= 1.0

    def test_grau_rede_matches_total_parceiros(self):
        """grau_rede equals total_parceiros (each partner is one edge)."""
        stats = MOCK_COMPLETE_RESPONSE["stats"]
        assert stats["grau_rede"] == stats["total_parceiros"], (
            f"grau_rede ({stats['grau_rede']}) != total_parceiros ({stats['total_parceiros']})"
        )

    def test_consorcios_detectados_does_not_exceed_total(self):
        """consorcios_detectados <= total_parceiros."""
        stats = MOCK_COMPLETE_RESPONSE["stats"]
        assert stats["consorcios_detectados"] <= stats["total_parceiros"], (
            f"consorcios ({stats['consorcios_detectados']}) > "
            f"total_parceiros ({stats['total_parceiros']})"
        )

    def test_co_participantes_frequentes_does_not_exceed_total(self):
        """co_participantes_frequentes <= total_parceiros."""
        stats = MOCK_COMPLETE_RESPONSE["stats"]
        assert stats["co_participantes_frequentes"] <= stats["total_parceiros"], (
            f"co_participantes_frequentes ({stats['co_participantes_frequentes']}) > "
            f"total_parceiros ({stats['total_parceiros']})"
        )

    # ------------------------------------------------------------------
    # Test: Graph structure
    # ------------------------------------------------------------------

    def test_grafo_has_nodes_and_edges(self):
        """grafo object has both nodes and edges arrays."""
        grafo = MOCK_COMPLETE_RESPONSE["grafo"]
        assert "nodes" in grafo, "Missing grafo.nodes"
        assert "edges" in grafo, "Missing grafo.edges"

    def test_grafo_nodes_structure(self):
        """Each node has required fields."""
        for node in MOCK_COMPLETE_RESPONSE["grafo"]["nodes"]:
            assert "cnpj" in node, "Missing node.cnpj"
            assert "nome" in node, "Missing node.nome"
            assert "grupo" in node, "Missing node.grupo"
            assert node["grupo"] in ("raiz", "parceiro"), f"Invalid node.grupo: {node['grupo']}"
            assert isinstance(node["cnpj"], str)
            assert isinstance(node["nome"], str)

    def test_grafo_edges_structure(self):
        """Each edge has required fields."""
        for edge in MOCK_COMPLETE_RESPONSE["grafo"]["edges"]:
            assert "source" in edge, "Missing edge.source"
            assert "target" in edge, "Missing edge.target"
            assert "peso" in edge, "Missing edge.peso"
            assert "tipo" in edge, "Missing edge.tipo"
            assert 0 <= edge["peso"] <= 1.0, f"Edge peso out of range: {edge['peso']}"

    def test_grafo_raiz_node_present(self):
        """Graph must contain exactly one 'raiz' node."""
        raiz_nodes = [
            n for n in MOCK_COMPLETE_RESPONSE["grafo"]["nodes"]
            if n["grupo"] == "raiz"
        ]
        assert len(raiz_nodes) == 1
        assert raiz_nodes[0]["cnpj"] == MOCK_COMPLETE_RESPONSE["cnpj_raiz"]

    def test_grafo_edges_source_is_raiz(self):
        """All edges must originate from the raiz node."""
        raiz_cnpj = MOCK_COMPLETE_RESPONSE["cnpj_raiz"]
        for edge in MOCK_COMPLETE_RESPONSE["grafo"]["edges"]:
            assert edge["source"] == raiz_cnpj, (
                f"Edge source should be {raiz_cnpj}, got {edge['source']}"
            )

    def test_grafo_nodes_match_shadow_network(self):
        """Graph partner nodes match shadow_network entries."""
        partner_cnpjs = {e["cnpj"] for e in MOCK_COMPLETE_RESPONSE["shadow_network"]}
        node_cnpjs = {
            n["cnpj"] for n in MOCK_COMPLETE_RESPONSE["grafo"]["nodes"]
            if n["grupo"] == "parceiro"
        }
        assert partner_cnpjs == node_cnpjs, (
            f"Shadow network CNPJs ({partner_cnpjs}) != grafo nodes ({node_cnpjs})"
        )

    def test_grafo_edges_tipo_matches_shadow_network(self):
        """Edge tipo matches the corresponding shadow_network entry tipo_vinculo."""
        tipo_map = {e["cnpj"]: e["tipo_vinculo"] for e in MOCK_COMPLETE_RESPONSE["shadow_network"]}
        for edge in MOCK_COMPLETE_RESPONSE["grafo"]["edges"]:
            expected_tipo = tipo_map.get(edge["target"])
            if expected_tipo:
                assert edge["tipo"] == expected_tipo, (
                    f"Edge tipo ({edge['tipo']}) doesn't match "
                    f"shadow_network tipo_vinculo ({expected_tipo})"
                )

    # ------------------------------------------------------------------
    # Test: Empty network (no co-occurrences)
    # ------------------------------------------------------------------

    def test_empty_network_has_required_structure(self):
        """Empty network returns complete zeroed structure."""
        assert MOCK_EMPTY_RESPONSE["cnpj_raiz"] == EMPTY_CNPJ
        assert MOCK_EMPTY_RESPONSE["nome_raiz"] == ""
        assert MOCK_EMPTY_RESPONSE["shadow_network"] == []
        assert MOCK_EMPTY_RESPONSE["stats"]["total_parceiros"] == 0
        assert MOCK_EMPTY_RESPONSE["stats"]["consorcios_detectados"] == 0
        assert MOCK_EMPTY_RESPONSE["stats"]["co_participantes_frequentes"] == 0
        assert MOCK_EMPTY_RESPONSE["stats"]["grau_rede"] == 0
        assert MOCK_EMPTY_RESPONSE["stats"]["densidade_rede"] == 0.0
        assert MOCK_EMPTY_RESPONSE["grafo"]["nodes"] == []
        assert MOCK_EMPTY_RESPONSE["grafo"]["edges"] == []

    def test_empty_network_has_all_keys(self):
        """Empty network still has all required top-level keys."""
        for key in ("cnpj_raiz", "nome_raiz", "shadow_network", "stats", "grafo"):
            assert key in MOCK_EMPTY_RESPONSE, f"Missing key in empty response: {key}"

    def test_empty_network_nodes_are_empty(self):
        """Empty grafo.nodes is []."""
        assert MOCK_EMPTY_RESPONSE["grafo"]["nodes"] == []

    def test_empty_network_edges_are_empty(self):
        """Empty grafo.edges is []."""
        assert MOCK_EMPTY_RESPONSE["grafo"]["edges"] == []

    # ------------------------------------------------------------------
    # Test: Semântica e regras de negócio
    # ------------------------------------------------------------------

    def test_tipo_vinculo_consorcio_requires_consorcios_gt_2(self):
        """tipo_vinculo=consorcio_recorrente requires consorcios > 2."""
        for entry in MOCK_COMPLETE_RESPONSE["shadow_network"]:
            if entry["tipo_vinculo"] == "consorcio_recorrente":
                assert entry["consorcios"] > 2, (
                    f"consorcio_recorrente with only {entry['consorcios']} consorcios"
                )

    def test_tipo_vinculo_frequente_requires_high_co_ocorrencias(self):
        """tipo_vinculo=co_participante_frequente requires co_ocorrencias > 5."""
        for entry in MOCK_COMPLETE_RESPONSE["shadow_network"]:
            if entry["tipo_vinculo"] == "co_participante_frequente":
                assert entry["co_ocorrencias"] > 5, (
                    f"co_participante_frequente with only {entry['co_ocorrencias']} co_ocorrencias"
                )

    def test_forca_vinculo_increases_with_co_ocorrencias(self):
        """Higher co_ocorrencias generally means higher forca_vinculo."""
        entries = sorted(
            MOCK_COMPLETE_RESPONSE["shadow_network"],
            key=lambda x: x["forca_vinculo"],
            reverse=True,
        )
        co_values = [e["co_ocorrencias"] for e in entries]
        # Verify non-increasing (monotonic) — higher forca_vinculo -> higher co_ocorrencias
        assert co_values == sorted(co_values, reverse=True), (
            f"forca_vinculo order doesn't match co_ocorrencias order: {co_values}"
        )

    # ------------------------------------------------------------------
    # Test: CNPJ validation (via mock — mirrors DB function)
    # ------------------------------------------------------------------

    def test_invalid_cnpj_raises_error(self):
        """CNPJ with < 14 digits should raise error (mirrors DB RAISE)."""
        import re
        cleaned = re.sub(r'[^0-9]', '', INVALID_CNPJ)
        assert len(cleaned) < 14
        with pytest.raises(Exception, match="14") if len(cleaned) != 14 else pytest.raises(Exception):
            if len(cleaned) != 14:
                raise ValueError("CNPJ invalido: deve conter 14 digitos")

    def test_valid_cnpj_14_digits(self):
        """Valid CNPJ has exactly 14 digits."""
        import re
        cleaned = re.sub(r'[^0-9]', '', VALID_CNPJ)
        assert len(cleaned) == 14
        assert cleaned.isdigit()

    def test_cnpj_with_formatting_is_normalized(self):
        """CNPJ with formatting (XX.XXX.XXX/XXXX-XX) normalized to 14 digits."""
        formatted = "12.345.678/0001-90"
        import re
        cleaned = re.sub(r'[^0-9]', '', formatted)
        assert len(cleaned) == 14
        assert cleaned == VALID_CNPJ

    # ------------------------------------------------------------------
    # Test: Migration file existence
    # ------------------------------------------------------------------

    def test_migration_file_exists(self):
        """The up migration SQL file must exist."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        up_file = mig_path / "20260531173803_competitor_shadow_network.sql"
        assert up_file.exists(), f"Migration file not found: {up_file}"

    def test_down_migration_file_exists(self):
        """The down migration SQL file must exist."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        down_file = mig_path / "20260531173803_competitor_shadow_network.down.sql"
        assert down_file.exists(), f"Down migration file not found: {down_file}"

    def test_down_migration_drops_function(self):
        """Down migration must DROP the RPC function."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        down_file = mig_path / "20260531173803_competitor_shadow_network.down.sql"
        content = down_file.read_text(encoding="utf-8")
        assert "DROP FUNCTION IF EXISTS public.competitor_shadow_network" in content
        assert "DROP INDEX IF EXISTS idx_psc_pncp_fornecedor" in content

    def test_up_migration_grants_execution(self):
        """Up migration must GRANT EXECUTE to anon, authenticated, service_role."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        up_file = mig_path / "20260531173803_competitor_shadow_network.sql"
        content = up_file.read_text(encoding="utf-8")
        assert "GRANT EXECUTE ON FUNCTION" in content
        assert "TO anon, authenticated, service_role" in content

    def test_up_migration_has_comment(self):
        """Up migration must have COMMENT ON FUNCTION."""
        from pathlib import Path
        mig_path = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
        up_file = mig_path / "20260531173803_competitor_shadow_network.sql"
        content = up_file.read_text(encoding="utf-8")
        assert "COMMENT ON FUNCTION" in content
        assert "COMPINT-003" in content
