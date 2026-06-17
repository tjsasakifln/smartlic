"""Shared helper utilities for dedup layers."""
import re
import unicodedata
from typing import Optional

from filter.stopwords import PT_BR_STOPWORDS

_FUZZY_STOPWORDS = PT_BR_STOPWORDS

_LOT_PATTERN = re.compile(
    r'\b(?:lote|item|grupo|lotes?)\s*(?:n[.\xba\xba]\s*)?(\d+)\b',
    re.IGNORECASE,
)


def tokenize_objeto(texto: str) -> frozenset:
    """Tokenize and normalize procurement object for Jaccard similarity."""
    texto = texto.lower()
    texto = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    texto = re.sub(r"[^\w\s]", " ", texto)
    return frozenset(
        t for t in texto.split()
        if len(t) > 2 and t not in _FUZZY_STOPWORDS
    )


def jaccard(a: frozenset, b: frozenset) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def extract_edital_number(source_id: str) -> int | None:
    """Extract numeric edital number from source_id."""
    match = re.search(r"/(\d{4,6})/", source_id or "")
    if match:
        try:
            return int(match.group(1))
        except (ValueError, TypeError):
            return None
    return None


def extract_lot_number(obj_text: str) -> Optional[str]:
    """Extract lot/item/group number from objetoCompra text."""
    m = _LOT_PATTERN.search(obj_text or "")
    return m.group(1) if m else None


def extract_process_base(source_id: str, cnpj: str) -> str | None:
    """Return a (cnpj, year) key if this source_id looks like a PNCP edital."""
    if not source_id or not cnpj:
        return None
    m = re.search(r"-(\d{4,6})/(\d{4})$", source_id)
    if m:
        year = m.group(2)
        return f"{cnpj}|{year}"
    return None
