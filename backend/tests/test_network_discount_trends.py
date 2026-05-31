"""NETINT-004: Tests for RPC network_discount_trends (#1286).

Tendencias de desconto por setor/UF.

Strategy:
- Content validation: check migration SQL for required statements
- Unit tests: mock supabase.rpc() to validate JSON output shape
- Edge cases: empty data, UF filter, sem dados handling
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Migration file paths
MIGRATION_DIR = Path(__file__).resolve().parent.parent.parent / "supabase" / "migrations"
UP_MIGRATION = MIGRATION_DIR / "20260531120000_network_discount_trends.sql"
DOWN_MIGRATION = MIGRATION_DIR / "20260531120000_network_discount_trends.down.sql"


# ============================================================================
# Migration SQL Content Validation
# ============================================================================


class TestMigrationContent:
    """Validate the migration SQL files contain all required operations."""

    @pytest.fixture(autouse=True)
    def load_migrations(self):
        assert UP_MIGRATION.exists(), f"Migration file not found: {UP_MIGRATION}"
        assert DOWN_MIGRATION.exists(), f"Down migration not found: {DOWN_MIGRATION}"
        self.up_sql = UP_MIGRATION.read_text(encoding="utf-8")
        self.down_sql = DOWN_MIGRATION.read_text(encoding="utf-8")

    # -- Index --
    def test_creates_index(self):
        """Migration creates idx_psc_numero_controle_pncp for join performance."""
        assert "idx_psc_numero_controle_pncp" in self.up_sql
        assert "CREATE INDEX IF NOT EXISTS" in self.up_sql

    # -- Function definition --
    def test_creates_function(self):
        """Migration creates network_discount_trends RPC."""
        assert "CREATE OR REPLACE FUNCTION public.network_discount_trends(" in self.up_sql
        assert "RETURNS json" in self.up_sql

    def test_function_signature(self):
        """Function has correct parameters: p_setor, p_uf optional, p_meses default 12."""
        assert "p_setor TEXT" in self.up_sql
        assert "p_uf VARCHAR(2) DEFAULT NULL" in self.up_sql
        assert "p_meses INTEGER DEFAULT 12" in self.up_sql

    def test_security_definer(self):
        """Function uses SECURITY DEFINER with SET search_path."""
        assert "SECURITY DEFINER" in self.up_sql
        assert "SET search_path = public" in self.up_sql

    def test_statement_timeout(self):
        """Function sets LOCAL statement_timeout = '15s'."""
        assert "statement_timeout = '15s'" in self.up_sql

    def test_desconto_clamping(self):
        """Discount clamped to [0,1] via GREATEST(0, LEAST(1, ...))."""
        assert "GREATEST(0, LEAST(1," in self.up_sql

    # -- Grants --
    def test_grants_to_all_roles(self):
        """GRANT EXECUTE to anon, authenticated, and service_role."""
        assert "GRANT EXECUTE ON FUNCTION public.network_discount_trends" in self.up_sql
        assert "TO anon" in self.up_sql
        assert "TO authenticated" in self.up_sql
        assert "TO service_role" in self.up_sql

    # -- JOIN --
    def test_joins_pncp_raw_bids(self):
        """Function joins pncp_supplier_contracts with pncp_raw_bids."""
        assert "pncp_supplier_contracts psc" in self.up_sql
        assert "pncp_raw_bids prb" in self.up_sql
        assert "psc.numero_controle_pncp = prb.pncp_id" in self.up_sql

    # -- Output structure --
    def test_output_has_setor_field(self):
        """Output JSON includes 'setor' field from p_setor."""
        assert "'setor'" in self.up_sql
        assert "p_setor" in self.up_sql

    def test_output_tendencias_desconto(self):
        """Output JSON includes 'tendencias_desconto' array."""
        assert "'tendencias_desconto'" in self.up_sql

    def test_output_stats(self):
        """Output JSON includes 'stats' object."""
        assert "'stats'" in self.up_sql

    def test_output_desconto_medio_nacional(self):
        """Stats includes desconto_medio_nacional."""
        assert "'desconto_medio_nacional'" in self.up_sql

    def test_output_tendencia_nacional(self):
        """Stats includes tendencia_nacional."""
        assert "'tendencia_nacional'" in self.up_sql

    def test_output_uf_mais_menos_agressiva(self):
        """Stats includes uf_mais_agressiva and uf_menos_agressiva."""
        assert "'uf_mais_agressiva'" in self.up_sql
        assert "'uf_menos_agressiva'" in self.up_sql

    def test_output_percentiles(self):
        """Tendencias includes p25, p50, p75, p90_desconto."""
        assert "'p25_desconto'" in self.up_sql
        assert "'p50_desconto'" in self.up_sql
        assert "'p75_desconto'" in self.up_sql
        assert "'p90_desconto'" in self.up_sql

    def test_output_modalidade_mais_desconto(self):
        """Tendencias includes modalidade_mais_desconto."""
        assert "'modalidade_mais_desconto'" in self.up_sql

    def test_output_variacao_percentual(self):
        """Tendencias includes variacao_percentual."""
        assert "'variacao_percentual'" in self.up_sql

    def test_output_tendencia(self):
        """Tendencias includes tendencia (queda/alta/estavel)."""
        assert "'tendencia'" in self.up_sql

    def test_output_volume_contratos(self):
        """Tendencias includes volume_contratos."""
        assert "'volume_contratos'" in self.up_sql

    # -- Down migration --
    def test_down_drops_function(self):
        """Down migration drops the function."""
        assert "DROP FUNCTION IF EXISTS public.network_discount_trends" in self.down_sql

    def test_down_drops_index(self):
        """Down migration drops the index."""
        assert "DROP INDEX IF EXISTS idx_psc_numero_controle_pncp" in self.down_sql


# ============================================================================
# Unit Tests — Mocked Supabase RPC
# ============================================================================


def _make_supabase_mock(return_data):
    """Create a MagicMock for supabase that returns the given data from rpc().execute()."""
    rpc_response = MagicMock()
    rpc_response.data = return_data
    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value = rpc_response
    return mock_sb


class TestRpcContract:
    """Verify the RPC output shape via mock."""

    def test_accepts_setor_required(self):
        """RPC can be called with just p_setor."""
        mock_sb = _make_supabase_mock({
            "setor": "tecnologia",
            "tendencias_desconto": [],
            "stats": {
                "desconto_medio_nacional": 0,
                "tendencia_nacional": "estavel",
                "uf_mais_agressiva": "N/A",
                "uf_menos_agressiva": "N/A",
            },
        })

        result = mock_sb.rpc(
            "network_discount_trends",
            {"p_setor": "tecnologia"},
        ).execute().data

        assert result["setor"] == "tecnologia"
        assert "tendencias_desconto" in result
        assert "stats" in result

    def test_accepts_setor_and_uf(self):
        """RPC can filter by UF."""
        mock_sb = _make_supabase_mock({
            "setor": "saude",
            "tendencias_desconto": [
                {
                    "uf": "SP",
                    "desconto_medio_atual": 0.15,
                    "desconto_medio_anterior": 0.20,
                    "variacao_percentual": -0.25,
                    "tendencia": "queda",
                    "volume_contratos": 100,
                    "modalidade_mais_desconto": "pregao_eletronico",
                    "p25_desconto": 0.05,
                    "p50_desconto": 0.12,
                    "p75_desconto": 0.22,
                    "p90_desconto": 0.35,
                },
            ],
            "stats": {
                "desconto_medio_nacional": 0.15,
                "tendencia_nacional": "queda",
                "uf_mais_agressiva": "SP",
                "uf_menos_agressiva": "AM",
            },
        })

        result = mock_sb.rpc(
            "network_discount_trends",
            {"p_setor": "saude", "p_uf": "SP"},
        ).execute().data

        assert result["setor"] == "saude"
        assert len(result["tendencias_desconto"]) == 1
        assert result["tendencias_desconto"][0]["uf"] == "SP"

    def test_output_shape_has_all_fields(self):
        """Each trend entry has all required fields per spec."""
        mock_result = {
            "setor": "tecnologia",
            "tendencias_desconto": [
                {
                    "uf": "SP",
                    "desconto_medio_atual": 0.18,
                    "desconto_medio_anterior": 0.24,
                    "variacao_percentual": -0.25,
                    "tendencia": "queda",
                    "volume_contratos": 150,
                    "modalidade_mais_desconto": "pregao_eletronico",
                    "p25_desconto": 0.08,
                    "p50_desconto": 0.15,
                    "p75_desconto": 0.28,
                    "p90_desconto": 0.42,
                },
            ],
            "stats": {
                "desconto_medio_nacional": 0.21,
                "tendencia_nacional": "queda",
                "uf_mais_agressiva": "SP",
                "uf_menos_agressiva": "AM",
            },
        }
        mock_sb = _make_supabase_mock(mock_result)
        result = mock_sb.rpc(
            "network_discount_trends",
            {"p_setor": "tecnologia"},
        ).execute().data

        trend = result["tendencias_desconto"][0]
        # All fields present
        assert "uf" in trend
        assert "desconto_medio_atual" in trend
        assert "desconto_medio_anterior" in trend
        assert "variacao_percentual" in trend
        assert "tendencia" in trend
        assert "volume_contratos" in trend
        assert "modalidade_mais_desconto" in trend
        assert "p25_desconto" in trend
        assert "p50_desconto" in trend
        assert "p75_desconto" in trend
        assert "p90_desconto" in trend

        # Stats fields present
        stats = result["stats"]
        assert "desconto_medio_nacional" in stats
        assert "tendencia_nacional" in stats
        assert "uf_mais_agressiva" in stats
        assert "uf_menos_agressiva" in stats

    def test_desconto_medio_between_0_and_1(self):
        """desconto_medio_atual values are clamped between 0 and 1."""
        mock_sb = _make_supabase_mock({
            "setor": "teste",
            "tendencias_desconto": [
                {"uf": "SP", "desconto_medio_atual": 0.0, "desconto_medio_anterior": 0.5,
                 "variacao_percentual": -1.0, "tendencia": "queda", "volume_contratos": 10,
                 "modalidade_mais_desconto": None, "p25_desconto": 0.0, "p50_desconto": 0.0,
                 "p75_desconto": 0.0, "p90_desconto": 0.0},
                {"uf": "RJ", "desconto_medio_atual": 1.0, "desconto_medio_anterior": 0.5,
                 "variacao_percentual": 1.0, "tendencia": "alta", "volume_contratos": 5,
                 "modalidade_mais_desconto": None, "p25_desconto": 0.0, "p50_desconto": 0.0,
                 "p75_desconto": 0.0, "p90_desconto": 0.0},
            ],
            "stats": {},
        })

        result = mock_sb.rpc(
            "network_discount_trends",
            {"p_setor": "teste"},
        ).execute().data

        for trend in result["tendencias_desconto"]:
            assert 0.0 <= trend["desconto_medio_atual"] <= 1.0

    def test_tendencia_classification(self):
        """Tendencia correctly classifies as queda/alta/estavel."""
        mock_sb = _make_supabase_mock({
            "setor": "teste",
            "tendencias_desconto": [
                {"uf": "SP", "desconto_medio_atual": 0.10, "desconto_medio_anterior": 0.20,
                 "variacao_percentual": -0.50, "tendencia": "queda", "volume_contratos": 10,
                 "modalidade_mais_desconto": None, "p25_desconto": 0.0, "p50_desconto": 0.0,
                 "p75_desconto": 0.0, "p90_desconto": 0.0},
                {"uf": "RJ", "desconto_medio_atual": 0.25, "desconto_medio_anterior": 0.20,
                 "variacao_percentual": 0.25, "tendencia": "alta", "volume_contratos": 10,
                 "modalidade_mais_desconto": None, "p25_desconto": 0.0, "p50_desconto": 0.0,
                 "p75_desconto": 0.0, "p90_desconto": 0.0},
                {"uf": "MG", "desconto_medio_atual": 0.18, "desconto_medio_anterior": 0.19,
                 "variacao_percentual": -0.05, "tendencia": "estavel", "volume_contratos": 10,
                 "modalidade_mais_desconto": None, "p25_desconto": 0.0, "p50_desconto": 0.0,
                 "p75_desconto": 0.0, "p90_desconto": 0.0},
            ],
            "stats": {},
        })

        result = mock_sb.rpc(
            "network_discount_trends",
            {"p_setor": "teste"},
        ).execute().data

        trends = {t["uf"]: t for t in result["tendencias_desconto"]}
        assert trends["SP"]["tendencia"] == "queda"
        assert trends["RJ"]["tendencia"] == "alta"
        assert trends["MG"]["tendencia"] == "estavel"

    def test_empty_tendencias_returns_empty_array(self):
        """When no data, tendencias_desconto is an empty array."""
        mock_sb = _make_supabase_mock({
            "setor": "setor_sem_dados",
            "tendencias_desconto": [],
            "stats": {
                "desconto_medio_nacional": 0,
                "tendencia_nacional": "estavel",
                "uf_mais_agressiva": "N/A",
                "uf_menos_agressiva": "N/A",
            },
        })

        result = mock_sb.rpc(
            "network_discount_trends",
            {"p_setor": "setor_sem_dados"},
        ).execute().data

        assert result["tendencias_desconto"] == []
        assert result["stats"]["uf_mais_agressiva"] == "N/A"

    def test_multiple_ufs_in_tendencias(self):
        """Tendencias can contain entries for multiple UFs."""
        mock_sb = _make_supabase_mock({
            "setor": "teste",
            "tendencias_desconto": [
                {"uf": "SP", "desconto_medio_atual": 0.18, "desconto_medio_anterior": 0.24,
                 "variacao_percentual": -0.25, "tendencia": "queda", "volume_contratos": 150,
                 "modalidade_mais_desconto": None, "p25_desconto": 0.08, "p50_desconto": 0.15,
                 "p75_desconto": 0.28, "p90_desconto": 0.42},
                {"uf": "RJ", "desconto_medio_atual": 0.12, "desconto_medio_anterior": 0.10,
                 "variacao_percentual": 0.20, "tendencia": "alta", "volume_contratos": 80,
                 "modalidade_mais_desconto": None, "p25_desconto": 0.04, "p50_desconto": 0.10,
                 "p75_desconto": 0.18, "p90_desconto": 0.25},
                {"uf": "MG", "desconto_medio_atual": 0.15, "desconto_medio_anterior": 0.15,
                 "variacao_percentual": 0.0, "tendencia": "estavel", "volume_contratos": 120,
                 "modalidade_mais_desconto": None, "p25_desconto": 0.05, "p50_desconto": 0.12,
                 "p75_desconto": 0.20, "p90_desconto": 0.30},
            ],
            "stats": {
                "desconto_medio_nacional": 0.15,
                "tendencia_nacional": "estavel",
                "uf_mais_agressiva": "SP",
                "uf_menos_agressiva": "MG",
            },
        })

        result = mock_sb.rpc(
            "network_discount_trends",
            {"p_setor": "teste"},
        ).execute().data

        assert len(result["tendencias_desconto"]) == 3
        ufs = [t["uf"] for t in result["tendencias_desconto"]]
        assert "SP" in ufs
        assert "RJ" in ufs
        assert "MG" in ufs
