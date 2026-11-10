from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from api.config import ApiSettings
from api.files import GeneratedFileError, TemporaryFileStore
from api.main import create_app
from api.security import create_download_token, verify_download_token
from services.calculador import CalculationResult


class FakeCalculator:
    def __init__(self, workbook: bytes = b"excel-real") -> None:
        self.workbook = workbook
        self.calls: list[tuple[int, int, dict[str, object], int]] = []

    def processar_periodo(self, year, month, *, filters, pix_records, preview_limit):
        self.calls.append((year, month, filters, preview_limit))
        return CalculationResult(
            status="concluido",
            message="Processamento concluído: 1 rota(s) calculada(s).",
            year=year,
            month=month,
            found=1,
            valid=1,
            inconsistent=0,
            duplicates=0,
            calculated=1,
            failed=0,
            metrics={"Total de rotas únicas": 1},
            preview=[{"ID RESPOSTA": 55, "NOME": "Ana"}],
            warnings=(),
            workbook=self.workbook,
            filename=f"checklists_{year}_{month:02d}_tratada.xlsx",
        )


def _settings(tmp_path: Path) -> ApiSettings:
    return ApiSettings(
        inbound_api_key="segredo-copilot",
        file_signing_secret="segredo-arquivos-independente",
        checklist_api_token="token-checklist",
        item_mapping={},
        public_api_base_url="https://api.example.test",
        file_ttl_seconds=900,
        max_generated_file_mb=1,
        temp_directory=tmp_path,
    )


def _app(tmp_path: Path):
    settings = _settings(tmp_path)
    calculator = FakeCalculator()
    store = TemporaryFileStore(tmp_path, ttl_seconds=900, max_size_mb=1)
    return create_app(settings, calculator, store), calculator


def _test_path() -> Path:
    path = Path(".tmp/api-tests") / str(uuid4())
    path.mkdir(parents=True)
    return path


@dataclass
class AsgiResponse:
    status_code: int
    content: bytes
    headers: dict[str, str]

    def json(self):
        return json.loads(self.content.decode("utf-8"))

    @property
    def text(self):
        return self.content.decode("utf-8")


async def _request(app, method: str, url: str, *, headers=None, json_body=None):
    parsed = urlsplit(url)
    body = b"" if json_body is None else json.dumps(json_body).encode("utf-8")
    raw_headers = [(b"host", b"testserver")]
    if json_body is not None:
        raw_headers.append((b"content-type", b"application/json"))
    raw_headers.extend(
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    )
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": parsed.path,
        "raw_path": parsed.path.encode("ascii"),
        "query_string": parsed.query.encode("ascii"),
        "root_path": "",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    messages = []
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await asyncio.wait_for(app(scope, receive, send), timeout=5)
    start = next(message for message in messages if message["type"] == "http.response.start")
    content = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    response_headers = {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in start["headers"]
    }
    return AsgiResponse(start["status"], content, response_headers)


def _sync_request(app, method: str, url: str, *, headers=None, json_body=None):
    return asyncio.run(
        _request(app, method, url, headers=headers, json_body=json_body)
    )


def test_health_is_public_and_reports_configuration():
    app, _ = _app(_test_path())
    response = _sync_request(app, "GET", "/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "servico": "Calculador de Rotas API",
        "versao": "1.0.0",
        "configurado": True,
    }


def test_protected_endpoints_reject_missing_or_wrong_key():
    app, _ = _app(_test_path())
    assert _sync_request(app, "GET", "/api/opcoes").status_code == 401
    response = _sync_request(
        app, "GET", "/api/opcoes", headers={"X-API-Key": "errada"}
    )
    assert response.status_code == 401
    assert response.json()["erro"] == "nao_autorizado"


def test_options_remain_available_before_checklist_credential_is_configured():
    root = _test_path()
    settings = replace(_settings(root), checklist_api_token="")
    app = create_app(
        settings,
        FakeCalculator(),
        TemporaryFileStore(root, ttl_seconds=900, max_size_mb=1),
    )

    options = _sync_request(
        app, "GET", "/api/opcoes", headers={"X-API-Key": "segredo-copilot"}
    )
    assert options.status_code == 200
    assert "processar_periodo" in options.json()["operacoes"]

    process = _sync_request(
        app,
        "POST",
        "/api/processar",
        headers={"X-API-Key": "segredo-copilot"},
        json_body={"ano": 2026, "mes": 10, "pix_por_usuario": []},
    )
    assert process.status_code == 503


