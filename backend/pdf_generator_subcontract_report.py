"""pdf_generator_subcontract_report.py — SUBINTEL-033: Executive PDF for subcontracting.

Generates an A4 PDF from data returned by the `subcontract_intel` RPC.
Follows the same ReportLab conventions as pdf_generator_sector_uf_report.py.

Usage (called by ARQ job in jobs/queue/jobs.py):
    >>> from pdf_generator_subcontract_report import generate_subcontract_report
    >>> bio = generate_subcontract_report(db=supabase_client, entity_key="12345678000195")
    >>> pdf_bytes = bio.getvalue()

entity_key format: CNPJ (14 digits) — e.g. "12345678000195".
                  Or "sector_id:UF" — e.g. "limpeza:SP" (falls back to sector_uf_intel).

Sections:
    Page 1:  Executive Summary — "Por que [setor/fornecedor] em [UF] tem
             oportunidade de subcontratacao"
    Page 2:  Partnership Opportunity Score (0-100)
    Pages 3-4: Regional Dependency Map + Heatmap
    Page 5:  Relevant Supplier Network
    Page 6:  Recommended Actions
"""

from __future__ import annotations

import html
import logging
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brand colors — kept in sync with pdf_generator_sector_uf_report.py
# ---------------------------------------------------------------------------
BRAND_DARK_BLUE = colors.HexColor("#1B3A5C")
BRAND_MEDIUM_BLUE = colors.HexColor("#2C5F8A")
BRAND_LIGHT_BLUE = colors.HexColor("#E8F0FE")
BRAND_ACCENT = colors.HexColor("#3B82F6")

VIABILITY_GREEN = colors.HexColor("#16A34A")
VIABILITY_YELLOW = colors.HexColor("#CA8A04")
VIABILITY_RED = colors.HexColor("#DC2626")
VIABILITY_GRAY = colors.HexColor("#64748B")

TABLE_HEADER_BG = BRAND_DARK_BLUE
TABLE_ALT_ROW = colors.HexColor("#F8FAFC")
TABLE_BORDER = colors.HexColor("#CBD5E1")
METRIC_BOX_BG = colors.HexColor("#EFF6FF")  # blue-50
SCORE_HIGH_BG = colors.HexColor("#DCFCE7")  # green-50
SCORE_MED_BG = colors.HexColor("#FEF9C3")   # yellow-50
SCORE_LOW_BG = colors.HexColor("#FEE2E2")   # red-50

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 2 * cm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

FOOTER_TEXT = "SmartLic Intelligence — smartlic.tech | Dados: PNCP | Atualizado em {data}"

# ---------------------------------------------------------------------------
# Helpers (duplicated from pdf_generator_sector_uf_report to keep modules independent)
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


