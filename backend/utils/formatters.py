"""Utility functions for formatting values in templates and emails.

STORY-371 AC4: BRL currency formatter and date helpers.
"""

import re
import unicodedata
from datetime import date, datetime
from typing import Optional


def format_brl(value: float) -> str:
    """Format a float value as BRL currency string.

    Examples:
        format_brl(87000.0) -> "R$ 87.000"
        format_brl(1234.56) -> "R$ 1.234,56"
        format_brl(500.0) -> "R$ 500,00"
    """
    if value >= 10_000:
        # No cents for large values
        return "R$ {:,.0f}".format(value).replace(",", ".")
    # Full format for small values
    formatted = "{:,.2f}".format(value)
    # Convert 1,234.56 -> 1.234,56
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def dias_ate_data(date_str: Optional[str]) -> Optional[int]:
    """Return number of days until a given ISO date string.

    Returns None if the date has already passed or if date_str is None.

    Examples:
        dias_ate_data("2026-12-31") -> positive int (future)
        dias_ate_data("2020-01-01") -> None (past)
        dias_ate_data(None) -> None
    """
    if not date_str:
        return None
    try:
        target = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        days = (target - date.today()).days
        return None if days < 0 else days
    except (ValueError, TypeError):
        return None


def truncate_text(text: str, max_length: int = 120) -> str:
    """Truncate text to max_length characters, adding ellipsis if needed."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


# normalize_text extracted from filter/keywords.py to break circular dependency
# (Issue #1965). Imported by synonyms.py, sectors.py, llm_arbiter/.
def normalize_text(text: str) -> str:
    """Lowercase + strip accents + remove punctuation + normalize whitespace."""
    if not text:
        return ""

    # Lowercase
    text = text.lower()

    # Remove accents using NFD normalization
    # NFD = Canonical Decomposition (separates base chars from combining marks)
    text = unicodedata.normalize("NFD", text)
    # Remove combining characters (category "Mn" = Mark, nonspacing)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")

    # Remove punctuation (keep only word characters and spaces)
    # Replace non-alphanumeric with spaces
    text = re.sub(r"[^\w\s]", " ", text)

    # Normalize multiple spaces to single space
    text = re.sub(r"\s+", " ", text)

    return text.strip()
