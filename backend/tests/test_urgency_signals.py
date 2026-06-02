"""CONV-016: Tests for recency/urgency signals on pSEO entity pages.

Covers:
  1. AtividadeRecenteData schema validation
  2. Trend calculation logic (_compute_trend)
  3. Seasonality detection (_compute_seasonality)
  4. build_recency_from_records helper
"""

import pytest
from datetime import datetime, timezone, timedelta
from routes._recency_helpers import (
    AtividadeRecenteData,
    build_recency_from_records,
)


class TestAtividadeRecenteData:
    """Schema validation for the AtividadeRecenteData model."""

    def test_defaults(self):
        """Default values should be zero/empty for all fields."""
        data = AtividadeRecenteData()
        assert data.contagem_30d == 0
        assert data.contagem_90d == 0
        assert data.valor_total_30d == 0.0
        assert data.tendencia_12m == "stable"
        assert data.tendencia_percentual == 0.0
        assert data.ultimo_evento_data is None
        assert data.sazonalidade_mes_pico is None

    def test_custom_values(self):
        """Custom values should be accepted."""
        data = AtividadeRecenteData(
            contagem_30d=5,
            contagem_90d=15,
            valor_total_30d=100000.00,
            tendencia_12m="up",
            tendencia_percentual=25.5,
            ultimo_evento_data="2026-05-28",
            sazonalidade_mes_pico=3,
        )
        assert data.contagem_30d == 5
        assert data.contagem_90d == 15
        assert data.valor_total_30d == pytest.approx(100000.00)
        assert data.tendencia_12m == "up"
        assert data.tendencia_percentual == pytest.approx(25.5)
        assert data.ultimo_evento_data == "2026-05-28"
        assert data.sazonalidade_mes_pico == 3


class TestBuildRecencyFromRecords:
    """Tests for the build_recency_from_records helper."""

    def _make_record(self, date_str: str, value: float = 1000.0) -> dict:
        return {"data_assinatura": date_str, "valor_global": value}

    def test_empty_records(self):
        """Empty records should return all-default recency data."""
        result = build_recency_from_records([])
        assert result["contagem_30d"] == 0
        assert result["contagem_90d"] == 0
        assert result["valor_total_30d"] == 0.0
        assert result["tendencia_12m"] == "stable"
        assert result["ultimo_evento_data"] is None

    def test_single_recent_record(self):
        """A single record from today should return correct counts."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        records = [self._make_record(today, 5000.0)]
        result = build_recency_from_records(records)

        assert result["contagem_30d"] == 1
        assert result["contagem_90d"] == 1
        assert result["valor_total_30d"] == pytest.approx(5000.0)
        assert result["ultimo_evento_data"] == today

    def test_record_older_than_90d(self):
        """A record older than 90 days should count only in trend."""
        past = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d")
        records = [self._make_record(past, 1000.0)]
        result = build_recency_from_records(records)

        assert result["contagem_30d"] == 0
        assert result["contagem_90d"] == 0
        assert result["valor_total_30d"] == 0.0
        # ultimo_evento_data should still be set
        assert result["ultimo_evento_data"] == past

    def test_mixed_records(self):
        """Mix of recent and old records should separate window counts."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        old = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
        very_old = (datetime.now(timezone.utc) - timedelta(days=200)).strftime("%Y-%m-%d")

        records = [
            self._make_record(today_str, 1000.0),
            self._make_record(today_str, 2000.0),
            self._make_record(old, 3000.0),
            self._make_record(very_old, 4000.0),
        ]
        result = build_recency_from_records(records)

        # 2 today + 1 within 90d = 3 in 90d window; 2 in 30d
        assert result["contagem_30d"] == 2
        assert result["contagem_90d"] == 3
        assert result["valor_total_30d"] == pytest.approx(3000.0)
        assert result["ultimo_evento_data"] == today_str

    def _make_monthly_records(self, counts_by_month_offset: list[tuple[int, int]]) -> list[dict]:
        """Helper to generate records with specific counts per month offset (0=current)."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        records = []
        for offset_months, count in counts_by_month_offset:
            m = now.month - offset_months
            y = now.year
            while m <= 0:
                m += 12
                y -= 1
            for _ in range(count):
                records.append(self._make_record(f"{y:04d}-{m:02d}-15", 1000.0))
        return records

    def test_trend_up(self):
        """Records concentrated in recent months should show 'up' trend."""
        records = self._make_monthly_records([
            (0, 5), (1, 5), (2, 5), (3, 5), (4, 5), (5, 5),  # recent: 5 each
            (6, 1), (7, 1), (8, 1), (9, 1), (10, 1), (11, 1),  # older: 1 each
        ])
        result = build_recency_from_records(records)
        assert result["tendencia_12m"] == "up"
        assert result["tendencia_percentual"] > 15

    def test_trend_down(self):
        """Records concentrated in older months should show 'down' trend."""
        records = self._make_monthly_records([
            (0, 1), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1),  # recent: 1 each
            (6, 5), (7, 5), (8, 5), (9, 5), (10, 5), (11, 5),  # older: 5 each
        ])
        result = build_recency_from_records(records)
        assert result["tendencia_12m"] == "down"
        assert result["tendencia_percentual"] < -15

    def test_trend_stable(self):
        """Similar counts across months should show 'stable' trend."""
        records = self._make_monthly_records([
            (i, 2) for i in range(12)  # 2 per month for 12 months
        ])
        result = build_recency_from_records(records)
        assert result["tendencia_12m"] == "stable"

    def test_seasonality_detected(self):
        """Peak month should be correctly identified."""
        from datetime import datetime, timezone
        year = datetime.now(timezone.utc).year
        records = []
        # Peak in month 3 (March): lots of records
        for _ in range(20):
            records.append(self._make_record(f"{year}-03-15", 1000.0))
        # Other months: few records
        for m in [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12]:
            records.append(self._make_record(f"{year}-{m:02d}-15", 1000.0))

        result = build_recency_from_records(records)
        assert result["sazonalidade_mes_pico"] == 3

    def test_custom_date_and_value_fields(self):
        """Custom field names should work for date and value."""
        from datetime import datetime, timezone, timedelta
        today = datetime.now(timezone.utc)
        recent1 = (today - timedelta(days=5)).strftime("%Y-%m-%d")
        recent2 = (today - timedelta(days=10)).strftime("%Y-%m-%d")
        records = [
            {"minha_data": recent1, "meu_valor": 999.99},
            {"minha_data": recent2, "meu_valor": 500.50},
        ]
        result = build_recency_from_records(
            records,
            date_field="minha_data",
            value_field="meu_valor",
        )
        assert result["contagem_30d"] == 2  # both within 30 days of now
        assert result["valor_total_30d"] > 0

    def test_insufficient_data_for_trend(self):
        """Fewer than 3 months of data should default to stable."""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        m1 = (now - timedelta(days=5)).strftime("%Y-%m-%d")
        m2 = (now - timedelta(days=35)).strftime("%Y-%m-%d")
        records = [
            self._make_record(m1, 1000.0),
            self._make_record(m2, 1000.0),
        ]
        result = build_recency_from_records(records)
        assert result["tendencia_12m"] == "stable"
        assert result["tendencia_percentual"] == 0.0