def _fmt_score(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{int(value)}/100"


def _format_date(date_str: str | None) -> str:
    if not date_str:
        return "—"
    try:
        parts = str(date_str).split("T")[0].split("-")
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
            "SCRTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=BRAND_DARK_BLUE,
            alignment=TA_CENTER,
            spaceAfter=6 * mm,
        ),
        "subtitle": _ps(
            "SCRSubtitle",
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=BRAND_MEDIUM_BLUE,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "section": _ps(
            "SCRSection",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=BRAND_DARK_BLUE,
            spaceBefore=6 * mm,
            spaceAfter=3 * mm,
        ),
        "body": _ps(
            "SCRBody",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#334155"),
            spaceAfter=2 * mm,
        ),
        "caption": _ps(
            "SCRCaption",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
        "label": _ps(
            "SCRLabel",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=BRAND_DARK_BLUE,
        ),
        "metric_val": _ps(
            "SCRMetricVal",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=BRAND_DARK_BLUE,
            alignment=TA_CENTER,
        ),
        "metric_label": _ps(
            "SCRMetricLabel",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
        "warning": _ps(
            "SCRWarning",
            fontName="Helvetica-Oblique",
            fontSize=7,
            leading=9,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
        "tbl_header": _ps(
            "SCRTblHeader",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.white,
        ),
        "tbl_cell": _ps(
            "SCRTblCell",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#334155"),
        ),
        "tbl_cell_num": _ps(
            "SCRTblCellNum",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#334155"),
            alignment=TA_RIGHT,
        ),
        "score_val": _ps(
            "SCRScoreVal",
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            textColor=BRAND_DARK_BLUE,
            alignment=TA_CENTER,
        ),
        "score_label": _ps(
            "SCRScoreLabel",
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=VIABILITY_GRAY,
            alignment=TA_CENTER,
        ),
    }


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _build_cover(data: dict, styles: dict) -> list:
    """Page 1 — Cover page with title."""
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    entity_type = data.get("entity_type") or "cnpj"
    entity_key = _sanitize(data.get("entity_key") or "")
    window_months = data.get("window_months") or 24

    # Extract display name
    fornecedor_nome = "Fornecedor"
    if entity_type == "cnpj":
        ps_data = data.get("partnership_score")
        if isinstance(ps_data, list) and len(ps_data) > 0:
            fornecedor_nome = _sanitize(
                ps_data[0].get("factors", {}).get("fornecedor_nome")
                or ps_data[0].get("supplier_name")
                or "Fornecedor"
            )

    story = []
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

    story.append(Paragraph("Relatorio de Subcontratacao", styles["title"]))
    story.append(Spacer(1, 4 * mm))

    if entity_type == "cnpj":
        story.append(
            Paragraph(f"Oportunidades de Parceria — {fornecedor_nome}", styles["subtitle"])
        )
        story.append(Paragraph(f"CNPJ: {entity_key}", styles["caption"]))
    else:
        sector_label = _sanitize(data.get("sector_id") or "")
        uf = _sanitize(data.get("uf") or "")
        story.append(
            Paragraph(f"Oportunidades de Subcontratacao — {sector_label} / {uf}",
                      styles["subtitle"])
        )

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Janela de analise: {window_months} meses", styles["caption"]))
    story.append(Paragraph(f"Data de geracao: {now_str}", styles["caption"]))

    story.append(Spacer(1, 12 * mm))
    story.append(HRFlowable(
        width=CONTENT_WIDTH,
        thickness=0.5,
        color=TABLE_BORDER,
        spaceAfter=4 * mm,
    ))
    story.append(Paragraph(
        "Analise baseada em dados do PNCP — Contratos registrados por orgaos publicos",
        styles["warning"],
    ))

    story.append(PageBreak())
    return story


def _build_executive_summary(data: dict, styles: dict) -> list:
    """Page 2 — Executive summary with key metrics."""
    story = []
    story.append(Paragraph("Sumario Executivo", styles["section"]))

    entity_type = data.get("entity_type") or "cnpj"

    if entity_type == "cnpj":
        ps_data = data.get("partnership_score")
        benchmark = data.get("benchmark")
        regional_dep = data.get("regional_dependency")

        # Extract values from partnership score
        score = 0
        factors = {}
        if isinstance(ps_data, list) and len(ps_data) > 0:
            p = ps_data[0]
            score = int(p.get("score") or 0)
            factors = p.get("factors") or {}

        total_contratos = int(factors.get("total_contratos") or 0)
        total_orgaos = int(factors.get("total_orgaos") or 0)
        total_ufs = int(factors.get("total_ufs") or 0)
        avg_ticket = float(factors.get("avg_ticket") or 0)
        tendencia = _sanitize(factors.get("tendencia_recente") or "estavel")

        # Find main UF from regional dependency
        main_uf = ""
        if isinstance(regional_dep, list) and len(regional_dep) > 0:
            main_uf = _sanitize(regional_dep[0].get("uf_sigla") or "")

        narrative = (
            f"O fornecedor analisado possui {_fmt_int(total_contratos)} contratos publicos "
            f"ativos no PNCP, distribuidos entre {_fmt_int(total_orgaos)} orgaos "
            f"compradores em {_fmt_int(total_ufs)} estados diferentes. "
            f"O ticket medio dos contratos e de {_fmt_currency(avg_ticket)}. "
        )
        if main_uf:
            narrative += (
                f"A maior concentracao de contratos esta em {main_uf}, "
            )
        narrative += (
            f"e a tendencia recente e de {_fmt_tendencia(tendencia)}. "
            f"O Score de Oportunidade de Parceria e {_fmt_score(score)}, "
            f"indicando {_fmt_score_interpretation(score)} para estabelecer "
            f"relacoes de subcontratacao."
        )

        story.append(Paragraph(narrative, styles["body"]))
        story.append(Spacer(1, 4 * mm))

        # Key metrics
        metrics = [
            (_fmt_score(score), "Score de Parceria"),
            (_fmt_int(total_contratos), "Total de Contratos"),
            (_fmt_int(total_orgaos), "Orgaos Atendidos"),
            (_fmt_int(total_ufs), "UFs de Atuacao"),
        ]

        col_w = CONTENT_WIDTH / 4
        metric_rows = [[
            Table(
                [[Paragraph(v, styles["metric_val"])],
                 [Paragraph(lbl, styles["metric_label"])]],
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

        # Benchmark summary
        if isinstance(benchmark, list) and len(benchmark) > 0:
            story.append(Spacer(1, 4 * mm))
            story.append(Paragraph("Benchmark Competitivo", styles["section"]))
            header = [
                Paragraph("Metrica", styles["tbl_header"]),
                Paragraph("Valor", styles["tbl_header"]),
                Paragraph("P25", styles["tbl_header"]),
                Paragraph("P50", styles["tbl_header"]),
                Paragraph("P75", styles["tbl_header"]),
                Paragraph("Interpretacao", styles["tbl_header"]),
            ]
            rows = [header]
            for b in benchmark[:4]:
                rows.append([
                    Paragraph(_sanitize(b.get("metric_name") or ""), styles["tbl_cell"]),
                    Paragraph(_fmt_currency(b.get("competitor_value")), styles["tbl_cell_num"]),
                    Paragraph(_fmt_currency(b.get("sector_p25")), styles["tbl_cell_num"]),
                    Paragraph(_fmt_currency(b.get("sector_p50")), styles["tbl_cell_num"]),
                    Paragraph(_fmt_currency(b.get("sector_p75")), styles["tbl_cell_num"]),
                    Paragraph(_trunc(b.get("interpretation") or "", 50), styles["tbl_cell"]),
                ])
            col_widths = [
                CONTENT_WIDTH * 0.18,
                CONTENT_WIDTH * 0.12,
                CONTENT_WIDTH * 0.10,
                CONTENT_WIDTH * 0.10,
                CONTENT_WIDTH * 0.10,
                CONTENT_WIDTH * 0.40,
            ]
            tbl = Table(rows, colWidths=col_widths)
            tbl.setStyle(_table_style_standard(len(rows)))
            story.append(tbl)

    else:
        sector_id = _sanitize(data.get("sector_id") or "")
        uf = _sanitize(data.get("uf") or "")
        story.append(Paragraph(
            f"O setor {sector_id} no estado {uf} apresenta oportunidades de subcontratacao. "
            f"Os dados detalhados de parceria requerem consulta por CNPJ de fornecedor especifico. "
            f"Consulte as secoes seguintes para o panorama setorial.",
            styles["body"],
        ))

    story.append(PageBreak())
    return story


def _build_partnership_score(data: dict, styles: dict) -> list:
    """Page 3 — Partnership Opportunity Score (0-100)."""
    story = []
    story.append(Paragraph("Score de Oportunidade de Parceria", styles["section"]))
    story.append(Spacer(1, 2 * mm))

    ps_data = data.get("partnership_score")
    if not isinstance(ps_data, list) or len(ps_data) == 0:
        story.append(Paragraph("Nenhum dado disponivel.", styles["body"]))
        story.append(PageBreak())
        return story

    p = ps_data[0]
    score = int(p.get("score") or 0)
    factors = p.get("factors") or {}

    # Big score display
    score_color = VIABILITY_GREEN if score >= 60 else (VIABILITY_YELLOW if score >= 30 else VIABILITY_RED)
    score_bg = SCORE_HIGH_BG if score >= 60 else (SCORE_MED_BG if score >= 30 else SCORE_LOW_BG)

    score_text = str(score)
    score_tbl_data = [[
        Paragraph(f'<font color="{score_color.hexval()}"><b>{score_text}</b></font>',
                  styles["score_val"]),
    ]]
    score_tbl = Table(score_tbl_data, colWidths=[CONTENT_WIDTH * 0.25])
    score_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), score_bg),
        ("BOX", (0, 0), (-1, -1), 2, score_color),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
    ]))

    interpretation = _fmt_score_interpretation(score)
    interp_tbl_data = [[
        Paragraph(interpretation, styles["score_label"]),
    ]]
    interp_tbl = Table(interp_tbl_data, colWidths=[CONTENT_WIDTH * 0.70])

    combo_data = [[score_tbl, interp_tbl]]
    combo_tbl = Table(combo_data, colWidths=[CONTENT_WIDTH * 0.25, CONTENT_WIDTH * 0.75])
    combo_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(combo_tbl)
    story.append(Spacer(1, 4 * mm))

    # Score factors breakdown
    story.append(Paragraph("Fatores do Score", styles["section"]))

    factor_items = [
        ("Volume de Contratos", f"{_fmt_int(factors.get('total_contratos') or 0)} contratos",
         min(25, int(factors.get("total_contratos") or 0)), 25),
        ("Diversidade Geografica",
         f"{_fmt_int(factors.get('total_ufs') or 0)} UFs",
         min(25, int(factors.get("total_ufs") or 0) * 5), 25),
        ("Diversidade de Orgaos",
         f"{_fmt_int(factors.get('total_orgaos') or 0)} orgaos",
         min(25, int(factors.get("total_orgaos") or 0) * 3), 25),
    ]

    hhi = float(factors.get("hhi_concentracao") or 0)
    hhi_score = 15 if hhi < 1000 else (10 if hhi < 2500 else (5 if hhi < 5000 else 0))
    factor_items.append(("Baixa Concentracao (HHI)", f"HHI: {hhi:.0f}", hhi_score, 15))

    tendencia = _sanitize(factors.get("tendencia_recente") or "estavel")
    trend_score = 10 if tendencia == "crescendo" else (5 if tendencia == "estavel" else 0)
    factor_items.append(("Tendencia Recente", f"Tendencia: {tendencia}", trend_score, 10))

    header = [
        Paragraph("Fator", styles["tbl_header"]),
        Paragraph("Valor", styles["tbl_header"]),
        Paragraph("Pontos", styles["tbl_header"]),
        Paragraph("Maximo", styles["tbl_header"]),
    ]
    rows = [header]
    for name, val, pts, mx in factor_items:
        rows.append([
            Paragraph(name, styles["tbl_cell"]),
            Paragraph(val, styles["tbl_cell"]),
            Paragraph(str(pts), styles["tbl_cell_num"]),
            Paragraph(str(mx), styles["tbl_cell_num"]),
        ])
    rows.append([
        Paragraph("<b>Total</b>", styles["tbl_cell"]),
        Paragraph("", styles["tbl_cell"]),
        Paragraph(f"<b>{score}</b>", styles["tbl_cell_num"]),
        Paragraph("<b>100</b>", styles["tbl_cell_num"]),
    ])

    col_widths = [
        CONTENT_WIDTH * 0.35,
        CONTENT_WIDTH * 0.35,
        CONTENT_WIDTH * 0.15,
        CONTENT_WIDTH * 0.15,
    ]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)

    story.append(PageBreak())
    return story


