"""Serviço compartilhado pelo Streamlit e pela API REST.

Este módulo apenas coordena os componentes existentes. As regras de consulta,
transformação, cálculo de rotas e geração do Excel continuam nos módulos
originais do projeto.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Callable

import pandas as pd

from analysis_engine import apply_filters, build_audit, calculate_metrics, prepare_analysis
from api.config import ApiSettings
from checklist_api import ChecklistApiClient
from checklist_transform import build_standardized_workbook, transformar_checklists_em_planilha
from route_processor import ProcessingSummary, process_workbook

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalculationResult:
    """Resultado serializável da importação e do cálculo de um período."""

    status: str
    message: str
    year: int
    month: int
    found: int
    valid: int
    inconsistent: int
    duplicates: int
    calculated: int
    failed: int
    metrics: dict[str, object]
    preview: list[dict[str, object]]
    warnings: tuple[str, ...]
    workbook: bytes | None
    filename: str | None


class CalculadorService:
    """Orquestra o mesmo motor utilizado pelo fluxo de importação do app."""

    def __init__(
        self,
        settings: ApiSettings,
        *,
        client_factory: Callable[[str], ChecklistApiClient] = ChecklistApiClient,
        workbook_processor: Callable[[bytes], ProcessingSummary] = process_workbook,
    ) -> None:
        self.settings = settings
        self.client_factory = client_factory
        self.workbook_processor = workbook_processor

    def processar_periodo(
        self,
        year: int,
        month: int,
        *,
        filters: dict[str, object] | None = None,
        preview_limit: int = 10,
    ) -> CalculationResult:
        process_started = time.perf_counter()
        client = self.client_factory(self.settings.checklist_api_token)
        stage_started = time.perf_counter()
        snapshot = client.fetch_month_snapshot(
            year,
            month,
            category_id=self.settings.category_id,
            timezone_name=self.settings.timezone_name,
        )
        LOGGER.info(
            "Checklist snapshot loaded",
            extra={
                "year": year,
                "month": month,
                "evaluations": len(snapshot.evaluations),
                "duration_ms": round((time.perf_counter() - stage_started) * 1000),
            },
        )
        stage_started = time.perf_counter()
        transformed = transformar_checklists_em_planilha(
            snapshot,
            self.settings.item_mapping,
            timezone_name=self.settings.timezone_name,
        )
        LOGGER.info(
            "Checklist records transformed",
            extra={
                "records": transformed.found,
                "valid_routes": transformed.valid,
                "duration_ms": round((time.perf_counter() - stage_started) * 1000),
            },
        )
        warnings = list(transformed.mapping_warnings)
        if transformed.duplicate_count:
            warnings.append(
                f"{transformed.duplicate_count} registro(s) duplicado(s) foram "
                "consolidados pelo ID da resposta."
            )

        if not transformed.valid:
            return CalculationResult(
                status="sem_rotas_validas",
                message=(
                    "A consulta foi concluída, mas nenhum registro possui as duas "
                    "coordenadas válidas para calcular a rota."
                ),
                year=year,
                month=month,
                found=transformed.found,
                valid=0,
                inconsistent=transformed.inconsistent,
                duplicates=transformed.duplicate_count,
                calculated=0,
                failed=0,
                metrics={},
                preview=_records(transformed.all_rows, preview_limit),
                warnings=tuple(warnings),
                workbook=None,
                filename=None,
            )

        standardized = build_standardized_workbook(transformed)
        stage_started = time.perf_counter()
        processed = self.workbook_processor(standardized)
        LOGGER.info(
            "Routes calculated and workbook generated",
            extra={
                "records": processed.total,
                "routes_calculated": processed.calculated,
                "routes_failed": processed.failed,
                "duration_ms": round((time.perf_counter() - stage_started) * 1000),
            },
        )
        stage_started = time.perf_counter()
        dataframe = pd.read_excel(BytesIO(processed.workbook))
        analysis = prepare_analysis(dataframe)
        selections = dict(filters or {})
        filter_start = selections.pop("data_inicio", None)
        filter_end = selections.pop("data_fim", None)
        if filter_start is not None or filter_end is not None:
            selections["periodo"] = (filter_start, filter_end)
        filtered = apply_filters(analysis, selections)
        audit = build_audit(analysis)
        inconsistent_indices = (
            set(audit["Índice da linha"].dropna().astype(int).tolist())
            if "Índice da linha" in audit
            else set()
        )
        metrics = calculate_metrics(analysis, filtered, inconsistent_indices)
        LOGGER.info(
            "Route analysis prepared",
            extra={"duration_ms": round((time.perf_counter() - stage_started) * 1000)},
        )
        warnings.extend(analysis.warnings)
        status = "concluido_com_alertas" if processed.failed else "concluido"
        message = (
            f"Processamento concluído: {processed.calculated} rota(s) calculada(s)"
            + (f" e {processed.failed} não calculada(s)." if processed.failed else ".")
        )
        public_columns = [column for column in filtered.columns if not str(column).startswith("__")]
        LOGGER.info(
            "Route processing finished",
            extra={"duration_ms": round((time.perf_counter() - process_started) * 1000)},
        )
        return CalculationResult(
            status=status,
            message=message,
            year=year,
            month=month,
            found=transformed.found,
            valid=transformed.valid,
            inconsistent=transformed.inconsistent,
            duplicates=transformed.duplicate_count,
            calculated=processed.calculated,
            failed=processed.failed,
            metrics=_json_safe_dict(metrics),
            preview=_records(filtered[public_columns], preview_limit),
            warnings=tuple(dict.fromkeys(warnings)),
            workbook=processed.workbook,
            filename=f"checklists_{year}_{month:02d}_tratada.xlsx",
        )


def _json_safe(value: object) -> object:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass
    return value


def _json_safe_dict(values: dict[str, object]) -> dict[str, object]:
    return {str(key): _json_safe(value) for key, value in values.items()}


def _records(dataframe: pd.DataFrame, limit: int) -> list[dict[str, object]]:
    if limit <= 0 or dataframe.empty:
        return []
    records: list[dict[str, object]] = []
    for row in dataframe.head(limit).to_dict(orient="records"):
        records.append({str(key): _json_safe(value) for key, value in row.items()})
    return records
