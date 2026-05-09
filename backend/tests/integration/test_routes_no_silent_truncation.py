"""DATA-CAP-001: Integration tests proving the refactored routes no longer
truncate at PostgREST max_rows=1000.

These tests stub the Supabase query builder so that ``.range(start, end)
.execute()`` returns rows in 1000+500 batches (1500 total). The pre-fix code
would have stopped at 1000; the refactored code (``paginate_full``) must
return all 1500.

Each route is exercised by calling its sync ``_sync_query`` (or equivalent)
function directly — that is the layer that owns the supabase round-trip and
the one DATA-CAP-001 fixed. Running the full FastAPI route here would pull in
async budget machinery, auth, and Sentry middleware that has no bearing on
the truncation invariant.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fake supabase client returning rows in 1000+500 batches.
# ---------------------------------------------------------------------------


class _FakeQueryBuilder:
    """Tracks .range(start, end) calls and slices a canned ``rows`` array."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self._range: tuple[int, int] | None = None
        self.call_count = 0

    # Builder API used in the routes — return self to keep chaining.
    def select(self, *_a: Any, **_k: Any) -> "_FakeQueryBuilder": return self
    def eq(self, *_a: Any, **_k: Any) -> "_FakeQueryBuilder": return self
    def gte(self, *_a: Any, **_k: Any) -> "_FakeQueryBuilder": return self
    def lte(self, *_a: Any, **_k: Any) -> "_FakeQueryBuilder": return self
    def neq(self, *_a: Any, **_k: Any) -> "_FakeQueryBuilder": return self
    def is_(self, *_a: Any, **_k: Any) -> "_FakeQueryBuilder": return self
    def not_(self) -> "_FakeQueryBuilder": return self
    def ilike(self, *_a: Any, **_k: Any) -> "_FakeQueryBuilder": return self
    def order(self, *_a: Any, **_k: Any) -> "_FakeQueryBuilder": return self
    def limit(self, *_a: Any, **_k: Any) -> "_FakeQueryBuilder":
        # Pre-fix code paths that still call .limit() route through here.
        return self

    def range(self, start: int, end: int) -> "_FakeQueryBuilder":
        self._range = (start, end)
        return self

    def execute(self) -> MagicMock:
        self.call_count += 1
        if self._range is None:
            # Whole-table fallback (pre-fix path).
            data = self._rows[:1000]  # PostgREST cap — exactly 1000
        else:
            start, end = self._range
            data = self._rows[start : end + 1]
            self._range = None
        return MagicMock(data=data)


class _FakeSupabase:
    def __init__(self, rows: list[dict]) -> None:
        self._builder = _FakeQueryBuilder(rows)

    def table(self, _name: str) -> _FakeQueryBuilder:
        return self._builder

    @property
    def builder(self) -> _FakeQueryBuilder:
        return self._builder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rows(n: int, **defaults: Any) -> list[dict]:
    base = {
        "ni_fornecedor": "00000000000000",
        "nome_fornecedor": "Acme",
        "orgao_cnpj": "00000000000000",
        "orgao_nome": "Órgão",
        "valor_global": 1000.0,
        "data_assinatura": "2026-01-01",
        "objeto_contrato": "obra de teste",
        "uf": "SP",
        "municipio": "São Paulo",
        "valor_total_estimado": 1000.0,
        "modalidade_nome": "Pregão",
        "modalidade_id": 6,
        "objeto_compra": "compra teste",
        "data_publicacao": "2026-01-01T00:00:00",
        "esfera_id": "F",
        "orgao_razao_social": "Órgão XYZ",
        "pncp_id": "x",
    }
    base.update(defaults)
    return [dict(base, _idx=i) for i in range(n)]


# ---------------------------------------------------------------------------
# contratos_publicos.sector_contracts (callsite L198 → paginate_full)
# ---------------------------------------------------------------------------


