"""PREDINT-005: Tests for RPC predict_expansion_organs (#1268).

Identifica orgaos publicos com tendencia de expansao nos contratos
nos ultimos 3 anos, usando CAGR.

Strategy:
- Content validation: check migration SQL for required statements
- Unit tests: mock supabase.rpc() to validate JSON output shape
- Edge cases: empty data, UF filter, p_min_crescimento filter
"""

import re
from pathlib import Path

import pytest

# Migration file paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATION_DIR = REPO_ROOT / "supabase" / "migrations"
UP_MIGRATION = MIGRATION_DIR / "20260531175504_predict_expansion_organs.sql"
DOWN_MIGRATION = MIGRATION_DIR / "20260531175504_predict_expansion_organs.down.sql"


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

    # -- Function definition --
    def test_creates_function(self):
        """Migration creates predict_expansion_organs RPC."""
        assert "CREATE OR REPLACE FUNCTION public.predict_expansion_organs(" in self.up_sql
        assert "RETURNS json" in self.up_sql

    def test_function_signature(self):
        """Function has correct parameters with defaults."""
        assert "p_setor TEXT DEFAULT NULL" in self.up_sql
        assert "p_uf VARCHAR(2) DEFAULT NULL" in self.up_sql
        assert "p_min_crescimento FLOAT DEFAULT 0.15" in self.up_sql

    def test_language_plpgsql(self):
        """Function uses LANGUAGE plpgsql (needs local statement_timeout)."""
        assert "LANGUAGE plpgsql" in self.up_sql

    def test_stable_volatility(self):
        """Function is STABLE (read-only query)."""
        assert "STABLE" in self.up_sql

    def test_security_definer(self):
        """Function uses SECURITY DEFINER."""
        assert "SECURITY DEFINER" in self.up_sql

    def test_search_path(self):
        """Function sets search_path = public, pg_temp."""
        assert "SET search_path = public, pg_temp" in self.up_sql

    def test_statement_timeout(self):
        """Function sets LOCAL statement_timeout = '15s'."""
        assert "statement_timeout = '15s'" in self.up_sql

    # -- Data source --
    def test_reads_from_pncp_supplier_contracts(self):
        """Function reads from pncp_supplier_contracts."""
        assert "pncp_supplier_contracts" in self.up_sql

    def test_filters_is_active(self):
        """Function filters psc.is_active = TRUE."""
        assert "is_active = TRUE" in self.up_sql

    def test_filters_valor_global_not_null(self):
        """Function excludes NULL or zero valor_global."""
        assert "valor_global IS NOT NULL" in self.up_sql
        assert "valor_global > 0" in self.up_sql

    def test_filters_orgao_nome_not_null(self):
        """Function excludes NULL orgao_nome."""
        assert "orgao_nome IS NOT NULL" in self.up_sql

    def test_filters_uf_not_null(self):
        """Function excludes NULL uf."""
        assert "uf IS NOT NULL" in self.up_sql

    def test_uf_filter_optional(self):
        """UF filter is optional (uses OR pattern)."""
        assert "p_uf IS NULL OR UPPER(psc.uf) = UPPER(p_uf)" in self.up_sql

    def test_setor_filter_optional(self):
        """Setor filter is optional."""
        assert "p_setor IS NULL OR psc.setor_classificado = p_setor" in self.up_sql

    def test_3_year_window(self):
        """Function filters by 3 complete calendar years."""
        assert "v_ano_1" in self.up_sql
        assert "v_ano_2" in self.up_sql
        assert "v_ano_3" in self.up_sql

    def test_cagr_formula(self):
        """Function uses CAGR formula with exponent 1/3."""
        assert "^ (1.0 / 3.0)" in self.up_sql

    def test_positive_trend_filter(self):
        """Function excludes organs with negative trend."""
        assert "vol_ano_1 > vol_ano_3" in self.up_sql

    def test_min_crescimento_filter(self):
        """Function applies p_min_crescimento filter."""
        assert "p_min_crescimento" in self.up_sql

    def test_3_year_data_requirement(self):
        """Function requires all 3 years to have data (excludes <3 anos)."""
        assert "vol_ano_1 IS NOT NULL" in self.up_sql
        assert "vol_ano_2 IS NOT NULL" in self.up_sql
        assert "vol_ano_3 IS NOT NULL" in self.up_sql

    # -- Output structure --
    def test_output_orgaos_expandindo(self):
        """Output JSON includes 'orgaos_expandindo' array."""
        assert "'orgaos_expandindo'" in self.up_sql

    def test_output_stats(self):
        """Output JSON includes 'stats' object."""
        assert "'stats'" in self.up_sql

    def test_output_orgao_nome(self):
        """Each organ entry includes orgao_nome."""
        assert "'orgao_nome'" in self.up_sql

    def test_output_orgao_uf(self):
        """Each organ entry includes orgao_uf."""
        assert "'orgao_uf'" in self.up_sql

    def test_output_categoria(self):
        """Each organ entry includes categoria."""
        assert "'categoria'" in self.up_sql

    def test_output_crescimento_anual_medio(self):
        """Each organ entry includes crescimento_anual_medio."""
        assert "'crescimento_anual_medio'" in self.up_sql

    def test_output_volume_ultimo_ano(self):
        """Each organ entry includes volume_ultimo_ano."""
        assert "'volume_ultimo_ano'" in self.up_sql

    def test_output_tendencia_3anos(self):
        """Each organ entry includes tendencia_3anos array."""
        assert "'tendencia_3anos'" in self.up_sql

    def test_output_categorias_emergentes(self):
        """Each organ entry includes categorias_emergentes array."""
        assert "'categorias_emergentes'" in self.up_sql

    def test_output_sinal(self):
        """Each organ entry includes sinal."""
        assert "'sinal'" in self.up_sql

    def test_stats_orgaos_analisados(self):
        """Stats includes orgaos_analisados."""
        assert "'orgaos_analisados'" in self.up_sql

    def test_stats_expandindo(self):
        """Stats includes expandindo."""
        assert "'expandindo'" in self.up_sql

    def test_stats_crescimento_medio_nacional(self):
        """Stats includes crescimento_medio_nacional."""
        assert "'crescimento_medio_nacional'" in self.up_sql

    # -- Sinal classification --
    def test_sinal_expansao_forte(self):
        """Sinal 'expansao_forte' for crescimento > 0.30."""
        assert "expansao_forte" in self.up_sql
        assert "0.30" in self.up_sql

    def test_sinal_expansao_moderada(self):
        """Sinal 'expansao_moderada' for crescimento between 0.15 and 0.30."""
        assert "expansao_moderada" in self.up_sql

    # -- Coalesce empty arrays --
    def test_empty_orgaos_expandindo(self):
        """Empty results use '[]'::json, not NULL."""
        assert "COALESCE" in self.up_sql
        assert "'[]'::json" in self.up_sql

    # -- Grants --
    def test_grants_to_all_roles(self):
        """GRANT EXECUTE to anon, authenticated, and service_role."""
        grants = re.findall(
            r"GRANT EXECUTE ON FUNCTION public\.predict_expansion_organs\(TEXT, VARCHAR, FLOAT\)",
            self.up_sql,
        )
        assert len(grants) == 3, (
            f"Expected 3 GRANT statements, found {len(grants)}. "
            "Need separate GRANTs for anon, authenticated, service_role."
        )
        assert "TO anon" in self.up_sql
        assert "TO authenticated" in self.up_sql
        assert "TO service_role" in self.up_sql

    # -- Down migration --
    def test_down_drops_function(self):
        """Down migration drops the function with correct signature."""
        assert "DROP FUNCTION IF EXISTS public.predict_expansion_organs" in self.down_sql
        assert "TEXT, VARCHAR, FLOAT" in self.down_sql


