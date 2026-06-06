"""
STORY-278 AC3 + DIGEST-005 (#1421): Daily digest email template.

Renders a mobile-responsive email showing top opportunities with
viability badges — the key SmartLic differentiator no competitor has.

DIGEST-005 adds:
- Tracking pixel (1x1 transparent GIF) for open detection
- Click tracking on the CTA button (wraps URL in /api/email/click/{id}?url=...)

Design:
- Stats summary (X new opportunities in your sector today)
- Top 10 opportunities with viability badge per item
- CTA: "Ver todas as oportunidades" → /buscar?auto=true
- Mobile-responsive (max-width 600px, inline CSS — same pattern as trial.py)
"""

import os
from urllib.parse import quote

from templates.emails.base import email_base, SMARTLIC_GREEN, FRONTEND_URL

# Backend URL for tracking pixel and click tracking
BACKEND_URL = os.getenv("BACKEND_URL", "https://smartlic-backend-production.up.railway.app")


# Viability badge colors and labels
_VIABILITY_COLORS = {
    "alta": {"bg": "#e8f5e9", "text": "#2e7d32", "label": "Alta viabilidade"},
    "media": {"bg": "#fff8e1", "text": "#f57f17", "label": "Viabilidade média"},
    "baixa": {"bg": "#ffebee", "text": "#c62828", "label": "Baixa viabilidade"},
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

    Args:
        score: Viability score 0.0-1.0, or None if not assessed.

    Returns:
        HTML string for the badge.
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
        opp: Dict with keys: titulo, orgao, valor_estimado, uf, viability_score, data_publicacao.
        index: Row number (1-based).

    Returns:
        HTML table row string.
    """
    titulo = opp.get("titulo", "Sem título")
    if len(titulo) > 120:
        titulo = titulo[:117] + "..."

    orgao = opp.get("orgao", "Órgão não informado")
    if len(orgao) > 60:
        orgao = orgao[:57] + "..."

    valor = opp.get("valor_estimado", 0.0) or 0.0
    uf = opp.get("uf", "—")
    viability_score = opp.get("viability_score")
    badge = _viability_badge(viability_score)

    valor_display = _format_brl(valor) if valor > 0 else "Valor não informado"

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


def _tracking_pixel(tracking_id: str, backend_url: str) -> str:
    """Render a 1x1 transparent tracking pixel for open detection.

    Args:
        tracking_id: UUID tracking identifier.
        backend_url: Backend base URL for tracking endpoint.

    Returns:
        HTML img tag string.
    """
    tracking_url = f"{backend_url}/api/email/open/{tracking_id}"
    return (
        f'<img src="{tracking_url}" width="1" height="1" '
        f'alt="" style="display:none;width:1px;height:1px;" />'
    )


def _click_tracking_url(tracking_id: str, target_url: str, backend_url: str) -> str:
    """Build a click-tracked URL wrapping the target.

    Args:
        tracking_id: UUID tracking identifier.
        target_url: The original destination URL.
        backend_url: Backend base URL for click tracking endpoint.

    Returns:
        Click tracking URL string.
    """
    encoded = quote(target_url, safe="")
    return f"{backend_url}/api/email/click/{tracking_id}?url={encoded}"


def render_daily_digest_email(
    user_name: str,
    opportunities: list[dict],
    stats: dict,
    tracking_id: str | None = None,
    backend_url: str | None = None,
) -> str:
    """Render the daily digest email.

    STORY-278 AC3: Mobile-responsive email with viability badges.
    DIGEST-005: Optional tracking_id for open/click tracking pixel.

    Args:
        user_name: User's display name.
        opportunities: List of dicts with keys:
            titulo, orgao, valor_estimado, uf, viability_score, data_publicacao.
        stats: Dict with keys:
            total_novas (int), setor_nome (str), total_valor (float).
        tracking_id: UUID for open/click tracking. If None, no tracking.
        backend_url: Backend base URL for tracking endpoints (defaults to env).

    Returns:
        Complete HTML email string.
    """
    backend_url = backend_url or BACKEND_URL
    total_novas = stats.get("total_novas", len(opportunities))
    setor_nome = stats.get("setor_nome", "seu setor")
    total_valor = stats.get("total_valor", 0.0)

    # Build opportunity rows
    opp_rows = ""
    for i, opp in enumerate(opportunities):
        opp_rows += _render_opportunity_row(opp, i + 1)

    # Stats summary line
    if total_valor > 0:
        stats_line = (
            f"{total_novas} novas oportunidades no setor de {setor_nome} hoje, "
            f"totalizando {_format_brl(total_valor)}."
        )
    else:
        stats_line = f"{total_novas} novas oportunidades no setor de {setor_nome} hoje."

    # Build CTA URL (with optional click tracking)
    manual_btn_url = FRONTEND_URL + "/buscar"
    cta_url = FRONTEND_URL + "/buscar?auto=true"
    if tracking_id and backend_url:
        manual_btn_url = _click_tracking_url(tracking_id, manual_btn_url, backend_url)
        cta_url = _click_tracking_url(tracking_id, cta_url, backend_url)

    # Tracking pixel (invisible 1x1)
    pixel_html = ""
    if tracking_id and backend_url:
        pixel_html = _tracking_pixel(tracking_id, backend_url)

    # Empty state
    if not opportunities:
        body = f"""
        <h1 style="color: #333; font-size: 22px; margin: 0 0 16px;">
          Bom dia, {user_name}!
        </h1>
        <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 24px;">
          Nenhuma nova oportunidade encontrada no seu setor hoje.
          Continuaremos monitorando e avisaremos assim que houver novidades.
        </p>
        <p style="text-align: center; margin: 24px 0 16px;">
          <a href="{manual_btn_url}" class="btn"
             style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
            Fazer análise manual
          </a>
        </p>
        {pixel_html}
        """
        return email_base(
            title="Resumo diário — SmartLic",
            body_html=body,
            is_transactional=False,
            unsubscribe_url=f"{FRONTEND_URL}/conta",
        )

    body = f"""
    <h1 style="color: #333; font-size: 22px; margin: 0 0 8px;">
      Bom dia, {user_name}!
    </h1>
    <p style="color: #555; font-size: 16px; line-height: 1.6; margin: 0 0 16px;">
      {stats_line}
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
            oportunidades encontradas
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
            Melhores oportunidades
          </span>
        </td>
      </tr>
      {opp_rows}
    </table>

    <!-- CTA (with optional click tracking) -->
    <p style="text-align: center; margin: 24px 0 16px;">
      <a href="{cta_url}" class="btn"
         style="display: inline-block; padding: 14px 32px; background-color: {SMARTLIC_GREEN}; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">
        Ver todas as oportunidades
      </a>
    </p>

    <p style="color: #888; font-size: 12px; text-align: center; margin: 16px 0 0;">
      Os indicadores de viabilidade mostram a compatibilidade da oportunidade com seu perfil.
      <br>
      Para ajustar suas preferências de alerta,
      <a href="{FRONTEND_URL}/conta" style="color: #888; text-decoration: underline;">acesse sua conta</a>.
    </p>

    {pixel_html}
    """

    return email_base(
        title=f"{total_novas} oportunidades no seu setor — SmartLic",
        body_html=body,
        is_transactional=False,
        unsubscribe_url=f"{FRONTEND_URL}/conta",
    )
