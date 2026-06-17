"""
Utility modules for SmartLic backend.

This package contains helper functions and utilities for:
- ordenacao: Sorting and ordering of procurement results
- formatters: Value/text formatting helpers (format_brl, normalize_text)
"""

from .formatters import (
    format_brl,
    dias_ate_data,
    truncate_text,
    normalize_text,
)
from .ordenacao import (
    parse_date,
    parse_valor,
    calcular_relevancia,
    ordenar_licitacoes,
)

__all__ = [
    "format_brl",
    "dias_ate_data",
    "truncate_text",
    "normalize_text",
    "parse_date",
    "parse_valor",
    "calcular_relevancia",
    "ordenar_licitacoes",
]
