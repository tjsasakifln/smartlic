"""NETINT-005: Tests for network event collector and event sanitizer.

Tests the fire-and-forget collection service and the PII sanitization utility.

Coverage goals:
  - Sanitizer rejects CNPJ, email, UUID, IP from values
  - Sanitizer removes sensitive keys (user_id, email, etc.)
  - Sanitizer removes keys ending with 'id'
  - Non-string values preserved
  - Empty/None metadata returns {}
  - Opt-out user => event silently discarded
  - Opt-in user => event sent to RPC
  - Fire-and-forget does not block (asyncio timeout mock)
  - Prometheus counter is incremented
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.event_sanitizer import sanitize_metadata, has_pii


# ═══════════════════════════════════════════════════════════════════════════════
# Event Sanitizer Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSanitizeMetadata:
    """AC: sanitize_metadata removes or redacts PII from metadata dicts."""

    def test_removes_sensitive_keys(self):
        """Known sensitive keys are removed from the result."""
        metadata = {
            "user_id": "abc-123",
            "email": "user@example.com",
            "ip_address": "192.168.1.1",
            "cnpj": "12.345.678/0001-90",
            "uf": "SP",
            "setor": "saude",
        }
        result = sanitize_metadata(metadata)
        assert "user_id" not in result
        assert "email" not in result
        assert "ip_address" not in result
        assert "cnpj" not in result
        assert result["uf"] == "SP"
        assert result["setor"] == "saude"

    def test_removes_case_insensitive_keys(self):
        """Sensitive keys are matched case-insensitively."""
        metadata = {
            "UserId": "abc",
            "USER_ID": "def",
            "Email": "test@test.com",
            "CNPJ": "12345678000190",
        }
        result = sanitize_metadata(metadata)
        assert len(result) == 0

    def test_removes_id_suffix_keys(self):
        """Keys ending with 'id', 'Id', or 'ID' are removed."""
        metadata = {
            "session_id": "abc",
            "profileId": "def",
            "requestID": "ghi",
            "setor": "saude",
        }
        result = sanitize_metadata(metadata)
        assert "session_id" not in result
        assert "profileId" not in result
        assert "requestID" not in result
        assert result["setor"] == "saude"

    def test_redacts_cnpj_in_value(self):
        """CNPJ pattern in a string value is redacted."""
        metadata = {
            "descricao": "Contrato com a empresa 12.345.678/0001-90 para servicos",
            "setor": "saude",
        }
        result = sanitize_metadata(metadata)
        assert "[REDACTED]" in result["descricao"]
        assert "12.345.678/0001-90" not in result["descricao"]

    def test_redacts_cnpj_14_digits(self):
        """14 consecutive digits matching CNPJ are redacted."""
        metadata = {"obs": "CNPJ 12345678000190"}
        result = sanitize_metadata(metadata)
        assert "[REDACTED]" in result["obs"]
        assert "12345678000190" not in result["obs"]

    def test_redacts_email_in_value(self):
        """Email pattern in a string value is redacted."""
        metadata = {"contato": "Fale com joao.silva@empresa.com.br"}
        result = sanitize_metadata(metadata)
        assert "[REDACTED]" in result["contato"]
        assert "joao.silva@empresa.com.br" not in result["contato"]

    def test_redacts_uuid_in_value(self):
        """UUID v4 pattern in a string value is redacted."""
        metadata = {
            "ref": "Processo 550e8400-e29b-41d4-a716-446655440000 concluido",
        }
        result = sanitize_metadata(metadata)
        assert "[REDACTED]" in result["ref"]
        assert "550e8400" not in result["ref"]

    def test_redacts_ip_in_value(self):
        """IPv4 pattern in a string value is redacted."""
        metadata = {"origem": "Acesso de 192.168.0.1"}
        result = sanitize_metadata(metadata)
        assert "[REDACTED]" in result["origem"]
        assert "192.168.0.1" not in result["origem"]

    def test_preserves_non_string_values(self):
        """Non-string values (ints, bools, lists) are preserved."""
        metadata = {
            "contagem": 42,
            "ativo": True,
            "tags": ["saude", "SP"],
            "valor": 1500.50,
        }
        result = sanitize_metadata(metadata)
        assert result["contagem"] == 42
        assert result["ativo"] is True
        assert result["tags"] == ["saude", "SP"]
        assert result["valor"] == 1500.50

    def test_empty_metadata(self):
        """Empty dict returns empty dict."""
        assert sanitize_metadata({}) == {}

    def test_none_metadata(self):
        """None returns empty dict."""
        assert sanitize_metadata(None) == {}

    def test_camel_case_variants_removed(self):
        """CamelCase variants of known keys are removed."""
        metadata = {"userId": "abc", "customerId": "def"}
        result = sanitize_metadata(metadata)
        assert "userId" not in result
        assert "customerId" not in result

    def test_partial_redaction(self):
        """Only PII parts are redacted, rest of string preserved."""
        metadata = {"msg": "O usuario email@test.com acessou"}
        result = sanitize_metadata(metadata)
        assert "O usuario " in result["msg"]
        assert "acessou" in result["msg"]
        assert "[REDACTED]" in result["msg"]


class TestHasPII:
    """AC: has_pii detects PII patterns in strings."""

    def test_detects_cnpj(self):
        assert has_pii("12.345.678/0001-90") is True
        assert has_pii("12345678000190") is True

    def test_detects_email(self):
        assert has_pii("user@example.com") is True

    def test_detects_uuid(self):
        assert has_pii("550e8400-e29b-41d4-a716-446655440000") is True

    def test_detects_ip(self):
        assert has_pii("192.168.1.1") is True

    def test_clean_string(self):
        assert has_pii("saude") is False
        assert has_pii("Servicos de limpeza") is False
        assert has_pii("SP") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Network Collector Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCollectEvent:
    """AC: collect_event service — opt-in gating, sanitization, fire-and-forget."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        """Set up patches for each test."""
        self.mock_db = MagicMock()
        self.mock_rpc = MagicMock()
        self.mock_table = MagicMock()

        # get_db() returns mock_db
        patcher_db = patch("services.network_collector.get_db", return_value=self.mock_db)
        # sb_execute async mock
        patcher_exec = patch("services.network_collector.sb_execute", new_callable=AsyncMock)
        # sanitize_metadata passthrough
        patcher_sanitize = patch(
            "services.network_collector.sanitize_metadata",
            side_effect=lambda x: x,  # passthrough
        )
        # _increment_metric no-op
        patcher_metric = patch("services.network_collector._increment_metric")

        self.mock_get_db = patcher_db.start()
        self.mock_sb_execute = patcher_exec.start()
        self.mock_sanitize = patcher_sanitize.start()
        self.mock_increment = patcher_metric.start()

        # Setup db.rpc() chain
        self.mock_db.rpc.return_value = self.mock_rpc

        yield

        patcher_db.stop()
        patcher_exec.stop()
        patcher_sanitize.stop()
        patcher_metric.stop()

    def _mock_profile_and_rpc(self, allow_value: bool | None, rpc_side_effect=None):
        """Configure sb_execute for profile + optional RPC responses.

        sb_execute is called:
        1. First for profile lookup
        2. If opt-in, again for RPC call

        If rpc_side_effect is provided, it is used for the second call.
        """
        profile_result = MagicMock()
        profile_result.data = {"allow_network_analytics": allow_value}

        if rpc_side_effect is not None:
            self.mock_sb_execute.side_effect = [profile_result, rpc_side_effect]
        elif allow_value is True:
            # Default successful RPC response
            rpc_ok = MagicMock()
            rpc_ok.data = []
            self.mock_sb_execute.side_effect = [profile_result, rpc_ok]
        else:
            # Opt-out — only one call expected
            self.mock_sb_execute.side_effect = [profile_result]

    async def _collect(self, user_id="user-1", opt_in=True) -> bool:
        """Helper to call collect_event with consistent defaults."""
        if opt_in is not None:
            self._mock_profile_and_rpc(True if opt_in else False)
        else:
            # Profile lookup returns None data
            profile_result = MagicMock()
            profile_result.data = None
            self.mock_sb_execute.side_effect = [profile_result]

        from services.network_collector import collect_event

        return await collect_event(
            user_id=user_id,
            evento_tipo="sector_view",
            dimensao_tipo="setor",
            dimensao_valor="saude",
            metadados={"source": "observatorio"},
        )

    async def test_opt_in_collects_event(self):
        """User with allow_network_analytics=true -> RPC is called."""
        result = await self._collect(opt_in=True)
        assert result is True
        # Profile lookup + RPC call = 2 calls
        assert self.mock_sb_execute.call_count == 2

    async def test_opt_out_discards_event(self):
        """User with allow_network_analytics=false -> no RPC call."""
        result = await self._collect(opt_in=False)
        assert result is True  # Silent discard
        # Only profile check — 1 call
        assert self.mock_sb_execute.call_count == 1

    async def test_null_opt_in_discards_event(self):
        """User with allow_network_analytics=NULL -> discard."""
        result = await self._collect(opt_in=None)
        assert result is True  # Silent discard

    async def test_fire_and_forget_error_handling(self):
        """If RPC raises exception, collect_event returns False."""
        from services.network_collector import collect_event

        # Profile returns opt-in = True, RPC raises
        rpc_failure = Exception("RPC failed")
        self._mock_profile_and_rpc(True, rpc_side_effect=rpc_failure)

        result = await collect_event(
            user_id="user-1",
            evento_tipo="sector_view",
            dimensao_tipo="setor",
            dimensao_valor="saude",
        )
        # Event returns False on error
        assert result is False

    async def test_metadata_is_sanitized(self):
        """Metadata passes through sanitize_metadata before RPC call."""
        from services.network_collector import collect_event

        self._mock_profile_and_rpc(True)

        await collect_event(
            user_id="user-1",
            evento_tipo="search_query",
            dimensao_tipo="setor",
            dimensao_valor="saude",
            metadados={"ufs": ["SP", "RJ"]},
        )

        # Verify sanitize_metadata was called
        self.mock_sanitize.assert_called_once()

    async def test_metric_incremented_on_success(self):
        """Prometheus counter is incremented on successful collection."""
        from services.network_collector import collect_event

        self._mock_profile_and_rpc(True)

        with patch("services.network_collector._increment_metric") as mock_inc:
            await collect_event(
                user_id="user-1",
                evento_tipo="sector_view",
                dimensao_tipo="setor",
                dimensao_valor="saude",
            )
            mock_inc.assert_called_once_with("sector_view", status="success")
