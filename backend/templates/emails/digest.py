"""
DIGEST-003: Digest email template -- B2G copy, viability badges, CTA.

Renders a mobile-responsive digest email (daily or weekly frequency) with:
- Setor + N oportunidades novas header
- Viability badges per opportunity (alta/verde, media/amarelo, baixa/cinza)
- CTA "Ver no SmartLic" linking to /buscar
- Footer with unsubscribe link (token-based, RFC 8058 compatible)

Builds on STORY-278 AC3 daily digest template.
"""

from templates.emails.base import email_base, SMARTLIC_GREEN, FRONTEND_URL

# DIGEST-003: Viability badge colors and labels
# alta = verde, media = amarelo, baixa = cinza
_VIABILITY_COLORS = {
    "alta": {"bg": "#e8f5e9", "text": "#2e7d32", "label": "Alta viabilidade"},
    "media": {"bg": "#fff8e1", "text": "#b76e00", "label": "Viabilidade media"},
    "baixa": {"bg": "#f5f5f5", "text": "#757575", "label": "Baixa viabilidade"},
}

# Frequency label mapping
_FREQUENCY_LABELS = {
    "daily": "diario",
    "weekly": "semanal",
}

_FREQUENCY_PERIOD = {
    "daily": "nas ultimas 24 horas",
    "weekly": "na ultima semana",
}


def _format_brl(value: float) -> str:
    """Format a float as Brazilian Real currency string."""
    if value >= 1_000_000:
        return f"R$ {value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"R$ {value / 1_000:.0f}k"
    return f"R$ {value:,.0f}".replace(",", ".")


def _viability_badge(score: float | None) -> str:
    """Render an inline viability badge based on score.

    DIGEST-003: alta=verde, media=amarelo, baixa=cinza.

    Args:
        score: Viability score 0.0-1.0, or None if not assessed.

    Returns:
        HTML string for the badge (inline-styled span).
    """
    if score is None:
        return ""

    if score >= 0.7:
        style = _VIABILITY_COLORS["alta"]
    elif score >= 0.4:
        style = _VIABILITY_COLORS["media"]
    else:
        style = _VIABILITY_COLORS["baixa"]

    return (
        f'<span style="display: inline-block; padding: 2px 8px; '
        f'background-color: {style["bg"]}; color: {style["text"]}; '
        f'border-radius: 4px; font-size: 11px; font-weight: 600; '
        f'line-height: 1.4;">{style["label"]}</span>'
    )


def _render_opportunity_row(opp: dict, index: int) -> str:
    """Render a single opportunity row in the digest table.

    Args:
        opp: Dict with keys: titulo, orgao, valor_estimado, uf, viability_score.
        index: Row number (1-based).

    Returns:
        HTML table row string.
    """
    titulo = opp.get("titulo", "Sem titulo")
    if len(titulo) > 120:
        titulo = titulo[:117] + "..."

    orgao = opp.get("orgao", "Orgao nao informado")
    if len(orgao) > 60:
        orgao = orgao[:57] + "..."

    valor = opp.get("valor_estimado", 0.0) or 0.0
    uf = opp.get("uf", "—")
    viability_score = opp.get("viability_score")
    badge = _viability_badge(viability_score)

    valor_display = _format_brl(valor) if valor > 0 else "Valor nao informado"

    bg_color = "#ffffff" if index % 2 == 1 else "#f9f9f9"

    return f"""
    <tr style="background-color: {bg_color};">
      <td style="padding: 12px 16px; border-bottom: 1px solid #eee; vertical-align: top;">
        <p style="margin: 0 0 4px; font-size: 14px; color: #333; font-weight: 600; line-height: 1.4;">
          {titulo}
        </p>
        <p style="margin: 0 0 4px; font-size: 13px; color: #666; line-height: 1.3;">
          {orgao} &mdash; {uf}
        </p>
        <p style="margin: 0; font-size: 13px;">
          <span style="color: {SMARTLIC_GREEN}; font-weight: 600;">{valor_display}</span>
          &nbsp;&nbsp;{badge}
        </p>
      </td>
    </tr>"""


