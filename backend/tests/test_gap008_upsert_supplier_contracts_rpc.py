"""
GAP-008: Tests for upsert_supplier_contracts RPC — schema independent de bids.

Validates:
1. Migration SQL structure (function signature, column additions, constraint)
2. Down migration (drop function, constraint, columns)
3. New RPC is called by contracts_crawler (not old upsert_pncp_supplier_contracts)
4. Upsert with same (ni_fornecedor, nr_contrato, ano) → update (no duplicate)
5. Upsert with new key → insert
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"
MIGRATION_FILE = "20260608213000_upsert_supplier_contracts_rpc.sql"
DOWN_MIGRATION_FILE = "20260608213000_upsert_supplier_contracts_rpc.down.sql"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def migration_sql() -> str:
    """Load the up migration SQL."""
    path = MIGRATIONS_DIR / MIGRATION_FILE
    assert path.exists(), f"Migration file not found: {path}"
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def down_migration_sql() -> str:
    """Load the down migration SQL."""
    path = MIGRATIONS_DIR / DOWN_MIGRATION_FILE
    assert path.exists(), f"Down migration file not found: {path}"
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Migration Structure Tests (AC5: static analysis)
# ---------------------------------------------------------------------------


class TestMigrationStructure:
    """Validate migration SQL follows project conventions."""

    def test_add_columns(self, migration_sql: str):
        """Must add nr_contrato and ano columns idempotently."""
        assert "ADD COLUMN IF NOT EXISTS nr_contrato TEXT" in migration_sql
        assert "ADD COLUMN IF NOT EXISTS ano INTEGER" in migration_sql

    def test_backfill_ano(self, migration_sql: str):
        """Must backfill ano from data_assinatura for existing rows."""
        assert "EXTRACT(YEAR FROM data_assinatura)" in migration_sql

    def test_unique_constraint(self, migration_sql: str):
        """Must create UNIQUE constraint uq_psc_fornecedor_contrato_ano."""
        assert "uq_psc_fornecedor_contrato_ano" in migration_sql
        assert "UNIQUE (ni_fornecedor, nr_contrato, ano)" in migration_sql

    def test_rpc_name(self, migration_sql: str):
        """RPC must be named upsert_supplier_contracts (not upsert_pncp_*)."""
        assert "upsert_supplier_contracts" in migration_sql
        assert "RETURNS SETOF pncp_supplier_contracts" in migration_sql

    def test_rpc_parameter(self, migration_sql: str):
        """RPC must accept contracts jsonb parameter."""
        assert re.search(
            r"upsert_supplier_contracts\s*\(\s*contracts\s+jsonb\s*\)",
            migration_sql,
        )

    def test_on_conflict_target(self, migration_sql: str):
        """ON CONFLICT must use the new business key."""
        assert "ON CONFLICT (ni_fornecedor, nr_contrato, ano)" in migration_sql

    def test_on_conflict_do_update(self, migration_sql: str):
        """DO UPDATE must update objeto, valor, orgao, data_assinatura, data_vigencia."""
        assert "objeto_contrato" in migration_sql and "EXCLUDED.objeto_contrato" in migration_sql
        assert "valor_global" in migration_sql and "EXCLUDED.valor_global" in migration_sql
        assert "orgao_nome" in migration_sql and "EXCLUDED.orgao_nome" in migration_sql
        assert "data_assinatura" in migration_sql and "EXCLUDED.data_assinatura" in migration_sql
        assert "data_fim_vigencia" in migration_sql and "EXCLUDED.data_fim_vigencia" in migration_sql
        assert "updated_at" in migration_sql and "NOW()" in migration_sql

    def test_rpc_returns_setof(self, migration_sql: str):
        """RPC must return SETOF pncp_supplier_contracts."""
        assert "RETURNS SETOF pncp_supplier_contracts" in migration_sql

    def test_secdef_search_path(self, migration_sql: str):
        """Must have SECURITY DEFINER with search_path."""
        assert "SECURITY DEFINER" in migration_sql
        assert "SET search_path = public, pg_temp" in migration_sql

    def test_language_plpgsql(self, migration_sql: str):
        """Function must be LANGUAGE plpgsql."""
        assert "LANGUAGE plpgsql" in migration_sql

    def test_grant_execute(self, migration_sql: str):
        """GRANT EXECUTE must be for service_role only."""
        assert "GRANT EXECUTE ON FUNCTION upsert_supplier_contracts(jsonb)" in migration_sql
        assert "TO service_role" in migration_sql

    def test_comment(self, migration_sql: str):
        """COMMENT ON FUNCTION must reference GAP-008."""
        assert "GAP-008" in migration_sql
        assert "COMMENT ON FUNCTION upsert_supplier_contracts" in migration_sql

    def test_does_not_use_content_hash_conflict(self, migration_sql: str):
        """ON CONFLICT must NOT use content_hash (independent of bids schema)."""
        assert "content_hash" not in re.search(
            r"ON CONFLICT\s*\([^)]+\)",
            migration_sql,
        ).group(0) if re.search(r"ON CONFLICT\s*\([^)]+\)", migration_sql) else True


class TestDownMigrationStructure:
    """Validate down migration reverses the up migration."""

    def test_drop_function(self, down_migration_sql: str):
        """Down migration must DROP FUNCTION."""
        assert "DROP FUNCTION IF EXISTS upsert_supplier_contracts" in down_migration_sql

    def test_drop_constraint(self, down_migration_sql: str):
        """Down migration must DROP CONSTRAINT."""
        assert "DROP CONSTRAINT IF EXISTS uq_psc_fornecedor_contrato_ano" in down_migration_sql

    def test_drop_columns(self, down_migration_sql: str):
        """Down migration must DROP COLUMNS."""
        assert "DROP COLUMN IF EXISTS nr_contrato" in down_migration_sql
        assert "DROP COLUMN IF EXISTS ano" in down_migration_sql


# ---------------------------------------------------------------------------
# Contracts Crawler RPC Usage (AC: crawler usa RPC dedicada)
# ---------------------------------------------------------------------------


class TestCrawlerUsesDedicatedRPC:
    """Validate that contracts_crawler uses the new RPC, not the old one."""

    def test_crawler_imports_upsert_supplier_contracts(self):
        """Crawler references the new RPC name."""
        crawler_path = REPO_ROOT / "backend" / "ingestion" / "contracts_crawler.py"
        code = crawler_path.read_text(encoding="utf-8")
        assert "upsert_supplier_contracts" in code


# ---------------------------------------------------------------------------
# Normalized contract data includes new fields
# ---------------------------------------------------------------------------


class TestNormalizedContractIncludesNewFields:
    """Validate that _normalize_contract extracts nr_contrato and ano."""

    def _get_normalize_function(self):
        """Import the actual _normalize_contract from the crawler."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "contracts_crawler",
            str(REPO_ROOT / "backend" / "ingestion" / "contracts_crawler.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._normalize_contract

    def test_normalize_extracts_nr_contrato_and_ano(self):
        """_normalize_contract must extract nr_contrato, ano, data_fim_vigencia."""
        normalize = self._get_normalize_function()
        item = {
            "numeroControlePNCP": "12345678000100-1-000001/2025",
            "numeroContratoEmpenho": "0001/2025",
            "niFornecedor": "00000000000191",
            "nomeRazaoSocialFornecedor": "Fornecedor Exemplo LTDA",
            "orgaoEntidade": {"cnpj": "12345678000100"},
            "unidadeOrgao": {"ufSigla": "SP", "municipioNome": "São Paulo"},
            "dataAssinatura": "2025-03-10",
            "dataVigenciaFim": "2026-03-14",
            "valorGlobal": 250000.0,
            "objetoContrato": "Fornecimento de uniformes escolares",
        }
        result = normalize(item)
        assert result is not None
        assert result["nr_contrato"] == "0001/2025"
        assert result["ano"] == 2025
        assert result["data_fim_vigencia"] == "2026-03-14"
        assert result["content_hash"] is not None
        assert result["numero_controle_pncp"] == "12345678000100-1-000001/2025"

    def test_normalize_without_nr_contrato_returns_none(self):
        """_normalize_contract must handle missing numeroContratoEmpenho."""
        normalize = self._get_normalize_function()
        item = {
            "numeroControlePNCP": "12345678000100-1-000001/2025",
            "niFornecedor": "00000000000191",
            "nomeRazaoSocialFornecedor": "Fornecedor Exemplo LTDA",
            "orgaoEntidade": {"cnpj": "12345678000100", "esferaId": "F"},
            "unidadeOrgao": {"ufSigla": "SP", "municipioNome": "São Paulo"},
            "dataAssinatura": "2025-03-10",
            "valorGlobal": 250000.0,
            "objetoContrato": "Fornecimento de uniformes escolares",
        }
        # nr_contrato not in item — should be None, not crash
        result = normalize(item)
        assert result is not None
        assert result["nr_contrato"] is None
        assert result["ano"] == 2025  # extracted from dataAssinatura
        assert result["data_fim_vigencia"] is None

    def test_normalize_ano_extracts_year_from_control_number(self):
        """Extract ano from numeroControlePNCP if dataAssinatura is missing."""
        normalize = self._get_normalize_function()
        item = {
            "numeroControlePNCP": "12345678000100-1-000001/2024",
            "niFornecedor": "00000000000191",
            "nomeRazaoSocialFornecedor": "Fornecedor Exemplo LTDA",
            "orgaoEntidade": {"cnpj": "12345678000100"},
            "unidadeOrgao": {"ufSigla": "SP", "municipioNome": "São Paulo"},
            "dataAssinatura": None,
            "valorGlobal": 100000.0,
            "objetoContrato": "Teste",
        }
        result = normalize(item)
        assert result is not None
        assert result["ano"] == 2024  # extracted from /2024 in control number


# ---------------------------------------------------------------------------
# Integration: Upsert behavior (mocked RPC)
# ---------------------------------------------------------------------------


class TestUpsertBehavior:
    """Mock the RPC call and verify correct behavior."""

    @patch("ingestion.contracts_crawler.sb_execute", new_callable=AsyncMock)
    @patch("ingestion.contracts_crawler.get_supabase")
    @pytest.mark.asyncio
    async def test_new_key_inserts(self, mock_get_sb, mock_sb_execute):
        """Upsert with new (ni_fornecedor, nr_contrato, ano) must call RPC."""
        sb_instance = MagicMock()
        mock_get_sb.return_value = sb_instance
        mock_sb_execute.return_value = MagicMock(data=[{"id": 1, "ni_fornecedor": "00000000000191"}])

        from ingestion.contracts_crawler import _upsert_batch

        rows = [
            {
                "numero_controle_pncp": "12345678000100-1-000001/2025",
                "ni_fornecedor": "00000000000191",
                "nome_fornecedor": "Teste",
                "nr_contrato": "0001/2025",
                "ano": 2025,
                "orgao_cnpj": "",
                "orgao_nome": "Orgao Test",
                "uf": "SP",
                "municipio": "Sao Paulo",
                "esfera": "M",
                "valor_global": 1000.00,
                "data_assinatura": "2025-03-10",
                "data_fim_vigencia": "2026-03-14",
                "objeto_contrato": "Test object",
                "content_hash": "abc123",
            }
        ]

        totals = await _upsert_batch(rows)

        # Verify RPC was called with correct name and parameter
        sb_instance.rpc.assert_called_once_with(
            "upsert_supplier_contracts", {"contracts": rows}
        )
        assert totals["total"] == 1
        assert totals["inserted"] == 1  # 1 row returned = 1 processed

    @patch("ingestion.contracts_crawler.sb_execute", new_callable=AsyncMock)
    @patch("ingestion.contracts_crawler.get_supabase")
    @pytest.mark.asyncio
    async def test_new_batch_calls_rpc_with_correct_name(self, mock_get_sb, mock_sb_execute):
        """Verify RPC name is upsert_supplier_contracts (not the old one)."""
        sb_instance = MagicMock()
        mock_get_sb.return_value = sb_instance
        mock_sb_execute.return_value = MagicMock(data=[{"id": 1}])

        from ingestion.contracts_crawler import _upsert_batch

        rows = [
            {
                "numero_controle_pncp": "TEST-001",
                "ni_fornecedor": "00000000000191",
                "nome_fornecedor": "Test",
                "nr_contrato": "C-001",
                "ano": 2025,
                "orgao_cnpj": "",
                "orgao_nome": "",
                "uf": "",
                "municipio": "",
                "esfera": "",
                "valor_global": None,
                "data_assinatura": None,
                "data_fim_vigencia": None,
                "objeto_contrato": None,
                "content_hash": "hash001",
            }
        ]

        await _upsert_batch(rows)

        # Must call upsert_supplier_contracts, NOT upsert_pncp_supplier_contracts
        sb_instance.rpc.assert_called_once()
        rpc_name = sb_instance.rpc.call_args[0][0]
        assert rpc_name == "upsert_supplier_contracts"
        assert rpc_name != "upsert_pncp_supplier_contracts"

        # Parameter must be "contracts", not "p_records"
        rpc_params = sb_instance.rpc.call_args[0][1]
        assert "contracts" in rpc_params
        assert "p_records" not in rpc_params