def test_process_returns_real_result_and_signed_download():
    root = _test_path()
    app, calculator = _app(root)
    response = _sync_request(
        app,
        "POST",
        "/api/processar",
        headers={"X-API-Key": "segredo-copilot"},
        json_body={
            "ano": 2026,
            "mes": 10,
            "filtros": {"usuario": ["Ana"]},
            "pix_por_usuario": [{"usuario": "ana@exemplo.com", "pix": "pix-teste"}],
            "limite_previa": 5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contagens"]["rotas_calculadas"] == 1
    assert body["indicadores"]["Total de rotas únicas"] == 1
    assert body["previa"][0]["NOME"] == "Ana"
    assert str(root.resolve()) not in response.text
    assert calculator.calls[0][0:2] == (2026, 10)
    assert calculator.calls[0][2]["usuario"] == ["Ana"]

    public_url = body["arquivo"]["url_download"]
    local_path = public_url.removeprefix("https://api.example.test")
    download = _sync_request(app, "GET", local_path)
    assert download.status_code == 200
    assert download.content == b"excel-real"
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "checklists_2026_10_tratada.xlsx" in download.headers["content-disposition"]


def test_invalid_download_token_and_renewal():
    app, _ = _app(_test_path())
    processed = (
        _sync_request(
            app,
            "POST",
            "/api/processar",
            headers={"X-API-Key": "segredo-copilot"},
            json_body={"ano": 2026, "mes": 10, "pix_por_usuario": []},
        )
    ).json()
    file_id = processed["arquivo"]["id"]

    invalid = _sync_request(app, "GET", f"/api/arquivos/{file_id}?token=invalido")
    assert invalid.status_code == 403
    assert invalid.json()["erro"] == "link_invalido"

    renewed = _sync_request(
        app,
        "POST",
        "/api/gerar-planilha",
        headers={"X-API-Key": "segredo-copilot"},
        json_body={"arquivo_id": file_id},
    )
    assert renewed.status_code == 200
    assert renewed.json()["arquivo"]["id"] == file_id


def test_validation_errors_are_safe_and_understandable():
    app, _ = _app(_test_path())
    response = _sync_request(
        app,
        "POST",
        "/api/processar",
        headers={"X-API-Key": "segredo-copilot"},
        json_body={"ano": 2026, "mes": 13, "campo_inventado": True},
    )
    assert response.status_code == 422
    assert response.json()["erro"] == "parametros_invalidos"
    assert "segredo-copilot" not in response.text

    outside_month = _sync_request(
        app,
        "POST",
        "/api/processar",
        headers={"X-API-Key": "segredo-copilot"},
        json_body={
            "ano": 2026,
            "mes": 10,
            "filtros": {"data_inicio": "2026-09-30"},
        },
    )
    assert outside_month.status_code == 422
    assert outside_month.json()["erro"] == "parametros_invalidos"


def test_copilot_contract_is_swagger_2_and_contains_security():
    contract = json.loads(Path("openapi-copilot.json").read_text(encoding="utf-8"))
    assert contract["swagger"] == "2.0"
    assert contract["securityDefinitions"]["apiKeyHeader"]["name"] == "X-API-Key"
    assert contract["paths"]["/processar"]["post"]["operationId"] == "processarPeriodo"
    assert contract["paths"]["/arquivos/{file_id}"]["get"]["security"] == []


def test_signed_token_and_temporary_file_expire():
    root = _test_path()
    store = TemporaryFileStore(root, ttl_seconds=60, max_size_mb=1)
    stored = store.save(b"arquivo", "resultado.xlsx", now=100)
    token = create_download_token("segredo", stored.file_id, stored.expires_at)

    assert verify_download_token("segredo", stored.file_id, token, now=159) == 160
    assert verify_download_token("segredo", stored.file_id, token, now=161) is None
    try:
        store.get(stored.file_id, now=161)
    except GeneratedFileError as exc:
        assert "expirou" in str(exc)
    else:
        raise AssertionError("O arquivo expirado permaneceu acessível")
    assert not stored.path.exists()
