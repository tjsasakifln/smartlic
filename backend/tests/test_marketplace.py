"""MKT-001 (#1616): Tests for Subcontract Marketplace MVP.

Covers:
- Schemas: serialization/validation
- Routes: listing, expressing interest, contact reveal
- Config: feature flag registration
- Discovery job: heuristic logic
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from schemas.marketplace import (
    ContactRevealResponse,
    ExpressInterestRequest,
    MarketplaceFilter,
    SubcontractOpportunity,
    SubcontractOpportunityResponse,
)

# ============================================================================
# Schema Tests
# ============================================================================


class TestMarketplaceSchemas:
    """Pydantic schema validation and serialization."""

    def test_subcontract_opportunity_minimal(self):
        """Minimal opportunity creates successfully."""
        opp = SubcontractOpportunity(
            id="abc-123",
            winner_cnpj="12345678000195",
            created_at=datetime.now(timezone.utc),
        )
        assert opp.id == "abc-123"
        assert opp.winner_cnpj == "12345678000195"
        assert opp.status == "open"
        assert opp.services_needed == []
        assert opp.interest_count == 0

    def test_subcontract_opportunity_full(self):
        """Full opportunity with all fields."""
        opp = SubcontractOpportunity(
            id="abc-123",
            contract_id="contract-1",
            winner_cnpj="12345678000195",
            winner_name="Empresa Exemplo Ltda",
            sector="construcao_civil",
            value=1500000.00,
            services_needed=["obra", "instalação elétrica"],
            status="open",
            uf="SP",
            municipio="São Paulo",
            orgao_nome="Prefeitura",
            objeto="Construção de escola municipal",
            discovery_reason="Múltiplas especialidades identificadas",
            created_at=datetime.now(timezone.utc),
            interest_count=3,
        )
        assert opp.value == 1500000.00
        assert len(opp.services_needed) == 2
        assert opp.interest_count == 3

    def test_subcontract_opportunity_response(self):
        """Paginated response serializes correctly."""
        opp = SubcontractOpportunity(
            id="abc-123",
            winner_cnpj="12345678000195",
            created_at=datetime.now(timezone.utc),
        )
        response = SubcontractOpportunityResponse(
            opportunities=[opp],
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
        )
        assert response.total == 1
        assert len(response.opportunities) == 1
        assert response.total_pages == 1

    def test_express_interest_request_minimal(self):
        """Minimal interest request."""
        req = ExpressInterestRequest(opportunity_id="abc-123")
        assert req.opportunity_id == "abc-123"
        assert req.message is None

    def test_express_interest_request_with_message(self):
        """Interest request with message."""
        req = ExpressInterestRequest(
            opportunity_id="abc-123",
            message="Tenho interesse em participar",
        )
        assert req.message == "Tenho interesse em participar"

    def test_express_interest_request_message_too_long(self):
        """Message longer than 1000 chars raises validation error."""
        with pytest.raises(ValueError):
            ExpressInterestRequest(
                opportunity_id="abc-123",
                message="x" * 1001,
            )

    def test_marketplace_filter_defaults(self):
        """Marketplace filter has correct defaults."""
        filt = MarketplaceFilter()
        assert filt.setor is None
        assert filt.uf is None
        assert filt.page == 1
        assert filt.page_size == 20

    def test_marketplace_filter_custom(self):
        """Marketplace filter with custom values."""
        filt = MarketplaceFilter(setor="construcao_civil", uf="SP", page=2, page_size=10)
        assert filt.setor == "construcao_civil"
        assert filt.uf == "SP"
        assert filt.page == 2
        assert filt.page_size == 10

    def test_contact_reveal_response(self):
        """Contact reveal response."""
        resp = ContactRevealResponse(
            winner_cnpj="12345678000195",
            winner_name="Empresa Ltda",
            winner_email="contato@empresa.com",
        )
        assert resp.winner_cnpj == "12345678000195"
        assert resp.winner_email == "contato@empresa.com"
        assert "Insight+" in resp.message


# ============================================================================
# Route Tests
# ============================================================================


class TestMarketplaceRoutes:
    """Route behavior with mocked dependencies."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database client."""
        db = MagicMock()
        db.table.return_value = db
        db.select.return_value = db
        db.eq.return_value = db
        db.order.return_value = db
        db.range.return_value = db
        db.limit.return_value = db
        db.count = 10
        return db

    @pytest.fixture
    def mock_user(self):
        """Create a mock authenticated user."""
        return {"sub": "user-123", "plan_type": "smartlic_pro"}

    @pytest.fixture
    def sample_opportunities(self):
        """Sample opportunity data as returned from DB."""
        now = datetime.now(timezone.utc).isoformat()
        return [
            {
                "id": "opp-1",
                "contract_id": "contract-1",
                "winner_cnpj": "12345678000195",
                "winner_name": "Construtora Exemplo Ltda",
                "sector": "construcao_civil",
                "value": 2500000.00,
                "services_needed": ["obra", "instalação elétrica"],
                "status": "open",
                "uf": "SP",
                "municipio": "São Paulo",
                "orgao_nome": "Prefeitura de SP",
                "objeto": "Construção de escola",
                "discovery_reason": "Múltiplas especialidades",
                "created_at": now,
            },
            {
                "id": "opp-2",
                "contract_id": "contract-2",
                "winner_cnpj": "98765432000110",
                "winner_name": "Tech Solutions Ltda",
                "sector": "informatica",
                "value": 500000.00,
                "services_needed": ["suporte técnico"],
                "status": "open",
                "uf": "RJ",
                "municipio": "Rio de Janeiro",
                "orgao_nome": "Governo do RJ",
                "objeto": "Suporte de TI",
                "discovery_reason": "Setor de alta subcontratação",
                "created_at": now,
            },
        ]

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    @patch("routes.marketplace.sb_execute")
    async def test_list_opportunities(
        self, mock_sb_execute, mock_enabled, mock_db, mock_user, sample_opportunities
    ):
        """GET /marketplace/opportunities returns paginated opportunities."""
        from routes.marketplace import list_opportunities

        # Mock the DB query result
        mock_result = MagicMock()
        mock_result.data = sample_opportunities
        mock_result.count = 2

        # First call returns opportunities, second call returns interest count
        mock_sb_execute.side_effect = [
            mock_result,  # opportunities query
            MagicMock(data=[{"id": "int-1"}], count=1),  # interest count for opp-1
            MagicMock(data=[], count=0),  # interest count for opp-2
        ]

        response = await list_opportunities(
            setor=None,
            uf=None,
            page=1,
            page_size=20,
            user=mock_user,
            db=mock_db,
        )

        assert len(response.opportunities) == 2
        assert response.total == 2
        assert response.page == 1
        assert response.total_pages == 1
        assert response.opportunities[0].interest_count >= 0

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    @patch("routes.marketplace.sb_execute")
    async def test_list_opportunities_empty(
        self, mock_sb_execute, mock_enabled, mock_db, mock_user
    ):
        """GET /marketplace/opportunities returns empty list when no results."""
        from routes.marketplace import list_opportunities

        mock_result = MagicMock()
        mock_result.data = []
        mock_result.count = 0
        mock_sb_execute.return_value = mock_result

        response = await list_opportunities(
            setor=None,
            uf=None,
            page=1,
            page_size=20,
            user=mock_user,
            db=mock_db,
        )

        assert len(response.opportunities) == 0
        assert response.total == 0

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    @patch("routes.marketplace.sb_execute")
    async def test_list_opportunities_with_filters(
        self, mock_sb_execute, mock_enabled, mock_db, mock_user
    ):
        """GET /marketplace/opportunities applies sector and UF filters."""
        from routes.marketplace import list_opportunities

        mock_result = MagicMock()
        mock_result.data = []
        mock_result.count = 0
        mock_sb_execute.return_value = mock_result

        await list_opportunities(
            setor="construcao_civil",
            uf="SP",
            page=1,
            page_size=20,
            user=mock_user,
            db=mock_db,
        )

        # Verify filters were applied
        mock_db.eq.assert_any_call("sector", "construcao_civil")
        mock_db.eq.assert_any_call("uf", "SP")

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled")
    async def test_list_opportunities_disabled(
        self, mock_enabled, mock_db, mock_user
    ):
        """When feature flag is false, endpoint returns 404."""
        from routes.marketplace import list_opportunities

        mock_enabled.side_effect = HTTPException(status_code=404, detail="Disabled")

        with pytest.raises(HTTPException) as exc:
            await list_opportunities(
                setor=None,
                uf=None,
                page=1,
                page_size=20,
                user=mock_user,
                db=mock_db,
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    @patch("routes.marketplace.sb_execute")
    async def test_express_interest_success(
        self, mock_sb_execute, mock_enabled, mock_db, mock_user
    ):
        """POST express-interest registers interest successfully."""
        from routes.marketplace import express_interest

        # First call: opportunity exists and is open
        opp_result = MagicMock()
        opp_result.data = [{"id": "opp-1", "status": "open"}]
        # Second call: insert interest
        insert_result = MagicMock()
        insert_result.data = [{"id": "int-1"}]

        mock_sb_execute.side_effect = [opp_result, insert_result]

        response = await express_interest(
            ExpressInterestRequest(opportunity_id="opp-1", message="Quero participar"),
            user=mock_user,
            db=mock_db,
        )

        assert response.success is True
        assert "sucesso" in response.message

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    @patch("routes.marketplace.sb_execute")
    async def test_express_interest_opportunity_not_found(
        self, mock_sb_execute, mock_enabled, mock_db, mock_user
    ):
        """POST express-interest returns 404 when opportunity doesn't exist."""
        from routes.marketplace import express_interest

        mock_result = MagicMock()
        mock_result.data = []
        mock_sb_execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc:
            await express_interest(
                ExpressInterestRequest(opportunity_id="invalid-id"),
                user=mock_user,
                db=mock_db,
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    @patch("routes.marketplace.sb_execute")
    async def test_express_interest_opportunity_closed(
        self, mock_sb_execute, mock_enabled, mock_db, mock_user
    ):
        """POST express-interest returns 400 when opportunity is closed."""
        from routes.marketplace import express_interest

        mock_result = MagicMock()
        mock_result.data = [{"id": "opp-1", "status": "closed"}]
        mock_sb_execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc:
            await express_interest(
                ExpressInterestRequest(opportunity_id="opp-1"),
                user=mock_user,
                db=mock_db,
            )
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    @patch("routes.marketplace.sb_execute")
    async def test_express_interest_duplicate(
        self, mock_sb_execute, mock_enabled, mock_db, mock_user
    ):
        """POST express-interest returns 409 on duplicate."""
        from routes.marketplace import express_interest

        opp_result = MagicMock()
        opp_result.data = [{"id": "opp-1", "status": "open"}]
        mock_sb_execute.side_effect = [
            opp_result,
            Exception("duplicate key value violates unique constraint"),
        ]

        with pytest.raises(HTTPException) as exc:
            await express_interest(
                ExpressInterestRequest(opportunity_id="opp-1"),
                user=mock_user,
                db=mock_db,
            )
        assert exc.value.status_code == 409

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    @patch("routes.marketplace.sb_execute")
    async def test_reveal_contact_insight_plus(
        self, mock_sb_execute, mock_enabled, mock_db
    ):
        """Users with Insight+ can reveal contact details."""
        from routes.marketplace import reveal_contact

        insight_user = {"sub": "user-123", "plan_type": "smartlic_pro"}

        opp_result = MagicMock()
        opp_result.data = [{
            "id": "opp-1",
            "winner_cnpj": "12345678000195",
            "winner_name": "Construtora Ltda",
            "value": 2500000.00,
            "orgao_nome": "Prefeitura",
        }]
        entity_result = MagicMock()
        entity_result.data = [{"email": "contato@empresa.com", "telefone": "11999999999"}]

        mock_sb_execute.side_effect = [opp_result, entity_result]

        response = await reveal_contact(
            opportunity_id="opp-1",
            user=insight_user,
            db=mock_db,
        )

        assert response.winner_cnpj == "12345678000195"
        assert response.winner_email == "contato@empresa.com"
        assert response.winner_phone == "11999999999"

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    async def test_reveal_contact_free_trial_blocked(
        self, mock_enabled, mock_db
    ):
        """Free trial users get 402 for contact reveal."""
        from routes.marketplace import reveal_contact

        free_user = {"sub": "user-123", "plan_type": "free_trial"}

        with pytest.raises(HTTPException) as exc:
            await reveal_contact(
                opportunity_id="opp-1",
                user=free_user,
                db=mock_db,
            )
        assert exc.value.status_code == 402

    @pytest.mark.asyncio
    @patch("routes.marketplace._marketplace_enabled", return_value=None)
    async def test_reveal_contact_opportunity_not_found(
        self, mock_enabled, mock_db
    ):
        """Contact reveal returns 404 when opportunity doesn't exist."""
        from routes.marketplace import reveal_contact

        insight_user = {"sub": "user-123", "plan_type": "smartlic_pro"}

        with patch("routes.marketplace.sb_execute") as mock_sb:
            mock_result = MagicMock()
            mock_result.data = []
            mock_sb.return_value = mock_result

            with pytest.raises(HTTPException) as exc:
                await reveal_contact(
                    opportunity_id="invalid-id",
                    user=insight_user,
                    db=mock_db,
                )
            assert exc.value.status_code == 404


# ============================================================================
# Discovery Job Tests
# ============================================================================


class TestSubcontractDiscovery:
    """Discovery job heuristic logic."""

    def test_derive_sector_from_objeto(self):
        """Sector derivation works from object keywords."""
        from jobs.cron.subcontract_discovery import _derive_sector

        assert _derive_sector("Construção de ponte metálica", []) == "construcao_civil"
        assert _derive_sector("Serviços de engenharia consultiva", []) == "engenharia"
        assert _derive_sector("Desenvolvimento de sistema web", []) == "software_desenvolvimento"
        assert _derive_sector("Limpeza e conservação", []) == "manutencao_predial"
        assert _derive_sector("Aquisição de alimentos", []) is None
        assert _derive_sector("Texto genérico sem setor definido", []) is None

    def test_derive_sector_from_keywords_fallback(self):
        """Sector derivation falls back to keywords if objeto is generic."""
        from jobs.cron.subcontract_discovery import _derive_sector

        result = _derive_sector("Contrato de prestação de serviços diversos", ["obra", "alvenaria"])
        assert result == "construcao_civil"

    def test_build_discovery_reason_multiple_specialties(self):
        """Discovery reason for multi-specialty heuristic."""
        from jobs.cron.subcontract_discovery import _build_discovery_reason

        reason = _build_discovery_reason(
            {"reason": "multiple_specialties", "keywords": ["obra", "instalação elétrica"]},
            "Construtora Exemplo Ltda",
            2000000.00,
        )
        assert "múltiplas especialidades" in reason
        assert "Construtora Exemplo Ltda" in reason
        assert "2,000,000" in reason

    def test_build_discovery_reason_small_winner(self):
        """Discovery reason for small winner heuristic."""
        from jobs.cron.subcontract_discovery import _build_discovery_reason

        reason = _build_discovery_reason(
            {"reason": "small_winner_large_contract"},
            "MEI João Silva",
            6000000.00,
        )
        assert "micro/pequena" in reason
        assert "MEI João Silva" in reason

    def test_build_discovery_reason_high_sub_sector(self):
        """Discovery reason for high sub sector heuristic."""
        from jobs.cron.subcontract_discovery import _build_discovery_reason

        reason = _build_discovery_reason(
            {"reason": "high_sub_sector"},
            "Tech Solutions Ltda",
            1500000.00,
        )
        assert "alta taxa" in reason
        assert "Tech Solutions Ltda" in reason

    @pytest.mark.asyncio
    @patch("jobs.cron.subcontract_discovery.sb_execute")
    async def test_discover_multi_specialty_upserts_opportunity(
        self, mock_sb_execute
    ):
        """Multi-specialty heuristic upserts opportunities."""
        from jobs.cron.subcontract_discovery import _discover_multi_specialty

        sb = MagicMock()
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.gte.return_value = sb
        sb.order.return_value = sb
        sb.limit.return_value = sb

        # First call: contracts found
        contracts_result = MagicMock()
        contracts_result.data = [
            {
                "id": "contract-1",
                "ni_fornecedor": "12345678000195",
                "nome_fornecedor": "Construtora Ltda",
                "valor_global": 2500000.00,
                "objeto_contrado": "Construção de escola com instalação elétrica e hidráulica",
                "uf": "SP",
                "municipio": "São Paulo",
                "orgao_nome": "Prefeitura",
            }
        ]

        # Second call: no existing opportunity
        existing_result = MagicMock()
        existing_result.data = []

        mock_sb_execute.side_effect = [
            contracts_result,
            existing_result,  # check existing
            MagicMock(data=[{"id": "new-opp"}]),  # insert
        ]

        result = await _discover_multi_specialty(sb)
        assert result == 1

    @pytest.mark.asyncio
    @patch("jobs.cron.subcontract_discovery.sb_execute")
    async def test_discover_multi_specialty_skips_existing(
        self, mock_sb_execute
    ):
        """Multi-specialty skips already discovered contracts."""
        from jobs.cron.subcontract_discovery import _discover_multi_specialty

        sb = MagicMock()
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.gte.return_value = sb
        sb.order.return_value = sb
        sb.limit.return_value = sb

        contracts_result = MagicMock()
        contracts_result.data = [
            {
                "id": "contract-1",
                "ni_fornecedor": "12345678000195",
                "nome_fornecedor": "Construtora Ltda",
                "valor_global": 2500000.00,
                "objeto_contrado": "Construção com instalação elétrica",
                "uf": "SP",
            }
        ]

        existing_result = MagicMock()
        existing_result.data = [{"id": "existing-opp"}]

        mock_sb_execute.side_effect = [
            contracts_result,
            existing_result,  # already exists
        ]

        result = await _discover_multi_specialty(sb)
        assert result == 0  # Skipped because already exists


# ============================================================================
# Feature Flag Tests
# ============================================================================


class TestMarketplaceFeatureFlag:
    """Feature flag registration and behavior."""

    def test_feature_flag_registered(self):
        """SUBCONTRACT_MARKETPLACE_ENABLED is registered with default true."""
        from config.features import _FEATURE_FLAG_REGISTRY

        assert "SUBCONTRACT_MARKETPLACE_ENABLED" in _FEATURE_FLAG_REGISTRY
        env_var, default = _FEATURE_FLAG_REGISTRY["SUBCONTRACT_MARKETPLACE_ENABLED"]
        assert env_var == "SUBCONTRACT_MARKETPLACE_ENABLED"
        assert default == "true"

    @patch.dict("os.environ", {"SUBCONTRACT_MARKETPLACE_ENABLED": "false"})
    def test_feature_flag_disabled(self):
        """Feature flag respects env var override."""
        from config.features import get_feature_flag

        assert get_feature_flag("SUBCONTRACT_MARKETPLACE_ENABLED") is False

    @patch.dict("os.environ", {}, clear=True)
    def test_feature_flag_default_true(self):
        """Feature flag defaults to true when env var not set."""
        from config.features import get_feature_flag, reload_feature_flags

        reload_feature_flags()
        assert get_feature_flag("SUBCONTRACT_MARKETPLACE_ENABLED") is True
