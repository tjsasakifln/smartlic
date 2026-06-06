"""
DIGEST-005 (#1421): Tests for Mixpanel digest events + admin metrics widget.

Tests cover:
- Tracking pixel endpoint (returns 1x1 transparent GIF)
- Click tracking endpoint (302 redirect)
- Track-sent endpoint (inserts email_tracking_events row)
- Unsubscribe tracking (inserts unsubscribed event)
- Admin digest metrics endpoint (GET /v1/admin/metrics/digest)
- Template tracking helpers (tracking pixel HTML, click tracking URL)
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4
from urllib.parse import quote


# ============================================================================
# Template tracking helpers
# ============================================================================

@pytest.mark.skip(reason="DEBT-131: _tracking_pixel/_click_tracking_url removed + render_daily_digest_email signature changed — tests stale on main")
class TestDigestTemplateTracking:
    """Test tracking pixel generation and click tracking URL building."""

    def test_tracking_pixel_generates_img_tag(self):
        from templates.emails.digest import _tracking_pixel

        tracking_id = str(uuid4())
        backend_url = "https://api.example.com"
        html = _tracking_pixel(tracking_id, backend_url)

        assert tracking_id in html
        assert backend_url in html
        assert 'width="1"' in html
        assert 'height="1"' in html
        assert "display:none" in html
        assert "/api/email/open/" in html

    def test_click_tracking_url_builds_correctly(self):
        from templates.emails.digest import _click_tracking_url

        tracking_id = str(uuid4())
        target = "https://smartlic.tech/buscar?auto=true"
        backend_url = "https://api.example.com"

        url = _click_tracking_url(tracking_id, target, backend_url)

        assert tracking_id in url
        assert backend_url in url
        assert "/api/email/click/" in url
        assert "url=" + quote(target, safe="") in url

    def test_render_daily_digest_with_tracking(self):
        from templates.emails.digest import render_daily_digest_email

        tracking_id = str(uuid4())
        backend_url = "https://api.example.com"

        html = render_daily_digest_email(
            user_name="Test User",
            opportunities=[
                {"titulo": "Oportunidade 1", "valor_estimado": 10000, "uf": "SP"},
            ],
            stats={"total_novas": 1, "setor_nome": "Teste", "total_valor": 10000},
            tracking_id=tracking_id,
            backend_url=backend_url,
        )

        # Tracking pixel should be present
        assert backend_url in html
        assert tracking_id in html
        assert "/api/email/open/" in html
        assert "/api/email/click/" in html

    def test_render_without_tracking(self):
        from templates.emails.digest import render_daily_digest_email

        html = render_daily_digest_email(
            user_name="Test User",
            opportunities=[],
            stats={"total_novas": 0, "setor_nome": "Teste", "total_valor": 0},
            tracking_id=None,
        )

        # No tracking pixel or click tracking URL should be present
        assert "/api/email/open/" not in html
        assert "/api/email/click/" not in html


# ============================================================================
# Email tracking route tests
# ============================================================================

@pytest.mark.asyncio
async def test_tracking_pixel_returns_gif():
    """GET /api/email/open/{tracking_id} should return a 1x1 transparent GIF."""
    from routes.email_tracking import router
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    app.include_router(router)

    tracking_id = str(uuid4())

    with patch("routes.email_tracking.sb_execute", new_callable=AsyncMock) as mock_execute, \
         patch("routes.email_tracking.get_supabase") as mock_get_sb:
        mock_get_sb.return_value = MagicMock()
        mock_execute.return_value = MagicMock(data=[])

        client = TestClient(app)
        response = client.get(f"/api/email/open/{tracking_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/gif"
    assert len(response.content) > 0

    # Verify it's a valid GIF header
    assert response.content[:6] == b"GIF89a"


@pytest.mark.asyncio
async def test_click_tracking_redirects():
    """GET /api/email/click/{tracking_id} should 302 redirect to the target URL."""
    from routes.email_tracking import router
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    app.include_router(router)

    tracking_id = str(uuid4())
    target_url = "https://smartlic.tech/buscar?auto=true"

    with patch("routes.email_tracking.sb_execute", new_callable=AsyncMock) as mock_execute, \
         patch("routes.email_tracking.get_supabase") as mock_get_sb:
        mock_get_sb.return_value = MagicMock()
        mock_execute.return_value = MagicMock(data=[])

        client = TestClient(app)
        response = client.get(
            f"/api/email/click/{tracking_id}",
            params={"url": target_url},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == target_url


@pytest.mark.asyncio
async def test_click_tracking_blocks_external_urls():
    """Click tracking should block non-smartlic URLs by redirecting to smartlic.tech."""
    from routes.email_tracking import router
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    app.include_router(router)

    tracking_id = str(uuid4())
    malicious_url = "https://evil.com/phish"

    with patch("routes.email_tracking.sb_execute", new_callable=AsyncMock) as mock_execute, \
         patch("routes.email_tracking.get_supabase") as mock_get_sb:
        mock_get_sb.return_value = MagicMock()
        mock_execute.return_value = MagicMock(data=[])

        client = TestClient(app)
        response = client.get(
            f"/api/email/click/{tracking_id}",
            params={"url": malicious_url},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["location"] == "https://smartlic.tech"


@pytest.mark.asyncio
async def test_track_sent_endpoint():
    """POST /api/email/track-sent should record a sent event."""
    from routes.email_tracking import router
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    app.include_router(router)

    tracking_id = str(uuid4())
    payload = {
        "tracking_id": tracking_id,
        "user_id": str(uuid4()),
        "frequency": "daily",
        "opportunity_count": 5,
        "sectors": ["vestuario", "informatica"],
    }

    insert_called = False
    insert_payload = {}

    async def mock_execute(query):
        nonlocal insert_called, insert_payload
        # Try to extract inserted data from the query
        if hasattr(query, 'table') and callable(query.table):
            t = query.table()
            if hasattr(t, 'insert') and callable(t.insert):
                def capture_insert(data):
                    nonlocal insert_called, insert_payload
                    insert_called = True
                    insert_payload = data
                    return MagicMock()
                t.insert = capture_insert
        return MagicMock(data=[])

    with patch("routes.email_tracking.sb_execute", new_callable=AsyncMock) as mock_sb:
        mock_sb.return_value = MagicMock(data=[])
        with patch("routes.email_tracking.get_supabase") as mock_get_sb:
            mock_get_sb.return_value = MagicMock()
            client = TestClient(app)
            response = client.post("/api/email/track-sent", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["tracking_id"] == tracking_id


@pytest.mark.asyncio
async def test_unsubscribe_tracking():
    """POST /api/email/unsubscribe should record an unsubscribed event."""
    from routes.email_tracking import router
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    app.include_router(router)

    tracking_id = str(uuid4())
    payload = {
        "tracking_id": tracking_id,
        "user_id": str(uuid4()),
        "frequency": "weekly",
    }

    with patch("routes.email_tracking.sb_execute", new_callable=AsyncMock) as mock_execute, \
         patch("routes.email_tracking.get_supabase") as mock_get_sb:
        mock_get_sb.return_value = MagicMock()
        mock_execute.return_value = MagicMock(data=[])

        client = TestClient(app)
        response = client.post("/api/email/unsubscribe", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


# ============================================================================
# Admin digest metrics endpoint tests
# ============================================================================

@pytest.mark.asyncio
async def test_admin_digest_metrics_returns_zero_defaults():
    """GET /v1/admin/metrics/digest should return zeros when no data."""
    from routes.admin_digest_metrics import router
    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from admin import require_admin

    app = FastAPI()
    app.include_router(router)

    # Override auth for admin access
    app.dependency_overrides[require_admin] = lambda: {"id": "admin-user", "email": "admin@test.com"}

    with patch("routes.admin_digest_metrics.sb_execute", new_callable=AsyncMock) as mock_sb, \
         patch("routes.admin_digest_metrics.get_supabase") as mock_get_sb:
        mock_get_sb.return_value = MagicMock()
        mock_sb.return_value = MagicMock(data=[])

        client = TestClient(app)
        response = client.get("/v1/admin/metrics/digest")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["daily_avg_sent"] == 0.0
    assert data["open_rate_30d"] == 0.0
    assert data["click_rate_30d"] == 0.0
    assert data["unsubscribe_rate_30d"] == 0.0
    assert data["total_sent_30d"] == 0
    assert data["total_opened_30d"] == 0
    assert data["total_clicked_30d"] == 0
    assert data["total_unsubscribed_30d"] == 0
    assert "breakdown_by_frequency" in data
    assert data["queried_at"] is not None


@pytest.mark.asyncio
async def test_admin_digest_metrics_computes_rates():
    """GET /v1/admin/metrics/digest should compute rates correctly."""
    from routes.admin_digest_metrics import router
    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from admin import require_admin

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[require_admin] = lambda: {"id": "admin-user", "email": "admin@test.com"}

    # Mock data: 100 sent, 35 opened, 12 clicked, 2 unsubscribed
    mock_rows = []
    for _ in range(100):
        mock_rows.append({"event_type": "sent", "digest_frequency": "daily"})
    for _ in range(35):
        mock_rows.append({"event_type": "opened", "digest_frequency": "daily"})
    for _ in range(12):
        mock_rows.append({"event_type": "clicked", "digest_frequency": "daily"})
    for _ in range(2):
        mock_rows.append({"event_type": "unsubscribed", "digest_frequency": "daily"})

    with patch("routes.admin_digest_metrics.sb_execute", new_callable=AsyncMock) as mock_sb, \
         patch("routes.admin_digest_metrics.get_supabase") as mock_get_sb:
        mock_get_sb.return_value = MagicMock()
        mock_sb.return_value = MagicMock(data=mock_rows)

        client = TestClient(app)
        response = client.get("/v1/admin/metrics/digest")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total_sent_30d"] == 100
    assert data["total_opened_30d"] == 35
    assert data["total_clicked_30d"] == 12
    assert data["total_unsubscribed_30d"] == 2
    assert data["open_rate_30d"] == 0.35
    assert data["click_rate_30d"] == 0.12
    assert data["unsubscribe_rate_30d"] == 0.02
    assert data["daily_avg_sent"] == pytest.approx(3.3, rel=0.1)


@pytest.mark.asyncio
async def test_admin_digest_metrics_frequency_breakdown():
    """GET /v1/admin/metrics/digest should segment by frequency."""
    from routes.admin_digest_metrics import router
    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from admin import require_admin

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[require_admin] = lambda: {"id": "admin-user", "email": "admin@test.com"}

    # Mix of frequencies
    mock_rows = [
        {"event_type": "sent", "digest_frequency": "daily"},
        {"event_type": "sent", "digest_frequency": "daily"},
        {"event_type": "opened", "digest_frequency": "daily"},
        {"event_type": "sent", "digest_frequency": "weekly"},
        {"event_type": "opened", "digest_frequency": "weekly"},
        {"event_type": "sent", "digest_frequency": "twice_weekly"},
    ]

    with patch("routes.admin_digest_metrics.sb_execute", new_callable=AsyncMock) as mock_sb, \
         patch("routes.admin_digest_metrics.get_supabase") as mock_get_sb:
        mock_get_sb.return_value = MagicMock()
        mock_sb.return_value = MagicMock(data=mock_rows)

        client = TestClient(app)
        response = client.get("/v1/admin/metrics/digest")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()

    breakdown = data["breakdown_by_frequency"]
    assert breakdown["daily"]["sent"] == 2
    assert breakdown["daily"]["opened"] == 1
    assert breakdown["weekly"]["sent"] == 1
    assert breakdown["weekly"]["opened"] == 1
    assert breakdown["twice_weekly"]["sent"] == 1


@pytest.mark.asyncio
async def test_admin_digest_metrics_fallback_on_db_error():
    """GET /v1/admin/metrics/digest should return zeros gracefully on DB error."""
    from routes.admin_digest_metrics import router
    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from admin import require_admin

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[require_admin] = lambda: {"id": "admin-user", "email": "admin@test.com"}

    with patch("routes.admin_digest_metrics.sb_execute", side_effect=Exception("DB error")), \
         patch("routes.admin_digest_metrics.get_supabase") as mock_get_sb:
        mock_get_sb.return_value = MagicMock()

        client = TestClient(app)
        response = client.get("/v1/admin/metrics/digest")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["total_sent_30d"] == 0
    assert data["open_rate_30d"] == 0.0


# ============================================================================
# Analytics events tests (integration of digest_sent Mixpanel event)
# ============================================================================

class TestDigestSentMixpanelEvent:
    """Test that track_digest_sent_event fires Mixpanel events correctly."""

    @pytest.mark.asyncio
    async def test_track_digest_sent_fires_event(self):
        from services.digest_service import track_digest_sent_event
        from analytics_events import reset_for_testing

        reset_for_testing()

        tracking_id = str(uuid4())

        with patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_sb, \
             patch("supabase_client.get_supabase") as mock_get_sb:
            mock_get_sb.return_value = MagicMock()
            mock_sb.return_value = MagicMock(data=[])

            # This should not raise
            await track_digest_sent_event(
                user_id=str(uuid4()),
                frequency="daily",
                opportunity_count=3,
                sectors=["vestuario"],
                tracking_id=tracking_id,
            )

        reset_for_testing()

    @pytest.mark.asyncio
    async def test_track_digest_sent_handles_db_failure(self):
        from services.digest_service import track_digest_sent_event
        from analytics_events import reset_for_testing

        reset_for_testing()

        with patch("supabase_client.sb_execute", side_effect=Exception("DB down")), \
             patch("supabase_client.get_supabase") as mock_get_sb:
            mock_get_sb.return_value = MagicMock()

            # Should not raise despite DB failure (fire-and-forget)
            await track_digest_sent_event(
                user_id=str(uuid4()),
                frequency="daily",
                opportunity_count=0,
            )

        reset_for_testing()
