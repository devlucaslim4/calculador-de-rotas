"""Rotas HTTP da integração com o Microsoft Copilot Studio."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from functools import partial
from urllib.parse import quote
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.responses import Response
from fastapi.security import APIKeyHeader

from api.config import ApiSettings
from api.files import GeneratedFileError, StoredFile, TemporaryFileStore
from api.schemas import (
    ArquivoTemporario,
    Contagens,
    GerarPlanilhaRequest,
    GerarPlanilhaResponse,
    HealthResponse,
    OpcoesResponse,
    Periodo,
    ProcessarRequest,
    ProcessarResponse,
)
from api.security import api_key_matches, create_download_token, verify_download_token
from checklist_api import ChecklistApiError, ChecklistAuthenticationError
from checklist_transform import ChecklistTransformationError
from route_processor import SpreadsheetError
from services.calculador import CalculationResult, CalculadorService

LOGGER = logging.getLogger(__name__)
EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MONTHS = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _problem(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"erro": code, "mensagem": message})


def build_router(
    settings: ApiSettings,
    calculator: CalculadorService,
    store: TemporaryFileStore,
) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["Calculador de Rotas"])

    async def require_api_key(provided: str | None = Security(api_key_header)) -> None:
        if not settings.ready:
            raise _problem(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "servico_nao_configurado",
                "A API ainda não foi configurada pelo administrador.",
            )
        if not api_key_matches(settings.inbound_api_key, provided):
            raise _problem(
                status.HTTP_401_UNAUTHORIZED,
                "nao_autorizado",
                "Chave de acesso ausente ou inválida.",
            )

    @router.get(
        "/health",
        response_model=HealthResponse,
        summary="Verificar disponibilidade da API",
        description="Use para confirmar que o serviço HTTP está ativo e configurado.",
    )
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok" if settings.ready else "configuracao_pendente",
            servico="Calculador de Rotas API",
            versao="1.0.0",
            configurado=settings.ready,
        )

    @router.get(
        "/opcoes",
        response_model=OpcoesResponse,
        dependencies=[Depends(require_api_key)],
        summary="Listar parâmetros aceitos",
        description=(
            "Retorna somente operações, meses e filtros que o motor atual realmente suporta. "
            "Não consulta nem processa checklists."
        ),
    )
    async def opcoes() -> OpcoesResponse:
        return OpcoesResponse(
            operacoes=["processar_periodo", "baixar_planilha", "renovar_link_planilha"],
            meses=[{"numero": index, "nome": name} for index, name in enumerate(MONTHS, 1)],
            filtros_suportados=[
                "data_inicio",
                "data_fim",
                "usuario",
                "unidade",
                "regiao",
                "motivo",
                "centro_custo",
                "status",
            ],
            categoria=settings.category_id,
            fuso_horario=settings.timezone_name,
            limite_previa=50,
            validade_link_segundos=settings.file_ttl_seconds,
        )

    @router.post(
        "/processar",
        response_model=ProcessarResponse,
        dependencies=[Depends(require_api_key)],
        summary="Importar checklists e calcular rotas",
        description=(
            "Consulta os checklists concluídos do mês, aplica o tratamento existente, "
            "calcula distâncias GPS, hodômetro e percentual de diferença, e devolve "
            "indicadores reais com um link temporário para o mesmo Excel produzido pelo app."
        ),
    )
    async def processar(payload: ProcessarRequest, request: Request) -> ProcessarResponse:
        current_year = datetime.now(ZoneInfo(settings.timezone_name)).year
        if payload.ano > current_year + 1:
            raise _problem(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "periodo_invalido",
                f"O ano não pode ser maior que {current_year + 1}.",
            )
        try:
            result = await asyncio.to_thread(
                partial(
                    calculator.processar_periodo,
                    payload.ano,
                    payload.mes,
                    filters=payload.filtros.model_dump(),
                    preview_limit=payload.limite_previa,
                )
            )
            return _process_response(result, request, settings, store)
        except ChecklistAuthenticationError as exc:
            raise _problem(
                status.HTTP_502_BAD_GATEWAY,
                "credencial_checklist_rejeitada",
                str(exc),
            ) from exc
        except ChecklistApiError as exc:
            raise _problem(status.HTTP_502_BAD_GATEWAY, "falha_checklist_facil", str(exc)) from exc
        except (ChecklistTransformationError, SpreadsheetError) as exc:
            raise _problem(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "dados_incompativeis",
                str(exc),
            ) from exc
        except GeneratedFileError as exc:
            raise _problem(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                "arquivo_nao_armazenado",
                str(exc),
            ) from exc
        except Exception as exc:
            LOGGER.exception("Falha inesperada no processamento solicitado pela API")
            raise _problem(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "erro_interno",
                "Não foi possível concluir o processamento. Tente novamente em alguns instantes.",
            ) from exc

    @router.post(
        "/gerar-planilha",
        response_model=GerarPlanilhaResponse,
        dependencies=[Depends(require_api_key)],
        summary="Renovar o link de uma planilha processada",
        description=(
            "Gera um novo link temporário para uma planilha criada por /api/processar, "
            "sem recalcular as rotas."
        ),
    )
    async def gerar_planilha(
        payload: GerarPlanilhaRequest, request: Request
    ) -> GerarPlanilhaResponse:
        try:
            stored = store.renew(payload.arquivo_id)
        except GeneratedFileError as exc:
            raise _problem(status.HTTP_404_NOT_FOUND, "arquivo_indisponivel", str(exc)) from exc
        return GerarPlanilhaResponse(
            mensagem="Novo link temporário gerado com sucesso.",
            arquivo=_file_response(stored, request, settings),
        )

    @router.get(
        "/arquivos/{file_id}",
        response_class=Response,
        summary="Baixar uma planilha por link assinado",
        description=(
            "Baixa o Excel usando o token curto presente no próprio link. O token expira e "
            "não expõe caminhos locais nem a chave usada pelo Copilot Studio."
        ),
    )
    async def baixar_arquivo(file_id: str, token: str) -> Response:
        if not settings.file_signing_secret:
            raise _problem(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "servico_nao_configurado",
                "A assinatura de arquivos ainda não foi configurada.",
            )
        if verify_download_token(settings.file_signing_secret, file_id, token) is None:
            raise _problem(
                status.HTTP_403_FORBIDDEN,
                "link_invalido",
                "O link da planilha é inválido ou expirou.",
            )
        try:
            stored = store.get(file_id)
        except GeneratedFileError as exc:
            raise _problem(status.HTTP_404_NOT_FOUND, "arquivo_indisponivel", str(exc)) from exc
        return Response(
            content=stored.path.read_bytes(),
            media_type=EXCEL_MIME,
            headers={
                "Cache-Control": "private, no-store, max-age=0",
                "Content-Disposition": (
                    "attachment; filename*=UTF-8''" + quote(stored.filename, safe="")
                ),
            },
        )

    return router


def _process_response(
    result: CalculationResult,
    request: Request,
    settings: ApiSettings,
    store: TemporaryFileStore,
) -> ProcessarResponse:
    file_data = None
    if result.workbook is not None and result.filename is not None:
        stored = store.save(result.workbook, result.filename)
        file_data = _file_response(stored, request, settings)
    return ProcessarResponse(
        status=result.status,
        mensagem=result.message,
        periodo=Periodo(ano=result.year, mes=result.month),
        contagens=Contagens(
            encontrados=result.found,
            validos_para_rota=result.valid,
            inconsistentes=result.inconsistent,
            duplicados_consolidados=result.duplicates,
            rotas_calculadas=result.calculated,
            rotas_nao_calculadas=result.failed,
        ),
        indicadores=result.metrics,
        previa=result.preview,
        avisos=list(result.warnings),
        arquivo=file_data,
    )


def _file_response(
    stored: StoredFile,
    request: Request,
    settings: ApiSettings,
) -> ArquivoTemporario:
    base_url = settings.public_api_base_url or str(request.base_url).rstrip("/")
    token = create_download_token(
        settings.file_signing_secret,
        stored.file_id,
        stored.expires_at,
    )
    download_url = f"{base_url}/api/arquivos/{stored.file_id}?token={quote(token, safe='.')}"
    expires = datetime.fromtimestamp(stored.expires_at, tz=timezone.utc).isoformat()
    return ArquivoTemporario(
        id=stored.file_id,
        nome=stored.filename,
        url_download=download_url,
        expira_em=expires,
    )