def _build_regional_dependency(data: dict, styles: dict) -> list:
    """Pages 4 — Regional Dependency Map + Heatmap."""
    story = []
    story.append(Paragraph("Mapa de Dependencia Regional", styles["section"]))

    regional_dep = data.get("regional_dependency")
    if not isinstance(regional_dep, list) or len(regional_dep) == 0:
        story.append(Paragraph("Nenhum dado regional disponivel.", styles["body"]))
        story.append(PageBreak())
        return story

    story.append(Paragraph(
        "Indice de dependencia regional: percentual de contratos concentrados em cada UF. "
        "Quanto maior o indice, maior a dependencia do fornecedor naquela regiao — "
        "e maior a oportunidade de subcontratacao para parceiros locais.",
        styles["body"],
    ))
    story.append(Spacer(1, 2 * mm))

    header = [
        Paragraph("UF", styles["tbl_header"]),
        Paragraph("Indice de Dependencia", styles["tbl_header"]),
        Paragraph("Nº Contratos", styles["tbl_header"]),
        Paragraph("Top Orgao", styles["tbl_header"]),
        Paragraph("Potencial Expansao", styles["tbl_header"]),
    ]
    rows = [header]

    for dep in regional_dep:
        uf_sigla = _sanitize(dep.get("uf_sigla") or "")
        dep_idx = float(dep.get("dependency_index") or 0)
        contract_cnt = int(dep.get("contract_count") or 0)
        top_orgaos = dep.get("top_orgaos") or []
        top_orgao_nome = ""
        if isinstance(top_orgaos, list) and len(top_orgaos) > 0:
            top_orgao_nome = top_orgaos[0].get("orgao_nome", "") or ""
        expansion = _sanitize(dep.get("expansion_potential") or "")

        # Color-code dependency index
        dep_color = VIABILITY_RED if dep_idx >= 50 else (VIABILITY_YELLOW if dep_idx >= 30 else VIABILITY_GREEN)

        rows.append([
            Paragraph(f'<font color="{dep_color.hexval()}"><b>{uf_sigla}</b></font>',
                      styles["tbl_cell"]),
            Paragraph(f'{dep_idx:.1f}%', styles["tbl_cell_num"]),
            Paragraph(_fmt_int(contract_cnt), styles["tbl_cell_num"]),
            Paragraph(_trunc(top_orgao_nome, 40), styles["tbl_cell"]),
            Paragraph(_fmt_expansion_label(expansion), styles["tbl_cell"]),
        ])

    col_widths = [
        CONTENT_WIDTH * 0.08,
        CONTENT_WIDTH * 0.17,
        CONTENT_WIDTH * 0.12,
        CONTENT_WIDTH * 0.38,
        CONTENT_WIDTH * 0.25,
    ]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)

    # Legend
    story.append(Spacer(1, 3 * mm))
    legend_items = [
        ("Alta Dependencia (>=50%)", "Vermelho"),
        ("Media Dependencia (30-50%)", "Amarelo"),
        ("Baixa Dependencia (<30%)", "Verde"),
    ]
    legend_text = "Legenda: " + " | ".join(f"{lbl}" for lbl, _ in legend_items)
    story.append(Paragraph(legend_text, styles["caption"]))

    story.append(PageBreak())
    return story


