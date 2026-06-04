"""Tests for GTM-RESILIENCE-D05: User Feedback Loop (AC11).

Tests:
1. POST /v1/feedback creates record
2. Duplicate feedback upserts
3. Rate limit enforced
4. Invalid search_id returns 422
5. Unauthenticated returns 401/403
6. GET /v1/admin/feedback/patterns returns breakdown
7. Suggestion generated for keyword in >5 FPs
8. DELETE /v1/feedback/{id} removes record
"""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from auth import require_auth
from admin import require_admin


# --- Fixtures ---

@pytest.fixture
def test_user():
    return {"id": "user-feedback-001", "sub": "user-feedback-001", "email": "test@example.com"}


@pytest.fixture
def admin_user():
    return {"id": "admin-feedback-001", "sub": "admin-feedback-001", "email": "admin@test.com", "role": "admin"}


@pytest.fixture
def client_as_user(test_user):
    app.dependency_overrides[require_auth] = lambda: test_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def client_as_admin(admin_user):
    app.dependency_overrides[require_auth] = lambda: admin_user
    app.dependency_overrides[require_admin] = lambda: admin_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def client_no_auth():
    app.dependency_overrides.pop(require_auth, None)
    return TestClient(app)


def _mock_supabase_table(table_name):
    """Create a fluent mock for Supabase table operations."""
    mock = MagicMock()
    mock.select.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.delete.return_value = mock
    mock.eq.return_value = mock
    mock.gte.return_value = mock
    return mock


# --- AC11 Test 1: POST /v1/feedback creates record ---

@patch("routes.feedback.get_feature_flag", return_value=True)
def test_submit_feedback_creates_record(mock_ff, client_as_user):
    """AC11-1: POST /v1/feedback creates feedback record in Supabase."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table

    # No existing feedback (for rate limit check and dedup check)
    mock_table.execute.return_value = MagicMock(data=[], count=0)

    # Insert response
    mock_insert = MagicMock()
    mock_insert.execute.return_value = MagicMock(data=[{"id": "fb-001"}])
    mock_table.insert.return_value = mock_insert

    mock_db.table.return_value = mock_table

    with patch("supabase_client.get_supabase", return_value=mock_db):
        resp = client_as_user.post("/v1/feedback", json={
            "search_id": "aaaaaaaa-bbbb-4ccc-9ddd-eeeeeeeeeeee",
            "bid_id": "bid-123",
            "user_verdict": "correct",
            "setor_id": "vestuario",
        })

    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "fb-001"
    assert data["updated"] is False
    assert "received_at" in data


# --- AC11 Test 2: Duplicate feedback upserts ---

@patch("routes.feedback.get_feature_flag", return_value=True)
def test_duplicate_feedback_upserts(mock_ff, client_as_user):
    """AC11-2: Second feedback for same search+bid updates existing record."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table

    # Rate limit check: 0 feedbacks in last hour
    # Dedup check: existing record found
    call_count = [0]
    def mock_execute():
        call_count[0] += 1
        if call_count[0] == 1:
            return MagicMock(data=[], count=0)  # rate limit
        return MagicMock(data=[{"id": "fb-existing-001"}])  # dedup

    mock_table.execute = mock_execute

    # Update mock
    mock_update = MagicMock()
    mock_update.eq.return_value = mock_update
    mock_update.execute.return_value = MagicMock(data=[{"id": "fb-existing-001"}])
    mock_table.update.return_value = mock_update

    mock_db.table.return_value = mock_table

    with patch("supabase_client.get_supabase", return_value=mock_db):
        resp = client_as_user.post("/v1/feedback", json={
            "search_id": "aaaaaaaa-bbbb-4ccc-9ddd-eeeeeeeeeeee",
            "bid_id": "bid-123",
            "user_verdict": "false_positive",
            "category": "wrong_sector",
        })

    assert resp.status_code == 201
    data = resp.json()
    assert data["updated"] is True


