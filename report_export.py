"""Geração do relatório executivo da análise em PDF."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from analysis_engine import AnalysisData

BLUE = colors.HexColor("#2563EB")
DARK = colors.HexColor("#111827")
SLATE = colors.HexColor("#475569")
LIGHT = colors.HexColor("#E2E8F0")
PALE = colors.HexColor("#F8FAFC")


def _display_metric(label: str, value: object) -> str:
    if value is None or pd.isna(value):
        return "Nao disponivel"
    if "quilômetro" in label.lower() or "média" in label.lower():
        return f"{float(value):,.2f} km".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(value):,}".replace(",", ".")


def _safe_text(value: object) -> str:
    return "" if value is None or pd.isna(value) else str(value)


def _footer(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LIGHT)
    canvas.line(16 * mm, 12 * mm, landscape(A4)[0] - 16 * mm, 12 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SLATE)
    canvas.drawString(16 * mm, 7.5 * mm, "Calculador de Rotas - Relatorio de analise")
    canvas.drawRightString(landscape(A4)[0] - 16 * mm, 7.5 * mm, f"Pagina {document.page}")
    canvas.restoreState()


def _data_table(rows: list[list[object]], widths: list[float] | None = None, repeat_rows: int = 1) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=repeat_rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("GRID", (0, 0), (-1, -1), .35, LIGHT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def analysis_pdf(
    metrics: dict[str, object],
    filtered: pd.DataFrame,
    audit: pd.DataFrame,
    analysis: AnalysisData,
    original_name: str,
) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title="Relatorio de analise de rotas",
        author="Calculador de Rotas",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("TitleCustom", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=DARK, spaceAfter=4)
    subtitle = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=9, textColor=SLATE, spaceAfter=12)
    section = ParagraphStyle("Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=DARK, spaceBefore=8, spaceAfter=7)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, leading=10, textColor=DARK)
    centered = ParagraphStyle("Centered", parent=small, alignment=TA_CENTER)
    right = ParagraphStyle("Right", parent=small, alignment=TA_RIGHT)

    story = [
        Paragraph("Relatorio consolidado de rotas", title),
        Paragraph(f"Arquivo analisado: {original_name} | Registros filtrados: {len(filtered):,}".replace(",", "."), subtitle),
    ]

    metric_cells = []
    for label, value in metrics.items():
        metric_cells.append([
            Paragraph(label, centered),
            Paragraph(f"<b>{_display_metric(label, value)}</b>", centered),
        ])
    metric_cards = []
    for start in range(0, len(metric_cells), 4):
        row = []
        for label_value in metric_cells[start:start + 4]:
            card = Table([[label_value[0]], [label_value[1]]], colWidths=[61 * mm], rowHeights=[9 * mm, 12 * mm])
            card.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), PALE),
                ("BOX", (0, 0), (-1, -1), .6, LIGHT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))
            row.append(card)
        metric_cards.append(row)
    cards = Table(metric_cards, colWidths=[63 * mm] * 4, hAlign="LEFT")
    cards.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    story.extend([cards, Spacer(1, 5 * mm)])

    routes = analysis.unique_routes(filtered)
    user, unit = analysis.columns.get("usuario"), analysis.columns.get("unidade")
    summaries = []
    if user:
        users = routes.groupby(user, dropna=False).agg(Rotas=(user, "size"), Quilometros=("__distancia_gps_valida", "sum")).reset_index().sort_values("Rotas", ascending=False).head(10)
        rows = [["Usuario", "Rotas", "Quilometros GPS"]] + [[Paragraph(str(row[user]), small), int(row["Rotas"]), Paragraph(_display_metric("quilômetros", row["Quilometros"]), right)] for _, row in users.iterrows()]
        summaries.append(("Principais usuarios", _data_table(rows, [52 * mm, 22 * mm, 34 * mm])))
    if unit:
        units = routes.groupby(unit, dropna=False).agg(Rotas=(unit, "size"), Quilometros=("__distancia_gps_valida", "sum")).reset_index().sort_values("Rotas", ascending=False).head(10)
        rows = [["Unidade", "Rotas", "Quilometros GPS"]] + [[Paragraph(str(row[unit]), small), int(row["Rotas"]), Paragraph(_display_metric("quilômetros", row["Quilometros"]), right)] for _, row in units.iterrows()]
        summaries.append(("Principais unidades", _data_table(rows, [52 * mm, 22 * mm, 34 * mm])))

    if summaries:
        blocks = []
        for heading, table in summaries:
            block = Table([[Paragraph(heading, section)], [table]], colWidths=[118 * mm])
            block.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
            blocks.append(block)
        story.append(Table([blocks], colWidths=[125 * mm] * len(blocks), hAlign="LEFT", style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8)])))

    story.extend([PageBreak(), Paragraph("Auditoria dos dados", title)])
    if audit.empty:
        story.append(Paragraph("Nenhuma inconsistencia foi identificada com os limites selecionados.", styles["Normal"]))
    else:
        visible = audit.drop(columns=["Índice da linha"], errors="ignore").copy().head(60)
        rows = [["ID", "Usuario", "Unidade", "Data", "Inconsistencia", "Valor", "Observacao"]]
        for _, row in visible.iterrows():
            date_value = row.get("Data")
            date_text = date_value.strftime("%d/%m/%Y %H:%M") if pd.notna(date_value) and hasattr(date_value, "strftime") else ""
            rows.append([
                Paragraph(_safe_text(row.get("ID da resposta")), small),
                Paragraph(_safe_text(row.get("Usuário")), small),
                Paragraph(_safe_text(row.get("Unidade")), small),
                Paragraph(date_text, small),
                Paragraph(_safe_text(row.get("Tipo da inconsistência")), small),
                Paragraph(_safe_text(row.get("Valor encontrado")), small),
                Paragraph(_safe_text(row.get("Observação")), small),
            ])
        story.append(_data_table(rows, [20 * mm, 27 * mm, 25 * mm, 29 * mm, 48 * mm, 25 * mm, 85 * mm]))
        if len(audit) > len(visible):
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph(f"O PDF apresenta as primeiras {len(visible)} inconsistencias. Consulte o Excel para a lista completa.", subtitle))

    document.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output.getvalue()
