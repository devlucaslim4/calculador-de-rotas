"""Identidade visual comum às planilhas geradas pelo Calculador de Rotas."""

from __future__ import annotations

import unicodedata

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

NAVY = "101C2B"
MINT = "56CFAD"
ORANGE = "F36C21"
ORANGE_LIGHT = "FCE4D6"
TEXT = "26384B"
STRIPE = "F3F6F9"
MINT_LIGHT = "EAF7F2"
GRID = "DCE5EB"

_WIDTHS = {
    "DESCRIÇÃO DO STATUS": 24,
    "ID RESPOSTA": 16,
    "NOME": 30,
    "TIPO DE USUÁRIO": 21,
    "UNIDADE": 24,
    "REGIÃO": 22,
    "DATA INÍCIO": 21,
    "DATA CONCLUSÃO": 21,
    "COORDENADA GPS INICIAL": 24,
    "VALOR ODOMETRO INICIAL": 22,
    "COORDENADA GPS FINAL": 24,
    "VALOR ODOMETRO FINAL": 22,
    "MOTIVO": 30,
    "CENTRO DE CUSTO": 24,
    "DISTÂNCIA HODÔMETRO": 21,
    "VALIDAÇÃO": 28,
    "PERCENTUAL DIFERENÇA %": 23,
    "DISTÂNCIA GPS": 18,
    "STATUS DA ROTA": 22,
    "LINK DA ROTA": 17,
    "PIX": 36,
    "VALOR": 18,
    "PAGAMENTO": 18,
}
_MINT_COLUMNS = {"PIX", "VALOR", "PAGAMENTO"}
_DATE_COLUMNS = {"DATA INÍCIO", "DATA CONCLUSÃO"}
_DECIMAL_COLUMNS = {
    "DISTÂNCIA HODÔMETRO",
    "VALOR ODOMETRO INICIAL",
    "VALOR ODOMETRO FINAL",
    "DISTÂNCIA GPS",
}
_PERCENT_COLUMNS = {"PERCENTUAL DIFERENÇA %"}


def _normalize_header(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper()


_NORMALIZED_WIDTHS = {_normalize_header(label): width for label, width in _WIDTHS.items()}
_NORMALIZED_MINT_COLUMNS = {_normalize_header(label) for label in _MINT_COLUMNS}
_NORMALIZED_DATE_COLUMNS = {_normalize_header(label) for label in _DATE_COLUMNS}
_NORMALIZED_DECIMAL_COLUMNS = {_normalize_header(label) for label in _DECIMAL_COLUMNS}
_NORMALIZED_PERCENT_COLUMNS = {_normalize_header(label) for label in _PERCENT_COLUMNS}


def style_worksheet(worksheet) -> None:
    """Aplica estilo logístico legível sem alterar valores ou fórmulas."""

    if worksheet.max_row < 1 or worksheet.max_column < 1:
        return

    worksheet.sheet_view.showGridLines = False
    worksheet.sheet_view.zoomScale = 90
    worksheet.sheet_properties.tabColor = MINT
    worksheet.freeze_panes = "C2"
    worksheet.auto_filter.ref = worksheet.dimensions
    worksheet.row_dimensions[1].height = 38

    header_fill = PatternFill("solid", fgColor=ORANGE_LIGHT)
    stripe_fill = PatternFill("solid", fgColor=STRIPE)
    mint_data_fill = PatternFill("solid", fgColor=MINT_LIGHT)
    no_fill = PatternFill(fill_type=None)
    header_border = Border(bottom=Side(style="medium", color=ORANGE))
    row_border = Border(bottom=Side(style="hair", color=GRID))
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    data_alignment = Alignment(vertical="center", wrap_text=False)

    headers: dict[int, str] = {}
    for cell in worksheet[1]:
        header = _normalize_header(cell.value)
        headers[cell.column] = header
        cell.font = Font(name="Aptos", size=10, bold=True, color=NAVY)
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = header_border
        worksheet.column_dimensions[get_column_letter(cell.column)].width = _NORMALIZED_WIDTHS.get(header, 19)

    for row_number in range(2, worksheet.max_row + 1):
        row_fill = stripe_fill if row_number % 2 == 0 else no_fill
        worksheet.row_dimensions[row_number].height = 21
        for cell in worksheet[row_number]:
            header = headers.get(cell.column, "")
            cell.fill = mint_data_fill if header in _NORMALIZED_MINT_COLUMNS else row_fill
            cell.alignment = data_alignment
            cell.border = row_border
            if cell.hyperlink:
                cell.font = Font(name="Aptos", size=10, color="2563EB", underline="single")
            else:
                cell.font = Font(name="Aptos", size=10, color=TEXT)
            if header in _NORMALIZED_DATE_COLUMNS:
                cell.number_format = "dd/mm/yyyy hh:mm:ss"
            elif header in _NORMALIZED_DECIMAL_COLUMNS and isinstance(cell.value, (int, float)):
                cell.number_format = "#,##0.00"
            elif header in _NORMALIZED_PERCENT_COLUMNS and isinstance(cell.value, (int, float)):
                cell.number_format = "0.00%"
            elif header in {"VALOR", "PAGAMENTO"} and isinstance(cell.value, (int, float)):
                cell.number_format = '"R$" #,##0.00'