# --- AC11 Test 3: Rate limit ---

@patch("routes.feedback.get_feature_flag", return_value=True)
def test_rate_limit_enforced(mock_ff, client_as_user):
    """AC11-3: 50+ feedbacks/hour triggers rate limit."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[], count=50)  # at limit
    mock_db.table.return_value = mock_table

    with patch("supabase_client.get_supabase", return_value=mock_db):
        resp = client_as_user.post("/v1/feedback", json={
            "search_id": "aaaaaaaa-bbbb-4ccc-9ddd-eeeeeeeeeeee",
            "bid_id": "bid-123",
            "user_verdict": "correct",
        })

    assert resp.status_code == 429
    assert "Rate limit" in resp.json()["detail"]


# --- AC11 Test 4: Invalid body returns 422 ---

@patch("routes.feedback.get_feature_flag", return_value=True)
def test_invalid_body_returns_422(mock_ff, client_as_user):
    """AC11-4: Missing required fields returns 422."""
    resp = client_as_user.post("/v1/feedback", json={
        "bid_id": "bid-123",
        # missing search_id and user_verdict
    })
    assert resp.status_code == 422


# --- AC11 Test 5: Unauthenticated returns 401/403 ---

def test_unauthenticated_returns_error(client_no_auth):
    """AC11-5: No auth token returns 401 or 403."""
    resp = client_no_auth.post("/v1/feedback", json={
        "search_id": "aaaaaaaa-bbbb-4ccc-9ddd-eeeeeeeeeeee",
        "bid_id": "bid-123",
        "user_verdict": "correct",
    })
    assert resp.status_code in (401, 403)


# --- AC11 Test 6: GET /v1/admin/feedback/patterns ---

@patch("routes.feedback.get_feature_flag", return_value=True)
def test_admin_patterns_returns_breakdown(mock_ff, client_as_admin):
    """AC11-6: Admin patterns endpoint returns correct breakdown."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[
        {"user_verdict": "correct", "category": None, "bid_objeto": "uniforme escolar", "setor_id": "vestuario"},
        {"user_verdict": "correct", "category": None, "bid_objeto": "jaleco branco", "setor_id": "vestuario"},
        {"user_verdict": "false_positive", "category": "wrong_sector", "bid_objeto": "uniformizacao fachada", "setor_id": "vestuario"},
    ])
    mock_db.table.return_value = mock_table

    with patch("supabase_client.get_supabase", return_value=mock_db):
        resp = client_as_admin.get("/v1/admin/feedback/patterns?setor_id=vestuario&days=30")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_feedbacks"] == 3
    assert data["breakdown"]["correct"] == 2
    assert data["breakdown"]["false_positive"] == 1
    assert data["precision_estimate"] == 0.67
    assert data["fp_categories"]["wrong_sector"] == 1


# --- AC11 Test 7: Keyword suggestion when >5 FPs ---

def test_keyword_suggestion_for_frequent_fps():
    """AC11-7: Analyzer suggests exclusion when keyword appears in >5 FPs."""
    from feedback_analyzer import analyze_feedback_patterns

    feedbacks = []
    # 6 FPs with "uniformizacao" in bid_objeto
    for i in range(6):
        feedbacks.append({
            "user_verdict": "false_positive",
            "category": "wrong_sector",
            "bid_objeto": f"uniformizacao de fachada item {i}",
        })
    # 1 correct with different text
    feedbacks.append({
        "user_verdict": "correct",
        "category": None,
        "bid_objeto": "uniforme escolar completo",
    })

    result = analyze_feedback_patterns(feedbacks, sector_keywords=["uniformizacao", "uniforme"])
    assert result["total_feedbacks"] == 7
    assert len(result["top_fp_keywords"]) >= 1
    assert result["top_fp_keywords"][0]["keyword"] == "uniformizacao"
    assert result["top_fp_keywords"][0]["count"] == 6