def _build_supplier_network(data: dict, styles: dict) -> list:
    """Page 5 — Relevant Supplier Network."""
    story = []
    story.append(Paragraph("Rede de Fornecedores Relevantes", styles["section"]))

    supplier_network = data.get("supplier_network")
    if not isinstance(supplier_network, list) or len(supplier_network) == 0:
        story.append(Paragraph("Nenhuma conexao em rede encontrada.", styles["body"]))
        story.append(PageBreak())
        return story

    story.append(Paragraph(
        "Fornecedores que co-ocorrem nos mesmos orgaos compradores — "
        "potenciais candidatos a parceria ou subcontratacao.",
        styles["body"],
    ))
    story.append(Spacer(1, 2 * mm))

    entity_key = data.get("entity_key") or ""

    header = [
        Paragraph("Fornecedor", styles["tbl_header"]),
        Paragraph("CNPJ", styles["tbl_header"]),
        Paragraph("Conexoes", styles["tbl_header"]),
        Paragraph("Orgaos Compartilhados", styles["tbl_header"]),
    ]
    rows = [header]

    for conn in supplier_network[:15]:
        source_cnpj = _sanitize(conn.get("source_cnpj") or "")
        source_name = _sanitize(conn.get("source_name") or "")
        target_cnpj = _sanitize(conn.get("target_cnpj") or "")
        target_name = _sanitize(conn.get("target_name") or "")
        weight = int(conn.get("weight") or 0)
        shared_orgaos = conn.get("shared_orgaos") or []

        # Determine which side is the "other" supplier
        if source_cnpj == entity_key or source_cnpj.replace(r"\D", "") == entity_key:
            other_name = target_name
            other_cnpj = target_cnpj
        else:
            other_name = source_name
            other_cnpj = source_cnpj

        orgao_names = []
        if isinstance(shared_orgaos, list):
            for o in shared_orgaos[:3]:
                n = o.get("orgao_nome") or o.get("orgao_name") or ""
                if n:
                    orgao_names.append(n)
        shared_text = "; ".join(orgao_names[:3])

        rows.append([
            Paragraph(_trunc(other_name, 45), styles["tbl_cell"]),
            Paragraph(_trunc(other_cnpj, 18), styles["tbl_cell"]),
            Paragraph(str(weight), styles["tbl_cell_num"]),
            Paragraph(_trunc(shared_text, 40), styles["tbl_cell"]),
        ])

    col_widths = [
        CONTENT_WIDTH * 0.32,
        CONTENT_WIDTH * 0.18,
        CONTENT_WIDTH * 0.10,
        CONTENT_WIDTH * 0.40,
    ]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(_table_style_standard(len(rows)))
    story.append(tbl)

    story.append(PageBreak())
    return story


