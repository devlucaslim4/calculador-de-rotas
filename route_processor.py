"""Processamento de planilhas e consulta de rotas via OSRM."""

from __future__ import annotations

import logging
import math
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode

# Usa os certificados confiáveis do Windows em redes corporativas. Isso precisa
# acontecer também neste módulo, pois ele pode ser executado sem importar o
# cliente do Checklist Fácil primeiro.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover - a dependência é instalada em produção
    pass

import requests
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

LOGGER = logging.getLogger(__name__)
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
OSRM_TABLE_URL = "https://router.project-osrm.org/table/v1/driving"
MAX_WORKERS = 4
# O servidor OSRM aceita até 100 coordenadas por tabela. Cada rota usa duas,
# portanto 50 pares reduzem pela metade as chamadas HTTP sem exceder o limite.
TABLE_BATCH_SIZE = 50
REQUEST_TIMEOUT = (5, 20)
MAX_RETRIES = 3

INITIAL_HEADER = "COORDENADA GPS INICIAL"
LEGACY_INITIAL_HEADER = "COORDENADA GPG INICIAL"
FINAL_HEADER = "COORDENADA GPS FINAL"
RESULT_HEADERS = ("DISTÂNCIA GPS", "STATUS DA ROTA", "LINK DA ROTA")
ODOMETER_INITIAL_HEADERS = (
    "VALOR ODOMETRO INICIAL",
    "ODOMETRO INICIAL",
    "HODOMETRO INICIAL",
    "KM INICIAL",
    "QUILOMETRAGEM INICIAL",
)
ODOMETER_FINAL_HEADERS = (
    "VALOR ODOMETRO FINAL",
    "ODOMETRO FINAL",
    "HODOMETRO FINAL",
    "KM FINAL",
    "QUILOMETRAGEM FINAL",
)
ODOMETER_DISTANCE_HEADER = "DISTÂNCIA HODÔMETRO"
PERCENT_DIFFERENCE_HEADER = "PERCENTUAL DIFERENÇA %"


class SpreadsheetError(ValueError):
    """Erro amigável relacionado à planilha enviada."""


@dataclass(frozen=True)
class RouteResult:
    distance_km: float | None
    status: str
    link: str | None


@dataclass(frozen=True)
class RouteGeometry:
    """Traçado rodoviário detalhado para a visualização interativa."""

    path: tuple[tuple[float, float], ...]
    distance_km: float
    duration_minutes: float


class RouteGeometryError(RuntimeError):
    """Falha amigável ao carregar o traçado detalhado de uma rota."""


@dataclass(frozen=True)
class ProcessingSummary:
    workbook: bytes
    total: int
    calculated: int
    failed: int


def normalize_header(value: object) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text).strip().upper()


