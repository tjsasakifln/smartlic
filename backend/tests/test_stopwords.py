"""Tests for PT-BR stopwords module (filter/stopwords.py).

Verifies:
- Total count is approximately 230 words
- Procurement-specific terms are present
- Common articles/prepositions are present
- is_stopword() helper works correctly
- The set works with NFD-normalized input
"""

import unicodedata

from filter.stopwords import PT_BR_STOPWORDS, is_stopword


def _nfd(text: str) -> str:
    """Strip combining marks (NFD normalization) to match stopword format."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


class TestStopwordsCount:
    """Verify total word count is in the expected range."""

    def test_total_count_within_expected_range(self):
        """~230 words expected: 200 NFD-unique NLTK + 27 procurement terms."""
        count = len(PT_BR_STOPWORDS)
        # Allow some margin: 220-235 is the expected range (verified: 227).
        # The exact count depends on NLTK version — hardcoded without NLTK dep.
        assert 220 <= count <= 235, (
            f"Expected ~227 stopwords, got {count}. "
            f"If NLTK added/removed words, adjust the expected range."
        )

    def test_minimum_count(self):
        """Must have at least 200 words (NLTK baseline)."""
        assert len(PT_BR_STOPWORDS) >= 200


class TestProcurementTerms:
    """Verify procurement-specific terms are present."""

    PROCUREMENT_TERMS = [
        "edital", "pregao", "licitacao", "contratacao",
        "publica", "municipal", "estadual", "federal",
        "aquisicao", "processo", "administrativo",
        "modalidade", "concorrencia", "precos",
        "convite", "leilao", "concurso", "dialogo",
        "competitivo", "disputa", "eletronica",
        "participacao", "habilitacao", "propostas",
    ]

    def test_all_procurement_terms_present(self):
        """All 24+ procurement terms must be in the stopword set."""
        for term in self.PROCUREMENT_TERMS:
            assert term in PT_BR_STOPWORDS, (
                f"Procurement term '{term}' missing from stopwords"
            )

    def test_procurement_count(self):
        """At least 24 procurement-specific terms."""
        procurement_count = len(
            {w for w in PT_BR_STOPWORDS if len(w) > 5}
        )
        # Procurement terms are typically longer than 5 chars
        assert procurement_count > 50, (
            f"Expected many longer words (procurement terms), got {procurement_count}"
        )


class TestCommonStopwords:
    """Verify basic Portuguese stopwords are present."""

    COMMON_WORDS = [
        "de", "do", "da", "dos", "das",
        "em", "no", "na", "nos", "nas",
        "para", "por", "com", "e", "a", "o",
        "um", "uma", "ao", "pelo", "pela",
        "que", "se", "ou", "os", "as",
        "este", "esta", "essa", "isso",
        "nao", "ja", "mais", "muito",
        "tambem", "ele", "ela", "eles", "elas",
        "ser", "estar", "haver",
        "sou", "tem", "esta", "foi", "sao",
        "nem", "mas", "quem",
    ]

    def test_common_stopwords_present(self):
        """All common PT-BR stopwords must be present."""
        for word in self.COMMON_WORDS:
            assert word in PT_BR_STOPWORDS, (
                f"Common stopword '{word}' missing"
            )

    def test_no_empty_strings(self):
        """No empty strings in the stopwords set."""
        assert "" not in PT_BR_STOPWORDS
        assert " " not in PT_BR_STOPWORDS


class TestAccentHandling:
    """Stopwords are stored without accents — input must be NFD-normalized."""

    def test_acentos_sao_stripados(self):
        """Words with accents are NOT in the set; NFD'd versions are."""
        # With accent
        assert "licitação" not in PT_BR_STOPWORDS
        # NFD-normalized (without combining marks)
        assert _nfd("licitação") == "licitacao"
        assert _nfd("licitação") in PT_BR_STOPWORDS

    def test_contratacao_sem_acento(self):
        """'contratacao' (NFD form) must be present."""
        assert "contratacao" in PT_BR_STOPWORDS

    def test_pregao_sem_acento(self):
        """'pregao' must be present."""
        assert "pregao" in PT_BR_STOPWORDS

    def test_publica_sem_acento(self):
        """'publica' must be present."""
        assert "publica" in PT_BR_STOPWORDS


class TestIsStopwordHelper:
    """Verify is_stopword() helper function."""

    def test_known_stopword_returns_true(self):
        assert is_stopword("de") is True
        assert is_stopword("para") is True
        assert is_stopword("edital") is True

    def test_non_stopword_returns_false(self):
        assert is_stopword("pavimentacao") is False
        assert is_stopword("engenharia") is False
        assert is_stopword("escola") is False

    def test_case_sensitive_lowercase(self):
        """is_stopword expects lowercase input."""
        assert is_stopword("De") is False  # must be lowercase
        assert is_stopword("de") is True

    def test_empty_string(self):
        assert is_stopword("") is False

    def test_nfd_normalized_input(self):
        """Works with NFD-normalized input."""
        nfd_licitacao = _nfd("licitação")
        assert is_stopword(nfd_licitacao) is True


class TestDuplicateDetection:
    """Verify the set has no duplicates (frozenset guarantees this)."""

    def test_frozenset_no_duplicates(self):
        """frozenset deduplicates by construction — just verify type."""
        assert isinstance(PT_BR_STOPWORDS, frozenset)

    def test_import_from_filter_package(self):
        """stopwords must be importable from the filter package."""
        from filter import PT_BR_STOPWORDS as pkged  # noqa: F811
        assert pkged is PT_BR_STOPWORDS


class TestUsageInDedup:
    """Verify the dedup module uses the new stopwords module."""

    def test_dedup_imports_from_stopwords_module(self):
        """DeduplicationEngine._FUZZY_STOPWORDS must reference PT_BR_STOPWORDS."""
        from consolidation.dedup import DeduplicationEngine
        assert DeduplicationEngine._FUZZY_STOPWORDS is PT_BR_STOPWORDS

    def test_tokenize_objeto_uses_new_stopwords(self):
        """_tokenize_objeto must filter out the new procurement stopwords."""
        from consolidation.dedup import DeduplicationEngine

        # These procurement terms were likely NOT in the old 30-word set
        # but should be filtered now.
        objeto = "Pregão eletrônico para aquisição de materiais hospitalares"
        tokens = DeduplicationEngine._tokenize_objeto(objeto)

        # NFD-normalized procurement terms should be filtered out
        assert "pregao" not in tokens, "pregao should be filtered as stopword"
        assert "eletronico" not in tokens, "eletronico should be filtered"
        assert "aquisicao" not in tokens, "aquisicao should be filtered"
        # Meaningful words should remain
        assert "materiais" in tokens
        assert "hospitalares" in tokens
