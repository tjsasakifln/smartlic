"""CONV-016: Shared recency/urgency data helpers for pSEO entity pages.

Provides the ``AtividadeRecenteData`` Pydantic model and helper functions
to compute recency indicators (counts, trends, seasonality) from the
DataLake tables (pncp_raw_bids, pncp_supplier_contracts).
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared model
# ---------------------------------------------------------------------------

class AtividadeRecenteData(BaseModel):
    """Recency/urgency data for entity pages (CONV-016).

    Each pSEO entity response should include this block so the frontend
    can render time-based urgency signals that create motivation to act.
    """
    contagem_30d: int = 0              # count of events in last 30 days
    contagem_90d: int = 0              # count in last 90 days
    valor_total_30d: float = 0.0       # total value in last 30 days
    tendencia_12m: str = "stable"      # "up", "stable", "down"
    tendencia_percentual: float = 0.0  # percent change
    ultimo_evento_data: Optional[str] = None  # ISO date of most recent event
    sazonalidade_mes_pico: Optional[int] = None  # peak month (1-12)


# ---------------------------------------------------------------------------
# Trend calculation
# ---------------------------------------------------------------------------

def _compute_trend(
    monthly_counts: dict[str, int],
) -> tuple[str, float]:
    """Compute 12-month trend from monthly count data.

    Splits the data into two 6-month halves and compares averages.
    Returns (direction, percent_change) where direction is
    "up", "down", or "stable".
    """
    if len(monthly_counts) < 3:
        return "stable", 0.0

    sorted_months = sorted(monthly_counts.keys())
    mid = len(sorted_months) // 2
    first_half = [monthly_counts[m] for m in sorted_months[:mid]]
    second_half = [monthly_counts[m] for m in sorted_months[mid:]]

    avg_first = sum(first_half) / len(first_half) if first_half else 0
    avg_second = sum(second_half) / len(second_half) if second_half else 0

    if avg_first == 0 and avg_second == 0:
        return "stable", 0.0

    if avg_first == 0:
        pct = 100.0 if avg_second > 0 else 0.0
    else:
        pct = ((avg_second - avg_first) / avg_first) * 100

    if pct > 15:
        return "up", round(pct, 1)
    elif pct < -15:
        return "down", round(pct, 1)
    else:
        return "stable", round(pct, 1)


def _compute_seasonality(monthly_counts: dict[str, int]) -> Optional[int]:
    """Find the peak month (1-12) from monthly count data.

    Returns None if data is insufficient.
    """
    month_total: Counter = Counter()
    for month_key, count in monthly_counts.items():
        try:
            month_num = int(month_key.split("-")[1])
            month_total[month_num] += count
        except (IndexError, ValueError):
            continue

    if not month_total:
        return None

    peak = month_total.most_common(1)[0]
    return peak[0] if peak[1] > 0 else None


# ---------------------------------------------------------------------------
# Build recency data from a list of records with date + value fields
# ---------------------------------------------------------------------------

def build_recency_from_records(
    records: list[dict],
    date_field: str = "data_assinatura",
    value_field: str = "valor_global",
) -> dict:
    """Compute ``AtividadeRecenteData`` fields from a flat record list.

    Args:
        records: List of dicts, each containing at least a date string.
        date_field: Key for the date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
        value_field: Key for the numeric value.

    Returns:
        A dict matching ``AtividadeRecenteData`` field names.
    """
    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    cutoff_90d = now - timedelta(days=90)

    contagem_30d = 0
    contagem_90d = 0
    valor_total_30d = 0.0
    ultimo_evento: Optional[str] = None
    monthly_counts: dict[str, int] = defaultdict(int)

    for rec in records:
        raw_date = rec.get(date_field) or ""
        date_str = raw_date[:10]  # YYYY-MM-DD
        if not date_str:
            continue

        try:
            dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue

        # Last event date
        if ultimo_evento is None or date_str > ultimo_evento:
            ultimo_evento = date_str

        # Window counts
        if dt >= cutoff_90d:
            contagem_90d += 1
        if dt >= cutoff_30d:
            contagem_30d += 1
            try:
                v = float(rec.get(value_field) or 0)
                valor_total_30d += v
            except (ValueError, TypeError):
                pass

        # Monthly bucket for trend
        month_key = date_str[:7]
        monthly_counts[month_key] += 1

    tendencia, pct = _compute_trend(dict(monthly_counts))
    sazonalidade = _compute_seasonality(dict(monthly_counts))

    return {
        "contagem_30d": contagem_30d,
        "contagem_90d": contagem_90d,
        "valor_total_30d": round(valor_total_30d, 2),
        "tendencia_12m": tendencia,
        "tendencia_percentual": pct,
        "ultimo_evento_data": ultimo_evento,
        "sazonalidade_mes_pico": sazonalidade,
    }
