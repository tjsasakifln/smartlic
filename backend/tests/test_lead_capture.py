"""Tests for REPO-004: Extended lead_capture endpoint.

Covers:
- All 8 valid sources accepted (Literal enum)
- Invalid source → 422
- mensagem > 500 chars → 422
- Backward compat: original 3 sources still work
- Optional REPO-004 fields pass through to DB insert
- DB failure is fail-open (returns 200 with success=True)
- Basic email validation returns 400
"""

from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

ENDPOINT = "/v1/lead-capture"

# ---------------------------------------------------------------------------
# Fake Supabase — mirrors fluent fake pattern used in test_relatorio_endpoint.py
# ---------------------------------------------------------------------------


class _FakeTable:
    """Tiny fake supporting the upsert().execute() chain."""

    def __init__(self, store: list, fail: bool = False):
        self._store = store
        self._fail = fail
        self._pending_row = None

    def upsert(self, row, on_conflict=None):  # noqa: ARG002
        self._pending_row = dict(row)
        return self

    def execute(self):
        if self._fail:
            raise RuntimeError("simulated db failure")
        email = self._pending_row.get("email")
        source = self._pending_row.get("source")
        for existing in self._store:
            if existing.get("email") == email and existing.get("source") == source:
                existing.update(self._pending_row)
                return MagicMock(data=[existing])
        row = dict(self._pending_row)
        row.setdefault("id", f"lead-{len(self._store) + 1}")
        self._store.append(row)
        return MagicMock(data=[row])


class FakeSupabase:
    def __init__(self, fail: bool = False):
        self.leads: list = []
        self._fail = fail

    def table(self, name):
        assert name == "leads", f"unexpected table: {name}"
        return _FakeTable(self.leads, fail=self._fail)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_sb():
    sb = FakeSupabase()
    with patch("supabase_client.get_supabase", return_value=sb):
        yield sb


@pytest.fixture
def fake_sb_db_fail():
    sb = FakeSupabase(fail=True)
    with patch("supabase_client.get_supabase", return_value=sb):
        yield sb


def _valid_payload(**overrides):
    base = {"email": "lead@empresa.com.br", "source": "calculadora"}
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Source validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("source", [
    "calculadora", "cnpj", "alertas",
    "consultoria", "radar", "report", "intel", "diagnostico",
])
async def test_all_8_sources_accepted(source, fake_sb):
    """All 8 Literal sources must return 200 with success=True."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(ENDPOINT, json=_valid_payload(source=source))
    assert r.status_code == 200, f"source={source!r} → {r.status_code}: {r.text}"
    assert r.json()["success"] is True


@pytest.mark.asyncio
async def test_invalid_source_returns_422(fake_sb):
    """Unknown source must be rejected by Pydantic Literal validation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(ENDPOINT, json=_valid_payload(source="newsletter"))
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Backward compatibility (original 3 sources)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["calculadora", "cnpj", "alertas"])
async def test_original_sources_backward_compat(source, fake_sb):
    """calculadora, cnpj, alertas must still work as before REPO-004."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(ENDPOINT, json=_valid_payload(source=source, setor="TI", uf="SP"))
    assert r.status_code == 200
    assert r.json()["success"] is True
    row = fake_sb.leads[0]
    assert row["source"] == source
    assert row["uf"] == "SP"
    assert row["setor"] == "TI"


# ---------------------------------------------------------------------------
# mensagem validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mensagem_within_limit_accepted(fake_sb):
    """mensagem up to 500 chars is accepted."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            ENDPOINT,
            json=_valid_payload(source="diagnostico", mensagem="x" * 500),
        )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_mensagem_over_500_chars_returns_422(fake_sb):
    """mensagem > 500 chars must be rejected (Field max_length=500)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            ENDPOINT,
            json=_valid_payload(source="diagnostico", mensagem="x" * 501),
        )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Optional fields pass-through
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_optional_fields_persisted_to_db(fake_sb):
    """All REPO-004 optional fields must be stored in the leads row."""
    payload = {
        "email": "diagnostico@b2g.com.br",
        "source": "diagnostico",
        "nome": "Ana Lima",
        "empresa": "Construtora Lima LTDA",
        "cnpj": "12.345.678/0001-99",
        "telefone": "+55 11 91234-5678",
        "modalidade_interesse": "intel",
        "mensagem": "Preciso de análise de concorrentes.",
        "utm_source": "google",
        "utm_campaign": "repo004-launch",
        "referer_path": "/observatorio/raio-x-setor/ti",
        "setor": "TI",
        "uf": "SP",
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(ENDPOINT, json=payload)

    assert r.status_code == 200
    assert len(fake_sb.leads) == 1
    row = fake_sb.leads[0]
    assert row["nome"] == "Ana Lima"
    assert row["empresa"] == "Construtora Lima LTDA"
    assert row["cnpj"] == "12.345.678/0001-99"
    assert row["telefone"] == "+55 11 91234-5678"
    assert row["modalidade_interesse"] == "intel"
    assert row["mensagem"] == "Preciso de análise de concorrentes."
    assert row["utm_source"] == "google"
    assert row["utm_campaign"] == "repo004-launch"
    assert row["referer_path"] == "/observatorio/raio-x-setor/ti"


@pytest.mark.asyncio
async def test_invalid_modalidade_interesse_returns_422(fake_sb):
    """modalidade_interesse must be one of the allowed Literal values."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            ENDPOINT,
            json=_valid_payload(source="diagnostico", modalidade_interesse="invalido"),
        )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_email_returns_400(fake_sb):
    """Malformed email (no @) returns 400 per route-level validation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(ENDPOINT, json=_valid_payload(email="notanemail"))
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Fail-open behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_failure_is_fail_open(fake_sb_db_fail):
    """If the DB upsert fails, the route still returns success=True (fail-open)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(ENDPOINT, json=_valid_payload())
    assert r.status_code == 200
    assert r.json()["success"] is True


# ---------------------------------------------------------------------------
# UF normalization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_uf_is_uppercased(fake_sb):
    """UF provided in lowercase must be stored uppercased."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(ENDPOINT, json=_valid_payload(uf="rj"))
    assert r.status_code == 200
    assert fake_sb.leads[0]["uf"] == "RJ"


@pytest.mark.asyncio
async def test_email_is_lowercased_and_stripped(fake_sb):
    """Email must be lowercased and stripped before storage."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(ENDPOINT, json=_valid_payload(email="  USER@Example.COM  "))
    assert r.status_code == 200
    assert fake_sb.leads[0]["email"] == "user@example.com"