def _build_recommended_actions(data: dict, styles: dict) -> list:
    """Page 6 — Recommended Actions for subcontracting."""
    story = []
    story.append(Paragraph("Acoes Recomendadas", styles["section"]))

    ps_data = data.get("partnership_score")
    recommended_actions = []
    if isinstance(ps_data, list) and len(ps_data) > 0:
        recommended_actions = ps_data[0].get("recommended_actions") or []
    similar_suppliers = []
    if isinstance(ps_data, list) and len(ps_data) > 0:
        similar_suppliers = ps_data[0].get("similar_suppliers") or []

    has_actions = (
        isinstance(recommended_actions, list) and len(recommended_actions) > 0
    )
    has_similar = (
        isinstance(similar_suppliers, list) and len(similar_suppliers) > 0
    )

    if not has_actions and not has_similar:
        story.append(Paragraph(
            "Nenhuma acao especifica recomendada no momento. "
            "Consulte os dados de dependencia regional e rede de fornecedores "
            "para identificar oportunidades de subcontratacao manualmente.",
            styles["body"],
        ))
        story.append(PageBreak())
        return story

    if has_actions:
        story.append(Paragraph("Acoes com Base no Score", styles["section"]))
        header = [
            Paragraph("Acao", styles["tbl_header"]),
            Paragraph("Prioridade", styles["tbl_header"]),
        ]
        rows = [header]
        for action in recommended_actions:
            action_text = _sanitize(action.get("action") or action.get("action_text") or "")
            priority = _sanitize(action.get("priority") or "media")
            priority_color = VIABILITY_RED if priority == "alta" else (
                VIABILITY_YELLOW if priority == "media" else VIABILITY_GREEN
            )
            rows.append([
                Paragraph(action_text, styles["tbl_cell"]),
                Paragraph(
                    f'<font color="{priority_color.hexval()}">{priority}</font>',
                    styles["tbl_cell"],
                ),
            ])
        col_widths = [CONTENT_WIDTH * 0.75, CONTENT_WIDTH * 0.25]
        tbl = Table(rows, colWidths=col_widths)
        tbl.setStyle(_table_style_standard(len(rows)))
        story.append(tbl)

    if has_similar:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("Fornecedores Similares para Parceria", styles["section"]))
        story.append(Paragraph(
            "Estes fornecedores atuam nos mesmos orgaos e regioes — "
            "candidatos naturais para subcontratacao ou parceria:",
            styles["body"],
        ))
        header = [
            Paragraph("Fornecedor", styles["tbl_header"]),
            Paragraph("CNPJ", styles["tbl_header"]),
            Paragraph("Contratos", styles["tbl_header"]),
            Paragraph("UFs", styles["tbl_header"]),
        ]
        rows = [header]
        for s in similar_suppliers[:8]:
            rows.append([
                Paragraph(_trunc(s.get("nome") or s.get("supplier_name") or "", 45),
                          styles["tbl_cell"]),
                Paragraph(_trunc(s.get("cnpj") or s.get("supplier_cnpj") or "", 18),
                          styles["tbl_cell"]),
                Paragraph(_fmt_int(s.get("contratos") or s.get("contract_count") or 0),
                          styles["tbl_cell_num"]),
                Paragraph(_fmt_int(s.get("ufs") or s.get("uf_count") or 0),
                          styles["tbl_cell_num"]),
            ])
        col_widths = [
            CONTENT_WIDTH * 0.40,
            CONTENT_WIDTH * 0.22,
            CONTENT_WIDTH * 0.18,
            CONTENT_WIDTH * 0.20,
        ]
        tbl = Table(rows, colWidths=col_widths)
        tbl.setStyle(_table_style_standard(len(rows)))
        story.append(tbl)

    story.append(PageBreak())
    return story


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _fmt_tendencia(tendencia: str) -> str:
    mapping = {
        "crescendo": "crescimento",
        "diminuindo": "reducao",
        "estavel": "estabilidade",
    }
    return mapping.get(tendencia, tendencia)