# --- AC11 Test 8: DELETE /v1/feedback/{id} ---

@patch("routes.feedback.get_feature_flag", return_value=True)
def test_delete_feedback(mock_ff, client_as_user, test_user):
    """AC11-8: DELETE removes user's own feedback."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[{
        "id": "fb-del-001",
        "user_id": test_user["id"],
    }])
    mock_table.delete.return_value = mock_table
    mock_db.table.return_value = mock_table

    with patch("supabase_client.get_supabase", return_value=mock_db):
        resp = client_as_user.delete("/v1/feedback/fb-del-001")

    assert resp.status_code == 200
    assert resp.json()["deleted"] is True


# --- Feature flag disabled ---

@patch("routes.feedback.get_feature_flag", return_value=False)
def test_feedback_disabled_returns_503(mock_ff, client_as_user):
    """AC10: When USER_FEEDBACK_ENABLED=false, endpoint returns 503."""
    resp = client_as_user.post("/v1/feedback", json={
        "search_id": "aaaaaaaa-bbbb-4ccc-9ddd-eeeeeeeeeeee",
        "bid_id": "bid-123",
        "user_verdict": "correct",
    })
    assert resp.status_code == 503
    assert "disabled" in resp.json()["detail"].lower()


# --- Analyzer edge cases ---

def test_analyzer_empty_feedbacks():
    """Edge case: empty feedback list returns safe defaults."""
    from feedback_analyzer import analyze_feedback_patterns
    result = analyze_feedback_patterns([])
    assert result["total_feedbacks"] == 0
    assert result["precision_estimate"] is None
    assert result["suggested_exclusions"] == []


def test_analyzer_bigram_suggestions():
    """Edge case: bigram suggestions for exclusion."""
    from feedback_analyzer import analyze_feedback_patterns

    feedbacks = []
    # 4 FPs with same bigram
    for i in range(4):
        feedbacks.append({
            "user_verdict": "false_positive",
            "bid_objeto": "padronizacao visual de identidade",
        })
    # 2 corrects without that bigram
    for i in range(2):
        feedbacks.append({
            "user_verdict": "correct",
            "bid_objeto": "uniforme escolar",
        })

    result = analyze_feedback_patterns(feedbacks)
    assert "padronizacao visual" in result["suggested_exclusions"]


# ============================================================================
# FEEDBACK-002: User Sector Affinity Tests
# ============================================================================


@pytest.mark.asyncio
async def test_affinity_correct_increases_by_0_1():
    """FEEDBACK-002 AC1: correct feedback adds +0.1 (capped at 1.0)."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"affinity_score": 0.5}])
    mock_select.eq.return_value = mock_select
    mock_table.select.return_value = mock_select
    mock_upsert = MagicMock()
    mock_upsert.execute.return_value = MagicMock(data=[])
    mock_table.upsert.return_value = mock_upsert
    mock_db.table.return_value = mock_table
    from feedback_affinity import update_affinity
    result = await update_affinity(mock_db, "user-001", "vestuario", "correct")
    assert result == 0.6
    assert mock_table.upsert.call_args[0][0]["affinity_score"] == 0.6