def parse_coordinate(value: object) -> tuple[float, float] | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        return None
    try:
        latitude, longitude = map(float, parts)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(latitude) and math.isfinite(longitude)):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def parse_number(value: object) -> float | None:
    """Converte números do Excel, inclusive formatos brasileiros."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = re.sub(r"[^\d,.-]", "", str(value).strip())
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def google_maps_link(origin: tuple[float, float], destination: tuple[float, float]) -> str:
    params = urlencode({
        "api": 1,
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "travelmode": "driving",
    })
    return f"https://www.google.com/maps/dir/?{params}"


def fetch_route_geometry(
    origin_value: object,
    destination_value: object,
    session: requests.Session | None = None,
) -> RouteGeometry:
    """Busca no OSRM o caminho completo entre duas coordenadas.

    Esta consulta é separada do cálculo em lote para não aumentar o tempo da
    importação. A interface a executa somente para a rota escolhida no mapa.
    """

    origin = parse_coordinate(origin_value)
    destination = parse_coordinate(destination_value)
    if origin is None or destination is None:
        raise RouteGeometryError("As coordenadas desta rota são inválidas.")

    client = session or requests.Session()
    coordinates = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    url = f"{OSRM_URL}/{coordinates}"
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.get(
                url,
                params={"overview": "full", "geometries": "geojson", "steps": "false"},
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "Calculador-de-Rotas/2.0"},
            )
            if response.status_code in {429, 500, 502, 503, 504}:
                raise requests.RequestException(
                    f"OSRM temporariamente indisponível ({response.status_code})"
                )
            response.raise_for_status()
            payload = response.json()
            routes = payload.get("routes")
            if payload.get("code") == "NoRoute" or not routes:
                raise RouteGeometryError("Não foi encontrado um trajeto rodoviário para esta rota.")
            if payload.get("code") != "Ok":
                raise RouteGeometryError("O serviço de rotas não conseguiu montar este trajeto.")

            route = routes[0]
            raw_path = route.get("geometry", {}).get("coordinates")
            if not isinstance(raw_path, list) or len(raw_path) < 2:
                raise ValueError("Geometria da rota ausente ou incompleta")
            path: list[tuple[float, float]] = []
            for coordinate in raw_path:
                if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
                    raise ValueError("Ponto inválido na geometria da rota")
                longitude, latitude = float(coordinate[0]), float(coordinate[1])
                if not (
                    math.isfinite(latitude)
                    and math.isfinite(longitude)
                    and -90 <= latitude <= 90
                    and -180 <= longitude <= 180
                ):
                    raise ValueError("Ponto fora dos limites geográficos")
                path.append((longitude, latitude))
            return RouteGeometry(
                path=tuple(path),
                distance_km=round(float(route["distance"]) / 1000, 2),
                duration_minutes=round(float(route["duration"]) / 60, 1),
            )
        except RouteGeometryError:
            raise
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            last_error = exc
            LOGGER.warning(
                "Falha ao buscar geometria OSRM (tentativa %s/%s): %s",
                attempt + 1,
                MAX_RETRIES,
                exc,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.75 * (2**attempt))
    raise RouteGeometryError(
        "Não foi possível carregar o mapa desta rota agora. Tente novamente."
    ) from last_error


def calculate_route(
    origin_value: object,
    destination_value: object,
    session: requests.Session | None = None,
) -> RouteResult:
    origin = parse_coordinate(origin_value)
    if origin is None:
        return RouteResult(None, "Coordenada inicial inválida", None)
    destination = parse_coordinate(destination_value)
    if destination is None:
        return RouteResult(None, "Coordenada final inválida", None)

    route_link = google_maps_link(origin, destination)
    client = session or requests.Session()
    coordinates = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    url = f"{OSRM_URL}/{coordinates}"
    for attempt in range(MAX_RETRIES):
        try:
            response = client.get(
                url,
                params={"overview": "false", "steps": "false"},
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "Calculador-de-Rotas/1.0"},
            )
            if response.status_code in {429, 500, 502, 503, 504}:
                raise requests.RequestException(f"OSRM temporariamente indisponível ({response.status_code})")
            response.raise_for_status()
            data = response.json()
            if data.get("code") == "NoRoute" or not data.get("routes"):
                return RouteResult(None, "Rota não encontrada", route_link)
            if data.get("code") != "Ok":
                return RouteResult(None, "Falha na consulta", route_link)
            distance = round(float(data["routes"][0]["distance"]) / 1000, 2)
            return RouteResult(distance, "Calculada", route_link)
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            LOGGER.warning("Falha na consulta OSRM (tentativa %s/%s): %s", attempt + 1, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.75 * (2**attempt))
    return RouteResult(None, "Falha na consulta", route_link)


def calculate_routes_batch(
    pairs: list[tuple[tuple[float, float], tuple[float, float]]],
    session: requests.Session | None = None,
) -> dict[tuple[tuple[float, float], tuple[float, float]], RouteResult]:
    """Calcula várias rotas em poucas chamadas ao serviço matricial do OSRM."""

    if not pairs:
        return {}
    client = session or requests.Session()
    results: dict[tuple[tuple[float, float], tuple[float, float]], RouteResult] = {}

    for offset in range(0, len(pairs), TABLE_BATCH_SIZE):
        batch = pairs[offset : offset + TABLE_BATCH_SIZE]
        coordinates: list[str] = []
        source_indexes: list[str] = []
        destination_indexes: list[str] = []
        for index, (origin, destination) in enumerate(batch):
            source_indexes.append(str(index * 2))
            destination_indexes.append(str(index * 2 + 1))
            coordinates.extend(
                (
                    f"{origin[1]},{origin[0]}",
                    f"{destination[1]},{destination[0]}",
                )
            )

        url = f"{OSRM_TABLE_URL}/{';'.join(coordinates)}"
        batch_finished = False
        for attempt in range(MAX_RETRIES):
            try:
                response = client.get(
                    url,
                    params={
                        "sources": ";".join(source_indexes),
                        "destinations": ";".join(destination_indexes),
                        "annotations": "distance",
                    },
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "Calculador-de-Rotas/2.0"},
                )
                if response.status_code in {429, 500, 502, 503, 504}:
                    raise requests.RequestException(
                        f"OSRM temporariamente indisponível ({response.status_code})"
                    )
                response.raise_for_status()
                payload = response.json()
                distances = payload.get("distances")
                if payload.get("code") != "Ok" or not isinstance(distances, list):
                    raise ValueError("Resposta matricial inválida do OSRM")
                if len(distances) != len(batch):
                    raise ValueError("Matriz de distâncias incompleta")

                for index, pair in enumerate(batch):
                    origin, destination = pair
                    route_link = google_maps_link(origin, destination)
                    row = distances[index]
                    meters = row[index] if isinstance(row, list) and index < len(row) else None
                    if meters is None:
                        results[pair] = RouteResult(None, "Rota não encontrada", route_link)
                    else:
                        distance = round(float(meters) / 1000, 2)
                        results[pair] = RouteResult(distance, "Calculada", route_link)
                batch_finished = True
                break
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                LOGGER.warning(
                    "Falha na consulta OSRM em lote (tentativa %s/%s): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                )
                if attempt < MAX_RETRIES - 1:
                    time.sleep(0.75 * (2**attempt))

        if not batch_finished:
            # Mantém o funcionamento mesmo se o endpoint matricial estiver
            # temporariamente indisponível.
            for pair in batch:
                origin, destination = pair
                results[pair] = calculate_route(
                    f"{origin[0]},{origin[1]}",
                    f"{destination[0]},{destination[1]}",
                    session=client,
                )
    return results


def _find_headers(worksheet) -> tuple[int, int, dict[str, int]]:
    headers: dict[str, int] = {}
    for cell in worksheet[1]:
        normalized = normalize_header(cell.value)
        if normalized:
            headers[normalized] = cell.column

    initial = headers.get(normalize_header(INITIAL_HEADER))
    if initial is None:
        initial = headers.get(normalize_header(LEGACY_INITIAL_HEADER))
    final = headers.get(normalize_header(FINAL_HEADER))
    missing = []
    if initial is None:
        missing.append(INITIAL_HEADER)
    if final is None:
        missing.append(FINAL_HEADER)
    if missing:
        raise SpreadsheetError("Coluna(s) obrigatória(s) não encontrada(s): " + ", ".join(missing) + ".")
    return initial, final, headers


def _find_optional_header(headers: dict[str, int], aliases: tuple[str, ...]) -> int | None:
    for alias in aliases:
        column = headers.get(normalize_header(alias))
        if column is not None:
            return column
    return None


def process_workbook(
    file_bytes: bytes,
    progress_callback: Callable[[int, int], None] | None = None,
    route_function: Callable[[object, object], RouteResult] = calculate_route,
) -> ProcessingSummary:
    try:
        workbook = load_workbook(BytesIO(file_bytes))
    except Exception as exc:
        LOGGER.exception("Não foi possível abrir a planilha")
        raise SpreadsheetError("O arquivo não é uma planilha Excel válida ou está corrompido.") from exc

    worksheet = workbook.active
    if worksheet.max_row < 2:
        raise SpreadsheetError("A planilha está vazia. Inclua ao menos uma linha de dados.")
    initial_col, final_col, headers = _find_headers(worksheet)
    total = worksheet.max_row - 1

    result_columns: dict[str, int] = {}
    next_column = worksheet.max_column + 1
    for header in RESULT_HEADERS:
        normalized = normalize_header(header)
        column = headers.get(normalized)
        if column is None:
            column = next_column
            next_column += 1
            worksheet.cell(1, column, header)
        result_columns[header] = column

    odometer_initial_col = _find_optional_header(headers, ODOMETER_INITIAL_HEADERS)
    odometer_final_col = _find_optional_header(headers, ODOMETER_FINAL_HEADERS)
    odometer_distance_col = headers.get(normalize_header(ODOMETER_DISTANCE_HEADER))
    percent_difference_col = headers.get(normalize_header(PERCENT_DIFFERENCE_HEADER))
    if odometer_initial_col is not None and odometer_final_col is not None:
        if odometer_distance_col is None:
            odometer_distance_col = next_column
            next_column += 1
            worksheet.cell(1, odometer_distance_col, ODOMETER_DISTANCE_HEADER)
        if percent_difference_col is None:
            percent_difference_col = next_column
            next_column += 1
            worksheet.cell(1, percent_difference_col, PERCENT_DIFFERENCE_HEADER)

    rows = [
        (row, worksheet.cell(row, initial_col).value, worksheet.cell(row, final_col).value)
        for row in range(2, worksheet.max_row + 1)
    ]
    results: dict[int, RouteResult] = {}
    completed = 0
    if route_function is calculate_route:
        rows_by_pair: dict[
            tuple[tuple[float, float], tuple[float, float]], list[int]
        ] = {}
        for row, origin_value, destination_value in rows:
            origin = parse_coordinate(origin_value)
            destination = parse_coordinate(destination_value)
            if origin is None:
                results[row] = RouteResult(None, "Coordenada inicial inválida", None)
                completed += 1
            elif destination is None:
                results[row] = RouteResult(None, "Coordenada final inválida", None)
                completed += 1
            else:
                rows_by_pair.setdefault((origin, destination), []).append(row)
            if progress_callback and row in results:
                progress_callback(completed, total)

        batched_results = calculate_routes_batch(list(rows_by_pair))
        for pair, pair_rows in rows_by_pair.items():
            result = batched_results[pair]
            for row in pair_rows:
                results[row] = result
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
    else:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, max(1, total))) as executor:
            futures = {
                executor.submit(route_function, origin, destination): row
                for row, origin, destination in rows
            }
            for future in as_completed(futures):
                row = futures[future]
                try:
                    results[row] = future.result()
                except Exception:
                    LOGGER.exception("Erro inesperado ao processar a linha %s", row)
                    results[row] = RouteResult(None, "Falha na consulta", None)
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

    calculated = 0
    for row, _, _ in rows:
        result = results[row]
        distance_cell = worksheet.cell(row, result_columns["DISTÂNCIA GPS"])
        status_cell = worksheet.cell(row, result_columns["STATUS DA ROTA"])
        link_cell = worksheet.cell(row, result_columns["LINK DA ROTA"])
        distance_cell.value = result.distance_km
        distance_cell.number_format = "0.00"
        status_cell.value = result.status
        link_cell.value = "ABRIR ROTA" if result.link else None
        link_cell.hyperlink = result.link
        if result.link:
            link_cell.style = "Hyperlink"

        odometer_distance: float | None = None
        if odometer_initial_col is not None and odometer_final_col is not None:
            odometer_initial = parse_number(worksheet.cell(row, odometer_initial_col).value)
            odometer_final = parse_number(worksheet.cell(row, odometer_final_col).value)
            if odometer_initial is not None and odometer_final is not None:
                odometer_distance = odometer_final - odometer_initial
            if odometer_distance_col is not None:
                odometer_cell = worksheet.cell(row, odometer_distance_col)
                odometer_cell.value = odometer_distance
                odometer_cell.number_format = "0.00"
            if percent_difference_col is not None:
                percentage_cell = worksheet.cell(row, percent_difference_col)
                if (
                    odometer_distance is not None
                    and result.distance_km is not None
                    and result.distance_km > 0
                ):
                    percentage_cell.value = abs(odometer_distance - result.distance_km) / result.distance_km
                else:
                    percentage_cell.value = None
                percentage_cell.number_format = "0.00%"
        if result.status == "Calculada":
            calculated += 1

    styled_columns = [
        (result_columns["DISTÂNCIA GPS"], "DISTÂNCIA GPS", 18),
        (result_columns["STATUS DA ROTA"], "STATUS DA ROTA", 32),
        (result_columns["LINK DA ROTA"], "LINK DA ROTA", 18),
    ]
    if odometer_distance_col is not None:
        styled_columns.append((odometer_distance_col, ODOMETER_DISTANCE_HEADER, 24))
    if percent_difference_col is not None:
        styled_columns.append((percent_difference_col, PERCENT_DIFFERENCE_HEADER, 25))
    for column, header, width in styled_columns:
        header_cell = worksheet.cell(1, column)
        header_cell.value = header
        header_cell.font = Font(bold=True, color="FFFFFF")
        header_cell.fill = PatternFill("solid", fgColor="2563EB")
        worksheet.column_dimensions[get_column_letter(column)].width = width

    output = BytesIO()
    workbook.save(output)
    return ProcessingSummary(output.getvalue(), total, calculated, total - calculated)


def output_filename(original_name: str) -> str:
    safe_name = Path(original_name).name
    stem = Path(safe_name).stem or "planilha"
    return f"{stem}_com_distancia_gps.xlsx"