def _fmt_score_interpretation(score: int) -> str:
    if score >= 70:
        return (
            "Alta oportunidade de parceria. O fornecedor tem carteira diversificada "
            "e presenca em multiplas regioes — ideal para subcontratacao."
        )
    if score >= 40:
        return (
            "Oportunidade moderada. Existe potencial de parceria, mas e recomendado "
            "avaliar a concentracao geografica e de orgaos."
        )
    return (
        "Oportunidade limitada. O fornecedor tem baixa diversificacao — "
        "a subcontratacao pode ser viavel em nichos especificos."
    )


def _fmt_expansion_label(expansion: str) -> str:
    mapping = {
        "alta_dependencia": "Alta Dependencia",
        "media_dependencia": "Media Dependencia",
        "diversificando": "Diversificando",
        "baixa_presenca": "Baixa Presenca",
    }
    return mapping.get(expansion, expansion.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def _fetch_rpc_data(db: Any, entity_key: str) -> dict:
    """Call subcontract_intel RPC and return the JSONB payload as a dict."""
    cnpj_clean = re.sub(r"[^0-9]", "", entity_key)

    if len(cnpj_clean) == 14:
        rpc_entity_key = cnpj_clean
    else:
        rpc_entity_key = entity_key  # "setor:UF" format

    result = db.rpc(
        "subcontract_intel",
        {
            "p_entity_key": rpc_entity_key,
            "p_window_months": 24,
        },
    ).execute()

    payload = getattr(result, "data", None)
    if not payload:
        raise ValueError(
            f"subcontract_intel returned no data for entity_key={entity_key!r}"
        )

    # PostgREST wraps RPC results in a list when returning a scalar JSONB
    if isinstance(payload, list) and len(payload) == 1:
        item = payload[0]
        if isinstance(item, dict) and "subcontract_intel" in item:
            return item["subcontract_intel"]
        return item

    if isinstance(payload, dict):
        return payload

    raise ValueError(
        f"subcontract_intel returned unexpected shape: {type(payload).__name__}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_subcontract_report(db: Any, entity_key: str) -> BytesIO:
    """Generate an A4 PDF for the SUBINTEL-033 Subcontracting Executive Report.

    Args:
        db: Supabase client (service role) — used to call the subcontract_intel RPC.
        entity_key: CNPJ (14 digits) or "sector_id:UF" format.
            CNPJ e.g. "12345678000195"
            sector:UF e.g. "limpeza:SP"

    Returns:
        BytesIO positioned at start containing the PDF.

    Raises:
        ValueError: If entity_key format is invalid or RPC returns no data.
    """
    if not entity_key or not entity_key.strip():
        raise ValueError("entity_key must be non-empty")

    entity_key = entity_key.strip()

    # Resolve display name for CNPJ
    cnpj_clean = re.sub(r"[^0-9]", "", entity_key)
    if len(cnpj_clean) != 14 and ":" not in entity_key:
        raise ValueError(
            f"Invalid entity_key {entity_key!r}. "
            "Expected CNPJ (14 digits) or 'sector_id:UF' format."
        )

    logger.info("subcontract_intel: entity_key=%s", entity_key)

    # --- Fetch RPC data ---
    data = _fetch_rpc_data(db=db, entity_key=entity_key)

    # --- Enrich with display fields ---
    data.setdefault("entity_key", entity_key)

    # --- Build PDF ---
    buf = BytesIO()
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y")

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.5 * cm,
        bottomMargin=2.5 * cm,
        title="SmartLic Intelligence — Relatorio de Subcontratacao",
        author="SmartLic",
    )

    styles = _build_styles()

    story: list = []
    story.extend(_build_cover(data, styles))
    story.extend(_build_executive_summary(data, styles))
    story.extend(_build_partnership_score(data, styles))
    story.extend(_build_regional_dependency(data, styles))
    story.extend(_build_supplier_network(data, styles))
    story.extend(_build_recommended_actions(data, styles))

    def _footer(canvas, doc):  # noqa: ANN001
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(VIABILITY_GRAY)
        footer = FOOTER_TEXT.format(data=now_str)
        canvas.drawCentredString(PAGE_WIDTH / 2, 1.2 * cm, footer)
        canvas.drawRightString(
            PAGE_WIDTH - MARGIN,
            1.2 * cm,
            f"Pagina {doc.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf
