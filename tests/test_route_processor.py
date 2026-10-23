from io import BytesIO

from openpyxl import Workbook, load_workbook

import pytest

from route_processor import (
    SpreadsheetError,
    RouteGeometryError,
    RouteResult,
    calculate_route,
    calculate_routes_batch,
    fetch_route_geometry,
    output_filename,
    parse_coordinate,
    process_workbook,
)


def make_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Rotas"
    sheet.append(["Cliente", " COORDENADA gpg INICIAL ", "coordenada gps final"])
    sheet.append(["Válida", "-23.5505, -46.6333", "-22.9068, -43.1729"])
    sheet.append(["Origem inválida", "91, 0", "-22.9, -43.1"])
    sheet.append(["Destino vazio", "-23.5, -46.6", None])
    extra = workbook.create_sheet("Observações")
    extra["A1"] = "Conteúdo preservado"
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def fake_route(origin, destination):
    parsed_origin = parse_coordinate(origin)
    parsed_destination = parse_coordinate(destination)
    if parsed_origin is None:
        return RouteResult(None, "Coordenada inicial inválida", None)
    if parsed_destination is None:
        return RouteResult(None, "Coordenada final inválida", None)
    return RouteResult(432.1, "Calculada", "https://www.google.com/maps/dir/?api=1")


def test_parse_coordinate_validates_format_and_limits():
    assert parse_coordinate(" -23.5, -46.6 ") == (-23.5, -46.6)
    assert parse_coordinate("91, 0") is None
    assert parse_coordinate("0, 181") is None
    assert parse_coordinate("") is None


def test_valid_coordinates_keep_google_maps_link_when_osrm_has_no_route():
    class NoRouteResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"code": "NoRoute", "routes": []}

    class NoRouteSession:
        @staticmethod
        def get(*args, **kwargs):
            return NoRouteResponse()

    result = calculate_route("-23.5, -46.6", "-22.9, -43.2", session=NoRouteSession())

    assert result.distance_km is None
    assert result.status == "Rota não encontrada"
    assert result.link.startswith("https://www.google.com/maps/dir/")


def test_batch_calculation_extracts_each_pair_distance_from_matrix_diagonal():
    class TableResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "code": "Ok",
                "distances": [
                    [3_628.9, 429_508.5],
                    [434_437.1, 5_018.3],
                ],
            }

    class TableSession:
        calls = []

        @classmethod
        def get(cls, url, params=None, timeout=None, headers=None):
            cls.calls.append((url, params))
            return TableResponse()

    pairs = [
        ((-23.55052, -46.63331), (-23.56141, -46.65649)),
        ((-22.9068, -43.1729), (-22.9035, -43.2096)),
    ]
    results = calculate_routes_batch(pairs, session=TableSession())

    assert len(TableSession.calls) == 1
    assert results[pairs[0]].distance_km == 3.63
    assert results[pairs[1]].distance_km == 5.02
    assert all(result.status == "Calculada" for result in results.values())
    assert all(result.link.startswith("https://www.google.com/maps/dir/") for result in results.values())


def test_fetch_route_geometry_requests_geojson_and_returns_detailed_path():
    class GeometryResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "code": "Ok",
                "routes": [{
                    "distance": 3_620.5,
                    "duration": 615.0,
                    "geometry": {
                        "coordinates": [
                            [-46.6333, -23.5505],
                            [-46.6400, -23.5550],
                            [-46.6565, -23.5614],
                        ]
                    },
                }],
            }

    class GeometrySession:
        call = None

        @classmethod
        def get(cls, url, params=None, timeout=None, headers=None):
            cls.call = (url, params)
            return GeometryResponse()

    geometry = fetch_route_geometry(
        "-23.5505, -46.6333",
        "-23.5614, -46.6565",
        session=GeometrySession(),
    )

    assert GeometrySession.call[1]["overview"] == "full"
    assert GeometrySession.call[1]["geometries"] == "geojson"
    assert geometry.path[0] == (-46.6333, -23.5505)
    assert geometry.path[-1] == (-46.6565, -23.5614)
    assert geometry.distance_km == 3.62
    assert geometry.duration_minutes == 10.2


def test_fetch_route_geometry_rejects_route_without_road_path():
    class NoRouteResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"code": "NoRoute", "routes": []}

    class NoRouteSession:
        @staticmethod
        def get(*args, **kwargs):
            return NoRouteResponse()

    with pytest.raises(RouteGeometryError, match="trajeto rodoviário"):
        fetch_route_geometry("-23.5, -46.6", "-23.6, -46.7", session=NoRouteSession())


def test_process_workbook_preserves_sheets_and_writes_results():
    progress = []
    summary = process_workbook(make_workbook(), lambda done, total: progress.append((done, total)), fake_route)
    assert (summary.total, summary.calculated, summary.failed) == (3, 1, 2)
    assert progress[-1] == (3, 3)

    workbook = load_workbook(BytesIO(summary.workbook))
    assert workbook.sheetnames == ["Rotas", "Observações"]
    assert workbook["Observações"]["A1"].value == "Conteúdo preservado"
    sheet = workbook["Rotas"]
    headers = {cell.value: cell.column for cell in sheet[1]}
    assert sheet.cell(2, headers["DISTÂNCIA GPS"]).value == 432.1
    assert sheet.cell(2, headers["STATUS DA ROTA"]).value == "Calculada"
    assert sheet.cell(2, headers["LINK DA ROTA"]).value == "ABRIR ROTA"
    assert sheet.cell(2, headers["LINK DA ROTA"]).hyperlink.target.startswith("https://")
    assert sheet.cell(3, headers["LINK DA ROTA"]).value is None


def test_output_filename_uses_uploaded_name():
    assert output_filename("rotas_junho.xlsx") == "rotas_junho_com_distancia_gps.xlsx"


def test_rejects_corrupted_workbook():
    with pytest.raises(SpreadsheetError, match="corrompido"):
        process_workbook("não é um arquivo xlsx".encode(), route_function=fake_route)


def test_rejects_missing_required_columns():
    workbook = Workbook()
    workbook.active.append(["Cliente", "Endereço"])
    workbook.active.append(["Teste", "Rua A"])
    output = BytesIO()
    workbook.save(output)
    with pytest.raises(SpreadsheetError, match="Coluna"):
        process_workbook(output.getvalue(), route_function=fake_route)
