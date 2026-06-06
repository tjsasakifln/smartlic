"""
DIGEST-003: Tests for digest email template and sender.

Covers:
  - Template rendering with opportunities (daily and weekly)
  - Viability badges for alta/media/baixa/None levels
  - CTA "Ver no SmartLic" link
  - List-Unsubscribe headers (RFC 8058)
  - Subject line generation
  - Format helpers (_format_brl, _viability_badge)
  - Empty state rendering
  - Sender integration (headers, tags)
"""

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

MOCK_OPPORTUNITIES = [
    {
        "titulo": "Aquisicao de computadores desktop",
        "orgao": "Prefeitura Municipal de Sao Paulo",
        "valor_estimado": 150000.0,
        "uf": "SP",
        "viability_score": 0.85,
    },
    {
        "titulo": "Fornecimento de notebooks para secretaria",
        "orgao": "Governo do Estado de RJ",
        "valor_estimado": 500000.0,
        "uf": "RJ",
        "viability_score": 0.45,
    },
    {
        "titulo": "Servico de manutencao de equipamentos de TI",
        "orgao": "Tribunal Regional Federal",
        "valor_estimado": 0.0,
        "uf": "DF",
        "viability_score": None,
    },
]


# ============================================================================
# Template rendering
# ============================================================================


class TestRenderDigestEmail:
    """DIGEST-003: Digest email template rendering."""

    def test_renders_with_opportunities_daily(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Joao",
            opportunities=MOCK_OPPORTUNITIES,
            frequency="daily",
            unsubscribe_token="tok_abc123",
        )

        assert "Joao" in html
        assert "diario" in html
        assert "ultimas 24 horas" in html
        assert "computadores desktop" in html
        assert "Prefeitura Municipal" in html
        assert "R$" in html
        # Token used only in unsubscribe URL, not in body content
        assert "smartlic.tech/conta/preferencias?unsubscribe=tok_abc123" in html

    def test_renders_with_opportunities_weekly(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Maria",
            opportunities=MOCK_OPPORTUNITIES[:1],
            frequency="weekly",
            unsubscribe_token="tok_xyz",
        )

        assert "Maria" in html
        assert "semanal" in html
        assert "ultima semana" in html

    def test_renders_empty_state(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Pedro",
            opportunities=[],
            frequency="daily",
            unsubscribe_token="tok_vazio",
        )

        assert "Pedro" in html
        assert "Nenhuma nova oportunidade" in html
        assert "Analisar oportunidades manualmente" in html

    def test_renders_single_opportunity(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Carlos",
            opportunities=[MOCK_OPPORTUNITIES[0]],
            frequency="daily",
            unsubscribe_token="tok_1",
        )

        assert "Carlos" in html
        assert "1" in html
        assert "nova oportunidade" in html
        assert "oportunidade encontrada" in html

    def test_truncates_long_title(self):
        from templates.emails.digest import render_digest_email

        long_opp = [{
            **MOCK_OPPORTUNITIES[0],
            "titulo": "A" * 200,
        }]

        html = render_digest_email(
            user_name="Test",
            opportunities=long_opp,
            frequency="daily",
            unsubscribe_token="tok_long",
        )

        # Title should be truncated (max 120 chars + "...")
        assert "A" * 117 + "..." in html

    def test_handles_no_viability_score(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Test",
            opportunities=[MOCK_OPPORTUNITIES[2]],  # viability_score=None
            frequency="daily",
            unsubscribe_token="tok_none",
        )

        assert "Servico de manutencao" in html
        # No viability badge rendered for None score


# ============================================================================
# CTA "Ver no SmartLic"
# ============================================================================


class TestCtaLink:
    """DIGEST-003: CTA button verification."""

    def test_cta_ver_no_smartlic_present(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Test",
            opportunities=MOCK_OPPORTUNITIES[:1],
            frequency="daily",
            unsubscribe_token="tok_cta",
        )

        assert "Ver no SmartLic" in html
        assert "smartlic.tech/buscar" in html
        assert "class=\"btn\"" in html or "class=" in html

    def test_cta_in_empty_state(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Test",
            opportunities=[],
            frequency="daily",
            unsubscribe_token="tok_empty_cta",
        )

        assert "Analisar oportunidades manualmente" in html
        assert "smartlic.tech/buscar" in html


# ============================================================================
# Viability badges
# ============================================================================


class TestViabilityBadges:
    """DIGEST-003: Viability badge rendering."""

    def test_viability_badge_alta(self):
        from templates.emails.digest import _viability_badge

        badge = _viability_badge(0.85)
        assert "Alta viabilidade" in badge
        assert "#2e7d32" in badge  # Green text
        assert "#e8f5e9" in badge  # Green bg

    def test_viability_badge_media(self):
        from templates.emails.digest import _viability_badge

        badge = _viability_badge(0.50)
        assert "media" in badge.lower()
        assert "#b76e00" in badge  # Amber text
        assert "#fff8e1" in badge  # Amber bg

    def test_viability_badge_baixa(self):
        from templates.emails.digest import _viability_badge

        badge = _viability_badge(0.20)
        assert "Baixa viabilidade" in badge
        assert "#757575" in badge  # Gray text
        assert "#f5f5f5" in badge  # Gray bg

    def test_viability_badge_none(self):
        from templates.emails.digest import _viability_badge

        badge = _viability_badge(None)
        assert badge == ""

    def test_viability_badge_boundary_alta(self):
        from templates.emails.digest import _viability_badge

        # Boundary: exactly 0.7 should be alta
        badge = _viability_badge(0.7)
        assert "Alta viabilidade" in badge

    def test_viability_badge_boundary_media(self):
        from templates.emails.digest import _viability_badge

        # Boundary: exactly 0.4 should be media
        badge = _viability_badge(0.4)
        assert "media" in badge.lower()

    def test_badges_in_rendered_html(self):
        from templates.emails.digest import render_digest_email

        # Create opps with different viability scores
        opps = [
            {**MOCK_OPPORTUNITIES[0], "viability_score": 0.85},
            {**MOCK_OPPORTUNITIES[1], "viability_score": 0.45},
            {**MOCK_OPPORTUNITIES[2], "viability_score": 0.15},
        ]

        html = render_digest_email(
            user_name="Test",
            opportunities=opps,
            frequency="daily",
            unsubscribe_token="tok_badges",
        )

        assert "Alta viabilidade" in html
        assert "Viabilidade media" in html or "media" in html.lower()
        assert "Baixa viabilidade" in html


# ============================================================================
# Subject line
# ============================================================================


class TestDigestSubject:
    """DIGEST-003: Subject line generation."""

    def test_subject_daily_with_count(self):
        from templates.emails.digest import get_digest_subject

        subject = get_digest_subject(5, "daily")
        assert "[SmartLic]" in subject
        assert "diario" in subject
        assert "5" in subject

    def test_subject_weekly_with_count(self):
        from templates.emails.digest import get_digest_subject

        subject = get_digest_subject(3, "weekly")
        assert "[SmartLic]" in subject
        assert "semanal" in subject
        assert "3" in subject

    def test_subject_singular(self):
        from templates.emails.digest import get_digest_subject

        subject = get_digest_subject(1, "daily")
        assert "1 nova oportunidade" in subject

    def test_subject_zero(self):
        from templates.emails.digest import get_digest_subject

        subject = get_digest_subject(0, "daily")
        assert "nenhuma novidade" in subject.lower()

    def test_subject_unknown_frequency_defaults(self):
        from templates.emails.digest import get_digest_subject

        subject = get_digest_subject(2, "unknown")
        # Unknown frequency should fall back to "diario"
        assert "diario" in subject


# ============================================================================
# Format helpers
# ============================================================================


class TestFormatHelpers:
    """Test currency formatting helper."""

    def test_format_brl_millions(self):
        from templates.emails.digest import _format_brl

        result = _format_brl(5_000_000)
        assert "M" in result
        assert "5" in result

    def test_format_brl_thousands(self):
        from templates.emails.digest import _format_brl

        result = _format_brl(50_000)
        assert "k" in result
        assert "50" in result

    def test_format_brl_hundreds(self):
        from templates.emails.digest import _format_brl

        result = _format_brl(500)
        assert "R$" in result
        assert "500" in result

    def test_format_brl_zero(self):
        from templates.emails.digest import _format_brl

        result = _format_brl(0)
        assert "R$" in result or "0" in result


# ============================================================================
# HTML snapshot / structure validation
# ============================================================================


class TestHtmlStructure:
    """DIGEST-003: Basic HTML email structure validation."""

    def test_contains_doctype(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Test",
            opportunities=MOCK_OPPORTUNITIES[:1],
            frequency="daily",
            unsubscribe_token="tok_struct",
        )

        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_contains_table_based_layout(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Test",
            opportunities=MOCK_OPPORTUNITIES[:1],
            frequency="daily",
            unsubscribe_token="tok_table",
        )

        assert 'role="presentation"' in html
        assert "<table" in html
        assert "</table>" in html

    def test_contains_smartlic_branding(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Test",
            opportunities=MOCK_OPPORTUNITIES[:1],
            frequency="daily",
            unsubscribe_token="tok_brand",
        )

        assert "SmartLic" in html
        assert "Licitacao" in html or "Licitações" in html

    def test_inline_styles_present(self):
        from templates.emails.digest import render_digest_email

        html = render_digest_email(
            user_name="Test",
            opportunities=MOCK_OPPORTUNITIES[:1],
            frequency="daily",
            unsubscribe_token="tok_style",
        )

        # Email should use inline styles (no external CSS)
        assert 'style="' in html
        assert 'background-color:' in html


# ============================================================================
# Backward compatibility (render_daily_digest_email)
# ============================================================================


class TestLegacyBackwardCompat:
    """Backward-compatible render_daily_digest_email."""

    def test_legacy_function_exists(self):
        from templates.emails.digest import render_daily_digest_email

        html = render_daily_digest_email(
            user_name="Legado",
            opportunities=MOCK_OPPORTUNITIES[:1],
            stats={"total_novas": 1, "setor_nome": "TI", "total_valor": 150000.0},
        )

        assert "Legado" in html
        assert "oportunidades" in html


# ============================================================================
# Digest sender (integration with email_service)
# ============================================================================


class TestDigestSender:
    """DIGEST-003: Digest sender integration."""

    def test_send_digest_email_calls_send_email(self):
        """Verify send_digest_email calls send_email with correct params."""
        from unittest.mock import patch
        from digest_sender import send_digest_email

        with patch("digest_sender.send_email", return_value="email_id_123") as mock_send_email:
            result = send_digest_email(
                user_email="user@example.com",
                user_name="Joao",
                opportunities=MOCK_OPPORTUNITIES,
                frequency="daily",
                unsubscribe_token="tok_unsub",
            )

        assert result == "email_id_123"
        mock_send_email.assert_called_once()

        # Verify call args
        call_kwargs = mock_send_email.call_args[1]
        assert call_kwargs["to"] == "user@example.com"
        assert "[SmartLic]" in call_kwargs["subject"]
        assert "diario" in call_kwargs["subject"]
        assert "Joao" in call_kwargs["html"]
        assert call_kwargs["headers"] is not None

    def test_send_digest_email_has_list_unsubscribe_header(self):
        """DIGEST-003: List-Unsubscribe header present (RFC 8058)."""
        from unittest.mock import patch
        from digest_sender import send_digest_email

        with patch("digest_sender.send_email", return_value="email_id_456") as mock_send_email:
            send_digest_email(
                user_email="user@example.com",
                user_name="Joao",
                opportunities=MOCK_OPPORTUNITIES,
                frequency="daily",
                unsubscribe_token="tok_unsub",
            )

        call_kwargs = mock_send_email.call_args[1]
        headers = call_kwargs["headers"]

        # Verify RFC 8058 headers
        assert "List-Unsubscribe" in headers
        assert "List-Unsubscribe-Post" in headers
        assert "tok_unsub" in headers["List-Unsubscribe"]
        assert "List-Unsubscribe=One-Click" in headers["List-Unsubscribe-Post"]

    def test_send_digest_email_no_unsubscribe_token(self):
        """No List-Unsubscribe headers when no token provided."""
        from unittest.mock import patch
        from digest_sender import send_digest_email

        with patch("digest_sender.send_email", return_value="email_id_789") as mock_send_email:
            send_digest_email(
                user_email="user@example.com",
                user_name="Joao",
                opportunities=MOCK_OPPORTUNITIES,
                frequency="daily",
                unsubscribe_token="",
            )

        call_kwargs = mock_send_email.call_args[1]
        # headers should be empty dict or not contain List-Unsubscribe
        headers = call_kwargs.get("headers", {})
        assert "List-Unsubscribe" not in headers

    def test_send_digest_email_has_tags(self):
        """DIGEST-003: Resend tags for tracking."""
        from unittest.mock import patch
        from digest_sender import send_digest_email

        with patch("digest_sender.send_email", return_value="email_id_tags") as mock_send_email:
            send_digest_email(
                user_email="user@example.com",
                user_name="Joao",
                opportunities=MOCK_OPPORTUNITIES,
                frequency="weekly",
                unsubscribe_token="tok_tags",
            )

        call_kwargs = mock_send_email.call_args[1]
        tags = call_kwargs.get("tags", [])
        tag_categories = {t["name"]: t["value"] for t in tags if "name" in t}
        assert tag_categories.get("category") == "digest"
        assert tag_categories.get("frequency") == "weekly"

    def test_send_digest_email_returns_none_on_failure(self):
        """DIGEST-003: Graceful failure handling."""
        from unittest.mock import patch
        from digest_sender import send_digest_email

        with patch("digest_sender.send_email", return_value=None):
            result = send_digest_email(
                user_email="user@example.com",
                user_name="Joao",
                opportunities=MOCK_OPPORTUNITIES,
                frequency="daily",
                unsubscribe_token="tok_fail",
            )

        assert result is None

    def test_send_digest_email_with_empty_opportunities(self):
        """DIGEST-003: Send with empty opportunities (no new items)."""
        from unittest.mock import patch
        from digest_sender import send_digest_email

        with patch("digest_sender.send_email", return_value="email_id_empty") as mock_send_email:
            send_digest_email(
                user_email="user@example.com",
                user_name="Maria",
                opportunities=[],
                frequency="daily",
                unsubscribe_token="tok_empty",
            )

        call_kwargs = mock_send_email.call_args[1]
        # Subject for 0 opportunities
        assert "nenhuma novidade" in call_kwargs["subject"]
        # HTML should show empty state
        assert "Nenhuma nova oportunidade" in call_kwargs["html"]