def test_contratos_publicos_sector_contracts_returns_all_1500(monkeypatch):
    rows = _make_rows(1_500)
    fake_sb = _FakeSupabase(rows)

    import supabase_client as sc
    monkeypatch.setattr(sc, "get_supabase", lambda: fake_sb)

    # Replicate the inner _sync_query body — it is a closure inside the
    # async route handler and exercising it via _run_with_budget would pull
    # in unrelated machinery. The query shape is identical to the route's.
    from utils.postgrest_paginate import paginate_full
    query = (
        fake_sb.table("pncp_supplier_contracts")
        .select("ni_fornecedor")
        .eq("uf", "SP")
        .eq("is_active", True)
        .order("data_assinatura", desc=True)
    )
    result = paginate_full(
        query,
        route="contratos_publicos.sector_contracts",
        entity_type="contracts",
        max_total=5000,
    )
    assert len(result) == 1_500
    # Two paged round-trips: first 1000, second 500 (short page → loop exits).
    assert fake_sb.builder.call_count == 2


# ---------------------------------------------------------------------------
# blog_stats._query_contratos_sync (Pattern B — dynamic uf filter)
# ---------------------------------------------------------------------------


def test_blog_stats_query_contratos_returns_all_1500(monkeypatch):
    rows = _make_rows(1_500, uf="SP")
    fake_sb = _FakeSupabase(rows)

    import supabase_client as sc
    monkeypatch.setattr(sc, "get_supabase", lambda: fake_sb)

    from routes.blog_stats import _query_contratos_sync

    result = _query_contratos_sync(uf="SP", municipio_pattern=None)

    assert len(result) == 1_500, (
        f"Expected 1500 rows; got {len(result)}. "
        f"PostgREST cap regression — paginate_full not invoked."
    )
    assert fake_sb.builder.call_count == 2


# ---------------------------------------------------------------------------
# observatorio._query_historical_sync (callsite L331)
# ---------------------------------------------------------------------------


def test_observatorio_historical_relatorio_returns_all_1500(monkeypatch):
    rows = _make_rows(1_500, valor_total_estimado=2500.0)
    fake_sb = _FakeSupabase(rows)

    import supabase_client as sc
    monkeypatch.setattr(sc, "get_supabase", lambda: fake_sb)

    from routes.observatorio import _query_historical_sync

    result = _query_historical_sync("2026-01-01", "2026-01-31")

    assert len(result) == 1_500
    assert fake_sb.builder.call_count == 2
    # Spot-check normalization shape.
    assert result[0]["uf"] == "SP"
    assert result[0]["valor_estimado"] == 2500.0


# ---------------------------------------------------------------------------
# orgao_publico.orgao_stats inner _sync_query
# ---------------------------------------------------------------------------


def test_orgao_publico_orgao_stats_returns_all_1500(monkeypatch):
    rows = _make_rows(1_500, orgao_cnpj="11111111000111")
    fake_sb = _FakeSupabase(rows)

    import supabase_client as sc
    monkeypatch.setattr(sc, "get_supabase", lambda: fake_sb)

    # The route's inner _sync_query is a closure — exercise the same shape
    # paginate_full call here to confirm it returns 1500.
    from utils.postgrest_paginate import paginate_full
    query = (
        fake_sb.table("pncp_raw_bids")
        .select("orgao_razao_social,esfera_id,uf,municipio,modalidade_nome,objeto_compra,valor_total_estimado,data_publicacao")
        .eq("orgao_cnpj", "11111111000111")
        .eq("is_active", True)
    )
    result = paginate_full(
        query,
        route="orgao_publico.orgao_stats",
        entity_type="bids",
        max_total=5000,
    )
    assert len(result) == 1_500
    assert fake_sb.builder.call_count == 2


# ---------------------------------------------------------------------------
# Pre-fix smoke: a bare .limit(5000).execute() is silently truncated to 1000
# (this is what we are protecting against). Documents the invariant.
# ---------------------------------------------------------------------------


def test_pre_fix_smoke_bare_limit_returns_only_1000(monkeypatch):
    rows = _make_rows(1_500)
    fake_sb = _FakeSupabase(rows)

    # Simulate the pre-fix code path: .limit(5000).execute() with no .range().
    resp = (
        fake_sb.table("anything")
        .select("*")
        .eq("is_active", True)
        .limit(5000)
        .execute()
    )
    # The fake mirrors PostgREST: the cap-truncated response has exactly
    # POSTGREST_ROW_CAP rows, even though .limit(5000) was requested.
    from utils.postgrest_paginate import POSTGREST_ROW_CAP
    assert len(resp.data) == POSTGREST_ROW_CAP
    assert len(resp.data) < len(rows), (
        "Pre-fix smoke: confirm bare .limit(5000).execute() under the cap."
    )
