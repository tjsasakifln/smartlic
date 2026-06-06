"""Tests for DIGEST-002 (#1411): Digest builder logic.

Tests get_user_plan_tier(), get_user_sectors(), get_user_frequency(),
find_opportunities_for_sector(), and build_personalized_digest().
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import timedelta


# ============================================================================
# Helper: mock sb_execute
# ============================================================================

def _make_sb_result(data: list | dict | None) -> MagicMock:
    """Create a mock sb_execute return value with data."""
    r = MagicMock()
    r.data = data
    return r


# ============================================================================
# get_user_plan_tier() tests
# ============================================================================

class TestGetUserPlanTier:
    """Test plan tier resolution."""

    @pytest.mark.asyncio
    async def test_subscription_consulting(self):
        from services.digest_service import get_user_plan_tier

        mock_db = MagicMock()
        sub_result = _make_sb_result([{"plan_id": "smartlic_consulting_mensal"}])

        with patch("services.digest_service.sb_execute", return_value=sub_result):
            tier = await get_user_plan_tier("user-123", db=mock_db)

        assert tier == "smartlic_consulting"

    @pytest.mark.asyncio
    async def test_subscription_pro(self):
        from services.digest_service import get_user_plan_tier

        mock_db = MagicMock()
        sub_result = _make_sb_result([{"plan_id": "smartlic_pro_mensal"}])

        with patch("services.digest_service.sb_execute", return_value=sub_result):
            tier = await get_user_plan_tier("user-123", db=mock_db)

        assert tier == "smartlic_pro"

    @pytest.mark.asyncio
    async def test_fallback_to_profile(self):
        from services.digest_service import get_user_plan_tier

        mock_db = MagicMock()
        profile_result = _make_sb_result([{"plan_type": "free_trial"}])

        # First call (subscription) returns empty; second (profile) succeeds
        empty_result = _make_sb_result([])

        with patch(
            "services.digest_service.sb_execute",
            side_effect=[empty_result, profile_result],
        ):
            tier = await get_user_plan_tier("user-123", db=mock_db)

        assert tier == "free_trial"

    @pytest.mark.asyncio
    async def test_default_on_error(self):
        from services.digest_service import get_user_plan_tier

        mock_db = MagicMock()

        # Both subscription and profile queries fail
        with patch(
            "services.digest_service.sb_execute",
            side_effect=[Exception("sub error"), Exception("profile error")],
        ):
            tier = await get_user_plan_tier("user-123", db=mock_db)

        assert tier == "free_trial"

    @pytest.mark.asyncio
    async def test_subscription_consultoria(self):
        """'consultoria' plan_id should map to smartlic_consulting."""
        from services.digest_service import get_user_plan_tier

        mock_db = MagicMock()
        sub_result = _make_sb_result([{"plan_id": "consultoria_mensal"}])

        with patch("services.digest_service.sb_execute", return_value=sub_result):
            tier = await get_user_plan_tier("user-123", db=mock_db)

        assert tier == "smartlic_consulting"


# ============================================================================
# get_user_sectors() tests
# ============================================================================

class TestGetUserSectors:
    """Test sector resolution."""

    @pytest.mark.asyncio
    async def test_from_user_sector_affinity(self):
        from services.digest_service import get_user_sectors

        mock_db = MagicMock()
        aff_result = _make_sb_result([
            {"sector_id": "vestuario"},
            {"sector_id": "informatica"},
        ])

        with patch("services.digest_service.sb_execute", return_value=aff_result):
            sectors = await get_user_sectors("user-123", db=mock_db)

        assert sectors == ["vestuario", "informatica"]

    @pytest.mark.asyncio
    async def test_fallback_to_context_data(self):
        from services.digest_service import get_user_sectors

        mock_db = MagicMock()
        profile_result = _make_sb_result([{
            "context_data": {"setor_id": "engenharia"},
            "sector": None,
        }])

        with patch(
            "services.digest_service.sb_execute",
            side_effect=[_make_sb_result([]), profile_result],
        ):
            sectors = await get_user_sectors("user-123", db=mock_db)

        assert sectors == ["engenharia"]

    @pytest.mark.asyncio
    async def test_fallback_to_profile_sector(self):
        from services.digest_service import get_user_sectors

        mock_db = MagicMock()
        profile_result = _make_sb_result([{
            "context_data": None,
            "sector": "vestuario",
        }])

        with patch(
            "services.digest_service.sb_execute",
            side_effect=[Exception("affinity error"), profile_result],
        ):
            sectors = await get_user_sectors("user-123", db=mock_db)

        assert sectors == ["vestuario"]

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_sectors(self):
        from services.digest_service import get_user_sectors

        mock_db = MagicMock()
        profile_result = _make_sb_result([{
            "context_data": None,
            "sector": None,
        }])

        with patch(
            "services.digest_service.sb_execute",
            side_effect=[_make_sb_result([]), profile_result],
        ):
            sectors = await get_user_sectors("user-123", db=mock_db)

        assert sectors == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_db_error(self):
        from services.digest_service import get_user_sectors

        mock_db = MagicMock()

        with patch(
            "services.digest_service.sb_execute",
            side_effect=[Exception("affinity error"), Exception("profile error")],
        ):
            sectors = await get_user_sectors("user-123", db=mock_db)

        assert sectors == []


# ============================================================================
# get_user_frequency() tests
# ============================================================================

class TestGetUserFrequency:
    """Test frequency resolution."""

    @pytest.mark.asyncio
    async def test_returns_configured_frequency(self):
        from services.digest_service import get_user_frequency

        mock_db = MagicMock()
        freq_result = _make_sb_result([{"frequency": "weekly"}])

        with patch("services.digest_service.sb_execute", return_value=freq_result):
            freq = await get_user_frequency("user-123", db=mock_db)

        assert freq == "weekly"

    @pytest.mark.asyncio
    async def test_defaults_to_daily_on_error(self):
        from services.digest_service import get_user_frequency

        mock_db = MagicMock()

        with patch(
            "services.digest_service.sb_execute",
            side_effect=Exception("DB error"),
        ):
            freq = await get_user_frequency("user-123", db=mock_db)

        assert freq == "daily"

    @pytest.mark.asyncio
    async def test_defaults_to_daily_when_no_data(self):
        from services.digest_service import get_user_frequency

        mock_db = MagicMock()
        freq_result = _make_sb_result([])

        with patch("services.digest_service.sb_execute", return_value=freq_result):
            freq = await get_user_frequency("user-123", db=mock_db)

        assert freq == "daily"


# ============================================================================
# find_opportunities_for_sector() tests
# ============================================================================

class TestFindOpportunitiesForSector:
    """Test sector-based opportunity query."""

    @pytest.mark.asyncio
    async def test_returns_normalized_opportunities(self):
        from services.digest_service import find_opportunities_for_sector

        mock_db = MagicMock()
        mock_sector = MagicMock()
        mock_sector.keywords = ["uniforme", "fardamento"]

        with (
            patch("sectors.SECTORS", {"vestuario": mock_sector}),
            patch("datalake_query.query_datalake") as mock_query,
        ):
            mock_query.return_value = [
                {
                    "numeroControlePNCP": "12345",
                    "objetoCompra": "Uniformes escolares",
                    "nomeOrgao": "Prefeitura SP",
                    "valorTotalEstimado": 500000.0,
                    "uf": "SP",
                    "modalidadeNome": "Pregão Eletrônico",
                    "dataPublicacaoFormatted": "2026-06-01",
                    "linkSistemaOrigem": "https://pncp.gov.br/12345",
                    "viability_score": 0.85,
                },
                {
                    "numeroControlePNCP": "67890",
                    "objetoCompra": "Camisetas",
                    "nomeOrgao": "Prefeitura RJ",
                    "valorTotalEstimado": 200000.0,
                    "uf": "RJ",
                    "modalidadeNome": "Dispensa",
                    "dataPublicacaoFormatted": "2026-06-02",
                    "viability_score": 0.45,
                },
            ]

            results = await find_opportunities_for_sector(
                sector_id="vestuario",
                lookback_days=1,
                limit=5,
                db=mock_db,
            )

        assert len(results) == 2
        assert results[0]["id"] == "12345"
        assert results[0]["titulo"] == "Uniformes escolares"
        assert results[0]["orgao"] == "Prefeitura SP"
        assert results[0]["valor_estimado"] == 500000.0
        assert results[0]["uf"] == "SP"
        assert results[0]["viability_score"] == 0.85

    @pytest.mark.asyncio
    async def test_deduplicates_by_id(self):
        from services.digest_service import find_opportunities_for_sector

        mock_db = MagicMock()
        mock_sector = MagicMock()
        mock_sector.keywords = ["uniforme"]

        with (
            patch("sectors.SECTORS", {"vestuario": mock_sector}),
            patch("datalake_query.query_datalake") as mock_query,
        ):
            mock_query.return_value = [
                {"numeroControlePNCP": "12345", "objetoCompra": "Item A"},
                {"numeroControlePNCP": "12345", "objetoCompra": "Item A dup"},
                {"numeroControlePNCP": "67890", "objetoCompra": "Item B"},
            ]

            results = await find_opportunities_for_sector(
                sector_id="vestuario",
                lookback_days=1,
                limit=10,
                db=mock_db,
            )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_returns_empty_on_query_error(self):
        from services.digest_service import find_opportunities_for_sector

        mock_db = MagicMock()
        mock_sector = MagicMock()
        mock_sector.keywords = ["uniforme"]

        with (
            patch("sectors.SECTORS", {"vestuario": mock_sector}),
            patch("datalake_query.query_datalake") as mock_query,
        ):
            mock_query.side_effect = Exception("Datalake error")

            results = await find_opportunities_for_sector(
                sector_id="vestuario",
                lookback_days=1,
                limit=5,
                db=mock_db,
            )

        assert results == []

    @pytest.mark.asyncio
    async def test_sorts_by_viability_then_value(self):
        from services.digest_service import find_opportunities_for_sector

        mock_db = MagicMock()
        mock_sector = MagicMock()
        mock_sector.keywords = ["servico"]

        with (
            patch("sectors.SECTORS", {"servicos": mock_sector}),
            patch("datalake_query.query_datalake") as mock_query,
        ):
            mock_query.return_value = [
                {"numeroControlePNCP": "a", "objetoCompra": "A", "valorTotalEstimado": 100, "viability_score": 0.3},
                {"numeroControlePNCP": "b", "objetoCompra": "B", "valorTotalEstimado": 200, "viability_score": 0.9},
                {"numeroControlePNCP": "c", "objetoCompra": "C", "valorTotalEstimado": 300, "viability_score": 0.3},
            ]

            results = await find_opportunities_for_sector(
                sector_id="servicos",
                lookback_days=1,
                limit=5,
                db=mock_db,
            )

        assert len(results) == 3
        # Highest viability first, then by value
        assert results[0]["id"] == "b"
        assert results[1]["id"] == "c"  # 0.3 viability, 300 value
        assert results[2]["id"] == "a"  # 0.3 viability, 100 value

    @pytest.mark.asyncio
    async def test_respects_limit(self):
        from services.digest_service import find_opportunities_for_sector

        mock_db = MagicMock()
        mock_sector = MagicMock()
        mock_sector.keywords = ["item"]

        with (
            patch("sectors.SECTORS", {"setor": mock_sector}),
            patch("datalake_query.query_datalake") as mock_query,
        ):
            mock_query.return_value = [
                {"numeroControlePNCP": str(i), "objetoCompra": f"Item {i}"}
                for i in range(20)
            ]

            results = await find_opportunities_for_sector(
                sector_id="setor",
                lookback_days=1,
                limit=3,
                db=mock_db,
            )

        assert len(results) == 3


# ============================================================================
# TIER_LIMITS / FREQUENCY_WINDOWS tests
# ============================================================================

class TestDigestConstants:
    """Test DIGEST-002 constants."""

    def test_tier_limits_free_trial(self):
        from services.digest_service import TIER_LIMITS
        assert TIER_LIMITS.get("free_trial") == 5

    def test_tier_limits_pro(self):
        from services.digest_service import TIER_LIMITS
        assert TIER_LIMITS.get("smartlic_pro") == 20

    def test_tier_limits_consulting(self):
        from services.digest_service import TIER_LIMITS
        assert TIER_LIMITS.get("smartlic_consulting") == 20

    def test_tier_limits_consultoria(self):
        from services.digest_service import TIER_LIMITS
        assert TIER_LIMITS.get("consultoria") == 20

    def test_frequency_windows_daily(self):
        from services.digest_service import FREQUENCY_WINDOWS
        assert FREQUENCY_WINDOWS["daily"] == timedelta(days=1)

    def test_frequency_windows_twice_weekly(self):
        from services.digest_service import FREQUENCY_WINDOWS
        assert FREQUENCY_WINDOWS["twice_weekly"] == timedelta(days=3)

    def test_frequency_windows_weekly(self):
        from services.digest_service import FREQUENCY_WINDOWS
        assert FREQUENCY_WINDOWS["weekly"] == timedelta(days=7)


# ============================================================================
# build_personalized_digest() tests
# ============================================================================

class TestBuildPersonalizedDigest:
    """Test the main DIGEST-002 digest builder."""

    @pytest.mark.asyncio
    async def test_returns_expected_structure(self):
        from services.digest_service import build_personalized_digest

        mock_db = MagicMock()

        # Four sb_execute calls: subscription (empty) -> profile (free_trial), sectors, frequency
        with (
            patch(
                "services.digest_service.sb_execute",
                side_effect=[
                    _make_sb_result([]),  # subscription empty -> fallback to profile
                    _make_sb_result([{"plan_type": "free_trial"}]),  # profile
                    _make_sb_result([{"sector_id": "vestuario"}]),
                    _make_sb_result([{"frequency": "daily"}]),
                ],
            ),
            patch("sectors.SECTORS", {"vestuario": MagicMock(keywords=["uniforme"])}),
            patch("datalake_query.query_datalake") as mock_query,
        ):
            mock_query.return_value = [
                {"numeroControlePNCP": "1", "objetoCompra": "Uniformes",
                 "nomeOrgao": "Orgao", "uf": "SP"},
            ]

            result = await build_personalized_digest("user-123", db=mock_db)

        assert result["user_id"] == "user-123"
        assert result["frequency"] == "daily"
        assert result["tier"] == "free_trial"
        assert "vestuario" in result["sectors"]
        assert result["sectors"]["vestuario"]["count"] == 1
        assert result["has_content"] is True
        assert result["total_opportunities"] == 1
        assert "generated_at" in result
        assert result["sectors"]["vestuario"]["opportunities"][0]["titulo"] == "Uniformes"

    @pytest.mark.asyncio
    async def test_has_content_false_when_no_opportunities(self):
        from services.digest_service import build_personalized_digest

        mock_db = MagicMock()

        with (
            patch(
                "services.digest_service.sb_execute",
                side_effect=[
                    _make_sb_result([{"plan_id": "free_trial"}]),
                    _make_sb_result([{"sector_id": "vestuario"}]),
                    _make_sb_result([{"frequency": "daily"}]),
                ],
            ),
            patch("sectors.SECTORS", {"vestuario": MagicMock(keywords=["uniforme"])}),
            patch("datalake_query.query_datalake", return_value=[]),
        ):
            result = await build_personalized_digest("user-123", db=mock_db)

        assert result["has_content"] is False
        assert result["total_opportunities"] == 0
        assert result["sectors"]["vestuario"]["count"] == 0

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_sectors(self):
        from services.digest_service import build_personalized_digest

        mock_db = MagicMock()

        with (
            patch(
                "services.digest_service.sb_execute",
                side_effect=[
                    _make_sb_result([{"plan_id": "free_trial"}]),
                    _make_sb_result([]),  # empty user_sector_affinity
                    _make_sb_result([{"context_data": None, "sector": None}]),  # profile fallback
                ],
            ),
            patch("sectors.SECTORS", {}),
            patch("datalake_query.query_datalake"),
        ):
            result = await build_personalized_digest("user-123", db=mock_db)

        assert result["has_content"] is False
        assert result["total_opportunities"] == 0
        assert result["sectors"] == {}

    @pytest.mark.asyncio
    async def test_applies_tier_limit(self):
        """free_trial tier should limit to 5 per sector."""
        from services.digest_service import build_personalized_digest

        mock_db = MagicMock()
        many_items = [
            {"numeroControlePNCP": str(i), "objetoCompra": f"Item {i}"}
            for i in range(50)
        ]

        with (
            patch(
                "services.digest_service.sb_execute",
                side_effect=[
                    _make_sb_result([]),  # subscription empty
                    _make_sb_result([{"plan_type": "free_trial"}]),  # profile
                    _make_sb_result([{"sector_id": "vestuario"}]),
                    _make_sb_result([{"frequency": "daily"}]),
                ],
            ),
            patch("sectors.SECTORS", {"vestuario": MagicMock(keywords=["uniforme"])}),
            patch("datalake_query.query_datalake", return_value=many_items),
        ):
            result = await build_personalized_digest("user-123", db=mock_db)

        # free_trial limit = 5
        assert result["sectors"]["vestuario"]["count"] == 5
        assert result["total_opportunities"] == 5

    @pytest.mark.asyncio
    async def test_applies_pro_tier_limit(self):
        """smartlic_pro tier should limit to 20 per sector."""
        from services.digest_service import build_personalized_digest

        mock_db = MagicMock()
        many_items = [
            {"numeroControlePNCP": str(i), "objetoCompra": f"Item {i}"}
            for i in range(50)
        ]

        with (
            patch(
                "services.digest_service.sb_execute",
                side_effect=[
                    _make_sb_result([{"plan_id": "smartlic_pro_mensal"}]),
                    _make_sb_result([{"sector_id": "informatica"}]),
                    _make_sb_result([{"frequency": "daily"}]),
                ],
            ),
            patch("sectors.SECTORS", {"informatica": MagicMock(keywords=["software"])}),
            patch("datalake_query.query_datalake", return_value=many_items),
        ):
            result = await build_personalized_digest("user-123", db=mock_db)

        # smartlic_pro limit = 20
        assert result["sectors"]["informatica"]["count"] == 20
        assert result["total_opportunities"] == 20

    @pytest.mark.asyncio
    async def test_uses_frequency_lookback(self):
        """Weekly frequency should use 7-day lookback."""
        from services.digest_service import build_personalized_digest

        mock_db = MagicMock()

        with (
            patch(
                "services.digest_service.sb_execute",
                side_effect=[
                    _make_sb_result([{"plan_id": "free_trial"}]),
                    _make_sb_result([{"sector_id": "vestuario"}]),
                    _make_sb_result([{"frequency": "weekly"}]),
                ],
            ),
            patch("sectors.SECTORS", {"vestuario": MagicMock(keywords=["uniforme"])}),
            patch("datalake_query.query_datalake", return_value=[
                {"numeroControlePNCP": "1", "objetoCompra": "Uniformes"},
            ]),
        ):
            result = await build_personalized_digest("user-123", db=mock_db)

        assert result["frequency"] == "weekly"
        assert result["has_content"] is True

    @pytest.mark.asyncio
    async def test_multiple_sectors(self):
        from services.digest_service import build_personalized_digest

        mock_db = MagicMock()

        with (
            patch(
                "services.digest_service.sb_execute",
                side_effect=[
                    _make_sb_result([{"plan_id": "free_trial"}]),
                    _make_sb_result([
                        {"sector_id": "vestuario"},
                        {"sector_id": "informatica"},
                    ]),
                    _make_sb_result([{"frequency": "daily"}]),
                ],
            ),
            patch(
                "sectors.SECTORS",
                {
                    "vestuario": MagicMock(keywords=["uniforme"]),
                    "informatica": MagicMock(keywords=["software"]),
                },
            ),
            patch("datalake_query.query_datalake") as mock_query,
        ):
            def query_side_effect(*, sector_id=None, **kwargs):
                if sector_id == "vestuario":
                    return [{"numeroControlePNCP": "1", "objetoCompra": "Uniforme A"}]
                return [{"numeroControlePNCP": "2", "objetoCompra": "Software B"}]

            mock_query.side_effect = query_side_effect

            result = await build_personalized_digest("user-123", db=mock_db)

        assert len(result["sectors"]) == 2
        assert result["sectors"]["vestuario"]["count"] == 1
        assert result["sectors"]["informatica"]["count"] == 1
        assert result["total_opportunities"] == 2
