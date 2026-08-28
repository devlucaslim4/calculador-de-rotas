"""Recursos de interface que não dependem do ciclo de renderização do Streamlit."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pandas as pd
from openpyxl import Workbook

from route_processor import FINAL_HEADER, INITIAL_HEADER, LEGACY_INITIAL_HEADER, normalize_header


@dataclass(frozen=True)
class UploadPreview:
    """Resultado da leitura e validação inicial de uma planilha."""

    dataframe: pd.DataFrame | None
    error: str | None

    @property
    def valid(self) -> bool:
        return self.dataframe is not None and self.error is None


def build_template_workbook() -> bytes:
    """Cria uma planilha modelo pequena, pronta para download."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rotas"
    sheet.append(["IDENTIFICAÇÃO", INITIAL_HEADER, FINAL_HEADER])
    sheet.append(["Exemplo 1", "-23.5505, -46.6333", "-22.9068, -43.1729"])
    sheet.freeze_panes = "A2"
    sheet.column_dimensions["A"].width = 22
    sheet.column_dimensions["B"].width = 29
    sheet.column_dimensions["C"].width = 29
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def validate_upload(file_bytes: bytes) -> UploadPreview:
    """Lê o Excel e valida os requisitos mínimos antes do processamento."""
    try:
        dataframe = pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
    except Exception:
        return UploadPreview(None, "Não foi possível abrir o arquivo. Confirme se ele é uma planilha .xlsx válida e não está corrompido.")

    if dataframe.empty:
        return UploadPreview(dataframe, "A planilha não contém rotas. Inclua pelo menos uma linha abaixo dos cabeçalhos.")

    headers = {normalize_header(column) for column in dataframe.columns}
    has_initial = normalize_header(INITIAL_HEADER) in headers or normalize_header(LEGACY_INITIAL_HEADER) in headers
    has_final = normalize_header(FINAL_HEADER) in headers
    missing = []
    if not has_initial:
        missing.append(INITIAL_HEADER)
    if not has_final:
        missing.append(FINAL_HEADER)
    if missing:
        return UploadPreview(dataframe, "Coluna(s) obrigatória(s) não encontrada(s): " + ", ".join(missing) + ".")
    return UploadPreview(dataframe, None)
