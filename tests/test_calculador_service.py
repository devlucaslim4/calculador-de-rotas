from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from openpyxl import load_workbook

from api.config import ApiSettings
from checklist_api import ChecklistSnapshot
from checklist_transform import build_standardized_workbook, transformar_checklists_em_planilha
from route_processor import RouteResult, process_workbook
from services.calculador import CalculadorService


def _snapshot() -> ChecklistSnapshot:
    return ChecklistSnapshot(
        category_id=2_879_584,
        checklist_id=9,
        year=2026,
        month=10,
        evaluations=[
            {
                "evaluationId": 55,
                "checklistId": 9,
                "status": 6,
                "userId": 3,
                "unitId": 4,
                "startedAt": "2026-10-05T11:00:00+00:00",
                "concludedAt": "2026-10-05T12:00:00+00:00",
                "initialLatitude": -23.5,
                "initialLongitude": -46.6,
                "finalLatitude": -22.9,
                "finalLongitude": -43.2,
            }
        ],
        results_by_evaluation={
            55: [
                {"resultId": 1, "itemId": 101, "categoryId": 2_879_584, "number": 1000},
                {"resultId": 2, "itemId": 102, "categoryId": 2_879_584, "number": 1125.5},
                {
                    "resultId": 3,
                    "itemId": 103,
                    "categoryId": 2_879_584,
                    "selectedOptions": [{"optionText": "Visita"}],
                },
                {"resultId": 4, "itemId": 104, "categoryId": 2_879_584, "text": "CC-100"},
            ]
        },
        users=[{"userId": 3, "name": "Ana", "userTypeId": 7}],
        user_types=[{"userTypeId": 7, "name": "Motorista"}],
        units=[{"unitId": 4, "name": "Unidade SP"}],
        unit_regions=[{"unitId": 4, "regionId": 8}],
        regions=[{"regionId": 8, "name": "Sudeste", "hierarchyName": "Brasil > Sudeste"}],
        items=[
            {"itemId": 101, "categoryId": 2_879_584, "name": "Valor hodômetro inicial"},
            {"itemId": 102, "categoryId": 2_879_584, "name": "Valor hodômetro final"},
            {"itemId": 103, "categoryId": 2_879_584, "name": "Motivo"},
            {"itemId": 104, "categoryId": 2_879_584, "name": "Centro de custo"},
        ],
    )


class FakeClient:
    def __init__(self, _token: str) -> None:
        pass

    def fetch_month_snapshot(self, year, month, *, category_id, timezone_name):
        assert (year, month, category_id, timezone_name) == (
            2026,
            10,
            2_879_584,
            "America/Sao_Paulo",
        )
        return _snapshot()


def _fake_route(_origin, _destination):
    return RouteResult(321.45, "Calculada", "https://www.google.com/maps/dir/?api=1")


def _processor(workbook: bytes):
    return process_workbook(workbook, route_function=_fake_route)


def _settings(tmp_path: Path) -> ApiSettings:
    return ApiSettings(
        inbound_api_key="api",
        file_signing_secret="files",
        checklist_api_token="checklist",
        item_mapping={},
        temp_directory=tmp_path,
    )


def _test_path() -> Path:
    path = Path(".tmp/service-tests") / str(uuid4())
    path.mkdir(parents=True)
    return path


def _cell_contract(workbook_bytes: bytes):
    workbook = load_workbook(BytesIO(workbook_bytes))
    return [
        [
            (cell.value, cell.number_format, cell.hyperlink.target if cell.hyperlink else None)
            for cell in row
        ]
        for row in workbook.active.iter_rows()
    ]


def test_api_service_reuses_the_same_excel_pipeline_as_streamlit():
    tmp_path = _test_path()
    service = CalculadorService(
        _settings(tmp_path),
        client_factory=FakeClient,
        workbook_processor=_processor,
    )
    result = service.processar_periodo(2026, 10, preview_limit=5)

    transformed = transformar_checklists_em_planilha(_snapshot(), {})
    direct = _processor(build_standardized_workbook(transformed))

    assert result.workbook is not None
    assert _cell_contract(result.workbook) == _cell_contract(direct.workbook)
    assert result.calculated == 1
    assert result.metrics["Total de rotas únicas"] == 1
    assert result.preview[0]["ID RESPOSTA"] == 55


def test_service_does_not_call_route_processor_without_valid_coordinates():
    tmp_path = _test_path()
    snapshot = _snapshot()
    snapshot.evaluations[0]["initialLatitude"] = None
    snapshot.evaluations[0]["initialLongitude"] = None

    class InvalidClient(FakeClient):
        def fetch_month_snapshot(self, *args, **kwargs):
            return snapshot

    called = False

    def processor(_workbook):
        nonlocal called
        called = True
        raise AssertionError("Não deveria calcular uma planilha sem rotas válidas")

    result = CalculadorService(
        _settings(tmp_path),
        client_factory=InvalidClient,
        workbook_processor=processor,
    ).processar_periodo(2026, 10)

    assert result.status == "sem_rotas_validas"
    assert result.workbook is None
    assert not called


def test_date_filter_changes_summary_but_preserves_generated_workbook():
    service = CalculadorService(
        _settings(_test_path()),
        client_factory=FakeClient,
        workbook_processor=_processor,
    )
    result = service.processar_periodo(
        2026,
        10,
        filters={"data_inicio": date(2026, 10, 6), "data_fim": None},
        preview_limit=5,
    )

    assert result.metrics["Total de rotas únicas"] == 0
    assert result.preview == []
    assert result.workbook is not None
    assert result.calculated == 1
