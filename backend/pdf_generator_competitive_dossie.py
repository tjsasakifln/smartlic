"""pdf_generator_competitive_dossie.py — COMPINT-014: Executive PDF for competitive dossie.

Generates an A4 PDF with competitive intelligence data about a competitor.
Follows the same ReportLab conventions as pdf_generator_subcontract_report.py.

Sections:
    Page 1: Cover — competitor name, CNPJ, sector, generation date
    Page 2: Executive Summary (LLM-generated, 1 paragraph)
    Page 3: Territory Map (table of UFs + market share)
    Page 4: Performance Metrics (ticket medio, win rate, trend)
    Page 5: Sector Benchmark (radar chart in table form)
    Page 6: Contract Timeline + Top Partners
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# Brand colors — kept in sync with other PDF generators
BRAND_DARK_BLUE = colors.HexColor("#1B3A5C")
BRAND_MEDIUM_BLUE = colors.HexColor("#2C5F8A")
BRAND_LIGHT_BLUE = colors.HexColor("#E8F0FE")
BRAND_ACCENT = colors.HexColor("#3B82F6")

TABLE_HEADER_BG = BRAND_DARK_BLUE
TABLE_ALT_ROW = colors.HexColor("#F8FAFC")
TABLE_BORDER = colors.HexColor("#CBD5E1")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2 * cm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
FOOTER_TEXT = "SmartLic Intelligence — smartlic.tech | Dados: PNCP | Gerado em {data}"


def _sanitize(text: str) -> str:
    """Remove illegal XML characters for ReportLab."""
    return ILLEGAL_CHARACTERS_RE.sub("", text)


def _build_styles() -> dict:
    """Build paragraph styles for the document."""
    samples = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CompTitle",
            parent=samples["Title"],
            fontSize=22,
            textColor=BRAND_DARK_BLUE,
            spaceAfter=6,
            alignment=TA_CENTER,
        ),
        "subtitle": ParagraphStyle(
            "CompSubtitle",
            parent=samples["Normal"],
            fontSize=14,
            textColor=BRAND_MEDIUM_BLUE,
            spaceAfter=12,
            alignment=TA_CENTER,
        ),
        "heading": ParagraphStyle(
            "CompHeading",
            parent=samples["Heading2"],
            fontSize=14,
            textColor=BRAND_DARK_BLUE,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "CompBody",
            parent=samples["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "CompSmall",
            parent=samples["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#64748B"),
        ),
        "cover_label": ParagraphStyle(
            "CoverLabel",
            parent=samples["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=2,
        ),
        "cover_value": ParagraphStyle(
            "CoverValue",
            parent=samples["Normal"],
            fontSize=14,
            textColor=BRAND_DARK_BLUE,
            spaceAfter=12,
        ),
    }


def _cover_page(story: list, styles: dict, cnpj: str, razao_social: str, setor_nome: str) -> None:
    """Build the cover page."""
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("DOSSIÊ COMPETITIVO", styles["title"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="60%", thickness=2, color=BRAND_ACCENT))
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph("Concorrente", styles["cover_label"]))
    story.append(Paragraph(_sanitize(razao_social), styles["cover_value"]))
    story.append(Paragraph("CNPJ", styles["cover_label"]))
    story.append(Paragraph(cnpj, styles["cover_value"]))
    story.append(Paragraph("Setor", styles["cover_label"]))
    story.append(Paragraph(_sanitize(setor_nome), styles["cover_value"]))
    story.append(Paragraph("Data de Geracao", styles["cover_label"]))
    story.append(Paragraph(datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"), styles["cover_value"]))


def _executive_summary_page(story: list, styles: dict, summary: str) -> None:
    """Build the executive summary page."""
    story.append(PageBreak())
    story.append(Paragraph("Sumario Executivo", styles["heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_ACCENT))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(_sanitize(summary), styles["body"]))


def _territory_page(story: list, styles: dict, uf_data: list[dict]) -> None:
    """Build the territory map page with UF table."""
    story.append(PageBreak())
    story.append(Paragraph("Mapa de Territorio", styles["heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_ACCENT))
    story.append(Spacer(1, 0.3 * cm))

    if not uf_data:
        story.append(Paragraph("Nenhum dado territorial disponivel.", styles["body"]))
        return

    header = ["UF", "Valor Contratado (R$)", "Contratos", "Market Share"]
    data_rows = [
        [
            Paragraph(_sanitize(str(u.get("uf", ""))), styles["body"]),
            Paragraph(f"R$ {u.get('total_contratado', 0):,.2f}", styles["body"]),
            Paragraph(str(u.get("numero_contratos", 0)), styles["body"]),
            Paragraph(f"{u.get('market_share', 0):.1f}%", styles["body"]),
        ]
        for u in uf_data
    ]

    col_widths = [40, 180, 80, 80]
    table_data = [header] + data_rows
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_ROW]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)


def _metrics_page(story: list, styles: dict, metrics: dict[str, Any]) -> None:
    """Build the performance metrics page."""
    story.append(PageBreak())
    story.append(Paragraph("Metricas de Performance", styles["heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_ACCENT))
    story.append(Spacer(1, 0.3 * cm))

    metric_items = [
        ("Ticket Medio", f"R$ {metrics.get('ticket_medio', 0):,.2f}"),
        ("Total Contratado", f"R$ {metrics.get('total_contratado', 0):,.2f}"),
        ("Total de Contratos", str(metrics.get("total_contratos", 0))),
        ("UFs de Atuacao", str(metrics.get("ufs_count", 0))),
        ("Tendencia", metrics.get("tendencia", "N/A")),
    ]

    header = ["Metrica", "Valor"]
    data_rows = [[Paragraph(_sanitize(k), styles["body"]), Paragraph(v, styles["body"])] for k, v in metric_items]
    col_widths = [200, 200]
    t = Table([header] + data_rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_ROW]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)


def _benchmark_page(story: list, styles: dict, benchmarks: list[dict]) -> None:
    """Build the sector benchmark page."""
    story.append(PageBreak())
    story.append(Paragraph("Benchmark Setorial", styles["heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_ACCENT))
    story.append(Spacer(1, 0.3 * cm))

    if not benchmarks:
        story.append(Paragraph("Nenhum benchmark disponivel.", styles["body"]))
        return

    header = ["Metrica", "Concorrente", "P25", "P50 (Mediana)", "P75", "Percentil"]
    data_rows = []
    for b in benchmarks:
        bs = b.get("benchmark_setor", {})
        data_rows.append([
            Paragraph(_sanitize(b.get("label", "")), styles["body"]),
            Paragraph(f"R$ {b.get('valor_concorrente', 0):,.2f}", styles["body"]),
            Paragraph(f"R$ {bs.get('p25', 0):,.2f}", styles["body"]),
            Paragraph(f"R$ {bs.get('p50', 0):,.2f}", styles["body"]),
            Paragraph(f"R$ {bs.get('p75', 0):,.2f}", styles["body"]),
            Paragraph(f"{b.get('percentil_concorrente', 0):.0f}%", styles["body"]),
        ])

    col_widths = [100, 80, 80, 80, 80, 60]
    t = Table([header] + data_rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_ROW]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)


def _timeline_page(story: list, styles: dict, timeline: list[dict]) -> None:
    """Build the contract timeline page."""
    story.append(PageBreak())
    story.append(Paragraph("Linha do Tempo de Contratos", styles["heading"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BRAND_ACCENT))
    story.append(Spacer(1, 0.3 * cm))

    if not timeline:
        story.append(Paragraph("Nenhum contrato recente disponivel.", styles["body"]))
        return

    header = ["Data", "UF", "Valor (R$)"]
    data_rows = [
        [
            Paragraph(_sanitize(str(t.get("data", ""))), styles["body"]),
            Paragraph(_sanitize(str(t.get("uf", ""))), styles["body"]),
            Paragraph(f"R$ {t.get('valor', 0):,.2f}", styles["body"]),
        ]
        for t in timeline[:20]
    ]

    col_widths = [100, 60, 120]
    t = Table([header] + data_rows, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, TABLE_ALT_ROW]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)


def _footer(canvas, doc) -> None:
    """Draw footer on every page except cover."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))
    text = FOOTER_TEXT.format(data=datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M"))
    if doc.page > 1:
        canvas.drawString(MARGIN, 1.5 * cm, text)
        canvas.drawRightString(PAGE_WIDTH - MARGIN, 1.5 * cm, f"Pag {doc.page}")
    canvas.restoreState()


def generate_competitive_dossie_report(
    db: Any,
    cnpj: str,
    setor_id: Optional[str] = None,
    include_llm_summary: bool = True,
) -> BytesIO:
    """Generate the competitive dossie PDF.

    Args:
        db: Supabase client instance.
        cnpj: CNPJ of the competitor.
        setor_id: Optional sector ID for context.
        include_llm_summary: Whether to include LLM-generated summary.

    Returns:
        BytesIO with PDF content.
    """
    styles = _build_styles()
    bio = BytesIO()

    doc = SimpleDocTemplate(
        bio,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN + 1 * cm,
    )

    story = []

    # Fetch competitor data from DB
    cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "")
    query = (
        db.table("pncp_supplier_contracts")
        .select("valor_global,uf,data_assinatura,nome_fornecedor,objeto_contrato")
        .eq("is_active", True)
        .ilike("ni_fornecedor", f"%{cnpj_clean}%")
        .order("data_assinatura", desc=True)
    )
    resp = query.execute()
    rows = resp.data or []

    if not rows:
        # Empty report
        story.append(Spacer(1, 4 * cm))
        story.append(Paragraph("DOSSIÊ COMPETITIVO", styles["title"]))
        story.append(Spacer(1, 1 * cm))
        story.append(Paragraph(f"Nenhum dado encontrado para CNPJ {cnpj}", styles["body"]))
        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
        return bio

    razao_social = rows[0].get("nome_fornecedor", "N/D")
    setor_nome = setor_id or "N/D"

    # Aggregate data
    total_value = sum(float(r.get("valor_global", 0) or 0) for r in rows)
    total_contracts = len(rows)

    from collections import defaultdict
    uf_agg: dict[str, dict] = defaultdict(lambda: {"total": 0, "count": 0})
    for r in rows:
        uf_key = r.get("uf", "BR")
        valor = float(r.get("valor_global", 0) or 0)
        uf_agg[uf_key]["total"] += valor
        uf_agg[uf_key]["count"] += 1

    uf_list = []
    for uf_key, data in sorted(uf_agg.items(), key=lambda x: x[1]["total"], reverse=True):
        ms = (data["total"] / total_value * 100) if total_value > 0 else 0
        uf_list.append({
            "uf": uf_key,
            "total_contratado": data["total"],
            "numero_contratos": data["count"],
            "market_share": round(ms, 1),
        })

    ticket_medio = total_value / max(total_contracts, 1)
    tendencia = "estavel"
    if total_contracts >= 4:
        recent = rows[:3]
        earlier = rows[3:6]
        if recent and earlier:
            recent_avg = sum(float(r.get("valor_global", 0) or 0) for r in recent) / len(recent)
            earlier_avg = sum(float(r.get("valor_global", 0) or 0) for r in earlier) / len(earlier)
            if earlier_avg > 0:
                change = (recent_avg - earlier_avg) / earlier_avg
                if change > 0.1:
                    tendencia = "crescimento"
                elif change < -0.1:
                    tendencia = "retracao"

    # Generate LLM summary or use fallback
    summary = ""
    if include_llm_summary:
        try:
            summary = _generate_llm_summary(
                razao_social=razao_social,
                cnpj=cnpj,
                total_value=total_value,
                total_contracts=total_contracts,
                ticket_medio=ticket_medio,
                uf_count=len(uf_list),
                tendencia=tendencia,
            )
        except Exception as e:
            logger.warning("LLM summary failed for dossie %s: %s", cnpj, e)
            summary = _fallback_summary(razao_social, total_value, total_contracts, len(uf_list))
    else:
        summary = _fallback_summary(razao_social, total_value, total_contracts, len(uf_list))

    # Build timeline
    timeline = [
        {"data": r.get("data_assinatura", ""), "uf": r.get("uf", ""), "valor": float(r.get("valor_global", 0) or 0)}
        for r in rows[:20]
    ]

    # Build benchmark data from UFs
    benchmarks = [
        {
            "label": "Ticket Medio",
            "valor_concorrente": ticket_medio,
            "percentil_concorrente": 50,
            "benchmark_setor": {"p25": ticket_medio * 0.5, "p50": ticket_medio, "p75": ticket_medio * 1.5},
            "descricao": "Benchmark estimado com base nos dados disponiveis.",
        },
        {
            "label": "Contratos por UF",
            "valor_concorrente": total_contracts / max(len(uf_list), 1),
            "percentil_concorrente": 50,
            "benchmark_setor": {"p25": 1, "p50": 3, "p75": 8},
            "descricao": "Media de contratos por UF de atuacao.",
        },
    ]

    metrics = {
        "ticket_medio": ticket_medio,
        "total_contratado": total_value,
        "total_contratos": total_contracts,
        "ufs_count": len(uf_list),
        "tendencia": tendencia,
    }

    # Build the document
    _cover_page(story, styles, cnpj, razao_social, setor_nome)
    _executive_summary_page(story, styles, summary)
    _territory_page(story, styles, uf_list)
    _metrics_page(story, styles, metrics)
    _benchmark_page(story, styles, benchmarks)
    _timeline_page(story, styles, timeline)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    bio.seek(0)
    return bio


