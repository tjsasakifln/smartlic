"""Tests for COMPINT-014: Competitive Dossie PDF endpoint.

Covers:
  - POST /v1/intel-concorrente/dossie/{cnpj}
  - GET  /v1/intel-concorrente/dossie/{cnpj}/{job_id}/status
  - PDF generation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
class TestCompetitiveDossie:
    """POST /v1/intel-concorrente/dossie/{cnpj} tests."""

    async def test_dossie_returns_job_id(self):
        """Should return a DossieResponse with a job_id."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
             patch("routes.competitive_intel._dossie_jobs", {}), \
             patch("pdf_generator_competitive_dossie.generate_competitive_dossie_report",
                   return_value=MagicMock(getvalue=MagicMock(return_value=b"%PDF-1.4 test"))):
            from routes.competitive_intel import generate_competitive_dossie
            result = await generate_competitive_dossie(
                cnpj="12345678000195",
                body=None,
            )
        assert result.job_id is not None
        assert result.cnpj == "12345678000195"
        assert result.status in ("queued", "done")

    async def test_dossie_status(self):
        """GET status should return current job state."""
        from routes.competitive_intel import _dossie_jobs, get_dossie_status

        _dossie_jobs["test-job"] = {
            "cnpj": "12345678000195",
            "status": "processing",
            "progress": 50,
            "download_url": None,
            "error": None,
            "created_at": "2026-06-12T00:00:00",
        }
        try:
            with patch("config.features.get_feature_flag", return_value=True), \
                 patch("authorization.has_master_access", new=AsyncMock(return_value=True)):
                result = await get_dossie_status(
                    cnpj="12345678000195",
                    job_id="test-job",
                )
            assert result.status == "processing"
            assert result.progress == 50
        finally:
            _dossie_jobs.pop("test-job", None)

    async def test_dossie_status_not_found(self):
        """Unknown job_id should return 404."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)):
            from routes.competitive_intel import get_dossie_status
            with pytest.raises(HTTPException) as exc:
                await get_dossie_status(
                    cnpj="12345678000195",
                    job_id="nonexistent-job",
                )
        assert exc.value.status_code == 404


class TestPdfGenerator:
    """PDF generator unit tests."""

    def test_generate_empty_dossie(self):
        """Empty data should produce a valid PDF."""
        from pdf_generator_competitive_dossie import generate_competitive_dossie_report

        db = MagicMock()

        # Mock the table chain: .table().select().eq().ilike().order().execute() -> data
        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=[])
        db.table.return_value.select.return_value.eq.return_value.ilike.return_value.order.return_value = mock_chain

        bio = generate_competitive_dossie_report(
            db=db, cnpj="12345678000195", setor_id="informatica",
            include_llm_summary=False,
        )
        pdf_bytes = bio.getvalue()
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 100

    def test_generate_dossie_with_data(self):
        """Should generate PDF with contract data."""
        from pdf_generator_competitive_dossie import generate_competitive_dossie_report

        db = MagicMock()
        mock_rows = [
            {
                "valor_global": 50000.0,
                "uf": "SP",
                "data_assinatura": "2026-01-15",
                "nome_fornecedor": "Empresa Teste Ltda",
                "objeto_contrato": "Servicos de TI",
            },
            {
                "valor_global": 30000.0,
                "uf": "RJ",
                "data_assinatura": "2026-02-20",
                "nome_fornecedor": "Empresa Teste Ltda",
                "objeto_contrato": "Consultoria",
            },
        ]

        mock_chain = MagicMock()
        mock_chain.execute.return_value = MagicMock(data=mock_rows)
        db.table.return_value.select.return_value.eq.return_value.ilike.return_value.order.return_value = mock_chain

        bio = generate_competitive_dossie_report(
            db=db, cnpj="12345678000195", setor_id="informatica",
            include_llm_summary=False,
        )
        pdf_bytes = bio.getvalue()
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 500
