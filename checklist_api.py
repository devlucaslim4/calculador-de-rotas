"""Cliente da API Analytics do Checklist Fácil.

As consultas deste módulo são deliberadamente acionadas somente pela interface.
Nenhuma credencial é persistida ou incluída em mensagens de log.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

# Em redes corporativas, o certificado raiz pode existir no Windows e não no
# pacote estático certifi usado pelo requests. O truststore mantém a validação
# TLS ativa e delega a confiança ao repositório nativo do sistema operacional.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:  # pragma: no cover - a dependência é instalada em produção
    pass

import requests

LOGGER = logging.getLogger(__name__)

API_BASE_URL = "https://api-analytics.checklistfacil.com.br"
DEFAULT_CATEGORY_ID = 2_879_584
DEFAULT_TIMEZONE = "America/Sao_Paulo"
PAGE_LIMIT = 1_000
REQUEST_TIMEOUT = (5, 45)
RETRYABLE_STATUS = {429, 500, 502, 503, 504, 519}


class ChecklistApiError(RuntimeError):
    """Erro amigável ao consultar a API Analytics."""


class ChecklistAuthenticationError(ChecklistApiError):
    """A chave não foi aceita ou não possui permissão."""


class ChecklistIncompleteError(ChecklistApiError):
    """A API não permitiu confirmar que todos os dados foram recebidos."""


@dataclass(frozen=True)
class ChecklistSnapshot:
    """Dados completos necessários para produzir a planilha do período."""

    category_id: int
    checklist_id: int
    year: int
    month: int
    evaluations: list[dict[str, Any]]
    results_by_evaluation: dict[int, list[dict[str, Any]]]
    users: list[dict[str, Any]]
    user_types: list[dict[str, Any]]
    units: list[dict[str, Any]]
    unit_regions: list[dict[str, Any]]
    regions: list[dict[str, Any]]
    items: list[dict[str, Any]]
    duplicate_count: int = 0


def month_bounds(year: int, month: int, timezone_name: str = DEFAULT_TIMEZONE) -> tuple[datetime, datetime]:
    """Retorna início inclusivo e fim exclusivo do mês no fuso informado."""

    if not 1 <= month <= 12:
        raise ValueError("O mês deve estar entre 1 e 12.")
    timezone = ZoneInfo(timezone_name)
    start = datetime(year, month, 1, tzinfo=timezone)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone)
    return start, end


def parse_api_datetime(value: object) -> datetime | None:
    """Converte uma data ISO 8601 da API para datetime com timezone."""

    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


class ChecklistApiClient:
    """Cliente HTTP com paginação, retentativas e validação de completude."""

    def __init__(
        self,
        token: str,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        min_interval_seconds: float = 0.31,
        max_retries: int = 3,
    ) -> None:
        if not token or not token.strip():
            raise ChecklistAuthenticationError(
                "A chave da API do Checklist Fácil não foi configurada nos secrets."
            )
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token.strip()}",
                "Accept": "application/json",
                "User-Agent": "Calculador-de-Rotas/2.0",
            }
        )
        self.sleep = sleep
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self.max_retries = max(1, max_retries)
        self._last_request_at: float | None = None

    def _respect_minimum_interval(self) -> None:
        if self._last_request_at is None or self.min_interval_seconds == 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            self.sleep(self.min_interval_seconds - elapsed)

    @staticmethod
    def _retry_delay(response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        try:
            return max(float(retry_after), 0.0)
        except (TypeError, ValueError):
            if response.status_code == 429:
                return 60.0
            return min(1.5 * (2**attempt), 30.0)

    def _get(self, path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
        url = f"{API_BASE_URL}{path}"
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            self._respect_minimum_interval()
            try:
                response = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                self._last_request_at = time.monotonic()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries - 1:
                    self.sleep(min(1.5 * (2**attempt), 30.0))
                    continue
                raise ChecklistApiError(
                    "Não foi possível conectar à API do Checklist Fácil. Tente novamente."
                ) from exc

            if response.status_code in {401, 403}:
                raise ChecklistAuthenticationError(
                    "A API recusou a credencial. Verifique a chave e as permissões do usuário."
                )
            if response.status_code == 429 and response.headers.get("X-DailyLimit-Remaining") == "0":
                reset = response.headers.get("X-DailyLimit-Reset", "horário informado pela API")
                raise ChecklistApiError(
                    f"O limite diário da API foi atingido. O contador será liberado em {reset}."
                )
            if response.status_code in RETRYABLE_STATUS:
                last_error = ChecklistApiError(f"Resposta temporária HTTP {response.status_code}.")
                if attempt < self.max_retries - 1:
                    self.sleep(self._retry_delay(response, attempt))
                    continue
                raise ChecklistApiError(
                    f"A API permaneceu indisponível apó {self.max_retries} tentativas "
                    f"(HTTP {response.status_code})."
                )
            if response.status_code in {400, 422}:
                detail = _validation_error_detail(response)
                suffix = f" Detalhes: {detail}" if detail else ""
                raise ChecklistApiError(
                    f"A API rejeitou os filtros da consulta (HTTP {response.status_code}).{suffix}"
                )
            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                raise ChecklistApiError(
                    f"A API rejeitou a consulta (HTTP {response.status_code}). Revise os filtros e tente novamente."
                ) from exc
            try:
                payload = response.json()
            except ValueError as exc:
                raise ChecklistIncompleteError("A API retornou uma resposta que não é JSON válido.") from exc
            if not isinstance(payload, dict):
                raise ChecklistIncompleteError("A resposta da API não possui o formato esperado.")
            return payload

        raise ChecklistApiError("A consulta falhou.") from last_error

    @staticmethod
    def _validate_page(payload: dict[str, Any], requested_page: int, path: str) -> tuple[list[dict[str, Any]], bool]:
        data = payload.get("data")
        meta = payload.get("meta")
        if not isinstance(data, list) or not isinstance(meta, dict):
            raise ChecklistIncompleteError(
                f"A resposta de {path} não trouxe os campos data/meta necessários."
            )
        current_page = meta.get("currentPage")
        if current_page is not None:
            try:
                if int(current_page) != requested_page:
                    raise ChecklistIncompleteError(
                        f"A API devolveu a página {current_page} quando a página {requested_page} foi solicitada."
                    )
            except (TypeError, ValueError) as exc:
                raise ChecklistIncompleteError("A API devolveu um número de página inválido.") from exc
        if "hasMore" not in meta:
            raise ChecklistIncompleteError(
                f"A resposta de {path} não informou hasMore; a completude não pode ser confirmada."
            )
        rows = [row for row in data if isinstance(row, dict)]
        if len(rows) != len(data):
            raise ChecklistIncompleteError(f"A resposta de {path} contém registros inválidos.")
        return rows, bool(meta["hasMore"])

    def iter_paginated(self, path: str, params: dict[str, object] | None = None) -> list[dict[str, Any]]:
        """Lê todas as páginas e só retorna quando a completude foi confirmada."""

        result: list[dict[str, Any]] = []
        page = 1
        while True:
            page_params = dict(params or {})
            page_params.update({"page": page, "limit": PAGE_LIMIT})
            payload = self._get(path, page_params)
            rows, has_more = self._validate_page(payload, page, path)
            result.extend(rows)
            if not has_more:
                return result
            if not rows:
                raise ChecklistIncompleteError(
                    f"A página {page} de {path} veio vazia, mas a API informou que existem mais dados."
                )
            page += 1
            if page > 10_000:
                raise ChecklistIncompleteError("A paginação excedeu o limite de segurança.")

    def get_evaluation_results(self, evaluation_id: int) -> list[dict[str, Any]]:
        """Obtém os resultados v3; o endpoint individual não expõe page/limit."""

        path = f"/v3/evaluations/{int(evaluation_id)}/results"
        payload = self._get(path)
        rows, has_more = self._validate_page(payload, 1, path)
        if has_more:
            raise ChecklistIncompleteError(
                f"A resposta da avaliação {evaluation_id} foi paginada, mas este endpoint não "
                "documenta parâmetros de paginação. Nenhum arquivo parcial foi gerado."
            )
        return rows

    def list_evaluation_results(
        self,
        checklist_id: int,
        year: int,
        month: int,
        evaluation_ids: set[int],
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> dict[int, list[dict[str, Any]]]:
        """Busca em lote e agrupa os resultados das avaliações selecionadas.

        O endpoint agregado evita uma chamada HTTP para cada checklist aplicado.
        A filtragem final pelos IDs já validados impede que respostas fora do
        período entrem no arquivo caso a API retorne dados adicionais.
        """

        grouped: dict[int, list[dict[str, Any]]] = {
            evaluation_id: [] for evaluation_id in evaluation_ids
        }
        if not evaluation_ids:
            return grouped

        start, end = month_bounds(year, month, timezone_name)
        rows = self.iter_paginated(
            "/v3/evaluations/results",
            {
                "checklistId": checklist_id,
                "concludedAt[gte]": start.isoformat(timespec="seconds"),
                "concludedAt[lte]": (end - timedelta(seconds=1)).isoformat(timespec="seconds"),
                "deletedAt": "null",
            },
        )
        for row in rows:
            evaluation_id = _integer(row.get("evaluationId"))
            if evaluation_id in grouped:
                grouped[evaluation_id].append(row)
        return grouped

    def resolve_checklist_id(self, category_id: int) -> int:
        categories = self.iter_paginated("/v1/categories", {"deletedAt": "null"})
        matches = [row for row in categories if _same_id(row.get("categoryId"), category_id)]
        if not matches:
            raise ChecklistApiError(
                f"A categoria {category_id} não foi encontrada ou não está acessível para esta chave."
            )
        checklist_ids = {_integer(row.get("checklistId")) for row in matches}
        checklist_ids.discard(None)
        if len(checklist_ids) != 1:
            raise ChecklistIncompleteError(
                f"Não foi possível determinar um único checklist para a categoria {category_id}."
            )
        return int(checklist_ids.pop())

    def list_evaluations(
        self,
        checklist_id: int,
        year: int,
        month: int,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> tuple[list[dict[str, Any]], int]:
        """Lista concluídos do mês e deduplica pelo ID, mantendo a versão mais recente."""

        start, end = month_bounds(year, month, timezone_name)
        params = {
            "checklistId": checklist_id,
            "status": 6,
            "deletedAt": "null",
            "concludedAt[gte]": start.isoformat(timespec="seconds"),
            "concludedAt[lte]": (end - timedelta(seconds=1)).isoformat(timespec="seconds"),
        }
        rows = self.iter_paginated("/v1/evaluations", params)
        timezone = ZoneInfo(timezone_name)
        in_period: list[dict[str, Any]] = []
        for row in rows:
            concluded = parse_api_datetime(row.get("concludedAt"))
            if concluded is None:
                continue
            local_concluded = concluded.astimezone(timezone)
            if not (start <= local_concluded < end):
                continue
            if not _same_id(row.get("checklistId"), checklist_id):
                continue
            if _integer(row.get("status")) != 6 or row.get("deletedAt") not in (None, ""):
                continue
            in_period.append(row)

        deduplicated: dict[int, dict[str, Any]] = {}
        for row in in_period:
            evaluation_id = _integer(row.get("evaluationId"))
            if evaluation_id is None:
                raise ChecklistIncompleteError("Uma avaliação foi retornada sem evaluationId válido.")
            current = deduplicated.get(evaluation_id)
            if current is None or _sort_timestamp(row) >= _sort_timestamp(current):
                deduplicated[evaluation_id] = row
        duplicates = len(in_period) - len(deduplicated)
        minimum = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
        ordered = sorted(
            deduplicated.values(),
            key=lambda row: (
                parse_api_datetime(row.get("concludedAt")) or minimum,
                _integer(row.get("evaluationId")) or 0,
            ),
        )
        return ordered, duplicates

    def fetch_month_snapshot(
        self,
        year: int,
        month: int,
        *,
        category_id: int = DEFAULT_CATEGORY_ID,
        timezone_name: str = DEFAULT_TIMEZONE,
    ) -> ChecklistSnapshot:
        """Consulta avaliações, respostas e cadastros necessários para o Excel."""

        checklist_id = self.resolve_checklist_id(category_id)
        evaluations, duplicate_count = self.list_evaluations(checklist_id, year, month, timezone_name)
        items = self.iter_paginated(
            "/v1/items",
            {"checklistId": checklist_id, "categoryId": category_id, "deletedAt": "null"},
        )
        if not evaluations:
            return ChecklistSnapshot(
                category_id, checklist_id, year, month, [], {}, [], [], [], [], [], items, duplicate_count
            )

        evaluation_ids = {int(evaluation["evaluationId"]) for evaluation in evaluations}
        results_by_evaluation = self.list_evaluation_results(
            checklist_id,
            year,
            month,
            evaluation_ids,
            timezone_name,
        )

        return ChecklistSnapshot(
            category_id=category_id,
            checklist_id=checklist_id,
            year=year,
            month=month,
            evaluations=evaluations,
            results_by_evaluation=results_by_evaluation,
            users=self.iter_paginated("/v1/users", {"deletedAt": "null"}),
            user_types=self.iter_paginated("/v1/user-types", {"deletedAt": "null"}),
            units=self.iter_paginated("/v1/units", {"deletedAt": "null"}),
            unit_regions=self.iter_paginated("/v1/units/regions"),
            regions=self.iter_paginated("/v1/regions", {"deletedAt": "null"}),
            items=items,
            duplicate_count=duplicate_count,
        )


def _integer(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _validation_error_detail(response: requests.Response) -> str:
    """Extrai apenas campos/mensagens de validação, nunca cabeçalhos da requisição."""

    try:
        payload = response.json()
    except ValueError:
        return ""
    if not isinstance(payload, dict):
        return ""
    errors = payload.get("errors")
    details: list[str] = []
    if isinstance(errors, dict):
        for field, messages in errors.items():
            if isinstance(messages, list):
                text = "; ".join(str(message) for message in messages)
            else:
                text = str(messages)
            details.append(f"{field}: {text}")
    if details:
        return " | ".join(details)
    message = payload.get("message")
    return str(message) if message else ""


def _same_id(left: object, right: object) -> bool:
    return _integer(left) is not None and _integer(left) == _integer(right)


def _sort_timestamp(row: dict[str, Any]) -> tuple[datetime, datetime]:
    minimum = datetime.min.replace(tzinfo=ZoneInfo("UTC"))
    return (
        parse_api_datetime(row.get("updatedAt")) or minimum,
        parse_api_datetime(row.get("concludedAt")) or minimum,
    )


def index_by_id(rows: Iterable[dict[str, Any]], key: str) -> dict[int, dict[str, Any]]:
    """Indexa cadastros e mantém o registro mais recente para IDs repetidos."""

    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        identifier = _integer(row.get(key))
        if identifier is None:
            continue
        current = indexed.get(identifier)
        if current is None or _sort_timestamp(row) >= _sort_timestamp(current):
            indexed[identifier] = row
    return indexed