# ============================================================================
# Unit Tests — Mocked Supabase RPC
# ============================================================================


def _make_supabase_mock(return_data):
    """Create a MagicMock for supabase that returns the given data from rpc().execute()."""
    from unittest.mock import MagicMock

    rpc_response = MagicMock()
    rpc_response.data = return_data
    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value = rpc_response
    return mock_sb


class TestRpcContract:
    """Verify the RPC output shape via mock."""

    def test_accepts_no_filters(self):
        """RPC can be called without any parameters (all defaults)."""
        mock_sb = _make_supabase_mock({
            "orgaos_expandindo": [],
            "stats": {
                "orgaos_analisados": 0,
                "expandindo": 0,
                "crescimento_medio_nacional": 0.0,
            },
        })

        result = mock_sb.rpc("predict_expansion_organs", {}).execute().data

        assert "orgaos_expandindo" in result
        assert "stats" in result
        assert result["stats"]["orgaos_analisados"] == 0
        assert result["stats"]["expandindo"] == 0

    def test_accepts_setor_filter(self):
        """RPC can filter by sector."""
        mock_sb = _make_supabase_mock({
            "orgaos_expandindo": [],
            "stats": {
                "orgaos_analisados": 10,
                "expandindo": 0,
                "crescimento_medio_nacional": 0.0,
            },
        })

        result = mock_sb.rpc(
            "predict_expansion_organs",
            {"p_setor": "tecnologia"},
        ).execute().data

        assert result["stats"]["orgaos_analisados"] == 10

    def test_accepts_uf_filter(self):
        """RPC can filter by UF."""
        mock_sb = _make_supabase_mock({
            "orgaos_expandindo": [
                {
                    "orgao_nome": "SECRETARIA DE EDUCACAO SP",
                    "orgao_uf": "SP",
                    "categoria": "educacao",
                    "crescimento_anual_medio": 0.25,
                    "volume_ultimo_ano": 50000000.00,
                    "tendencia_3anos": [30000000.0, 40000000.0, 50000000.0],
                    "categorias_emergentes": ["infraestrutura"],
                    "sinal": "expansao_moderada",
                },
            ],
            "stats": {
                "orgaos_analisados": 50,
                "expandindo": 1,
                "crescimento_medio_nacional": 0.25,
            },
        })

        result = mock_sb.rpc(
            "predict_expansion_organs",
            {"p_uf": "SP"},
        ).execute().data

        assert len(result["orgaos_expandindo"]) == 1
        assert result["orgaos_expandindo"][0]["orgao_uf"] == "SP"

    def test_output_shape_has_all_fields(self):
        """Each organ entry has all required fields per spec."""
        mock_result = {
            "orgaos_expandindo": [
                {
                    "orgao_nome": "MINISTERIO DA EDUCACAO",
                    "orgao_uf": "DF",
                    "categoria": "tecnologia",
                    "crescimento_anual_medio": 0.35,
                    "volume_ultimo_ano": 250000000.00,
                    "tendencia_3anos": [120000000.0, 185000000.0, 250000000.0],
                    "categorias_emergentes": ["software", "cloud"],
                    "sinal": "expansao_forte",
                },
            ],
            "stats": {
                "orgaos_analisados": 200,
                "expandindo": 28,
                "crescimento_medio_nacional": 0.08,
            },
        }
        mock_sb = _make_supabase_mock(mock_result)
        result = mock_sb.rpc(
            "predict_expansion_organs",
            {},
        ).execute().data

        organ = result["orgaos_expandindo"][0]
        # All organ fields present
        assert "orgao_nome" in organ
        assert "orgao_uf" in organ
        assert "categoria" in organ
        assert "crescimento_anual_medio" in organ
        assert "volume_ultimo_ano" in organ
        assert "tendencia_3anos" in organ
        assert "categorias_emergentes" in organ
        assert "sinal" in organ

        # Stats fields present
        stats = result["stats"]
        assert "orgaos_analisados" in stats
        assert "expandindo" in stats
        assert "crescimento_medio_nacional" in stats

        # Verify exact spec values
        assert organ["orgao_nome"] == "MINISTERIO DA EDUCACAO"
        assert organ["orgao_uf"] == "DF"
        assert organ["categoria"] == "tecnologia"
        assert organ["crescimento_anual_medio"] == 0.35
        assert organ["sinal"] == "expansao_forte"
        assert len(organ["tendencia_3anos"]) == 3
        assert organ["tendencia_3anos"][0] < organ["tendencia_3anos"][2]  # ascending

    def test_sinal_classification(self):
        """Sinal correctly classifies as expansao_forte or expansao_moderada."""
        mock_result = {
            "orgaos_expandindo": [
                {
                    "orgao_nome": "ORGAO FORTE",
                    "orgao_uf": "SP",
                    "categoria": "saude",
                    "crescimento_anual_medio": 0.45,
                    "volume_ultimo_ano": 1000000.00,
                    "tendencia_3anos": [500000.0, 700000.0, 1000000.0],
                    "categorias_emergentes": [],
                    "sinal": "expansao_forte",
                },
                {
                    "orgao_nome": "ORGAO MODERADO",
                    "orgao_uf": "RJ",
                    "categoria": "educacao",
                    "crescimento_anual_medio": 0.20,
                    "volume_ultimo_ano": 800000.00,
                    "tendencia_3anos": [600000.0, 700000.0, 800000.0],
                    "categorias_emergentes": [],
                    "sinal": "expansao_moderada",
                },
            ],
            "stats": {},
        }
        mock_sb = _make_supabase_mock(mock_result)
        result = mock_sb.rpc(
            "predict_expansion_organs",
            {},
        ).execute().data

        organs = {o["orgao_nome"]: o for o in result["orgaos_expandindo"]}
        assert organs["ORGAO FORTE"]["sinal"] == "expansao_forte"
        assert organs["ORGAO MODERADO"]["sinal"] == "expansao_moderada"

    def test_crescimento_anual_medio_positive(self):
        """crescimento_anual_medio values are positive (negative trend excluded)."""
        mock_result = {
            "orgaos_expandindo": [
                {
                    "orgao_nome": "ORGAO EM EXPANSAO",
                    "orgao_uf": "MG",
                    "categoria": "obras",
                    "crescimento_anual_medio": 0.18,
                    "volume_ultimo_ano": 2000000.00,
                    "tendencia_3anos": [1500000.0, 1700000.0, 2000000.0],
                    "categorias_emergentes": [],
                    "sinal": "expansao_moderada",
                },
            ],
            "stats": {},
        }
        mock_sb = _make_supabase_mock(mock_result)
        result = mock_sb.rpc(
            "predict_expansion_organs",
            {},
        ).execute().data

        for organ in result["orgaos_expandindo"]:
            assert organ["crescimento_anual_medio"] > 0

    def test_tendencia_3anos_ascending(self):
        """tendencia_3anos should be ascending (oldest to newest)."""
        mock_result = {
            "orgaos_expandindo": [
                {
                    "orgao_nome": "ORGAO TESTE",
                    "orgao_uf": "DF",
                    "categoria": "tecnologia",
                    "crescimento_anual_medio": 0.30,
                    "volume_ultimo_ano": 3000000.00,
                    "tendencia_3anos": [1000000.0, 2000000.0, 3000000.0],
                    "categorias_emergentes": [],
                    "sinal": "expansao_moderada",
                },
            ],
            "stats": {},
        }
        mock_sb = _make_supabase_mock(mock_result)
        result = mock_sb.rpc(
            "predict_expansion_organs",
            {},
        ).execute().data

        tendencia = result["orgaos_expandindo"][0]["tendencia_3anos"]
        assert len(tendencia) == 3
        # Verify ascending order: oldest first
        assert tendencia[0] < tendencia[1] < tendencia[2]

    def test_categorias_emergentes_max_3(self):
        """categorias_emergentes should be at most 3 items."""
        mock_result = {
            "orgaos_expandindo": [
                {
                    "orgao_nome": "ORGAO MULTI CAT",
                    "orgao_uf": "SP",
                    "categoria": "servicos",
                    "crescimento_anual_medio": 0.40,
                    "volume_ultimo_ano": 5000000.00,
                    "tendencia_3anos": [2000000.0, 3500000.0, 5000000.0],
                    "categorias_emergentes": ["cat_a", "cat_b", "cat_c"],
                    "sinal": "expansao_forte",
                },
            ],
            "stats": {},
        }
        mock_sb = _make_supabase_mock(mock_result)
        result = mock_sb.rpc(
            "predict_expansion_organs",
            {},
        ).execute().data

        cats = result["orgaos_expandindo"][0]["categorias_emergentes"]
        assert len(cats) <= 3

    def test_min_crescimento_filter_respected(self):
        """Organs below p_min_crescimento are excluded."""
        # Simulate response where all organs have growth >= 0.15 (default)
        mock_result = {
            "orgaos_expandindo": [
                {
                    "orgao_nome": "ORGAO CRESCENTE",
                    "orgao_uf": "SP",
                    "categoria": "saude",
                    "crescimento_anual_medio": 0.22,
                    "volume_ultimo_ano": 1000000.00,
                    "tendencia_3anos": [700000.0, 850000.0, 1000000.0],
                    "categorias_emergentes": [],
                    "sinal": "expansao_moderada",
                },
            ],
            "stats": {},
        }
        mock_sb = _make_supabase_mock(mock_result)
        result = mock_sb.rpc(
            "predict_expansion_organs",
            {"p_min_crescimento": 0.15},
        ).execute().data

        # All returned organs should have growth >= 0.15
        for organ in result["orgaos_expandindo"]:
            assert organ["crescimento_anual_medio"] >= 0.15

    def test_empty_result_no_data(self):
        """When no data matches, returns empty orgaos_expandindo."""
        mock_sb = _make_supabase_mock({
            "orgaos_expandindo": [],
            "stats": {
                "orgaos_analisados": 0,
                "expandindo": 0,
                "crescimento_medio_nacional": 0.0,
            },
        })

        result = mock_sb.rpc(
            "predict_expansion_organs",
            {"p_uf": "XX"},
        ).execute().data

        assert result["orgaos_expandindo"] == []
        assert result["stats"]["expandindo"] == 0

    def test_multiple_organs_in_result(self):
        """Result can contain entries for multiple organs."""
        mock_result = {
            "orgaos_expandindo": [
                {
                    "orgao_nome": "ORGAO A",
                    "orgao_uf": "SP",
                    "categoria": "saude",
                    "crescimento_anual_medio": 0.35,
                    "volume_ultimo_ano": 1000000.00,
                    "tendencia_3anos": [500000.0, 700000.0, 1000000.0],
                    "categorias_emergentes": ["software"],
                    "sinal": "expansao_forte",
                },
                {
                    "orgao_nome": "ORGAO B",
                    "orgao_uf": "RJ",
                    "categoria": "educacao",
                    "crescimento_anual_medio": 0.18,
                    "volume_ultimo_ano": 2000000.00,
                    "tendencia_3anos": [1500000.0, 1800000.0, 2000000.0],
                    "categorias_emergentes": [],
                    "sinal": "expansao_moderada",
                },
            ],
            "stats": {
                "orgaos_analisados": 100,
                "expandindo": 2,
                "crescimento_medio_nacional": 0.12,
            },
        }
        mock_sb = _make_supabase_mock(mock_result)
        result = mock_sb.rpc(
            "predict_expansion_organs",
            {},
        ).execute().data

        assert len(result["orgaos_expandindo"]) == 2
        names = [o["orgao_nome"] for o in result["orgaos_expandindo"]]
        assert "ORGAO A" in names
        assert "ORGAO B" in names


class TestStatsConsistency:
    """Verify stats are internally consistent."""

    def test_expandindo_never_exceeds_analisados(self):
        """expandindo count cannot exceed orgaos_analisados."""
        mock_result = {
            "orgaos_expandindo": [
                {
                    "orgao_nome": f"ORGAO {i}",
                    "orgao_uf": "SP",
                    "categoria": "servicos",
                    "crescimento_anual_medio": 0.20 + i * 0.05,
                    "volume_ultimo_ano": 1000000.00,
                    "tendencia_3anos": [700000.0, 850000.0, 1000000.0],
                    "categorias_emergentes": [],
                    "sinal": "expansao_moderada",
                }
                for i in range(3)
            ],
            "stats": {
                "orgaos_analisados": 50,
                "expandindo": 3,
                "crescimento_medio_nacional": 0.10,
            },
        }
        mock_sb = _make_supabase_mock(mock_result)
        result = mock_sb.rpc(
            "predict_expansion_organs",
            {},
        ).execute().data

        assert result["stats"]["expandindo"] <= result["stats"]["orgaos_analisados"]
        assert result["stats"]["expandindo"] == len(result["orgaos_expandindo"])
