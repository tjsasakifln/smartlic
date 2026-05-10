"""Tests for utils/cnpj_validator — alfanumérico-ready (IN 2.229/2024)."""

import pytest

from utils.cnpj_validator import is_valid_cnpj_format, normalize_cnpj


@pytest.mark.parametrize("cnpj,expected", [
    # Válidos — numérico sem máscara
    ("12345678000195", True),
    ("00000000000191", True),   # BNDES
    # Válidos — alfanumérico futuro (12 alnum + 2 dígitos)
    ("AB3DEF78000195", True),
    ("ab3def78000195", True),   # lowercase deve ser normalizado
    ("AAAAAAAAAAAA12", True),   # 12 letras + 2 dígitos
    ("000000000A0A12", True),   # mix
    # Válidos — com máscara padrão
    ("12.345.678/0001-95", True),
    ("00.000.000/0001-91", True),
    # Inválidos — CPF (11 dígitos)
    ("93513712553", False),
    ("00000000000", False),
    # Inválidos — tamanho errado
    ("570731320001602", False),  # 15 dígitos
    ("1234567800019", False),    # 13 dígitos
    ("123456780001", False),     # 12 dígitos
    # Inválidos — vazio / None / tipo errado
    ("", False),
    (None, False),   # type: ignore[arg-type]
    (12345678000195, False),  # type: ignore[arg-type]  # int
    # Inválidos — caracteres especiais restantes após remoção de máscara
    ("12345678 0001 95", False),  # espaço → 16 chars → mismatch
])
def test_is_valid_cnpj_format(cnpj, expected):
    assert is_valid_cnpj_format(cnpj) == expected, f"cnpj={cnpj!r} expected={expected}"


@pytest.mark.parametrize("raw,expected", [
    ("12.345.678/0001-95", "12345678000195"),
    ("ab3def78000195", "AB3DEF78000195"),
    ("", ""),
    (None, ""),
    ("AB-CD/EF.12", "ABCDEF12"),
])
def test_normalize_cnpj(raw, expected):
    assert normalize_cnpj(raw) == expected, f"raw={raw!r} expected={expected!r}"
