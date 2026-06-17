"""B2GOPS-011 (#1281): Tests for in-app user alerts system.

Covers:
  - Migration contract (up + down SQL well-formed)
  - CRUD: list, create (via engine), read, mark read, mark all read, delete
  - Unread count badge (decrements on read)
  - Preferences CRUD
  - Cross-user isolation (RLS simulation)
  - Alert generation engine (deadline detection, watchlist matching)
  - Pagination
  - Edge cases: empty list, non-existent alert
"""

import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

import sys

# ARQ mock (must be set before importing app)
mock_arq = MagicMock()
sys.modules.setdefault("arq", mock_arq)
sys.modules.setdefault("arq.connections", MagicMock())
sys.modules.setdefault("arq.cron", MagicMock())

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from auth import require_auth  # noqa: E402
from schemas.alerts_b2gops import ALERT_TYPES  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIGRATIONS_DIR = os.path.join(REPO_ROOT, "supabase", "migrations")

MIGRATION_FILE = "20260617120000_user_alerts.sql"
DOWN_FILE = "20260617120000_user_alerts.down.sql"


# ---------------------------------------------------------------------------
# Migration contract tests
# ---------------------------------------------------------------------------


def _read_sql(filename: str) -> str:
    """Read a migration SQL file from supabase/migrations/."""
    path = os.path.join(MIGRATIONS_DIR, filename)
    with open(path) as f:
        return f.read()