@pytest.mark.asyncio
async def test_affinity_correct_caps_at_1_0():
    """FEEDBACK-002 AC1: correct feedback caps at 1.0."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"affinity_score": 0.95}])
    mock_select.eq.return_value = mock_select
    mock_table.select.return_value = mock_select
    mock_upsert = MagicMock()
    mock_upsert.execute.return_value = MagicMock(data=[])
    mock_table.upsert.return_value = mock_upsert
    mock_db.table.return_value = mock_table
    from feedback_affinity import update_affinity
    result = await update_affinity(mock_db, "user-001", "vestuario", "correct")
    assert result == 1.0
    assert mock_table.upsert.call_args[0][0]["affinity_score"] == 1.0


@pytest.mark.asyncio
async def test_affinity_false_positive_decreases_by_0_2():
    """FEEDBACK-002 AC2: false_positive feedback subtracts -0.2."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"affinity_score": 0.5}])
    mock_select.eq.return_value = mock_select
    mock_table.select.return_value = mock_select
    mock_upsert = MagicMock()
    mock_upsert.execute.return_value = MagicMock(data=[])
    mock_table.upsert.return_value = mock_upsert
    mock_db.table.return_value = mock_table
    from feedback_affinity import update_affinity
    result = await update_affinity(mock_db, "user-001", "vestuario", "false_positive")
    assert result == 0.3
    assert mock_table.upsert.call_args[0][0]["affinity_score"] == 0.3


@pytest.mark.asyncio
async def test_affinity_false_positive_floors_at_0_0():
    """FEEDBACK-002 AC2: false_positive feedback floors at 0.0."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"affinity_score": 0.1}])
    mock_select.eq.return_value = mock_select
    mock_table.select.return_value = mock_select
    mock_upsert = MagicMock()
    mock_upsert.execute.return_value = MagicMock(data=[])
    mock_table.upsert.return_value = mock_upsert
    mock_db.table.return_value = mock_table
    from feedback_affinity import update_affinity
    result = await update_affinity(mock_db, "user-001", "vestuario", "false_positive")
    assert result == 0.0
    assert mock_table.upsert.call_args[0][0]["affinity_score"] == 0.0


@pytest.mark.asyncio
async def test_affinity_false_negative_increases_by_0_05():
    """FEEDBACK-002 AC3: false_negative feedback adds +0.05."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"affinity_score": 0.3}])
    mock_select.eq.return_value = mock_select
    mock_table.select.return_value = mock_select
    mock_upsert = MagicMock()
    mock_upsert.execute.return_value = MagicMock(data=[])
    mock_table.upsert.return_value = mock_upsert
    mock_db.table.return_value = mock_table
    from feedback_affinity import update_affinity
    result = await update_affinity(mock_db, "user-001", "vestuario", "false_negative")
    assert result == 0.35
    assert mock_table.upsert.call_args[0][0]["affinity_score"] == 0.35


@pytest.mark.asyncio
async def test_affinity_cold_start_returns_0_5():
    """FEEDBACK-002 AC5: cold start (no row) defaults to 0.5 (neutral)."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[])
    mock_select.eq.return_value = mock_select
    mock_table.select.return_value = mock_select
    mock_upsert = MagicMock()
    mock_upsert.execute.return_value = MagicMock(data=[])
    mock_table.upsert.return_value = mock_upsert
    mock_db.table.return_value = mock_table
    from feedback_affinity import update_affinity
    result = await update_affinity(mock_db, "user-new", "saude", "correct")
    assert result == 0.6
    assert mock_table.upsert.call_args[0][0]["affinity_score"] == 0.6


@pytest.mark.asyncio
async def test_affinity_unknown_feedback_type_returns_none():
    """FEEDBACK-002: unknown feedback_type returns None."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_select = MagicMock()
    mock_select.execute.return_value = MagicMock(data=[{"affinity_score": 0.5}])
    mock_select.eq.return_value = mock_select
    mock_table.select.return_value = mock_select
    mock_db.table.return_value = mock_table
    from feedback_affinity import update_affinity
    result = await update_affinity(mock_db, "user-001", "vestuario", "unknown_type")
    assert result is None
    mock_table.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_affinity_no_sector_id_skips_update():
    """FEEDBACK-002: empty sector_id skips affinity update."""
    mock_db = MagicMock()
    from feedback_affinity import update_affinity
    result = await update_affinity(mock_db, "user-001", "", "correct")
    assert result is None
    mock_db.table.assert_not_called()