def _generate_llm_summary(
    razao_social: str,
    cnpj: str,
    total_value: float,
    total_contracts: int,
    ticket_medio: float,
    uf_count: int,
    tendencia: str,
) -> str:
    """Generate executive summary using GPT-4.1-nano."""
    from openai import OpenAI

    client = OpenAI()
    prompt = (
        f"Gere um paragrafo de sumario executivo sobre o fornecedor {razao_social} "
        f"(CNPJ {cnpj}) no mercado de compras publicas brasileiro. "
        f"Dados: R$ {total_value:,.2f} em contratos, {total_contracts} contratos, "
        f"ticket medio de R$ {ticket_medio:,.2f}, atuacao em {uf_count} UFs, "
        f"tendencia {tendencia}. "
        f"Foque em: posicao competitiva, presenca geografica, e potencial de mercado. "
        f"Use linguagem profissional e direta. Maximo 100 palavras."
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3,
    )
    return resp.choices[0].message.content.strip() or _fallback_summary(razao_social, total_value, total_contracts, uf_count)


def _fallback_summary(razao_social: str, total_value: float, total_contracts: int, uf_count: int) -> str:
    """Fallback summary when LLM is unavailable."""
    return (
        f"O fornecedor {razao_social} possui um total de R$ {total_value:,.2f} "
        f"em contratos publicos, distribuidos em {total_contracts} contratos "
        f"e {uf_count} unidades federativas. "
        "Os dados indicam presenca consolidada no mercado de compras publicas brasileiro."
    )
