"""pdf_generator_intel_report.py — INTEL-REPORT-001: Raio-X do Concorrente PDF.

Generates an 8-12 page A4 PDF from data returned by the `cnpj_supplier_intel` RPC.
Follows the same ReportLab conventions as pdf_generator_edital.py.

Usage:
    >>> from pdf_generator_intel_report import generate_cnpj_report
    >>> bio = generate_cnpj_report(data)
    >>> pdf_bytes = bio.getvalue()
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Brand colors — kept in sync with pdf_generator_edital.py
# ---------------------------------------------------------------------------
BRAND_DARK_BLUE = colors.HexColor("#1B3A5C")
BRAND_MEDIUM_BLUE = colors.HexColor("#2C5F8A")
BRAND_LIGHT_BLUE = colors.HexColor("#E8F0FE")
BRAND_ACCENT = colors.HexColor("#3B82F6")

VIABILITY_GREEN = colors.HexColor("#16A34A")
VIABILITY_YELLOW = colors.HexColor("#CA8A04")
VIABILITY_GRAY = colors.HexColor("#64748B")

TABLE_HEADER_BG = BRAND_DARK_BLUE
TABLE_ALT_ROW = colors.HexColor("#F8FAFC")
TABLE_BORDER = colors.HexColor("#CBD5E1")
METRIC_BOX_BG = colors.HexColor("#EFF6FF")  # blue-50

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2 * cm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

FOOTER_TEXT = "SmartLic Intelligence — smartlic.tech | Dados: PNCP | Atualizado em {data}"

ESFERA_LABELS = {
    "F": "Federal",
    "E": "Estadual",
    "M": "Municipal",
    "D": "Distrital",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize(value: Any) -> str:
    if value is None:
        return ""
    return ILLEGAL_CHARACTERS_RE.sub(" ", html.escape(str(value)))


def _fmt_currency(value: float | int | None) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
    except (ValueError, TypeError):
        return "—"
    if v == 0:
        return "R$ 0,00"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_int(value: Any) -> str:
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "—"


def _format_date(date_str: str | None) -> str:
    if not date_str:
        return "—"
    try:
        parts = date_str.split("T")[0].split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except Exception:
        return _sanitize(date_str)


def _trunc(text: Any, max_chars: int = 80) -> str:
    s = _sanitize(text)
    if len(s) <= max_chars:
        return s
    return s[:max_chars - 1] + "…"


def _build_styles() -> dict:
    base = getSampleStyleSheet()

    def _ps(name: str, **kw) -> ParagraphStyle:
        parent = kw.pop("parent", base["Normal"])
        return ParagraphStyle(name, parent=parent, **kw)

    return {
        "title": _ps(
            "IRTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=BRAND_DARK_BLUE,
            alignment=TA_CENTER,
            spaceAfter=6 * mm,
        ),
        "subtitle": _ps(
            "IRSubtitle",
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=BRAND_MEDIUM_BLUE,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "section": _ps(
            "IRSection",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=BRAND_DARK_BLUE,
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
        ),
        "body": _ps(
            "IRBody",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
            spaceAfter=2 * mm,
        ),
        "caption": _ps(
            "IRCaption",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
        "label": _ps(
            "IRLabel",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=BRAND_DARK_BLUE,
        ),
        "value": _ps(
            "IRValue",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#334155"),
        ),
        "metric_val": _ps(
            "IRMetricVal",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=BRAND_DARK_BLUE,
            alignment=TA_CENTER,
        ),
        "metric_label": _ps(
            "IRMetricLabel",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
        "warning": _ps(
            "IRWarning",
            fontName="Helvetica-Oblique",
            fontSize=7,
            leading=9,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
        "tbl_header": _ps(
            "IRTblHeader",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.white,
        ),
        "tbl_cell": _ps(
            "IRTblCell",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#334155"),
        ),
        "tbl_cell_num": _ps(
            "IRTblCellNum",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#334155"),
            alignment=TA_RIGHT,
        ),
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_cover(data: dict, styles: dict) -> list:
    """Page 1 — Cover."""
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    cnpj = _sanitize(data.get("cnpj", ""))
    supplier_name = _sanitize(data.get("fornecedor_nome") or data.get("nome_fornecedor") or "Fornecedor")
    periodo = _sanitize(data.get("periodo_analisado") or "Últimos 12 meses")

    story = []

    # Logo header
    story.append(Spacer(1, 15 * mm))
    story.append(Paragraph(
        '<font color="#1B3A5C"><b>SmartLic</b></font>'
        '<font color="#3B82F6"> Intelligence</font>',
        ParagraphStyle(
            "CoverLogo",
            parent=styles["title"],
            fontSize=18,
            spaceBefore=0,
            spaceAfter=2 * mm,
        ),
    ))
    story.append(HRFlowable(
        width=CONTENT_WIDTH,
        thickness=2,
        color=BRAND_ACCENT,
        spaceAfter=6 * mm,
    ))

    story.append(Paragraph("Raio-X do Concorrente", styles["title"]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(supplier_name, styles["subtitle"]))
    if cnpj:
        story.append(Paragraph(f"CNPJ: {cnpj}", styles["caption"]))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Período analisado: {periodo}", styles["caption"]))
    story.append(Paragraph(f"Data de geração: {now_str}", styles["caption"]))

    story.append(Spacer(1, 12 * mm))
    story.append(HRFlowable(
        width=CONTENT_WIDTH,
        thickness=0.5,
        color=TABLE_BORDER,
        spaceAfter=4 * mm,
    ))
    story.append(Paragraph(
        "Análise gerada por IA — dados auditáveis no apêndice",
        styles["warning"],
    ))

    story.append(PageBreak())
    return story


def _build_executive_summary(data: dict, styles: dict) -> list:
    """Page 2 — Executive Summary."""
    story = []
    story.append(Paragraph("Sumário Executivo", styles["section"]))

    # Narrative paragraph
    narrative = data.get("narrative") or {}
    if isinstance(narrative, dict):
        padrao = _sanitize(narrative.get("padrao_competitivo", ""))
        clientes = _sanitize(narrative.get("principais_clientes", ""))
        setores = _sanitize(narrative.get("setores_foco", ""))
        atencao = _sanitize(narrative.get("pontos_atencao", ""))
        narrative_text = " ".join(filter(None, [padrao, clientes, setores, atencao]))
    else:
        narrative_text = _sanitize(str(narrative))

    if not narrative_text:
        # deterministic fallback
        total_c = data.get("total_contratos") or 0
        valor_t = data.get("valor_total") or 0.0
        narrative_text = (
            f"Fornecedor com {_fmt_int(total_c)} contrato(s) registrado(s) no PNCP, "
            f"totalizando {_fmt_currency(valor_t)}. "
            "Consulte as seções seguintes para detalhes sobre órgãos compradores, "
            "distribuição geográfica e evolução temporal."
        )

    story.append(Paragraph(narrative_text, styles["body"]))
    story.append(Spacer(1, 4 * mm))

    # 4 metric boxes
    total_contratos = data.get("total_contratos") or 0
    valor_total = data.get("valor_total") or 0.0
    ticket_medio = (valor_total / total_contratos) if total_contratos > 0 else 0.0
    ufs_ativas = data.get("ufs_ativas") or len(data.get("uf_breakdown") or {})

    metrics = [
        (_fmt_int(total_contratos), "Total de Contratos"),
        (_fmt_currency(valor_total), "Valor Total"),
        (_fmt_currency(ticket_medio), "Ticket Médio"),
        (str(ufs_ativas), "UFs Ativas"),
    ]

    col_w = CONTENT_WIDTH / 4

    metric_rows = [[
        Table(
            [[Paragraph(v, styles["metric_val"])], [Paragraph(lbl, styles["metric_label"])]],
            colWidths=[col_w - 4 * mm],
        )
        for v, lbl in metrics
    ]]

    metric_tbl = Table(metric_rows, colWidths=[col_w] * 4)
    metric_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), METRIC_BOX_BG),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(metric_tbl)
    story.append(PageBreak())
    return story


def _table_style_standard(num_rows: int) -> TableStyle:
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.3, TABLE_BORDER),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i in range(1, num_rows):
        if i % 2 == 0:
            commands.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW))
    return TableStyle(commands)


def _build_top_orgaos(data: dict, styles: dict) -> list:
    """Page 3 — Top 10 Órgãos Compradores."""
    story = []
    story.append(Paragraph("Top 10 Órgãos Compradores", styles["section"]))

    orgaos = data.get("orgaos_top") or []
    if not orgaos:
        story.append(Paragraph("Nenhum dado disponível.", styles["body"]))
        story.append(PageBreak())
        return story

    header = [
        Paragraph("Órgão", styles["tbl_header"]),
        Paragraph("UF", styles["tbl_header"]),
        Paragraph("Nº Contratos", styles["tbl_header"]),
        Paragraph("Valor Total", styles["tbl_header"]),
        Paragraph("% Share", styles["tbl_header"]),
    ]

    valor_total_geral = sum(float(o.get("valor_total") or 0) for o in orgaos)

    rows = [header]
    for o in orgaos[:10]:
        vt = float(o.get("valor_total") or 0)
        pct = (vt / valor_total_geral * 100) if valor_total_geral > 0 else 0.0
        rows.append([
            Paragraph(_trunc(o.get("orgao_nome") or o.get("orgao") or "—", 50), styles["tbl_cell"]),
            Paragraph(_sanitize(o.get("uf") or "—"), styles["tbl_cell"]),
            Paragraph(_fmt_int(o.get("total_contratos") or o.get("n_contratos") or 0), styles["tbl_cell_num"]),
            Paragraph(_fmt_currency(vt), styles["tbl_cell_num"]),
            Paragraph(_fmt_pct(pct), styles["tbl_cell_num"]),
        ])

    col_widths = [
        CONTENT_WIDTH * 0.40,
        CONTENT_WIDTH * 0.08,
        CONTENT_WIDTH * 0.14,
        CONTENT_WIDTH * 0.24,
        CONTENT_WIDTH * 0.14,
    ]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)
    story.append(PageBreak())
    return story


def _build_temporal_evolution(data: dict, styles: dict) -> list:
    """Page 4 — Evolução Temporal (table-based, no matplotlib dependency)."""
    story = []
    story.append(Paragraph("Evolução Temporal", styles["section"]))

    temporal = data.get("evolucao_temporal") or data.get("temporal_evolution") or []
    if not temporal:
        story.append(Paragraph("Nenhum dado temporal disponível.", styles["body"]))
        story.append(PageBreak())
        return story

    header = [
        Paragraph("Mês/Ano", styles["tbl_header"]),
        Paragraph("Nº Contratos", styles["tbl_header"]),
        Paragraph("Valor Total", styles["tbl_header"]),
    ]

    rows = [header]
    for entry in temporal:
        mes = _sanitize(entry.get("mes") or entry.get("month") or entry.get("periodo") or "—")
        n = entry.get("total_contratos") or entry.get("count") or 0
        v = float(entry.get("valor_total") or entry.get("valor") or 0)
        rows.append([
            Paragraph(mes, styles["tbl_cell"]),
            Paragraph(_fmt_int(n), styles["tbl_cell_num"]),
            Paragraph(_fmt_currency(v), styles["tbl_cell_num"]),
        ])

    col_widths = [CONTENT_WIDTH * 0.30, CONTENT_WIDTH * 0.30, CONTENT_WIDTH * 0.40]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Nota: visualização em tabela — gráfico disponível na interface web",
        styles["caption"],
    ))
    story.append(PageBreak())
    return story


def _build_top_objetos(data: dict, styles: dict) -> list:
    """Page 5 — Top 10 Objetos Contratados."""
    story = []
    story.append(Paragraph("Top 10 Objetos Contratados", styles["section"]))

    objetos = data.get("objetos_top") or []
    if not objetos:
        story.append(Paragraph("Nenhum dado disponível.", styles["body"]))
        story.append(PageBreak())
        return story

    header = [
        Paragraph("Objeto (descrição)", styles["tbl_header"]),
        Paragraph("Frequência", styles["tbl_header"]),
        Paragraph("Valor Médio", styles["tbl_header"]),
    ]

    rows = [header]
    for o in objetos[:10]:
        rows.append([
            Paragraph(_trunc(o.get("objeto") or o.get("descricao") or "—", 70), styles["tbl_cell"]),
            Paragraph(_fmt_int(o.get("frequencia") or o.get("count") or 0), styles["tbl_cell_num"]),
            Paragraph(_fmt_currency(o.get("valor_medio") or o.get("valor_médio") or 0), styles["tbl_cell_num"]),
        ])

    col_widths = [CONTENT_WIDTH * 0.60, CONTENT_WIDTH * 0.18, CONTENT_WIDTH * 0.22]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)
    story.append(PageBreak())
    return story


def _build_geo_esfera(data: dict, styles: dict) -> list:
    """Page 6 — Distribuição Geográfica + Esfera."""
    story = []
    story.append(Paragraph("Distribuição Geográfica e Esfera", styles["section"]))

    uf_breakdown = data.get("uf_breakdown") or {}
    esfera_breakdown = data.get("esfera_breakdown") or {}

    # UF table
    if uf_breakdown:
        story.append(Paragraph("Distribuição por UF", styles["label"]))
        story.append(Spacer(1, 1 * mm))

        uf_items = sorted(uf_breakdown.items(), key=lambda x: -float(x[1] if not isinstance(x[1], dict) else x[1].get("total_contratos", 0)))

        header = [
            Paragraph("UF", styles["tbl_header"]),
            Paragraph("Nº Contratos", styles["tbl_header"]),
            Paragraph("Valor Total", styles["tbl_header"]),
        ]
        rows = [header]
        for uf, info in uf_items:
            if isinstance(info, dict):
                n = info.get("total_contratos") or info.get("count") or 0
                v = float(info.get("valor_total") or info.get("valor") or 0)
            else:
                n = int(info) if info else 0
                v = 0.0
            rows.append([
                Paragraph(_sanitize(uf), styles["tbl_cell"]),
                Paragraph(_fmt_int(n), styles["tbl_cell_num"]),
                Paragraph(_fmt_currency(v), styles["tbl_cell_num"]),
            ])

        col_widths = [CONTENT_WIDTH * 0.20, CONTENT_WIDTH * 0.30, CONTENT_WIDTH * 0.50]
        tbl = Table(rows, colWidths=col_widths)
        tbl.setStyle(_table_style_standard(len(rows)))
        story.append(tbl)
        story.append(Spacer(1, 4 * mm))

    # Esfera text
    if esfera_breakdown:
        story.append(Paragraph("Distribuição por Esfera", styles["label"]))
        story.append(Spacer(1, 1 * mm))
        esfera_lines = []
        for code, count in esfera_breakdown.items():
            label = ESFERA_LABELS.get(str(code).upper(), _sanitize(code))
            esfera_lines.append(f"{label}: {_fmt_int(count)} contrato(s)")
        story.append(Paragraph(" | ".join(esfera_lines), styles["body"]))

    story.append(PageBreak())
    return story


def _build_appendix(data: dict, styles: dict) -> list:
    """Page 7+ — Apêndice: últimos 50 contratos."""
    story = []
    story.append(Paragraph("Apêndice — Contratos Recentes", styles["section"]))
    story.append(Paragraph(
        "Listagem dos últimos 50 contratos registrados no PNCP.",
        styles["body"],
    ))

    contratos = data.get("contratos_recentes") or data.get("contracts") or []
    if not contratos:
        story.append(Paragraph("Nenhum contrato disponível.", styles["body"]))
        return story

    header = [
        Paragraph("Nº Controle", styles["tbl_header"]),
        Paragraph("Órgão", styles["tbl_header"]),
        Paragraph("UF", styles["tbl_header"]),
        Paragraph("Valor", styles["tbl_header"]),
        Paragraph("Data Assinatura", styles["tbl_header"]),
        Paragraph("Objeto", styles["tbl_header"]),
    ]

    rows = [header]
    for c in contratos[:50]:
        rows.append([
            Paragraph(_trunc(c.get("numero_controle") or c.get("numero_contrato") or "—", 20), styles["tbl_cell"]),
            Paragraph(_trunc(c.get("orgao_nome") or c.get("orgao") or "—", 30), styles["tbl_cell"]),
            Paragraph(_sanitize(c.get("uf") or "—"), styles["tbl_cell"]),
            Paragraph(_fmt_currency(c.get("valor_global") or c.get("valor") or 0), styles["tbl_cell_num"]),
            Paragraph(_format_date(c.get("data_assinatura") or c.get("data") or ""), styles["tbl_cell"]),
            Paragraph(_trunc(c.get("objeto") or c.get("objeto_contrato") or "—", 80), styles["tbl_cell"]),
        ])

    col_widths = [
        CONTENT_WIDTH * 0.13,
        CONTENT_WIDTH * 0.22,
        CONTENT_WIDTH * 0.06,
        CONTENT_WIDTH * 0.15,
        CONTENT_WIDTH * 0.12,
        CONTENT_WIDTH * 0.32,
    ]
    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)
    return story


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cnpj_report(data: dict) -> BytesIO:
    """Generate an 8-12 page A4 PDF for the INTEL-REPORT-001 Raio-X do Concorrente.

    Args:
        data: Aggregated dict from the `cnpj_supplier_intel` RPC. Expected keys:
            cnpj, fornecedor_nome, periodo_analisado, total_contratos, valor_total,
            ufs_ativas, narrative (dict with padrao_competitivo, principais_clientes,
            setores_foco, pontos_atencao), orgaos_top, evolucao_temporal, objetos_top,
            uf_breakdown, esfera_breakdown, contratos_recentes.

    Returns:
        BytesIO positioned at start containing the PDF.

    Raises:
        ValueError: If data is falsy/None.
    """
    if not data:
        raise ValueError("data must be a non-empty dict")

    buf = BytesIO()
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.5 * cm,
        bottomMargin=2.5 * cm,
        title="SmartLic Intelligence — Raio-X do Concorrente",
        author="SmartLic",
    )

    styles = _build_styles()

    # Build all sections
    story: list = []
    story.extend(_build_cover(data, styles))
    story.extend(_build_executive_summary(data, styles))
    story.extend(_build_top_orgaos(data, styles))
    story.extend(_build_temporal_evolution(data, styles))
    story.extend(_build_top_objetos(data, styles))
    story.extend(_build_geo_esfera(data, styles))
    story.extend(_build_appendix(data, styles))

    def _footer(canvas, doc):  # noqa: ANN001
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(VIABILITY_GRAY)
        footer = FOOTER_TEXT.format(data=now_str)
        canvas.drawCentredString(PAGE_WIDTH / 2, 1.2 * cm, footer)
        # Page number
        canvas.drawRightString(
            PAGE_WIDTH - MARGIN,
            1.2 * cm,
            f"Página {doc.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf
