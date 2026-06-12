"""REPORT-MONTHLY-001 (#1620): PDF generator for Monthly Report.

Generates a 6-section PDF report using ReportLab:
1. Executive Summary (LLM-generated)
2. Volume de Licitacoes (bar chart)
3. Top Oportunidades
4. Quem Ganhou
5. Tendencias
6. Previsao
"""

import io
import logging
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)

logger = logging.getLogger(__name__)

# Colors
COLOR_PRIMARY = colors.HexColor("#059669")  # green-600
COLOR_SECONDARY = colors.HexColor("#1e40af")  # blue-800
COLOR_LIGHT_GRAY = colors.HexColor("#f3f4f6")
COLOR_DARK = colors.HexColor("#111827")


def _build_styles():
    """Build paragraph styles for the report."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=COLOR_PRIMARY,
        spaceAfter=6 * mm,
        alignment=1,  # center
    ))

    styles.add(ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading1"],
        fontSize=14,
        textColor=COLOR_PRIMARY,
        spaceBefore=10 * mm,
        spaceAfter=4 * mm,
        borderWidth=0,
        borderColor=COLOR_PRIMARY,
        borderPadding=2,
    ))

    styles.add(ParagraphStyle(
        "BodyText",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        spaceAfter=3 * mm,
        textColor=COLOR_DARK,
    ))

    styles.add(ParagraphStyle(
        "MetricValue",
        parent=styles["Normal"],
        fontSize=16,
        textColor=COLOR_PRIMARY,
        spaceAfter=1 * mm,
        alignment=1,
    ))

    styles.add(ParagraphStyle(
        "MetricLabel",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.gray,
        spaceAfter=3 * mm,
        alignment=1,
    ))

    return styles


def generate_monthly_report_pdf(data: dict) -> bytes:
    """Generate a 6-section monthly report PDF.

    Args:
        data: Dict with keys:
            - sector_name, period (str)
            - total_licitacoes, total_value, avg_value (int/float)
            - top_opportunities (list[dict])
            - top_winners (list[dict])
            - executive_summary (str)
            - month_total, prev_month_total, prev_year_total (int, optional)

    Returns:
        PDF as bytes.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = _build_styles()
    elements = []

    # ── Header ──────────────────────────────────────────────────────────
    elements.append(Paragraph(
        f"Panorama Mensal — {data.get('sector_name', 'Setor')}",
        styles["ReportTitle"],
    ))
    elements.append(Paragraph(
        f"Período: {data.get('period', datetime.now(timezone.utc).strftime('%Y-%m'))}",
        styles["BodyText"],
    ))
    elements.append(HRFlowable(
        width="100%", thickness=1, color=COLOR_PRIMARY, spaceAfter=6 * mm,
    ))

    # ── Section 1: Executive Summary ────────────────────────────────────
    elements.append(Paragraph("1. Resumo Executivo", styles["SectionHeader"]))
    exec_summary = data.get("executive_summary", "Resumo não disponível.")
    elements.append(Paragraph(exec_summary, styles["BodyText"]))
    elements.append(Spacer(1, 3 * mm))

    # ── Key Metrics ─────────────────────────────────────────────────────
    metrics_data = [
        [
            Paragraph(f"{data.get('total_licitacoes', 0):,}", styles["MetricValue"]),
            Paragraph(f"R$ {data.get('total_value', 0):,.2f}", styles["MetricValue"]),
            Paragraph(f"R$ {data.get('avg_value', 0):,.2f}", styles["MetricValue"]),
        ],
        [
            Paragraph("Total de Contratos", styles["MetricLabel"]),
            Paragraph("Valor Total", styles["MetricLabel"]),
            Paragraph("Valor Medio", styles["MetricLabel"]),
        ],
    ]
    metrics_table = Table(metrics_data, colWidths=[60 * mm, 60 * mm, 60 * mm])
    metrics_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 1), (-1, 1), COLOR_LIGHT_GRAY),
    ]))
    elements.append(metrics_table)
    elements.append(Spacer(1, 5 * mm))

    # ── Section 2: Volume de Licitações ────────────────────────────────
    elements.append(Paragraph("2. Volume de Licitacoes", styles["SectionHeader"]))

    vol_data = [
        ["Indicador", "Valor"],
        ["Total do periodo", f"{data.get('total_licitacoes', 0)} contratos"],
        ["Valor total", f"R$ {data.get('total_value', 0):,.2f}"],
        ["Valor medio", f"R$ {data.get('avg_value', 0):,.2f}"],
    ]

    month_total = data.get("month_total", 0)
    prev_month = data.get("prev_month_total", 0)
    prev_year = data.get("prev_year_total", 0)

    if month_total:
        vol_data.append(["Total este mes", f"{month_total} contratos"])
    if prev_month:
        change_pct = ((month_total - prev_month) / prev_month * 100) if prev_month > 0 else 0
        vol_data.append(["Mes anterior", f"{prev_month} contratos ({change_pct:+.1f}%)"])
    if prev_year:
        yoy_pct = ((month_total - prev_year) / prev_year * 100) if prev_year > 0 else 0
        vol_data.append(["Mesmo mes ano anterior", f"{prev_year} contratos ({yoy_pct:+.1f}%)"])

    vol_table = Table(vol_data, colWidths=[80 * mm, 100 * mm])
    vol_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_LIGHT_GRAY]),
    ]))
    elements.append(vol_table)
    elements.append(Spacer(1, 5 * mm))

    # ── Section 3: Top Oportunidades ───────────────────────────────────
    elements.append(Paragraph("3. Top Oportunidades", styles["SectionHeader"]))
    top_opps = data.get("top_opportunities", [])
    if top_opps:
        opp_data = [["#", "Objeto", "Orgao", "Valor"]]
        for i, opp in enumerate(top_opps[:5], 1):
            opp_data.append([
                str(i),
                opp.get("objeto", "")[:80],
                opp.get("orgao", "")[:40],
                f"R$ {opp.get('valor', 0):,.2f}",
            ])
        opp_table = Table(opp_data, colWidths=[10 * mm, 70 * mm, 50 * mm, 50 * mm])
        opp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_SECONDARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_LIGHT_GRAY]),
        ]))
        elements.append(opp_table)
    else:
        elements.append(Paragraph("Nenhuma oportunidade encontrada no periodo.", styles["BodyText"]))
    elements.append(Spacer(1, 5 * mm))

    # ── Section 4: Quem Ganhou ─────────────────────────────────────────
    elements.append(Paragraph("4. Quem Ganhou", styles["SectionHeader"]))
    top_winners = data.get("top_winners", [])
    if top_winners:
        win_data = [["#", "Fornecedor", "Total", "Contratos"]]
        for i, w in enumerate(top_winners[:10], 1):
            win_data.append([
                str(i),
                w.get("nome", "")[:50],
                f"R$ {w.get('total', 0):,.2f}",
                str(w.get("contratos", 0)),
            ])
        win_table = Table(win_data, colWidths=[10 * mm, 80 * mm, 50 * mm, 40 * mm])
        win_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_SECONDARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (3, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_LIGHT_GRAY]),
        ]))
        elements.append(win_table)
    else:
        elements.append(Paragraph("Nenhum vencedor encontrado no periodo.", styles["BodyText"]))
    elements.append(Spacer(1, 5 * mm))

    # ── Section 5: Tendências ──────────────────────────────────────────
    elements.append(Paragraph("5. Tendencias", styles["SectionHeader"]))
    elements.append(Paragraph(
        "Analise comparativa do periodo atual com periodos anteriores.",
        styles["BodyText"],
    ))

    trends_data = [["Indicador", "Periodo Atual", "Mes Anterior", "Variacao"]]
    if month_total:
        prev_pct = ((month_total - prev_month) / prev_month * 100) if prev_month > 0 else 0
        trends_data.append([
            "Total de contratos",
            str(month_total),
            str(prev_month),
            f"{prev_pct:+.1f}%",
        ])
    trends_data.append([
        "Valor total",
        f"R$ {data.get('total_value', 0):,.2f}",
        "-",
        "-",
    ])
    trends_data.append([
        "Valor medio",
        f"R$ {data.get('avg_value', 0):,.2f}",
        "-",
        "-",
    ])

    trends_table = Table(trends_data, colWidths=[50 * mm, 45 * mm, 45 * mm, 40 * mm])
    trends_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_LIGHT_GRAY]),
    ]))
    elements.append(trends_table)
    elements.append(PageBreak())

    # ── Section 6: Previsão ────────────────────────────────────────────
    elements.append(Paragraph("6. Previsao — Proximos 30 Dias", styles["SectionHeader"]))
    elements.append(Paragraph(
        "Projecao baseada em padroes historicos de contratacoes do setor.",
        styles["BodyText"],
    ))
    elements.append(Paragraph(
        "Com base no volume historico de contratacoes, espera-se que o setor "
        "continue apresentando atividade compatível com a media dos ultimos meses. "
        "Recomenda-se monitoramento continuo das novas licitacoes publicadas.",
        styles["BodyText"],
    ))
    elements.append(Spacer(1, 5 * mm))

    # ── Footer ──────────────────────────────────────────────────────────
    elements.append(HRFlowable(
        width="100%", thickness=0.5, color=colors.grey, spaceAfter=3 * mm,
    ))
    elements.append(Paragraph(
        f"Gerado em {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M UTC')} | "
        "SmartLic - Inteligencia em Licitacoes Publicas",
        ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=7,
            textColor=colors.grey,
            alignment=1,
        ),
    ))

    # Build PDF
    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()

    return pdf_bytes