def render_digest_email(
    user_name: str,
    opportunities: list[dict],
    frequency: str = "daily",
    unsubscribe_token: str = "",
) -> str:
    """Render the digest email HTML (daily or weekly).

    DIGEST-003: B2G copy, viability badges, CTA "Ver no SmartLic",
    token-based unsubscribe in footer.

    Args:
        user_name: User's display name.
        opportunities: List of dicts with keys:
            titulo, orgao, valor_estimado, uf, viability_score.
        frequency: "daily" or "weekly".
        unsubscribe_token: Token for one-click unsubscribe URL.

    Returns:
        Complete HTML email string.
    """
    total_novas = len(opportunities)
    freq_label = _FREQUENCY_LABELS.get(frequency, "diario")
    period_label = _FREQUENCY_PERIOD.get(frequency, "nas ultimas 24 horas")

    # Build unsubscribe URL (RFC 8058 compatible)
    unsubscribe_url = ""
    if unsubscribe_token:
        unsubscribe_url = f"{FRONTEND_URL}/conta/preferencias?unsubscribe={unsubscribe_token}"

    # Empty state
    if not opportunities:
        body = f"""
        <h1 style="color: #333; font-size: 22px; margin: 0 0 16px;">
          Ola, {user_name}!
        </h1>
        <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">
          Nenhuma nova oportunidade encontrada {period_label}.
          Continuaremos monitorando e avisaremos assim que houver novidades.
        </p>
        <p style="text-align: center; margin: 24px 0 16px;">
          <a href="{FRONTEND_URL}/buscar" class="btn"
             style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
            Analisar oportunidades manualmente
          </a>
        </p>
        """
        return email_base(
            title=f"Resumo {freq_label} — SmartLic",
            body_html=body,
            is_transactional=False,
            unsubscribe_url=unsubscribe_url,
        )

    # Build opportunity rows
    opp_rows = ""
    for i, opp in enumerate(opportunities):
        opp_rows += _render_opportunity_row(opp, i + 1)

    # Plural forms
    s_plural = "s" if total_novas != 1 else ""
    body = f"""
    <h1 style="color: #333; font-size: 22px; margin: 0 0 8px;">
      Ola, {user_name}!
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      Seu resumo <strong>{freq_label}</strong> de oportunidades <strong>{period_label}</strong>:
      <strong>{total_novas}</strong> nova{s_plural} oportunidade{s_plural} encontrada{s_plural}.
    </p>

    <!-- Stats highlight bar -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background-color: #e8f5e9; border-radius: 8px; margin: 0 0 24px;">
      <tr>
        <td style="padding: 12px 16px; text-align: center;">
          <span style="color: {SMARTLIC_GREEN}; font-size: 24px; font-weight: 700;">
            {total_novas}
          </span>
          <span style="color: #555; font-size: 14px; margin-left: 8px;">
            {"oportunidade" if total_novas == 1 else "oportunidades"} encontrada{"s" if total_novas != 1 else ""}
          </span>
        </td>
      </tr>
    </table>

    <!-- Opportunities table -->
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="border: 1px solid #eee; border-radius: 8px; overflow: hidden; margin: 0 0 24px;">
      <tr>
        <td style="padding: 10px 16px; background-color: #f5f5f5; border-bottom: 2px solid #eee;">
          <span style="font-size: 13px; font-weight: 600; color: #555; text-transform: uppercase; letter-spacing: 0.5px;">
            Oportunidades encontradas
          </span>
        </td>
      </tr>
      {opp_rows}
    </table>

    <!-- DIGEST-003: CTA "Ver no SmartLic" -->
    <p style="text-align: center; margin: 24px 0 16px;">
      <a href="{FRONTEND_URL}/buscar" class="btn"
         style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
        Ver no SmartLic &rarr;
      </a>
    </p>

    <!-- Footer: viability explanation + preferences -->
    <p style="color: #888; font-size: 12px; text-align: center; margin: 16px 0 0;">
      Os indicadores de viabilidade consideram modalidade, prazo, valor e geografia
      para mostrar a compatibilidade da oportunidade com seu perfil B2G.
    </p>
    """

    return email_base(
        title=f"Resumo {freq_label} — {total_novas} oportunidades — SmartLic",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=unsubscribe_url,
    )


# ---------------------------------------------------------------------------
# Backward compatibility: keep render_daily_digest_email for existing callers
# ---------------------------------------------------------------------------

def render_daily_digest_email(
    user_name: str,
    opportunities: list[dict],
    stats: dict,
) -> str:
    """Render the daily digest email (legacy interface).

    Delegates to render_digest_email() with frequency="daily".
    The stats dict is used for backward compatibility but the new
    renderer derives display values directly from opportunities.

    Args:
        user_name: User's display name.
        opportunities: List of opportunity dicts.
        stats: Legacy stats dict (total_novas, setor_nome, total_valor).

    Returns:
        Complete HTML email string.
    """
    return render_digest_email(
        user_name=user_name,
        opportunities=opportunities,
        frequency="daily",
        unsubscribe_token="",
    )


# ---------------------------------------------------------------------------
# Subject line helpers
# ---------------------------------------------------------------------------

def get_digest_subject(
    total_count: int,
    frequency: str = "daily",
) -> str:
    """Generate the email subject line for a digest.

    DIGEST-003: "[SmartLic] Seu resumo [diario|semanal] -
    [N] novas oportunidades"

    Args:
        total_count: Number of new opportunities.
        frequency: "daily" or "weekly".

    Returns:
        Email subject string.
    """
    freq_label = _FREQUENCY_LABELS.get(frequency, "diario")
    if total_count == 0:
        return f"[SmartLic] Seu resumo {freq_label} — nenhuma novidade"
    if total_count == 1:
        return f"[SmartLic] Seu resumo {freq_label} — 1 nova oportunidade"
    return f"[SmartLic] Seu resumo {freq_label} — {total_count} novas oportunidades"