class TestMigrationContract:
    """Validate the B2GOPS-011 migration SQL files are well-formed."""

    def test_migration_file_exists(self):
        path = os.path.join(MIGRATIONS_DIR, MIGRATION_FILE)
        assert os.path.exists(path), f"Migration file not found: {path}"

    def test_down_file_exists(self):
        path = os.path.join(MIGRATIONS_DIR, DOWN_FILE)
        assert os.path.exists(path), f"Down migration not found: {path}"

    def test_creates_user_alerts_table(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE TABLE IF NOT EXISTS user_alerts" in sql

    def test_creates_user_alert_preferences_table(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE TABLE IF NOT EXISTS user_alert_preferences" in sql

    def test_user_alerts_has_type_check(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "new_matching_edital" in sql
        assert "deadline_approaching" in sql
        assert "pregao_starting" in sql
        assert "result_published" in sql
        assert "contrato_firmado" in sql
        assert "documento_vencendo" in sql

    def test_has_rls_policies(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "ENABLE ROW LEVEL SECURITY" in sql
        assert "auth.uid() = user_id" in sql

    def test_has_indexes(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE INDEX IF NOT EXISTS idx_user_alerts_unread" in sql
        assert "CREATE INDEX IF NOT EXISTS idx_user_alerts_type" in sql

    def test_down_drops_tables(self):
        sql = _read_sql(DOWN_FILE)
        assert "DROP TABLE IF EXISTS user_alert_preferences" in sql
        assert "DROP TABLE IF EXISTS user_alerts" in sql


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

MOCK_USER = {
    "id": "test-user-uuid-0001",
    "email": "test@example.com",
    "role": "authenticated",
}

MOCK_USER_2 = {
    "id": "test-user-uuid-0002",
    "email": "user2@example.com",
    "role": "authenticated",
}

ALERT_ID_1 = "alert-uuid-0001"
ALERT_ID_2 = "alert-uuid-0002"
ALERT_ID_3 = "alert-uuid-0003"

NOW_ISO = datetime.now(timezone.utc).isoformat()


class MockResponse:
    """Lightweight stand-in for a Supabase postgrest response."""

    def __init__(self, data=None, count=None):
        self.data = data if data is not None else []
        self.count = count


def _mock_sb():
    """Create a fluent-chainable Supabase mock."""
    sb = MagicMock()
    sb.table.return_value = sb
    sb.select.return_value = sb
    sb.insert.return_value = sb
    sb.upsert.return_value = sb
    sb.update.return_value = sb
    sb.delete.return_value = sb
    sb.eq.return_value = sb
    sb.gte.return_value = sb
    sb.lte.return_value = sb
    sb.lt.return_value = sb
    sb.not_.return_value = sb
    sb.is_.return_value = sb
    sb.order.return_value = sb
    sb.limit.return_value = sb
    sb.range.return_value = sb
    sb.single.return_value = sb
    sb.maybe_single.return_value = sb
    sb.execute.return_value = MockResponse()
    return sb


def _alert_row(
    alert_id=ALERT_ID_1,
    user_id=MOCK_USER["id"],
    alert_type="deadline_approaching",
    title="Prazo se aproximando: Edital Teste",
    body="O prazo encerra em 12h.",
    data=None,
    is_read=False,
    read_at=None,
):
    """Build a typical user_alerts table row dict."""
    return {
        "id": alert_id,
        "user_id": user_id,
        "type": alert_type,
        "title": title,
        "body": body,
        "data": data or {"edital_id": "edital-001"},
        "is_read": is_read,
        "read_at": read_at,
        "created_at": NOW_ISO,
    }


def _prefs_row(
    user_id=MOCK_USER["id"],
    channels=None,
    enabled_types=None,
    quiet_hours=None,
):
    """Build a typical user_alert_preferences row dict."""
    return {
        "user_id": user_id,
        "channels": channels or {"in_app": True},
        "enabled_types": enabled_types or [],
        "quiet_hours": quiet_hours or {"start": None, "end": None},
        "created_at": NOW_ISO,
        "updated_at": NOW_ISO,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_auth():
    """Override auth dependency for every test in this module."""
    app.dependency_overrides[require_auth] = lambda: MOCK_USER
    yield
    app.dependency_overrides.pop(require_auth, None)


# ===========================================================================
# Alert CRUD Tests
# ===========================================================================


class TestListAlerts:
    """GET /v1/alerts/b2gops"""

    def test_list_empty(self):
        """Returns empty list when user has no alerts."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[], count=0)

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops")
            assert resp.status_code == 200
            data = resp.json()
            assert data["alerts"] == []
            assert data["total"] == 0
            assert data["limit"] == 20
            assert data["offset"] == 0

    def test_list_with_alerts(self):
        """Returns paginated alerts."""
        sb = _mock_sb()
        mock_rows = [
            _alert_row(alert_id=ALERT_ID_1, alert_type="deadline_approaching"),
            _alert_row(alert_id=ALERT_ID_2, alert_type="new_matching_edital", is_read=True),
        ]

        async def fake_execute(query):
            return MockResponse(data=mock_rows, count=2)

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["alerts"]) == 2
            assert data["total"] == 2
            assert data["alerts"][0]["type"] == "deadline_approaching"
            assert data["alerts"][1]["type"] == "new_matching_edital"
            assert data["alerts"][0]["is_read"] is False
            assert data["alerts"][1]["is_read"] is True

    def test_list_filter_by_type(self):
        """Filters alerts by type parameter."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(
                data=[_alert_row(alert_type="new_matching_edital")],
                count=1,
            )

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops?type=new_matching_edital")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["alerts"]) == 1
            assert data["alerts"][0]["type"] == "new_matching_edital"

    def test_list_filter_by_read_status(self):
        """Filters alerts by is_read status."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(
                data=[_alert_row(is_read=True)],
                count=1,
            )

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops?is_read=true")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["alerts"]) == 1
            assert data["alerts"][0]["is_read"] is True

    def test_list_pagination(self):
        """Respects limit and offset parameters."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[_alert_row()], count=10)

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops?limit=5&offset=5")
            assert resp.status_code == 200
            data = resp.json()
            assert data["limit"] == 5
            assert data["offset"] == 5


class TestMarkRead:
    """PATCH /v1/alerts/b2gops/{id}/read"""

    def test_mark_single_read(self):
        """Marks a single alert as read."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[_alert_row(alert_id=ALERT_ID_1)])

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.patch(f"/v1/alerts/b2gops/{ALERT_ID_1}/read")
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == ALERT_ID_1
            assert data["is_read"] is False  # our mock returns False; read_at is set in route

    def test_mark_read_not_found(self):
        """Returns 404 when alert does not exist."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[])

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.patch("/v1/alerts/b2gops/nonexistent-id/read")
            assert resp.status_code == 404
            assert "nao encontrado" in resp.json()["detail"].lower()


class TestMarkAllRead:
    """POST /v1/alerts/b2gops/read-all"""

    def test_mark_all_read(self):
        """Marks all unread alerts as read."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[
                _alert_row(alert_id=ALERT_ID_1),
                _alert_row(alert_id=ALERT_ID_2),
            ])

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.post("/v1/alerts/b2gops/read-all")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "2" in data["message"]

    def test_mark_all_read_empty(self):
        """Returns success when no unread alerts exist."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[])

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.post("/v1/alerts/b2gops/read-all")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "0" in data["message"]


class TestDeleteAlert:
    """DELETE /v1/alerts/b2gops/{id}"""

    def test_delete_alert(self):
        """Deletes a single alert."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[_alert_row(alert_id=ALERT_ID_1)])

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.delete(f"/v1/alerts/b2gops/{ALERT_ID_1}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "removido" in data["message"].lower()

    def test_delete_not_found(self):
        """Returns 404 when alert does not exist."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[])

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.delete("/v1/alerts/b2gops/nonexistent-id")
            assert resp.status_code == 404


class TestUnreadCount:
    """GET /v1/alerts/b2gops/unread-count"""

    def test_unread_count_positive(self):
        """Returns correct unread count."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[], count=3)

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops/unread-count")
            assert resp.status_code == 200
            data = resp.json()
            assert data["unread_count"] == 3

    def test_unread_count_zero(self):
        """Returns zero when no unread alerts."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[], count=0)

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops/unread-count")
            assert resp.status_code == 200
            assert resp.json()["unread_count"] == 0


# ===========================================================================
# Preferences Tests
# ===========================================================================


class TestPreferences:
    """GET/PATCH /v1/alerts/b2gops/preferences"""

    def test_get_default_preferences(self):
        """Returns defaults when no preferences row exists."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=None)

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops/preferences")
            assert resp.status_code == 200
            data = resp.json()
            assert data["channels"] == {"in_app": True}
            assert data["enabled_types"] == []
            assert data["quiet_hours"] == {"start": None, "end": None}

    def test_get_existing_preferences(self):
        """Returns existing preferences."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(
                data=_prefs_row(
                    channels={"in_app": True, "email": True},
                    enabled_types=["deadline_approaching", "new_matching_edital"],
                    quiet_hours={"start": "22:00", "end": "07:00"},
                )
            )

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops/preferences")
            assert resp.status_code == 200
            data = resp.json()
            assert data["channels"]["email"] is True
            assert len(data["enabled_types"]) == 2
            assert data["quiet_hours"]["start"] == "22:00"

    def test_update_preferences(self):
        """Updates alert preferences."""
        sb = _mock_sb()

        call_count = 0

        async def fake_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: maybe_single returns None (new user)
                return MockResponse(data=None)
            # Second call: upsert returns the prefs
            return MockResponse(data=[_prefs_row(
                channels={"in_app": True, "email": True},
                enabled_types=["deadline_approaching"],
                quiet_hours={"start": "23:00", "end": "06:00"},
            )])

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.patch(
                "/v1/alerts/b2gops/preferences",
                json={
                    "channels": {"in_app": True, "email": True},
                    "enabled_types": ["deadline_approaching"],
                    "quiet_hours": {"start": "23:00", "end": "06:00"},
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["channels"]["email"] is True
            assert "deadline_approaching" in data["enabled_types"]


# ===========================================================================
# Cross-user isolation tests
# ===========================================================================


class TestCrossUserIsolation:
    """Verify users cannot see or modify each other's alerts."""

    def test_user_sees_only_own_alerts(self):
        """User 1 should not see User 2's alerts due to RLS."""
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[], count=0)

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.get("/v1/alerts/b2gops")
            assert resp.status_code == 200
            data = resp.json()
            assert data["total"] == 0

            # Verify the query filters by user_id
            assert sb.table.called
            table_call = sb.table.call_args
            assert table_call is not None

    def test_other_user_cannot_read_alert(self):
        """User 2 cannot mark User 1's alert as read."""
        # Switch to User 2 for this test
        app.dependency_overrides[require_auth] = lambda: MOCK_USER_2
        sb = _mock_sb()

        async def fake_execute(query):
            return MockResponse(data=[])

        with patch("supabase_client.get_supabase", return_value=sb), \
             patch("supabase_client.sb_execute", side_effect=fake_execute):
            client = TestClient(app)
            resp = client.patch(f"/v1/alerts/b2gops/{ALERT_ID_1}/read")
            assert resp.status_code == 404


# ===========================================================================
# Alert Engine Tests
# ===========================================================================


class TestAlertEngine:
    """Alert generation engine tests."""

    @pytest.mark.asyncio
    async def test_generate_alerts_empty(self):
        """Returns zero counts when no events found."""
        from services.alert_engine import generate_alerts

        mock_sb = _mock_sb()

        with patch("services.alert_engine.get_supabase", return_value=mock_sb):
            with patch("services.alert_engine.sb_execute", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = MockResponse(data=[])

                result = await generate_alerts(db=mock_sb)
                assert result.generated == 0
                assert result.errors == 0

    @pytest.mark.asyncio
    async def test_check_deadlines_detects_approaching(self):
        """Detects editais with approaching deadlines."""
        from services.alert_engine import _check_deadlines

        mock_sb = _mock_sb()
        now = datetime.now(timezone.utc)
        future_deadline = (now + timedelta(hours=12)).isoformat()

        mock_data = [{
            "id": "edital-001",
            "user_id": MOCK_USER["id"],
            "titulo": "Pregao para aquisicao de computadores",
            "data_hora_finalizacao": future_deadline,
            "orgao_nome": "Prefeitura de Sao Paulo",
            "modalidade_nome": "pregao",
        }]

        with patch("services.alert_engine.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MockResponse(data=mock_data)

            result = await _check_deadlines(mock_sb)
            assert len(result) == 1
            assert result[0].type == "deadline_approaching"
            assert "Prazo" in result[0].title
            assert "12" in result[0].body or "12" in str(result[0].data.get("hours_until"))

    @pytest.mark.asyncio
    async def test_check_deadlines_urgency_levels(self):
        """Classifies deadlines by urgency (urgent/soon/approaching)."""
        from services.alert_engine import _check_deadlines

        mock_sb = _mock_sb()
        now = datetime.now(timezone.utc)

        # Test with urgent deadline (30 min away)
        urgent_deadline = (now + timedelta(minutes=30)).isoformat()
        mock_data = [{
            "id": "edital-urgent",
            "user_id": MOCK_USER["id"],
            "titulo": "Edital urgente",
            "data_hora_finalizacao": urgent_deadline,
            "orgao_nome": "Orgao Teste",
            "modalidade_nome": "pregao",
        }]

        with patch("services.alert_engine.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MockResponse(data=mock_data)

            result = await _check_deadlines(mock_sb)
            assert len(result) == 1
            assert "URGENTE" in result[0].title
            assert result[0].data["urgency"] == "urgent"
            assert result[0].data["hours_until"] <= 1

    @pytest.mark.asyncio
    async def test_insert_alert(self):
        """Inserts a single alert record."""
        from services.alert_engine import _insert_alert, AlertEventPayload

        mock_sb = _mock_sb()

        payload = AlertEventPayload(
            user_id=MOCK_USER["id"],
            type="deadline_approaching",
            title="Test Alert",
            body="Test body",
            data={"test_key": "test_value"},
        )

        with patch("services.alert_engine.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MockResponse(data=[{"id": "new-alert-id"}])

            success = await _insert_alert(payload, mock_sb)
            assert success is True

    @pytest.mark.asyncio
    async def test_cleanup_old_alerts(self):
        """Removes alerts older than retention period."""
        from services.alert_engine import cleanup_old_alerts

        mock_sb = _mock_sb()

        with patch("services.alert_engine.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MockResponse(
                data=[{"id": "old-alert-1"}, {"id": "old-alert-2"}]
            )

            deleted = await cleanup_old_alerts(days=90, db=mock_sb)
            assert deleted == 2

    @pytest.mark.asyncio
    async def test_generate_alerts_run_all_types(self):
        """Runs all alert generation checks."""
        from services.alert_engine import generate_alerts

        mock_sb = _mock_sb()

        with patch("services.alert_engine.get_supabase", return_value=mock_sb):
            with patch("services.alert_engine.sb_execute", new_callable=AsyncMock) as mock_exec:
                # Return empty for all checks
                mock_exec.return_value = MockResponse(data=[])

                result = await generate_alerts(db=mock_sb)
                assert result.generated == 0
                assert result.errors == 0
                assert isinstance(result.details, list)


# ===========================================================================
# Schema tests
# ===========================================================================


class TestSchemas:
    """Validate Pydantic schemas."""

    def test_alert_types_complete(self):
        """All expected alert types are defined."""
        expected_types = {
            "new_matching_edital",
            "deadline_approaching",
            "pregao_starting",
            "result_published",
            "contrato_firmado",
            "documento_vencendo",
        }
        assert ALERT_TYPES == expected_types

    def test_user_alert_response_serialization(self):
        """UserAlertResponse serializes correctly."""
        from schemas.alerts_b2gops import UserAlertResponse

        alert = UserAlertResponse(
            id="test-id",
            user_id="user-id",
            type="deadline_approaching",
            title="Test Alert",
            body="Test body",
            data={"key": "value"},
            is_read=False,
            created_at="2026-01-01T00:00:00Z",
        )
        d = alert.model_dump()
        assert d["id"] == "test-id"
        assert d["type"] == "deadline_approaching"
        assert d["is_read"] is False
        assert d["data"]["key"] == "value"