@pytest.mark.asyncio
async def test_affinity_unknown_sector_skips_update():
    """FEEDBACK-002: 'unknown' sector_id skips affinity update."""
    mock_db = MagicMock()
    from feedback_affinity import update_affinity
    result = await update_affinity(mock_db, "user-001", "unknown", "correct")
    assert result is None
    mock_db.table.assert_not_called()


@pytest.mark.asyncio
async def test_affinity_decay_applies_0_99():
    """FEEDBACK-002 AC4: decay_all_affinities calls RPC."""
    mock_db = MagicMock()
    mock_rpc = MagicMock()
    mock_rpc.execute.return_value = MagicMock(data=42)
    mock_db.rpc.return_value = mock_rpc
    from feedback_affinity import decay_all_affinities
    result = await decay_all_affinities(mock_db)
    assert result == 42
    mock_db.rpc.assert_called_once_with("decay_user_sector_affinities")


@pytest.mark.asyncio
async def test_affinity_decay_graceful_on_error():
    """FEEDBACK-002 AC4: decay_all_affinities handles gracefully."""
    mock_db = MagicMock()
    mock_rpc = MagicMock()
    mock_rpc.execute.side_effect = RuntimeError("RPC not found")
    mock_db.rpc.return_value = mock_rpc
    from feedback_affinity import decay_all_affinities
    result = await decay_all_affinities(mock_db)
    assert result is None
    mock_db.rpc.assert_called_once_with("decay_user_sector_affinities")


@patch("routes.feedback.get_feature_flag", return_value=True)
def test_submit_feedback_still_works_with_affinity(mock_ff, client_as_user):
    """FEEDBACK-002 AC6: feedback endpoint works with affinity (zero regressao)."""
    mock_db = MagicMock()
    def mock_table_factory(table_name):
        mt = MagicMock()
        mt.select.return_value = mt
        mt.eq.return_value = mt
        mt.gte.return_value = mt
        mt.execute.return_value = MagicMock(data=[], count=0)
        mi = MagicMock()
        mi.execute.return_value = MagicMock(data=[{"id": "fb-aff-001"}])
        mt.insert.return_value = mi
        return mt
    mock_db.table.side_effect = mock_table_factory
    mock_db.rpc.return_value = MagicMock()
    with patch("supabase_client.get_supabase", return_value=mock_db):
        resp = client_as_user.post("/v1/feedback", json={
            "search_id": "aaaaaaaa-bbbb-4ccc-9ddd-eeeeeeeeeeee",
            "bid_id": "bid-123",
            "user_verdict": "correct",
            "setor_id": "vestuario",
        })
    assert resp.status_code == 201
    assert resp.json()["id"] == "fb-aff-001"


@patch("routes.feedback.get_feature_flag", return_value=True)
def test_submit_feedback_graceful_if_table_missing(mock_ff, client_as_user):
    """FEEDBACK-002: feedback works even if user_sector_affinity table missing."""
    mock_db = MagicMock()
    def mock_table_factory(table_name):
        mt = MagicMock()
        mt.select.return_value = mt
        mt.eq.return_value = mt
        mt.gte.return_value = mt
        if table_name == "user_sector_affinity":
            mt.execute.side_effect = RuntimeError("relation does not exist")
        else:
            mt.execute.return_value = MagicMock(data=[], count=0)
        mi = MagicMock()
        mi.execute.return_value = MagicMock(data=[{"id": "fb-graceful-001"}])
        mt.insert.return_value = mi
        return mt
    mock_db.table.side_effect = mock_table_factory
    with patch("supabase_client.get_supabase", return_value=mock_db):
        resp = client_as_user.post("/v1/feedback", json={
            "search_id": "aaaaaaaa-bbbb-4ccc-9ddd-eeeeeeeeeeee",
            "bid_id": "bid-123",
            "user_verdict": "correct",
            "setor_id": "vestuario",
        })
    assert resp.status_code == 201
    assert resp.json()["id"] == "fb-graceful-001"
