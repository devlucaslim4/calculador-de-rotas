"""Ponto de entrada ASGI da API do Calculador de Rotas."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from api.config import ApiSettings
from api.files import TemporaryFileStore
from api.routes import build_router
from services.calculador import CalculadorService


def create_app(
    settings: ApiSettings | None = None,
    calculator: CalculadorService | None = None,
    store: TemporaryFileStore | None = None,
) -> FastAPI:
    resolved = settings or ApiSettings.from_environment()
    service = calculator or CalculadorService(resolved)
    file_store = store or TemporaryFileStore(
        resolved.temp_directory,
        ttl_seconds=resolved.file_ttl_seconds,
        max_size_mb=resolved.max_generated_file_mb,
    )
    application = FastAPI(
        title="Calculador de Rotas API",
        summary="API externa para o Microsoft Copilot Studio e Microsoft Teams.",
        description=(
            "Expõe o motor existente de importação, cálculo e geração de Excel. "
            "A interface Streamlit permanece independente."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    @application.get(
        "/openapi-copilot.json",
        include_in_schema=False,
        response_class=FileResponse,
    )
    async def copilot_openapi_definition() -> FileResponse:
        """Disponibiliza a especificação Swagger 2.0 compatível com o Copilot Studio."""
        specification = Path(__file__).resolve().parents[1] / "openapi-copilot.json"
        return FileResponse(specification, media_type="application/json")

    @application.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "erro" in exc.detail:
            body = exc.detail
        else:
            body = {"erro": "erro_http", "mensagem": str(exc.detail)}
        return JSONResponse(status_code=exc.status_code, content=body, headers=exc.headers)

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "campo": ".".join(str(part) for part in error["loc"] if part != "body"),
                "mensagem": error["msg"],
                "tipo": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "erro": "parametros_invalidos",
                "mensagem": "Revise os parâmetros enviados.",
                "detalhes": details,
            },
        )

    application.include_router(build_router(resolved, service, file_store))
    return application


app = create_app()
